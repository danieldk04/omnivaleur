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

import difflib
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


def _telling(tabel: str, **filters) -> int | None:
    """Aantal rijen zonder ze op te halen, of None als we het niet mogen weten.

    Zonder count='exact' haalde dit scherm bij elke verversing tienduizenden
    rijen op om er één getal van te maken.

    WAAROM None EN GEEN 0 (29-08-2026). Op de server draait dit op de publieke
    sleutel, en die mag jobs/listings/import_candidates niet lezen. Dat liep in
    de except hieronder en werd een nul — dus stond er "0 advertenties live" en
    "0 imports open" op het scherm terwijl het er 8.916 en 5.260 waren. Een nul
    is een bewering; niet mogen kijken is iets anders, en dat hoort het scherm te
    zeggen in plaats van iets rustgevends te verzinnen.
    """
    try:
        # Géén `head=True`: de clientversie in requirements.txt (postgrest
        # 0.16.11) kent die niet en gooit een TypeError, die hier in de except
        # belandt — dan staat er "onbekend" op het beheerscherm terwijl de
        # database gewoon antwoordt. De telling komt uit de kop, dus één rij
        # ophalen is genoeg. Zie docs/kennisbank.md, "SDK-pin valstrik".
        q = get_db().table(tabel).select("*", count="exact")
        for kolom, waarde in filters.items():
            if kolom.endswith("__gte"):
                q = q.gte(kolom[:-5], waarde)
            elif kolom.endswith("__lt"):
                q = q.lt(kolom[:-4], waarde)
            elif kolom.endswith("__not_null"):
                q = q.not_.is_(kolom[:-10], "null")
            else:
                q = q.eq(kolom, waarde)
        return execute_with_retry(q.limit(1)).count or 0
    except Exception as e:
        logger.warning("Tellen mislukt op %s (%s): %s", tabel, filters, e)
        return None


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
        "open_tracking_reden": "Gemeten op mail 2, mail 3 en de opvolgmails — niet op mail 1.",
        "opens": _mail_opens(list(state.keys())),
        "lagen": _mail_lagen(state),
        "soorten": _mail_soorten(state),
        "advies": _mail_advies(),
        "leren": _mail_leren(),
        "fouten_vandaag": (_leadgen_lezen("mail_plan") or {}).get("fouten") or [],
    }


def _open_tellingen() -> dict[str, set]:
    """Per laag de adressen die die mail geopend hebben. Twee vormen: de oude
    (adres → telling, altijd een opvolgmail) en de nieuwe (adres → laag →
    telling). Zie backend/api/tracking.py."""
    per_laag: dict[str, set] = {}
    for adres, waarde in (_leadgen_lezen("mail_opens") or {}).items():
        if not isinstance(waarde, dict):
            continue
        if "aantal" in waarde:
            per_laag.setdefault("opvolg", set()).add(adres)
            continue
        for laag in waarde:
            per_laag.setdefault(laag, set()).add(adres)
    return per_laag


def _welke_beurt(st: dict, binnen: float | None) -> str:
    """Welke mail stond er als laatste tegenover deze reactie? Zelfde regel als
    _welke_beurt in scripts/leadgen_mail.py — de laatste mail die vóór het
    antwoord verstuurd is."""
    verstuurd = st.get("verstuurd") or []
    if not verstuurd:
        return "?"
    if binnen is None:
        return str(verstuurd[-1].get("beurt") or "?")
    laatste = "?"
    for m in verstuurd:
        try:
            op = datetime.fromisoformat(m["op"]).timestamp()
        except Exception:
            continue
        if op <= binnen:
            laatste = str(m.get("beurt") or "?")
    return laatste


# Vanaf dit moment dragen mail 2 en 3 een meetpixel (zie _open_pixel_html in
# scripts/leadgen_mail.py). Alles daarvóór is per definitie ongemeten.
_PIXEL_VANAF = "2026-08-27T13:00:00"

_LAAGNAMEN = {"mail1": "Mail 1 — eerste contact",
              "mail2": "Mail 2 — eerste opvolging",
              "mail3": "Mail 3 — laatste bericht"}


