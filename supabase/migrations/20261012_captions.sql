-- Toolverse: Caption Generator (Phase 5) — history table + first version of the daily counter.
-- Run once in the Supabase SQL Editor. The counter part is replaced by 20261013_captions_limits.sql.

-- History (logged-in only)
create table public.captions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  topic      text not null check (char_length(btrim(topic)) between 1 and 500),
  platform   text not null check (platform in ('instagram', 'linkedin')),
  captions   jsonb not null check (jsonb_typeof(captions) = 'array'),
  created_at timestamptz not null default now()
);
create index captions_user_created_idx on public.captions (user_id, created_at desc);
alter table public.captions enable row level security;
create policy "owner select" on public.captions for select using (auth.uid() = user_id);
create policy "owner insert" on public.captions for insert with check (auth.uid() = user_id);
create policy "owner delete" on public.captions for delete using (auth.uid() = user_id);

-- Daily usage counter (guests by IP hash, users by id). RLS on, NO policies:
-- nobody reads/writes it directly, only via the functions below.
create table public.caption_usage (
  subject text not null,          -- 'ip:<hmac>' or 'user:<uuid>'
  day     date not null default current_date,
  count   int  not null default 0,
  primary key (subject, day)
);
alter table public.caption_usage enable row level security;

-- Atomically use one try. Returns tries used (or -1 if limit already reached).
create or replace function public.consume_caption_try(p_ip_hash text, p_limit int)
returns int language plpgsql security definer set search_path = '' as $$
declare
  v_subject text := coalesce('user:' || auth.uid()::text, 'ip:' || p_ip_hash);
  v_count int;
begin
  insert into public.caption_usage (subject, day, count) values (v_subject, current_date, 1)
  on conflict (subject, day) do update set count = public.caption_usage.count + 1
    where public.caption_usage.count < p_limit
  returning count into v_count;
  return coalesce(v_count, -1);
end $$;

-- Give the try back when the AI call fails.
create or replace function public.refund_caption_try(p_ip_hash text)
returns void language sql security definer set search_path = '' as $$
  update public.caption_usage set count = greatest(count - 1, 0)
  where subject = coalesce('user:' || auth.uid()::text, 'ip:' || p_ip_hash) and day = current_date;
$$;

revoke all on function public.consume_caption_try(text, int), public.refund_caption_try(text) from public;
grant execute on function public.consume_caption_try(text, int), public.refund_caption_try(text) to anon, authenticated;
