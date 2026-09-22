"""Welke live advertenties staan in een andere taal dan het kanaal verwacht?

WAAROM DIT ER IS (22-09-2026, De Juiste Toon)

Zijn lederhose stond in het Duits op marktplaats.nl. Oorzaak en reparatie staan
in docs/team-notes.md: onze taalherkenning kende alleen Nederlands en Engels, dus
een Duitse tekst met zijn Nederlandse winkelblok eronder telde als "staat al in
het Nederlands" en de vertaling werd overgeslagen. Dat is gerepareerd, maar de
advertenties die er toen al stonden blijven Duits tot ze opnieuw geplaatst
worden.

Zijn vraag via Daniel: *"Dus dan moet ik alles nakijken? En gaan omzetten.
Kunnen jullie vast sneller dan ik."* Terecht. Dit script zoekt ze voor hem op.

WAT DIT SCRIPT WEL EN NIET DOET

Standaard schrijft het NIETS: het meldt alleen welke advertenties in een andere
taal staan dan het kanaal verwacht, met de telling per taal erbij, zodat je ziet
of het om drie of om driehonderd gaat.

Met `--doen` zet het ze opnieuw op de gewone manier: `refresh_listing(...,
"relist")`, precies het pad dat de nachtelijke herplaatsronde ook gebruikt. Alle
bestaande remmen blijven dus staan — de afkoeling van 21 dagen, het dagquotum,
en de rem op rubrieken die op 2dehands geld kosten.

WAAROM HIER GEEN OPTIE ZIT OM HET DAGQUOTUM TE OMZEILEN

`MAX_REFRESHES_PER_USER_PER_DAY` staat op 8 en dat is geen technische grens maar
een bescherming: honderden advertenties op één dag opnieuw plaatsen is op
Marktplaats geen winkelonderhoud meer maar een patroon. Die grens omzeilen zou
het probleem van de verkoper verplaatsen naar zijn account.

EN WAAROM JE NIET ALLES IN ÉÉN KEER MOET WILLEN OMZETTEN

Op Marktplaats en 2dehands bestaat alleen de strategie "relist": de advertentie
wordt weggehaald en opnieuw geplaatst. Dat kost hem het advertentienummer en de
positie die de advertentie had opgebouwd. Voor advertenties die tóch aan de
beurt komen in de herplaatsronde is dat geen extra prijs — die worden sowieso
herplaatst, en komen er voortaan in het Nederlands uit. Alleen waar haast bij is
(bij hem: de lederhosen voor de oktoberfeesten) is het de moeite om voor te
kruipen. Daar is `--bevat` voor.

Gebruik:
    python3 scripts/vreemde_taal_advertenties.py --user-id 96e30080-...
    python3 scripts/vreemde_taal_advertenties.py --email djt@dejuistetoon.eu
    python3 scripts/vreemde_taal_advertenties.py --user-id ... --bevat lederhos
    python3 scripts/vreemde_taal_advertenties.py --user-id ... --bevat lederhos --doen --max 3
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IN_BROK = 200
KANALEN = ("marktplaats", "2dehands")


def _zoek_user_id(args) -> str | None:
    if args.user_id:
        return args.user_id
    if not args.email:
        print("Geef --email of --user-id op.")
        return None
    # Het opzoeken van een adres vraagt de servicesleutel; de gewone client
    # draait op de anon-sleutel en krijgt daar "User not allowed" terug.
    sleutel = os.environ.get("SUPABASE_SERVICE_KEY")
    if not sleutel:
        print("Zonder SUPABASE_SERVICE_KEY kan ik geen adres opzoeken. Geef --user-id op.")
        return None
    from supabase import create_client
    beheer = create_client(os.environ["SUPABASE_URL"], sleutel)
    for gebruiker in beheer.auth.admin.list_users():
        if (gebruiker.email or "").lower() == args.email.lower():
            return gebruiker.id
    print(f"Geen account gevonden voor {args.email}")
    return None


def _welke_taal(tekst: str) -> str:
    """De taal die het zwaarst weegt in deze tekst, voor de melding op het scherm."""
    from backend.services.crosslist import _taaltellingen
    tellingen, _ = _taaltellingen(tekst)
    taal, aantal = max(tellingen.items(), key=lambda p: p[1])
    return taal if aantal else "?"


def kies_verdachte(advertenties: list[dict], items: dict[str, dict],
                   bevat: str | None = None) -> list[tuple[dict, dict, str]]:
    """Welke van deze live advertenties staan niet in het Nederlands?

    Losgetrokken van de database zodat de keuze te beproeven is zonder Supabase
    en zonder Marktplaats — dezelfde afspraak als `vergelijk` in
    scripts/controleer_advertenties_online.py.
    """
    from backend.services.crosslist import leest_als_andere_taal

    uit = []
    for rij in advertenties:
        item = items.get(rij["item_id"])
        if not item:
            continue
        if bevat and bevat.lower() not in (item.get("title") or "").lower():
            continue
        samen = f"{item.get('title') or ''}\n{item.get('description') or ''}"
        # Dezelfde functie die de server gebruikt om te beslissen of er vertaald
        # moet worden. Eén bron, anders meldt dit script iets anders dan er gebeurt.
        if leest_als_andere_taal(samen, "nl"):
            uit.append((rij, item, _welke_taal(samen)))
    return uit


def _artikelen(db, uid: str) -> dict[str, dict]:
    """Alle artikelen van deze verkoper. MET .order("id").

    Zonder vaste volgorde mag de database elke pagina anders sorteren: dan komen
    sommige artikelen dubbel terug en andere helemaal niet. Zie de toelichting in
    scripts/controleer_advertenties_online.py — dat is daar echt misgegaan.
    """
    uit, off = {}, 0
    while True:
        blok = (db.table("items").select("id,title,description")
                .eq("user_id", uid).order("id").range(off, off + 999).execute().data) or []
        for r in blok:
            uit[r["id"]] = r
        off += len(blok)
        if len(blok) < 1000:
            break
    return uit


def _live_advertenties(db, item_ids: list[str], kanalen: tuple[str, ...]) -> list[dict]:
    rijen = []
    for i in range(0, len(item_ids), IN_BROK):
        rijen += (db.table("listings")
                  .select("item_id,platform,status,platform_listing_id")
                  .in_("item_id", item_ids[i:i + IN_BROK])
                  .in_("platform", list(kanalen))
                  .eq("status", "active")
                  .not_.is_("platform_listing_id", "null")
                  .execute().data or [])
    return rijen


async def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", help="het e-mailadres van de verkoper")
    ap.add_argument("--user-id", help="of meteen zijn user_id")
    ap.add_argument("--kanaal", choices=KANALEN, help="alleen dit kanaal (standaard: allebei)")
    ap.add_argument("--bevat", help="alleen advertenties met dit woord in de titel, "
                                    "bijvoorbeeld: lederhos")
    ap.add_argument("--doen", action="store_true",
                    help="ook echt opnieuw plaatsen. Zonder deze vlag wordt er niets geschreven.")
    ap.add_argument("--max", type=int, default=3,
                    help="hoeveel er hoogstens opnieuw geplaatst worden (standaard 3)")
    args = ap.parse_args()

    from backend.database import get_db

    db = get_db()
    uid = _zoek_user_id(args)
    if not uid:
        return 1

    items = _artikelen(db, uid)
    if not items:
        print("Dit account heeft geen artikelen.")
        return 0
    kanalen = (args.kanaal,) if args.kanaal else KANALEN
    advertenties = _live_advertenties(db, list(items), kanalen)

    verdacht = kies_verdachte(advertenties, items, args.bevat)

    print(f"{args.email or uid}: {len(items)} artikelen, "
          f"{len(advertenties)} live advertenties op {', '.join(kanalen)}"
          + (f" met '{args.bevat}' in de titel" if args.bevat else "") + ".")
    if not verdacht:
        print("Geen enkele daarvan staat in een andere taal dan het Nederlands.")
        return 0

    per_taal: dict[str, int] = {}
    for _, _, taal in verdacht:
        per_taal[taal] = per_taal.get(taal, 0) + 1
    print(f"\n{len(verdacht)} advertentie(s) staan NIET in het Nederlands: "
          + ", ".join(f"{n}x {t}" for t, n in sorted(per_taal.items(), key=lambda p: -p[1])))
    for rij, item, taal in verdacht[:60]:
        print(f"  [{taal}] {rij['platform']:11} {rij['platform_listing_id']:<14} "
              f"{(item.get('title') or '')[:58]}")
    if len(verdacht) > 60:
        print(f"  … en nog {len(verdacht) - 60}")

    if not args.doen:
        print("\nEr is niets gewijzigd. Draai met --doen om ze opnieuw te laten plaatsen.")
        print("Let op: op Marktplaats en 2dehands betekent dat weghalen en opnieuw")
        print("plaatsen, dus een nieuw advertentienummer en een nieuwe startpositie.")
        print("Wie geen haast heeft laat de nachtelijke herplaatsronde zijn werk doen:")
        print("die gaat sinds vandaag ook door de vertaling.")
        return 0

    from backend.services.relist import RefreshError, refresh_listing
    print(f"\nOpnieuw plaatsen, hoogstens {args.max}:")
    gedaan = 0
    for rij, item, _taal in verdacht:
        if gedaan >= args.max:
            print(f"  (gestopt bij --max {args.max})")
            break
        titel = (item.get("title") or "")[:50]
        try:
            uit = await refresh_listing(rij["item_id"], rij["platform"], uid, "relist")
            gedaan += 1
            print(f"  ok   {rij['platform']:11} {titel} → {uit.get('status')}")
        except RefreshError as e:
            # Het dagquotum, de afkoeling van 21 dagen of een rubriek die geld
            # kost. Alle drie bewust, en alle drie een reden om te stoppen in
            # plaats van door te drukken.
            print(f"  stop {rij['platform']:11} {titel} → {e}")
            break
        except Exception as e:  # noqa: BLE001 — één advertentie mag de rest niet meenemen
            print(f"  FOUT {rij['platform']:11} {titel} → {e}")
    print(f"\n{gedaan} advertentie(s) opnieuw klaargezet. De extensie plaatst ze "
          f"zodra Chrome bij hem openstaat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
