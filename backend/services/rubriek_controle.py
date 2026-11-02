"""Staat een advertentie van ons echt in de rubriek waarvoor we hem klaarzetten?

WAAROM DIT ER IS (02-11-2026, Esther van hetisvintastisch)
Op Marktplaats is de rubriek na het plaatsen niet meer te wijzigen. Staat een
advertentie fout, dan moet hij weg en opnieuw. Wie een webshop met honderden
artikelen overzet wil dus weten dat het in een keer goed gaat. Tot nu toe
bewaakte alleen de plaatsing zelf (geen standaardrubriek, een onbekende rubriek
weigert) en keek niets daarna of Marktplaats de advertentie ook echt in die
rubriek heeft gezet. Zo'n stille afwijking zag niemand: Amanda (30-08-2026) kreeg
na een verversing alles in de verkeerde rubriek en kwam het zelf te weten.

HOE ER GEMETEN WORDT
De extensie meldt bij elke plaatsing in welke rubriek ze het formulier opende
(`rubriek: {l1, l2}`, uit het adres /plaats/{l1}/{l2}); bij een herplaatsing
geldt de rubriek uit de opdracht. Deze ronde zoekt de advertentie daarna op
nummer in de openbare zoek-API van Marktplaats/2dehands (geen login nodig),
leest op de advertentiepagina zelf welke rubriek het platform eraan hangt en
vergelijkt. Het resultaat komt in `jobs.result.rubriekcontrole`:
  ok          de advertentie staat in de rubriek die we bedoelden
  afwijkend   ze staat ergens anders; het dashboard meldt het de verkoper
  onbekend    na enkele rondes nog niet terug te vinden of niet te lezen

DE REMMEN
1. Alleen per verkoper uit de database lezen, nooit jobs.result over meerdere
   klanten (de database ging daar twee keer plat van, zie kennisbank).
2. Een leeg antwoord of een weigering is een storing en geen uitspraak: dan staat
   er "onbekend" en blijft de advertentie met rust. Er wordt hier NOOIT iets
   verwijderd of herplaatst; deze ronde meet en meldt alleen.
3. Hoogstens MAX_PER_RONDE advertenties per ronde, en meteen stoppen als
   Marktplaats ons weigert (marktplaats_rem).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus

logger = logging.getLogger(__name__)

ADVERTENTIENUMMER = re.compile(r"^m\d{6,}$")
KANALEN = ("marktplaats", "2dehands")
VENSTER = timedelta(days=3)       # zo lang na het plaatsen kijken we nog
MAX_PER_RONDE = 40
MAX_PER_VERKOPER = 15
MAX_POGINGEN = 12                # 12 rondes = twee uur wachten tot het platform hem toont
WACHT_TUSSEN = 0.6                # seconden tussen twee vragen aan het platform


def verwachte_rubriek(result: dict | None, payload: dict | None) -> dict | None:
    """Welke rubriek we bedoelden: wat de extensie meldde, anders de opdracht."""
    for bron in ((result or {}).get("rubriek"), (payload or {}).get("mp_category")):
        if isinstance(bron, dict):
            try:
                l1, l2 = int(bron.get("l1")), int(bron.get("l2"))
            except (TypeError, ValueError):
                continue
            return {"l1": l1, "l2": l2}
    return None


def beoordeel(verwacht: dict | None, echt: dict | None) -> str:
    """ok / afwijkend / onbekend. Alleen een gelezen rubriek mag 'afwijkend' zeggen.

    Het adres /plaats/{l1}/{l2} noemt soms een rubriek die dieper ligt dan het
    tweede niveau (Steps, Zwembaden: ouder is geen hoofdrubriek). De advertentie
    meldt dan dat diepere nummer als `blad`; ook dat telt als dezelfde rubriek."""
    if not verwacht or not echt:
        return "onbekend"
    try:
        e1, e2 = int(echt.get("l1")), int(echt.get("l2"))
    except (TypeError, ValueError):
        return "onbekend"
    if e1 != verwacht["l1"]:
        return "afwijkend"
    try:
        blad = int(echt.get("blad")) if echt.get("blad") is not None else None
    except (TypeError, ValueError):
        blad = None
    return "ok" if verwacht["l2"] in (e2, blad) else "afwijkend"


async def echte_rubriek(client, platform: str, nummer: str) -> dict | None:
    """De rubriek die het platform zelf aan deze advertentie hangt, of None.

    None betekent: niet kunnen vaststellen (nog niet geïndexeerd, geweigerd,
    pagina onleesbaar). Nooit een gok."""
    from backend.services.mp_enrich import ZOEK_PER_PLATFORM, _pagina, categorie_uit_html

    zoek_url, basis = ZOEK_PER_PLATFORM[platform]
    try:
        r = await client.get(zoek_url, params={"query": nummer, "limit": 5})
        if r.status_code != 200:
            return None
        lijst = r.json().get("listings") or []
    except Exception as e:  # noqa: BLE001 — een gemiste meting mag nooit iets breken
        logger.warning("rubriekcontrole: zoeken naar %s mislukt: %s", nummer, e)
        return None
    gevonden = next((a for a in lijst if a.get("itemId") == nummer), None)
    if not gevonden or not gevonden.get("vipUrl"):
        return None
    html = await _pagina(client, basis + gevonden["vipUrl"])
    rubriek = categorie_uit_html(html)
    if not (rubriek.get("l1") and rubriek.get("l2")):
        return None
    if gevonden.get("categoryId") is not None:
        rubriek["blad"] = gevonden["categoryId"]
    return rubriek


async def _kandidaten(db, user_id: str, platform: str) -> list[dict]:
    """Plaatsingen van één verkoper die nog een controle nodig hebben."""
    grens = (datetime.now(timezone.utc) - VENSTER).isoformat()
    rijen = (await naast_de_lus(lambda: db.table("jobs")
             .select("id,item_id,result,payload->mp_category")
             .eq("user_id", user_id).eq("platform", platform)
             .eq("action", "create").eq("status", "done")
             .gte("done_at", grens).order("done_at", desc=False)
             .limit(300).execute())).data or []
    uit = []
    for rij in rijen:
        res = rij.get("result") if isinstance(rij.get("result"), dict) else {}
        nummer = str(res.get("platform_listing_id") or "")
        if not ADVERTENTIENUMMER.match(nummer):
            continue
        vorige = res.get("rubriekcontrole") or {}
        if vorige.get("status") in ("ok", "afwijkend"):
            continue
        if (vorige.get("pogingen") or 0) >= MAX_POGINGEN:
            continue
        verwacht = verwachte_rubriek(res, {"mp_category": rij.get("mp_category")})
        if not verwacht:
            continue
        uit.append({"job_id": rij["id"], "item_id": rij.get("item_id"), "nummer": nummer,
                    "result": res, "verwacht": verwacht})
    return uit


async def _bewaar(db, kandidaat: dict, status: str, echt: dict | None) -> None:
    res = dict(kandidaat["result"])
    vorige = res.get("rubriekcontrole") or {}
    res["rubriekcontrole"] = {
        "status": status,
        "verwacht": kandidaat["verwacht"],
        "echt": ({k: echt.get(k) for k in ("l1", "l2", "l1_naam", "l2_naam", "blad")}
                 if echt else None),
        "pogingen": (vorige.get("pogingen") or 0) + 1,
        "gecontroleerd_op": datetime.now(timezone.utc).isoformat(),
    }
    await naast_de_lus(lambda: db.table("jobs").update({"result": res})
                       .eq("id", kandidaat["job_id"]).execute())


async def controleer_rubrieken() -> dict:
    """Eén ronde. Geeft tellingen terug zodat een test ze kan nalopen."""
    import httpx
    from backend.services import marktplaats_rem
    from backend.services.mp_enrich import UA

    db = get_db()
    telling = {"ok": 0, "afwijkend": 0, "onbekend": 0}
    over = MAX_PER_RONDE
    for platform in KANALEN:
        if over <= 0:
            break
        gekoppeld = [r.get("user_id") for r in ((await naast_de_lus(
            lambda p=platform: db.table("platform_credentials").select("user_id")
            .eq("platform", p).execute())).data or [])]
        async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=30,
                                     follow_redirects=True) as client:
            for user_id in gekoppeld:
                if over <= 0:
                    break
                if marktplaats_rem.dicht():
                    logger.info("rubriekcontrole: %s weigert ons, ronde gestopt", platform)
                    return telling
                try:
                    kandidaten = (await _kandidaten(db, user_id, platform))[:MAX_PER_VERKOPER]
                except Exception as e:  # noqa: BLE001
                    logger.warning("rubriekcontrole: kandidaten van %s niet gelezen: %s", user_id, e)
                    continue
                for k in kandidaten:
                    if over <= 0 or marktplaats_rem.dicht():
                        break
                    over -= 1
                    echt = await echte_rubriek(client, platform, k["nummer"])
                    status = beoordeel(k["verwacht"], echt)
                    await _bewaar(db, k, status, echt)
                    telling[status] += 1
                    if status == "afwijkend":
                        logger.warning(
                            "rubriekcontrole: AFWIJKING %s %s van %s: bedoeld %s, staat in %s",
                            platform, k["nummer"], user_id, k["verwacht"],
                            {x: echt.get(x) for x in ("l1", "l1_naam", "l2", "l2_naam")})
                    await asyncio.sleep(WACHT_TUSSEN)
    if any(telling.values()):
        logger.info("rubriekcontrole: %s", telling)
    return telling


async def afwijkingen_voor(db, user_id: str) -> list[dict]:
    """Voor het dashboard: advertenties van deze verkoper in een andere rubriek."""
    grens = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    rijen = (await naast_de_lus(lambda: db.table("jobs")
             .select("id,platform,item_id,result")
             .eq("user_id", user_id).eq("action", "create").eq("status", "done")
             .in_("platform", list(KANALEN)).gte("done_at", grens)
             .order("done_at", desc=True).limit(500).execute())).data or []
    uit = []
    for rij in rijen:
        res = rij.get("result") if isinstance(rij.get("result"), dict) else {}
        controle = res.get("rubriekcontrole") or {}
        if controle.get("status") != "afwijkend":
            continue
        uit.append({
            "job_id": rij["id"], "platform": rij["platform"], "item_id": rij.get("item_id"),
            "advertentie": res.get("platform_listing_id"),
            "url": res.get("platform_listing_url"),
            "verwacht": controle.get("verwacht"), "echt": controle.get("echt"),
        })
    ids = [u["item_id"] for u in uit if u["item_id"]]
    if ids:
        titels = {r["id"]: r.get("title") for r in ((await naast_de_lus(
            lambda: db.table("items").select("id,title").in_("id", ids[:100]).execute()
        )).data or [])}
        for u in uit:
            u["titel"] = titels.get(u["item_id"])
    return uit
