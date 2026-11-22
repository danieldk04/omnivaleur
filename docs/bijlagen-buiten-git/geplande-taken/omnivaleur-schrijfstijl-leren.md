---
name: omnivaleur-schrijfstijl-leren
description: Leest dagelijks wat Daniel zelf verstuurde, vergelijkt met Claudes concepten en scherpt docs/schrijfstijl-daniel.md aan.
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Doel: Daniels schrijfstijl in klantmails steeds beter leren, zodat conceptantwoorden van Claude zonder aanpassing verstuurd kunnen worden. Antwoord aan Daniel in het Nederlands, kort, zonder gedachtestreepjes.

Stappen:
1. Lees docs/schrijfstijl-daniel.md.
2. Draai: python3 scripts/schrijfstijl_leren.py ophalen --dagen 3
   Faalt dit, meld dan de fout als storing en stop. Draai in dat geval NIET 'klaar'. Een fout is nooit "geen nieuwe mails".
   Het script print eerst een regel "Gekeken: X mails in Verzonden, Y van Daniel, Z daarvan al verwerkt." Neem die cijfers letterlijk over in je logregel en in je rapport. Is Y gelijk aan 0 terwijl X groot is (meer dan 20), of is X zelf 0, dan klopt de koppeling waarschijnlijk niet: meld dat als storing met [NU] en schrijf geen "niets te leren".
3. Lees data/schrijfstijl/nieuw.json. Zijn er 0 mails, schrijf dan alleen een logregel (stap 6) met de cijfers uit stap 2 en stop.
4. Elke mail heeft 'verstuurd' (wat Daniel echt stuurde) en soms 'concept' (wat Claude voorstelde). 
   - Mét concept: vergelijk ze. Wat schrapte Daniel, wat voegde hij toe, wat herschreef hij, wat veranderde in aanhef, afsluiting, lengte, toon, woordkeus? Dit is het belangrijkste leersignaal.
   - Zonder concept: leer alleen algemene patronen (aanhef, afsluiting, lengte, toon, vaste zinnen). Let op: veel van Daniels antwoorden zijn eerder door Claude voorgesteld en daarna licht aangepast, dus behandel zulke tekst niet als zuivere Daniel zonder te kijken wat er bij concepten verandert.
5. Werk docs/schrijfstijl-daniel.md bij: voeg samen in plaats van achteraan plakken, houd het onder circa 120 regels, zet regels vooraan die vaak terugkomen, schrap wat tegengesproken wordt. Een patroon pas als regel opnemen als het minstens twee keer opduikt, anders onder 'Nog te leren'. Nooit namen, adressen of klantgegevens in het bestand, alleen patronen en geanonimiseerde voorbeelden.
6. Voeg onder 'Logboek van de routine' één regel toe: datum, de cijfers uit stap 2, aantal met concept, wat er nieuw was (max. 1 zin).
7. Draai: python3 scripts/schrijfstijl_leren.py klaar
8. Commit alleen docs/schrijfstijl-daniel.md en push naar main. Neem geen andere bestanden mee.
9. Rapporteer in de vier blokjes van CLAUDE.md, maar zeer kort: wat er geleerd is, zekerheid, actiepunten (meestal 'Niets, klaar.').

Regels: data/schrijfstijl/ bevat klantmails en blijft buiten git. Lees nooit .env uit en print nooit wachtwoorden. Geen subagents.