# Revaleur-herbouw: overdracht aan de andere developer (27-11-2026)

Lees eerst `revaleur/README.md` (scheiding met Omnivaleur) en dit bestand. Er staan GEEN geheimen in dit bestand of in git.

## Doel en harde eisen (Daniel)
revaleur.com (nu Shopify, €28 per maand) wordt een eigen webshop met bijna nul vaste kosten. UX en UI minstens gelijk aan nu, nooit
extra onderhoud voor Daniel, alles tweetalig (EN en NL), alles binnen gratis limieten waar mogelijk, en Revaleur staat helemaal los
van Omnivaleur (eigen database, Stripe, mail, server). Opdrachtteksten: `revaleur/docs/revaleur-ontwerp.md`, `docs/opdracht-revaleur-herbouw.md`.

## Architectuur
```
Revaleur-Supabase (producten, collecties, artikelen, reserveringen, bestellingen)
   -> catalogus_uit_db.py -> bouw.py -> statische site (614 pagina's, EN+NL)  -> Cloudflare Pages (project "revaleur")
Foto's: Cloudflare R2 bucket "revaleur-fotos" (openbaar via r2.dev)
Winkelmand (localStorage) -> POST /api/revaleur/checkout (FastAPI op Railway) -> Stripe Checkout -> webhook
   -> bestelling opslaan, product op verkocht, Omnivaleur melden (sku), bevestigingsmail (Resend), site opnieuw bouwen (deploy hook)
Omnivaleur <-> Revaleur: alleen ondertekende berichten op artikelnummer (sku), zie koppeling.md
```

