"""Welke live advertenties staan in een andere taal dan het kanaal verwacht?

WAAROM DIT ER IS (22-09-2026, De Juiste Toon)

Zijn lederhose stond in het Duits op marktplaats.nl. Niet omdat hij Duits had
geplakt (dat dacht de notitie van 22-09 eerst): zijn artikel was Nederlands, en
onze vertaling maakte er een Duitse omschrijving van met het stempel `_taal: nl`
erop. Zie docs/team-notes.md, 23-09-2026. Dat is gerepareerd, maar de
advertenties die er toen al stonden blijven fout tot ze opnieuw geplaatst
worden.

Zijn vraag via Daniel: *"Dus dan moet ik alles nakijken? En gaan omzetten.
Kunnen jullie vast sneller dan ik."* Terecht. Dit script zoekt ze voor hem op.

WAAR DE TEKST VANDAAN KOMT (23-09-2026)

Uit de openbare zoek-API van het kanaal (marktplaats.nl en 2dehands.be,
`sellerIds[]`, 100 per pagina), niet uit onze items-tabel. De eerste versie las
items.title/description en meldde bij Toon "geen enkele in een andere taal",
terwijl er 10 Duits of Engels online stonden: de artikelen waren Nederlands, de
fout zat in de opdracht die naar het kanaal ging (Duitse omschrijving met het
stempel `_taal: nl`). Wat de bezoeker ziet is dus de enige bron die telt.

Het verkopersnummer wordt bewezen met een van onze eigen advertentienummers,
en de advertenties worden aan onze boeken gekoppeld via platform_listing_id.
Kan het nummer niet bewezen worden, dan zegt het script dat het niets zag in
plaats van "nul fout". De zoek-API geeft van de omschrijving alleen de eerste
200 tekens; daar staat de tekst zelf, het winkelblok valt er meestal af.

WAT DIT SCRIPT WEL EN NIET DOET

Standaard schrijft het NIETS: het meldt alleen welke advertenties in een andere
taal staan dan het kanaal verwacht, met de telling per taal erbij, zodat je ziet
of het om drie of om driehonderd gaat.

Met `--doen` zet het ze opnieuw op de gewone manier: `refresh_listing(...,
"relist", negeer_afkoeling=True)`. Zonder afkoeling, want dit is een reparatie:
deze advertenties zijn vaak pas een paar dagen oud, en de afkoeling van 21 dagen
liet ze op 23-09 anders weken in de verkeerde taal staan. Het dagquotum en de
rem op rubrieken die op 2dehands geld kosten blijven gewoon staan.

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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IN_BROK = 200
KANALEN = ("marktplaats", "2dehands")
# Alleen echte advertentienummers staan op de openbare verkoperslijst. Een
# Admarkt- of webwinkelnummer niet; daarover doet dit script geen uitspraak.
ADVERTENTIENUMMER = re.compile(r"^m\d{6,}$")


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


def kies_verdachte(openbaar: list[dict], onze: dict[str, dict],
                   bevat: str | None = None) -> list[tuple[dict | None, dict, str]]:
    """Welke van deze LIVE advertenties staan niet in het Nederlands?

    `openbaar` is wat de zoek-API van het kanaal teruggeeft (itemId, title,
    description): de tekst die een bezoeker echt ziet. `onze` zijn onze
    advertentierijen op platform_listing_id. Geeft (rij, advertentie, taal);
    `rij` is None als de advertentie wel op zijn lijst staat maar niet in onze
    boeken, want die kunnen we niet opnieuw plaatsen en mogen we niet verzwijgen.

    Waarom niet de items-rij: op 23-09-2026 stond die bij De Juiste Toon overal
    in het Nederlands, terwijl er 10 advertenties Duits of Engels online stonden.
    De fout zat in wat er naar het kanaal ging, niet in het artikel.

    Losgetrokken van de database en van het net, zodat de keuze te beproeven is.
    """
    from backend.services.crosslist import leest_als_andere_taal

    uit = []
    for adv in openbaar:
        rij = onze.get(adv.get("itemId"))
        titel = adv.get("title") or ""
        if bevat and bevat.lower() not in titel.lower():
            continue
        samen = f"{titel}\n{adv.get('description') or ''}"
        # Dezelfde functie die de server gebruikt om te beslissen of er vertaald
        # moet worden. Eén bron, anders meldt dit script iets anders dan er gebeurt.
        if leest_als_andere_taal(samen, "nl"):
            uit.append((rij, adv, _welke_taal(samen)))
    return uit


def _onze_advertenties(db, uid: str, kanalen: tuple[str, ...]) -> dict[str, dict]:
    """Onze live advertenties van deze ene verkoper, op advertentienummer,
    inclusief die al opnieuw klaargezet zijn (status 'relisting').

    Alleen per user_id en zonder grote kolommen: de productiedatabase is één
    kleine instantie die de live site deelt (twee keer plat, 19-09 en 22-09).
    Artikelen MET .order("id"), anders mist het pagineren rijen.
    """
    titels, off = {}, 0
    while True:
        blok = (db.table("items").select("id,title")
                .eq("user_id", uid).order("id").range(off, off + 999).execute().data) or []
        for r in blok:
            titels[r["id"]] = r.get("title")
        off += len(blok)
        if len(blok) < 1000:
            break
    ids = list(titels)
    uit: dict[str, dict] = {}
    for i in range(0, len(ids), IN_BROK):
        for r in (db.table("listings")
                  .select("item_id,platform,status,platform_listing_id")
                  .in_("item_id", ids[i:i + IN_BROK])
                  .in_("platform", list(kanalen))
                  # 'relisting' hoort erbij: dan staat de oude advertentie nog
                  # live tot de extensie hem weghaalt. Zonder die status
                  # heetten Toons vijf lederhosen op 23-09 "niet van ons".
                  .in_("status", ["active", "relisting"])
                  .not_.is_("platform_listing_id", "null")
                  .execute().data or []):
            if ADVERTENTIENUMMER.match(str(r["platform_listing_id"])):
                uit[r["platform_listing_id"]] = {**r, "titel": titels.get(r["item_id"])}
    return uit


async def _openbare_lijst(kanaal: str, onze: list[dict]) -> tuple[int | None, list[dict], bool]:
    """(verkopersnummer, zijn openbare advertenties, lijst compleet?).

    Het verkopersnummer wordt bewezen met een van onze eigen advertentienummers,
    niet gestemd op titels: stemmen leverde op 13-09-2026 een vreemde verkoper
    met 3.700 advertenties op. Dezelfde functies als de fotocontrole.
    """
    import httpx
    from backend.services.foto_controle import _verkopersnummer, _verkoperslijst
    from backend.services.mp_enrich import UA, ZOEK_PER_PLATFORM
    zoek_url, basis = ZOEK_PER_PLATFORM[kanaal]
    async with httpx.AsyncClient(base_url=basis, headers={"User-Agent": UA},
                                 timeout=30, follow_redirects=True) as client:
        verkoper = await _verkopersnummer(client, zoek_url, onze)
        if not verkoper:
            return None, [], False
        lijst, volledig = await _verkoperslijst(client, zoek_url, verkoper)
        return verkoper, lijst, volledig


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

    kanalen = (args.kanaal,) if args.kanaal else KANALEN
    onze = _onze_advertenties(db, uid, kanalen)
    print(f"{args.email or uid}: {len(onze)} advertenties met een advertentienummer "
          f"op {', '.join(kanalen)} in onze boeken.")

    verdacht: list[tuple[dict | None, dict, str]] = []
    geen_uitspraak = []
    for kanaal in kanalen:
        eigen = [r for r in onze.values() if r["platform"] == kanaal]
        if not eigen:
            print(f"  {kanaal}: geen advertenties van ons, overgeslagen.")
            continue
        verkoper, lijst, volledig = await _openbare_lijst(kanaal, eigen)
        if not verkoper:
            # Niet "nul fout": we hebben niets gezien.
            print(f"  {kanaal}: verkopersnummer niet te bewijzen met een eigen "
                  f"advertentienummer. GEEN uitspraak over dit kanaal.")
            geen_uitspraak.append(kanaal)
            continue
        gekoppeld = sum(1 for a in lijst if a.get("itemId") in onze)
        print(f"  {kanaal}: verkoper {verkoper}, {len(lijst)} openbare advertenties, "
              f"waarvan {gekoppeld} aan onze boeken gekoppeld"
              + ("" if volledig else ". LET OP: lijst niet compleet") + ".")
        if not lijst:
            geen_uitspraak.append(kanaal)
            continue
        verdacht += kies_verdachte(lijst, onze, args.bevat)

    if not verdacht:
        if geen_uitspraak:
            print(f"\nNiets gevonden, maar over {', '.join(geen_uitspraak)} kon ik niets zien.")
            return 1
        print("\nGeen enkele live advertentie staat in een andere taal dan het Nederlands"
              + (f" (met '{args.bevat}' in de titel)." if args.bevat else "."))
        return 0

    per_taal: dict[str, int] = {}
    for _, _, taal in verdacht:
        per_taal[taal] = per_taal.get(taal, 0) + 1
    print(f"\n{len(verdacht)} live advertentie(s) staan NIET in het Nederlands: "
          + ", ".join(f"{n}x {t}" for t, n in sorted(per_taal.items(), key=lambda p: -p[1])))
    for rij, adv, taal in verdacht[:60]:
        waar = (("al klaargezet" if rij["status"] == "relisting" else rij["platform"])
                if rij else "niet van ons")
        print(f"  [{taal}] {waar:13} {adv.get('itemId') or '':<14} "
              f"{(adv.get('title') or '')[:58]}")
    if len(verdacht) > 60:
        print(f"  … en nog {len(verdacht) - 60}")
    bezig = sum(1 for rij, _a, _t in verdacht if rij and rij["status"] == "relisting")
    if bezig:
        print(f"\n{bezig} daarvan staan al klaar om opnieuw geplaatst te worden; de oude "
              "advertentie verdwijnt zodra de extensie bij hem draait.")
    los = [adv for rij, adv, _ in verdacht if rij is None]
    if los:
        print(f"\n{len(los)} daarvan staan niet in onze boeken; die kan dit script niet "
              "opnieuw plaatsen.")

    if not args.doen:
        print("\nEr is niets gewijzigd. Draai met --doen om ze opnieuw te laten plaatsen.")
        print("Let op: op Marktplaats en 2dehands betekent dat weghalen en opnieuw")
        print("plaatsen, dus een nieuw advertentienummer en een nieuwe startpositie.")
        return 0

    from backend.services.relist import RefreshError, refresh_listing
    print(f"\nOpnieuw plaatsen, hoogstens {args.max}:")
    gedaan = 0
    for rij, adv, _taal in verdacht:
        if rij is None or rij["status"] == "relisting":
            continue
        if gedaan >= args.max:
            print(f"  (gestopt bij --max {args.max})")
            break
        titel = (adv.get("title") or "")[:50]
        try:
            # negeer_afkoeling: dit is een reparatie, geen verversing. Deze
            # advertenties zijn vaak net geplaatst; de afkoeling van 21 dagen
            # zou ze weken in de verkeerde taal laten staan. Het dagquotum en
            # de rem op betaalde rubrieken blijven gewoon gelden.
            uit = await refresh_listing(rij["item_id"], rij["platform"], uid, "relist",
                                        negeer_afkoeling=True)
            gedaan += 1
            print(f"  ok   {rij['platform']:11} {titel} → {uit.get('status')}")
        except RefreshError as e:
            # Het dagquotum of een rubriek die geld kost. Allebei bewust, en
            # allebei een reden om te stoppen in plaats van door te drukken.
            print(f"  stop {rij['platform']:11} {titel} → {e}")
            break
        except Exception as e:  # noqa: BLE001 — één advertentie mag de rest niet meenemen
            print(f"  FOUT {rij['platform']:11} {titel} → {e}")
    print(f"\n{gedaan} advertentie(s) opnieuw klaargezet. De extensie plaatst ze "
          f"zodra Chrome bij hem openstaat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
