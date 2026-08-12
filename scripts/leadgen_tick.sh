#!/bin/zsh
# Eén autonome beurt van de koude-mailmachine, elke tien minuten gestart door de
# LaunchAgent com.omnivaleur.leadgen.
#
# WAAROM HIER EN NIET IN DE PROJECTMAP
# macOS geeft een achtergrondtaak geen toegang tot ~/Documents ("Operation not
# permitted"), en iCloud haalt daar bovendien bestanden weg die even niet gebruikt
# zijn ("Resource deadlock avoided"). Samen legden die twee de machine op 11-08
# een halve dag stil zonder dat er iets zichtbaar misging. Daarom draait de
# machine volledig buiten Documenten:
#   code      ~/Library/Application Support/omnivaleur/code/
#   gegevens  ~/Library/Application Support/omnivaleur/leads/
#   wrapper   ~/Library/Application Support/omnivaleur/tick.sh   (dit bestand)
#
# De projectmap blijft de bron. Na elke wijziging aan leadgen_mail.py of
# leadgen_notion.py moet je de kopie bijwerken:
#   scripts/leadgen_deploy.sh
#
# Wachtwoorden staan in de sleutelhanger van de Mac, niet in dit bestand.
set -u

CODE=~/Library/Application\ Support/omnivaleur/code
LOG=~/Library/Application\ Support/omnivaleur/tick.log

cd $CODE || exit 1

export MAIL_HOST=smtp.zoho.eu
export IMAP_HOST=imap.zoho.eu
export MAIL_USER=daniel@omnivaleur.nl
export MAIL_PASS="$(security find-generic-password -a daniel@omnivaleur.nl -s omnivaleur-leadgen-mail -w 2>/dev/null)"
export NOTION_TOKEN="$(security find-generic-password -a notion -s omnivaleur-notion-token -w 2>/dev/null)"

# Logboek kort houden: hooguit de laatste duizend regels.
if [[ -f $LOG && $(wc -l < $LOG) -gt 1000 ]]; then
  tail -400 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi

if [[ -z "$MAIL_PASS" ]]; then
  echo "$(date '+%d-%m %H:%M') — geen wachtwoord in de sleutelhanger, niets gedaan"
  exit 1
fi

/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  leadgen_mail.py tick "$@" || echo "$(date '+%d-%m %H:%M') — tick mislukt"
