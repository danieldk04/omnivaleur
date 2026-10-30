---
name: interview-daniel
description: Daniel interviewen over het beoogde eindresultaat, alleen als dat echt nodig is. Activeer wanneer een opdracht twee of meer wezenlijk verschillende uitkomsten kan hebben en het antwoord niet in de code, docs/team-notes.md, docs/kennisbank.md, de te-bouwen-sheet of de data te vinden is. Niet activeren voor vragen waar een verstandige standaard bestaat.
---

# Daniel interviewen (sinds 30-10-2026)

Doel: jij begrijpt het eindresultaat 1000%, zonder dat Daniel tijd verspilt aan vragen waar jij het antwoord zelf kunt vinden of kiezen.

Daniel, 30-10-2026: "vermijd vragen om het vragen, het gaat om het eindresultaat, je hoeft niet te vragen als je geen vragen hebt."

## Eerst zelf zoeken, dan pas vragen

1. Zoek het antwoord zelf: de repo, `docs/team-notes.md`, `docs/kennisbank.md`, de Google Sheet "Omnivaleur te bouwen", de productiedata (alleen lezen, per klant), eerdere berichten in dit gesprek.
2. Is er een verstandige standaard? Kies hem, noem hem in je rapport in één zin, en ga door.
3. Vraag alleen als een verkeerde gok duur is: moeilijk terug te draaien, zichtbaar voor klanten, of het kost geld of vertrouwen.

## Hoe je vraagt

- Eén keer, hooguit drie vragen tegelijk, met `AskUserQuestion`. Jouw aanbeveling staat bovenaan met "(Recommended)".
- Over het eindresultaat, in gewone taal: "Wat moet een klant zien als het klaar is?", "Wat is een geslaagde uitkomst?", "Wat mag nooit meer gebeuren?". Nooit over techniek: Daniel is geen programmeur.
- Geen open vraag als een keuze volstaat. Geen vraag waarvan het antwoord je werk niet verandert.
- Daarna, in één zin, het eindresultaat zoals jij het nu begrijpt. Klopt het niet, dan corrigeert hij.

## Daarna

- Bouw het, en test het zelf tot het aantoonbaar werkt (zie "Zekerheid boven aannemelijkheid" in CLAUDE.md).
- Is een antwoord blijvend (een beslissing, een regel, een voorkeur), zet het dan als dagboekregel in `docs/team-notes.md` en, als het een les is, in de kennisbank (`python3 scripts/export_kennisbank.py`).
- Escaleer in je actiepunten alleen wat alleen Daniel kan doen.
