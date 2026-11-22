---
name: gemini-gratis-sleutel-check
description: Leest /health van Omnivaleur en meldt Daniel hoeveel taalvragen Gemini gratis deed en hoeveel naar het betaalde Claude gingen
---

Werkmap: /Users/Danie/Documents/omnivaleur. Volg de CLAUDE.md daar (Nederlands, gewone taal, vier blokjes met zekerheid en actiepunten met urgentielabel, nooit een gedachtestreepje als leesteken).

Achtergrond: op 24-09-2026 was het betaalde Gemini-tegoed op (HTTP 402). Daniel zette een gratis Google-sleutel in Railway (vingerafdruk ddf59aed). Daarna gaf Google vaak 503 "te druk", en dan gaat de vraag naar het betaalde Claude. Sinds commit 0784cbba doet de server bij drukte na 4 seconden nog een ronde. Sinds commit c97d9afc staat op https://omnivaleur.com/health onder config.taalmodel_sinds_start een telling sinds de laatste herstart: antwoord_door (gemini / claude / geen_antwoord) en google_codes (http_200, http_503, http_429, http_402, gered_door_tweede_ronde, geen_verbinding).

Taak:
1. curl -s https://omnivaleur.com/health en lees commit, config.google_sleutel_vingerafdruk en config.taalmodel_sinds_start.
2. Kijk met git log sinds 24-09-2026 17:10 of er gedeployd is (een deploy zet de telling op nul). Noem over welke periode de telling gaat.
3. Wantrouw een lege telling: is alles 0 of leeg, controleer dan of er simpelweg geen verkeer was (kort na een deploy) voordat je conclusies trekt.
4. Oordeel:
   - Het deel dat gemini beantwoordde van gemini + claude. Boven 70%: de gratis sleutel werkt, niets doen.
   - Veel claude en veel http_503: de gratis laag is structureel te druk. Adviseer dan een klein tegoed (bijvoorbeeld 10 euro) op het betaalde Google-project, omdat dat goedkoper is dan alles via Claude.
   - http_429 vaak: dagmaximum van de gratis laag bereikt, zelfde advies.
   - http_402: verkeerde sleutel, vingerafdruk moet ddf59aed zijn.
   - geen_antwoord boven 0: ook Claude faalde, mogelijk is het Anthropic-tegoed op. Dat is [NU].
5. Rapporteer kort aan Daniel in de vier blokjes, met de echte getallen. Verander geen code. Voeg één regel met de uitkomst toe onderaan docs/team-notes.md (datum 25-09-2026), commit en push die.