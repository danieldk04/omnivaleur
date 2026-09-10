"""Vangnet: een verkocht artikel dat ergens anders tóch nog te koop staat.

WAAROM DIT ER IS
`handle_item_sold` meldt een verkocht artikel meteen af bij alle andere kanalen:
API-kanalen (Shopify, eBay) rechtstreeks, extensie-kanalen (Marktplaats,
2dehands, Vinted, Facebook) via een verwijderopdracht die in de browser van de
verkoper draait. Elk van die stappen kan stil mislukken:

  * de verwijderopdracht komt op 'error' te staan (advertentie niet gevonden,
    sessie verlopen) en niets probeert hem opnieuw;
  * de browser van de verkoper stond dagen uit, de opdracht verliep;
  * de Shopify-advertentierij had geen product-id, dus de API-verwijdering
    vond niets;
  * de verkoop werd pas laat opgemerkt en er was intussen al opnieuw geplaatst.

In al die gevallen is het artikel op één kanaal verkocht en staat het op een
ander kanaal gewoon te koop: precies het dubbelverkoop-risico dat we beloven weg
te nemen. Deze ronde kijkt elke 20 minuten of dat ergens zo is en zet de
afmelding opnieuw in gang. Veilig, want er is al een bevestigde 'sold'-rij: dit
raadt niets, het maakt alleen af wat al had moeten gebeuren.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus, IN_BROK

logger = logging.getLogger(__name__)

# Hoe ver terug we verkopen meenemen. Alles wat binnen deze week niet is
# opgeruimd, ruimt deze ronde alsnog op. Ouder dan dat en het is geen storing
# meer maar geschiedenis.
TERUGBLIK_DAGEN = 7

# Speling na de verkoop voordat we ingrijpen: de gewone afmelding (en de
# extensie) krijgen eerst de kans. Onder deze grens laten we het met rust.
RESPIJT_MINUTEN = 20

# Hooguit zoveel artikelen per ronde echt aanpakken, oudste verkoop eerst, zodat
# één ronde altijd afloopt en de databaseverbinding het aankan.
PER_RONDE = 40

# Statussen waarin een advertentie nog op het platform kan staan.
_NOG_LEVEND = ("active", "error", "relisting", "hidden", "pending")

# HET VANGNET MOET ZICH ZIJN EIGEN POGINGEN HERINNEREN.
#
# GEMETEN 10-09-2026 (De Juiste Toon). Zijn artikel "Lederhosen maat 54" was op
# Vinted verkocht. De Marktplaats-advertentie ervan is voor de extensie niet te
# vinden — hij heeft een zakelijk account en zijn "Mijn advertenties" is leeg —
# dus kwam de verwijderopdracht op 'error' en bleef de rij op 'active' staan.
# Deze ronde zag dat als "nog niet afgemeld" en zette de afmelding elke twintig
# minuten opnieuw in gang: van 09-09 19:52 tot 10-09 17:26 elke keer twee
# opdrachten, elke keer dezelfde fout. Systeembreed waren 462 van de 1.790
# verwijderopdrachten sinds 25-08 een herhaling van een eerdere, verdeeld over
# vier verkopers.
#
# Dat is niet gratis: elke herhaling opent een tabblad in de browser van de
# verkoper, en schrijvende opdrachten gaan één voor één, dus zijn echte werk
# schuift elke twintig minuten naar achteren. Een vangnet dat blijft proberen is
# geen vangnet meer maar een lopende band; zie de les bij een status die niemand
# afsluit (herplaatsing-laat-oude-rij-staan).
MAX_POGINGEN = 4
# Wachttijd vóór een volgende poging, naar het aantal pogingen dat er al is
# geweest: de eerste mag meteen, daarna een uur, dan vier uur, dan een dag.
# Na MAX_POGINGEN laten we het kanaal met rust; de advertentierij houdt zijn
# foutmelding, dus het staat in het dashboard en de verkoper kan zelf herkansen.
WACHT_UREN = (0, 1, 4, 24)


async def reconcileer_verkochte_artikelen() -> dict:
    db = get_db()
    grens = (datetime.now(timezone.utc) - timedelta(days=TERUGBLIK_DAGEN)).isoformat()
    respijt = datetime.now(timezone.utc) - timedelta(minutes=RESPIJT_MINUTEN)

    try:
        verkocht = ((await naast_de_lus(
            lambda: db.table("listings")
            .select("item_id,platform,sold_at")
            .eq("status", "sold")
            .gte("sold_at", grens)
            .order("sold_at", desc=False)
            .limit(1500)
            .execute(), herkans=True)).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("verkoop-reconciliatie: kon de verkopen niet lezen: %s", e)
        return {"bekeken": 0, "opnieuw_ingezet": 0, "gearchiveerd": 0}

    if not verkocht:
        return {"bekeken": 0, "opnieuw_ingezet": 0, "gearchiveerd": 0}

    # Per artikel: wanneer was de (vroegste) verkoop, en op welke kanalen.
    verkoop_van: dict[str, dict] = {}
    for r in verkocht:
        iid = r.get("item_id")
        if not iid:
            continue
        d = verkoop_van.setdefault(iid, {"sold_at": r.get("sold_at"), "platforms": set()})
        d["platforms"].add(r["platform"])
        if r.get("sold_at") and (not d["sold_at"] or r["sold_at"] < d["sold_at"]):
            d["sold_at"] = r["sold_at"]

    item_ids = list(verkoop_van.keys())

    # Alle advertentierijen van die artikelen ophalen, in brokken (een te lange
    # .in_() maakt een URL die stilletjes wordt geweigerd — zie IN_BROK).
    rijen_per_item: dict[str, list[dict]] = {}
    for i in range(0, len(item_ids), IN_BROK):
        brok = item_ids[i:i + IN_BROK]
        try:
            rows = ((await naast_de_lus(
                lambda: db.table("listings")
                .select("item_id,platform,status,platform_listing_id")
                .in_("item_id", brok).execute(), herkans=True)).data or [])
        except Exception as e:  # noqa: BLE001
            logger.warning("verkoop-reconciliatie: listings-brok overgeslagen: %s", e)
            continue
        for row in rows:
            rijen_per_item.setdefault(row["item_id"], []).append(row)

    # Kandidaten: verkocht op kanaal A, nog levend (of nog onbevestigd) op kanaal
    # B, verkoop oud genoeg.
    kandidaten: list[tuple[str, str]] = []  # (sold_at, item_id) voor sortering
    for iid, info in verkoop_van.items():
        try:
            verkocht_op_dt = datetime.fromisoformat((info["sold_at"] or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            verkocht_op_dt = respijt - timedelta(minutes=1)  # geen datum: behandel als oud
        if verkocht_op_dt > respijt:
            continue
        andere = [r for r in rijen_per_item.get(iid, []) if r["platform"] not in info["platforms"]]
        nog_levend = [r for r in andere if r.get("status") in _NOG_LEVEND]
        onbevestigd = [r for r in andere if r.get("status") == "sold_unconfirmed"]
        if nog_levend or onbevestigd:
            kandidaten.append((info["sold_at"] or "", iid))

    # Wat er al geprobeerd is, per (artikel, kanaal). Eén vraag per brok, niet
    # per artikel: deze ronde draait elke twintig minuten.
    pogingen: dict[tuple[str, str], list[str]] = {}
    kandidaat_ids = [iid for _, iid in kandidaten]
    for i in range(0, len(kandidaat_ids), IN_BROK):
        brok = kandidaat_ids[i:i + IN_BROK]
        try:
            rows = ((await naast_de_lus(
                lambda b=brok: db.table("jobs")
                .select("item_id,platform,created_at")
                .eq("action", "delete").in_("item_id", b)
                .gte("created_at", grens).execute(), herkans=True)).data or [])
        except Exception as e:  # noqa: BLE001
            logger.warning("verkoop-reconciliatie: kon eerdere pogingen niet lezen: %s", e)
            rows = []
        for r in rows:
            if r.get("item_id") and r.get("platform"):
                pogingen.setdefault((r["item_id"], r["platform"]), []).append(
                    r.get("created_at") or "")

    nu = datetime.now(timezone.utc)

    def _tijd(waarde) -> datetime | None:
        try:
            t = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

    def _mag_opnieuw(iid: str, platform: str) -> bool:
        # Alleen de pogingen NA de verkoop tellen mee. Een verwijderopdracht van
        # daarvoor hoort bij iets anders (een herplaatsing, een handmatige
        # afmelding) en mag dit vangnet niet vooraf opgebruiken.
        verkocht_op = _tijd((verkoop_van.get(iid) or {}).get("sold_at"))
        eerder = sorted(
            t for t in (_tijd(x) for x in pogingen.get((iid, platform), []))
            if t is not None and (verkocht_op is None or t >= verkocht_op)
        )
        if len(eerder) >= MAX_POGINGEN:
            return False
        if not eerder:
            return True
        wacht = WACHT_UREN[min(len(eerder), len(WACHT_UREN) - 1)]
        if wacht <= 0:
            return True
        return nu - eerder[-1] >= timedelta(hours=wacht)

    def _levende_kanalen(iid: str) -> set[str]:
        return {r["platform"] for r in rijen_per_item.get(iid, [])
                if r.get("status") in _NOG_LEVEND
                and r["platform"] not in verkoop_van[iid]["platforms"]}

    # Artikelen waar élk nog-levend kanaal zijn pogingen erop heeft zitten (of
    # nog moet wachten) gaan er hier uit, zodat ze de PER_RONDE-plekken niet
    # opeten van artikelen die wél een poging verdienen.
    binnen_budget: list[tuple[str, str]] = []
    overgeslagen = 0
    for sold_at, iid in kandidaten:
        kanalen = _levende_kanalen(iid)
        if not kanalen or any(_mag_opnieuw(iid, p) for p in kanalen):
            binnen_budget.append((sold_at, iid))
        else:
            overgeslagen += 1
    kandidaten = binnen_budget

    kandidaten.sort()
    kandidaten = kandidaten[:PER_RONDE]

    if not kandidaten:
        if overgeslagen:
            logger.info("verkoop-reconciliatie: %d artikel(en) overgeslagen, hun kanalen "
                        "hebben hun pogingen erop zitten", overgeslagen)
        return {"bekeken": len(item_ids), "opnieuw_ingezet": 0, "gearchiveerd": 0,
                "overgeslagen": overgeslagen}

    # Eigenaren erbij zoeken (delist_all_platforms wil het user_id).
    doel_ids = [iid for _, iid in kandidaten]
    eigenaar: dict[str, str] = {}
    for i in range(0, len(doel_ids), IN_BROK):
        brok = doel_ids[i:i + IN_BROK]
        rows = ((await naast_de_lus(
            lambda: db.table("items").select("id,user_id").in_("id", brok).execute(),
            herkans=True)).data or [])
        for row in rows:
            eigenaar[row["id"]] = row["user_id"]

    from backend.services.crosslist import delist_all_platforms

    opnieuw = 0
    gearchiveerd = 0
    for _, iid in kandidaten:
        uid = eigenaar.get(iid)
        if not uid:
            continue
        andere = [r for r in rijen_per_item.get(iid, [])
                  if r["platform"] not in verkoop_van[iid]["platforms"]]
        levend = [r["platform"] for r in andere if r.get("status") in _NOG_LEVEND]

        # Onbevestigde-verkoop-rijen op een ander kanaal: de verkoop staat al
        # elders vast (harde bron of eerder bevestigd), dus de vraag hoeft niet
        # meer. Rechtstreeks archiveren.
        for r in andere:
            if r.get("status") == "sold_unconfirmed":
                try:
                    (await naast_de_lus(lambda rr=r: db.table("listings").update(
                        {"status": "delisted", "error_message": None}).eq("id", rr["id"]).execute()))
                    gearchiveerd += 1
                    logger.info("verkoop-reconciliatie: item %s %s stond op 'mogelijk verkocht' "
                                "terwijl het elders al verkocht is — gearchiveerd", iid, r["platform"])
                except Exception:  # noqa: BLE001
                    pass

        if not levend:
            continue
        toegestaan = {r["platform"] for r in andere
                      if _mag_opnieuw(iid, r["platform"])}
        if not (set(levend) & toegestaan):
            overgeslagen += 1
            continue
        try:
            res = await delist_all_platforms(iid, uid, alleen_platforms=toegestaan)
            opnieuw += 1
            logger.info(
                "verkoop-reconciliatie: item %s was verkocht op %s maar stond nog op %s "
                "— afmelding opnieuw ingezet: %s",
                iid, sorted(verkoop_van[iid]["platforms"]), sorted(set(levend)),
                [(x.get("platform"), x.get("status")) for x in (res or [])],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("verkoop-reconciliatie: item %s afmelden mislukte: %s", iid, e)

    logger.info("verkoop-reconciliatie: %d artikel(en) bekeken, %d opnieuw ingezet, "
                "%d gearchiveerd, %d overgeslagen (pogingen op)",
                len(item_ids), opnieuw, gearchiveerd, overgeslagen)
    return {"bekeken": len(item_ids), "opnieuw_ingezet": opnieuw,
            "gearchiveerd": gearchiveerd, "overgeslagen": overgeslagen}
