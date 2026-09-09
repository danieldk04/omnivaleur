-- Meetlaag voor influencer- en affiliate-samenwerkingen (besloten 09-09-2026).
-- Draai dit één keer in de Supabase SQL editor.
--
-- Wat hier bewust NIET staat: de status van de klant. Die komt altijd vers uit
-- `subscriptions`. Status op twee plekken bijhouden loopt gegarandeerd uit de
-- pas, en dan betaal je commissie voor iemand die allang weg is.

create table if not exists referral_codes (
    code            text primary key,
    creator_name    text        not null default '',
    platform        text        not null default '',
    profile_url     text        not null default '',
    -- Bounty per klant die 60 dagen betaald heeft. Standaard 25 euro.
    bounty_cents    integer     not null default 2500,
    -- Eventueel vast bedrag dat vooraf betaald is, voor de kosten per klant.
    fee_paid_cents  integer     not null default 0,
    active          boolean     not null default true,
    created_at      timestamptz not null default now()
);

create table if not exists referrals (
    user_id        uuid        primary key references auth.users (id) on delete cascade,
    code           text        not null references referral_codes (code),
    created_at     timestamptz not null default now(),
    -- Wordt één keer gestempeld door de Stripe-webhook zodra er echt betaald
    -- wordt. Hier begint de 60 dagen te lopen.
    first_paid_at  timestamptz
);
create index if not exists referrals_code_idx on referrals (code);

create table if not exists referral_clicks (
    id          bigserial   primary key,
    code        text        not null,
    ua          text,
    -- Alleen een hash: we willen dubbele kliks kunnen zien, geen mensen volgen.
    ip_hash     text,
    created_at  timestamptz not null default now()
);
create index if not exists referral_clicks_code_idx on referral_clicks (code);

-- Dichtzetten. Alleen de service_role-sleutel mag erbij, en dat is precies wat
-- Railway sinds 06-09-2026 gebruikt. Zonder policies komt de publieke
-- anon-sleutel er niet in, en dat hoort ook niet: hier staat wat je uitbetaalt.
-- Let op: lokaal lezen met de anon-sleutel geeft hierdoor een lege lijst. Dat
-- is dan RLS, geen echte leegte. Lees lokaal met SUPABASE_SERVICE_KEY.
alter table referral_codes  enable row level security;
alter table referrals       enable row level security;
alter table referral_clicks enable row level security;
