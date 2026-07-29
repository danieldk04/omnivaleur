-- Herstel na de RLS-storing op `subscriptions`.
--
-- RLS stond aan zonder policy, dus elke insert vanuit de backend werd stil
-- geweigerd. Gevolg: 22 accounts, 1 abonnementsrij. Iedereen zag een
-- proefperiode die nooit werd vastgelegd en dus ook nooit verliep.
--
-- Draai deze twee stappen één keer in de Supabase SQL editor.

-- 1. De oorzaak wegnemen. Zonder dit faalt stap 2 net zo stil.
ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY;

-- 2. Bestaande accounts alsnog een proefperiode geven: 7 dagen vanaf nu, zodat
--    niemand van de ene op de andere dag buitengesloten wordt door een fout
--    die aan onze kant zat. Accounts die al een rij hebben blijven ongemoeid.
INSERT INTO subscriptions (user_id, status, plan, trial_ends_at)
SELECT u.id, 'trialing', 'pro', NOW() + INTERVAL '7 days'
FROM auth.users u
LEFT JOIN subscriptions s ON s.user_id = u.id
WHERE s.id IS NULL;

-- 3. Controle: iedereen hoort nu een rij te hebben.
SELECT u.email, s.status,
       CEIL(EXTRACT(EPOCH FROM (s.trial_ends_at - NOW())) / 86400) AS dagen_over
FROM auth.users u
LEFT JOIN subscriptions s ON s.user_id = u.id
ORDER BY s.trial_ends_at;
