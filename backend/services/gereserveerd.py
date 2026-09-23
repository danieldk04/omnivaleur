"""Een advertentie die het platform zelf op "gereserveerd" zet, wordt de verkoopvraag.

WAAROM DIT ER IS (23-09-2026, De Juiste Toon)

Toon: "Ik zie dat er Lederhosen die verkocht worden op marktplaats op
gereserveerd komen te staan. En op de Belg gebeurt dat niet, loopt dat niet
door." Klopt. Verkoopt hij via Marktplaats, dan zet Marktplaats de advertentie
zelf op gereserveerd. Wij zagen dat nergens:

- de verkoopcontrole op de server (polling.py) slaat hem over, want hij heeft
  geen koppeling, en zoekt bovendien alleen naar "verkocht";
- het groene "Verkocht!"-labeltje in zijn berichten koppelen we aan "(1308)"
  vooraan de titel, en dat heeft geen van zijn artikelen;
- de extensie meldde bij hem nog nooit één gereserveerde advertentie.

Gemeten die ochtend: zes lederhosen gereserveerd op Marktplaats, alle zes bij
ons nog "live", vijf daarvan nog te koop op 2dehands en alle zes op Vinted. En
één stond klaar om die dag opnieuw geplaatst te worden, als te koop.

HOE ER GEMETEN WORDT
De openbare zoek-API geeft per advertentie `reserved: true/false`. Geen login,
geen Chrome: dezelfde lijst die de fotocontrole al leest (foto_controle.py).
Die bewijst het verkopersnummer met een van onze eigen advertentienummers en
geeft het hier door; deze ronde leest de lijst daarna elk uur opnieuw.

WAT ER GEBEURT
- Gereserveerd: de advertentie wordt de bestaande vraag "is dit verkocht?" in
  het dashboard. Ja = overal af, precies als de Sold-knop. Een klaargezette
  herplaatsing van dat artikel wordt teruggenomen: die zou de gereserveerde
  advertentie weghalen en hem als te koop terugzetten.
- Reservering weer weg en nog niemand geantwoord: de vraag verdwijnt vanzelf,
  de advertentie is gewoon weer live.
- "Nee" op de vraag: de advertentie blijft live en deze reservering wordt niet
  opnieuw gevraagd (zie listings.answer_possibly_sold).

Een vraag, geen automatische afmelding: een reservering kan de verkoper ook met
de hand zetten voor een koper die morgen komt, en dan kan de koop nog afketsen.
Zie de kennisbank, "verkoopsignaal hard vs zacht".
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from backend.database import get_db, naast_de_lus

logger = logging.getLogger(__name__)

# Staat ineens een groot deel van één lijst op gereserveerd, dan is het veld
# omgedoopt of anders gaan betekenen, en is dat geen uitverkoop. Toon had er op
# 23-09-2026 zes op 1096.
TE_VEEL_AANTAL = 15
TE_VEEL_AANDEEL = 0.25

# Welke verkoper bij welk verkopersnummer hoort, bewezen door de fotocontrole.
# Na een herstart is dit leeg tot de eerste fotoronde (tien minuten na de start),
# en die ronde kijkt de reserveringen zelf ook na.
_verkopers: dict[tuple[str, str], int] = {}


def onthoud_verkoper(user_id: str, platform: str, verkoper_id: int) -> None:
    _verkopers[(user_id, platform)] = verkoper_id


def _redenen() -> tuple[str, str]:
    from backend.api.listings import VERDENKING_REDENEN, GERESERVEERD_NEE
    return VERDENKING_REDENEN["gereserveerd"], GERESERVEERD_NEE


def gereserveerd_beslissing(op_nummer: dict, onze: list[dict],
                            reden: str, nee: str) -> tuple[list[dict], list[dict], list[dict], bool]:
    """Wat er met onze rijen moet gebeuren, gegeven de openbare lijst.

    `onze` zijn onze advertentierijen van deze verkoper op dit kanaal die ertoe
    doen: de gereserveerde nummers, en de rijen die al een reserveringsvraag of
    -nee dragen. Geeft (vragen, vraag_intrekken, nee_vergeten, te_veel).

    Alleen wat we op de lijst ZIEN telt. Ontbreekt een nummer, dan zegt dat hier
    niets: dat is de verdwenen-controle van foto_controle.py.
    """
    gereserveerd = {nr for nr, a in op_nummer.items() if (a or {}).get("reserved") is True}
    te_veel = (len(gereserveerd) > TE_VEEL_AANTAL
               and len(gereserveerd) / max(1, len(op_nummer)) > TE_VEEL_AANDEEL)
    vragen, intrekken, vergeten = [], [], []
    for r in onze:
        nr = r.get("platform_listing_id")
        if nr not in op_nummer:
            continue
        status, melding = r.get("status"), r.get("error_message")
        if nr in gereserveerd:
            if status in ("active", "relisting") and melding != nee:
                vragen.append(r)
        elif status == "sold_unconfirmed" and melding == reden:
            intrekken.append(r)
        elif status == "active" and melding == nee:
            vergeten.append(r)
    return (([] if te_veel else vragen), intrekken, vergeten, te_veel)


def _neem_herplaatsingen_terug(db, user_id: str, item_id: str, platform: str) -> int:
    """Klaargezette herplaatsingen van dit artikel terugnemen, op elk kanaal.

    Een herplaatsing haalt de advertentie weg en zet hem opnieuw als te koop.
    Bij een gereserveerd artikel is dat precies wat niet mag. Een losse plaatsing
    op het gereserveerde kanaal zelf ook niet: daar staat hij al.
    """
    from backend.api.jobs import _neem_herplaatsing_terug
    nu = datetime.now(timezone.utc).isoformat()
    reden = "Niet opnieuw geplaatst: dit artikel staat als gereserveerd op het platform."
    geraakt = 0
    for job in (db.table("jobs").select("id,user_id,item_id,platform,created_at,payload")
                .eq("user_id", user_id).eq("item_id", item_id)
                .eq("action", "delete").eq("status", "pending")
                .execute().data or []):
        if (job.get("payload") or {}).get("_refresh_rollback"):
            _neem_herplaatsing_terug(db, job, nu, reden)
            geraakt += 1
    for job in (db.table("jobs").select("id")
                .eq("user_id", user_id).eq("item_id", item_id).eq("platform", platform)
                .eq("action", "create").eq("status", "pending")
                .execute().data or []):
        db.table("jobs").update({"status": "cancelled", "result": {"cancelled": reden},
                                 "done_at": nu}).eq("id", job["id"]).execute()
        geraakt += 1
    return geraakt


def _onze_rijen(db, user_id: str, platform: str, nummers: list[str],
                reden: str, nee: str) -> list[dict]:
    """Alleen de rijen die ertoe doen, en alleen van deze ene verkoper."""
    kolommen = "id,item_id,platform_listing_id,status,error_message,items!inner(user_id)"
    basis = (lambda: db.table("listings").select(kolommen)
             .eq("platform", platform).eq("items.user_id", user_id))
    rijen: dict[str, dict] = {}
    for i in range(0, len(nummers), 100):
        for r in (basis().in_("platform_listing_id", nummers[i:i + 100])
                  .in_("status", ["active", "relisting"]).execute().data or []):
            rijen[r["id"]] = r
    for status, melding in (("sold_unconfirmed", reden), ("active", nee)):
        for r in (basis().eq("status", status).eq("error_message", melding)
                  .execute().data or []):
            rijen[r["id"]] = r
    return list(rijen.values())


async def verwerk_lijst(db, user_id: str, platform: str, op_nummer: dict) -> int:
    """Eén openbare verkoperslijst naast onze boeken leggen. Geeft het aantal nieuwe vragen."""
    from backend.services.instellingen import verkoopvraag_aan
    reden, nee = _redenen()
    # Wie de vraag uit heeft staan verkoopt nieuwe voorraad, geen unica: een
    # reservering op één kanaal zegt dan niets over de andere. Niets doen.
    if not await naast_de_lus(lambda: verkoopvraag_aan(user_id)):
        return 0
    nummers = sorted(nr for nr, a in op_nummer.items() if (a or {}).get("reserved") is True)
    onze = await naast_de_lus(lambda: _onze_rijen(db, user_id, platform, nummers, reden, nee))
    vragen, intrekken, vergeten, te_veel = gereserveerd_beslissing(op_nummer, onze, reden, nee)
    if te_veel:
        logger.error("gereserveerd: %s van %s advertenties van %s op %s gereserveerd. Dat is "
                     "een meetfout, geen uitverkoop; er wordt niets gevraagd.",
                     len(nummers), len(op_nummer), user_id, platform)
    nu = datetime.now(timezone.utc).isoformat()
    for r in vragen:
        await naast_de_lus(lambda rr=r: db.table("listings").update(
            {"status": "sold_unconfirmed", "error_message": reden, "last_checked": nu})
            .eq("id", rr["id"]).in_("status", ["active", "relisting"]).execute())
        try:
            weg = await naast_de_lus(lambda rr=r: _neem_herplaatsingen_terug(
                db, user_id, rr["item_id"], platform))
            if weg:
                logger.warning("gereserveerd: %s klaargezette opdracht(en) voor %s teruggenomen",
                               weg, r["item_id"])
        except Exception as e:  # noqa: BLE001 — de vraag staat er al, dat is het belangrijkste
            logger.error("gereserveerd: herplaatsing van %s niet teruggenomen: %s", r["item_id"], e)
    for r in intrekken:
        await naast_de_lus(lambda rr=r: db.table("listings").update(
            {"status": "active", "error_message": None, "last_checked": nu})
            .eq("id", rr["id"]).eq("status", "sold_unconfirmed").execute())
    for r in vergeten:
        await naast_de_lus(lambda rr=r: db.table("listings").update({"error_message": None})
                           .eq("id", rr["id"]).eq("status", "active").execute())
    if vragen or intrekken:
        logger.warning("gereserveerd: %s van %s op %s nu als vraag, %s vraag/vragen ingetrokken "
                       "(reservering vervallen)", len(vragen), user_id, platform, len(intrekken))
    return len(vragen)


async def controleer_gereserveerd() -> int:
    """Elk uur: de lijsten van de verkopers die de fotocontrole al heeft bewezen."""
    import httpx
    from backend.services.foto_controle import _verkoperslijst
    from backend.services.mp_enrich import ZOEK_PER_PLATFORM, UA

    db = get_db()
    gevraagd = 0
    for (user_id, platform), verkoper_id in list(_verkopers.items()):
        zoek_url, basis = ZOEK_PER_PLATFORM[platform]
        try:
            async with httpx.AsyncClient(base_url=basis, headers={"User-Agent": UA},
                                         timeout=30, follow_redirects=True) as client:
                lijst, _ = await _verkoperslijst(client, zoek_url, verkoper_id)
            if lijst:
                gevraagd += await verwerk_lijst(db, user_id, platform,
                                                {a.get("itemId"): a for a in lijst})
        except Exception as e:  # noqa: BLE001 — één verkoper mag de rest niet stoppen
            logger.error("gereserveerd: %s op %s mislukte: %s", user_id, platform, e)
        await asyncio.sleep(1)
    return gevraagd
