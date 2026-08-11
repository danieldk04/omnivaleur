#!/bin/zsh
# Eén autonome beurt van de koude-mailmachine, elke tien minuten gestart door de
# LaunchAgent com.omnivaleur.leadgen.
#
# LET OP: de versie die echt draait staat in
#   ~/Library/Application Support/omnivaleur/tick.sh
# en niet in de projectmap. macOS laat launchd geen programma starten dat in
# Documenten staat (privacybescherming); vandaar de kopie. Pas je hier iets aan,
# kopieer het dan ook daarheen.
#
# Wachtwoorden staan NIET in dit bestand maar in de sleutelhanger van de Mac.
set -u

cd /Users/Danie/Documents/omnivaleur || exit 1

export MAIL_HOST=smtp.zoho.eu
export IMAP_HOST=imap.zoho.eu
export MAIL_USER=daniel@omnivaleur.nl
export MAIL_PASS="$(security find-generic-password -a daniel@omnivaleur.nl -s omnivaleur-leadgen-mail -w 2>/dev/null)"
export NOTION_TOKEN="$(security find-generic-password -a notion -s omnivaleur-notion-token -w 2>/dev/null)"

LOG=~/Library/Application\ Support/omnivaleur/tick.log
# Logboek kort houden: hooguit de laatste duizend regels.
if [[ -f $LOG && $(wc -l < $LOG) -gt 1000 ]]; then
  tail -400 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi

if [[ -z "$MAIL_PASS" ]]; then
  echo "$(date '+%d-%m %H:%M') — geen wachtwoord in de sleutelhanger, niets gedaan"
  exit 1
fi

/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  scripts/leadgen_mail.py tick "$@" || echo "$(date '+%d-%m %H:%M') — tick mislukt"
