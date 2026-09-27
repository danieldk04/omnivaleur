"""De ronde die zoekertjes die al op 2dehands staan bijwerkt naar de verzendkeuze
van de verkoper. Het waarom staat in verzending_2dh.py.

Hij draait op de server en niet in een verzoek: Railway doodt lopende verzoeken
bij elke deploy (kennisbank railway-doodt-lopend-verzoek-bij-deploy). De stand
staat per verkoper in platform_credentials, zodat de volgende server verder gaat
waar deze was. Wat hij doet per artikel: bij Marktplaats het eigen bedrag lezen
(alleen als het ertoe doet), bij 2dehands kijken wat er nu staat, en alleen als
dat anders is een bijwerking klaarzetten (content_refresh met
_verzending_bijwerken, uitgevoerd door extensie 1.0.354+).
"""
from __future__ import annotations

import bisect
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from backend.database import fetch_all, get_db
from backend.services.verzending_2dh import EIGEN_MAX_ARTIKELEN, _EIGEN_CACHE, doel, eigen_keuzes

logger = logging.getLogger(__name__)

# ── de ronde over wat al online staat ─────────────────────────────────────────
# Stand per verkoper in een eigen rij, zodat een deploy (Railway doodt dan alles
# wat loopt, zie kennisbank railway-doodt-lopend-verzoek-bij-deploy) hem niet
# kwijtmaakt: de volgende server gaat verder waar deze was.
RIJ_RONDE = "_verzending_2dh_ronde"
MAX_POGINGEN = 3                  # wat Marktplaats of 2dehands niet beantwoordde
WACHT_VOOR_HERKANSING = timedelta(seconds=60)
MP_RUST_NA_BLOKKADE = 30          # seconden: na een 403 niet meteen opnieuw kloppen
# Weigert Marktplaats een paar keer achter elkaar, dan telkens twee keer zo lang
# wachten, tot hooguit vijf minuten. Gemeten 27-09-2026 bij Egbert op de server:
# eerst 1 op de 18 pagina's geweigerd, een kwartier later bijna de helft. Met een
# vaste halve minuut verbrandde elke blokkade een van de drie kansen van een
# artikel; na een geslaagde pagina is het weer een halve minuut.
MP_RUST_MAX = 300
_MP_OP_RIJ = [0]
GOEDKOOP_PER_TIK = 25             # beslissingen zonder verzoek naar buiten per tik
SCHRIJF_ELKE = 20                 # seconden tussen twee keer de stand bewaren
LEASE = timedelta(seconds=90)
LADEN_ELKE = 60
EIGEN_CACHE_SEC = 60
TELLERS = ("aangepast", "onderweg", "al_goed", "bpost", "niet_op_mp", "ophalen", "weg")

_EIGENAAR = uuid.uuid4().hex      # dit serverproces
_RONDES: dict[str, dict] = {}
_LIJST: dict[tuple[str, str], list[str]] = {}
_GESCHREVEN: dict[str, float] = {}
_GELADEN = [0.0]
_MP_RUST_TOT = [0.0]
_BEURT = [0]


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat()


def _lees_rij(db, user_id: str) -> dict | None:
    rij = (db.table("platform_credentials").select("extra_data").eq("user_id", user_id)
           .eq("platform", RIJ_RONDE).limit(1).execute().data or [])
    return (rij[0].get("extra_data") or None) if rij else None


def _schrijf_rij(db, user_id: str, st: dict) -> None:
    st["eigenaar"] = _EIGENAAR
    st["lease_tot"] = _iso(_nu() + LEASE)
    st["bijgewerkt_op"] = _iso(_nu())
    db.table("platform_credentials").upsert(
        {"user_id": user_id, "platform": RIJ_RONDE, "extra_data": st},
        on_conflict="user_id,platform").execute()
    _GESCHREVEN[user_id] = time.monotonic()


