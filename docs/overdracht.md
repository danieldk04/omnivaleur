# Overdracht: lees dit als eerste

Bijgewerkt 16-11-2026 (middag) door het tweede account, op verzoek van Daniel: "1 op 1 met
wat je kunt zien, en dit elke sessie en elke dag bijhouden". Basis was de overdracht van
15-11 (Daniels Mac), vorige daarvoor 28-10. Alles hieronder is gemeten op 15 of 16-11-2026,
tenzij er een andere datum staat. Hoe je dit bestand zelf bijhoudt:
`docs/routines/kennisoverdracht.md` (aan het eind van elke sessie, plus een dagelijkse taak). Bewijs staat in `docs/team-notes.md` onder het
genoemde kopje, lessen in `docs/kennisbank.md`. Daniel wil zelf geen acties hoeven uitvoeren:
wat te doen is, doen de sessies zelf.

## Eén regel boven alles: je zit op een andere computer

Jouw machine is niet Daniels Mac. Dit account is een reserve voor als het hoofdaccount geen
ruimte meer heeft. Daarom geldt:

- Doe alleen werk dat in de cloud kan: de repo (git), de productiedatabase (Supabase),
  Railway, GitHub, Stripe en de gewone webpagina's. Raak niets aan wat aan Daniels Mac hangt.
- Bestaat een bestand of programma uit deze pagina niet op jouw machine (alles onder
  `~/.omnivaleur/`, LaunchAgents, de Zoho-koppeling, Chrome met Daniels inlogs), probeer het
  dan niet na te maken en ga er niet omheen. Sla die stap over en schrijf één regel in
  `docs/team-notes.md`: wat je niet kon en waarom.
- Maak nooit een tweede kopie van een taak die op de Mac draait (zie "Alleen Daniels Mac"),
  want twee rondes die hetzelfde doen veroorzaken dubbele mails en dubbele reparaties.
- Plaats, mail en betaal niets namens Daniel behalve wat de routinebestanden zelf toestaan.

**Gemeten 16-11 op het tweede account:** de sessie draait onder `/Users/Danie` en ziet
`~/.omnivaleur/` en `~/.claude/scheduled-tasks/` van Daniel, dus waarschijnlijk dezelfde Mac
onder een tweede Claude-account (niet bewezen). De regel hierboven blijft gelden: raak
niets aan wat bij Daniels eigen taken hoort. Praktisch: gebruik `/usr/local/bin/python3`
(3.13 met supabase 2.31); de standaard `python3` is 3.14 zonder httpx. Schijf is 94% vol
(13 GB vrij), let op bij video's of grote bestanden.

## Wat je in je EERSTE sessie zelf doet, zonder te vragen

1. `git pull`. Lees daarna deze pagina, de onderkant van `docs/team-notes.md` (alles sinds
   28-10; `grep -n "^## " docs/team-notes.md | tail -150`) en zoek in `docs/kennisbank.md`
   gericht op je onderwerp (`grep -n "^## " docs/kennisbank.md`; nooit het hele bestand lezen).
   Wat veranderde in de code: `git log --since="2026-10-28" --name-only --format='%h %ad %s' --date=short`.
   Let op commits met "auto: update ...": daar zit echt werk achter.
2. **Controleer je lokale `.env`.** Sinds 27-10 zijn alle sleutels vernieuwd. Je hebt de
   `sb_secret_`-sleutel nodig in `SUPABASE_KEY` en `SUPABASE_SERVICE_KEY`, en `supabase>=2.16`.
   Controle: `python3 -c "from backend.database import get_db;
   print(len(get_db().table('items').select('id').limit(1).execute().data))"` moet 1 geven.
   Lege uitkomst is een verkeerde sleutel, geen lege database. Ontbreekt de sleutel: stop,
   schrijf het in team-notes, en doe alleen nog het lezen van de repo. Daniel heeft de sleutel.
   Een ontbrekende `MAIL_PASS` betekent: geen onboardingmails versturen (zie hieronder).
