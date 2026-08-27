"""
Het beheerscherm: alles wat de eigenaar moet weten, op één plek.

WAAROM DIT BESTAAT
De cijfers lagen verspreid over Stripe, Supabase, Search Console, Analytics en
de koude-mailmachine. Wie wilde weten hoe het ervoor stond, moest vijf plekken
langs en drie daarvan kon niemand lezen zonder SQL. Dit endpoint doet dat
rondje één keer per opvraging en geeft één samenhangend beeld terug.

DRIE REGELS DIE HIER GELDEN
1. Eigenaar-only. Elk endpoint controleert het e-mailadres, net als de rest van
   /admin. Er staan klantgegevens in.
2. Elke bron faalt zacht. Ligt Search Console eruit, dan hoort dát blok leeg te
   zijn met een reden erbij — niet de hele pagina. Een dashboard dat bij één
   kapotte koppeling helemaal wit blijft, wordt niet meer geopend.
3. De trage en betaalde bronnen (Apify, Google) zitten achter hun eigen endpoint
   met een cache. Het scherm ververst zichzelf elke minuut; zonder die scheiding
   zou dat elke minuut Apify-tegoed kosten en de Google-quota opmaken.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user_full
from backend.config import settings
from backend.database import execute_with_retry, get_admin_db, get_db
from backend.services.billing import is_owner_email as _is_owner_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/beheer", tags=["beheer"])


def _eigenaar(user) -> None:
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")


# ---------------------------------------------------------------------------
# Cache. Bewust piepklein: een dict met (tijdstip, waarde) per sleutel. Het gaat
# om drie tot vier ingangen die elke minuut opgevraagd worden door één persoon.
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, dict]] = {}


def _uit_cache(sleutel: str, seconden: int):
    gevonden = _cache.get(sleutel)
    if gevonden and (time.time() - gevonden[0]) < seconden:
        return gevonden[1]
    return None


def _in_cache(sleutel: str, waarde: dict) -> dict:
    _cache[sleutel] = (time.time(), waarde)
    return waarde


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dagen_terug: int) -> str:
    return (_nu() - timedelta(days=dagen_terug)).isoformat()


def _dag(dagen_terug: int) -> str:
    return (date.today() - timedelta(days=dagen_terug)).isoformat()


def _tijd(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        dt = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _dagen_tot(waarde) -> int | None:
    dt = _tijd(waarde)
    return None if dt is None else (dt - _nu()).days


def _telling(tabel: str, **filters) -> int:
    """Aantal rijen zonder ze op te halen. Zonder count='exact' haalde dit
    scherm bij elke verversing tienduizenden rijen op om er één getal van te
    maken."""
    try:
        q = get_db().table(tabel).select("*", count="exact", head=True)
        for kolom, waarde in filters.items():
            if kolom.endswith("__gte"):
                q = q.gte(kolom[:-5], waarde)
            elif kolom.endswith("__lt"):
                q = q.lt(kolom[:-4], waarde)
            elif kolom.endswith("__not_null"):
                q = q.not_.is_(kolom[:-10], "null")
            else:
                q = q.eq(kolom, waarde)
        return execute_with_retry(q).count or 0
    except Exception as e:
        logger.warning("Tellen mislukt op %s (%s): %s", tabel, filters, e)
        return 0


# ---------------------------------------------------------------------------
# Stripe. Bewust via de gewone REST-API en niet via de SDK: die verplaatste
# current_period_end naar binnen in het items-object, waardoor sub["..."] en
# sub.get() allebei stukliepen op de ene plek waar het echt om geld gaat.
# ---------------------------------------------------------------------------
def _stripe_get(pad: str, params: dict | None = None) -> dict:
    if not settings.stripe_secret_key:
        return {}
    r = httpx.get(f"https://api.stripe.com/v1/{pad}", params=params or {},
                  auth=(settings.stripe_secret_key, ""), timeout=20.0)
    r.raise_for_status()
    return r.json()


def _geld() -> dict:
    """Omzet en betalingen rechtstreeks uit Stripe — dat is de enige plek waar
    dit echt klopt. Onze eigen subscriptions-tabel is een kopie die kan
    achterlopen als een webhook mist."""
    if not settings.stripe_secret_key:
        return {"gekoppeld": False, "reden": "Geen Stripe-sleutel op de server"}
    try:
        mrr_cent = 0
        betalend = proef = 0
        opzeggingen = 0
        maand_start = _nu().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starting_after = None
        for _ in range(10):  # 1000 abonnementen; ruim genoeg, en nooit oneindig
            params = {"status": "all", "limit": 100}
            if starting_after:
                params["starting_after"] = starting_after
            blok = _stripe_get("subscriptions", params)
            rijen = blok.get("data") or []
            for sub in rijen:
                status = sub.get("status")
                if status == "active":
                    betalend += 1
                    for regel in (sub.get("items") or {}).get("data") or []:
                        prijs = regel.get("price") or {}
                        bedrag = prijs.get("unit_amount") or 0
                        aantal = regel.get("quantity") or 1
                        per = (prijs.get("recurring") or {}).get("interval")
                        maandbedrag = bedrag * aantal
                        if per == "year":
                            maandbedrag = maandbedrag / 12
                        mrr_cent += maandbedrag
                elif status == "trialing":
                    proef += 1
                if sub.get("canceled_at") and datetime.fromtimestamp(
                        sub["canceled_at"], timezone.utc) >= maand_start:
                    opzeggingen += 1
            if not blok.get("has_more"):
                break
            starting_after = rijen[-1]["id"] if rijen else None

        mislukt = _stripe_get("invoices", {"status": "open", "limit": 100}).get("data") or []
        openstaand = sum((f.get("amount_due") or 0) for f in mislukt)
        return {
            "gekoppeld": True,
            "mrr": round(mrr_cent / 100, 2),
            "betalend": betalend,
            "proef": proef,
            "opgezegd_deze_maand": opzeggingen,
            "open_facturen": len(mislukt),
            "open_bedrag": round(openstaand / 100, 2),
        }
    except Exception as e:
        logger.warning("Stripe-blok mislukt: %s", e)
        return {"gekoppeld": False, "reden": f"Stripe antwoordde niet: {type(e).__name__}"}


# ---------------------------------------------------------------------------
# Klanten
# ---------------------------------------------------------------------------
def _adressen() -> dict[str, dict]:
    """user_id → e-mailadres en laatste login. Vereist de service-role sleutel;
    met de publieke sleutel weigert Supabase dit en blijft de kolom leeg in
    plaats van dat de pagina omvalt."""
    uit: dict[str, dict] = {}
    page = 1
    while page <= 20:
        try:
            gevonden = get_admin_db().auth.admin.list_users(page=page, per_page=200)
        except Exception as e:
            logger.warning("Gebruikerslijst niet beschikbaar: %s", e)
            break
        if not gevonden:
            break
        for u in gevonden:
            uit[u.id] = {
                "email": u.email,
                "laatste_login": str(u.last_sign_in_at) if u.last_sign_in_at else None,
                "aangemeld": str(u.created_at) if u.created_at else None,
            }
        if len(gevonden) < 200:
            break
        page += 1
    return uit


def _klanten() -> dict:
    db = get_db()
    abos = execute_with_retry(db.table("subscriptions").select(
        "user_id, status, plan, trial_ends_at, current_period_end, stripe_subscription_id"
    )).data or []
    adressen = _adressen()

    # Advertenties per klant. listings heeft geen user_id, dus de brug loopt via
    # items — precies de val waar eerdere overzichten in trapten en waardoor de
    # aantallen van alle klanten door elkaar liepen.
    items = execute_with_retry(db.table("items").select("id, user_id")).data or []
    eigenaar_van = {i["id"]: i["user_id"] for i in items}
    items_per_klant: dict[str, int] = {}
    for i in items:
        items_per_klant[i["user_id"]] = items_per_klant.get(i["user_id"], 0) + 1

    live_per_klant: dict[str, int] = {}
    verkocht_per_klant: dict[str, int] = {}
    try:
        rijen = execute_with_retry(db.table("listings").select(
            "item_id, status, sold_at")).data or []
    except Exception as e:
        logger.warning("Advertenties niet op te halen: %s", e)
        rijen = []
    week_terug = _nu() - timedelta(days=7)
    for r in rijen:
        klant = eigenaar_van.get(r.get("item_id"))
        if not klant:
            continue
        if r.get("status") == "active":
            live_per_klant[klant] = live_per_klant.get(klant, 0) + 1
        verkocht = _tijd(r.get("sold_at"))
        if verkocht and verkocht >= week_terug:
            verkocht_per_klant[klant] = verkocht_per_klant.get(klant, 0) + 1

    # Wie is er echt aan het werk? Een baan die de afgelopen week klaar is
    # gekomen zegt meer dan een login: inloggen doet iemand ook om op te zeggen.
    actief: dict[str, str] = {}
    try:
        banen = execute_with_retry(db.table("jobs").select("user_id, done_at")
                                   .gte("done_at", _iso(7))).data or []
        for b in banen:
            klant, wanneer = b.get("user_id"), b.get("done_at")
            if klant and wanneer and wanneer > actief.get(klant, ""):
                actief[klant] = wanneer
    except Exception as e:
        logger.warning("Activiteit niet op te halen: %s", e)

    hartslag: dict[str, str] = {}
    try:
        for h in (db.table("extension_heartbeat").select("user_id, last_seen")
                  .execute().data or []):
            hartslag[h["user_id"]] = h.get("last_seen")
    except Exception:
        pass  # tabel bestaat mogelijk nog niet; dan blijft de kolom leeg

    volgorde = {"active": 0, "trialing": 1, "past_due": 2, "canceled": 3}
    lijst = []
    for a in abos:
        klant = a["user_id"]
        info = adressen.get(klant, {})
        online = _tijd(hartslag.get(klant))
        lijst.append({
            "user_id": klant,
            "email": info.get("email") or "(adres onbekend)",
            "status": a.get("status") or "onbekend",
            "betaalt": bool(a.get("stripe_subscription_id")),
            "proef_tot": a.get("trial_ends_at"),
            "dagen_over": _dagen_tot(a.get("trial_ends_at"))
                          if (a.get("status") == "trialing") else None,
            "verlengt": a.get("current_period_end"),
            "laatste_login": info.get("laatste_login"),
            "aangemeld": info.get("aangemeld"),
            "artikelen": items_per_klant.get(klant, 0),
            "live": live_per_klant.get(klant, 0),
            "verkocht_7d": verkocht_per_klant.get(klant, 0),
            "laatst_actief": actief.get(klant),
            "extensie_online": bool(online and online >= _nu() - timedelta(minutes=15)),
        })
    lijst.sort(key=lambda r: (volgorde.get(r["status"], 9), -r["live"]))

    return {
        "totaal": len(abos),
        "accounts_zonder_abo": max(0, len(adressen) - len(abos)),
        "nieuw_7d": sum(1 for r in lijst
                        if (_tijd(r["aangemeld"]) or _nu() - timedelta(days=999))
                        >= _nu() - timedelta(days=7)),
        "actief_7d": len(actief),
        "extensies_online": sum(1 for r in lijst if r["extensie_online"]),
        "klanten": lijst,
    }


def _techniek() -> dict:
    """Draait de machine? Mislukte banen zijn het eerste dat een klant merkt en
    het laatste dat iemand ziet als er geen scherm voor is."""
    dag = _iso(1)
    return {
        "banen_mislukt_24u": _telling("jobs", status="failed", created_at__gte=dag),
        "banen_wachtend": _telling("jobs", status="pending"),
        "banen_klaar_24u": _telling("jobs", status="done", done_at__gte=dag),
        "advertenties_live": _telling("listings", status="active"),
        "advertenties_fout": _telling("listings", status="error"),
        "verkocht_7d": _telling("listings", sold_at__gte=_iso(7)),
        "importkandidaten_open": _telling("import_candidates", status="pending"),
    }


# ---------------------------------------------------------------------------
# Koude mail. De administratie van de mailmachine staat in leadgen_opslag onder
# de sleutel 'mail_state'; die tabel is met de publieke sleutel niet leesbaar,
# dus lokaal blijft dit blok leeg en op de server niet.
# ---------------------------------------------------------------------------
def _leadgen_lezen(naam: str):
    """Eén rij uit leadgen_opslag, of None als hij er niet is of niet leesbaar."""
    try:
        rijen = execute_with_retry(get_db().table("leadgen_opslag")
                                   .select("inhoud").eq("naam", naam)).data or []
    except Exception:
        return None
    return rijen[0].get("inhoud") if rijen else None


def _mail() -> dict:
    state = _leadgen_lezen("mail_state")
    if state is None:
        return {"gekoppeld": False,
                "reden": "Nog geen administratie gevonden (leadgen_opslag/mail_state)"}
    verstuurd = 0
    # Per dag én per laag: alleen zo is te zien of een piek uit nieuwe leads
    # komt of uit opvolgingen op de bestaande lijst.
    per_dag: dict[str, dict[str, int]] = {}
    for v in state.values():
        for m in (v.get("verstuurd") or []):
            verstuurd += 1
            # Het veld heet "op" (zie scripts/leadgen_mail.py, send()) — "datum"/"dag"
            # bestaan niet en lieten deze grafiek altijd leeg zien.
            dag = str(m.get("op") or "")[:10] if isinstance(m, dict) else str(m)[:10]
            if dag:
                emmer = per_dag.setdefault(dag, {})
                laag = str(m.get("beurt") or "?") if isinstance(m, dict) else "?"
                emmer[laag] = emmer.get(laag, 0) + 1
    benaderd = len(state)
    antwoorden = sum(1 for v in state.values() if v.get("beantwoord"))
    # Warm = geïnteresseerd, dat is de positieve reactie. Afwijzing en "gebruikt
    # al een concurrent" zijn allebei een nee, dus samen de negatieve kant.
    positief = sum(1 for v in state.values() if v.get("soort") == "warm")
    negatief = sum(1 for v in state.values() if v.get("afgewezen") or v.get("concurrent"))
    laatste_14 = []
    for i in range(13, -1, -1):
        d = _dag(i)
        emmer = per_dag.get(d, {})
        laatste_14.append({"dag": d, "mail1": emmer.get("mail1", 0),
                           "mail2": emmer.get("mail2", 0), "mail3": emmer.get("mail3", 0),
                           "aantal": sum(emmer.values())})
    return {
        "gekoppeld": True,
        "benaderd": benaderd,
        "verstuurd": verstuurd,
        "antwoorden": antwoorden,
        "antwoordpercentage": round(100 * antwoorden / benaderd, 1) if benaderd else 0,
        "positief": positief,
        "negatief": negatief,
        "afgemeld": sum(1 for v in state.values() if v.get("afgemeld")),
        "bounces": sum(1 for v in state.values() if v.get("bounce")),
        "per_dag": laatste_14,
        # Alleen de opvolgmails (na de eerste koude mail) dragen een pixel — zie
        # _open_pixel_html in scripts/leadgen_mail.py. De eerste mail blijft
        # bewust puur tekst, om niet als marketing over te komen.
        "open_tracking": True,
        "open_tracking_reden": "Alleen gemeten op de opvolgmails, niet op de eerste koude mail.",
        "opens": _mail_opens(list(state.keys())),
        "leren": _mail_leren(),
        "fouten_vandaag": (_leadgen_lezen("mail_plan") or {}).get("fouten") or [],
    }


def _mail_opens(adressen: list[str]) -> dict:
    opens = _leadgen_lezen("mail_opens") or {}
    gemeten = [a for a in adressen if a in opens]
    return {
        "adressen": len(gemeten),
        "totaal_geopend": sum(v.get("aantal", 0) for v in opens.values()),
    }


_CITAAT_SPLITSER = re.compile(r"\n\s*(?:Op .{0,60}schreef|Van:|-----Oorspronkelijk)")


def _zonder_citaat(t: str) -> str:
    """Zelfde afkap als _kern() in scripts/leadgen_mail.py: alleen de eigen
    tekst, zonder het geciteerde gesprek eronder — anders toont de kaart
    dezelfde quote twee keer en is niet in één oogopslag te zien wát er
    veranderd is."""
    return _CITAAT_SPLITSER.split(t or "", maxsplit=1)[0].strip()


def _mail_leren() -> dict:
    """Wat Daniel zelf van de voorstellen maakt, is de enige echte leerbron: hij
    verandert alleen iets als het voorstel niet goed genoeg was. Zie
    scripts/leadgen_mail.py, _onthoud_concept/_leer_van_verzonden."""
    log = _leadgen_lezen("leerlog") or []
    afgerond = [x for x in log if x.get("verstuurd")]
    aangepast = [x for x in afgerond if x.get("aangepast")]
    recent = sorted(afgerond, key=lambda x: x.get("op", ""), reverse=True)[:5]
    return {
        "totaal": len(afgerond),
        "aangepast": len(aangepast),
        "ongewijzigd_pct": round(100 * (len(afgerond) - len(aangepast)) / len(afgerond), 1)
                           if afgerond else None,
        "recent": [{"adres": x.get("adres"), "op": x.get("op"),
                    "aangepast": bool(x.get("aangepast")),
                    "voorstel": _zonder_citaat(x.get("voorstel"))[:280],
                    "verstuurd": _zonder_citaat(x.get("verstuurd"))[:280]} for x in recent],
    }


# ---------------------------------------------------------------------------
# Zoekverkeer: van cijfers naar iets om te doen
#
# Klikken en vertoningen vertellen je hoe het ging, niet wat je moet doen. Deze
# drie lijsten doen dat wel:
#   kansen   — je staat net naast de eerste pagina (positie 5 t/m 20) en er wordt
#              wél op gezocht. Eén betere pagina en je staat erin.
#   onbenut  — Google toont je vaak, niemand klikt. Dat is een titel- en
#              omschrijvingsprobleem, geen rankingprobleem.
#   stijgers/dalers — waar beweegt het, zodat je niet elke week hetzelfde
#              rijtje leest zonder te zien wat er veranderd is.
# ---------------------------------------------------------------------------
def _gsc_kansen(rijen: list[dict], limiet: int = 12) -> list[dict]:
    uit = [
        {"term": r["keys"][0], "vertoningen": r.get("impressions", 0),
         "klikken": r.get("clicks", 0), "positie": round(r.get("position", 0), 1)}
        for r in rijen
        if 5 <= r.get("position", 0) <= 20 and r.get("impressions", 0) >= 3
    ]
    return sorted(uit, key=lambda r: -r["vertoningen"])[:limiet]


def _gsc_onbenut(rijen: list[dict], limiet: int = 10) -> list[dict]:
    uit = [
        {"term": r["keys"][0], "vertoningen": r.get("impressions", 0),
         "positie": round(r.get("position", 0), 1)}
        for r in rijen
        if r.get("clicks", 0) == 0 and r.get("impressions", 0) >= 5 and r.get("position", 0) <= 30
    ]
    return sorted(uit, key=lambda r: -r["vertoningen"])[:limiet]


def _gsc_verschil(nu: list[dict], eerder: list[dict], omhoog: bool, limiet: int = 8) -> list[dict]:
    was = {r["keys"][0]: r for r in eerder}
    uit = []
    for r in nu:
        term = r["keys"][0]
        oud = was.get(term)
        verschil = r.get("impressions", 0) - (oud.get("impressions", 0) if oud else 0)
        if r.get("impressions", 0) < 3 and abs(verschil) < 3:
            continue
        uit.append({"term": term, "vertoningen": r.get("impressions", 0),
                    "verschil": verschil, "nieuw": oud is None})
    uit = [r for r in uit if (r["verschil"] > 0) == omhoog and r["verschil"] != 0]
    return sorted(uit, key=lambda r: -r["verschil"] if omhoog else r["verschil"])[:limiet]


def _gsc_weken(gsc, aantal: int = 8) -> list[dict]:
    """Klikken en vertoningen per week. Dit is het enige echte voortgangscijfer
    voor SEO: één week zegt niets, acht weken naast elkaar wel."""
    uit = []
    for i in range(aantal, 0, -1):
        start, eind = _dag(3 + i * 7), _dag(3 + (i - 1) * 7 + 1)
        try:
            rijen = gsc.query_window(["date"], start, eind, row_limit=10)
        except Exception:
            rijen = []
        uit.append({
            "week": start,
            "klikken": sum(r.get("clicks", 0) for r in rijen),
            "vertoningen": sum(r.get("impressions", 0) for r in rijen),
        })
    return uit


# ---------------------------------------------------------------------------
# Groei: gaat het de goede kant op?
# ---------------------------------------------------------------------------
def _omzet_per_maand(maanden: int = 6) -> list[dict]:
    """Wat is er echt binnengekomen per maand, uit de betaalde facturen van
    Stripe. Niet de huidige omzet doorgerekend, maar wat er stond."""
    if not settings.stripe_secret_key:
        return []
    vanaf = int((_nu() - timedelta(days=31 * maanden)).timestamp())
    per_maand: dict[str, float] = {}
    starting_after = None
    try:
        for _ in range(10):
            params = {"status": "paid", "limit": 100, "created[gte]": vanaf}
            if starting_after:
                params["starting_after"] = starting_after
            blok = _stripe_get("invoices", params)
            rijen = blok.get("data") or []
            for f in rijen:
                betaald = f.get("status_transitions", {}).get("paid_at") or f.get("created")
                if not betaald:
                    continue
                maand = datetime.fromtimestamp(betaald, timezone.utc).strftime("%Y-%m")
                per_maand[maand] = per_maand.get(maand, 0) + (f.get("amount_paid") or 0) / 100
            if not blok.get("has_more"):
                break
            starting_after = rijen[-1]["id"] if rijen else None
    except Exception as e:
        logger.warning("Omzetgeschiedenis mislukt: %s", e)
        return []
    return [{"maand": m, "bedrag": round(b, 2)} for m, b in sorted(per_maand.items())]


def _per_week(rijen: list[dict], veld: str, weken: int = 8) -> list[dict]:
    """Tel rijen per week op basis van een datumveld. Weken lopen terug vanaf nu,
    zodat 'deze week' altijd de laatste kolom is."""
    emmers = {i: 0 for i in range(weken)}
    for r in rijen:
        dt = _tijd(r.get(veld))
        if not dt:
            continue
        weg = (_nu() - dt).days // 7
        if 0 <= weg < weken:
            emmers[weg] += 1
    return [{"week": f"-{i}w", "aantal": emmers[i]} for i in range(weken - 1, -1, -1)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/kern")
def kern(user=Depends(get_current_user_full)):
    """Geld, klanten, techniek en koude mail. Alles hier komt uit Stripe of uit
    onze eigen database: snel genoeg om elke minuut te verversen."""
    _eigenaar(user)
    return {
        "tijd": _nu().isoformat(),
        "geld": _geld(),
        "klanten": _klanten(),
        "techniek": _techniek(),
        "mail": _mail(),
    }


@router.get("/groei")
def groei(user=Depends(get_current_user_full)):
    """Gaat het de goede kant op? Eén week zegt niets; dit zet acht weken en zes
    maanden naast elkaar. Vijf minuten cache — dit verandert niet per minuut."""
    _eigenaar(user)
    klaar = _uit_cache("groei", 300)
    if klaar:
        return klaar

    db = get_db()
    try:
        abos = execute_with_retry(db.table("subscriptions")
                                  .select("created_at, status")
                                  .gte("created_at", _iso(70))).data or []
    except Exception as e:
        logger.warning("Aanmeldingen per week mislukt: %s", e)
        abos = []
    try:
        nieuwe_advertenties = execute_with_retry(
            db.table("listings").select("created_at").gte("created_at", _iso(70))).data or []
    except Exception:
        nieuwe_advertenties = []
    try:
        verkopen = execute_with_retry(
            db.table("listings").select("sold_at").gte("sold_at", _iso(70))).data or []
    except Exception:
        verkopen = []

    uit = {
        "tijd": _nu().isoformat(),
        "aanmeldingen_per_week": _per_week(abos, "created_at"),
        "advertenties_per_week": _per_week(nieuwe_advertenties, "created_at"),
        "verkopen_per_week": _per_week(verkopen, "sold_at"),
        "omzet_per_maand": _omzet_per_maand(),
    }
    return _in_cache("groei", uit)


@router.get("/website")
def website(user=Depends(get_current_user_full)):
    """Bezoekers en zoekverkeer. Tien minuten cache: Google heeft dagquota, en
    Search Console loopt sowieso twee tot drie dagen achter — vaker opvragen
    levert letterlijk hetzelfde antwoord."""
    _eigenaar(user)
    klaar = _uit_cache("website", 600)
    if klaar:
        return klaar

    from backend.services import ga4, search_console as gsc

    uit: dict = {"tijd": _nu().isoformat()}

    proef = ga4.probe(_dag(7), _dag(1))
    if not proef.get("ok"):
        # Bewust niet stilzwijgend nul tonen. Een dashboard dat "0 bezoekers"
        # zegt terwijl de koppeling stuk is, is erger dan een leeg blok: je gaat
        # aan je website sleutelen om een probleem dat er niet is.
        uit["analytics"] = {"gekoppeld": False, "reden": proef.get("reden")}
    else:
        try:
            nu_start, nu_eind = _dag(7), _dag(1)
            eerder_start, eerder_eind = _dag(14), _dag(8)
            totalen = ga4.totals(nu_start, nu_eind) or {}
            eerder = ga4.totals(eerder_start, eerder_eind) or {}
            per_dag = ga4.sessions_by_day(_dag(29), _dag(0)) or {}
            sociaal: dict[str, int] = {}
            for bron in ga4.traffic_sources(nu_start, nu_eind) or []:
                platform = ga4.platform_of(str(bron.get("sessionSource") or ""))
                if platform:
                    sociaal[platform] = sociaal.get(platform, 0) + int(bron.get("sessions") or 0)
            uit["analytics"] = {
                "gekoppeld": True,
                "bezoeken_7d": int(totalen.get("sessions") or 0),
                "bezoeken_vorige_7d": int(eerder.get("sessions") or 0),
                "gebruikers_7d": int(totalen.get("activeUsers") or 0),
                "nieuw_7d": int(totalen.get("newUsers") or 0),
                "per_dag": [{"dag": d, "aantal": int(a)} for d, a in sorted(per_dag.items())],
                "landingspaginas": (ga4.top_landing_pages(nu_start, nu_eind, limit=10) or [])[:10],
                "kanalen": (ga4.channels(nu_start, nu_eind) or [])[:8],
                "social": sorted(({"platform": k, "bezoeken": v} for k, v in sociaal.items()),
                                 key=lambda r: -r["bezoeken"]),
            }
        except Exception as e:
            logger.warning("Analytics-blok mislukt: %s", e)
            uit["analytics"] = {"gekoppeld": False, "reden": f"Analytics gaf een fout: {type(e).__name__}"}

    if not gsc.is_configured():
        uit["zoekverkeer"] = {"gekoppeld": False, "reden": "Search Console niet gekoppeld"}
    else:
        try:
            def _som(rijen):
                return (sum(r.get("clicks", 0) for r in rijen),
                        sum(r.get("impressions", 0) for r in rijen))

            # GSC loopt achter, dus het venster begint drie dagen terug. Anders
            # vergelijk je een halfvolle week met een volle en lijkt alles te dalen.
            nu_rijen = gsc.query_window(["query"], _dag(10), _dag(3), row_limit=250)
            eerder_rijen = gsc.query_window(["query"], _dag(17), _dag(11), row_limit=250)
            paginas = gsc.query_window(["page"], _dag(10), _dag(3), row_limit=25)
            klikken, vertoningen = _som(nu_rijen)
            k_eerder, v_eerder = _som(eerder_rijen)
            uit["zoekverkeer"] = {
                "gekoppeld": True,
                "klikken": klikken,
                "klikken_vorige": k_eerder,
                "vertoningen": vertoningen,
                "vertoningen_vorige": v_eerder,
                "zoektermen": [
                    {"term": r["keys"][0], "klikken": r.get("clicks", 0),
                     "vertoningen": r.get("impressions", 0),
                     "positie": round(r.get("position", 0), 1)}
                    for r in sorted(nu_rijen, key=lambda r: -r.get("clicks", 0))[:12]
                ],
                "paginas": [
                    {"pagina": r["keys"][0], "klikken": r.get("clicks", 0),
                     "vertoningen": r.get("impressions", 0)}
                    for r in sorted(paginas, key=lambda r: -r.get("clicks", 0))[:10]
                ],
                "weken": _gsc_weken(gsc),
                "kansen": _gsc_kansen(nu_rijen),
                "onbenut": _gsc_onbenut(nu_rijen),
                "stijgers": _gsc_verschil(nu_rijen, eerder_rijen, omhoog=True),
                "dalers": _gsc_verschil(nu_rijen, eerder_rijen, omhoog=False),
            }
        except Exception as e:
            logger.warning("Search Console-blok mislukt: %s", e)
            uit["zoekverkeer"] = {"gekoppeld": False, "reden": f"Search Console gaf een fout: {type(e).__name__}"}

    return _in_cache("website", uit)


@router.get("/social")
def social(ververs: bool = False, user=Depends(get_current_user_full)):
    """Berichten en bereik per social kanaal. Dit haalt Apify aan en dat kost
    tegoed, dus zes uur cache en alleen op verzoek — nooit vanzelf bij de
    minuutverversing van het scherm."""
    _eigenaar(user)
    if not ververs:
        klaar = _uit_cache("social", 6 * 3600)
        if klaar:
            return klaar

    from backend.services import social_scrape

    if not social_scrape.is_configured():
        return {"gekoppeld": False, "reden": "Geen Apify-sleutel op de server"}
    try:
        data = social_scrape.weekly(_dag(7), _dag(0), limit_per_platform=15)
    except Exception as e:
        logger.warning("Social-blok mislukt: %s", e)
        return {"gekoppeld": False, "reden": f"Ophalen mislukt: {type(e).__name__}"}
    data["tijd"] = _nu().isoformat()
    return _in_cache("social", data)
