---
name: omnivaleur-fotometing-uitkomst
description: Eenmalig: de uitkomst van de gratis fotometing (foto naar advertentie) lezen en aan Daniel melden
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Antwoord in het Nederlands, in vier korte blokjes (wat er aan de hand was, zekerheid in procenten, actiepunten met label [NU/DEZE WEEK/OOIT/OVERSLAAN] en tijd), geen gedachtestreepjes als leesteken, geen opmaaktekens in mail.

Opdracht: lees ~/.omnivaleur/meting_foto/samenvatting.txt (staat die er niet, draai dan `python3.13 scripts/meet_fotoadvertentie.py samenvatting` in de repo) en ~/.omnivaleur/meting_foto/resultaten.jsonl. Controleer eerst of de meting af is (110 artikelen) en of de LaunchAgent com.omnivaleur.fotometing zichzelf heeft weggehaald (`launchctl list | grep fotometing`). Is hij niet klaar, zeg dan hoeveel er zijn en laat hem doorlopen (niets forceren, daglimiet gratis laag is 20 per dag voor het sterke model).

Beoordeel eerlijk: per veld (kleur, merk, maat, merk verzonnen, maat verzonnen) en per model (gemini-3.5-flash en gemini-3.1-flash-lite) hoeveel goed is. Bekijk ook 10 voorbeelden naast elkaar in resultaten.jsonl en zeg of het model echt bruikbaar invult. Besluit: is foto naar advertentie goed genoeg om aan klanten te beloven als onderdeel van het AI-pakket (3 betalende vrienden)? Regel van Daniel: alleen beloven wat 100% zeker werkt, nooit half uitrollen. Is het onvoldoende, zeg dat dan met zoveel woorden en noem de goedkoopste volgende stap. Schrijf de uitkomst als korte entry onder in docs/team-notes.md, push dat, en zet de Omnivaleur-te-bouwen sheet bij met scripts/te_bouwen.py als daar iets over staat. Doe niets aan de uitnodigactie-vlag (REFERRAL_KORTING_AAN) of aan klanten.