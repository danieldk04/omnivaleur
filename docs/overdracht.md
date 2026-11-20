# Overdracht: lees dit als eerste

Aangevuld 20-11-2026 door de ochtendronde klantfouten (Daniels Mac, alleen de regel over herplaatsrubriek en Shopify-dubbelen). Bijgewerkt 17-11-2026 (op verzoek van Daniel, voor de overdracht) door Daniels hoofdaccount; daarvoor 16-11-2026 22:30 door het tweede account. Eerder die dag op verzoek van Daniel: "1 op 1 met
wat je kunt zien, en dit elke sessie en elke dag bijhouden". Basis was de overdracht van
15-11 (Daniels Mac), vorige daarvoor 28-10. Alles hieronder is gemeten op 15 of 16-11-2026,
tenzij er een andere datum staat. Hoe je dit bestand zelf bijhoudt:
`docs/routines/kennisoverdracht.md` (aan het eind van elke sessie, plus een dagelijkse taak). Bewijs staat in `docs/team-notes.md` onder het
genoemde kopje, lessen in `docs/kennisbank.md`. Build in public (Daniel, dag 163 op 16-11): open beloften aan lezers en ideeën uit Indie Hackers-reacties staan in `docs/build-in-public-ideeen.md`; vul dat aan en kijk het na bij elke overdracht. Sinds 17-11 beantwoordt de reageerronde ook de reacties onder zijn eigen posts (X, Indie Hackers, Bluesky; blok BUILD IN PUBLIC in `data/social/ronde-prompt.txt`, hulp: `scripts/bip_reacties.py`, `scripts/ih_onbeantwoord.js`), legt vragen, ideeën en toezeggingen met terugkomdatum vast in die lijst, en meldt elke ochtend (eerste cron-ronde in het gesprek na 08:00) wat aan de beurt is. Daniel wil zelf geen acties hoeven uitvoeren:
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

- 20-11 (klantfouten ochtend): herplaatsen van een VERLOPEN advertentie kreeg nooit zijn eigen rubriek (/seller/view-adres onleesbaar, zoek-API toont verlopen advertenties niet). mp_enrich leest nu het kortadres /m{nr}, ook als 410 (13c0a26b); 212 wachtende herplaatsingen bijgewerkt. Zilverwebsite (26cf5471): 276 webshop-dubbelen samengevoegd; 3 in de webshop verkochte stukken (2 Zilverwebsite, 1 Esther) stonden nog op MP, nu als verkocht geboekt. Nacontrole-script geeft geen valse prijs/omschrijving/weg meer. Detail in team-notes.

## Wat nu open staat (niemand hoeft te wachten op Daniel tenzij er "beslissing" staat)

- **GA4, gedaan 17-11 (Daniel, tip van een Indie Hackers-lezer), voor de andere developer:** (1) `echte_bezoeker` staat als
  belangrijke gebeurtenis; het gegevensfilter "Internal Traffic" stond al op Actief en sluit `traffic_type = internal` uit.
  (2) Nieuwe gebeurtenis `verkoper_intentie` (klik op aanmelden, inloggen of prijzen, één keer per pagina, parameter `doel`) op / en
  /nl. **Jij mag hem als sleutelgebeurtenis aanvinken zodra hij in GA4 verschijnt** (Beheer, Gebeurtenissen, Recente gebeurtenissen,
  ster ernaast; hij verschijnt pas na de eerste klik, dus klik zelf een keer op "Start free trial" op omnivaleur.com/?intern=0 of
  vraag Daniel). De GA4 van Daniel is bereikbaar in de ingelogde browser van de sessie, property Omnivaleur, stream 15253103769.
  (3) Eigen verkeer: bewust geen IP-regel (Daniels IPv4 en IPv6 wisselen) maar een apparaatvlag: omnivaleur.com/?intern=1 op een
  eigen apparaat zet `traffic_type=internal` mee in alle pagina's (?intern=0 haalt het weg). Zet dit ook op jouw eigen browsers
  voordat je het dashboard of de site test, anders tellen je proefaanmeldingen mee. Tests: tests/verkoper-intentie-test.js en
  tests/ga4-intern-verkeer-test.js. Les van de lezer: 47 van 48 Search Console-klikken zijn merknaamzoekers, GA4 telt die als organisch
  terwijl een post of groep de aanleiding was; beoordeel posts dus niet alleen op GA4, en laat analytics een paar weken met rust.
