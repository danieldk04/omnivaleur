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

TELLER=~/Library/Application\ Support/omnivaleur/mislukt.txt

if /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 leadgen_mail.py tick "$@"; then
  rm -f $TELLER
else
  echo "$(date '+%d-%m %H:%M') — tick mislukt"
  # Drie keer achter elkaar mis betekent dat het niet vanzelf overgaat. Dan moet
  # Daniel het weten, en wel via een weg die niets van het script nodig heeft —
  # want het script is juist wat kapot is. Dit gebeurde op 11-08: 21 uur stil
  # zonder één signaal.
  N=$(( $(cat $TELLER 2>/dev/null || echo 0) + 1 ))
  echo $N > $TELLER
  if [[ $N -eq 3 ]]; then
    /usr/bin/python3 - "$MAIL_USER" "$MAIL_PASS" <<'PYEOF'
import smtplib, ssl, sys, socket
from datetime import datetime
from email.message import EmailMessage
van, pw = sys.argv[1], sys.argv[2]
msg = EmailMessage()
msg["From"] = f"Leadmachine <{van}>"
msg["To"] = "danieldekoning66@gmail.com, info@revaleur.com"
msg["Subject"] = "Leadmachine LIGT STIL"
msg.set_content(
    f"De koude-mailmachine is drie keer achter elkaar gecrasht en verstuurt niets meer.\n"
    f"Tijd: {datetime.now():%d-%m-%Y %H:%M} op {socket.gethostname()}\n\n"
    f"Het logboek staat in:\n"
    f"  ~/Library/Application Support/omnivaleur/tick.log\n\n"
    f"Laat Claude ernaar kijken.\n")
try:
    with smtplib.SMTP_SSL("smtp.zoho.eu", 465, context=ssl.create_default_context()) as s:
        s.login(van, pw); s.send_message(msg)
    print("noodsignaal verstuurd")
except Exception as e:
    print("noodsignaal MISLUKT:", e)
PYEOF
  fi
fi