3. Controleer je geplande taken (`list_scheduled_tasks`). Maak ontbrekende zelf aan, lokale
   tijd, met de tekst "Je werkt aan Omnivaleur in <jouw repomap>. Lees <bestand> in die repo
   en volg het precies. Rondenaam: <naam>.":
   - `omnivaleur-onboarding-nieuwe-klanten-middag`, dagelijks 10:00,
     bestand `docs/routines/onboarding-nieuwe-klanten.md`, rondenaam `onboarding-middag`.
   - `omnivaleur-klantfouten-middagronde`, dagelijks 14:00,
     bestand `docs/routines/klantfouten.md`, rondenaam `middagronde`.
   Dit zijn de enige twee. Staan ze er al, laat ze staan. Schrijf in team-notes dat ze staan.
   In team-notes staat sinds 20-10 geen enkele `onboarding-middag` of `middagronde`: alles
   daarna deed Daniels Mac, dus jouw account draaide niet of was niet actief.
4. Draai meteen een eerste keer wat vandaag nog niet gedraaid is. Het gedeelde slot
   `python3 scripts/klantfouten.py ronde begin <rondenaam>` zegt of een andere ronde bezig
   is of net klaar was; bij exit 3 niet forceren. Sluit elke ronde af met `ronde klaar`,
   ook bij afbreken.
5. Noem in je eerste antwoord kort wat je gezien hebt (CLAUDE.md eist dat).
6. Werk deze pagina bij als je iets afrondt of ontdekt dat hier iets niet meer klopt, en push.
   Aan het eind van elke sessie volg je `docs/routines/kennisoverdracht.md`. Ontbreekt jouw
   dagelijkse taak (`omnivaleur-kennisoverdracht-avond` 22:30 op het tweede account,
   `omnivaleur-kennisoverdracht-ochtend` 07:45 op Daniels hoofdaccount), maak hem dan aan.

## Wat er sinds 28-10 gebeurde (de lijn, niet elk detail)

**Nieuwe plannen en prijzen (besluiten 09 en 11-11, alles gebouwd maar UIT).**
- Vier plannen op actieve artikelen: Light 9,99 tot 20, Pro 19,99 tot 250, Plus 29,99 tot
  1.500, Ultra 49 onbeperkt (Etsy en nieuwe features later). Jaarbetaling: Light 99, Pro 199,
  Plus 299, Ultra 490. Bestaande klanten gaan mee. De drie accounts boven 3.000 artikelen
  stappen op: 1-1 tot 31-3 29,99, 1-4 tot 30-6 39, daarna 49. De grenzen van Pro en Plus gaan
  pas gelden vanaf 15-01-2027, voor iedereen tegelijk. Light is al live strikt 20.
- Stimulus tot 01-01-2027: 10 euro korting per betalende vriend per maand (nooit meer dan
  50% van wat de vriend betaalt, telt alleen vanaf Pro), 1 betalende vriend geeft 2 gratis
  maanden, 3 geven het AI-pakket. Gebouwd achter de vlag `REFERRAL_KORTING_AAN`, de nieuwe
  plannen achter `NIEUWE_PLANNEN_AAN` (Railway-variabelen, beide uit). Prijzen bestaan al in
  Stripe (live). Checkout, planwissel met verschil (`/api/billing/wijzig-plan`) en de
  keuzeknoppen in het dashboard zijn klaar en bewezen in Stripe-testmodus.
- **Zet geen vlag aan, verstuur geen aankondiging, bouw het AI-pakket niet af zonder Daniel.**
  Eerst wacht de uitkomst van de fotometing (19-11, taak op Daniels Mac). De concepttekst van
  de aankondiging staat in `docs/aankondiging-nieuwe-plannen.md`, niets is live.
- **Valkuil (11-11)**: een Stripe-proef die `backend.api.billing` importeert pakt de ECHTE
  sleutel uit `.env`. Zo ontstond een gearchiveerd product in de echte Stripe. Gebruik voor
  proeven altijd expliciet de testsleutel (`tests/proeven/stripe_proef_*.py`), nooit de echte.
- Regel van Daniel (09-11): alleen bouwen wat 100% zeker werkt, niets half uitrollen. Etsy is
  geblokkeerd (Daniels eigen Etsy-account), dus geen Etsy-koppeling bouwen.

