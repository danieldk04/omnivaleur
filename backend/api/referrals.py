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
from backend.api.deps import get_current_user_full
from backend.services.billing import is_owner_email as _is_owner_email
from backend.services.referral_codes import (
    codes_van,
    kies_eigen_code,
    link_voor,
    schoon_code,
    zorg_voor_code,
)
from backend.services.referral_mail import email_van, maskeer
from backend.services.referral_rewards import (
    BETALEND,
    vergeet_kortingsrecht,
    verwerk_beloning,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["referrals"])

# Zolang iemand niet uitbetaald krijgt voor een klant die meteen weer weg is,
# blijft de bounty veilig. 60 dagen is de afspraak van 09-09-2026.
COMMISSIE_NA_DAGEN = 60
STANDAARD_BOUNTY_CENTS = 2500

def _schoon(code: str | None) -> str | None:
    """Zie backend/services/referral_codes.schoon_code. Hier alleen nog als naam,
    zodat de regels op één plek staan: de app, het aanmelden en het toekennen
    accepteren daardoor gegarandeerd dezelfde codes."""
    return schoon_code(code)


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
    """Zet first_paid_at zodra een verwezen gebruiker echt gaat betalen, en kent
    meteen de gratis maand toe aan wie hem heeft aangebracht. Wordt vanuit de
    Stripe-webhook aangeroepen.

    Eén keer stempelen: een latere statuswijziging mag de commissieklok niet
    opnieuw laten beginnen. Het toekennen gebeurt daarna WEL elke keer, want dat
    is uit zichzelf al eenmalig (zie verwerk_beloning) en zo wordt een beloning
    die de vorige keer niet lukte alsnog goed gezet.
    """
    if not user_id:
        return
    try:
        db = get_db()
        rij = execute_with_retry(
            db.table("referrals").select("user_id, first_paid_at").eq("user_id", user_id)
        )
        data = rij.data or []
        if not data:
            return
        if not data[0].get("first_paid_at"):
            execute_with_retry(
                db.table("referrals").update({
                    "first_paid_at": datetime.now(timezone.utc).isoformat()
                }).eq("user_id", user_id)
            )
            logger.info("Eerste betaling gestempeld voor verwezen gebruiker %s", user_id)
    except Exception:
        logger.exception("Kon eerste betaling niet stempelen voor %s", user_id)

    # De vriendenkorting geldt alleen tot de eerste betaling; het onthouden
    # antwoord klopt vanaf nu niet meer.
    vergeet_kortingsrecht(user_id)

    # Bewust buiten de try hierboven: ook als het stempelen mislukte hoort de
    # aanbrenger zijn maand te krijgen. verwerk_beloning vangt zelf alles af.
    verwerk_beloning(user_id)


@router.get("/r/{code}")
def volg_klik(code: str, request: Request) -> RedirectResponse:
    """De link die iemand deelt. Telt de klik en stuurt door naar de
    landingspagina met de code erin."""
    schoon = _schoon(code)
    doel = f"{settings.app_url}/{_landingspagina(request)}"
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


def _landingspagina(request: Request) -> str:
    """Nederlands of Engels, op de taalvoorkeur van de browser.

    Klantlinks gaan van verkoper naar verkoper en blijven dus meestal binnen
    Nederland en Vlaanderen, maar niet altijd. Eerder ging iedereen hoe dan ook
    naar de Nederlandse pagina, en dan landt een Duitse of Poolse verkoper op
    een tekst die hij niet leest.
    """
    talen = (request.headers.get("accept-language") or "").lower()
    eerste = talen.split(",")[0].strip()
    return "nl.html" if eerste.startswith("nl") else "index.html"


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
        "kind": "creator",
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

    # Klanten die elkaar aanbrengen staan in dezelfde codetabel, maar horen niet
    # in dit lijstje: daar gaat geen geld naartoe maar een gratis maand. Zonder
    # deze scheiding zou de commissieteller bedragen optellen die nooit betaald
    # worden. Ze krijgen hun eigen blok onderaan.
    klant_codes = [c for c in codes if c.get("owner_user_id")]
    codes = [c for c in codes if not c.get("owner_user_id")]

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
        "gebruikers": _klanten_die_aanbrengen(klant_codes, verwijzingen, abos, klik_per_code),
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


# ── De eigen verwijspagina in de app ─────────────────────────────────────────

