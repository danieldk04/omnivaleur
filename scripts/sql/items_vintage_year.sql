-- Bouwjaar van een artikel, voor Etsy (vintage = 20+ jaar). Handmatig draaien in Supabase.
-- Tot die tijd laat de server de kolom weg uit elke opslagactie (kolom_bestaat) en leest
-- Etsy het jaar uit titel of omschrijving.
ALTER TABLE items ADD COLUMN IF NOT EXISTS vintage_year INTEGER;
