#!/bin/zsh
# Geeft GitHub elk half uur een seintje om een ronde van de koude-mailmachine te
# draaien (workflow leadgen-mail.yml). Waarom: GitHub start geplande rondes maar
# 2 a 3 keer per dag, terwijl het dagbudget 30 tot 44 mails is en een ronde er
# hooguit 12 verstuurt. Staat de Mac uit, dan draait GitHub's eigen planning
# gewoon door. Geen dubbele mail mogelijk: alleen een seintje als er geen ronde
# loopt of wacht, en de machine zelf bepaalt per dagrooster wat er uitgaat.
# Gebouwd 28-09-2026, zie docs/team-notes.md.
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
LOG="$HOME/Library/Application Support/omnivaleur/leadmachine_seintje.log"
REPO=danieldk04/omnivaleur
nu=$((10#$(date +%H%M)))
if [ $nu -lt 800 ] || [ $nu -gt 2130 ]; then exit 0; fi
bezig=$(gh run list -R $REPO --workflow=leadgen-mail.yml --limit 5 --json status --jq '[.[] | select(.status != "completed")] | length' 2>>"$LOG")
if [ "$bezig" = "0" ]; then
  if gh workflow run leadgen-mail.yml -R $REPO -f opdracht=tick 2>>"$LOG"; then
    echo "$(date '+%d-%m %H:%M') seintje gegeven" >> "$LOG"
  else
    echo "$(date '+%d-%m %H:%M') seintje MISLUKT" >> "$LOG"
  fi
else
  echo "$(date '+%d-%m %H:%M') ronde loopt al (${bezig:-onbekend}), geen seintje" >> "$LOG"
fi
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
