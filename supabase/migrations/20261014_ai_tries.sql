-- Toolverse: ONE daily-limit system for every AI tool (Captions, CV Generator AI help, later
-- the CV Checker). Run once in the Supabase SQL Editor, after 20261012_captions.sql.
-- It works whether or not 20261013_captions_limits.sql was run, and replaces its objects.
--
-- How it works (same idea as the caption limits, now with a `tool` column):
--   * Every AI try is its own row with a secret id. The app reserves a try BEFORE calling the
--     AI and gives back exactly that try (by id) if the AI fails.
--   * Per-tool limits: a guest / user gets N tries a day for each tool (numbers come from the
--     app's config).
--   * One site-wide limit across ALL tools together, so Gemini's free daily quota is never used up.
--   * RLS is ON with NO policies: nobody reads or writes the table directly, only through the
--     functions below. Guests are counted by an HMAC of their IP (made with the app's
--     SECRET_KEY), never the raw IP; users by auth.uid() from their own token.
--   * Days are UTC (Supabase runs Postgres in UTC).
-- Today's caption counts start again from zero after this runs (one-time, harmless).

-- Old caption-only objects (both versions).
drop function if exists public.consume_caption_try(text, int);
drop function if exists public.refund_caption_try(text);
drop table if exists public.caption_usage;
drop function if exists public.consume_caption_try(text, int, int);
drop function if exists public.refund_caption_try(uuid);
drop function if exists public.caption_tries_used(text);
drop function if exists public.caption_subject(text);
drop table if exists public.caption_tries;

create table public.ai_tries (
  id         uuid primary key default gen_random_uuid(),
  tool       text not null check (tool in ('captions', 'cv_writer')),
  subject    text not null,                 -- 'user:<uuid>' or 'ip:<hmac>'
  day        date not null default current_date,
  created_at timestamptz not null default now()
);
create index ai_tries_tool_subject_day_idx on public.ai_tries (tool, subject, day);
create index ai_tries_day_idx on public.ai_tries (day);
alter table public.ai_tries enable row level security;
revoke all on public.ai_tries from anon, authenticated;

-- Who is asking: the signed-in user if there is one, otherwise the guest's IP hash.
create or replace function public.ai_subject(p_ip_hash text)
returns text language sql stable security definer set search_path = '' as $$
  select coalesce('user:' || auth.uid()::text, 'ip:' || nullif(btrim(p_ip_hash), ''));
$$;

-- Use one try of `p_tool`.
-- Returns {"status": "ok" | "limit" | "site_limit", "try_id": uuid|null, "used": int}.
-- One lock for the whole table keeps the counts exact when many requests arrive at once
-- (fine for a few thousand tries a day).
create or replace function public.consume_ai_try(p_tool text, p_ip_hash text, p_limit int, p_site_limit int)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_subject text := public.ai_subject(p_ip_hash);
  v_used int;
  v_site int;
  v_id uuid;
begin
  if v_subject is null then
    raise exception 'ai_subject_missing';
  end if;
  if p_tool is null or p_tool not in ('captions', 'cv_writer') then
    raise exception 'ai_tool_unknown';
  end if;

  perform pg_advisory_xact_lock(hashtext('public.ai_tries'));

  -- Old rows are never needed again; the day index makes this cheap.
  delete from public.ai_tries where day < current_date - 30;

  select count(*) into v_used from public.ai_tries
  where tool = p_tool and subject = v_subject and day = current_date;
  if v_used >= p_limit then
    return jsonb_build_object('status', 'limit', 'try_id', null, 'used', v_used);
  end if;

  select count(*) into v_site from public.ai_tries where day = current_date;
  if v_site >= p_site_limit then
    return jsonb_build_object('status', 'site_limit', 'try_id', null, 'used', v_used);
  end if;

  insert into public.ai_tries (tool, subject) values (p_tool, v_subject) returning id into v_id;
  return jsonb_build_object('status', 'ok', 'try_id', v_id, 'used', v_used + 1);
end $$;

-- Give back one try (the AI call failed). Needs the secret id that consume_ai_try returned.
create or replace function public.refund_ai_try(p_try_id uuid)
returns void language sql security definer set search_path = '' as $$
  delete from public.ai_tries where id = p_try_id and day = current_date;
$$;

-- How many tries of `p_tool` this guest/user has used today (for "X tries left").
create or replace function public.ai_tries_used(p_tool text, p_ip_hash text)
returns int language sql stable security definer set search_path = '' as $$
  select count(*)::int from public.ai_tries
  where tool = p_tool and subject = public.ai_subject(p_ip_hash) and day = current_date;
$$;

revoke all on function public.ai_subject(text) from public, anon, authenticated;
revoke all on function public.consume_ai_try(text, text, int, int), public.refund_ai_try(uuid),
  public.ai_tries_used(text, text) from public;
grant execute on function public.consume_ai_try(text, text, int, int), public.refund_ai_try(uuid),
  public.ai_tries_used(text, text) to anon, authenticated;
