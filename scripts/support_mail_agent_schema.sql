-- Handmatige stap voor de support-mailagent (scripts/support_mail_agent.py).
--
-- Draai dit één keer in de Supabase SQL editor. Zonder deze tabel start het
-- script niet (het weigert te draaien zonder plek om trends bij te houden,
-- zodat er nooit stil PII in de git-repo belandt in plaats van hier).
--
-- Waarom een aparte tabel en niet leadgen_opslag: dit is klantdata (support-
-- vragen, e-mailadressen), leadgen_opslag is prospectdata. Gescheiden houden
-- voorkomt dat een query voor het een per ongeluk het ander meeneemt.

CREATE TABLE IF NOT EXISTS support_mail_log (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,   -- Message-ID van het inkomende bericht; voorkomt dubbel verwerken
    van_adres TEXT NOT NULL,
    onderwerp TEXT,
    topic TEXT NOT NULL,               -- vrije classificatie, bv. "admarkt-scan-batching"
    is_simple_fix BOOLEAN DEFAULT FALSE,
    concept_klaargezet BOOLEAN DEFAULT FALSE,
    auto_fix_branch TEXT,              -- gevuld zodra module B een branch heeft aangemaakt
    verwerkt_op TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS support_mail_log_topic_idx ON support_mail_log (topic);
CREATE INDEX IF NOT EXISTS support_mail_log_verwerkt_idx ON support_mail_log (verwerkt_op);

-- Row Level Security staat voor nieuwe tabellen soms standaard aan met een
-- lege policy (zie scripts/backfill_subscriptions.sql — dat brak inserts
-- stilletjes). Dit script schrijft met de service-role key, dus RLS mag aan
-- blijven zolang er geen policy nodig is voor de service role. Zet 'm alleen
-- uit als schrijven onverklaarbaar blijft mislukken:
-- ALTER TABLE support_mail_log DISABLE ROW LEVEL SECURITY;
