#!/bin/bash
# Wrapper zodat de leadgen-mailscripts (koude mail, creator-outreach) altijd op
# dezelfde manier draaien: wachtwoord/token uit de sleutelhanger, nooit in een
# bestand of in de shell-history. Bestaat zodat er precies één commandopatroon
# is om aan de permissieregels toe te staan, in plaats van elke keer een nieuwe
# variant van "security find-generic-password | python3 ...".
#
# Gebruik: scripts/run_leadgen_mail.sh <scriptnaam.py> [argumenten]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

export NOTION_TOKEN="$(security find-generic-password -a notion -s omnivaleur-notion-token -w 2>/dev/null || true)"
export MAIL_PASS="$(security find-generic-password -a daniel@omnivaleur.nl -s omnivaleur-leadgen-mail -w 2>/dev/null || true)"
export MAIL_HOST="${MAIL_HOST:-smtp.zoho.eu}"
export MAIL_USER="${MAIL_USER:-daniel@omnivaleur.nl}"

script="$1"
shift
exec python3 "scripts/$script" "$@"
