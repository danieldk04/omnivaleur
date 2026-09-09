"""Vul week_metingen met terugwerkende kracht.

Draai dit één keer nadat de tabellen mail_events en week_metingen in Supabase
zijn aangemaakt (zie schema.sql). Het leest de laatste weken opnieuw uit
auth.users, mail_state en mail_opens en schrijft één rij per week weg. De
Resend-velden (bezorging, bounce) blijven leeg voor weken van vóór de webhook;
die vullen zich vanzelf zodra de webhook loopt.

    python3 scripts/backfill_week_metingen.py [aantal_weken]

Veilig om vaker te draaien: het is een upsert op de maandag van de week.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.week_meting import backfill

if __name__ == "__main__":
    weken = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    uit = backfill(weken)
    for r in uit:
        rij = r.get("rij", {})
        stand = "ok" if r.get("ok") else f"FOUT: {r.get('reden')}"
        print(f"{rij.get('week_maandag')}  aanmeldingen={rij.get('signups_nieuw')} "
              f"verstuurd={rij.get('km_verstuurd')} open2={rij.get('km_open_pct_mail2')}% "
              f"bounce={rij.get('km_bounced')}  [{stand}]")
    mislukt = [r for r in uit if not r.get("ok")]
    if mislukt:
        print(f"\n{len(mislukt)} week(en) niet opgeslagen. Bestaat de tabel week_metingen al?")
        sys.exit(1)
    print(f"\n{len(uit)} weken weggeschreven naar week_metingen.")