def stand(user_id: str, db=None) -> dict | None:
    """De ronde van deze verkoper zoals hij nu is, of None als er nooit een was."""
    st = _RONDES.get(user_id)
    if st is None:
        try:
            st = _lees_rij(db or get_db(), user_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("verzendronde van %s niet gelezen: %s", user_id, e)
            return None
    return dict(st) if st else None


def openbaar(st: dict | None) -> dict | None:
    """Wat het scherm te zien krijgt: tellingen, geen lijsten met nummers."""
    if not st:
        return None
    wacht = st.get("wacht_tot")
    return {
        "status": st.get("status"),
        "soort": st.get("soort"),
        "gestart_op": st.get("gestart_op"),
        "klaar_op": st.get("klaar_op"),
        "aantal": st.get("aantal"),
        "bekeken": st.get("bekeken", 0),
        "tel": {k: int((st.get("tel") or {}).get(k, 0)) for k in TELLERS},
        "niet_gelezen": len(st.get("niet_gelezen_ids") or []) if st.get("status") != "loopt"
        else len(st.get("opnieuw") or []),
        "poging": st.get("poging", 1),
        "wacht_op_herkansing": bool(wacht) and st.get("status") == "loopt",
        "instelling": st.get("instelling"),
    }


def _nieuwe_stand(regel: dict, alles: bool, ids: list[str]) -> dict:
    return {"status": "loopt", "gestart_op": _iso(_nu()), "klaar_op": None,
            "instelling": regel, "alles": alles, "cursor": None,
            "ids": ids, "pos": 0, "extra": [], "opnieuw": [], "poging": 1,
            "wacht_tot": None, "aantal": None if alles else len(ids), "bekeken": 0,
            "tel": {k: 0 for k in TELLERS}, "niet_gelezen_ids": [], "blokkades": 0}


def start(user_id: str, item_ids=None, opnieuw_niet_gelezen: bool = False, db=None) -> dict:
    """Een ronde beginnen.

    Zonder item_ids: alles wat deze verkoper op 2dehands heeft. Loopt er al zo'n
    ronde met dezelfde instelling, dan is dat deze (een tweede klik start niets
    nieuws). Met een andere instelling begint hij opnieuw, met de nieuwe.

    Met item_ids (een eigen keuze per artikel): loopt er al een ronde, dan komen
    ze er achteraan; anders een ronde voor alleen die artikelen.
    """
    from backend.services.instellingen import verzending_2dh_regel
    db = db or get_db()
    regel = verzending_2dh_regel(user_id, db)
    if regel is None:
        raise RuntimeError("could not read the shipping setting")
    nu = stand(user_id, db)
    loopt = bool(nu) and nu.get("status") == "loopt"
    if opnieuw_niet_gelezen:
        ids = list((nu or {}).get("niet_gelezen_ids") or [])
        if loopt or not ids:
            return nu or {}
        st = _nieuwe_stand(regel, False, ids)
    elif item_ids is None:
        if loopt and nu.get("soort") == "alles" and nu.get("instelling") == regel:
            return nu
        st = _nieuwe_stand(regel, True, [])
        st["soort"] = "alles"
    else:
        ids = list(dict.fromkeys(str(i) for i in item_ids if i))
        if not ids:
            return nu or {}
        if loopt:
            st = _RONDES.get(user_id) or nu
            st["extra"] = list(dict.fromkeys((st.get("extra") or []) + ids))
            _RONDES[user_id] = st
            _schrijf_rij(db, user_id, st)
            return st
        st = _nieuwe_stand(regel, False, ids)
    st["soort"] = st.get("soort") or "lijst"
    _RONDES[user_id] = st
    _schrijf_rij(db, user_id, st)
    return st


def stop_als_verouderd(user_id: str, regel: dict, db=None) -> bool:
    """De verkoper koos iets anders: een lopende ronde met de oude keuze stopt.
    Anders zet hij nog uren bedragen die hij net heeft afgezegd."""
    st = stand(user_id, db)
    if not st or st.get("status") != "loopt" or st.get("instelling") == regel:
        return False
    st["status"] = "gestopt"
    st["klaar_op"] = _iso(_nu())
    _RONDES[user_id] = st
    try:
        _schrijf_rij(db or get_db(), user_id, st)
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendronde van %s niet gestopt: %s", user_id, e)
    return True


# ── één stap ──────────────────────────────────────────────────────────────────
def _alles_lijst(db, user_id: str, st: dict) -> list[str]:
    """Alle artikelen met een actief 2dehands-zoekertje, op volgorde, eenmaal per
    ronde. Eén gekoppelde vraag: per brok van 200 geeft bij grote accounts 502
    (kennisbank gekoppelde-vraag-ipv-brokken)."""
    sleutel = (user_id, st.get("gestart_op") or "")
    if sleutel not in _LIJST:
        rijen = fetch_all(lambda: db.table("listings").select("id,item_id,items!inner(user_id)")
                          .eq("items.user_id", user_id).eq("platform", "2dehands")
                          .eq("status", "active").not_.is_("platform_listing_id", "null"))
        for oud in [k for k in _LIJST if k[0] == user_id]:
            del _LIJST[oud]
        _LIJST[sleutel] = sorted({str(r["item_id"]) for r in rijen if r.get("item_id")})
        if st.get("aantal") is None:
            st["aantal"] = len(_LIJST[sleutel])
    return _LIJST[sleutel]


def volgende(db, user_id: str, st: dict) -> str | None:
    """Het volgende artikel, of None als er nu niets te doen is. Zet de ronde op
    'klaar' als alles gedaan is."""
    if st.get("alles"):
        lijst = _alles_lijst(db, user_id, st)
        i = bisect.bisect_right(lijst, st.get("cursor") or "")
        if i < len(lijst):
            st["cursor"] = lijst[i]
            st["bekeken"] = st.get("bekeken", 0) + 1
            return lijst[i]
        st["alles"] = False
    ids, pos = st.get("ids") or [], int(st.get("pos") or 0)
    if pos < len(ids):
        st["pos"] = pos + 1
        if st.get("poging", 1) == 1:
            st["bekeken"] = st.get("bekeken", 0) + 1
        return ids[pos]
    if st.get("extra"):
        st["ids"], st["pos"], st["extra"] = list(st["extra"]), 0, []
        st["aantal"] = (st.get("aantal") or 0) + len(st["ids"])
        st["poging"] = 1
        return volgende(db, user_id, st)
    if st.get("opnieuw") and st.get("poging", 1) < MAX_POGINGEN:
        if not st.get("wacht_tot"):
            st["wacht_tot"] = _iso(_nu() + WACHT_VOOR_HERKANSING)
            return None
        if _nu() < datetime.fromisoformat(st["wacht_tot"]):
            return None
        st["ids"], st["pos"], st["opnieuw"] = list(st["opnieuw"]), 0, []
        st["poging"] = st.get("poging", 1) + 1
        st["wacht_tot"] = None
        return volgende(db, user_id, st)
    st["status"] = "klaar"
    st["klaar_op"] = _iso(_nu())
    st["niet_gelezen_ids"] = list(st.get("opnieuw") or [])[:EIGEN_MAX_ARTIKELEN]
    st["opnieuw"] = []
    st["wacht_tot"] = None
    return None


def _info(db, user_id: str, item_id: str) -> dict:
    """Titel en de zoekertjes op 2dehands en Marktplaats van dit artikel, alleen
    als het van deze verkoper is."""
    rijen = (db.table("listings")
             .select("platform,platform_listing_id,platform_listing_url,items!inner(title,user_id)")
             .eq("item_id", item_id).eq("items.user_id", user_id).eq("status", "active")
             .in_("platform", ["2dehands", "marktplaats"]).execute().data or [])
    uit = {"titel": "", "dh": None, "dh_url": None, "mp": None}
    for r in rijen:
        uit["titel"] = ((r.get("items") or {}).get("title") or uit["titel"])
        if not r.get("platform_listing_id"):
            continue
        if r["platform"] == "2dehands":
            uit["dh"], uit["dh_url"] = r["platform_listing_id"], r.get("platform_listing_url")
        else:
            uit["mp"] = r["platform_listing_id"]
    return uit


def _onderweg(db, user_id: str, item_id: str) -> bool:
    """Staat er al een bijwerking voor dit zoekertje klaar? Nooit twee
    (kennisbank herkansen-mag-geen-dubbele-opdracht)."""
    return bool(db.table("jobs").select("id").eq("user_id", user_id).eq("item_id", item_id)
                .eq("platform", "2dehands").eq("action", "content_refresh")
                .in_("status", ["pending", "claimed"]).limit(1).execute().data)


def _eigen_uit_cache(db, user_id: str) -> dict | None:
    bewaard = _EIGEN_CACHE.get(user_id)
    if bewaard and time.monotonic() - bewaard[0] < EIGEN_CACHE_SEC:
        return bewaard[1]
    eigen = eigen_keuzes(user_id, db)
    if eigen is not None:
        _EIGEN_CACHE[user_id] = (time.monotonic(), eigen)
    return eigen


async def lees_marktplaats(nummer: str, user_id: str):
    from backend.services.mp_enrich import verzending_van_advertentie
    return await verzending_van_advertentie(nummer, user_id)


async def lees_2dehands(lid: str):
    """Wat de openbare 2dehands-pagina toont: dict, "weg", of None (storing)."""
    import httpx
    from backend.services.mp_enrich import UA, verzending_uit_html
    m = re.fullmatch(r"([am]?)(\d+)", str(lid or "").strip().lower())
    if not m:
        return None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                     headers={"User-Agent": UA}) as client:
            r = await client.get(f"https://www.2dehands.be/{m.group(1) or 'm'}{m.group(2)}",
                                 headers={"Accept": "text/html"})
    except Exception as e:  # noqa: BLE001
        logger.warning("2dehands %s niet te lezen: %s", lid, e)
        return None
    if r.status_code in (404, 410):
        return "weg"
    if r.status_code != 200:
        logger.warning("2dehands %s gaf HTTP %s", lid, r.status_code)
        return None
    return verzending_uit_html(r.text)


