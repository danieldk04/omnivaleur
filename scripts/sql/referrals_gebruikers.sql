-- Gebruikers die elkaar aanbrengen (besloten 20-09-2026).
--
-- Draai dit één keer in de Supabase SQL editor. Zolang dit niet gedraaid is
-- blijft de rest van de app gewoon werken: de verwijspagina in het dashboard
-- zegt dan eerlijk dat hij nog niet klaarstaat in plaats van een leeg scherm te
-- tonen of een fout te geven.
--
-- Bouwt voort op scripts/sql/referrals.sql (de influencer-meetlaag). Dezelfde
-- codetabel, dezelfde kliktelling, dezelfde koppeling bij het aanmelden. Het
-- enige verschil is WIE de code bezit en WAT de beloning is:
--
--   creator  -> code van Daniel uitgegeven, beloning is geld (bounty_cents)
--   user     -> code van een klant zelf, beloning is een gratis maand
--
-- Bewust geen tweede codetabel: dan zouden er twee plekken zijn waar een code
-- kan bestaan en zou /r/CODE moeten gokken in welke hij moet kijken.

alter table referral_codes add column if not exists owner_user_id uuid;
alter table referral_codes add column if not exists kind text not null default 'creator';
create index if not exists referral_codes_owner_idx on referral_codes (owner_user_id);

-- Wanneer de aanbrenger gemaild is dat er iemand via zijn link is binnengekomen.
-- Leeg = nog niet gemaild. Zonder deze kolom zou de ronde die dat mailt elke keer
-- opnieuw dezelfde mail sturen.
alter table referrals add column if not exists aanmelding_gemeld_at timestamptz;

-- Het kasboek van de gratis maanden. Eén rij per AANGEBRACHTE klant, nooit meer
-- dan één: die unieke sleutel is de hele bescherming tegen dubbel uitkeren. Twee
-- webhooks die tegelijk binnenkomen verliezen er allebei op, op één na.
--
-- status:  pending  = geclaimd, nog niet verwerkt (of verwerken mislukte)
--          granted  = de maand is echt toegekend
--          skipped  = bewust niets gedaan (eigenaar, zelfverwijzing)
-- method:  tegoed            = geld bijgeschreven bij Stripe, gaat automatisch
--                              van de volgende factuur af
--          proef_verlengd    = de proefperiode in onze eigen tabel opgerekt
--          stripe_proef      = de proefperiode bij Stripe zelf opgerekt
create table if not exists referral_rewards (
    id                bigserial   primary key,
    referrer_user_id  uuid        not null,
    referred_user_id  uuid        not null unique,
    code              text        not null,
    status            text        not null default 'pending',
    method            text,
    amount_cents      integer     not null default 0,
    detail            text,
    attempts          integer     not null default 0,
    last_error        text,
    created_at        timestamptz not null default now(),
    granted_at        timestamptz
);
create index if not exists referral_rewards_referrer_idx on referral_rewards (referrer_user_id);
create index if not exists referral_rewards_status_idx on referral_rewards (status);

-- Dichtzetten, net als de andere verwijstabellen: alleen de service_role-sleutel
-- mag erbij. Hier staat wat er aan gratis maanden is weggegeven.
alter table referral_rewards enable row level security;