**Taalmodellen, kosten en vertalen.**
- Vertalen gaat sinds 02-11 eerst via Azure Translator (gratis laag), Gemini alleen voor
  rubrieken en als reserve.
- Het betaalde Gemini-tegoed raakte op 11-11 op. Sinds 14-11 draait de server op de
  **gratis** Google-sleutel (vingerafdruk `279422aa` op `/health`); de oude betaalde sleutel
  (`27d2bcd9`) ligt alleen op Daniels Mac. De sterke modellen hebben 20 vragen per dag; bij een
  grote bulkimport blijven artikelen tijdelijk zonder rubriek en vult de nachtronde
  (`herstel_rubrieken`, 200 per nacht, alleen lege velden) aan. Rubriekvragen gaan nooit naar
  Claude (kostenrem 09-10). Zet de betaalde sleutel nooit terug zonder Daniels woord.

**Dashboard en website.**
- Startpoort voor nieuwe klanten (30-10, `frontend/poort.js`): dashboard blijft dicht tot
  extensie, marktplaats-login en minstens één item er zijn. Wie al werkte komt er nooit in.
- Nieuwe openbare site en nieuwe stijl voor dashboard en extensie (06-11, op één stylesheet).
- 15-11: onder "je computer is online" staat nu per marktplaats wanneer de verkopen voor het
  laatst zijn nagekeken (`backend/services/controle.py`; 2dehands via extensie 1.0.422).
- Wijzig je klanttekst: altijd ook Nederlands (`scripts/i18n_extract.py`, zie CLAUDE.md).

**Klantwerk dat doorloopt.**
- Reparaties sinds 28-10, kort: Vinted-woontextiel zonder kleur krijgt automatisch
  Meerkleurig of de kleur uit de titel (15-11, Toon); verwijscode-link `/r/CODE` verloor de
  code door een omleiding en is hersteld (14-11); verkoop van een Woo-product met meerdere
  stuks haalde het artikel overal weg (10-11, Toon); telefoonhouders en zilver/goud-
  voorinvulling (Goudlief, Mieneke). Details per kopje in team-notes.
- Toon (96e30080): afspraak van Daniel (11-11): wat hij zelf in Omnivaleur kan, blijft hij
  zelf doen. Contact is voor support en fouten, niet om voor hem te werken.
- Janina (f0cead08, creator, Duitse Vinted-voorraad): gratis toegang staat (14-11),
  commissie 25%. Gratis toegang zet de routine alleen zelf bij Amanda, nergens anders.
- Terughaalronde verlopen proefaccounts (09 tot 13-11): Daniel verstuurde 37 persoonlijke
  mails, de opvolging staat als concept klaar; hij verstuurt. Wie vroeg te stoppen staat in
  `mail_unsubscribed`. Twee accounts zijn Daniels eigen en worden nooit gemaild of meegeteld
  (dkresellacademy@gmail.com, aertssen.pleun@gmail.com).
- Monaim heeft nu niets met Omnivaleur te maken (09-11). Noem hem nooit in een reactie of
  klanttekst.

## Wat nu open staat (niemand hoeft te wachten op Daniel tenzij er "beslissing" staat)

