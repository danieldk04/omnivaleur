-- Commissie voor creators (besloten 24-10-2026, gebouwd 27-10-2026).
--
-- Draai dit één keer in de Supabase SQL editor. Zolang het niet gedraaid is
-- blijft de rest van de app gewoon werken: de uurronde logt dan een fout en
-- doet niets, en de opdracht scripts/creator_commissie.py zegt eerlijk dat de
-- tabel ontbreekt.
--
-- De afspraak in de creatormail: 25% van wat klanten betalen die via de eigen
-- link komen. Bestaande codes (de oude bounty van 25 euro) houden
-- commission_pct 0 en worden dus niet geraakt.

alter table referral_codes add column if not exists commission_pct integer not null default 0;

-- Het kasboek. Eén rij per BETAALDE FACTUUR, nooit meer dan één: die unieke
-- sleutel is de hele bescherming tegen dubbel tellen, net als bij
-- referral_rewards. De uurronde mag dezelfde factuur dus honderd keer zien.
--
-- netto_cents       wat de klant betaalde zonder btw, en na eventuele teruggave
-- commission_pct    het percentage op het moment van de betaling (later
--                   veranderen van het percentage herschrijft de geschiedenis niet)
-- status:  open       = nog niet uitbetaald
--          uitbetaald = Daniel heeft het overgemaakt (uitbetaling_ref zegt hoe)
create table if not exists creator_commissie (
    invoice_id          text        primary key,
    code                text        not null,
    referred_user_id    uuid        not null,
    paid_at             timestamptz not null,
    bruto_cents         integer     not null default 0,
    netto_cents         integer     not null default 0,
    terugbetaald_cents  integer     not null default 0,
    commission_pct      integer     not null,
    commission_cents    integer     not null default 0,
    status              text        not null default 'open',
    uitbetaald_at       timestamptz,
    uitbetaling_ref     text,
    updated_at          timestamptz not null default now()
);
create index if not exists creator_commissie_code_idx on creator_commissie (code);
create index if not exists creator_commissie_status_idx on creator_commissie (status);

-- Dichtzetten, net als de andere verwijstabellen: alleen de service_role-sleutel
-- mag erbij. Hier staat wat je aan creators verschuldigd bent.
alter table creator_commissie enable row level security;

notify pgrst, 'reload schema';
