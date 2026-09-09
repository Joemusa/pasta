-- SA Home Care Intelligence — Supabase schema
-- Apply in the Supabase SQL editor. The Next.js UI reads via intelligenceService;
-- point that layer at these tables when NEXT_PUBLIC_SUPABASE_URL is set.

create table if not exists public.intelligence_signals (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source text not null,
  source_url text,
  published_at timestamptz,
  detected_at timestamptz not null default now(),
  signal_type text not null,
  category text,
  brand text,
  retailer text,
  province text,
  summary text,
  why_it_matters text,
  fact text,
  interpretation text,
  recommendation text,
  suggested_internal_query text,
  severity text not null check (severity in ('low', 'medium', 'high', 'critical')),
  confidence text not null check (confidence in ('low', 'medium', 'high')),
  commercial_impact text not null default 'unvalidated',
  raw_content text,
  source_type text,
  sentiment text,
  relevance_score integer,
  importance_score integer,
  attention text,
  author text,
  author_handle text,
  engagement jsonb,
  hashtags text[],
  search_query text,
  topic text,
  created_at timestamptz not null default now()
);

create table if not exists public.competitors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  company text,
  category text,
  active boolean not null default true
);

create table if not exists public.retailers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text,
  active boolean not null default true
);

create table if not exists public.opportunities (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  category text,
  brand text,
  opportunity_score integer not null check (opportunity_score between 0 and 100),
  impact text,
  confidence text,
  evidence jsonb not null default '[]'::jsonb,
  recommended_action text,
  status text not null default 'open',
  created_at timestamptz not null default now()
);

create table if not exists public.macro_triggers (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  type text,
  location text,
  severity text,
  start_date date,
  end_date date,
  description text,
  potential_homecare_impact text
);

create table if not exists public.internal_queries (
  id uuid primary key default gen_random_uuid(),
  signal_id uuid references public.intelligence_signals(id),
  query text not null,
  agent text,
  response jsonb,
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

create table if not exists public.news_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  url text not null,
  region text,
  active boolean not null default true
);

alter table public.intelligence_signals enable row level security;
alter table public.competitors enable row level security;
alter table public.retailers enable row level security;
alter table public.opportunities enable row level security;
alter table public.macro_triggers enable row level security;
alter table public.internal_queries enable row level security;
alter table public.news_sources enable row level security;

create table if not exists public.intelligence_feed (
  id text primary key,
  last_scan_at timestamptz,
  signals jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.intelligence_feed enable row level security;

drop policy if exists "public read intelligence feed" on public.intelligence_feed;
create policy "public read intelligence feed"
  on public.intelligence_feed
  for select
  using (true);

grant select on public.intelligence_feed to anon, authenticated;
grant all on public.intelligence_feed to service_role;

-- Live scan ids are not UUIDs. Store the whole feed as one JSONB snapshot
-- so every Vercel instance can read the same last-good Home Care scan.
comment on table public.intelligence_feed is
  'Latest live Home Care scan snapshot shared across serverless instances';

alter table public.intelligence_signals add column if not exists source_type text;
alter table public.intelligence_signals add column if not exists sentiment text;
alter table public.intelligence_signals add column if not exists relevance_score integer;
alter table public.intelligence_signals add column if not exists importance_score integer;
alter table public.intelligence_signals add column if not exists attention text;
alter table public.intelligence_signals add column if not exists author text;
alter table public.intelligence_signals add column if not exists author_handle text;
alter table public.intelligence_signals add column if not exists engagement jsonb;
alter table public.intelligence_signals add column if not exists hashtags text[];
alter table public.intelligence_signals add column if not exists search_query text;
alter table public.intelligence_signals add column if not exists topic text;
