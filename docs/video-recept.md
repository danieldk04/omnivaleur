# Recept: Omnivaleur-video's in de stijl van renno.app

Gebouwd op 10-11-2026 (versie 1 tot 3). Code staat in `scripts/video/`. Werkmap per video: kopie daarvan.

## Opzet
- Basis: `~/claude-animation-skills/` (kit met stem, woordtiming, node_modules met three en playwright, .venv met python 3.13).
  Herstel: `gh repo clone artemnovitckii/claude-animation-skills ~/claude-animation-skills`, daarna `install.sh --voice`.
  Op deze Mac faalde python 3.14 bij `ensurepip`: maak de venv met `/usr/local/bin/python3.13`.
- Aanvullende skills (geklooid naar de thuismap): `~/huashu-art-motion`, `~/huashu-motion`, `~/earshot`.
- Stappen: `script.json` (voice-overregels) → Kokoro stem (`am_michael`, snelheid 1.05) → `words.py` (Parakeet, woordtiming)
  → `captions.py` print CAPTIONS en DURATION → shots in `src/shots.js` getimed op de voice-over → `node render.mjs video silent.mp4 30`
  (720x1280, ongeveer 0,55 s per frame, 18 s kost 5 minuten, in de achtergrond draaien) → `sound.py` (muziek en geluidjes) → ffmpeg mixen
  (amix, loudnorm I=-14, schalen naar 1080x1920).
- Poppetje: `src/blocky.js`. Armen worden met `solveArms` op de toetsen gezet, zodat handen precies op het toetsenbord zitten.

## Wat Daniel afkeurde en hoe het is opgelost
- Te statisch (alleen een laptop): 17 snelle shots in uiteenlopende omgevingen met whip-overgangen.
- Poppetje door de laptop: deksel aan de verkeerde kant, stoel te ver weg, handhoeken fout. Gemeten met `clip.mjs` (kogel tegen kist, drempel 0,3):
  388 doorsteken naar 0. Draai `clip.mjs` na elke wijziging.
- Oude dashboardbeelden met "6 dagen proef" en "Coming soon": vers vastleggen uit het ingelogde dashboard.
- Geluidjes te luid en piepend: zachte druppel en zoef, bed eerst normaliseren, geluidjes erna op piek 0,16.

## Valkuilen
- Eén hulp uit het skill kan stil falen: controleer dat `silent.mp4` echt de verwachte lengte heeft.
- Een patch in een python-script dat stilvalt laat het oude bestand staan: draai na elke patch de test opnieuw.
- Geluid is nooit beluisterd door mij: gebruik earshot om te meten (luidheid, verstaanbaarheid), niet "klinkt goed".