# Zoveel namen zoeken we hoogstens op voor het lijstje "wie heb ik uitgenodigd".
# Elk adres is een aparte vraag aan Supabase; bij iemand met honderd uitnodigingen
# zou de pagina anders staan te wachten op honderd rondjes.
_MAX_VRIENDEN = 20


def _stand_van(abo: dict | None) -> str:
    """Waar staat een uitgenodigde vriend: betaalt hij, zit hij in proef, of is
    hij afgehaakt."""
    if not abo:
        return "signed_up"
    status = abo.get("status")
    if status in BETALEND and abo.get("stripe_subscription_id"):
        return "paying"
    if status in ("trialing", "payment_processing"):
        return "trial"
    return "inactive"


def _tegoed_eur(user_id: str) -> float | None:
    """Het openstaande tegoed bij Stripe in euro's, of None als we het niet
    kunnen weten. Bewust live opgehaald en niet zelf bijgehouden: Stripe haalt er
    bij elke factuur vanaf, en een eigen telling zou daar binnen een maand naast
    zitten."""
    if not settings.stripe_secret_key:
        return None
    try:
        import stripe

        db = get_db()
        rij = execute_with_retry(
            db.table("subscriptions").select("stripe_customer_id").eq("user_id", user_id).limit(1)
        )
        klant = ((rij.data or [{}])[0] or {}).get("stripe_customer_id")
        if not klant:
            return None
        saldo = stripe.Customer.retrieve(klant).get("balance") or 0
        # Bij Stripe is een tegoed negatief.
        return round(-saldo / 100, 2) if saldo < 0 else 0.0
    except Exception:
        logger.exception("Kon het Stripe-tegoed niet ophalen voor %s", user_id)
        return None


@router.get("/api/referrals/me")
def mijn_verwijzingen(compact: bool = False, user=Depends(get_current_user_full)):
    """Alles wat de verwijspagina in het dashboard laat zien.

    `compact` is voor de kaart op het dashboard, die bij ELKE keer openen van de
    app wordt opgehaald. Die heeft aan de link en de tellers genoeg. Het lijstje
    namen en het tegoed kosten een vraag per vriend plus een aanroep naar Stripe;
    dat hoort alleen te gebeuren als iemand het scherm zelf openslaat.
    """
    try:
        code = zorg_voor_code(user.id, getattr(user, "email", None))
        mijn_codes = [c["code"] for c in codes_van(user.id)]
    except Exception as e:
        # Niet stilletjes nullen tonen: een ontbrekende tabel ziet er anders uit
        # als "er heeft nog nooit iemand geklikt".
        raise HTTPException(
            status_code=503,
            detail=f"Referrals are not live yet ({e}). Run scripts/sql/referrals_gebruikers.sql in Supabase.",
        )

    db = get_db()
    kliks = (execute_with_retry(
        db.table("referral_clicks").select("code").in_("code", mijn_codes)).data) or []
    verwijzingen = (execute_with_retry(
        db.table("referrals").select("user_id, code, created_at, first_paid_at")
        .in_("code", mijn_codes).order("created_at", desc=True)).data) or []
    beloningen = (execute_with_retry(
        db.table("referral_rewards").select("referred_user_id, status, method, granted_at")
        .eq("referrer_user_id", user.id)).data) or []

    ids = [v["user_id"] for v in verwijzingen]
    abos = {}
    if ids:
        abos = {r["user_id"]: r for r in ((execute_with_retry(
            db.table("subscriptions").select("user_id, status, stripe_subscription_id")
            .in_("user_id", ids)).data) or [])}
    per_vriend = {b["referred_user_id"]: b for b in beloningen}

    vrienden = []
    for v in ([] if compact else verwijzingen[:_MAX_VRIENDEN]):
        stand = _stand_van(abos.get(v["user_id"]))
        beloning = per_vriend.get(v["user_id"]) or {}
        vrienden.append({
            "name": maskeer(email_van(v["user_id"])),
            "joined": (v.get("created_at") or "")[:10],
            "status": stand,
            "rewarded": beloning.get("status") == "granted",
        })

    standen = [_stand_van(abos.get(v["user_id"])) for v in verwijzingen]
    maanden = sum(1 for b in beloningen if b.get("status") == "granted")
    return {
        "ready": True,
        "compact": compact,
        "code": code,
        "link": link_voor(code),
        "old_links": [link_voor(c) for c in mijn_codes[1:]],
        "reward_months": 1,
        "friend_discount_percent": 50,
        "stats": {
            "clicks": len(kliks),
            "signups": len(verwijzingen),
            "trial": sum(1 for s in standen if s == "trial"),
            "paying": sum(1 for s in standen if s == "paying"),
            "months_earned": maanden,
        },
        "credit_eur": None if compact else _tegoed_eur(user.id),
        "friends": vrienden,
        "more_friends": 0 if compact else max(0, len(verwijzingen) - len(vrienden)),
    }