- **Nieuw sinds 16-11: verlopen advertenties zijn zichtbaar** (klokje op het kanaalicoon, tabblad
  Expired bij Items, regel onder de kanaaltegel, popup en rondleiding; team-notes "verlopen
  advertenties zichtbaar"). Nog te doen door wie eerst werkt: op telefoonbreedte nalopen, en de
  Drive-kopie van `docs/klantenservice-brein.md` bijwerken (Drive-koppeling had geen verbinding).
- **Controleren op 17-11-2026, door wie er dan als eerste werkt**: Daniels eigen account
  (3bfbed2c) kreeg sinds 19-09 geen verlengingen en herplaatsingen omdat de poort van de
  nachtrondes de eigenaar niet kende (gerepareerd 16-11, d801091d, team-notes "eigenaar-poort").
  2dehands is bewezen (31 verlengingen ingepland en lopend op 16-11). Marktplaats nog niet: kijk
  of er op dat account opdrachten van de nachtronde staan (verwijderen plus plaatsen, hooguit
  ~25 per dag). Staan ze er niet, zoek dan verder in `relist_expiring_marktplaats`.
- **Gepland voor 17-11-2026, door wie er dan als eerste werkt (Daniel, 16-11)**: in Google Analytics
  (property Omnivaleur, Beheer > Gebeurtenissen > tabblad Recente gebeurtenissen) de gebeurtenis
  `echte_bezoeker` markeren als belangrijke gebeurtenis (ster ervoor). Hij staat sinds 16-11 live op / en /nl
  en verschijnt pas na een eerste echt bezoek; staat hij er nog niet, probeer het een dag later. Moet je
  Google-login hebben en zie je het welkomstscherm voor een nieuw account: NIET op "Meting starten" klikken,
  het is dan het verkeerde account; vraag Daniel in te loggen. Daarna: kijk in beheer ("Landen, 28 dagen")
  of NL+BE naast de rest klopt, en meld het in team-notes. Daarna dit punt hier weghalen.
  Achtergrond: US/China/Singapore waren machines (20% of minder betrokken), zie team-notes 16-11.
- **GA4 en Stripe, nagekeken 16-11**: `stripe.com` staat al in Ongewenste verwijzingen (Google-tag, Instellingen).
  Niets gewijzigd. Toch stonden er in de 7 dagen daarvoor 16 sessies met bron checkout.stripe.com: meet over
  een week opnieuw (Verkeersacquisitie, bron/medium). Komen er dan nog steeds nieuwe bij, dan werkt de lijst
  niet voor de gtag in de HTML en is er een echt probleem.
- **Cloudflare 4xx, gemeten 16-11 (24 uur)**: 152.7k van de 157.8k fouten zijn **422** = extensie zonder
  inlog (Authorization-kop ontbreekt; zie kennisbank), de rest 404 4.1k, 401 756. De extensie blijft dan
  elke ~15 s vier kanalen vragen (`pollJobsEenRonde`, `extension/background.js`). Kost de server vrijwel niets
  (geweigerd voor de database), dus GEEN spoed. Wil je het wegnemen: in `pollJobsEenRonde` overslaan zonder
  Authorization-kop, test op de echte extensie, en dan pas een Web Store-versie (Daniel uploadt).
- **Extensie in de Web Store**: de Web Store levert 1.0.421, de repo staat op 1.0.422
  (`dist/omnivaleur-extension-1.0.422.zip`). Uploaden kan alleen met Daniels Google-account.
- **Tijdgebonden**: 19-11 uitkomst fotometing AI-pakket (Mac); 26-11 SEO-nameting (Mac);
  1-12 kosten- en doelenronde (Mac); 15-01-2027 grenzen Pro en Plus gaan gelden.
- **Klanten, stand 15-16 november (nog niet opgelost, meet opnieuw voor je iets aanneemt)**:
  Toon (96e30080): kelim KEXL33 heeft foto's alleen op Marktplaats-adressen die nu 404
  geven, 20 van 1.688 artikelen zitten zo (Toon moet foto's opnieuw toevoegen); merk "Gaudi"
  vindt de Marktplaats-merkkiezer niet en er is geen terugval (open: eerst meten wat de
  kiezer toont); MP "Not published" zonder rood veld 2x op tapijten, oorzaak niet bewezen;
  Bieden-zoekertjes (prijs 1,00) geven bewust "geen prijsveld", klant-eigen. Janneke
  (31d28378), 1ba42900, Goudlief, bcdf9aa4, 0b28c1ce: extensie dagen offline, wachtrijen
  groeien, klant-eigen. 1ba42900 is op 2dehands uitgelogd. Facebook Staat-veld en Vinted
  LEGO maat/kleur: eenmalig, onbewezen. Nieuwe proefklant Janina (f0cead08) staat op
  gratis toegang met 25% commissie, nog niets geplaatst. tamboer.joost: nieuwe proef tot 20-11.
- **Terughaal opvolging (13-11)**: 33 zwijgers hebben een opvolgmail als concept klaarstaan
  (volgens team-notes 13-11 "concepten/"; die map bestaat niet in `data/schrijfstijl/terughaal/`,
  daar staan alleen `mails.txt`, `mails.json`, `niet_mailen.json`, `kanalen.md`; of ze in
  Daniels Zoho staan is niet gecontroleerd, die koppeling hoort bij zijn account). Daniel
  verstuurt. Antwoordconcept voor jordi.waning ook. Kanalen zonder mail: `kanalen.md`.
- **Social video's**: week 47 heeft vijf video's klaar in Drive (Social media video's
  Claude/Week 47), nog niets geplaatst of gemeten. Schedchie-API-sleutel pas na Daniels eerste
  betaling; vanaf week 47 opnieuw vragen. Daniel plaatst alles zelf.
- **Beslissing Daniel**: wanneer de nieuwe plannen en de vriendenactie live gaan, en de
  aankondiging. Niet zelf aanzetten.
- **Niet opnieuw nagekeken sinds 28-10, dus alleen een startpunt**: Janneke (31d28378, Vinted
  stond tot 31-10 stil), Goudlief (5aae4954, wacht op extensie 1.0.419 of nieuwer, telefoon-
  koorden), Egbert (bcdf9aa4, 28 artikelen met een geraden rubriek: klantdata, beslissing
  Daniel), Mieneke (09e089ec, 12-11: 2dehands rekent kosten bij plaatsen na Marktplaats).
  Lees hun kopjes in team-notes en meet zelf opnieuw voor je iets aanneemt.
- **Klant-eigen, niet repareren**: klanten die niet ingelogd zijn op een marktplaats of
  waarvan computer of extensie uit staat terwijl werk wacht.
- Rode proeven die al rood waren vóór 28-10 (niet van ons werk): 8 Python
  (test_veger_geeft_de_echte_reden, test_vinted_eigen_slottekst, test_vinted_vaste_staat;
  test_vinted_na_klik_zoeken soms) en 19 JS-proeven. test_antwoord_uit_de_code hoort bij de
  AI-klantenservice die sinds 06-09 uit staat. Meet voor je werk wat al rood was.
- Op de planning, niet zelf oppakken: alles in de Drive-sheet "Omnivaleur te bouwen"
  (`scripts/te_bouwen.py lijst`), o.a. rubriekvraag kleiner maken, AI-titels
  (`backend/services/titel_ai.py`, gebouwd, niet aangesloten), kanalen.

## De vaste routines (alles staat als bestand in de repo)

| Routine | Wie / wanneer | Bestand |
|---|---|---|
| Klantfouten | Daniels Mac 08:00 (`ochtendronde`), **jouw account 14:00** (`middagronde`) | `docs/routines/klantfouten.md` |
| Onboarding nieuwe klanten | Daniels Mac 11:00 (`onboarding-ochtend`), **jouw account 10:00** (`onboarding-middag`) | `docs/routines/onboarding-nieuwe-klanten.md` |
| Platformcontrole Vinted, Marktplaats, 2dehands | Alleen Daniels Mac 10:00 (Chrome) | `docs/routines/platformcontrole.md` |
| Kosten en doelen (Drive-sheet "Kosten en doelen (Omnivaleur en Revaleur)") | Alleen Daniels Mac, 1e van de maand | `docs/routines/kosten-bijhouden.md` |
| Schrijfstijl leren uit Daniels mail | Alleen Daniels Mac (Zoho), 07:15 | `docs/schrijfstijl-daniel.md` |
| Creator-outreach status | Alleen Daniels Mac, ma en do 09:00 | `.claude/skills/creator-outreach/SKILL.md` |
| Facebook-reactiebot bijwerken (alleen lezen) | Alleen Daniels Mac, 07:30 | `docs/routines/facebook-reactiebot.md` |
| Social video's | Alleen Daniels Mac, dinsdag 09:30 | `docs/routines/social-videos.md` |
| Reageren op X, Indie Hackers, Facebook, Instagram | Alleen Daniels vastgepinde gesprek | `docs/routines/social-reageren.md` |
| Fotometing AI-pakket | Alleen Daniels Mac (LaunchAgent, haalt zichzelf weg) | `scripts/meet_fotoadvertentie.py` |
| Kennisoverdracht (overdracht.md gelijk houden) | Aan het eind van elke sessie; dagelijks 07:45 Daniels hoofdaccount, 22:30 tweede account | `docs/routines/kennisoverdracht.md` |

Onboardingmails: alleen `scripts/onboarding_mail.py stuur ... --echt` (harde controles in de
code), en alleen als `MAIL_PASS` in jouw `.env` staat. Staat die er niet, zet de mail dan
klaar in team-notes en verstuur niets; Daniels Mac pakt het in zijn ronde op.

Alle dagelijkse rondes delen één slot, dus twee rondes doen nooit tegelijk hetzelfde. Wat een
vorige ronde als gerepareerd noteerde, repareer je niet opnieuw: je meet alleen of het weg is.

## Alleen Daniels Mac, bewust niet bij jou

De Zoho-mailkoppeling (zijn mailbox), de agenda, Chrome met zijn inlogs (platformcontrole,
Facebook, social, Web Store), de map `~/.omnivaleur/` (back-ups, sleutels, meetresultaten,
`gemini-betaald-oud.txt`), de LaunchAgents, de map `data/schrijfstijl/` en `data/social/`
(buiten git), en alles wat plaatst of verstuurt op sociale media. Op jouw machine bestaat dit
niet en hoort het ook niet te bestaan.

## Werkafspraken die overal gelden

- Antwoord Nederlands, gewone taal, de vier blokjes (wat er aan de hand was, wat er nu
  veranderd is, zekerheid in %, actiepunten met `[NU/DEZE WEEK/OOIT/OVERSLAAN, tijd]`), kort,
  één scherm. Nooit een gedachtestreepje als leesteken. Daniel wil zo min mogelijk zelf doen:
  geef hem alleen wat echt alleen hij kan.
- "Waarschijnlijk goed" bestaat niet: oorzaak bewijzen, echte code draaien, voor-en-na-proef
  (oude versie laten falen). Een lege meting eerst wantrouwen. Alleen bouwen wat 100% zeker
  werkt.
- Elke wijziging aan klanttekst: ook in het Nederlands (`python3 scripts/i18n_extract.py`,
  daarna `--versie`). De GitHub-proef kleurt anders rood.
- Klantberichten: nooit "sorry", "ligt aan ons" of "onze fout". Eerst het goede nieuws, dan
  neutraal wat er speelde en wat de klant nu kan. Concept in de chat, eerst
  `docs/schrijfstijl-daniel.md` lezen.
- De auto-push-hook zet elke Edit los live, ook halve tussenstanden (kennisbank:
  "auto-push-zet-tussenstand-live"). Werk in kleine, werkende stappen, of schrijf het bestand
  in één keer. Een voor-proef draai je tegen de commit van vóór je eerste Edit, niet HEAD.
- Meten op de productiedatabase: nooit een zware telling over meerdere klanten, alleen per
  user_id of in brokken (kennisbank: "meten-op-de-productiedatabase"). Supabase geeft
  maximaal 1.000 rijen per vraag: tel grote accounts met `.range()`.
- Klantdata: alleen lege velden vullen uit een bewezen bron, oude waarde eerst bewaren, nooit
  wissen (kennisbank: "klantdata-niet-op-eigen-initiatief").
- Een klantwens of besluit hoort meteen in de te-bouwen-sheet (CLAUDE.md).
- Leer je iets nieuws dat ook op Daniels account moet gelden: geheugenbestand schrijven,
  `python3 scripts/export_kennisbank.py`, committen. Beslissing of afspraak: dagboekregel in
  `docs/team-notes.md`, pushen.
- Zuinig met tokens: batchen, gericht lezen, geen subagents tenzij Daniel erom vraagt.

Prijs en product vandaag live: EUR 19,99 per maand (Pro), 5 kanalen, 7 dagen proef plus 2
respijt; Omnivaleur Light EUR 9,99 tot 20 actieve artikelen. De nieuwe plannen staan uit (zie
boven). Details in de kennisbank (`omnivaleur-demovideo-en-prijs`, `proefperiode-en-toegangsslot`,
`omnivaleur-light-plan`).
