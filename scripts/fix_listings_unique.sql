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
-- Draai eerst alleen dit en stuur de uitkomst door. Er verandert niets.
--
-- Waarom deze stap niet over te slaan is: in de database staan zes item/kanaal-
-- combinaties die volgens een gewone sleutel op (item_id, platform) niet zouden
-- kunnen bestaan, en ze hebben alle zes hoogstens één advertentie met de status
-- 'active'. Dat wijst op een GEDEELTELIJKE sleutel (eentje met een voorwaarde).
-- Welke voorwaarde dat precies is, bepaalt hoe stap 2 eruit moet zien.

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'listings';

SELECT conname, pg_get_constraintdef(oid) AS definitie
FROM pg_constraint
WHERE conrelid = 'listings'::regclass;


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

BEGIN;

ALTER TABLE listings
  DROP CONSTRAINT IF EXISTS listings_item_platform_unique;

-- Was het een index in plaats van een constraint, dan vangt deze regel dat op.
DROP INDEX IF EXISTS listings_item_platform_unique;

ALTER TABLE listings
  ADD CONSTRAINT listings_item_platform_advert_unique
  UNIQUE NULLS NOT DISTINCT (item_id, platform, platform_listing_id);

COMMIT;


-- ── STAP 3: CONTROLEREN ─────────────────────────────────────────────────────
-- Moet één regel teruggeven met de nieuwe naam.

SELECT conname, pg_get_constraintdef(oid) AS definitie
FROM pg_constraint
WHERE conrelid = 'listings'::regclass
  AND conname = 'listings_item_platform_advert_unique';


-- ── ALS STAP 2 KLAAGT ───────────────────────────────────────────────────────
-- "could not create unique index ... duplicate key value" betekent dat er al
-- twee advertenties met hetzelfde nummer op hetzelfde item en kanaal staan.
-- Deze query laat zien welke dat zijn. Niets weggooien voordat je ze bekeken
-- hebt — het zijn echte advertenties die online kunnen staan.

SELECT item_id, platform, platform_listing_id, COUNT(*) AS aantal
FROM listings
GROUP BY item_id, platform, platform_listing_id
HAVING COUNT(*) > 1;