- **EERSTE KLUS VOOR DE ANDERE DEVELOPER (Daniel, 17-11): de hele eerste-minuten-loop doorlopen met een vers account en alles
  rechtzetten wat rommelig of onduidelijk is.** Daniel kan dat niet op het tweede account en jij wel: jij kijkt mee
  op zijn account. Uitgangspunt van Daniel, onthoud het: elke nieuwe klant heeft haast, heeft een minuscule aandachtsspanne,
  wil in twee minuten zien "dit werkt voor mij" en je legt nooit verantwoordelijkheid bij de klant (geheugen
  `nieuwe-klant-heeft-haast`). Beoordeel elke stap als iemand die Omnivaleur nog nooit zag.
  Wat al staat (alles live, 16 en 17-11): poort.js start het inlezen vanzelf, "Plaats nu" kiest één artikel per kanaal,
  hulpknop na 10 min, link naar de computer per mail, stilstandmail na een uur (stil_na_aanmelding.py), voortgangsbalk,
  "Account aangemaakt" vooraf afgevinkt, extensie 1.0.424 tot 1.0.426 (3 tegelijk lezen, eerste 20 vooruit via
  /api/jobs/{id}/scan-deel, merk en maat uit de pagina, tweede leesronde, ruimer budget).
  Daniels testaccount: uid `ac7a394f-f25b-4c0d-8187-0743ea27a13a` (aangemeld 16-11 16:24 UTC). Stand 17-11: geen extensie
  gemeld (heartbeat leeg), 0 artikelen, 0 opdrachten, de stilstandmail is wel uitgegaan (19:21 UTC, drie uur te laat omdat elke
  deploy de uurklok van de planner terugzet). Meet ALLEEN per user_id (kennisbank: meten-op-de-productiedatabase), nooit jobs zonder
  user_id: een eerste meting zonder filter liep op 16-11 in een statement timeout.
  Wat je doet, in volgorde: (1) installeer de extensie in jouw Chrome en log in op dat account, (2) loop de poort af en let op
  tekst, taalmix, lege omschrijvingen, tijd tot het eerste artikel, voortgang die je ziet, meldingen die een nieuweling niet snapt,
  (3) plaats het eerste artikel met "Plaats nu" en meet of het echt online staat, (4) reken elke fout na met voor-en-na-proef.
  Open punten die Daniel al kent: de extensie haalt bij ~197 van 257 artikelen de omschrijving niet zelf op (de aanvulstap
  in het dashboard doet dat, nu 12 rondes; oorzaak niet gevonden, scan_meta.enrichment_retry laat het zien); de
  oude Engelse aanvulmelding blijft zichtbaar na een eerdere import; lege omschrijvingen worden na import niet geblokkeerd;
  maat ontbreekt bij 13 van 253; het "hoe ziet het eruit op het andere kanaal"-voorbeeld bij Plaats nu is niet gebouwd (idee
  van een Indie Hackers-lezer); uurklok van de planner reset bij deploy (interval-taken zonder vaste tijd).
  Daarna in de te-bouwen-sheet: regel "Quick win in 2 minuten" bijwerken.