def _mail_lagen(state: dict) -> list[dict]:
    """De kernvraag van dit dashboard: welke van de drie teksten opent een
    gesprek? Een reactie hoort bij de mail die er als laatste tegenover stond."""
    opens = _open_tellingen()
    # Sinds wanneer draagt een mail een pixel? Alles wat daarvóór verstuurd is
    # kán niet gemeten zijn, en meetellen in de noemer maakt van "nog niet
    # gemeten" een "niemand opent" — precies de verkeerde conclusie.
    gemeten_vanaf = _leadgen_lezen("mail_opens_vanaf") or _PIXEL_VANAF
    uit = []
    for sleutel, naam in _LAAGNAMEN.items():
        rij = {"laag": sleutel, "naam": naam, "verstuurd": 0, "meetbaar": 0,
               "reacties": 0, "warm": 0, "afwijzing": 0, "concurrent": 0, "afmelding": 0}
        for st in state.values():
            for m in (st.get("verstuurd") or []):
                if isinstance(m, dict) and m.get("beurt") == sleutel:
                    rij["verstuurd"] += 1
                    if str(m.get("op") or "") >= gemeten_vanaf:
                        rij["meetbaar"] += 1
            if st.get("beantwoord"):
                try:
                    binnen = datetime.fromisoformat(st["beantwoord"]).timestamp()
                except Exception:
                    binnen = None
                if _welke_beurt(st, binnen) == sleutel:
                    rij["reacties"] += 1
                    soort = st.get("soort")
                    if soort in rij:
                        rij[soort] += 1
        rij["reactie_pct"] = (round(100 * rij["reacties"] / rij["verstuurd"], 1)
                              if rij["verstuurd"] else 0)
        geopend = len(opens.get(sleutel, ()))
        rij["geopend"] = geopend
        # Mail 1 draagt bewust nooit een pixel. Mail 2 en 3 pas sinds de pixel
        # erin zit; is er sindsdien niets verstuurd, dan is er niets te melden.
        rij["open_pct"] = (round(100 * geopend / rij["meetbaar"], 1)
                           if sleutel != "mail1" and rij["meetbaar"] else None)
        rij["open_reden"] = ("Mail 1 blijft bewust zonder meetpixel." if sleutel == "mail1"
                             else ("Nog niets verstuurd sinds de meting aanstaat."
                                   if not rij["meetbaar"] else ""))
        uit.append(rij)
    # Reacties van mensen die Daniel zelf mailde horen bij geen enkele laag.
    # Zonder deze regel tellen de kolommen niet op tot het totaal erboven, en
    # dan gaat iemand terecht twijfelen aan de rest van het scherm.
    los = {"laag": "?", "naam": "Buiten de campagne om", "verstuurd": 0, "meetbaar": 0,
           "reacties": 0, "warm": 0, "afwijzing": 0, "concurrent": 0, "afmelding": 0,
           "reactie_pct": 0, "geopend": 0, "open_pct": None,
           "open_reden": "Door jou zelf gemaild, buiten de machine om."}
    for st in state.values():
        if not st.get("beantwoord"):
            continue
        try:
            binnen = datetime.fromisoformat(st["beantwoord"]).timestamp()
        except Exception:
            binnen = None
        if _welke_beurt(st, binnen) not in _LAAGNAMEN:
            los["reacties"] += 1
            if st.get("soort") in los:
                los[st.get("soort")] += 1
    if los["reacties"]:
        uit.append(los)
    return uit


def _mail_soorten(state: dict) -> list[dict]:
    """De verdeling van alle reacties — de basis voor het cirkeldiagram."""
    telling: dict[str, int] = {}
    for st in state.values():
        if st.get("beantwoord"):
            telling[st.get("soort") or "onbekend"] = telling.get(st.get("soort") or "onbekend", 0) + 1
    labels = {"warm": "Warm / interesse", "afwijzing": "Geen interesse",
              "concurrent": "Gebruikt al iets", "afmelding": "Afgemeld",
              "onbekend": "Onbekend"}
    return [{"soort": k, "naam": labels.get(k, k), "aantal": v}
            for k, v in sorted(telling.items(), key=lambda kv: -kv[1])]