def _later(st: dict, item_id: str) -> None:
    if item_id not in (st.get("opnieuw") or []):
        st.setdefault("opnieuw", []).append(item_id)


def _tel(st: dict, wat: str) -> None:
    st.setdefault("tel", {})
    st["tel"][wat] = int(st["tel"].get(wat, 0)) + 1


async def bekijk(db, user_id: str, st: dict, item_id: str,
                 lees_mp=None, lees_dh=None) -> bool:
    """Eén artikel: zo nodig een bijwerking klaarzetten. Geeft terug of er een
    verzoek naar buiten ging (Marktplaats of 2dehands), zodat de tik weet of hij
    moet ophouden. Wat niet te lezen was gaat naar de herkansing, nooit naar een
    teller die iets beweert."""
    lees_mp = lees_mp or lees_marktplaats
    lees_dh = lees_dh or lees_2dehands
    try:
        info = _info(db, user_id, item_id)
        if not info["dh"]:
            _tel(st, "weg")
            return False
        if _onderweg(db, user_id, item_id):
            _tel(st, "onderweg")
            return False
        alle_eigen = _eigen_uit_cache(db, user_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendronde %s: %s niet te lezen: %s", user_id, item_id, e)
        _later(st, item_id)
        return False
    if alle_eigen is None:
        _later(st, item_id)
        return False
    from backend.services.instellingen import heeft_marktplaats_nodig
    regel, eigen, titel = st.get("instelling") or {}, alle_eigen.get(item_id), info["titel"]
    buiten = False
    mp = {}
    if eigen is None and heeft_marktplaats_nodig(regel, titel):
        if not info["mp"]:
            _tel(st, "niet_op_mp")
            return False
        mp = await lees_mp(info["mp"], user_id)
        buiten = True
        if mp is None:
            st["blokkades"] = st.get("blokkades", 0) + 1
            _MP_OP_RIJ[0] += 1
            _MP_RUST_TOT[0] = time.monotonic() + min(
                MP_RUST_NA_BLOKKADE * 2 ** (_MP_OP_RIJ[0] - 1), MP_RUST_MAX)
            _later(st, item_id)
            return buiten
        _MP_OP_RIJ[0] = 0
        if not mp:
            _tel(st, "niet_op_mp")
            return buiten
    wil = doel(regel, eigen, titel, mp)
    if wil is None:
        _later(st, item_id)
        return buiten
    if wil.get("soort") != "zelf":
        _tel(st, "bpost")
        return buiten
    nu = await lees_dh(info["dh"])
    buiten = True
    if nu is None:
        _later(st, item_id)
        return buiten
    if nu == "weg":
        _tel(st, "weg")
        return buiten
    if nu.get("soort") == "geen":
        # Alleen ophalen: het wijzigformulier heeft dan geen verzendkeuze, en een
        # bijwerking die daarop faalt zet de noodrem voor al zijn bijwerkingen dicht.
        _tel(st, "ophalen")
        return buiten
    if nu == wil:
        _tel(st, "al_goed")
        return buiten
    try:
        if _onderweg(db, user_id, item_id):
            _tel(st, "onderweg")
            return buiten
        db.table("jobs").insert({
            "user_id": user_id, "item_id": item_id, "platform": "2dehands",
            "action": "content_refresh", "status": "pending",
            "payload": {"platform_listing_id": info["dh"], "platform_listing_url": info["dh_url"],
                        "title": titel, "_verzending_bijwerken": True, "verzending": wil},
        }).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendronde %s: bijwerking %s niet klaar te zetten: %s", user_id, item_id, e)
        _later(st, item_id)
        return buiten
    _tel(st, "aangepast")
    return buiten


# ── de klok ───────────────────────────────────────────────────────────────────
def _laad(db) -> None:
    """Lopende rondes uit de database halen: na een herstart, of een ronde die
    een ander proces liet vallen (lease verlopen)."""
    if time.monotonic() - _GELADEN[0] < LADEN_ELKE:
        return
    _GELADEN[0] = time.monotonic()
    rijen = (db.table("platform_credentials").select("user_id,extra_data")
             .eq("platform", RIJ_RONDE).eq("extra_data->>status", "loopt").execute().data or [])
    nu = _iso(_nu())
    for r in rijen:
        uid, st = r["user_id"], r.get("extra_data") or {}
        eigen = _RONDES.get(uid)
        if eigen and eigen.get("gestart_op") == st.get("gestart_op"):
            continue
        if eigen and (eigen.get("gestart_op") or "") > (st.get("gestart_op") or ""):
            continue
        if st.get("eigenaar") not in (None, _EIGENAAR) and (st.get("lease_tot") or "") > nu:
            continue
        _RONDES[uid] = st


def _mag_schrijven(db, user_id: str, st: dict) -> bool:
    """Is deze ronde nog van ons? Een ander proces (tijdens een deploy draaien er
    even twee) kan hem hebben overgenomen of een nieuwe gestart."""
    rij = (db.table("platform_credentials")
           .select("gestart:extra_data->>gestart_op,eigenaar:extra_data->>eigenaar,"
                   "lease:extra_data->>lease_tot,status:extra_data->>status")
           .eq("user_id", user_id).eq("platform", RIJ_RONDE).limit(1).execute().data or [])
    if not rij:
        return True
    r = rij[0]
    if (r.get("gestart") or "") != (st.get("gestart_op") or ""):
        return (r.get("gestart") or "") < (st.get("gestart_op") or "")
    if r.get("status") != "loopt" and st.get("status") == "loopt":
        return False          # elders gestopt
    return r.get("eigenaar") in (None, _EIGENAAR) or (r.get("lease") or "") <= _iso(_nu())


def _bewaar(db, user_id: str, st: dict, meteen: bool = False) -> None:
    if not meteen and time.monotonic() - _GESCHREVEN.get(user_id, 0.0) < SCHRIJF_ELKE:
        return
    try:
        if not _mag_schrijven(db, user_id, st):
            if _RONDES.get(user_id) is st:
                _RONDES.pop(user_id, None)
            return
        _schrijf_rij(db, user_id, st)
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendronde %s niet bewaard: %s", user_id, e)


async def tik(db=None, lees_mp=None, lees_dh=None) -> None:
    """Elke paar seconden: een stap in één lopende ronde. Hooguit één verzoek
    naar Marktplaats of 2dehands per tik, voor alle verkopers samen: zestig
    Marktplaats-pagina's in vijftien seconden gaf 403 (26-09-2026)."""
    db = db or get_db()
    try:
        _laad(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("verzendrondes niet geladen: %s", e)
    lopend = sorted(u for u, st in _RONDES.items() if st.get("status") == "loopt")
    if not lopend or time.monotonic() < _MP_RUST_TOT[0]:
        return
    _BEURT[0] = (_BEURT[0] + 1) % len(lopend)
    user_id = lopend[_BEURT[0]]
    st = _RONDES[user_id]
    for _ in range(GOEDKOOP_PER_TIK):
        try:
            item_id = volgende(db, user_id, st)
        except Exception as e:  # noqa: BLE001
            logger.warning("verzendronde %s: volgende niet te bepalen: %s", user_id, e)
            return
        if item_id is None:
            break
        voor = (st.get("tel") or {}).get("aangepast", 0)
        buiten = await bekijk(db, user_id, st, item_id, lees_mp, lees_dh)
        if (st.get("tel") or {}).get("aangepast", 0) != voor:
            # Meteen bewaren: na een herstart mag dit artikel niet nog eens als
            # "aangepast" tellen (de bijwerking staat er, dus dan heet het onderweg).
            _bewaar(db, user_id, st, meteen=True)
        if buiten:
            break
    klaar = st.get("status") != "loopt"
    if klaar:
        logger.info("verzendronde %s klaar: %s, %s niet te lezen, %s blokkades",
                    user_id, st.get("tel"), len(st.get("niet_gelezen_ids") or []),
                    st.get("blokkades", 0))
    _bewaar(db, user_id, st, meteen=klaar)


async def werk_verzendrondes_bij() -> None:
    """Voor de planner (scheduler.py)."""
    await tik()


def extensie_kan_bijwerken(user_id: str, db=None) -> bool | None:
    """Kan de extensie van deze verkoper een zoekertje bijwerken (1.0.354+)?
    None = weten we niet (nooit gezien, of de hartslag is niet te lezen)."""
    from backend.api.jobs import MINIMALE_2DH_BIJWERK_VERSIE
    try:
        rij = ((db or get_db()).table("extension_heartbeat").select("ext_version")
               .eq("user_id", user_id).limit(1).execute().data or [])
    except Exception:  # noqa: BLE001
        return None
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", str((rij or [{}])[0].get("ext_version") or ""))
    if not m:
        return None
    return tuple(int(x) for x in m.groups()) >= MINIMALE_2DH_BIJWERK_VERSIE
