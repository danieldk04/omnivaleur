#!/bin/zsh
# Kopieert de mailmachine naar de plek waar hij echt draait, buiten iCloud en
# buiten ~/Documents. Draai dit na ELKE wijziging aan leadgen_mail.py,
# leadgen_notion.py of mail_analyse.py — anders blijft de achtergrondtaak de oude
# versie gebruiken. mail_analyse.py hoort er sinds 06-09-2026 bij: leadgen_mail.py
# doet `import mail_analyse` voor de toonmeting en de storingsstand, en zonder dat
# bestand meldt de tick stil "No module named 'mail_analyse'".
set -eu
cd "$(dirname "$0")/.."
DOEL="$HOME/Library/Application Support/omnivaleur"
mkdir -p "$DOEL/code/output"
cp scripts/leadgen_mail.py scripts/leadgen_notion.py scripts/mail_analyse.py "$DOEL/code/"
cp scripts/leadgen_tick.sh "$DOEL/tick.sh"
chmod +x "$DOEL/tick.sh"
ln -sfn "$DOEL/leads" "$DOEL/code/output/leads"
echo "mailmachine bijgewerkt in $DOEL"