## Waar staat wat (geen geheimen)
| Onderdeel | Waarde |
|---|---|
| Code | repo `danieldk04/omnivaleur`, map `revaleur/`, alles op main |
| Testsite | https://revaleur.pages.dev (Cloudflare Pages, project `revaleur`, directe upload, geen Git) |
| API | https://api-production-a52c044e.up.railway.app (Railway-project `revaleur-api`, service `api`, project-id d6e4d445-9b0d-4dcb-8f47-9b4ecbe0bfbb) |
| Database | Supabase-project `pwptworlzhgcombgearz` (https://pwptworlzhgcombgearz.supabase.co), regio Frankfurt, schema in `revaleur/sql/schema.sql` (gedraaid, incl. publiek-lezen-policies) |
| Foto's | R2-bucket `revaleur-fotos`, openbaar adres https://pub-62b872fcfc544e398968b5274d2ee45a.r2.dev |
| Cloudflare | account a6c88fb3157aa10166303cc79b163723, DNS-zone revaleur.com (nog niet actief, 28 records overgenomen, geen proxy) |
| Stripe | sandbox-account `acct_1UfIBePetYvl0Q7t` ("Revaleur sandbox", NL), webhook-endpoint op de API aangemaakt; LIVE nog niet |
| Resend | domein revaleur.com geverifieerd (Ierland), afzender `Daniel van Revaleur <info@revaleur.com>`, testmail in inbox |
| Omnivaleur-kant | `backend/api/revaleur_koppeling.py`, variabelen `REVALEUR_KOPPELING_GEHEIM` en `REVALEUR_API_URL` staan op Omnivaleurs Railway (gecontroleerd 27-11) |
| Geplande controle | taak `trig_01FhHKbakKDjyn1HujLWzAmn` (28-11 10:00 Amsterdam): controleert of de domeinoverdracht klaar is |

**Geheimen** (Supabase secret key, Stripe sandbox-sleutel, Cloudflare-token en R2-sleutels, Railway-token, Resend-sleutel, koppelingsgeheim)
stonden alleen in `~/.revaleur/env` in de cloudsessie (die verdwijnt) en als variabelen op de Railway-dienst. Ze hebben in een chat gestaan:
**draai ze allemaal om** (Supabase, Cloudflare, R2, Railway, Resend, Stripe, koppelingsgeheim aan beide kanten) zodra de site live is.
Nieuwe sleutels via de dashboards van Daniel; zet ze nooit in git. Variabelen van de API: `REVALEUR_SUPABASE_URL`, `REVALEUR_SUPABASE_SERVICE_KEY`,
`REVALEUR_STRIPE_SECRET_KEY`, `REVALEUR_STRIPE_WEBHOOK_SECRET`, `REVALEUR_RESEND_API_KEY`, `REVALEUR_MAIL_VAN`, `REVALEUR_KOPPELING_GEHEIM`,
`REVALEUR_SITE_URL`, `REVALEUR_EXTRA_ORIGINS`, optioneel `REVALEUR_DEPLOY_HOOK`.

## Wat klaar en getest is
- Inventaris (`revaleur-inventaris.md`), ontwerp, wettelijk (`revaleur-wettelijk.md`, met open punten), deploy-gids (`deploy.md`), koppeling (`koppeling.md`).
- Catalogus: 250 producten (2 verkocht), 18 collecties, 30 blogartikelen in de Revaleur-database. 8 dubbele artikelnummers zijn samengevoegd op de HOOGSTE prijs, met 301's (`site/omleidingen.json`). `sku` is dus NIET uniek in de database; een verkoop of afmelding geldt voor alle advertenties met dezelfde sku.
- Site: 614 pagina's, zelfde URL's als Shopify (alle 423 oude URL's getest, 0 fouten), zoeken, filteren, winkelmand, beleid en voorwaarden in NL, Google Merchant-feed (`/feeds/google-merchant.xml`, 248 items), sitemap, robots, bedrijfsgegevens in de voet (KvK 86792423, btw NL004117227B97).
- Foto's: alle 2130 in R2, juiste bestandstypes (43 waren PNG; het script `fotos_naar_r2.py` bepaalt het type nu uit de bytes). Nieuwe producten: draai `python3 -m revaleur.site.fotos_naar_r2`.
- Afrekenen (sandbox): Stripe Checkout met iDEAL en kaart, alleen euro (Adaptive Pricing uit), reservering per artikel 30 min, 409 bij "net verkocht" en bij prijsverschil, automatische factuur met "Bijzondere regeling - gebruikte goederen" en GEEN Stripe Tax (margeregeling), webhook idempotent, bestelling, verkocht, mail, melding aan Omnivaleur. Getest met een echte sandbox-sessie en met een ondertekende betaalmelding naar de live API. Een betaling met testkaart op Stripe's eigen pagina is NIET gedaan.
- Tests: `python3 -m pytest revaleur/tests tests/test_revaleur_koppeling.py -q` (16 groen). De rest van de Omnivaleur-suite heeft 91 rode tests die al voor mijn werk rood waren (ontbrekende pakketten in de cloudomgeving); op een volledige machine opnieuw meten.
- Mail: DNS-records toegevoegd in Shopify-DNS (resend._domainkey, rsend, send), testmail vanaf info@revaleur.com kwam in de inbox.
- Domein: registrar is Tucows via Shopify, verloopt 05-06-2027. Daniel heeft de overdracht naar Cloudflare gestart (Shopify meldt "transfer in progress"; kan tot 5 dagen duren). Cloudflare-zone bevat alle bestaande records (Shopify, Hostinger-mail, Shopify-mail, Resend, verificatie), allemaal ZONDER proxy.

## Open, in volgorde
1. **Domeinoverdracht afronden** (loopt). Controleer: NS van revaleur.com = savanna.ns.cloudflare.com en wilson.ns.cloudflare.com, registrar Cloudflare, zone actief. Mail (Hostinger) en Shopify-site moeten daarna blijven werken: controleer MX en een Shopify-pagina.
2. **Deploy hook / Git-koppeling.** Het Pages-project is aangemaakt met directe upload en kan geen deploy hook hebben. Maak het project Git-gekoppeld (Cloudflare Pages, Connect to Git, repo `danieldk04/omnivaleur`, branch main; instellingen in `deploy.md`) OF laat de API zelf na een verkoop bouwen en uploaden. Zet daarna `REVALEUR_DEPLOY_HOOK` op Railway. Tot die tijd blijft een verkocht artikel zichtbaar; de checkout vangt het af.
3. **Stripe live.** Daniel rondt de bedrijfsverificatie af. Daarna: live secret key en een live webhook (events: checkout.session.completed, async_payment_succeeded, async_payment_failed, expired) naar `<api>/api/revaleur/stripe-webhook`; zet de live waarden op Railway. Controleer in het dashboard dat iDEAL aan staat (en PayPal/Klarna als Shopify die ook had; de FAQ noemt ze).
4. **Echte proefbestelling van €1** (Daniel betaalt, later terugbetalen): volledige keten controleren: betaling, bestelling in `bestellingen` (`omnivaleur_gemeld_op` gevuld), artikel op verkocht, factuur met margeregeling-tekst, mail, en dat het artikel op de andere kanalen is afgemeld. Gebruik een testartikel dat je daarna terugzet (`producten.status` beschikbaar, bestelling verwijderen).
5. **Verzendlabels:** Sendcloud of MyParcel (de goedkoopste die bij Daniels werkwijze past), trackingmail. Nog niets gebouwd.
6. **Factuur als pdf/mail met doorlopend factuurnummer** en margeregeling-tekst is nu alleen de Stripe-factuur; bevestig met de boekhouder (`revaleur-wettelijk.md`: margeregeling-methode, 7 jaar bewaren, herroepingsformulier toevoegen).
7. **Omzetten (alleen na stap 4):** DNS van revaleur.com (nu in de Cloudflare-zone) naar de Pages-site: vervang de A/AAAA/www-records van Shopify door een Pages-koppeling (Custom domain in het Pages-project), laat MX, SPF, DKIM en Resend-records staan. Zet `REVALEUR_SITE_URL` op https://revaleur.com en `API` in `site/bouw.py` bij voorkeur op een eigen adres (`api.revaleur.com` als Custom Domain op Railway). Bouw en upload opnieuw. Houd Shopify 30 dagen aan als vangnet en zeg het pas daarna op (Daniel). Voordat Shopify stopt: controleer dat het domein niet meer van Shopify afhangt.
8. **Zoekmachines en advertenties:** Search Console (sitemap indienen, dekking bekijken), Merchant Center met de feed, Meta-catalogus (zelfde feed) en pixel (alleen met toestemmingsbanner, nu geen cookies).
9. **Sitecheck:** `docs/routines/revaleur-sitecheck.md` is al herschreven voor de nieuwe site; draai hem één keer groen en controleer dat de geplande taak `omnivaleur-revaleur-sitecheck` hem volgt.
10. **Sleutels omdraaien** (zie hierboven), en `docs/overdracht.md`, `docs/team-notes.md` en de kennisbank bijwerken na elke stap (CLAUDE.md).
11. Klaar-criteria uit `docs/opdracht-revaleur-herbouw.md`: echte bestelling van betaling tot mail met afmelding op alle kanalen, 301-steekproef (gedaan), feeds werken, sitecheck één keer groen, docs bijgewerkt, gemerged en `/health` gecontroleerd.

## Valkuilen (kostte mij tijd)
- Cloudflare weigert verzoeken met de User-Agent van kale scripts (`Python-urllib`) met een 403, ook op pages.dev en op omnivaleur.com. Gebruik een gewone browser-UA of httpx. De echte API-aanroepen (httpx) komen wel door.
- Shopify toont aan curl een bot-controle; alleen `/products.json`, `/collections.json` en `blogs/news.atom` werken zonder browser. Voor pagina's: Playwright.
- Stripe Checkout toont standaard dollars (Adaptive Pricing) en kost de klant 4% omrekenkosten; staat nu uit (`adaptive_pricing.enabled=false`). Nooit Stripe Tax aanzetten: margeregeling.
- Cloudflare Pages met directe upload: geen deploy hook, geen automatische build. Upload: `python3 -m revaleur.site.catalogus_uit_db && python3 -m revaleur.site.bouw && npx wrangler pages deploy revaleur/site/dist --project-name revaleur --branch main`.
- Railway uitrollen zonder GitHub: kopieer `revaleur/__init__.py` en `revaleur/shop_api/` naar een lege map met `requirements.txt` (zonder pytest), een `Procfile` (`web: uvicorn revaleur.shop_api.main:app --host 0.0.0.0 --port $PORT`) en `railway.json`, dan `railway up --service api`. Railpack heeft de Procfile nodig.
- Een reservering houdt een artikel 30 minuten vast; een geannuleerde of verlopen sessie geeft het vrij via de Stripe-webhook. Bij testen: laat openstaande testsessies verlopen of wacht.
- Supabase gratis pauzeert na een week zonder verkeer. Resend gratis: 100 mails per dag. Railway is niet gratis. R2 en Pages wel (ruim).
- De R2 S3-adressen werken niet vanuit de cloudsessie (proxy), op een gewone pc wel; gebruik anders de Cloudflare-API (zie `fotos_naar_r2.py`).
- Cloudflare-zone: alle records bewust zonder proxy zolang Shopify nog de site toont.

## Rollback
Zolang revaleur.com nog naar Shopify wijst, raakt niets de klanten. Na het omzetten: zet de A/AAAA/www-records in de Cloudflare-zone terug naar Shopify (A 23.227.38.70, AAAA 2620:127:f00f:a::, www CNAME shops.myshopify.com); Shopify blijft 30 dagen bestaan.

## Werkwijze (CLAUDE.md van de repo)
Rapporteer aan Daniel in vier blokjes met urgentielabels, kort. Klanttekst altijd EN en NL, nooit "sorry" in klantberichten. Merge klare, geteste wijzigingen zelf fast-forward naar main en controleer `https://omnivaleur.com/health`; Revaleur zit niet in die deploy (de API en de site rol je zelf uit). Geen pull requests nodig. Houd `docs/overdracht.md` en `docs/team-notes.md` bij.

## Stand 27-11-2026 avond (bijgewerkt)
- Stap 3 (Stripe live) KLAAR: live account `acct_1UgN3zB31GM6PwWd`, live webhook `we_1UgRj3B31GM6PwWdBaXnttyo` (4 events), live restricted key `revaleur-api-railway` (rk_live, volledige toegang behalve gevoelige bewerkingen) en de live signing secret staan op Railway (uitgerold). Test: POST /api/revaleur/checkout geeft een echte `cs_live_`-sessie. De sandbox-sleutels zijn vervangen en hoeven niet meer.
- Nog open: iDEAL aan zetten in Stripe live (Instellingen > Betaalmethoden) controleren; stap 4 (proefbestelling) vraagt een testartikel van €1 in de Revaleur-database (geen bestaand artikel kost €1); stap 1 (domein): zie team-notes, overdracht naar Porkbun loopt, controle 29-11 10:00.
- Sleutels omdraaien: nieuwe Stripe-sleutels zijn al vers; de rest (Supabase, Cloudflare, R2, Railway, Resend, koppelingsgeheim) volgt na de omzetting.
