-- Eigen prijs per platform voor Etsy (26-11-2026). Handmatig draaien in Supabase.
-- Tot die tijd laat de server de kolom weg uit elke opslagactie (kolom_bestaat).
ALTER TABLE items ADD COLUMN IF NOT EXISTS price_etsy NUMERIC(10,2);
