# Overdracht: lees dit als eerste

Bijgewerkt 28-10-2026 door de sessie op Daniels Mac, op zijn verzoek ("dat jullie allebei
op één lijn zitten, 100% gesynchroniseerd"). Daniel wil zelf geen acties hoeven uitvoeren:
wat te doen is, doen de sessies zelf. Alles hieronder is gemeten op 28-10-2026, tenzij er
een andere datum staat. Details en bewijs staan in `docs/team-notes.md` onder de genoemde
kopjes; lessen in `docs/kennisbank.md`.

## Wat je in je EERSTE sessie zelf doet, zonder te vragen

1. `git pull`. Lees daarna deze pagina, de onderkant van `docs/team-notes.md` (alles sinds
   15-10) en zoek in `docs/kennisbank.md` gericht op je onderwerp
   (`grep -n "^## " docs/kennisbank.md`; nooit het hele bestand lezen).
2. **Je lokale `.env` werkt waarschijnlijk niet meer.** Op 27-10 zijn na het Railway-lek alle
   sleutels vernieuwd en de oude Supabase-sleutels (die met `ey...`) uitgezet. Sinds 28-10
   staat RLS aan op 10 tabellen, dus met een publieke sleutel (`sb_publishable_`) zie je lege
   lijsten zonder foutmelding. Je hebt de `sb_secret_`-sleutel nodig in `SUPABASE_KEY` en
   `SUPABASE_SERVICE_KEY`, en `supabase>=2.16` (2.7.4 weigert de nieuwe sleutel met
   "Invalid API key"). Controle: `python3 -c "from backend.database import get_db;
   print(len(get_db().table('items').select('id').limit(1).execute().data))"` moet 1 geven.
   Lege uitkomst = verkeerde sleutel, niet een lege database. Daniel heeft de sleutel.
3. Controleer je geplande taken (`list_scheduled_tasks`). Maak ontbrekende zelf aan, lokale
   tijd, met de tekst "Je werkt aan Omnivaleur in <jouw repomap>. Lees <bestand> in die repo
   en volg het precies. Rondenaam: <naam>.":
   - `omnivaleur-onboarding-nieuwe-klanten-middag`, dagelijks 10:00,
     bestand `docs/routines/onboarding-nieuwe-klanten.md`, rondenaam `onboarding-middag`.
   - `omnivaleur-klantfouten-middagronde`, dagelijks 14:00,
     bestand `docs/routines/klantfouten.md`, rondenaam `middagronde`.
   Let op: in team-notes staat sinds 20-10 geen enkele `onboarding-middag` of `middagronde`
   meer. Jouw taken draaiden dus niet, of jouw account was niet actief. Alles daarna deed
   Daniels Mac. Schrijf in team-notes dat ze weer staan, en push.
4. Draai meteen een eerste keer wat vandaag nog niet gedraaid is (het gedeelde slot
   `python3 scripts/klantfouten.py ronde begin <rondenaam>` zegt of een andere ronde bezig
   is of net klaar was; bij exit 3 niet forceren).
5. Noem in je eerste antwoord kort wat je gezien hebt (CLAUDE.md eist dat).

## Wat sinds de vorige overdracht (15-10) is afgerond

- **Toon (96e30080), foto's van SiteGround**: opgelost. Bronfoto's komen via de GitHub-taak
  `.github/workflows/bronfotos.yml` binnen; 0 van zijn 1.624 artikelen wijzen nog naar
  dejuistetoon.eu (was 241). Laatste run "Bronfoto's" groen (28-10 07:31 UTC). Vinted-woontextiel,
  categoriestap, merk en staat zijn gerepareerd in 1.0.392 tot 1.0.394; vachten gaan bewust niet
  meer naar Vinted (dierenhuid, 21-10); zijn WooCommerce-doorvoer staat op zijn verzoek uit (21-10).
- **Te-bouwen-lijst in Drive**: gedaan op 20-10 vanaf Daniels account. Google Sheet
  "Omnivaleur te bouwen" (zie CLAUDE.md, sectie "De centrale lijst"), bijwerken met
  `scripts/te_bouwen.py lijst|voeg|wijzig`. `docs/te-bouwen.md` is alleen nog een verwijzing.
- **Railway-lek (22 en 27-10)**: alle hoofdsleutels vernieuwd: Supabase, Google, Resend,
  Anthropic, Stripe (webhook-endpoint nu `we_1UV6jq09Y8J5okHsXNO8szrl`, alle events
  afgeleverd). GitHub-geheimen mee vervangen; `SUPABASE_KEY` op GitHub is op 28-10 09:08
  vervangen, de Leadmachine draaide daarna zonder sleutelfout. Nog bewust niet vernieuwd:
  R2, Cloudinary, Apify, SMTP, Resend-webhookgeheim, Shopify/eBay-geheimen, Google OAuth,
  SECRET_KEY, ANALYTICS_DASHBOARD_TOKEN (team-notes 27-10).
- **RLS aan** op 10 tabellen (28-10). `content_pages` bewust open (blogroutine op GitHub).
- **Marktplaats veranderde de beschrijvingseditor (21-10)**: gerepareerd in 1.0.400; de server
  geeft plaatswerk alleen aan een extensie die de nieuwe editor kent.
- **Onboardingmails**: de routine verstuurt sinds 25-10 zelf, alleen via
  `scripts/onboarding_mail.py stuur ... --echt` (harde controles in de code), en meet opens,
  kliks, antwoorden en wat de klant daarna deed (`onboarding_mail.py rapport`).
- **Platformcontrole** (dagelijks op Daniels Mac): uitgebreid op 25-10, vergelijkt elke stap met
  gisteren en loopt drie extra Marktplaats-rubrieken per dag door.
- **Creatorcommissie 25%** gebouwd en in productie bewezen (27 en 28-10): loopt zolang de
  aangebrachte klant betaalt, kasboek `creator_commissie`, Daniel maakt zelf over.
- **Account wissen en gegevens downloaden** (AVG, 15-10): kaart "Privacy & your data".
- **Herplaatsen op vaste dagen en uur** (19-10, toezegging aan Voordeelsieraden) en de knop
  Herplaatsen op het tabblad Verkocht (21-10, Janneke; een REV-kopie is nooit een dubbele, 25-10).
- **eBay België** (20 en 21-10): per klant `extra_data.ebay_marktplaats`; een offer op EBAY_BE wordt
  door eBay geaccepteerd, publiceren wacht op Daniels identiteitsverificatie bij eBay.
- **Rubrieken zonder taalmodel (28-10)**:
  - Nieuwe tak `hobby` met "hobby kledingapplicaties en strijkemblemen" (Marktplaats en
    2dehands 1099/2855, gemeten) en een woordenlijst voor strijkemblemen en stropdassen
    (`_strijkembleem_of_stropdas` in imports.py). De server stuurt de Marktplaats-nummers mee
    (`_MP_NUMMERS_VAN_DE_SERVER` in jobs.py), dus Marktplaats en 2dehands werken met elke
    extensie; Vinted wacht op 1.0.406 (`MINIMALE_HOBBY_VERSIE`).
  - Het Shopify-producttype bepaalt bij het inlezen de rubriek (`rubriek_uit_producttype`):
    251 sieraden bij Voordeelsieraden en Goudlief gevuld, terug te zetten uit
    `~/.omnivaleur/backups/rubriek_uit_producttype_28-10.jsonl` (Daniels Mac).
  - Rubriek overnemen van Vinted: bewust niet gebouwd, maar 11 van de 542 lege rubrieken
    kwamen van Vinted.
  - **Google-betaling aan** (Daniel, 28-10 ~11:15, 10 euro). Daarvoor gaf de gratis sleutel
    2.606x HTTP 429 en 0x 200; de gratis portie ging op aan vertalen. Daarna antwoordde Google
    weer (5 van 5). De nachtronde rubriekherstel (05:00, 200 per nacht) haalt de ~250 lege
    rubrieken in. Claude doet bewust geen rubriekvragen (kosten, 09-10).

## Wat nu open staat (niemand hoeft te wachten op Daniel tenzij er "beslissing" staat)

- **Extensie in de Web Store**: de Web Store levert 1.0.404, de repo staat op 1.0.406.
  1.0.405 (Vinted "Meerkleurig" op een Engelse pagina) en 1.0.406 (strijkemblemen op Vinted)
  zitten samen in `dist/omnivaleur-extension-1.0.406.zip`. Uploaden kan alleen met Daniels
  Google-account in het Chrome Web Store-dashboard.
- **Controle Google-kosten**: eenmalige taak `omnivaleur-google-kosten-check` op Daniels Mac,
  31-10 10:00. Meet de kosten, of Google antwoordt en hoeveel rubrieken nog leeg zijn (was 252).
- **Janneke (31d28378)**: Vinted heeft haar account tot en met 31-10 stilgezet (reden niet
  bewezen; tempo tot 50 plaatsingen per avond, gedeelde foto's). Advies: niets forceren tot
  1-11, daarna rustig hervatten met Calm mode. Haar 158 lege rubrieken (titels als
  "* Accessoires", geen producttype) wachten op de rubriekvraag.
- **Goudlief (5aae4954, Dahli)**: sinds 28-10 Pro (tot 28-11). Hij wil alles ook via Omnivaleur op
  Marktplaats, naast zijn eigen Marktplaats Pro-feed (loopt t/m 31-12-2026); de 996 tegengehouden
  opdrachten staan weer in de rij, 260 bestaande dubbelen blijven staan. Zijn keuze, niets aan doen.
- **Delftsblaeu (eac0cccc)**: mailpauze tot en met 29-10 (`MAIL_PAUZE_TOT` in email.py), daarna
  vanzelf normaal.
- **Egbert (bcdf9aa4)**: 28 artikelen met een verkeerd geraden rubriek (babykleding, unisex
  accessoires) niet aangepast: klantdata, beslissing Daniel.
- **Klant-eigen, niet repareren**: 26cf5471 en f8c0cce9 niet ingelogd op Vinted (scans falen);
  0b28c1ce, 1ba42900, 96e30080, 12fc61d0 met computer of extensie uit terwijl werk wacht.
- Rode proeven die al rood waren vóór 28-10 (niet van ons werk): 8 Python
  (test_veger_geeft_de_echte_reden 3, test_vinted_eigen_slottekst 4, test_vinted_vaste_staat 1;
  test_vinted_na_klik_zoeken soms) en 19 JS-proeven. test_antwoord_uit_de_code hoort bij de
  AI-klantenservice die sinds 06-09 uit staat.
- Op de planning, niet zelf oppakken: rubriekvraag kleiner maken (~9.000 tokens per product);
  AI-titels (`backend/services/titel_ai.py`, gebouwd, niet aangesloten). Zie de te-bouwen-sheet.

## De vaste routines (alles staat als bestand in de repo)

| Routine | Wie / wanneer | Bestand |
|---|---|---|
| Klantfouten | Daniels Mac 08:00 (`ochtendronde`), jouw account 14:00 (`middagronde`) | `docs/routines/klantfouten.md` |
| Onboarding nieuwe klanten, verstuurt zelf het mailtje | Daniels Mac 11:00 (`onboarding-ochtend`), jouw account 10:00 (`onboarding-middag`) | `docs/routines/onboarding-nieuwe-klanten.md` |
| Platformcontrole Vinted, Marktplaats, 2dehands | Daniels Mac 10:00 | geplande taak `omnivaleur-platformcontrole`, scripts in `scripts/platformcontrole/` |
| Kosten bijhouden (Drive-sheet "Omnivaleur kosten") | Daniels Mac, 1e van de maand | `docs/routines/kosten-bijhouden.md` |
| Schrijfstijl leren uit Daniels verzonden mail | Alleen Daniels Mac (Zoho), dagelijks 07:15 | `docs/schrijfstijl-daniel.md` |
| Creator-outreach status | Daniels Mac, maandag en donderdag 09:00 | `.claude/skills/creator-outreach/SKILL.md` |

Alle dagelijkse rondes delen één slot, dus twee rondes doen nooit tegelijk hetzelfde. Wat een
vorige ronde als gerepareerd noteerde, repareer je niet opnieuw: je meet alleen of het weg is.
Sluit elke ronde af met `ronde klaar`, ook bij afbreken.

Alleen op Daniels Mac, bewust niet bij jou: de Zoho-mailkoppeling (`zoho-mail`, zijn mailbox),
de agenda, en de back-ups in `~/.omnivaleur/backups/`.

## Werkafspraken die overal gelden

- Antwoord Nederlands, gewone taal, de vier blokjes (wat er aan de hand was, wat er nu
  veranderd is, zekerheid in %, actiepunten met `[NU/DEZE WEEK/OOIT/OVERSLAAN, tijd]`).
  Nooit een gedachtestreepje als leesteken. Daniel wil zo min mogelijk zelf doen: geef hem
  alleen wat echt alleen hij kan.
- "Waarschijnlijk goed" bestaat niet: oorzaak bewijzen, echte code draaien, voor-en-na-proef
  (oude versie laten falen). Een lege meting eerst wantrouwen.
- Elke wijziging aan klanttekst: ook in het Nederlands (`python3 scripts/i18n_extract.py`,
  daarna `--versie`; zie CLAUDE.md). De GitHub-proef kleurt anders rood.
- De auto-push-hook zet elke Edit los live (kennisbank: "auto-push-zet-tussenstand-live"), ook
  halve tussenstanden: op 28-10 stond een te brede woordenlijstregel een uur live voordat de
  proeven klaar waren. Werk in kleine, werkende stappen, of schrijf het bestand in één keer.
  Een voor-proef draai je dus tegen de commit van vóór je eerste Edit, niet tegen HEAD.
- Meten op de productiedatabase: nooit een zware telling over meerdere klanten, alleen per
  user_id of in brokken (kennisbank: "meten-op-de-productiedatabase"). Supabase geeft
  maximaal 1.000 rijen per vraag: tel grote accounts met `.range()`.
- Klantdata: alleen lege velden vullen uit een bewezen bron, oude waarde eerst bewaren, nooit
  wissen (kennisbank: "klantdata-niet-op-eigen-initiatief"). Klantmails van Daniel: concept in
  de chat, eerst `docs/schrijfstijl-daniel.md` lezen, concept bewaren met
  `scripts/schrijfstijl_leren.py concept`. Onboardingmails gaan alleen via het script.
- Een klantwens of besluit hoort meteen in de te-bouwen-sheet (CLAUDE.md).
- Leer je iets nieuws dat ook op Daniels account moet gelden: geheugenbestand schrijven,
  `python3 scripts/export_kennisbank.py`, committen. Beslissing of afspraak: dagboekregel in
  `docs/team-notes.md`, pushen.
- Zuinig met tokens: batchen, gericht lezen, geen subagents tenzij Daniel erom vraagt.

Prijs en product in het kort: EUR 19,99 per maand (Pro), 5 kanalen, 7 dagen proef plus 2
respijt; Omnivaleur Light EUR 9,99 tot 20 actieve artikelen. Details in de kennisbank
(`omnivaleur-demovideo-en-prijs`, `proefperiode-en-toegangsslot`, `omnivaleur-light-plan`).
