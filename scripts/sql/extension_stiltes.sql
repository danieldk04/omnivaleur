create table if not exists extension_stiltes (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  stil_van timestamptz not null,
  stil_tot timestamptz not null,
  minuten numeric,
  ext_version text,
  user_agent text,
  created_at timestamptz not null default now()
);
create index if not exists extension_stiltes_user_tot on extension_stiltes (user_id, stil_tot desc);
alter table extension_stiltes enable row level security;
