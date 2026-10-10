-- Toolverse: Notes table (Phase 3)
-- Run once in the Supabase SQL Editor. See docs/phase2-plan.md for how Supabase is set up,
-- and CLAUDE.md section 8 for how this project's auth/data access works.

create table public.notes (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title       text not null check (char_length(btrim(title)) between 1 and 200),
  content     text not null default '' check (char_length(content) <= 20000),
  client_id   uuid,  -- a guest note's id from the browser, so moving it into the account twice never duplicates it
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint notes_user_client_unique unique (user_id, client_id)
);

-- Fast "my notes, newest first".
create index notes_user_updated_idx on public.notes (user_id, updated_at desc);

-- updated_at changes automatically on every edit.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger notes_set_updated_at
before update on public.notes
for each row execute function public.set_updated_at();

-- Row Level Security: every user sees and changes only their own notes.
alter table public.notes enable row level security;

create policy "Users can read their own notes"
  on public.notes for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can add their own notes"
  on public.notes for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can edit their own notes"
  on public.notes for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own notes"
  on public.notes for delete to authenticated
  using ((select auth.uid()) = user_id);

-- Extra safety: logged-out visitors get nothing, and a user may only write the columns the
-- app actually sends (user_id always comes from the database default, never from the app).
revoke all on public.notes from anon;
revoke insert, update on public.notes from authenticated;
grant insert (title, content, client_id) on public.notes to authenticated;
grant update (title, content) on public.notes to authenticated;
