-- Eigen prijs per platform voor WooCommerce (10-10-2026). Handmatig draaien in Supabase.
-- Tot die tijd laat de server de kolom weg uit elke opslagactie (kolom_bestaat).
ALTER TABLE items ADD COLUMN IF NOT EXISTS price_woocommerce NUMERIC(10,2);
