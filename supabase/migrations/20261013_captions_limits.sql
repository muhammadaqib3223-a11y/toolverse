-- Toolverse: Caption Generator daily limits, version 2. Run once in the Supabase SQL Editor,
-- AFTER 20261012_captions.sql.
--
-- What changes and why:
--   1. A site-wide daily limit (all guests + users together), so Gemini's free quota is never used up.
--   2. Every try is now its own row with a secret id. A failed AI call gives back exactly that
--      try. (The old refund_caption_try() let a logged-in user call it directly and reset their
--      own counter forever.)
--
-- The table has Row Level Security ON and NO policies: nobody can read or write it directly,
-- only through the functions below. Guests are counted by an HMAC of their IP (made with the
-- app's SECRET_KEY), never the raw IP; users by auth.uid() from their own token.
-- Days are UTC (Supabase runs Postgres in UTC).

drop function if exists public.consume_caption_try(text, int);
drop function if exists public.refund_caption_try(text);
drop table if exists public.caption_usage;

create table public.caption_tries (
  id         uuid primary key default gen_random_uuid(),
  subject    text not null,                 -- 'user:<uuid>' or 'ip:<hmac>'
  day        date not null default current_date,
  created_at timestamptz not null default now()
);
create index caption_tries_subject_day_idx on public.caption_tries (subject, day);
create index caption_tries_day_idx on public.caption_tries (day);
alter table public.caption_tries enable row level security;

-- Who is asking: the signed-in user if there is one, otherwise the guest's IP hash.
create or replace function public.caption_subject(p_ip_hash text)
returns text language sql stable security definer set search_path = '' as $$
  select coalesce('user:' || auth.uid()::text, 'ip:' || nullif(btrim(p_ip_hash), ''));
$$;

-- Use one try. Returns {"status": "ok" | "limit" | "site_limit", "try_id": uuid|null, "used": int}.
-- One lock for the whole table keeps the counts exact when many requests arrive at once
-- (fine for a few thousand tries a day).
create or replace function public.consume_caption_try(p_ip_hash text, p_limit int, p_site_limit int)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_subject text := public.caption_subject(p_ip_hash);
  v_used int;
  v_site int;
  v_id uuid;
begin
  if v_subject is null then
    raise exception 'caption_subject_missing';
  end if;

  perform pg_advisory_xact_lock(hashtext('public.caption_tries'));

  -- Old rows are never needed again; the day index makes this cheap.
  delete from public.caption_tries where day < current_date - 30;

  select count(*) into v_used from public.caption_tries where subject = v_subject and day = current_date;
  if v_used >= p_limit then
    return jsonb_build_object('status', 'limit', 'try_id', null, 'used', v_used);
  end if;

  select count(*) into v_site from public.caption_tries where day = current_date;
  if v_site >= p_site_limit then
    return jsonb_build_object('status', 'site_limit', 'try_id', null, 'used', v_used);
  end if;

  insert into public.caption_tries (subject) values (v_subject) returning id into v_id;
  return jsonb_build_object('status', 'ok', 'try_id', v_id, 'used', v_used + 1);
end $$;

-- Give back one try (the AI call failed). Needs the secret id that consume_caption_try returned.
create or replace function public.refund_caption_try(p_try_id uuid)
returns void language sql security definer set search_path = '' as $$
  delete from public.caption_tries where id = p_try_id and day = current_date;
$$;

-- How many tries this guest/user has used today (for "X tries left").
create or replace function public.caption_tries_used(p_ip_hash text)
returns int language sql stable security definer set search_path = '' as $$
  select count(*)::int from public.caption_tries
  where subject = public.caption_subject(p_ip_hash) and day = current_date;
$$;

revoke all on function public.caption_subject(text) from public, anon, authenticated;
revoke all on function public.consume_caption_try(text, int, int), public.refund_caption_try(uuid),
  public.caption_tries_used(text) from public;
grant execute on function public.consume_caption_try(text, int, int), public.refund_caption_try(uuid),
  public.caption_tries_used(text) to anon, authenticated;
