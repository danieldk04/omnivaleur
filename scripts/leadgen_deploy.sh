#!/bin/zsh
# Kopieert de mailmachine naar de plek waar hij echt draait, buiten iCloud en
# buiten ~/Documents. Draai dit na ELKE wijziging aan leadgen_mail.py of
# leadgen_notion.py — anders blijft de achtergrondtaak de oude versie gebruiken.
set -eu
cd "$(dirname "$0")/.."
DOEL=~/Library/Application\ Support/omnivaleur
mkdir -p $DOEL/code/output
cp scripts/leadgen_mail.py scripts/leadgen_notion.py $DOEL/code/
cp scripts/leadgen_tick.sh $DOEL/tick.sh
chmod +x $DOEL/tick.sh
ln -sfn $DOEL/leads $DOEL/code/output/leads
echo "mailmachine bijgewerkt in $DOEL"
