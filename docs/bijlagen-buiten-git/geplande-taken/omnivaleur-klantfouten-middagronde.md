---
name: omnivaleur-klantfouten-middagronde
description: Dagelijks 14:00: fouten en vastlopers van alle klanten opsporen, aantoonbaar repareren, zonder dubbel werk met Daniels ochtendronde.
---

Je werkt voor Omnivaleur, map /Users/Danie/Documents/omnivaleur. Volg CLAUDE.md van die repo en van ~/. Antwoord Nederlands, gewone taal, de vier blokjes (wat er aan de hand was, wat er nu veranderd is, zekerheid in %, actiepunten met [NU/DEZE WEEK/OOIT/OVERSLAAN, tijd]). Kort. Nooit een gedachtestreepje of los streepje als leesteken. Geen subagents, batch je opdrachten, lees gericht. Python is altijd /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 (hieronder P).

DIT IS DE MIDDAGRONDE. Daniel heeft een eigen ochtendronde (rond 08:00) en er is een automatische wachter die losse sessies start op nieuwe fouten. Jouw ronde vult die aan, en mag NOOIT een probleem oplossen dat al is of wordt opgelost.

DOEL: uitzoeken waar klanten de afgelopen 24 uur echt tegenaan liepen (harde fouten, vastlopers, betaalslot, stilstaande reeksen), dat aantoonbaar REPAREREN, en zorgen dat het niet terugkomt.

STAP 0, het slot en dubbel werk voorkomen. Voer dit uit voor al het andere:
  cd /Users/Danie/Documents/omnivaleur && P scripts/klantfouten.py ronde begin middagronde
- Exit 3: een andere ronde is bezig. STOP meteen. Rapporteer in twee zinnen wie en sinds wanneer, verder niets. Niets repareren, niets committen, geen ronde klaar.
- Exit 0: het script print wat de vorige ronde deed. Lees dat. Vanaf nu MOET je aan het eind altijd `P scripts/klantfouten.py ronde klaar middagronde "samenvatting in één zin"` draaien, ook als je halverwege stopt of vastloopt (dan "afgebroken: reden").
- `git fetch -q origin main`, dan `git log origin/main --since="36 hours ago" --name-only`, en de onderkant van docs/team-notes.md: alle kopjes "Dagelijkse klantfouten" en "Klantfouten (automatisch)" van vandaag en gisteren.
- `P scripts/klantfouten.py`: alleen soorten met [OPEN] zijn van jou. [afgehandeld] laat je met rust.
- Regel tegen dubbel repareren: staat een probleem (zelfde klant, zelfde oorzaak) in de notities of commits als gerepareerd, repareer het dan NIET opnieuw. Meet alleen of het echt weg is. Is het nog aanwezig, dan is die reparatie mislukt of nog niet live: zoek waarom en bouw voort op díe reparatie, maak geen tweede parallelle oplossing. Staat het als klant of onbekend beoordeeld en is er sindsdien niets nieuws gebeurd, doe het onderzoek dan niet over.
- Voordat je een bestand wijzigt: `git log -3 --format="%h %ar %s" -- <bestand>` en `git diff origin/main -- <bestand>`. Is het in de laatste uren door een ander aangepast, lees die wijziging eerst.

