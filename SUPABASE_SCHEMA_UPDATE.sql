-- Add columns for new NLP fields and favorites
alter table public.articles
  add column if not exists summary_zh text,
  add column if not exists key_points jsonb,
  add column if not exists trend_tag text,
  add column if not exists heat_score numeric,
  add column if not exists is_favorite boolean default false,
  add column if not exists favorite_analysis text;

-- RLS policies for public favorite update (anon key)
-- Enable RLS if not already enabled
alter table public.articles enable row level security;

-- Allow public read
create policy if not exists "public_select" on public.articles
  for select using (true);

-- Allow public to set favorites (simple policy)
create policy if not exists "public_favorite_update" on public.articles
  for update using (true)
  with check (is_favorite = true);
