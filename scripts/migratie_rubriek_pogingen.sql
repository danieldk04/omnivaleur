-- Opgeefgrens voor de nachtelijke rubriekronde (19-09-2026).
--
-- De ronde in backend/services/categorie_herstel.py vroeg het model elke nacht
-- opnieuw naar dezelfde artikelen. Gemeten op 19-09-2026: van de 200 die hij
-- die nacht las waren er 175 PlayStation- en PSP-spellen plus autobanden, en de
-- taxonomie kent geen enkele rubriek voor spellen of auto-onderdelen. 200
-- modelvragen per nacht, ongeveer 0,55 dollar per nacht, voor een antwoord dat
-- van tevoren vaststond.
--
-- Deze twee kolommen laten de ronde bijhouden hoe vaak hij het al geprobeerd
-- heeft. Na drie keer houdt hij op, tot de verkoper de tekst aanpast.
--
-- Veilig om te draaien terwijl alles live is: beide kolommen zijn nieuw, de
-- teller krijgt de waarde 0 voor alles wat er al staat, en geen bestaande code
-- leest of schrijft ze. Draait de app nog zonder deze kolommen, dan gedraagt de
-- ronde zich precies zoals hiervoor.

alter table items
  add column if not exists rubriek_pogingen integer not null default 0;

alter table items
  add column if not exists rubriek_gepoogd_op timestamptz;

-- 19-09-2026, na meting tegen de echte database: de items-tabel zet updated_at
-- bij ELKE schrijfactie op de systeemtijd, ook bij die van de teller hierboven.
-- Op "updated_at is nieuwer dan de laatste poging" afgaan betekent dus dat de
-- ronde zijn eigen schrijfactie aanziet voor een bewerking door de verkoper en
-- iedereen de volgende nacht weer drie kansen geeft; de besparing zou nul zijn.
-- Daarom beslist de tekst zelf: hierin staat een korte vingerafdruk van titel,
-- omschrijving en merk zoals ze in de laatste modelvraag stonden.
alter table items
  add column if not exists rubriek_gevraagd_over text;

-- De ronde zoekt op "geen rubriek" plus "minder dan drie pogingen". Zonder deze
-- index scant hij daarvoor de hele voorraad.
create index if not exists items_rubriek_herstel_idx
  on items (rubriek_pogingen, created_at desc)
  where category is null or category = '';

-- Dit bestand is opnieuw te draaien: elke regel is "if not exists".
