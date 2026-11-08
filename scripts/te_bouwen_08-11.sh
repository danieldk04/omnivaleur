#!/bin/bash
# Eenmalig draaien op een machine met de sheets-sleutel; verwijder dit bestand daarna.
# Voegt de drie ideeen van 08-11-2026 toe aan de sheet "Omnivaleur te bouwen".
cd "$(dirname "$0")/.." || exit 1
python3 scripts/te_bouwen.py voeg \
  "Premium features ontgrendelen via uitnodigen: trap 1/3/5/10 betalende vrienden, vergrendelde features zichtbaar in dashboard" \
  "Uitgesteld" "Hoog" "1" "Daniel" \
  "08-11-2026: korte termijn bedoeld. Alleen nieuwe features, vereist betalend Pro. Zie team-notes 08-11. Eerst terugkomen bij Daniel, niet zelf bouwen."
python3 scripts/te_bouwen.py voeg \
  "Twee deuren: Etsy en andere premium features via 3 of 5 betalende uitnodigingen OF via Ultra-plan (40-50 euro per maand)" \
  "Uitgesteld" "Hoog" "1" "Daniel" \
  "08-11-2026: werven moet meer opleveren dan Ultra verkopen (3 vrienden = ca 60 euro). Ultra ook limieten en support. Prijs 39 tegen 49 testen. Etsy-kanaal moet nog gebouwd."
python3 scripts/te_bouwen.py voeg \
  "Win-back verlopen proefaccounts: segmenteren op gedrag, versten eerst, persoonlijk bericht met vraag, alleen eigen kanalen" \
  "Overwegen" "Hoog" "1" "Daniel" \
  "08-11-2026: zo snel mogelijk, verse proef komt vaker terug. Geen Google/LinkedIn-zoekwerk op mailadressen. Eerst per segment tellen. Zie team-notes 08-11."
