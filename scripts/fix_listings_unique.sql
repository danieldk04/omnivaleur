-- Samenvoegen van dubbele artikelen mogelijk maken
-- ============================================================================
-- Draai dit in Supabase: Dashboard > SQL Editor > New query > plakken > Run.
--
-- WAAROM (31-08-2026). Daniel drukte op "Merge all 13" en kreeg elf serverfouten
-- op rij. De oorzaak zit niet in de code maar hier: op `listings` staat een
-- unieke sleutel `listings_item_platform_unique` die per item hoogstens één
-- advertentie per kanaal toestaat. Precies wat samenvoegen oplevert — acht
-- kopieën van dezelfde trui met elk een eigen Marktplaats-advertentie — botst
-- daarmee. De app vangt die botsing sinds vandaag netjes af (geen foutmelding
-- meer), maar slaat zo'n groep dan over. Dat is juist het normale geval, dus
-- zonder deze wijziging blijft samenvoegen in de praktijk onbruikbaar.
--
-- Deze sleutel staat NIET in schema.sql; hij is ooit los in Supabase gezet.
-- Daarom eerst kijken, dan pas wijzigen.


-- ── STAP 1: KIJKEN ──────────────────────────────────────────────────────────
-- LET OP: draai deze query ALLEEN, zonder de rest te selecteren. De Supabase
-- SQL Editor toont bij meerdere query's achter elkaar alleen het resultaat van
-- de laatste, en juist deze eerste heb ik nodig.
--
-- Op 31-08-2026 is `pg_constraint` al bekeken: daar staan alleen
-- `listings_pkey` en `listings_item_id_fkey`. `listings_item_platform_unique`
-- zit er NIET bij, en dat is het antwoord in plaats van een raadsel — een
-- unieke INDEX verschijnt niet in `pg_constraint`, alleen hier. Postgres staat
-- bovendien geen constraint met een voorwaarde toe, wél een index met een
-- voorwaarde. Dat sluit aan op de zes item/kanaal-combinaties die naast elkaar
-- bestaan en alle zes hoogstens één advertentie met status 'active' hebben.
--
-- Wat ik uit de uitkomst moet halen: staat er achter de index een WHERE, en zo
-- ja welke. Die voorwaarde moet in stap 2 terugkomen, anders verdwijnt met de
-- botsing ook de bescherming tegen dubbel publiceren.

-- 1a — welke indexen staan er (uitgevoerd 31-08-2026):
--   listings_pkey, idx_listings_item_id, idx_listings_status,
--   idx_listings_platform, listings_item_platform_unique
-- De laatste is dus inderdaad een UNIQUE INDEX. Alleen viel de definitie rechts
-- van het scherm weg, en juist daar zou een WHERE staan.

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'listings';


-- 1b — DE ENIGE VRAAG DIE NOG OPEN STAAT. Geeft dit NULL terug, dan geldt de
-- index voor álle rijen. Komt er tekst uit, dan is dat de voorwaarde en moet
-- die ONVERANDERD mee naar de nieuwe index in stap 2.
-- Deze vorm past altijd op het scherm, hoe smal de kolom ook is.

SELECT pg_get_expr(i.indpred, i.indrelid) AS voorwaarde
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
WHERE c.relname = 'listings_item_platform_unique';


-- ── STAP 2: WIJZIGEN ────────────────────────────────────────────────────────
-- Draai dit PAS als stap 1 bevestigt dat de sleutel op (item_id, platform)
-- staat. Blijkt hij anders te liggen, laat het dan eerst zien — dan pas ik dit
-- aan in plaats van dat je iets draait wat niet past.
--
-- Wat er verandert: één item mag meerdere advertenties per kanaal hebben, zolang
-- het echt verschillende advertenties zijn (verschillend `platform_listing_id`).
--
-- Waarom NULLS NOT DISTINCT erbij hoort: Postgres beschouwt twee lege waarden
-- normaal als verschillend. Zonder deze toevoeging zouden er onbeperkt rijen
-- ZONDER advertentienummer per item en kanaal kunnen ontstaan — en precies dat
-- is wat de oude sleutel tegenhield: dubbel publiceren. Er staan nu 101 van de
-- 11.102 advertenties zonder nummer in de database, dus dat is geen theorie.
-- Met deze toevoeging blijft die bescherming staan én kunnen echte advertenties
-- naast elkaar bestaan.
--
-- Alles binnen één transactie: gaat er iets mis, dan draait de hele wijziging
-- terug en blijft de oude sleutel gewoon staan.

-- Stap 1 is uitgevoerd (31-08-2026). De oude index is:
--
--   CREATE UNIQUE INDEX listings_item_platform_unique
--     ON public.listings USING btree (item_id, platform)
--     WHERE ((status)::text = 'active'::text);
--
-- De voorwaarde `status = 'active'` verklaart de zes item/kanaal-combinaties
-- die naast elkaar bestaan: daar is er telkens hooguit één actief. Die
-- voorwaarde blijft hieronder ONGEWIJZIGD staan — hij is de reden dat een
-- verkochte of ingetrokken advertentie niets blokkeert.
--
-- Wat er verandert is alleen `platform_listing_id` erbij. Daarmee mag één item
-- meerdere lopende advertenties op hetzelfde kanaal hebben, zolang het echt
-- verschillende advertenties zijn.
--
-- NULLS NOT DISTINCT is het deel dat de oude bescherming overeind houdt.
-- Postgres ziet twee lege waarden normaal als verschillend; zonder deze regel
-- zouden er onbeperkt ACTIEVE rijen zonder advertentienummer per item en kanaal
-- kunnen ontstaan, en dat is precies wat dubbel publiceren oplevert. Er staan
-- 101 van de 11.102 advertenties zonder nummer in de database, dus dat geval is
-- echt. (Vereist Postgres 15 of hoger; klaagt hij hierover, laat het me weten —
-- dan is er een langere variant met een tweede index.)

BEGIN;

DROP INDEX IF EXISTS listings_item_platform_unique;

-- Voor het geval hij ooit tóch als constraint is aangemaakt:
ALTER TABLE listings
  DROP CONSTRAINT IF EXISTS listings_item_platform_unique;

CREATE UNIQUE INDEX listings_item_platform_advert_unique
  ON listings (item_id, platform, platform_listing_id)
  NULLS NOT DISTINCT
  WHERE status = 'active';

COMMIT;


-- ── STAP 3: CONTROLEREN ─────────────────────────────────────────────────────
-- Moet één regel teruggeven met de nieuwe naam, en de oude mag niet meer
-- voorkomen. Draai ook deze los.

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'listings';


-- ── ALS STAP 2 KLAAGT ───────────────────────────────────────────────────────
-- "could not create unique index ... duplicate key value" betekent dat er al
-- twee advertenties met hetzelfde nummer op hetzelfde item en kanaal staan.
-- Deze query laat zien welke dat zijn. Niets weggooien voordat je ze bekeken
-- hebt — het zijn echte advertenties die online kunnen staan.

SELECT item_id, platform, platform_listing_id, COUNT(*) AS aantal
FROM listings
GROUP BY item_id, platform, platform_listing_id
HAVING COUNT(*) > 1;
