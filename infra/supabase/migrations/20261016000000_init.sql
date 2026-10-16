-- Break the Gate: initial schema (docs/PRD.md section 8).
-- No schema qualification, so tests can apply it into a throwaway schema.
-- The API connects as the table owner (server side only); RLS with no policies
-- plus revoked grants keeps Supabase's public anon/authenticated roles out.

create table sessions (
  id uuid primary key default gen_random_uuid(),
  handle text check (handle is null or char_length(handle) between 3 and 20),
  consent_training boolean not null default false,
  ip_hash text,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table attempts (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  level smallint not null check (level between 1 and 5),
  goal_id smallint not null check (goal_id between 1 and 12),
  task text not null check (char_length(task) <= 300),
  command text not null check (char_length(command) <= 1000),
  approved boolean not null,
  p_safe real not null,
  threshold real not null,
  deciding_layer text not null,
  layers jsonb not null,
  verified boolean,                        -- null only if the verifier was unavailable (denials only)
  verify_p real,                           -- same rule as verified
  verify_cache_hit boolean not null default false,
  points integer not null default 0 check (points >= 0),
  gate_version text not null,
  latency_ms integer,
  consent_training boolean not null,       -- copied at attempt time
  created_at timestamptz not null default now()
);
create index attempts_level_created_idx on attempts (level, created_at);
create index attempts_session_created_idx on attempts (session_id, created_at);

create table evals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  gate_version text not null,
  payload jsonb not null,                  -- the eval JSON the report page shows
  file_hash text not null
);

create table reveals (
  id uuid primary key default gen_random_uuid(),
  attempt_id uuid not null references attempts(id) on delete cascade,
  session_id uuid not null references sessions(id) on delete cascade,
  level smallint not null,
  variant text not null default 'standard' check (variant in ('standard', 'legendary')),
  expires_at timestamptz not null,
  claimed_at timestamptz,
  needs_review boolean not null default false,
  created_at timestamptz not null default now(),
  unique (session_id, level)
);

create table idempotency_keys (
  session_id uuid not null references sessions(id) on delete cascade,
  key text not null check (char_length(key) between 8 and 64),
  request_hash text not null,              -- SHA-256 of the canonical JSON body
  status text not null default 'in_progress' check (status in ('in_progress', 'done')),
  response jsonb,                          -- stored 200 body, set when done
  created_at timestamptz not null default now(),
  primary key (session_id, key)
);

-- Running daily spend for the budget guard (PRD 4.3), UTC days. Estimates from
-- token counts and configured prices; reconcile against Endor usage rows.
create table spend_daily (
  day date primary key,
  input_tokens bigint not null default 0,
  usd numeric(12, 6) not null default 0
);

-- security_invoker: the view runs with the caller's rights, so RLS still applies.
create view leaderboard with (security_invoker = true) as
  select a.level,
         a.session_id,                     -- for joins only, never returned by the API
         s.handle,
         sum(a.points) as score,
         count(*) as attempts,
         min(a.created_at) filter (where a.points > 0) as first_win_at
  from attempts a join sessions s on s.id = a.session_id
  where s.deleted_at is null and s.handle is not null
  group by a.level, a.session_id, s.handle;

alter table sessions enable row level security;
alter table attempts enable row level security;
alter table evals enable row level security;
alter table reveals enable row level security;
alter table idempotency_keys enable row level security;
alter table spend_daily enable row level security;

-- Supabase's API roles get nothing. Guarded so plain Postgres (tests) works too.
do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on sessions, attempts, evals, reveals, idempotency_keys, spend_daily, leaderboard from %I', r);
    end if;
  end loop;
end $$;
