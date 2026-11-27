-- Revaleur: EIGEN Supabase-project, los van Omnivaleur. Draai dit in de SQL-editor van HET REVALEUR-PROJECT.
-- Nooit in het Omnivaleur-project (daar hoort niets van Revaleur te staan).

CREATE TABLE IF NOT EXISTS producten (
    id TEXT PRIMARY KEY,                 -- bij de import: het Shopify-product-id (blijft stabiel voor 301's)
    handle TEXT UNIQUE NOT NULL,         -- URL-deel, zoals /products/<handle>
    sku TEXT NOT NULL,                   -- artikelnummer; de enige sleutel naar Omnivaleur. NIET uniek: Shopify had 8 nummers dubbel
                                         -- (twee advertenties van één stuk); verkoop of afmelding geldt voor alle met dezelfde sku
    titel TEXT NOT NULL,
    merk TEXT, type TEXT,
    prijs DECIMAL(10,2) NOT NULL,
    retail DECIMAL(10,2),
    beschrijving_html TEXT,
    fotos JSONB NOT NULL DEFAULT '[]',   -- [{src, b, h}]
    tags TEXT[] DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'beschikbaar',   -- beschikbaar, verkocht, verborgen
    gemaakt_op TIMESTAMPTZ DEFAULT NOW(),
    bijgewerkt_op TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_producten_sku ON producten(sku);

CREATE TABLE IF NOT EXISTS collecties (
    handle TEXT PRIMARY KEY, titel TEXT NOT NULL, omschrijving TEXT,
    producten TEXT[] DEFAULT '{}'        -- product-id's in volgorde
);

CREATE TABLE IF NOT EXISTS artikelen (   -- blog
    handle TEXT PRIMARY KEY, titel TEXT NOT NULL, datum DATE, html TEXT
);

-- Eén exemplaar per artikel: een reservering houdt een artikel 30 minuten vast tijdens het afrekenen.
CREATE TABLE IF NOT EXISTS reserveringen (
    product_id TEXT PRIMARY KEY REFERENCES producten(id) ON DELETE CASCADE,
    sessie_id TEXT NOT NULL,
    tot TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reserveringen_sessie ON reserveringen(sessie_id);

CREATE TABLE IF NOT EXISTS bestellingen (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nummer BIGINT GENERATED ALWAYS AS IDENTITY,
    stripe_sessie TEXT UNIQUE NOT NULL,
    betaald_op TIMESTAMPTZ DEFAULT NOW(),
    email TEXT, naam TEXT, adres JSONB, land TEXT, taal TEXT DEFAULT 'en',
    artikelen JSONB NOT NULL,            -- [{product_id, sku, titel, prijs}]
    subtotaal DECIMAL(10,2), verzendkosten DECIMAL(10,2), totaal DECIMAL(10,2),
    status TEXT DEFAULT 'betaald',       -- betaald, verzonden, geretourneerd
    track_trace TEXT,
    mail_bevestiging_op TIMESTAMPTZ,
    omnivaleur_gemeld_op TIMESTAMPTZ,    -- wanneer Omnivaleur de verkoop kreeg (artikel van andere kanalen af)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE producten ENABLE ROW LEVEL SECURITY;
ALTER TABLE collecties ENABLE ROW LEVEL SECURITY;
ALTER TABLE artikelen ENABLE ROW LEVEL SECURITY;
ALTER TABLE reserveringen ENABLE ROW LEVEL SECURITY;
ALTER TABLE bestellingen ENABLE ROW LEVEL SECURITY;
-- Alleen de service-sleutel (backend) leest en schrijft; er is bewust geen publieke policy.