def _mail_opens(adressen: list[str]) -> dict:
    opens = _leadgen_lezen("mail_opens") or {}
    gemeten = [a for a in adressen if a in opens]
    totaal = 0
    for waarde in opens.values():
        if not isinstance(waarde, dict):
            continue
        if "aantal" in waarde:
            totaal += waarde.get("aantal", 0)
        else:
            totaal += sum(v.get("aantal", 0) for v in waarde.values() if isinstance(v, dict))
    return {"adressen": len(gemeten), "totaal_geopend": totaal}


_CITAAT_SPLITSER = re.compile(r"\n\s*(?:Op .{0,60}schreef|Van:|-----Oorspronkelijk)")


def _zonder_citaat(t: str) -> str:
    """Zelfde afkap als _kern() in scripts/leadgen_mail.py: alleen de eigen
    tekst, zonder het geciteerde gesprek eronder — anders toont de kaart
    dezelfde quote twee keer en is niet in één oogopslag te zien wát er
    veranderd is."""
    return _CITAAT_SPLITSER.split(t or "", maxsplit=1)[0].strip()


_PATROON_REGEL = re.compile(r"^\s*(\d+)\s*\|\s*([^|]{2,60}?)\s*\|\s*(.+?)\s*$")


def _mail_advies() -> dict:
    """De analyse, met de PATRONEN-regels apart zodat het scherm er balken van
    kan tekenen in plaats van nog een lap tekst. Valt de opmaak tegen (oudere
    analyse, of het model week af), dan blijft de tekst gewoon staan — liever
    leesbaar dan weg."""
    advies = _leadgen_lezen("mail_advies") or {}
    tekst = advies.get("tekst") or ""
    if not tekst:
        return advies
    patronen, rest, in_patronen = [], [], False
    for regel in tekst.splitlines():
        kaal = regel.strip()
        if kaal in ("PATRONEN", "WAT WERKT", "AANBEVELINGEN"):
            in_patronen = kaal == "PATRONEN"
            if not in_patronen:
                rest.append(regel)
            continue
        gevonden = _PATROON_REGEL.match(regel) if in_patronen else None
        if gevonden:
            patronen.append({"aantal": int(gevonden.group(1)),
                             "naam": gevonden.group(2), "uitleg": gevonden.group(3)})
        elif not in_patronen or kaal:
            rest.append(regel)
    return {**advies, "patronen": patronen, "tekst": "\n".join(rest).strip()}


def _overeenkomst(a: str, b: str) -> float:
    """Hoeveel procent van het voorstel bleef staan, 0-100.

    Het oude cijfer was ja/nee: één toegevoegde smiley telde net zo zwaar als
    een volledig herschreven mail, en dus stond er 0% terwijl de voorstellen
    vrijwel woordelijk werden verstuurd. Dat leest als "waardeloos" terwijl het
    tegendeel waar is. Dit meet hoevéél er bleef staan."""
    a, b = re.sub(r"\s+", " ", a or "").strip().lower(), re.sub(r"\s+", " ", b or "").strip().lower()
    if not a or not b:
        return 0.0
    return round(100 * difflib.SequenceMatcher(None, a, b).ratio(), 1)


