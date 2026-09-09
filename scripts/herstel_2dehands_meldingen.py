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

    geraakt = _zet_betaalmuur_recht(db, apply, geraakt)

    print(f"\n{'BIJGEWERKT' if apply else 'ZOU BIJWERKEN'}: "
          f"{geraakt['listings']} advertentierijen, {geraakt['jobs']} opdrachten")
    if not apply:
        print("Draai opnieuw met --apply om het echt te doen.")


# De teksten die op een rij kunnen staan terwijl de echte oorzaak de betaalmuur
# was. Alleen deze worden aangeraakt; een echte, uitgelegde fout ("vul de
# foto's in") blijft staan, want die zegt wél iets over dat ene artikel.
_TE_HERSCHRIJVEN = OUD_HERKENBAAR + (
    "listing form never opened",
    "is on hold for your account",
    # De schadelijkste van allemaal: bij Egbert 357 keer, en aantoonbaar onwaar.
    # Zijn scan van diezelfde minuut gaf HTTP 200 op het afgeschermde overzicht.
    "not signed in to",
    "don't appear to be signed in",
    # Ook onze eigen eerdere uitleg mag herschreven worden: zolang de oorzaak
    # scherper wordt, hoort de tekst op de rij mee te bewegen.
    "does not let your account place adverts for free",
)


def _zet_betaalmuur_recht(db, apply: bool, geraakt: dict) -> dict:
    """Rijen van accounts waar het kanaal aantoonbaar om geld vraagt.

    WAAROM DIT APART STAAT (09-09-2026, Egbert Brouwer). De ronde hierboven zet
    een onjuiste conclusie recht met een waarneming: "het formulier meldde zich
    nooit". Voor hem is inmiddels gemeten dát het formulier zich meldde, en waar
    het tabblad daarna heen ging: /payments/orderOverview. Zijn 275 rode rijen
    wijzen hem dus nog steeds naar zijn inlog terwijl de oorzaak ergens anders
    ligt, en die tekst blijft staan tot er ooit een 2dehands-advertentie lukt.
    Dat gaat op dit account niet gebeuren.

    Alleen accounts waar de betaalmuur echt is waargenomen worden aangeraakt.
    Gemeten op 09-09-2026 over alle 46 accounts en vier kanalen: dat is er
    precies één.
    """
    from backend.database import fetch_all
    from backend.api.jobs import (_BETAALMUUR, _melding_kanaal_vraagt_geld,
                                  _melding_link_uit_advertentie)
    from backend.services.crosslist import _zonder_links

    # WIE ER GERAAKT WORDT KOMT UIT DE OPDRACHTEN ZELF, niet uit auth.admin:
    # die laatste heeft de servicesleutel nodig en is hier niet altijd voorhanden.
    for platform in ("2dehands", "marktplaats"):
        alle = fetch_all(lambda: db.table("jobs").select("user_id")
                         .eq("platform", platform).eq("action", "create")
                         .in_("status", ["error", "cancelled"])) or []
        for uid in sorted({j["user_id"] for j in alle if j.get("user_id")}):
            # WELKE VAN DE TWEE VERHALEN IS HET.
            #
            # Strandde het op de betaalmuur terwijl er een webadres in de tekst
            # stond, dan is dat de oorzaak en is die inmiddels weggenomen: dan
            # hoort er "het is opgelost, klik opnieuw" te staan, geen kanaal dat
            # dicht gaat. Was de tekst al schoon, dan rekent het kanaal echt
            # geld en gaat het uit. Zie _kanaal_hard_dicht in jobs.py.
            geraakte = fetch_all(lambda: db.table("jobs").select("result,payload")
                                 .eq("user_id", uid).eq("platform", platform)
                                 .eq("action", "create")
                                 .in_("status", ["error", "cancelled"])) or []
            betaal = [j for j in geraakte if _BETAALMUUR.search(
                f"{(j.get('result') or {}).get('error') or ''} "
                f"{(j.get('result') or {}).get('error_oorspronkelijk') or ''}")]
            if not betaal:
                continue
            door_link = [j for j in betaal
                         if _zonder_links(str((j.get("payload") or {}).get("description") or ""))
                         != str((j.get("payload") or {}).get("description") or "")]
            if len(door_link) == len(betaal):
                nieuw = _melding_link_uit_advertentie(platform)
                print(f"\n{uid} / {platform}: gestrand op het webadres in de tekst "
                      f"({len(betaal)} opdrachten) — oorzaak weggenomen")
            else:
                nieuw = _melding_kanaal_vraagt_geld(platform)
                print(f"\n{uid} / {platform}: kanaal vraagt geld per advertentie")

            # listings draagt geen user_id: via de artikelen van deze verkoper.
            artikelen = fetch_all(lambda: db.table("items").select("id").eq("user_id", uid)) or []
            mijn = {a["id"] for a in artikelen}
            rijen = fetch_all(lambda: db.table("listings")
                              .select("id,item_id,error_message")
                              .eq("platform", platform).eq("status", "error")) or []
            doelen = [r["id"] for r in rijen
                      if r.get("item_id") in mijn
                      and any(z in (r.get("error_message") or "") for z in _TE_HERSCHRIJVEN)]
            print(f"  {len(doelen)} advertentierijen dragen nog de oude uitleg")
            geraakt["listings"] += len(doelen)
            if apply:
                for i in range(0, len(doelen), 200):
                    db.table("listings").update({"error_message": nieuw}) \
                        .in_("id", doelen[i:i + 200]).execute()

            # Alleen plaatsopdrachten: een scan komt nooit op de betaalpagina uit,
            # en een scanfout ("401 op je advertentieoverzicht") is een echt,
            # ander verhaal dat gewoon moet blijven staan.
            opdrachten = fetch_all(lambda: db.table("jobs").select("id,result")
                                   .eq("user_id", uid).eq("platform", platform)
                                   .eq("action", "create")
                                   .in_("status", ["cancelled", "error"])) or []
            jdoelen = [j["id"] for j in opdrachten
                       if any(z in str((j.get("result") or {}).get("error") or "")
                              for z in _TE_HERSCHRIJVEN)]
            print(f"  {len(jdoelen)} opdrachten dragen nog de oude uitleg")
            geraakt["jobs"] += len(jdoelen)
            if apply:
                for i in range(0, len(jdoelen), 200):
                    db.table("jobs").update(
                        {"result": {"cancelled": "queue stopped", "error": nieuw}}) \
                        .in_("id", jdoelen[i:i + 200]).execute()
    return geraakt


if __name__ == "__main__":
    main("--apply" in sys.argv)
