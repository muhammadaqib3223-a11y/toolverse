create table expenses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  client_id   text,
  amount      numeric(14,2) not null check (amount > 0),
  description text not null,
  currency    text not null default 'PKR',
  spent_at    date not null default current_date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, client_id)
);

alter table expenses enable row level security;

create policy "owner select" on expenses for select using (auth.uid() = user_id);
create policy "owner insert" on expenses for insert with check (auth.uid() = user_id);
create policy "owner update" on expenses for update using (auth.uid() = user_id);
create policy "owner delete" on expenses for delete using (auth.uid() = user_id);

create index expenses_user_month on expenses (user_id, date_trunc('month', spent_at));
