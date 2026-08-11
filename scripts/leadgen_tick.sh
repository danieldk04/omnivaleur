#!/bin/zsh
# Eén autonome beurt van de koude-mailmachine. Wordt elke tien minuten gestart
# door de LaunchAgent com.omnivaleur.leadgen (zie ~/Library/LaunchAgents/).
#
# Wachtwoorden staan NIET in dit bestand maar in de sleutelhanger van de Mac.
# Daardoor kan dit script gewoon mee in git zonder dat er iets uitlekt, en werkt
# het alleen op deze computer wanneer Daniel is ingelogd.
set -u

cd "$(dirname "$0")/.." || exit 1

export MAIL_HOST=smtp.zoho.eu
export IMAP_HOST=imap.zoho.eu
export MAIL_USER=daniel@omnivaleur.nl
export MAIL_PASS="$(security find-generic-password -a daniel@omnivaleur.nl -s omnivaleur-leadgen-mail -w 2>/dev/null)"
export NOTION_TOKEN="$(security find-generic-password -a notion -s omnivaleur-notion-token -w 2>/dev/null)"

if [[ -z "$MAIL_PASS" ]]; then
  echo "$(date '+%d-%m %H:%M') — geen wachtwoord in de sleutelhanger, niets gedaan"
  exit 1
fi

exec /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  scripts/leadgen_mail.py tick "$@"