STAP 1, meten met echte data, nooit schatten. P met sys.path.insert(0, repo), `import mail_analyse as A; A._omgeving_uit_env_bestand()` (scripts in sys.path) en `from backend.database import get_db`. De productiedatabase is twee keer omgevallen op een zware meting: lees `jobs.result` (ook één veld eruit) ALLEEN per user_id, nooit over meerdere klanten; pagineer in brokken van 200 met .order(); pauzes ertussen; na afloop /health nakijken. Bekijk over 24 uur:
- jobs per platform/action/status, fouten per klant met result->>error, opdrachten te lang op claimed of pending, en per klant de pending-telling per actie (veel wachtend werk terwijl de klant online is en ander werk wel doorloopt = een rem, zoals de 2dehands-noodrem van 27-09).
- subscriptions (evaluate_access uit backend.services.billing) en extension_heartbeat (last_seen, ext_version): betaalslot, verlopen proef, extensie stil terwijl er werk wacht, oude extensieversie.
- https://omnivaleur.com/health.
Onderscheid (a) fout in ONZE code of een kanaal dat de pagina veranderde, en (b) klant-eigen oorzaak (computer uit, uitgelogd, advertentie al weg, betaalmuur, maat die niet in de lijst past). Alleen (a) repareer je. Wantrouw lege uitkomsten: nul betekent eerst controleren of de meting zelf werkte (RLS, sleutel, filter).
Controleer een advertentie op het kanaal zelf via de openbare pagina (https://www.2dehands.be/m{nummer} of https://www.marktplaats.nl/m{nummer}; /v/a/ geeft altijd 404), rustig aan (Marktplaats blokkeert na ongeveer 60 snelle verzoeken).

STAP 2, repareren: alleen met zekerheid. Een reparatie meld je pas als gerepareerd als ALLE punten waar zijn:
1. Oorzaak bewezen: je kunt het mechanisme aanwijzen met echte gegevens, niet "zou kunnen".
2. Echte code gerepareerd met een proef in tests/, en een voor-en-na-proef: de oude code, geladen van een VAST commitnummer (nooit HEAD, want na de commit vergelijkt die zich met zichzelf), faalt onder dezelfde omstandigheden en de nieuwe slaagt.
3. De hele testreeks groen: `P -m pytest -q tests`.
4. Live: `git pull --rebase --autostash origin main`, commit, push naar main (Railway deployt; let op, een auto-push-hook commit soms al vanzelf). Wacht tot https://omnivaleur.com/health bij "commit" jouw commit (of een latere) toont.
5. Effect gemeten bij de echte klant na de uitrol: de rij loopt weer, de opdracht slaagt, het zoekertje toont het goede bedrag. Kun je dit niet meten, dan is het oordeel "onbekend" en schrijf je het met zoveel woorden op als open punt. Nooit "gerepareerd" zonder deze meting.
Twijfel je aan de oorzaak: niet repareren, open punt. Extensiewijziging: manifest bumpen en scripts/build-extension.sh volgens de kennisbank; uploaden naar de Chrome Web Store kan alleen Daniel, dat wordt een actiepunt. Klanttekst gewijzigd: `P scripts/i18n_extract.py`, vertaling in frontend/i18n/nl.json, `P scripts/i18n_extract.py --versie`. Lees docs/kennisbank.md voor je iets aanpakt dat je niet kent.
Klantdata: nooit verwijderen, nooit een wachtrij wissen of annuleren, nooit klanten mailen, nooit .env of geheimen committen. Eén opdracht rechtzetten mag alleen met bewijs (bijvoorbeeld een valse mislukking waarvan de openbare pagina laat zien dat het gelukt is) en je noemt het in de notitie. Een nieuwe opdracht klaarzetten opent de 2dehands-noodrem niet; alleen de laatst afgelopen opdracht rechtzetten doet dat.

STAP 3, vastleggen:
- Onderaan docs/team-notes.md een kort kopje "## DD-MM-JJJJ (middag): Dagelijkse klantfouten": fouten en aantal klanten, wat gerepareerd is (commit), wat van de vorige ronde nog aanwezig of opgelost is, wat open blijft. Committen en pushen (eerst git pull --rebase --autostash).
- Meld ELKE soort die `P scripts/klantfouten.py` als OPEN toont terug: `P scripts/klantfouten.py oordeel <soort> gerepareerd|klant|onbekend "zin"`. "gerepareerd" alleen als stap 2 punt 5 gemeten is.
- Nieuwe les: memorybestand in ~/.claude/projects/-Users-Danie-Documents-omnivaleur/memory/ plus regel in MEMORY.md, `python3 scripts/export_kennisbank.py`, committen.
- Als laatste: `P scripts/klantfouten.py ronde klaar middagronde "samenvatting in één zin, met commitnummers"`.

STAP 4, rapport in de vier blokjes. Rustig en niets gevonden: zeg dat in twee zinnen. Noem eerlijk wat je niet kon meten (fouten die alleen in de browser van de klant staan en nooit bij de server aankomen).