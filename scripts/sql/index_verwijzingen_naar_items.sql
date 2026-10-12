-- Indexen op de kolommen die naar items verwijzen (12-10-2026).
--
-- Waarom: een artikel verwijderen laat Postgres in elke tabel die naar items
-- verwijst zoeken naar rijen van dat artikel (ON DELETE CASCADE / SET NULL).
-- Zonder index op die kolom leest hij de hele tabel. jobs (~27.000 rijen, grote
-- payload) en import_candidates (~36.000 rijen, volledige scan-kopieën) hebben er
-- in schema.sql geen; listings wel. Op 12-10 liep het verwijderen van een artikel
-- zonder listings (e92e6c8e, Revaleur) daardoor in een statement timeout (57014).
--
-- DRAAIEN IN HET SUPABASE-DASHBOARD (SQL Editor), ELKE STAP APART.
-- CREATE INDEX CONCURRENTLY mag niet in een transactie: selecteer steeds alleen
-- die ene regel en klik Run. Concurrently blokkeert de site niet, maar leest de
-- tabel wel een keer helemaal: doe het buiten de drukke avonduren.

-- Stap 1: kijken wat er nu staat (leest alleen de catalogus, kost niets).
select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public' and tablename in ('jobs', 'import_candidates', 'listings')
order by tablename, indexname;

-- Stap 2: index op jobs.item_id.
create index concurrently if not exists idx_jobs_item_id on public.jobs (item_id);

-- Stap 3: index op import_candidates.suggested_item_id.
create index concurrently if not exists idx_import_candidates_suggested_item_id
    on public.import_candidates (suggested_item_id);

-- Stap 4: controle. Beide moeten er staan en indisvalid moet true zijn. Is een
-- van beide false (afgebroken bouw), dan: drop index concurrently <naam>; en stap
-- 2 of 3 opnieuw.
select c.relname, i.indisvalid
from pg_index i join pg_class c on c.oid = i.indexrelid
where c.relname in ('idx_jobs_item_id', 'idx_import_candidates_suggested_item_id');

-- Stap 5: het proefitem van 12-10 opruimen (Revaleur). Bewust hier en niet via
-- de verwijderknop: dit item gebruikt een foto uit Jannekes map, en de knop zou
-- die foto uit de opslag wissen omdat hij alleen naar Revaleurs eigen artikelen
-- kijkt. Zo blijft haar foto staan.
delete from public.items
where id = 'e92e6c8e-997f-4514-8d9d-db987cd60ea2'
  and user_id = '3bfbed2c-e8a7-4b28-8870-f3581d48afc5';
