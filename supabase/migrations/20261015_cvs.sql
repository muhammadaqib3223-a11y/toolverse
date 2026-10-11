-- Toolverse: saved CVs (Phase 6B). Run once in the Supabase SQL Editor, after
-- 20261010_notes.sql (it reuses public.set_updated_at()).
--
-- A logged-in user can keep several CVs (max 20). Each row holds the whole form as JSON
-- (personal details, summary, experience, education, skills) plus the chosen template,
-- accent colour and CV language. The app checks the JSON's shape and sizes; the database
-- guards the basics. Row Level Security: every user sees and changes only their own CVs.

create table public.cvs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title       text not null check (char_length(btrim(title)) between 1 and 120),
  data        jsonb not null default '{}'::jsonb
              check (jsonb_typeof(data) = 'object' and octet_length(data::text) <= 100000),
  template    text not null default 'modern' check (template ~ '^[a-z]{1,20}$'),
  accent      text not null default 'indigo' check (accent ~ '^[a-z]{1,20}$'),
  language    text not null default 'en' check (language in ('en', 'ur')),
  client_id   uuid,  -- a guest CV's id from the browser, so moving it into the account twice never duplicates it
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint cvs_user_client_unique unique (user_id, client_id)
);

-- Fast "my CVs, newest first".
create index cvs_user_updated_idx on public.cvs (user_id, updated_at desc);

-- updated_at changes automatically on every edit (function from 20261010_notes.sql).
create trigger cvs_set_updated_at
before update on public.cvs
for each row execute function public.set_updated_at();

-- At most 20 CVs per user, checked inside the database so two tabs saving at once can't go over.
create or replace function public.cvs_enforce_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform pg_advisory_xact_lock(hashtext('public.cvs:' || new.user_id::text));
  if (select count(*) from public.cvs where user_id = new.user_id) >= 20 then
    raise exception 'cv_limit_reached' using errcode = 'P0001';
  end if;
  return new;
end;
$$;

create trigger cvs_limit
before insert on public.cvs
for each row execute function public.cvs_enforce_limit();

-- Row Level Security.
alter table public.cvs enable row level security;

create policy "Users can read their own CVs"
  on public.cvs for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can add their own CVs"
  on public.cvs for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can edit their own CVs"
  on public.cvs for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own CVs"
  on public.cvs for delete to authenticated
  using ((select auth.uid()) = user_id);

-- Extra safety: logged-out visitors get nothing, and a user may only write the columns the
-- app actually sends (user_id always comes from the database default, never from the app).
revoke all on public.cvs from anon;
revoke insert, update on public.cvs from authenticated;
grant insert (title, data, template, accent, language, client_id) on public.cvs to authenticated;
grant update (title, data, template, accent, language) on public.cvs to authenticated;
revoke all on function public.cvs_enforce_limit() from public, anon, authenticated;
