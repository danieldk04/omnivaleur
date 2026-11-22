#!/bin/bash
# Stuurt een korte tekst naar Daniels Telegram via zijn eigen bot.
# Token en chat-id staan in telegram.env (TELEGRAM_TOKEN=..., TELEGRAM_CHAT_ID=...), nooit in dit script.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
ENVFILE="$DIR/telegram.env"
[ -f "$ENVFILE" ] || { echo "geen telegram.env: Telegram niet ingesteld" >&2; exit 2; }
# shellcheck disable=SC1090
. "$ENVFILE"
[ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || { echo "token of chat-id ontbreekt" >&2; exit 2; }
[ $# -ge 1 ] || { echo "gebruik: stuur_telegram.sh \"tekst\"" >&2; exit 2; }
curl -sS --max-time 20 -o /dev/null -w "%{http_code}\n" \
  "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=$1"
