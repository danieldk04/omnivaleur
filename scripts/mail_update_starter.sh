#!/bin/zsh
# Eén wekelijkse ronde: stelt de "wekelijkse update"-mail op (zie
# scripts/mail_update_prompt.txt) en stuurt een testmail naar Daniel zelf.
# Verstuurt NOOIT iets naar echte klanten, dat blijft zijn eigen klik in
# beheer.html. Gestart door de LaunchAgent com.omnivaleur.mailupdate
# (config/com.omnivaleur.mailupdate.plist), zelfde opzet als
# com.omnivaleur.devstarter (zie scripts/dev_starter.sh voor de uitleg
# waarom deze tussenlaag nodig is: launchd kent geen PATH en geeft geen
# eigen foutmelding als macOS de toegang tot ~/Documents weigert).
set -u

REPO=~/Documents/omnivaleur
LOG=~/Library/Application\ Support/omnivaleur/mail-update.log
export PATH=/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH

mkdir -p ~/Library/Application\ Support/omnivaleur

if [[ -f $LOG && $(wc -l < $LOG) -gt 1000 ]]; then
  tail -400 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi

if ! head -c 1 $REPO/scripts/mail_update_prompt.txt >/dev/null 2>&1; then
  {
    echo "$(date '+%d-%m %H:%M') — GEEN TOEGANG tot $REPO. Er is niets gestart."
    echo "    macOS blokkeert dit. Oplossen: Systeeminstellingen > Privacy en"
    echo "    beveiliging > Volledige schijftoegang, klik op +, druk cmd+shift+G,"
    echo "    typ /bin/zsh en voeg die toe."
  } >> $LOG
  exit 1
fi

CLAUDE=$(command -v claude || echo "$HOME/.local/bin/claude")
if [[ ! -x $CLAUDE ]]; then
  echo "$(date '+%d-%m %H:%M') — de claude-opdrachtregel is niet gevonden, niets gestart" >> $LOG
  exit 1
fi

cd $REPO || exit 1
echo "$(date '+%d-%m %H:%M') — wekelijkse update-ronde" >> $LOG

# ANTHROPIC_API_KEY eruit: dit moet op Daniels eigen Claude-abonnement lopen,
# niet afgerekend per token via de API-sleutel uit .env. Zelfde reden als in
# scripts/dev_starter.py.
env -u ANTHROPIC_API_KEY "$CLAUDE" -p "$(cat scripts/mail_update_prompt.txt)" \
  --dangerously-skip-permissions >> $LOG 2>&1
