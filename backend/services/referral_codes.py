"""Wie heeft welke verwijscode.

Eén codetabel voor iedereen (zie scripts/sql/referrals.sql en
referrals_gebruikers.sql). Een code van Daniel aan een influencer heet
kind='creator' en levert geld op; een code van een klant heet kind='user',
heeft owner_user_id ingevuld en levert een gratis maand op.

Bewust dezelfde tabel: /r/CODE hoeft dan niet te gokken waar hij moet kijken, en
het koppelen bij het aanmelden werkt voor beide soorten ongewijzigd.
"""
from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timezone

from backend.config import settings
from backend.database import execute_with_retry, get_db

logger = logging.getLogger(__name__)

_CODE_MAX = 40
_CODE_MIN = 3
# Codes die nooit van een klant mogen worden: het zijn paden op de site of ze
# wekken de indruk dat Omnivaleur zelf de afzender is.
_VERBODEN = {
    "r", "api", "app", "admin", "beheer", "login", "register", "logout", "blog",
    "nl", "en", "index", "help", "support", "info", "pricing", "prijs", "terms",
    "privacy", "omnivaleur", "crosslist", "revaleur", "account", "billing",
    "checkout", "demo", "test", "www", "mail", "static", "assets", "sitemap",
    "robots", "marketplaces", "onboarding",
}
# Hoeveel eigen codes iemand mag hebben. Een hernoeming maakt een nieuwe code en
# laat de oude staan, zodat een al gedeelde link blijft werken; zonder bovengrens
# zou iemand de hele codenaamruimte kunnen opkopen.
# Merknamen mogen nergens in een klantcode voorkomen, ook niet als deel van een
# langer woord. Een link die eruitziet alsof hij van ons komt is een link
# waarmee je namens ons kunt spreken.
_MERKEN = ("omnivaleur", "revaleur", "crosslist", "support", "official", "admin")

MAX_CODES_PER_GEBRUIKER = 5


# ── Codes ────────────────────────────────────────────────────────────────────

def schoon_code(code: str | None) -> str | None:
    """Kort, kleine letters, cijfers, streepje. Al het andere weigeren we in
    plaats van op te schonen: een half opgeschoonde code koppelt stilletjes aan
    de verkeerde persoon."""
    if not code:
        return None
    code = code.strip().lower()
    if len(code) < _CODE_MIN or len(code) > _CODE_MAX:
        return None
    if not all(c.isalnum() or c in "-_" for c in code):
        return None
    if code in _VERBODEN:
        return None
    # Ook als deel van een langere code: omnivaleur.com/r/omnivaleur-support
    # leest als een officiële link van ons, en dat is precies wat iemand met
    # slechte bedoelingen zou kiezen.
    if any(merk in code for merk in _MERKEN):
        return None
    return code


def _basis_uit_email(email: str | None) -> str:
    """Een herkenbare start voor de persoonlijke code: het deel vóór de punt of
    het plusje in het e-mailadres. Herkenbaar deelt makkelijker dan een reeks
    willekeurige tekens."""
    lokaal = (email or "").split("@")[0].lower()
    eerste = re.split(r"[._+\-]", lokaal)[0]
    basis = re.sub(r"[^a-z0-9]", "", eerste)[:14]
    if len(basis) < _CODE_MIN or basis in _VERBODEN:
        basis = re.sub(r"[^a-z0-9]", "", lokaal)[:14]
    if len(basis) < _CODE_MIN or basis in _VERBODEN:
        basis = "friend"
    return basis


def _toeval(lengte: int = 4) -> str:
    # Geen i/l/1/o/0: die worden verkeerd overgetypt zodra iemand de code
    # voorleest of met de hand intikt.
    alfabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(random.choice(alfabet) for _ in range(lengte))


def _code_bestaat(db, code: str) -> bool:
    rij = execute_with_retry(db.table("referral_codes").select("code").eq("code", code).limit(1))
    return bool(rij.data)


