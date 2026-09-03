#!/usr/bin/env python3
"""Eenmalig: zet de onjuiste 2dehands-melding recht die klanten te zien kregen.

WAT ER MIS WAS (03-09-2026)

De teruggenomen wachtrij schreef op elke wachtende advertentierij de tekst
"That is what it looks like when you are not signed in to 2dehands". Dat was een
conclusie, geen waarneming, en hij was fout: www.marktplaats.nl geeft op precies
hetzelfde adres precies dezelfde HTTP 401 als www.2dehands.be, en daar
publiceert dezelfde verkoper wel. Egbert Brouwer kreeg die tekst op 303
artikelrijen en mailde terug dat hij gewoon was ingelogd. Hij had gelijk.

Deze reparatie zet op die rijen (en op de teruggenomen opdrachten zelf) de
herschreven melding: de waarneming, plus de controle die hij in een klik zelf
kan doen. Zonder deze ronde blijft de oude tekst staan tot er ooit met succes
gepubliceerd wordt, en dat is precies wat er niet lukt.

Lezen is gratis, schrijven alleen met --apply:
    python3 scripts/herstel_2dehands_meldingen.py
    python3 scripts/herstel_2dehands_meldingen.py --apply
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# De zinnen die de oude, onjuiste melding herkenbaar maken. Alleen rijen die
# hier op passen worden aangeraakt: een echte, andere fout blijft staan.
OUD_HERKENBAAR = (
    "That is what it looks like when you are not signed in",
    "Extension timed out waiting for this 2dehands job to finish",
    "Extension timed out waiting for this marktplaats job to finish",
)


def main(apply: bool) -> None:
    from backend.database import get_db, fetch_all
    from backend.api.jobs import _melding_formulier_ging_niet_open

    db = get_db()
    geraakt = {"listings": 0, "jobs": 0}

    for platform in ("2dehands", "marktplaats"):
        nieuw = _melding_formulier_ging_niet_open(platform)

        rijen = fetch_all(lambda: db.table("listings")
                          .select("id,item_id,error_message")
                          .eq("platform", platform).eq("status", "error")) or []
        doelen = [r["id"] for r in rijen
                  if any(z in (r.get("error_message") or "") for z in OUD_HERKENBAAR)]
        print(f"{platform}: {len(doelen)} van {len(rijen)} mislukte advertentierijen dragen de oude tekst")
        geraakt["listings"] += len(doelen)
        if apply:
            for i in range(0, len(doelen), 200):
                db.table("listings").update({"error_message": nieuw}) \
                    .in_("id", doelen[i:i + 200]).execute()

        opdrachten = fetch_all(lambda: db.table("jobs")
                               .select("id,result")
                               .eq("platform", platform).eq("status", "cancelled")) or []
        jdoelen = [j["id"] for j in opdrachten
                   if any(z in str((j.get("result") or {}).get("error") or "") for z in OUD_HERKENBAAR)]
        print(f"{platform}: {len(jdoelen)} teruggenomen opdrachten dragen de oude tekst")
        geraakt["jobs"] += len(jdoelen)
        if apply:
            for i in range(0, len(jdoelen), 200):
                db.table("jobs").update({"result": {"cancelled": "queue stopped", "error": nieuw}}) \
                    .in_("id", jdoelen[i:i + 200]).execute()

    print(f"\n{'BIJGEWERKT' if apply else 'ZOU BIJWERKEN'}: "
          f"{geraakt['listings']} advertentierijen, {geraakt['jobs']} opdrachten")
    if not apply:
        print("Draai opnieuw met --apply om het echt te doen.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