def _mail_leren() -> dict:
    """Wat Daniel zelf van de voorstellen maakt, is de enige echte leerbron: hij
    verandert alleen iets als het voorstel niet goed genoeg was. Zie
    scripts/leadgen_mail.py, _onthoud_concept/_leer_van_verzonden."""
    log = _leadgen_lezen("leerlog") or []
    afgerond = [x for x in log if x.get("verstuurd")]
    for x in afgerond:
        x["_gelijk"] = _overeenkomst(_zonder_citaat(x.get("voorstel")),
                                     _zonder_citaat(x.get("verstuurd")))
    # Onder de 90% is er echt iets herschreven; daarboven gaat het om een woord,
    # een naam of een smiley — dat is bijschaven, geen afkeuring.
    herschreven = [x for x in afgerond if x["_gelijk"] < 90]
    recent = sorted(afgerond, key=lambda x: x.get("op", ""), reverse=True)[:5]
    return {
        "totaal": len(afgerond),
        "aangepast": len(herschreven),
        "ongewijzigd_pct": (round(sum(x["_gelijk"] for x in afgerond) / len(afgerond), 1)
                            if afgerond else None),
        "recent": [{"adres": x.get("adres"), "op": x.get("op"),
                    "gelijk": x["_gelijk"],
                    "aangepast": x["_gelijk"] < 90,
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


# ---------------------------------------------------------------------------
# De klantenservicemedewerker. Wat er in de post speelt, wat er voor Daniel
# ligt, en welke storingen terugkomen. Gevuld door scripts/mail_analyse.py.
#
# WAAROM DIT ER IS. De rolverdeling ligt vast (zie docs/team-notes.md): Daniel is
# CEO en hoort geen mail te lezen om te weten wat er speelt. Dit scherm is wat
# hij in plaats daarvan opent.
# ---------------------------------------------------------------------------
@router.get("/klantenservice")
def klantenservice(user=Depends(get_current_user_full)):
    _eigenaar(user)
    analyses = _leadgen_lezen("mail_analyse")
    if analyses is None:
        return {"gekoppeld": False,
                "reden": "Nog geen beoordeelde post (leadgen_opslag/mail_analyse)"}
    signalen = _leadgen_lezen("bug_signalen") or {}
    lijst = _leadgen_lezen("mail_escalaties") or []
    starter = _starter_stand(signalen)

    grens = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    recent = [r for r in analyses.values() if (r.get("wanneer") or "") >= grens]

    def tel(veld: str, waar=lambda r: True) -> dict:
        uit: dict[str, int] = {}
        for r in recent:
            if not waar(r):
                continue
            k = r.get(veld) or "overig"
            uit[k] = uit.get(k, 0) + 1
        return dict(sorted(uit.items(), key=lambda kv: -kv[1])[:12])

    binnen = [r for r in recent if r.get("richting") == "in"]
    return {
        "gekoppeld": True,
        "berichten_14d": len(recent),
        "binnen_14d": len(binnen),
        "uit_14d": len(recent) - len(binnen),
        "van_klanten": sum(1 for r in binnen if r.get("klant")),
        "themas": tel("thema", lambda r: r.get("richting") == "in"),
        "stemming": tel("stemming", lambda r: r.get("richting") == "in"),
        # ALLEEN WAT ER ÉCHT LIGT (31-08-2026). Hier stonden de laatste 25
        # niet-afgehandelde escalaties, wat in de praktijk een muur van 25
        # regels opleverde waarin de urgente tussen de weken oude verdween.
        # Daniel over dit scherm: "kopje marketing en werkplaats zijn een
        # chaos." Een lijst die alles toont, toont niets.
        "escalaties": _escalaties_die_er_toe_doen(lijst),
        "escalaties_ouder": max(0, len([e for e in lijst if not e.get("afgehandeld")])
                                - len(_escalaties_die_er_toe_doen(lijst))),
        "storingen": sorted(
            [{"sleutel": k, "melders": len(v.get("melders") or []),
              "omschrijving": v.get("omschrijving", ""), "status": v.get("status", "open"),
              "laatst": (v.get("laatst") or "")[:10],
              "moet_zeker": bool(v.get("moet_zeker")),
              # `reden` hoort bij verlopen/afgewezen, `uitleg` bij opgelost.
              # Ze door elkaar halen laat een uitgedoofde melding lezen als een
              # reparatie, en dat is precies het verschil dat ertoe doet.
              "reden": v.get("reden", ""),
              "uitleg": v.get("uitleg", "")}
             for k, v in signalen.items()],
            key=lambda s: (s["status"] != "open", not s["moet_zeker"],
                           -s["melders"], s["laatst"]))[:25],
        "storingen_totaal": {
            soort: sum(1 for v in signalen.values() if v.get("status", "open") == soort)
            for soort in ("open", "opgelost", "verlopen", "afgewezen")},
        "starter": starter,
    }


# Twee weken. Wat langer dan dat blijft liggen is geen taak meer maar een
# aantekening, en die hoort niet bovenaan het scherm te schreeuwen.
ESCALATIE_DAGEN = 14


def _escalaties_die_er_toe_doen(lijst: list) -> list:
    """De openstaande escalaties van de afgelopen twee weken, urgentste eerst."""
    grens = (datetime.now(timezone.utc) - timedelta(days=ESCALATIE_DAGEN)).isoformat()
    open_ = [e for e in lijst if not e.get("afgehandeld")]
    vers = [e for e in open_ if (e.get("wanneer") or "") >= grens]
    # Geld en vertrek eerst: dat zijn de twee die geld kosten als ze blijven
    # liggen. De rest op volgorde van binnenkomst, nieuwste boven.
    rang = {"vertrek": 0, "geld": 1, "storing_bij_meerderen": 2}
    return sorted(vers, key=lambda e: (rang.get(e.get("escalatie"), 3),
                                       -(len(e.get("wanneer") or ""))))[:12]


# ---------------------------------------------------------------------------
# De werkplaats. Wat de developer doet, voor wie, en waarom — plus de lijn
# tussen de klantenservice en de developer, van melding tot bericht terug.
#
# WAAROM DIT ER IS. De rolverdeling ligt vast: de mailagent en Claude Code
# praten onderling en storen Daniel alleen als het echt bij hem hoort. Dat werkt
# alleen als hij kán zien wat die twee doen zonder het te vragen. Dit scherm is
# dat venster; het verving het oude tabblad Systeem, dat alleen losse tellers
# liet zien. Die tellers staan er nog, maar onderaan.
# ---------------------------------------------------------------------------

# Hoe lang een sessie hoogstens hoort te draaien. Staat hij daarna nog op
# "gestart", dan is hij niet aan het werk maar vastgelopen. De server kan geen
# procesnummer op Daniels Mac nakijken, dus dit is hier het enige houvast.
# Gelijk aan MAX_MINUTEN in scripts/dev_starter.py.
SESSIE_MAX_MINUTEN = 90
# Zo lang wacht de starter na een sessie die meteen afsloeg, voor hij het weer
# probeert. Gelijk aan HERSTELPAUZE_MINUTEN in scripts/dev_starter.py.
STARTER_HERSTELPAUZE_MINUTEN = 60


def _minuten_sinds(waarde) -> int | None:
    if not waarde:
        return None
    try:
        toen = datetime.fromisoformat(str(waarde))
    except ValueError:
        return None
    if toen.tzinfo is None:
        toen = toen.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - toen).total_seconds() // 60)


def _storing_rij(sleutel: str, v: dict, sessie: dict | None) -> dict:
    """Eén storing met de hele lijn eromheen: wie, waarom, wat ermee gebeurd is.

    Bewust dezelfde vorm voor een wachtende en een afgehandelde storing. Zonder
    de melder en de reden is een storingssleutel een woord zonder verhaal, en
    dan kan Daniel niet zien of het werk over de juiste dingen gaat.
    """
    return {
        "sleutel": sleutel,
        "omschrijving": v.get("omschrijving", ""),
        "melders": v.get("melders") or [],
        "waarom": v.get("waarom_zeker") or [],
        "voorrang": bool(v.get("moet_zeker")),
        "eerst": (v.get("eerst") or "")[:10],
        "laatst": (v.get("laatst") or "")[:10],
        "status": v.get("status", "open"),
        "uitleg": v.get("uitleg") or v.get("reden") or "",
        # Apart van `uitleg`, want het verschil is wat het scherm moet laten
        # zien: `uitleg` hoort bij een reparatie waar de klant bericht over
        # krijgt, `reden` bij een melding die is afgewezen of vanzelf uitgedoofd
        # en waar juist NIEMAND bericht over krijgt.
        "reden": v.get("reden") or "",
        "klaar_op": (v.get("gerepareerd_op") or v.get("afgewezen_op")
                     or v.get("verlopen_op") or ""),
        # Wie er bericht over kreeg. Nul terwijl het wél is opgelost betekent dat
        # de klantenservice het concept nog moet klaarzetten — zichtbare
        # informatie, geen detail.
        "bericht_naar": len(v.get("bericht_verstuurd") or []),
        "opgepakt_op": str((sessie or {}).get("gestart", "")),
        "sessie": (sessie or {}).get("status", ""),
        # Waarom een sessie niets heeft opgeleverd. Zonder dit staat de reden in
        # een logboek dat niemand opent; zo stopten er op 29-08-2026 drie sessies
        # op de maandlimiet zonder dat het ergens te zien was.
        "sessie_mislukt": (sessie or {}).get("mislukt", ""),
    }


def _tijdlijn(signalen: dict, sessies: dict, escalaties: list) -> list[dict]:
    """De exacte communicatie tussen de klantenservice en de developer, op tijd.

    Een operationeel scherm hoort te laten zien wat er NU gebeurt en wat er net
    gebeurd is, niet alleen een eindstand. Zonder deze lijst kun je wel zien dat
    een storing is opgelost, maar niet dat hij drie uur eerder is doorgegeven, om
    kwart over twee is opgepakt en om tien voor drie is teruggemeld. Die volgorde
    is precies wat er te controleren valt.

    Alles wordt afgeleid uit de administratie die er al is — geen nieuwe opslag.
    """
    uit: list[dict] = []

    def zet(wanneer, van, naar, wat, sleutel="", extra=""):
        if wanneer:
            uit.append({"wanneer": str(wanneer), "van": van, "naar": naar,
                        "wat": wat, "sleutel": sleutel, "extra": extra})

    for sleutel, v in signalen.items():
        melders = v.get("melders") or []
        zet(v.get("laatst"), "klant", "klantenservice",
            f"gemeld door {', '.join(melders[:2]) or 'onbekend'}"
            + (f" +{len(melders) - 2}" if len(melders) > 2 else ""),
            sleutel, v.get("omschrijving", ""))
        if v.get("moet_zeker"):
            zet(v.get("gemeld_als_patroon") or v.get("laatst"), "klantenservice", "developer",
                "met voorrang doorgegeven", sleutel,
                "; ".join(v.get("waarom_zeker") or []))
        ses = sessies.get(sleutel) or {}
        zet(ses.get("gestart"), "developer", "developer",
            "sessie gestart" if not ses.get("mislukt") else "sessie sloeg af voor hij begon",
            sleutel, ses.get("mislukt", ""))
        if v.get("status") == "opgelost":
            zet(v.get("gerepareerd_op"), "developer", "klantenservice",
                "teruggemeld als opgelost", sleutel, v.get("uitleg", ""))
        elif v.get("status") == "afgewezen":
            zet(v.get("afgewezen_op"), "developer", "klantenservice",
                "geen storing, niet gerepareerd", sleutel, v.get("reden", ""))
        if v.get("bericht_verstuurd"):
            zet(v.get("gerepareerd_op"), "klantenservice", "klant",
                f"concept klaargezet voor {', '.join(v['bericht_verstuurd'][:2])}", sleutel)

    # In gewone taal. "kan_niet_onderbouwen" met liggende streepjes is jargon uit
    # de code; op dit scherm hoort te staan wat het betekent.
    reden_naam = {"geld": "gaat over geld", "vertrek": "dreigt te stoppen",
                  "storing_bij_meerderen": "meerdere mensen, zelfde storing",
                  "kan_niet_onderbouwen": "hier heb ik geen antwoord op"}
    for e in escalaties:
        if not e.get("afgehandeld"):
            soort = e.get("escalatie", "aandacht")
            zet(e.get("gezien_op") or e.get("wanneer"), "klantenservice", "Daniel",
                f"{reden_naam.get(soort, soort)} — {e.get('adres', '')}",
                "", e.get("samenvatting", ""))

    uit.sort(key=lambda r: r["wanneer"], reverse=True)
    return uit[:30]


def _voor_jou(signalen: dict, escalaties: list, starter: dict, probleem: str) -> list[dict]:
    """Wat er op DIT moment van Daniel wordt gevraagd, en niets anders.

    Expliciet eigenaarschap is het verschil tussen een scherm dat informeert en
    een scherm waar je iets mee doet. Alles wat de klantenservice of de developer
    zelf afhandelt hoort hier dus NIET te staan.
    """
    lijst = []
    for e in escalaties:
        if e.get("afgehandeld"):
            continue
        # Ging de escalatie over een storing die intussen is gerepareerd, dan is
        # er voor Daniel niets meer te doen. Nagemeten op 29-08-2026: vier van de
        # twaalf punten op zijn lijst waren al opgelost — precies de manier
        # waarop zo'n lijst zijn waarde verliest.
        sleutel = e.get("bug_sleutel") or ""
        if sleutel and (signalen.get(sleutel) or {}).get("status") in ("opgelost", "afgewezen"):
            continue
        lijst.append({"soort": e.get("escalatie", "aandacht"), "wie": e.get("adres", ""),
                      "wat": e.get("samenvatting", "")})
    # Iemand die bericht hoort te krijgen, maar bij wie al post klaarligt: er gaat
    # nooit twee mail tegelijk naar dezelfde persoon, dus die wacht op Daniel.
    # Per PERSOON gebundeld, niet per storing: vier losse regels voor dezelfde
    # man met dezelfde oorzaak is vier keer dezelfde actie.
    wachtenden: dict[str, list[str]] = {}
    for sleutel, v in signalen.items():
        if v.get("status") != "opgelost":
            continue
        for adres in (v.get("melders") or []):
            if adres not in (v.get("bericht_verstuurd") or []):
                wachtenden.setdefault(adres, []).append(sleutel)
    for adres, sleutels in wachtenden.items():
        wat = (f"{len(sleutels)} berichten wachten" if len(sleutels) > 1
               else "een bericht wacht")
        lijst.append({"soort": "concept", "wie": adres,
                      "wat": f"{wat} op je vorige mail aan hem; daarna gaat het vanzelf "
                             f"klaarstaan ({', '.join(s.replace('-', ' ') for s in sleutels[:3])})"})
    if probleem:
        lijst.append({"soort": "machine", "wie": "de developer", "wat": probleem})
    if starter.get("waarschuwing"):
        lijst.append({"soort": "machine", "wie": "de starter", "wat": starter["waarschuwing"]})
    # Geld en vertrek bovenaan: dat is de volgorde waarin Daniel zelf heeft
    # gekozen gestoord te worden (docs/team-notes.md, 29-08-2026).
    orde = {"machine": 0, "geld": 1, "vertrek": 2, "concept": 3}
    lijst.sort(key=lambda a: orde.get(a["soort"], 4))
    return lijst


@router.get("/werkplaats")
def werkplaats(user=Depends(get_current_user_full)):
    _eigenaar(user)
    signalen = _leadgen_lezen("bug_signalen")
    if signalen is None:
        return {"gekoppeld": False,
                "reden": "Nog geen storingen doorgegeven (leadgen_opslag/bug_signalen)"}
    sessies = _leadgen_lezen("dev_sessies") or {}

    bezig = None
    for sleutel, ses in sessies.items():
        minuten = _minuten_sinds(ses.get("gestart"))
        if ses.get("status") != "gestart" or minuten is None or minuten > SESSIE_MAX_MINUTEN:
            continue
        # De starter zet een sessie pas op "afgerond" bij zijn volgende ronde,
        # tien minuten later. Heeft de storing intussen al een terugmelding, dan
        # is het werk klaar en stond hier tot tien minuten lang "aan het werk"
        # boven een kaart die de reparatie al beschreef.
        if (signalen.get(sleutel) or {}).get("status") in (
                "opgelost", "afgewezen", "verlopen"):
            continue
        bezig = {**_storing_rij(sleutel, signalen.get(sleutel) or {}, ses), "minuten": minuten}
        break

    wachtrij, gedaan, overig = [], [], 0
    for sleutel, v in signalen.items():
        if bezig and sleutel == bezig["sleutel"]:
            continue
        rij = _storing_rij(sleutel, v, sessies.get(sleutel))
        # `verlopen` hoort hier bij het afgehandelde werk. Zonder dat viel een
        # uitgedoofde melding in "overig", en dan leest hij als iets dat nog
        # wacht terwijl er juist bewust niets meer mee gebeurt.
        if v.get("status") in ("opgelost", "afgewezen", "verlopen"):
            gedaan.append(rij)
        elif v.get("moet_zeker"):
            wachtrij.append(rij)
        else:
            overig += 1
    wachtrij.sort(key=lambda r: (-len(r["melders"]), r["laatst"]))
    gedaan.sort(key=lambda r: r["klaar_op"], reverse=True)

    # Een sessie die niets opleverde is geen detail — maar hij mag ook niet
    # blijven staan als hij allang voorbij is. De starter wacht een uur en
    # probeert het dan opnieuw; daarna is de melding niet meer waar, en een
    # waarschuwing die niet meer waar is leert je hem te negeren.
    mislukt = sorted((x for x in sessies.values() if x.get("mislukt")),
                     key=lambda x: str(x.get("gestart", "")))
    probleem = ""
    if mislukt:
        wacht = _minuten_sinds(mislukt[-1].get("gestart"))
        if wacht is not None and wacht < STARTER_HERSTELPAUZE_MINUTEN:
            probleem = mislukt[-1].get("mislukt", "")
    escalaties = _leadgen_lezen("mail_escalaties") or []
    starter = _starter_stand(signalen)
    return {
        "gekoppeld": True,
        "bezig": bezig,
        "tijdlijn": _tijdlijn(signalen, sessies, escalaties),
        "voor_jou": _voor_jou(signalen, escalaties, starter, probleem),
        "nu": datetime.now(timezone.utc).isoformat(),
        "wachtrij": wachtrij[:15],
        "gedaan": gedaan[:15],
        "overig_open": overig,
        "sessie_probleem": probleem,
        "starter": starter,
    }


def _starter_stand(signalen: dict) -> dict:
    """Draait de automatische developer-starter nog?

    WAAROM DIT HIER STAAT. De starter draait op Daniels Mac als LaunchAgent, en
    macOS blokkeert een achtergrondtaak standaard de toegang tot ~/Documents —
    zonder een enkele foutmelding op een plek die iemand leest. Dezelfde val
    heeft de koude-mailmachine op 11-08-2026 een halve dag stilgelegd. Een
    starter die stil kan vallen zonder dat iemand het merkt is geen starter.

    Hij schrijft daarom bij elke ronde een hartslag weg. Blijft die uit terwijl
    er werk klaarstaat, dan staat dat hier — op het scherm dat Daniel toch al
    opent.
    """
    hartslag = _leadgen_lezen("dev_starter_hartslag") or {}
    wachtend = sum(1 for v in signalen.values()
                   if v.get("status") == "open" and v.get("moet_zeker"))
    laatst = hartslag.get("wanneer") or ""
    stil_minuten = None
    if laatst:
        try:
            stil_minuten = int((datetime.now(timezone.utc)
                                - datetime.fromisoformat(laatst)).total_seconds() // 60)
        except ValueError:
            stil_minuten = None
    # Hij hoort elke tien minuten langs te komen. Een uur stilte is geen toeval.
    stil = stil_minuten is None or stil_minuten > 60
    return {
        "laatste_ronde": laatst,
        "stil_minuten": stil_minuten,
        "wacht_op_sessie": wachtend,
        "waarschuwing": (
            "De automatische starter heeft zich niet gemeld. Meestal blokkeert macOS "
            "de toegang tot de projectmap: Systeeminstellingen > Privacy en beveiliging "
            "> Volledige schijftoegang, en zet /bin/zsh erbij."
        ) if stil and wachtend else "",
    }
