---
name: omnivaleur-btw-oss-kwartaal
description: Bereidt elk kwartaal de gewone btw-aangifte en de OSS-melding van Daniel voor en zet ze klaar tot vlak voor verzenden.
---

Je werkt aan Omnivaleur/Revaleur in /Users/danieldekoning/Projects/omnivaleur. Lees eerst docs/routines/oss-aangifte.md en de skill btw-omzetbelasting, en de laatste onderaan docs/team-notes.md. Het is het begin van een nieuw kwartaal; bereid de aangiftes over het zojuist afgelopen kwartaal voor (jan = Q4 vorig jaar, apr = Q1, jul = Q2, okt = Q3). Deadlines: de laatste dag van die maand voor zowel de gewone btw-aangifte als de OSS-melding.

Doe dit:
1. Download de P&L van de Drive-sheet Profitsheet Right (fileId 13tHt7SWYqYdPKwyZaj5kkAcZt3G_IJCzksZYSL-zxgI) als CSV (download_file_content, text/csv) en filter op Date Sold in het kwartaal.
2. Controle van de sheet: (a) elke buitenlandse verkoop moet in verborgen kolom AC (Binnenland verkocht?) 'Nee' hebben; meld lege cellen. (b) Elk reguliere item buiten NL moet een OSS-bedrag hebben. (c) Meld items waar Price Sold is ingevuld maar Date Sold leeg is, BEHALVE de door Daniel als oud bevestigde nummers 66, 67, 70, 73, 86, 105, 203, 213, 226, 277, 582, 727, 793, 814, 1270, 1298, 1299, 1300, 1314, 1316 (die nooit melden).
3. Bereken OSS per land (tarief van het land van de koper: BE 21, FR 20, ES 21, IT 22, DE 19, PT 23, anders opzoeken) uit alleen reguliere verkopen aan consumenten in andere EU-landen, vanaf 1 juli 2026. Bereken de gewone aangifte: marge-items via globalisatie (alle margeverkopen, ook die naar het buitenland), reguliere NL-verkopen over de volle prijs 21/121, geen enkele OSS-verkoop in 1a. Voorbelasting en verlegde btw uit de Gekko-export van Daniel (vraag hem erom als die ontbreekt). Controleer dat elke verkoop in precies een van de twee aangiftes staat.
4. Neem de kleine correctie van de vorige kwartalen mee die nog openstaat (zie team-notes: Q3 2026 vermoedelijk 5 tot 13 euro te veel btw in 1a, te verwerken in de Q4-aangifte, onder de 1.000 euro hoeft geen suppletie). Lees in Mijn Belastingdienst Zakelijk de laatst ingediende aangifte om de ingediende bedragen te vergelijken met de sheet en meld afwijkingen.
5. Open via Claude in Chrome (select_browser: het profiel waar Daniel is ingelogd bij Belastingdienst; probeer beide verbonden browsers) mijnzakelijk.belastingdienst.nl en vul de OSS-melding in (Btw > E-commerce > Btw-meldingen; het veld Btw-bedrag is het btw-bedrag, niet de omzet) en bereid de gewone aangifte voor. STOP voor de verklaring en het verzenden: klik die nooit zelf, betaal nooit, en zet geen bankgegevens of deelnemersnummers in de repo of in git.
6. Schrijf het resultaat kort in docs/team-notes.md (bedragen, afwijkingen, wat Daniel nog moet doen) en push. Werk docs/routines/oss-aangifte.md bij als je iets nieuws leert.
7. Zet de actiepunten voor Daniel in zijn Google Tasks via de skill omnivaleur-taken (verzenden, betalen met de gegevens uit het OSS-overzicht, boekhouder).

Antwoord aan Daniel in vier blokjes (wat er aan de hand was, wat er veranderd is, zekerheid in procenten, actiepunten met [NU/DEZE WEEK/OOIT/OVERSLAAN] en tijd), kort, en zonder het woord sorry.