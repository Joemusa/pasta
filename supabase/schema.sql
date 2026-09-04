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
