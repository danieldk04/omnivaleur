#!/bin/zsh
# ── Installeren op de Mac ──────────────────────────────────────────────────
#   cp config/dev_starter_stub.sh ~/Library/Application\ Support/omnivaleur/dev_starter.sh
#   chmod +x ~/Library/Application\ Support/omnivaleur/dev_starter.sh
#   cp config/com.omnivaleur.devstarter.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.omnivaleur.devstarter.plist
# Stub voor de LaunchAgent com.omnivaleur.devstarter.
#
# De echte wrapper staat in de projectmap (scripts/dev_starter.sh), zodat een
# wijziging daar meteen meetelt. Dit bestand staat bewust BUITEN ~/Documents,
# want dat is precies de map waar macOS een achtergrondtaak geen toegang toe
# geeft — en dan moet er nog iets zijn dat dat kan zeggen.
#
# LET OP: testen met [[ -r bestand ]] werkt hier NIET. macOS laat het opvragen
# van de bestandsgegevens gewoon toe en weigert pas het openen, dus die test
# slaagt terwijl de volgende regel alsnog stukloopt. We lezen daarom echt een byte.
set -u
REPO=~/Documents/omnivaleur

if ! head -c 1 $REPO/scripts/dev_starter.sh >/dev/null 2>&1; then
  echo "$(date '+%d-%m %H:%M') — GEEN TOEGANG tot $REPO. Er is niets gestart."
  echo "    macOS blokkeert dit. Oplossen: Systeeminstellingen > Privacy en"
  echo "    beveiliging > Volledige schijftoegang, klik op +, druk cmd+shift+G,"
  echo "    typ /bin/zsh en voeg die toe. Daarna:"
  echo "      launchctl kickstart -k gui/\$(id -u)/com.omnivaleur.devstarter"
  exit 1
fi

exec /bin/zsh $REPO/scripts/dev_starter.sh "$@"
