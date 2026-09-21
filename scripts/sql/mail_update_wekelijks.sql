-- Wekelijkse update-mail, bovenop de verbinding-campagne (scripts/sql/mail_verbinding.sql,
-- eerst draaien als dat nog niet gebeurd is). Besloten 21-09-2026, zie docs/team-notes.md.
-- Draai dit één keer in de Supabase SQL editor.

-- Eén rij, altijd overschreven: de inhoud die een lokale geplande sessie deze
-- week heeft klaargezet (git log + team-notes nagekeken, geen verzonnen tekst).
-- status: 'concept' = nog niet door Daniel bekeken, 'verstuurd' = al de deur uit.
create table if not exists mail_update_actueel (
    id              text        primary key default 'current',
    blokjes         jsonb       not null,
    week_van        date,
    status          text        not null default 'concept',
    samengesteld_op timestamptz not null default now()
);

alter table mail_update_actueel enable row level security;

notify pgrst, 'reload schema';