class EigenCode(BaseModel):
    code: str


@router.post("/api/referrals/me/code")
def kies_code(body: EigenCode, user=Depends(get_current_user_full)):
    """Een eigen naam voor de link. De oude link blijft werken, zodat een link
    die al in een appgroep of een video staat nooit doodloopt."""
    try:
        code = kies_eigen_code(user.id, body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Referrals are not live yet ({e}). Run scripts/sql/referrals_gebruikers.sql in Supabase.",
        )
    return {"ok": True, "code": code, "link": link_voor(code)}


def _klanten_die_aanbrengen(klant_codes: list[dict], verwijzingen: list[dict],
                            abos: dict, klik_per_code: dict) -> dict:
    """Wat het aanbrengen door klanten zelf oplevert en kost: aanmeldingen,
    betalende klanten, en hoeveel gratis maanden daarvoor zijn weggegeven."""
    eigen = {c["code"] for c in klant_codes}
    mijn = [v for v in verwijzingen if v.get("code") in eigen]
    betalend = [v for v in mijn if abos.get(v["user_id"]) in {"active", "payment_processing"}]

    maanden = 0
    openstaand = 0
    try:
        rijen = (execute_with_retry(
            get_db().table("referral_rewards").select("status")).data) or []
        maanden = sum(1 for r in rijen if r.get("status") == "granted")
        openstaand = sum(1 for r in rijen if r.get("status") == "pending")
    except Exception:
        # Tabel bestaat nog niet: dan is er ook nog niets weggegeven.
        logger.info("referral_rewards nog niet beschikbaar voor het overzicht")

    return {
        "codes": len(klant_codes),
        "klikken": sum(klik_per_code.get(c, 0) for c in eigen),
        "aanmeldingen": len(mijn),
        "betalend": len(betalend),
        "maanden_weggegeven": maanden,
        "beloningen_open": openstaand,
    }


@router.get("/api/referrals/admin/zelftest")
def zelftest(user=Depends(get_current_user_full)):
    """Staat alles klaar? Eén knop, echte aanroepen, geen aannames.

    Bestaat omdat de twee dingen die buiten de code liggen precies de twee
    dingen zijn die stil kunnen ontbreken: de tabellen in Supabase en de
    kortingscoupon bij Stripe. Zonder deze proef merk je dat pas als de eerste
    aangebrachte klant zijn beloofde korting niet krijgt.
    """
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")

    from backend.services.referral_rewards import (
        VRIENDENKORTING_PROCENT,
        vriendenkorting_coupon,
    )

    db = get_db()
    uitslag = []

    def proef(naam: str, doe):
        try:
            uitslag.append({"naam": naam, "ok": True, "detail": doe()})
        except Exception as e:
            uitslag.append({"naam": naam, "ok": False, "detail": f"{type(e).__name__}: {e}"})

    proef("Codetabel kent eigenaren", lambda: (
        f"{len(execute_with_retry(db.table('referral_codes').select('code, kind, owner_user_id')).data or [])} code(s)"))
    proef("Aanmeldingen zijn gekoppeld", lambda: (
        f"{len(execute_with_retry(db.table('referrals').select('user_id, aanmelding_gemeld_at')).data or [])} aanmelding(en)"))
    proef("Kasboek van de gratis maanden", lambda: (
        f"{len(execute_with_retry(db.table('referral_rewards').select('referred_user_id, status')).data or [])} beloning(en)"))

    def coupon():
        code = vriendenkorting_coupon()
        if not code:
            raise RuntimeError("Stripe gaf geen coupon terug (staat de sleutel goed?)")
        return f"{code} ({VRIENDENKORTING_PROCENT}% op de eerste maand)"

    proef("Vriendenkorting bij Stripe", coupon)

    return {"alles_goed": all(r["ok"] for r in uitslag), "proeven": uitslag}
