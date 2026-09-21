-- E-mailmarketing naar bestaande gebruikers ("verbinding"-campagne, besloten
-- 21-09-2026, zie docs/team-notes.md). Draai dit één keer in de Supabase SQL
-- editor voor er ook maar één testmail wordt verstuurd: zonder mail_unsubscribed
-- kan een afmelding niet vastgehouden worden, en dat is een harde eis (zie
-- backend/services/mail_verbinding.py).

-- Wie geen marketingmail van Omnivaleur meer wil. Blijvend: nooit rijen
-- verwijderen, ook niet op verzoek — een lege tabel na een "opschonen" zou
-- iedereen weer mailbaar maken. Geldt voor alle campagnesoorten, niet per
-- kind: wie zich één keer afmeldt, is voorgoed klaar met dit soort mail.
create table if not exists mail_unsubscribed (
    user_id           uuid        primary key,
    email             text        not null,
    unsubscribed_at   timestamptz not null default now(),
    bron              text        not null default 'link'   -- 'link' (klik), 'bounce', 'klacht'
);

-- Log van elke verstuurde campagnemail. Drie dingen hangen hiervan af:
--   1. dubbelverzending voorkomen (nooit twee keer dezelfde 'kind' naar
--      dezelfde gebruiker),
--   2. de regel "hoogstens één mail per persoon per drie dagen, over alle
--      soorten heen" (query over alle kind-waarden samen),
--   3. de meting per mailsoort/groep/taal uit STAP 4 van de opdracht.
-- Transactiemail (proefherinnering, verkoopherinnering, extensie offline) valt
-- hier bewust buiten: dat blijft zoals het was, dit is alleen voor de
-- verbinding-/updatecampagne.
create table if not exists mail_campaign_log (
    id          bigserial   primary key,
    user_id     uuid        not null,
    email       text        not null,
    kind        text        not null,      -- bv. 'verbinding_trial', 'verbinding_inactive', 'verbinding_customer'
    segment     text        not null,      -- 'trial' | 'inactive' | 'customer'
    taal        text        not null default 'en',
    resend_id   text,                       -- koppelt aan mail_events.email_id voor bezorgstatus
    sent_at     timestamptz not null default now()
);
create index if not exists mail_campaign_log_user_idx on mail_campaign_log (user_id, sent_at desc);
create index if not exists mail_campaign_log_kind_idx on mail_campaign_log (kind);

alter table mail_unsubscribed enable row level security;
alter table mail_campaign_log enable row level security;

notify pgrst, 'reload schema';
