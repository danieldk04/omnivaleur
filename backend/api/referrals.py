"""Meetlaag voor influencer- en affiliate-samenwerkingen.

Elke creator krijgt een eigen code. De keten die we willen kunnen tellen:

    klik -> aanmelding -> proef -> betalend -> 60 dagen betalend -> commissie

Bewust ontwerp: de verwijzingstabel legt alleen vast WIE door WIE is
binnengekomen en WANNEER er voor het eerst betaald is. De huidige status komt
altijd vers uit `subscriptions`. Zo kan de meting niet uit de pas gaan lopen met
de werkelijkheid, wat wel gebeurt als je de status op twee plekken bijhoudt.

Commissie is pas verschuldigd als iemand 60 dagen betaald heeft en op dat moment
nog steeds betaalt. Dat is de bescherming tegen uitval: bij een klant die na een
maand opzegt wordt er niets uitgekeerd.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.config import settings
from backend.database import execute_with_retry, get_db
from backend.api.deps import get_current_user_full, is_owner_email as _is_owner_email

logger = logging.getLogger(__name__)

router = APIRouter(tags=["referrals"])

# Zolang iemand niet uitbetaald krijgt voor een klant die meteen weer weg is,
# blijft de bounty veilig. 60 dagen is de afspraak van 09-09-2026.
COMMISSIE_NA_DAGEN = 60
STANDAARD_BOUNTY_CENTS = 2500

_CODE_MAX = 40


def _schoon(code: str | None) -> str | None:
    """Codes zijn kort, kleine letters, cijfers, streepje. Al het andere weigeren
    we in plaats van op te schonen: een half opgeschoonde code koppelt stilletjes
    aan de verkeerde creator."""
    if not code:
        return None
    code = code.strip().lower()
    if not code or len(code) > _CODE_MAX:
        return None
    if not all(c.isalnum() or c in "-_" for c in code):
        return None
    return code


def registreer_verwijzing(user_id: str, code: str | None) -> None:
    """Koppelt een verse gebruiker aan een creatorcode. Mag het aanmelden nooit
    laten mislukken, dus alles wordt hier opgevangen en gelogd."""
    code = _schoon(code)
    if not code or not user_id:
        return
    try:
        db = get_db()
        bekend = execute_with_retry(
            db.table("referral_codes").select("code").eq("code", code).eq("active", True)
        )
        if not (bekend.data or []):
            logger.warning("Aanmelding met onbekende verwijscode %r, niet gekoppeld", code)
            return
        execute_with_retry(
            db.table("referrals").upsert({
                "user_id": user_id,
                "code": code,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="user_id")
        )
        logger.info("Verwijzing vastgelegd: %s <- %s", user_id, code)
    except Exception:
        logger.exception("Kon verwijzing niet vastleggen voor %s (%s)", user_id, code)


def stempel_eerste_betaling(user_id: str) -> None:
    """Zet first_paid_at zodra een verwezen gebruiker echt gaat betalen. Wordt
    vanuit de Stripe-webhook aangeroepen. Eén keer stempelen: een latere
    statuswijziging mag de klok niet opnieuw laten beginnen."""
    if not user_id:
        return
    try:
        db = get_db()
        rij = execute_with_retry(
            db.table("referrals").select("user_id, first_paid_at").eq("user_id", user_id)
        )
        data = rij.data or []
        if not data or data[0].get("first_paid_at"):
            return
        execute_with_retry(
            db.table("referrals").update({
                "first_paid_at": datetime.now(timezone.utc).isoformat()
            }).eq("user_id", user_id)
        )
        logger.info("Eerste betaling gestempeld voor verwezen gebruiker %s", user_id)
    except Exception:
        logger.exception("Kon eerste betaling niet stempelen voor %s", user_id)


@router.get("/r/{code}")
def volg_klik(code: str, request: Request) -> RedirectResponse:
    """De link die een creator deelt. Telt de klik en stuurt door naar de
    Nederlandse landingspagina met de code erin."""
    schoon = _schoon(code)
    doel = f"{settings.app_url}/nl.html"
    if not schoon:
        return RedirectResponse(url=doel, status_code=302)

    try:
        ip = (request.client.host if request.client else "") or ""
        db = get_db()
        execute_with_retry(db.table("referral_clicks").insert({
            "code": schoon,
            "ua": (request.headers.get("user-agent") or "")[:300],
            # Alleen een hash: we hoeven niemand te herkennen, alleen dubbele
            # kliks van hetzelfde apparaat te kunnen zien.
            "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:32] if ip else None,
        }))
    except Exception:
        # Een kapotte teller mag nooit de bezoeker tegenhouden.
        logger.exception("Kon klik niet loggen voor code %s", schoon)

    return RedirectResponse(url=f"{doel}?ref={schoon}", status_code=302)


class NieuweCode(BaseModel):
    code: str
    creator_name: str = ""
    platform: str = ""
    profile_url: str = ""
    bounty_cents: int = STANDAARD_BOUNTY_CENTS
    fee_paid_cents: int = 0


@router.post("/api/referrals/admin/code")
def maak_code(body: NieuweCode, user=Depends(get_current_user_full)):
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    code = _schoon(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="Ongeldige code: alleen letters, cijfers, - en _")
    db = get_db()
    execute_with_retry(db.table("referral_codes").upsert({
        "code": code,
        "creator_name": body.creator_name,
        "platform": body.platform,
        "profile_url": body.profile_url,
        "bounty_cents": body.bounty_cents,
        "fee_paid_cents": body.fee_paid_cents,
        "active": True,
    }, on_conflict="code"))
    return {"ok": True, "code": code, "link": f"{settings.app_url}/r/{code}"}


@router.get("/api/referrals/admin/overzicht")
def overzicht(user=Depends(get_current_user_full)):
    """Per creator de hele trechter plus wat het gekost heeft."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")

    db = get_db()
    try:
        codes = (execute_with_retry(db.table("referral_codes").select("*")).data) or []
        verwijzingen = (execute_with_retry(db.table("referrals").select("*")).data) or []
        kliks = (execute_with_retry(db.table("referral_clicks").select("code")).data) or []
    except Exception as e:
        # Niet stilletjes nullen tonen: een ontbrekende tabel ziet er anders uit
        # als "de campagne werkt niet" terwijl er nooit iets gemeten is.
        raise HTTPException(
            status_code=503,
            detail=f"Verwijzingstabellen niet leesbaar ({e}). Draai eerst scripts/sql/referrals.sql in Supabase.",
        )

    gebruikers = [v["user_id"] for v in verwijzingen]
    abos = {}
    if gebruikers:
        rijen = (execute_with_retry(
            db.table("subscriptions").select("user_id, status").in_("user_id", gebruikers)
        ).data) or []
        abos = {r["user_id"]: r.get("status") for r in rijen}

    klik_per_code: dict[str, int] = {}
    for k in kliks:
        klik_per_code[k["code"]] = klik_per_code.get(k["code"], 0) + 1

    nu = datetime.now(timezone.utc)
    betalend_nu = {"active", "payment_processing"}

    regels = []
    totaal = {"klikken": 0, "aanmeldingen": 0, "betalend": 0, "commissie_rijp": 0,
              "uitgegeven_cents": 0, "commissie_cents": 0}

    for c in codes:
        code = c["code"]
        mijn = [v for v in verwijzingen if v.get("code") == code]
        betalend = [v for v in mijn if abos.get(v["user_id"]) in betalend_nu]

        rijp = 0
        for v in betalend:
            eerste = v.get("first_paid_at")
            if not eerste:
                continue
            try:
                dt = datetime.fromisoformat(str(eerste).replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt + timedelta(days=COMMISSIE_NA_DAGEN) <= nu:
                rijp += 1

        bounty = c.get("bounty_cents") or STANDAARD_BOUNTY_CENTS
        fee = c.get("fee_paid_cents") or 0
        commissie = rijp * bounty
        uitgegeven = fee + commissie
        klikken = klik_per_code.get(code, 0)

        regels.append({
            "code": code,
            "creator_name": c.get("creator_name") or "",
            "platform": c.get("platform") or "",
            "profile_url": c.get("profile_url") or "",
            "link": f"{settings.app_url}/r/{code}",
            "klikken": klikken,
            "aanmeldingen": len(mijn),
            "in_proef": sum(1 for v in mijn if abos.get(v["user_id"]) == "trialing"),
            "betalend": len(betalend),
            "commissie_rijp": rijp,
            "vast_bedrag_eur": round(fee / 100, 2),
            "commissie_eur": round(commissie / 100, 2),
            "uitgegeven_eur": round(uitgegeven / 100, 2),
            # Kosten per betalende klant. Zonder klant is dat niet te delen, dan
            # is het bedrag zelf het antwoord op "wat heeft dit gekost".
            "cac_eur": round(uitgegeven / 100 / len(betalend), 2) if betalend else None,
            "klik_naar_aanmelding": round(len(mijn) / klikken * 100, 1) if klikken else None,
        })

        totaal["klikken"] += klikken
        totaal["aanmeldingen"] += len(mijn)
        totaal["betalend"] += len(betalend)
        totaal["commissie_rijp"] += rijp
        totaal["uitgegeven_cents"] += uitgegeven
        totaal["commissie_cents"] += commissie

    regels.sort(key=lambda r: (-r["betalend"], -r["aanmeldingen"], -r["klikken"]))

    return {
        "creators": regels,
        "totaal": {
            "klikken": totaal["klikken"],
            "aanmeldingen": totaal["aanmeldingen"],
            "betalend": totaal["betalend"],
            "commissie_rijp": totaal["commissie_rijp"],
            "uitgegeven_eur": round(totaal["uitgegeven_cents"] / 100, 2),
            "commissie_eur": round(totaal["commissie_cents"] / 100, 2),
            "cac_eur": (round(totaal["uitgegeven_cents"] / 100 / totaal["betalend"], 2)
                        if totaal["betalend"] else None),
        },
        "commissie_na_dagen": COMMISSIE_NA_DAGEN,
    }
