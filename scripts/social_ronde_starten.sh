#!/bin/bash
# Start de reageerronde zonder dat Claude Desktop open staat (LaunchAgent, elk uur).
# Poort: 09:00-22:00, minstens 4 uur na de vorige ronde, hooguit 3 per dag.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
R="$HOME/Documents/omnivaleur"; D="$R/data/social"; cd "$R" || exit 1
H=$(date +%H); NU=$(date +%s); VAND=$(date +%Y-%m-%d)
[ "$H" -ge 9 ] && [ "$H" -lt 22 ] || exit 0
LOCK=/tmp/omnivaleur-ronde.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  [ $(( NU - $(stat -f %m "$LOCK") )) -gt 5400 ] && rmdir "$LOCK" && mkdir "$LOCK" || exit 0
fi
trap 'rmdir "$LOCK"' EXIT
if [ -f "$D/laatste-ronde.txt" ]; then
  L=$(date -j -f "%Y-%m-%d %H:%M" "$(head -1 "$D/laatste-ronde.txt")" +%s 2>/dev/null || echo 0)
  [ $(( NU - L )) -ge 14400 ] || exit 0
fi
N=$(grep -c "^$VAND.*start" "$D/rondes.log" 2>/dev/null); [ "${N:-0}" -lt 3 ] || exit 0
[ "$1" = "--droog" ] && { echo "poort open: ronde zou nu starten"; exit 0; }
date +'%Y-%m-%d %H:%M' > "$D/laatste-ronde.txt"
echo "$(date +'%Y-%m-%d %H:%M') start (LaunchAgent)" >> "$D/rondes.log"
pgrep -x "Google Chrome" >/dev/null || { open -ga "Google Chrome"; sleep 20; }
caffeinate -i claude -p --chrome --dangerously-skip-permissions \
  "Lees data/social/ronde-prompt.txt en voer de reageerronde precies zo uit. De POORT is al gepasseerd door het startscript: sla die stap over en schrijf laatste-ronde.txt niet opnieuw. VERNIEUWEN van de cron overslaan, dat doet het startscript niet nodig." \
  > /tmp/omnivaleur-ronde-uit.txt 2>&1
cat /tmp/omnivaleur-ronde-uit.txt >> "$D/ronde-uitvoer.log"
if grep -q "Failed to authenticate" /tmp/omnivaleur-ronde-uit.txt; then rm -f "$D/laatste-ronde.txt"; sed -i '' '$d' "$D/rondes.log"; echo "$(date +'%Y-%m-%d %H:%M') mislukt: niet ingelogd" >> "$D/rondes.log"; fi
echo "$(date +'%Y-%m-%d %H:%M') klaar" >> "$D/rondes.log"
