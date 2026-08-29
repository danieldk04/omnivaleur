#!/bin/zsh
# Eén ronde van de automatische developer-starter, elke tien minuten gestart door
# de LaunchAgent com.omnivaleur.devstarter (zie config/com.omnivaleur.devstarter.plist).
#
# WAAROM DIT BESTAND ER TUSSEN ZIT
# launchd start geen python en kent geen PATH van Daniels schil. Bovendien moet
# er iets zijn dat het hárd meldt wanneer macOS de achtergrondtaak geen toegang
# geeft tot ~/Documents — dat is namelijk de meest waarschijnlijke manier waarop
# dit stilvalt, en het valt dan stil zonder één foutmelding. Zie de notitie
# hierover in scripts/leadgen_tick.sh: dezelfde val heeft de koude-mailmachine
# een halve dag stilgelegd.
#
# De sleutels komen uit de .env van het project (SUPABASE_URL / SUPABASE_SERVICE_KEY);
# hier staat dus met opzet geen enkel wachtwoord.
set -u

REPO=~/Documents/omnivaleur
LOG=~/Library/Application\ Support/omnivaleur/dev-starter.log
# launchd geeft een kaal PATH mee, zonder node. De sessie draait daardoor wel,
# maar haar eigen hooks vallen om met "node: command not found" — zichtbaar in
# de logboeken van 29-08-2026. Dit zet de gebruikelijke plekken erbij.
export PATH=/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH

PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
[[ -x $PYTHON ]] || PYTHON=$(command -v python3)

mkdir -p ~/Library/Application\ Support/omnivaleur

# Logboek kort houden: hooguit de laatste duizend regels.
if [[ -f $LOG && $(wc -l < $LOG) -gt 1000 ]]; then
  tail -400 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
fi

if [[ ! -r $REPO/scripts/dev_starter.py ]]; then
  echo "$(date '+%d-%m %H:%M') — kan $REPO niet lezen. Geef de LaunchAgent volledige"
  echo "    schijftoegang: Systeeminstellingen > Privacy en beveiliging > Volledige"
  echo "    schijftoegang, en zet /bin/zsh erbij."
  exit 1
fi

cd $REPO || exit 1
echo "$(date '+%d-%m %H:%M') — ronde"
$PYTHON scripts/dev_starter.py "$@"
