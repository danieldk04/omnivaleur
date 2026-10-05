# Routine: dagelijkse klantfouten

De vaste opdracht voor de klantfoutenronde. Daniels Mac draait hem om 08:00 (rondenaam
`ochtendronde`), het account van de tweede ontwikkelaar om 14:00 (rondenaam
`middagronde`, geplande taak `omnivaleur-klantfouten-middagronde`). De geplande taken
zeggen alleen "volg dit bestand". Wijzig je de routine, wijzig dan dit bestand en push.
Je hebt de Supabase-service-sleutel nodig in je lokale .env (zie kennisbank:
"railway-blokkeert-smtp" en "leadgen-status-leest-anon-sleutel").

Je werkt voor Daniel aan Omnivaleur, in jouw eigen kopie van de repo. Volg CLAUDE.md van die repo en van ~/. Antwoord Nederlands, gewone taal, de vier blokjes (wat er aan de hand was, wat er nu veranderd is, zekerheid in %, actiepunten met [NU/DEZE WEEK/OOIT/OVERSLAAN, tijd]). Kort. Geen gedachtestreepjes.

DOEL: uitzoeken waar klanten de afgelopen 24 uur echt tegenaan liepen (harde fouten, vastlopers), dat REPAREREN, en zorgen dat een probleem van gisteren vandaag niet weer voorkomt.

STAP 0, één ronde tegelijk (er draaien twee rondes per dag op twee accounts). Eerst: `python3 scripts/klantfouten.py ronde begin <rondenaam>`. Exit 3 = een andere ronde is bezig: stop meteen en meld in twee zinnen wie en sinds wanneer. Exit 0 = het script print wat de vorige ronde deed; wat daar als gerepareerd staat repareer je niet opnieuw, je meet alleen of het weg is. Aan het eind ALTIJD, ook bij afbreken: `python3 scripts/klantfouten.py ronde klaar <rondenaam> "samenvatting in één zin met commitnummers"`.

STAP 1, begin zoals CLAUDE.md voorschrijft: git log van de laatste 30 uur en de onderkant van docs/team-notes.md. Zoek daar het laatste kopje "Dagelijkse klantfouten" of "Klantfouten (automatisch)" (vorige run of automatische sessie) en lees welke problemen toen gemeld waren. Draai ook `python3 scripts/klantfouten.py`: dat is de lijst foutsoorten van de automatische wachter, met welke al afgehandeld zijn.

STAP 2, meten (echte data, nooit schatten). Gebruik een python3 waarin supabase geïnstalleerd is met sys.path.insert(0, repo) en `from backend.database import get_db`. Lees in brokken, nooit één zware telling (zie kennisbank: meten op de productiedatabase). Bekijk over de laatste 24 uur:
- jobs: telling per platform/action/status, en de result->error teksten van status 'error', gegroepeerd per foutsoort én per klant (user_id). Ook jobs die te lang op 'claimed' of 'pending' hangen. Noem 'cancelled' alleen als het opvalt.
- extension_heartbeat en subscriptions: klanten met betaalslot (402), verlopen proef, of extensie die stil staat terwijl er werk wacht.
- Railway-serverlogs of /health als die bereikbaar zijn, en het foutenlogboek/mailalarm als dat bestaat.
Onderscheid: (a) fout in ONZE code of een kanaal dat de pagina veranderde, (b) klant-eigen oorzaak (computer uit, uitgelogd, advertentie al weg, betaalmuur). Alleen (a) repareer je. Wantrouw lege uitkomsten: controleer dat de meting zelf werkte (bijv. dat de telling niet 0 is door een RLS- of sleutelprobleem).

STAP 3, vergelijk met de vorige run. Per probleem van gisteren: is het nog aanwezig? Zo ja is de reparatie mislukt of niet uitgerold, meld dat expliciet en zoek de reden. Een probleem dat gisteren gemeld en vandaag weg is: noem het als 'opgelost'.

STAP 4, repareren. Voor elke fout in categorie (a) met een aantoonbare oorzaak: bewijs het mechanisme, repareer met de echte code, draai de bestaande tests, doe de voor-en-na-proef (oude code laten falen), commit en push naar main (deploy gaat via Railway; nooit .env of geheimen committen, geen HEAD-vergelijking in proeven). Bij een extensiewijziging: manifest bumpen en build-extension.sh volgens de kennisbank. Twijfel je of iets echt de oorzaak is, repareer dan niet, zet het als open punt. Raak nooit klantdata destructief aan (geen verwijderen, geen wachtrijen wissen) zonder toestemming van Daniel. Lees docs/kennisbank.md voor je iets aanpakt wat je niet kent.

STAP 5, vastleggen. Voeg onderaan docs/team-notes.md een kort kopje toe "## DD-MM-JJJJ: Dagelijkse klantfouten" met: welke fouten en hoeveel klanten, wat gerepareerd is (commit), wat open blijft. Committen en pushen. Leerde je iets nieuws: memorybestand plus `python3 scripts/export_kennisbank.py`, committen. Meld ELKE foutsoort die `python3 scripts/klantfouten.py` als OPEN toont terug met `python3 scripts/klantfouten.py oordeel <soort> gerepareerd|klant|onbekend "zin"`, anders begint de automatische wachter er straks opnieuw aan.

STAP 6, rapport aan Daniel in de vier blokjes. Verandert er niets en is alles rustig, zeg dat in twee zinnen. Geen extra controlerondes, geen subagents, batch je opdrachten, lees gericht.

Zichtbare grenzen: meld eerlijk wat je niet kon meten (bijv. fouten die alleen in de browser van de klant staan en nergens naar de server gaan).