- 16-11: quick win voor nieuwe klanten gebouwd en live (poort.js, account.py). Meting: van 22
  aanmelders in 30 dagen kwam 45% nooit bij een artikel, eerste artikel pas na 30 tot 150 min.
  Nu: inlezen start vanzelf zodra extensie en login kloppen (elke 10 min opnieuw zolang er geen
  artikel is), dan staat er één artikel klaar met "Place it now" (Marktplaats, 2dehands, Vinted,
  geen Facebook; alleen artikelen zonder ontbrekende velden; eigen foto's eerst), na 10 min vast
  een knop "Help me" (mail naar Daniel, antwoordadres de klant), en op de telefoon mailt de server
  de link naar de computer. NOG NIET GEZIEN met een echt nieuw account in Chrome; de proef
  hierna is de eerstvolgende aanmelder. Mail na een uur stilstand ook gebouwd
  (backend/services/stil_na_aanmelding.py, elk uur, één keer per klant, overdag). Extensie forceren te updaten
  bewust niet gebouwd: de 22 aanmelders draaiden 1.0.400 tot 1.0.423, boven de ondergrens; ze werden stil, ze waren niet oud. Proefklok blijft vanaf aanmelding (Daniel besloot).

- 16-11 later: import sneller en completer (extensie 1.0.424, gebouwd in dist/, WACHT OP UPLOAD door Daniel
  naar de Chrome Web Store). Marktplaats/2dehands lezen advertenties nu 3 tegelijk, sturen de eerste 20 na
  ongeveer een halve minuut vooruit via POST /api/jobs/{id}/scan-deel (alleen kandidaten), het dashboard
  importeert die meteen (wachtOpScan, deel_klaar) zodat "Plaats nu" kan; merk en maat komen uit het
  "attr"-blok van de advertentiepagina (Merk, size) of uit "Heren M" in de titel. Gemeten op Daniels
  eigen 253 geïmporteerde artikelen: 0 met merk of maat, 176 missen merk en 191 maat voor 2dehands; die
  worden bij een nieuwe scan met 1.0.424 aangevuld (bestaande backfill). Niet gezien met een echte scan.
  Dashboard (live): API-kanalen alleen na koppelen, wachtende scan telt niet als stilstand, eerste
  plaatsing kiest per kanaal een artikel dat daar nog niet staat.
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
- **Extensie in de Web Store** (stand 16-11 avond): repo en manifest staan op 1.0.426. Nieuw
  sinds 1.0.424: 1.0.425 (tweede leesronde voor artikelen zonder omschrijving) en 1.0.426
  (2dehands verlengen herlaadt de pagina bij een leeg antwoord; proef
  `tests/verlengen-2dehands-verversen-test.js`). Wat de Web Store nu levert is niet gecontroleerd
  (laatst bekend 1.0.421). Uploaden kan alleen met Daniels Google-account: Daniel, zip in `dist/`.
  Open: de tests verlengen-2dehands-gericht-lezen en loopt-af falen al voor 1.0.426 (nagebouwde
  omgeving mist _klokTabbladen), niemand heeft ze gerepareerd.
- 16-11 avond: automatische import doet nu twaalf aanvulrondes voor omschrijving en prijs,
  voortgangsbalk bij import (commit 131a9e5c, 91597261). Eerste echte scan met 1.0.425 of 1.0.426
  is nog niet gezien (open voor wie eerst werkt). Shopify zonder koppeling aangevinkt gaf
  een scanfout bij een nieuwe klant; al gerepareerd in 220fd5bd. Server draait commit ef67b846.
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

## 17-11-2026: rubrieken in groepen (voor wie hierna verder gaat)
- WAT: nieuwe klant 3eeceb51 (info@hetisvintastisch.nl) kon niets plaatsen, 267 van 294 artikelen zonder rubriek. Oorzaak: gratis Google-sleutel op (429) en Claude voor rubrieken bewust uit (te duur per losse vraag). Zijn artikelen zijn gevuld (nog 2 leeg, die kiest hij zelf). Daniel stuurde hem een mail, geen actie meer.
- GEBOUWD: `backend/services/rubriek_groepen.py`, job `rubrieken_in_groepen` elke 5 min in scheduler.py. 20 artikelen per vraag aan Claude Haiku, rubriekenlijst in de systeemtekst (cache). $0,0004 per artikel tegen $0,0095 per losse vraag; 294 artikelen ~13 cent. Dagplafond 3000 artikelen (~1,20). Alleen artikelen van de laatste 72 uur, alleen lege rubrieken, nooit overschrijven. De vraagtekst staat in `imports._bouw_rubrieksprompt` (identiek aan de oude). Tests: tests/test_rubriek_groepen.py.
- GEMETEN: eerste echte ronde op de server: 400 bekeken, 390 gevuld (ook van andere klanten, alleen lege velden). Google-eerst GEMETEN en NIET gebouwd: zelfde kwaliteit op tak (82% tegen 81%), maar exact 42% tegen 54%, en kiest bij 44 van 80 anders dan Haiku; besparing 13 cent per import. Daniel hoeft hier niets meer over te beslissen, tenzij hij wil dat het toch gratis wordt.
- NIET GEDAAN / OPEN: nog niet gezien bij een echt nieuw account na deze fix (volgende nieuwe klant: kijk in `python3.13 scripts/nieuwe_klanten.py` of "rubrieken: (geen)" bijna 0 is). Kijk 1 keer per dag in de Railway-log naar `Rubriekgroepen:` (bekeken/gevuld/zonder antwoord); veel "zonder antwoord" betekent dat Anthropic niet antwoordt of het tegoed op is.
- VALKUILEN: lokaal is de Anthropic-sleutel in .env ongeldig; meten met echte sleutels gaat via `npx -y @railway/cli run python3.13 script.py`. De productiedatabase alleen per user_id meten, behalve de rubriekrondes (die staan al zo). Zie ook docs/kennisbank.md, les rubrieken-in-groepen-van-twintig.

## 18-11-2026: uitnodigsysteem verder gebouwd, alles achter vlaggen (Claude, Daniels Mac)
- Gebouwd en bewezen, staat UIT: klassement, niveaus (Brons 1, Zilver 3, Goud 5, Platina 10) en Founding Circle (eerste 10 met 5 betalende vrienden). Rekenregels `backend/services/klassement.py` (7 tests), API `/api/referrals/klassement` en `/klassement/naam` achter vlag `KLASSEMENT_AAN` (Railway, standaard uit), kaart op het Uitnodigen-scherm in app.html. Deelname vrijwillig met een naam, opgeslagen als instelling `klassement_naam` (geen migratie). Op echte data is er niets te meten: er bestaat 1 verwijzing, van een creator.
- De trap op het Uitnodigen-scherm is horizontaal (drie kaarten). Nog steeds achter `REFERRAL_KORTING_AAN`.
- Fasering grote drie (29,99 vanaf 1 jan, 39 vanaf 1 apr, 49 vanaf 1 jul): `backend/services/fasering.py` + `scripts/fasering_grote_drie.py` (droog draaien zonder `--toepassen`). Bewezen met een Stripe-testklok op SDK 10.12.0 en 15.3.0: `tests/proeven/stripe_proef_fasering.py`. Niet bewezen: automatische btw (testaccount heeft die niet; live abonnementen hebben hem, het script kopieert de instelling). De eerste nieuwe prijs geldt vanaf de factuur NA 1 jan, niet voor 1 jan.
- Onboardingroutine kent nu `scripts/nieuwe_vrienden.py` en geeft vrienden van klanten voorrang. Het plaatsen van "de eerste 100 artikelen" kan alleen de klant zelf (zijn extensie); wij lezen in en lopen na. Mail A belooft meer dan dat: Daniel moet de zin kiezen.
- NIET gebouwd, bewust: "Wat is er nieuw"-venster, updatelog en rondleiding voor de uitnodigactie. Het bestaande mechanisme is een enkele NIEUWS_ID; een tweede variant achter een vlag zou het live venster van 16-11 en tests/test_updates_log.py raken. Teksten staan klaar in docs/aankondiging-nieuwe-plannen.md; op de dag zelf is het een ruil van id, tekst en rondleiding.
- Daniel vroeg: wacht op de fotometing van 19-11 (101 van 110 artikelen op 18-11) voor het AI-pakket in de trap; Etsy later, vermoedelijk via een CSV-bestand.

## 20-11-2026: AI-pakket gebouwd, donker achter AI_PAKKET_AAN (Claude, geplande taak)
- Vlag `ai_pakket_aan` (config.py) staat UIT. Uit = alle routes onder `/api/ai-pakket` geven 404 en niets draait. Zet hem niet aan zonder besluit van Daniel.
- Gebouwd en getest (tests/test_ai_pakket.py, 40 groen): `backend/services/ai_bulk.py` (bulkopdracht: model kiest een vaste bewerking, gewone code controleert en voert uit, voorbeeld op 5 artikelen, bevestigen, extra bevestiging bij prijs onder 1 euro of meer dan verdubbeld, ongedaan maken dat latere eigen wijzigingen van de klant laat staan), `ai_quota.py` (maandplafond per klant in de instellingenrij, sleutel `ai_pakket`, overleeft herstart), `ai_tekst.py` (titels inkorten en beschrijving herschrijven met harde controle), `backend/api/ai_pakket.py`.
- Gemeten op echte artikelen (gratis Gemini 3.1 flash-lite): bulk 30 opdrachten, 0 gevaarlijk uitgevoerd; titels 136 lange titels, 131 door de controle (96,3%); beschrijvingen 165, 146 door de strenge controle (88,5%, dus UIT het pakket). Foto naar advertentie niet beloven (19-11).
- NIET gebouwd: het dashboardscherm voor de bulkopdracht en het aansluiten van titels inkorten op het plaatsen (`_mp_titel_binnen_grens` in backend/api/jobs.py is de plek). Teksten voor venster en updatelog staan klaar in docs/aankondiging-nieuwe-plannen.md.
- Meetscript: `scripts/meting_ai_pakket.py` (steekproef, bulk, titels, beschrijvingen); de gratis sleutel geeft 500 vragen per dag per model, zet `MODEL=gemini-3.1-flash-lite` als het standaardmodel op is. Uitkomsten in ~/.omnivaleur/meting_ai/.

## 20-11-2026 (later): aankondiging plannen, Etsy en AI in frontend
- Live: blok "What is coming" bovenaan Wat is nieuw (app.html #komt-eraan), updatelogbericht 2026-11-plannen-en-ai, venster en rondleiding (plannen-en-ai), notitie #plannen-vanaf-januari boven Account, plannenblok op index.html en nl.html (#plans-next, eigen stijl in het blok zelf). Vertaald via nl.json.
- Niets functioneels aan: NIEUWE_PLANNEN_AAN, REFERRAL_KORTING_AAN, KLASSEMENT_AAN en AI_PAKKET_AAN staan niet in Railway (uit). Bij elke volgende stap (Plus/Ultra live, AI-onderdeel af) de stand in #komt-eraan aanpassen, in beide talen, en de site.
- Bij livegang 1 januari: Stripe-prijs-id's Plus en Ultra in Railway, vlag aan, tekst "From 1 January" in blok en notitie omzetten naar de dan geldende stand.

## 20-11-2026 (avond): vriendenactie aan en prominent
- Trap 1/3/5 (2 maanden plus 10 euro, AI-pakket, Ultra) staat in Wat is nieuw, popup, rondleiding, Uitnodigen en op de site. REFERRAL_KORTING_AAN aan in Railway. Open: ontgrendelen van AI-pakket en Ultra bij 3 en 5 vrienden is nog niet gebouwd; mail A nog te versturen.

## 20-11-2026 (nacht): OVERDRACHT AAN DE ANDERE ONTWIKKELAAR (Daniel, 20-11)
Wat er gebeurde sinds Daniel weer zelf aan het roer zit (alles op main, geen losse eindjes in git):
- 33de4f33 en 8a90ff5a: AI-pakket donker gebouwd (bulkopdracht met voorbeeld en ongedaan, titels inkorten, beschrijving per kanaal, maandplafond) achter AI_PAKKET_AAN (uit).
- bd8a124d: metingen in scripts/meting_*.py met uitkomsten in ~/.omnivaleur/meting_ai/ (prijsadvies 46%, niet beloven; foto naar advertentie kleur 51 tot 67%, merk 41 tot 52%, maat 0%, niet beloven).
- 2f7a178e: aankondiging plannen 1 januari, Etsy komt eraan, AI-pakket (in aanbouw / in test) in dashboard en op de site.
- d61785e5: vriendenactie prominent (trap 1/3/5) en REFERRAL_KORTING_AAN AAN in Railway. NIEUWE_PLANNEN_AAN, KLASSEMENT_AAN en AI_PAKKET_AAN zijn nog uit. Plus- en Ultra-prijs-id's ontbreken in Railway.
- Mail A (vrienden) en mail B (nieuwe plannen, een mail voor iedereen met voorbeelden) staan klaar in docs/aankondiging-nieuwe-plannen.md. NIET verstuurd. Mail B moet uiterlijk 1 december de deur uit (voorwaarden art. 5, 30 dagen).

Jouw opdracht, in deze volgorde (Daniel verdeelt het werk):
1. Ontgrendelen bij 3 en 5 betalende vrienden BOUWEN. Nu belooft het dashboard het (AI-pakket bij 3, Ultra bij 5, zolang zij betalen) maar er wordt niets ontgrendeld. Eerst dit, voor de achtergrondverwijdering.
2. Achtergrond verwijderen en de andere AI-onderdelen (zie lijst "Building" en "Testing" in app.html #komt-eraan-ai). Een functie gaat pas live bij minstens 95 op 100 goed op echte artikelen. Werk de statussen in dashboard EN op de site (EN en NL) bij als iets verschuift. Open bouwwerk: scherm voor de bulkopdracht, titels inkorten koppelen aan het plaatsen (_mp_titel_binnen_grens in backend/api/jobs.py), koperbericht-assistent op echte data, waarschuwing "foto te klein".
3. Plansysteem per 1 januari: Plus- en Ultra-prijs-id's in Railway, NIEUWE_PLANNEN_AAN aan, de tekst "From 1 January" in #komt-eraan en #plannen-vanaf-januari omzetten naar de dan geldende stand.

**Controleer alles op 100% juistheid (Daniel vraagt dit expliciet), zonder fouten of misvattingen over hoe het systeem werkelijk werkt:**
- Vriendenactie live met echt geld: wordt het tegoed per betaalde vriendenfactuur goed afgeboekt in Stripe (korting nooit hoger dan 50% van wat de vriend betaalt, Light-vriend telt niet, 2 gratis maanden vóór 1 januari, 10 euro vastgezet voor wie vóór 1 januari binnenkomt)? Draai tests/proeven/stripe_proef_vriendenkorting.py opnieuw en kijk de eerste echte vriend na in Stripe.
- Staan alle teksten in dashboard en site gelijk aan wat de code doet (bedragen, grenzen, data, 15 januari-uitstel, "blijft online, alleen nieuwe artikelen wachten")? Ook de oude teksten die "1 maand gratis" zeiden zijn aangepast; zoek op restanten.
- Staan AI-onderdelen niet als "klaar" terwijl klanten ze niet kunnen gebruiken? Prijsadvies mag nergens beloofd worden.
- Mail A en mail B: kloppen de voorbeelden (180 artikelen, 600, boven 1.500, fasering 29,99/39/49) met wat het plansysteem straks echt rekent?
- tests/test_updates_log.py, tests/test_i18n_compleet.py en tests/test_referral_korting.py moeten groen blijven.

- Aanvulling 20-11 (nacht): (a) aangebrachte vrienden moeten 14 dagen proef krijgen (Daniel); de code geeft iedereen 7 (backend/api/billing.py _get_or_create_subscription, ook expire_trials en de proef/respijt-regels en de teksten op register.html nakijken). Bouw dit, daarna "14 dagen" in mail A. (b) Mail B noemt de fasering voor accounts boven 1.500 niet meer; die ene paar klanten krijgen een aparte mail. Mail A mag naar alle klanten.

- 20-11 nacht: mail A en B zijn verstuurd (21 adressen, zie team-notes). URGENT: mail A zegt 14 dagen proef voor vrienden, de code geeft 7. Bouw dit als eerste, en zet het aantal ook op register.html. Daarna ontgrendelen bij 3 en 5 vrienden, dan de AI-onderdelen.

## 20-11-2026 (middag): 14 dagen vrienden en ontgrendelen gebouwd (Claude)
- 14 dagen proef voor wie via een klantlink (kind='user', niet de eigen code) binnenkomt: `proefdagen_voor` in backend/api/billing.py, rest blijft 7. Registratiepagina toont 14 dagen en de tekst bij uitgenodigden. Tests: tests/test_proefdagen_vriend.py. Open: kijk de eerste echte vriend na (trial_ends_at 14 dagen), en of respijt en herinneringen van expire_trials ook voor 14 dagen kloppen.
- Ontgrendelen: `backend/services/vriendenvoordeel.py` telt betalende vrienden op Pro of hoger (2 min onthouden, achter referral_korting_aan). 5 vrienden = plan 'ultra' via `plan_van_gebruiker` (light.py, nooit omlaag); 3 vrienden of Ultra of eigenaar = toegang tot /api/ai-pakket (403 anders, vlag uit blijft 404). Tests: tests/test_vriendenvoordeel.py.
- NOG NIET: Ultra-functies buiten de artikelgrens (Etsy, voorrang) en de AI-onderdelen zelf (achtergrond verwijderen, dashboardscherm bulkopdracht, titels koppelen aan plaatsen). Die zijn voor jou, zie lijst hierboven.

## 20-11-2026 (middag, later): bulkscherm gebouwd (Claude)
- Dashboard: knop "AI assistant" + scherm `#view-ai` in frontend/app.html (voorbeeld, bevestigen met extra vinkje bij prijs onder 1 euro of dubbel, ongedaan maken). De knop verschijnt alleen als /api/ai-pakket/status 200 geeft, dus onzichtbaar tot AI_PAKKET_AAN aan staat en de klant 3 vrienden of Ultra heeft. Vertaald. Niet gezien met een echte inlog, alleen syntax en tests.
- Bewust NIET gebouwd: titels slim inkorten in het plaatsen (`_mp_titel_binnen_grens`): dat zou een modelaanroep midden in de live uitgifte zetten, en eerdere meting liet zien dat "controle goed" niet gelijk is aan "goede titel". Achtergrond verwijderen: nog geen gemeten model. Beide eerst meten op echte artikelen (95 op 100) voor ze live gaan.

## 20-11-2026 (middag): achtergrond verwijderen gemeten, NIET goed genoeg (Claude)
- Gemeten met rembg (model u2net, lokaal, gratis) op 18 willekeurige eerste foto's van Daniels eigen artikelen (dkresellacademy, staat nu op Ultra). Donkere en gekleurde kleding: schoon. Witte en lichte kleding (gestreepte trui, wit overhemd, witte kabeltrui): de donkere ruimte tussen arm en lijf blijft staan als grijze vlek, plus een donker randje. Dat is 3 van 18 duidelijk fout (circa 83% goed), dus onder de norm van 95 op 100. Een mask-verkleining (5 px) lost de vlekken niet op.
- Niet live zetten. Volgende stap voor wie dit oppakt: een sterker model proberen (bijvoorbeeld birefnet in rembg, of een betaalde dienst) op dezelfde 18 plus lichte kleding, zelfde meting. Scripts stonden in de scratchpad van deze sessie; opnieuw maken is 20 regels.

## 20-11-2026 (avond): 2dehands herplaatsen als proef (Claude)
- Daniel: automatisch herplaatsen op 2dehands, eerst alleen voor Voordeelsieraden (09e089ec). `RELIST_2DEHANDS_PROEF` in backend/services/crosslist.py; de herplaatsronde draait nu per platform (`_relist_ronde`), 2dehands alleen voor de proefverkopers. Verlengen is voor hen vangnet (relist_dagen + 3). Tests: tests/test_herplaatsen_2dehands_proef.py. De rem voor betalende rubrieken in api/jobs.py geldt al voor beide kanalen.
- Open: kijk na de eerste ronde (morgen 16:00 NL) of haar 2dehands-herplaatsingen slagen (jobs delete+create op platform 2dehands) en of er kosten of een betaalpagina opduiken. Pas daarna uitbreiden naar anderen.

## 20-11-2026 (later): achtergrond verwijderen met birefnet-general-lite (Claude)
- Dezelfde 18 foto's, model birefnet-general-lite via rembg. Witte kleding is nu schoon (de grijze vlekken tussen arm en lijf zijn weg). Overgebleven fouten: op de roze kabeltrui bleven bloemen uit de achtergrond zweven (1 van 18), en bij wit overhemd en gestreepte trui zit een dun donker randje. Circa 17 van 18 goed (94%), een kleine steekproef, net onder de norm van 95 en te klein om op te vertrouwen.
- Snelheid is het echte probleem: de 18 foto's kostten ruim 30 minuten rekentijd op de Mac (zonder videokaart). Op Railway is dat niet te draaien. Live kan alleen via een externe dienst of een eigen server met GPU; dat kost geld per foto, dus een besluit van Daniel. Eerst meten met minstens 100 foto's, ook donkere en rommelige achtergronden, voor je iets bouwt.

## 20-11-2026 (avond): proef achtergrond verwijderen in de browser (Claude)
- Proefpagina `frontend/ai-achtergrond-proef.html` (niet gelinkt, noindex): BiRefNet lite via transformers.js 3.8.1, model onnx-community/BiRefNet_lite-ONNX (licentie MIT op de modelkaart, fp16 115 MB, fp32 230 MB), alles in de browser, niets geupload. Kies foto's, zie origineel en resultaat op wit met tijd per foto. `?cpu=1` forceert de trage CPU-route.
- Resultaat in de ingebouwde browser van Claude: WebGPU-route gaf een fout (getal 146972536, waarschijnlijk geheugen of ondersteuning van die browser); CPU-route laadde 230 MB en blokkeerde de pagina (inferentie op de hoofdthread). Dus nog NIET bewezen dat het werkt. Volgende stap: proberen in echte Chrome op Daniels Mac (WebGPU), en de inferentie in een Web Worker zetten zodat de pagina niet bevriest. Pas bouwen in het dashboard als snelheid per foto en kwaliteit op echte Chrome kloppen.

## 20-11-2026 (avond, uitkomst): browserproef achtergrond verwijderen mislukt (Claude, met Daniels eigen Chrome)
- De standaard BiRefNet-lite-export geeft op WebGPU een fout (146972536). De aangepaste WebGPU-export (jiabins0303/birefnet-lite-1024-webgpu, fp16) draait wel, maar geeft rommel: foto 1 helemaal wit (kledingstuk weg), foto 2 vol ruis en gaten; 18 tot 26 seconden per foto. Dus onbruikbaar zoals het nu is, op een gewone Mac met echte Chrome.
- Niet verder in de browser zonder reden: een 512-versie in fp32 of een ander model kan werken, maar elke proef kost uren en de snelheid blijft traag voor klanten met honderden foto's. Gratis lokaal draaien (rembg op de Mac) werkt wel goed maar niet voor klanten.
- Goedkoopste werkende route is een betaalde dienst per foto (fal.ai BiRefNet, ruwe schatting 1 tot 3 euro per 1.000 foto's, nog niet gemeten), alleen op verzoek en met maandplafond. Dat is een besluit van Daniel. De testpagina `frontend/ai-achtergrond-proef.html` mag weg of blijven staan (niet gelinkt).

## 20-11-2026 (avond, onderzoek): hoe anderen achtergrond verwijderen (Claude)
- Aanbieders draaien BiRefNet-achtige modellen op een GPU (Replicate circa 0,05 cent per foto op een T4, fal.ai betaalt per rekenseconde; Photoroom 2 cent, Bria 1,8 cent als verkoopprijs). Op een gewone processor is hetzelfde model 10 tot 100 keer trager, dat is de hele reden dat het "lastig" lijkt. Browserdiensten (Backgroundless: 1 tot 3 s per foto met WebGPU) gebruiken een klein model (RMBG-1.4); de gewichten daarvan zijn niet-commercieel zonder Bria-licentie, dus niet zomaar over te nemen.
- Gemeten 20-11 op dezelfde 18 foto's: ISNet (rembg-standaard) circa 5 s per foto op de Mac en laat net als u2net grijze vlekken staan bij witte kleding, dus slechter dan BiRefNet lite. BiRefNet lite blijft het beste (17 van 18) maar vraagt een GPU.
- Advies: alleen op verzoek, via een GPU-dienst per foto (circa 0,05 tot 0,2 cent), met maandplafond. Nog niet gemeten met echte rekening.

## 20-11-2026 (nacht): Modal-proef voor achtergrond verwijderen (Claude)
- `scripts/modal_achtergrond.py`: BiRefNet lite op een T4 bij Modal, max 2 containers, stopt na 30 s stilte. De image bouwt (90 s). Draaien faalt met "Please add a payment method to use T4 GPU functions": Modal wil een betaalmethode voor GPU, ook voor het gratis tegoed van $30 per maand. Daniel moet dat zelf toevoegen en tegelijk een uitgavenlimiet zetten. Het Modal-token staat alleen in ~/.modal.toml (profiel danieldk04), niet in git.
- Nog te doen na de betaalmethode: `modal run scripts/modal_achtergrond.py --urls <lijst>` en kijken naar kwaliteit, tijd en tegoed. Pin ook de revisie van ZhengPeng7/BiRefNet_lite (trust_remote_code haalt code op van Hugging Face) voor het live gaat. Daarna pas dag- en maandplafond in onze code en aansluiten achter de AI-vlag.
