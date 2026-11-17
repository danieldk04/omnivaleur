"""
Lege rubrieken van nieuwe artikelen invullen, twintig tegelijk.

WAAROM DIT BESTAAT (17-11-2026, gemeten).

Een nieuwe klant (info@hetisvintastisch.nl) las 294 artikelen in, en 267 kwamen
zonder rubriek binnen. Zonder rubriek weigeren Marktplaats en 2dehands een
artikel, dus hij kon niets plaatsen en vroeg om hulp. Oorzaak: de rubriekvraag
ging één artikel per vraag naar de gratis Google-sleutel, die elke dag binnen
een paar honderd vragen op is (HTTP 429 op alle modellen), en Claude staat voor
rubrieken bewust uit sinds 09-10 ("echt veel te duur", ~17 dollar per dag).

Het mechanisme van die kosten: elke vraag draagt de hele rubriekenlijst mee,
ruim 8.000 tokens, voor één artikel. Gemeten op 214 echte artikelen met Haiku:

    één vraag per artikel     $0,0095 per artikel
    twintig per vraag         $0,0004 per artikel   (22x goedkoper)

De rubriekenlijst gaat dan één keer mee voor twintig artikelen, en staat in de
vaste systeemtekst zodat Claude hem tussen vragen onthoudt. Kwaliteit gelijk:
op dezelfde 40 artikelen kwam de groepsvraag in 26 van 40 op hetzelfde als de
enkele vraag, en dezelfde tak (wonen, antiek, kleding, enz.) in 86 tot 90%.
Wat verschilt is meestal een smaakkwestie (vintage wandlamp: wonen of antiek).
Met 600 tekens omschrijving per artikel was de uitkomst niet slechter dan met
1.500, dus 600. Veertig per vraag gaf meer mislukkingen (9 tegen 3 tot 5), dus
twintig.

Een 294-artikelen-import kost daarmee ongeveer 13 cent.

DRIE DINGEN DIE HIER BEWUST ZO ZIJN:

1. Dezelfde regels als de enkele vraag (imports._bouw_rubrieksprompt), en
   dezelfde controles: een rubriek buiten de lijst telt niet, "low" telt niet,
   "none" (past in geen tak) blijft leeg, schoenen in een niet-schoenrubriek
   blijven leeg.
2. Een dagplafond (DAGMAX_ARTIKELEN) als noodrem. De teller loopt per proces.
3. Alleen lege velden worden gevuld, en de schrijfactie herhaalt de eis dat de
   rubriek nog leeg is. Een artikel dat de verkoper tussendoor zelf indeelde,
   wordt nooit overschreven.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.database import get_db

logger = logging.getLogger(__name__)

GROEP = 20                 # artikelen per vraag (gemeten: 40 gaf meer mislukkingen)
OMSCHRIJVING_TEKENS = 600  # gemeten: niet slechter dan 1.500
DAGMAX_ARTIKELEN = 3000    # ~$1,20 per dag aan Claude, noodrem
TERUGKIJKEN_UREN = 72      # alleen artikelen van de laatste drie dagen
PER_RONDE = 400
GELIJKTIJDIG = 2

_DAG: dict = {"dag": None, "n": 0}

_SLOT = (
    'Respond with ONLY a JSON array with exactly one object per listing, in order: '
    '[{"n":1,"gender":"...","category":"...","confidence":"high|medium|low"}, ...]. '
    "Judge every listing on its own."
)


def _ruimte(aantal: int) -> bool:
    vandaag = datetime.now(timezone.utc).date()
    if _DAG["dag"] != vandaag:
        _DAG["dag"], _DAG["n"] = vandaag, 0
    if _DAG["n"] + aantal > DAGMAX_ARTIKELEN:
        return False
    _DAG["n"] += aantal
    return True


def _systeemtekst() -> str:
    """Kop en regels van de enkele vraag, zonder het ene artikel. Bij elke
    wijziging van de regels in imports.py verandert dit vanzelf mee."""
    from backend.api import imports as I
    p = I._bouw_rubrieksprompt("x", "x", "x")
    kop = p[:p.index("Brand:")]
    regels = p[p.index("Pick the single best"):]
    regels = regels.rsplit("Respond with ONLY JSON", 1)[0]
    return kop + regels + _SLOT


def _gebruikertekst(groep: list[dict]) -> str:
    return "\n\n".join(
        f"[{k + 1}] Brand: {x.get('brand') or 'unknown'}\n"
        f"Title: {x.get('title') or ''}\n"
        f"Description: {(x.get('description') or '')[:OMSCHRIJVING_TEKENS]}"
        for k, x in enumerate(groep))


def _vraag_claude(systeem: str, gebruiker: str, n: int) -> str:
    """Eén groepsvraag aan Haiku. Synchroon; de aanroeper zet hem in een werkdraad."""
    import anthropic
    from backend.services.taalmodel import HAIKU
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60)
    bericht = client.messages.create(
        model=HAIKU, max_tokens=60 * n + 100,
        system=[{"type": "text", "text": systeem,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": gebruiker}])
    return "".join(getattr(b, "text", "") or "" for b in (bericht.content or []))


def _lees_antwoord(raw: str, groep: list[dict]) -> dict[str, dict]:
    """{item_id: {'gender','category'} of {'geen_tak': True}} voor wat telt.
    Een artikel dat ontbreekt in het antwoord of niet telt, staat er niet in."""
    from backend.api import imports as I
    m = re.search(r"\[.*\]", raw or "", re.S)
    if not m:
        return {}
    try:
        reeks = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {}
    uit: dict[str, dict] = {}
    for d in reeks if isinstance(reeks, list) else []:
        try:
            x = groep[int(d["n"]) - 1]
        except Exception:  # noqa: BLE001
            continue
        cat = d.get("category")
        if str(cat or "").strip().lower() in ("none", "null", ""):
            uit[x["id"]] = {"geen_tak": True}
            continue
        if d.get("confidence") == "low" or cat not in I._ALL_CATEGORIES:
            continue
        # Dezelfde schoencontrole als de enkele vraag: staat er "shoes" en kiest het
        # model iets anders, dan liever leeg dan een schoen onder jeans.
        if (I._is_footwear_text(x.get("title"), x.get("description"))
                and not I._is_footwear_category(cat)):
            continue
        uit[x["id"]] = {"gender": I._TAK_VAN_RUBRIEK[cat], "category": cat}
    return uit


async def deel_in(items: list[dict]) -> dict[str, dict]:
    """Rubrieken voor een lijst artikelen, twintig per vraag. Geeft per artikel
    dat een antwoord kreeg {'gender','category'} of {'geen_tak': True}. Een groep
    die twee keer mislukt, ontbreekt gewoon: dan telt het niet als antwoord."""
    if not items or not settings.anthropic_api_key:
        return {}
    systeem = _systeemtekst()
    groepen = [items[i:i + GROEP] for i in range(0, len(items), GROEP)]
    rem = asyncio.Semaphore(GELIJKTIJDIG)
    uit: dict[str, dict] = {}

    async def een(groep: list[dict]):
        if not _ruimte(len(groep)):
            logger.warning("Rubriekgroepen: dagplafond van %d artikelen bereikt", DAGMAX_ARTIKELEN)
            return
        for poging in range(2):
            try:
                async with rem:
                    raw = await asyncio.to_thread(
                        _vraag_claude, systeem, _gebruikertekst(groep), len(groep))
                antwoord = _lees_antwoord(raw, groep)
                if antwoord:
                    uit.update(antwoord)
                    return
            except Exception as e:  # noqa: BLE001
                logger.warning("Rubriekgroep mislukt (poging %d): %s: %s",
                               poging + 1, type(e).__name__, e)
            await asyncio.sleep(2)

    await asyncio.gather(*(een(g) for g in groepen))
    return uit


# ── De ronde ────────────────────────────────────────────────────────────────

def _lees_kandidaten(db, uren: int, limiet: int) -> list[dict]:
    from backend.services.categorie_herstel import MAX_POGINGEN, _TELLER
    sinds = (datetime.now(timezone.utc) - timedelta(hours=uren)).isoformat()
    velden = f"id,user_id,title,description,brand,category,gender,{_TELLER}"
    try:
        return (db.table("items").select(velden)
                .or_("category.is.null,category.eq.").gte("created_at", sinds)
                .lt(_TELLER, MAX_POGINGEN)
                .order("created_at", desc=True).limit(limiet).execute().data or [])
    except Exception:  # noqa: BLE001  (teller-kolom ontbreekt: ronde zonder opgeefgrens)
        return (db.table("items").select("id,user_id,title,description,brand,category,gender")
                .or_("category.is.null,category.eq.").gte("created_at", sinds)
                .order("created_at", desc=True).limit(limiet).execute().data or [])


def _schrijf_rubriek(db, item_id: str, patch: dict) -> None:
    (db.table("items").update(patch).eq("id", item_id)
       .or_("category.is.null,category.eq.").execute())


async def vul_rubrieken_in_groepen(uren: int = TERUGKIJKEN_UREN, limiet: int = PER_RONDE) -> dict:
    """Vul de lege rubrieken van recente artikelen in, twintig tegelijk. Bedoeld
    voor elke paar minuten: een nieuwe klant ziet zijn artikelen dan binnen
    minuten klaar voor plaatsing, ook als de gratis Google-limiet op is."""
    from backend.services.categorie_herstel import MAX_POGINGEN, _TELLER, _schrijf_pogingen
    db = get_db()
    items = await asyncio.to_thread(_lees_kandidaten, db, uren, limiet)
    if not items:
        return {"gelezen": 0, "gevuld": 0, "geen_antwoord": 0}
    antwoorden = await deel_in(items)
    gevuld = 0
    zonder: dict[int, list[dict]] = {}
    for item in items:
        a = antwoorden.get(item["id"])
        if a is None:
            continue  # geen antwoord gekregen: telt niet als kans
        if a.get("category") and not str(item.get("category") or "").strip():
            patch = {"category": a["category"]}
            if not str(item.get("gender") or "").strip():
                patch["gender"] = a["gender"]
            try:
                await asyncio.to_thread(_schrijf_rubriek, db, item["id"], patch)
                gevuld += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("Rubriek opslaan mislukt voor %s: %s", item["id"], e)
        else:
            stand = int(item.get(_TELLER) or 0) + 1
            zonder.setdefault(min(stand, MAX_POGINGEN), []).append(item)
    if zonder and gevuld > 0:
        await asyncio.to_thread(_schrijf_pogingen, db, zonder)
    logger.info("Rubriekgroepen: %d bekeken, %d gevuld, %d zonder uitkomst, %d zonder antwoord",
                len(items), gevuld, sum(len(v) for v in zonder.values()),
                len(items) - len(antwoorden))
    return {"gelezen": len(items), "gevuld": gevuld,
            "geen_antwoord": len(items) - len(antwoorden)}
