"""Staat er een advertentie van ons online zonder foto? Dan halen we hem terug.

WAAROM DIT ER IS (13-09-2026, De Juiste Toon)

Toon stuurde "Originele Lederhosen XXXL maat 60" door met één zin erachter:
"Bovenstaande link heeft geen foto's". Het artikel had er dertien. Hetzelfde
gold voor "Konijnenvacht Setje bruin" met vijf. Een advertentie zonder foto
wordt op Marktplaats niet aangeklikt, dus die twee stonden er wel, maar
verkochten niets.

De oorzaak zit in de extensie en is daar gerepareerd (1.0.323): mislukt of hangt
de upload naar Marktplaats, dan houdt het formulier nul foto's vast, en tot nu
toe werd er dan toch op Plaatsen geklikt. Dat alleen is niet genoeg. Een nieuwe
extensieversie moet eerst door de Chrome Web Store, en dat duurt weken; in die
weken draait bij elke verkoper nog de oude kopie. Daarom kijkt de server het
zelf na, want dit is precies het soort stilte dat niemand meldt: de verkoper
ziet een groen vinkje en de advertentie staat er ook echt, alleen kaal.

HOE ER GEMETEN WORDT
De openbare zoek-API van Marktplaats/2dehands toont per advertentie de foto's
die het platform zelf heeft. Geen login nodig, en het is de waarheid van de
bezoeker in plaats van die van onze eigen administratie. Het verkopersnummer
halen we uit een titelzoekopdracht op één van ONZE eigen advertentienummers, dus
nooit uit een gok: een verkeerd nummer zou de lijst van een vreemde opleveren en
al zijn advertenties als "zonder foto" aanmerken.

WAT ER GEBEURT ALS ER EEN GEVONDEN WORDT
Herplaatsen langs refresh_listing: eerst weg, dan opnieuw, met de rem en het
dagquotum die daar al op zitten. Nooit zelf iets weghalen.

DE VIER REMMEN
1. Een lege lijst is een storing, geen uitspraak. Komt de lijst leeg terug of is
   het verkopersnummer niet te bewijzen, dan gebeurt er niets.
2. Alleen advertenties die we ECHT op zijn lijst terugvinden tellen mee. Staat
   een advertentie er niet tussen, dan is dat een ander verhaal (verwijderd,
   hernummerd) en niet aan deze ronde.
3. Alleen als wij zelf foto's hebben om mee terug te komen. Zonder foto's bij
   ons levert herplaatsen dezelfde kale advertentie op.
4. Hoogstens twee reparaties per advertentie, geteld aan de plaatsopdrachten die
   zijn klaargezet ná het moment waarop dit advertentienummer binnenkwam — dus
   zonder de plaatsing die de advertentie zelf maakte. Een vangnet zonder
   geheugen wordt een lus, en dat is hier duur: elke poging haalt een echte
   advertentie weg. Blijft hij daarna kaal, dan zegt het logboek "met de hand
   nakijken" in plaats van het nog eens te proberen.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from backend.database import get_db, fetch_all, naast_de_lus

logger = logging.getLogger(__name__)

# Alleen echte advertentienummers van Marktplaats/2dehands. Een Admarkt- of
# webwinkelnummer staat niet op de openbare verkoperslijst en zou hier eeuwig
# als "niet teruggevonden" langskomen.
ADVERTENTIENUMMER = re.compile(r"^m\d{6,}$")

MAX_HERSTEL_PER_RONDE = 10      # per ronde, over alle verkopers samen
MAX_POGINGEN = 2                # reparaties per advertentienummer
LUS_GRENS = 3                   # plaatsingen in POGING_VENSTER: daarboven is het een lus
POGING_VENSTER = timedelta(days=14)
PAGINAS_PER_VERKOPER = 60       # 100 advertenties per pagina


def _tijd(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _fotos(advertentie: dict) -> list:
    return (advertentie.get("pictures")
            or advertentie.get("imageUrls")
            or advertentie.get("thumbsUrls")
            or [])


async def _verkopersnummer(client, zoek_url: str, onze: list[dict]) -> int | None:
    """Het verkopersnummer, bewezen via een van onze eigen advertentienummers.

    Niet geraden en niet gestemd: we zoeken op onze eigen titel en nemen het
    nummer alleen over als de gevonden advertentie HET nummer draagt dat bij ons
    in de boeken staat. Dat kan niet per ongeluk iemand anders zijn.
    """
    from backend.services.mp_enrich import _json
    for rij in onze[:25]:
        if not rij.get("titel"):
            continue
        try:
            data = await _json(client, zoek_url, {"query": rij["titel"], "limit": 30})
        except Exception as e:                       # zoek-API plat: geen uitspraak
            logger.info("fotocontrole: zoeken op '%s' mislukte: %s", rij["titel"][:40], e)
            continue
        for gevonden in (data.get("listings") or []):
            if gevonden.get("itemId") == rij["platform_listing_id"]:
                return ((gevonden.get("sellerInformation") or {}).get("sellerId"))
        await asyncio.sleep(0.7)
    return None


async def _verkoperslijst(client, zoek_url: str, verkoper_id: int) -> list[dict]:
    from backend.services.mp_enrich import _json, PAGINA
    uit: list[dict] = []
    for pagina in range(PAGINAS_PER_VERKOPER):
        try:
            data = await _json(client, zoek_url, {"sellerIds[]": verkoper_id,
                                                  "limit": PAGINA,
                                                  "offset": pagina * PAGINA})
        except Exception as e:
            logger.info("fotocontrole: verkoperslijst %s brak af op pagina %s: %s",
                        verkoper_id, pagina, e)
            # Halve lijst is geen lijst: wat we niet zagen mag niet als "zonder
            # foto" of als "weg" tellen.
            return []
        rijen = data.get("listings") or []
        uit += rijen
        if not rijen or len(uit) >= (data.get("totalResultCount") or 0):
            break
        await asyncio.sleep(0.8)
    return uit


async def _pogingen_op(db, item_id: str, platform: str, nummer: str) -> int:
    """Hoe vaak is er al een reparatie geprobeerd sinds DIT advertentienummer er is?

    TEL NIET DE PLAATSING DIE DE ADVERTENTIE ZELF MAAKTE.

    Eerst stond hier een vast venster van veertien dagen. Dat telde ook de
    opdracht mee die de advertentie überhaupt online zette, plus een eventueel
    afgebroken poging daarvoor — en dan was het budget op vóór er ook maar één
    reparatie was gedaan. De proefronde liet dat meteen zien: de lederhosen kreeg
    "blijft zonder foto na 2 pogingen" terwijl er nul reparaties waren geweest.
    Het startmoment van de advertentierij helpt ook niet: die rij wordt al
    aangemaakt als de opdracht wordt weggeschreven, dus hij valt op de
    microseconde samen met de opdracht die hem vult.

    Het ijkpunt dat wél klopt is het moment waarop DIT nummer binnenkwam: de
    afronding van de plaatsopdracht die dit advertentienummer opleverde. Alles
    wat daarna is klaargezet is een reparatie. Is die opdracht niet meer te
    vinden (opgeruimd), dan valt de teller terug op het venster.
    """
    opdrachten = ((await naast_de_lus(lambda: db.table("jobs")
                   .select("created_at,done_at,result")
                   .eq("item_id", item_id).eq("platform", platform)
                   .eq("action", "create")
                   .order("created_at")
                   .execute())).data or [])
    ijkpunt = None
    for j in opdrachten:
        res = j.get("result") if isinstance(j.get("result"), dict) else {}
        if str(res.get("platform_listing_id") or "") == str(nummer):
            ijkpunt = _tijd(j.get("done_at") or j.get("created_at"))
    if ijkpunt is None:
        ijkpunt = datetime.now(timezone.utc) - POGING_VENSTER
    sinds_dit_nummer = len([j for j in opdrachten
                            if (_tijd(j.get("created_at")) or ijkpunt) > ijkpunt])

    # DE TWEEDE REM, DIE EEN HERNUMMERING OVERLEEFT.
    #
    # De teller hierboven telt vanaf het huidige advertentienummer. Slaagt een
    # reparatie, dan krijgt de advertentie een NIEUW nummer en begint die teller
    # dus weer bij nul. Komt de nieuwe advertentie opnieuw kaal online — precies
    # het geval waar dit vangnet voor is — dan zou deze ronde elke zes uur
    # opnieuw een echte advertentie weghalen en terugzetten, zonder eind.
    #
    # Daarom telt dit er een tweede keer overheen, zonder ijkpunt: hoeveel
    # plaatsingen heeft dit artikel op dit kanaal in veertien dagen gehad? Bij
    # normaal gedrag is dat er hooguit één (automatisch herplaatsen staat op
    # ordes van weken). Drie of meer is geen onderhoud meer maar een lus.
    venster = datetime.now(timezone.utc) - POGING_VENSTER
    in_venster = len([j for j in opdrachten
                      if (_tijd(j.get("created_at")) or venster) > venster])
    return max(sinds_dit_nummer, MAX_POGINGEN if in_venster >= LUS_GRENS else 0)


async def controleer_fotos_op_advertenties():
    """Eén ronde langs de openbare verkoperslijsten."""
    import httpx
    from backend.services.mp_enrich import ZOEK_PER_PLATFORM, UA

    db = get_db()
    hersteld = 0
    for platform in ("marktplaats", "2dehands"):
        adressen = ZOEK_PER_PLATFORM.get(platform)
        if not adressen:
            continue
        zoek_url, basis = adressen

        # PAGINEREN, ANDERS MEET JE EEN FRAGMENT.
        #
        # Een gewone select geeft er hooguit duizend terug en zegt daar niets
        # over. Met 9.160 actieve Marktplaats-advertenties zou deze ronde dus
        # over een negende van de voorraad een uitspraak doen en over de rest
        # zwijgen — precies het soort lege uitkomst dat op "niets aan de hand"
        # lijkt. Zie fetch_all in backend/database.py.
        rijen = await naast_de_lus(lambda p=platform: fetch_all(
            lambda: db.table("listings")
            .select("item_id,platform_listing_id,items(user_id,title,photo_urls)")
            .eq("platform", p).eq("status", "active")
            .not_.is_("platform_listing_id", "null"),
            order_by="id"))
        per_verkoper: dict[str, list[dict]] = {}
        for r in rijen:
            item = r.get("items") or {}
            if not ADVERTENTIENUMMER.match(str(r.get("platform_listing_id") or "")):
                continue
            per_verkoper.setdefault(item.get("user_id"), []).append({
                "item_id": r["item_id"],
                "platform_listing_id": r["platform_listing_id"],
                "titel": item.get("title"),
                "fotos_bij_ons": len(item.get("photo_urls") or []),
            })
        per_verkoper.pop(None, None)
        if not per_verkoper:
            continue

        async with httpx.AsyncClient(base_url=basis, headers={"User-Agent": UA},
                                     timeout=30, follow_redirects=True) as client:
            for user_id, onze in per_verkoper.items():
                if hersteld >= MAX_HERSTEL_PER_RONDE:
                    break
                verkoper_id = await _verkopersnummer(client, zoek_url, onze)
                if not verkoper_id:
                    logger.info("fotocontrole: %s op %s — verkopersnummer niet te "
                                "bewijzen, geen uitspraak", user_id, platform)
                    continue
                lijst = await _verkoperslijst(client, zoek_url, verkoper_id)
                if not lijst:
                    logger.info("fotocontrole: lege verkoperslijst voor %s (%s) — "
                                "dat is een storing, geen uitspraak", user_id, verkoper_id)
                    continue

                op_nummer = {a.get("itemId"): a for a in lijst}
                zonder = [r for r in onze
                          if r["platform_listing_id"] in op_nummer
                          and not _fotos(op_nummer[r["platform_listing_id"]])]
                if not zonder:
                    continue
                logger.warning("fotocontrole: %s advertentie(s) van %s staan zonder foto "
                               "op %s", len(zonder), user_id, platform)

                for rij in zonder:
                    if hersteld >= MAX_HERSTEL_PER_RONDE:
                        break
                    if not rij["fotos_bij_ons"]:
                        logger.info("fotocontrole: %s overgeslagen — wij hebben zelf geen "
                                    "foto's, herplaatsen levert dezelfde kale advertentie",
                                    rij["platform_listing_id"])
                        continue
                    if await _pogingen_op(db, rij["item_id"], platform,
                                          rij["platform_listing_id"]) >= MAX_POGINGEN:
                        logger.warning("fotocontrole: %s (%s) blijft zonder foto na %s "
                                       "pogingen — met de hand nakijken",
                                       rij["platform_listing_id"], rij["titel"], MAX_POGINGEN)
                        continue
                    from backend.services.relist import refresh_listing, RefreshError
                    try:
                        await refresh_listing(rij["item_id"], platform, user_id,
                                              "relist", eigen_quotum=True)
                        hersteld += 1
                        logger.warning("fotocontrole: %s (%s) opnieuw ingepland — stond "
                                       "zonder foto online terwijl wij er %s hebben",
                                       rij["platform_listing_id"], rij["titel"],
                                       rij["fotos_bij_ons"])
                    except RefreshError as e:
                        logger.info("fotocontrole: %s nog niet herplaatst: %s",
                                    rij["platform_listing_id"], e)
                    except Exception as e:
                        logger.error("fotocontrole: herplaatsen van %s mislukte: %s",
                                     rij["platform_listing_id"], e)

    if hersteld:
        logger.warning("fotocontrole: %s advertentie(s) zonder foto opnieuw ingepland", hersteld)
    return hersteld