def codes_van(user_id: str) -> list[dict]:
    """Alle codes van deze gebruiker, nieuwste eerst. De nieuwste is de code die
    de app laat zien; de oudere blijven werken zodat een al gedeelde link nooit
    doodloopt."""
    db = get_db()
    rij = execute_with_retry(
        db.table("referral_codes").select("code, created_at")
        .eq("owner_user_id", user_id).order("created_at", desc=True)
    )
    return rij.data or []


def zorg_voor_code(user_id: str, email: str | None) -> str:
    """De persoonlijke code van deze gebruiker; maakt hem aan als hij er nog niet
    is. Veilig om vaak aan te roepen."""
    db = get_db()
    bestaand = codes_van(user_id)
    if bestaand:
        return bestaand[0]["code"]

    basis = _basis_uit_email(email)
    # "friend" is de terugval voor een adres waar geen naam uit te halen valt.
    # Die mag nooit kaal vergeven worden: dan bezit de eerste de ene mooie
    # algemene link en krijgt de rest hem nooit meer.
    kaal_mag = basis != "friend"
    for poging in range(12):
        kandidaat = basis if (poging == 0 and kaal_mag) else f"{basis}-{_toeval(3 if poging < 6 else 5)}"
        if _code_bestaat(db, kandidaat):
            continue
        try:
            execute_with_retry(db.table("referral_codes").insert({
                "code": kandidaat,
                "creator_name": (email or "")[:120],
                "platform": "user",
                "kind": "user",
                "owner_user_id": user_id,
                # Een klantcode kost geen geld maar een maand. Zou hier de
                # standaard bounty blijven staan, dan telde de beheerpagina
                # commissie op voor iets wat nooit wordt uitbetaald.
                "bounty_cents": 0,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }))
            logger.info("Verwijscode %s aangemaakt voor %s", kandidaat, user_id)
            return kandidaat
        except Exception as e:
            # Twee schermen tegelijk open: de ander was net iets eerder. Dan is
            # zijn code de onze, dus opnieuw kijken.
            if "23505" in str(e) or "duplicate" in str(e).lower():
                opnieuw = codes_van(user_id)
                if opnieuw:
                    return opnieuw[0]["code"]
                continue
            raise
    raise RuntimeError("Kon geen vrije verwijscode vinden")


def kies_eigen_code(user_id: str, gewenst: str) -> str:
    """Een eigen naam voor de link. De oude code blijft actief en blijft naar
    dezelfde persoon wijzen, zodat een link die al in een appgroep staat blijft
    werken."""
    code = schoon_code(gewenst)
    if not code:
        raise ValueError(
            "Use 3 to 40 characters: letters, numbers, - or _. Some words are reserved."
        )
    db = get_db()
    bestaand = codes_van(user_id)
    if bestaand and bestaand[0]["code"] == code:
        return code
    if len(bestaand) >= MAX_CODES_PER_GEBRUIKER:
        raise ValueError("You have changed your link too often. Contact us if you need another one.")
    if _code_bestaat(db, code):
        raise ValueError("That link is already taken. Try another one.")
    try:
        execute_with_retry(db.table("referral_codes").insert({
            "code": code,
            "creator_name": "",
            "platform": "user",
            "kind": "user",
            "owner_user_id": user_id,
            "bounty_cents": 0,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception as e:
        if "23505" in str(e) or "duplicate" in str(e).lower():
            raise ValueError("That link is already taken. Try another one.")
        raise
    logger.info("Eigen verwijscode %s gekozen door %s", code, user_id)
    return code


def eigenaar_van_code(code: str) -> dict | None:
    """De rij uit referral_codes, of None. Geeft ook kind/owner_user_id terug,
    want daaraan zien we of dit een klantcode of een creatorcode is."""
    if not code:
        return None
    db = get_db()
    rij = execute_with_retry(
        db.table("referral_codes").select("code, kind, owner_user_id, active").eq("code", code).limit(1)
    )
    return (rij.data or [None])[0]


def link_voor(code: str) -> str:
    return f"{settings.app_url}/r/{code}"

