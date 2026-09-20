"""Klanten die klanten aanbrengen: de gratis maand en alles eromheen.

De afspraak (20-09-2026):

    wie een vriend aanbrengt die gaat betalen, krijgt één maand gratis.
    de vriend zelf betaalt de eerste maand voor de helft.

Waarom de beloning pas valt bij de EERSTE BETALING en niet bij het aanmelden:
een gratis maand bij aanmelding kan iedereen tien keer pakken met tien
e-mailadressen, zonder dat er ooit een euro binnenkomt. Nu staat er tegenover
elke weggegeven maand een klant die echt 19,99 heeft betaald.

De hele bescherming tegen dubbel uitkeren zit in één unieke sleutel:
referral_rewards.referred_user_id. Elke aangebrachte klant kan dus hoogstens
één keer een maand opleveren, hoe vaak de webhook ook binnenkomt en hoe vaak
de herstelronde er ook overheen loopt.

Toekennen kan op drie manieren, afhankelijk van waar de aanbrenger staat:

  * betaalt al           -> geld bijschrijven bij Stripe (tegoed). Stripe haalt
                            dat automatisch van de volgende factuur af.
  * proef loopt bij Stripe -> die proef 30 dagen opschuiven.
  * nog geen abonnement  -> de proefperiode in onze eigen tabel 30 dagen
                            oprekken (ook als die net verlopen was: dan komt de
                            toegang terug, en dat is precies wat "een maand
                            gratis" hoort te betekenen).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import stripe

from backend.config import settings
from backend.database import execute_with_retry, get_db
from backend.services.billing import invalidate_access_cache, is_owner_email
from backend.services.referral_codes import eigenaar_van_code
from backend.services.referral_mail import email_van, mail_aanmelding, mail_beloning

logger = logging.getLogger(__name__)

# Eén maand gratis = 30 dagen erbij, of één maandbedrag aan tegoed.
MAAND_DAGEN = 30
STANDAARD_MAANDPRIJS_CENTS = 1999

# De korting voor de aangebrachte vriend. Wordt zo nodig zelf bij Stripe
# aangemaakt, zodat er niets met de hand klaargezet hoeft te worden.
VRIENDENKORTING_ID = "omnivaleur-vriendenkorting-50"
VRIENDENKORTING_PROCENT = 50

# Zoveel keer proberen we een mislukte toekenning nog opnieuw voordat de
# herstelronde hem laat liggen. Blijft hij hangen, dan staat de reden in
# last_error en ziet Daniel hem op de beheerpagina.
MAX_POGINGEN = 6

# Statussen die "hier komt geld binnen" betekenen.
BETALEND = {"active", "payment_processing"}


# ── De vriendenkorting (50% op de eerste maand) ──────────────────────────────

_coupon_cache: tuple[float, str | None] | None = None


def vriendenkorting_coupon() -> str | None:
    """Het coupon-id bij Stripe, en maakt hem aan als hij er nog niet is.

    Bewust zelf aanmaken in plaats van een instelling die met de hand gevuld moet
    worden: een vergeten instelling betekent dat de vriend zijn beloofde korting
    niet krijgt, en dat merk je pas als iemand klaagt.
    """
    global _coupon_cache
    if not settings.stripe_secret_key:
        return None
    if _coupon_cache and _coupon_cache[0] > time.monotonic():
        return _coupon_cache[1]

    gevonden: str | None = None
    try:
        stripe.Coupon.retrieve(VRIENDENKORTING_ID)
        gevonden = VRIENDENKORTING_ID
    except Exception:
        try:
            stripe.Coupon.create(
                id=VRIENDENKORTING_ID,
                percent_off=VRIENDENKORTING_PROCENT,
                duration="once",
                name="Invited by a friend",
            )
            gevonden = VRIENDENKORTING_ID
            logger.info("Vriendenkorting aangemaakt bij Stripe (%s)", VRIENDENKORTING_ID)
        except Exception as e:
            # Kan de korting niet gemaakt worden, dan mag dat het afrekenen nooit
            # blokkeren: liever betalen zonder korting dan niet kunnen betalen.
            if "already exists" in str(e).lower():
                gevonden = VRIENDENKORTING_ID
            else:
                logger.exception("Kon de vriendenkorting niet klaarzetten")
    _coupon_cache = (time.monotonic() + (3600 if gevonden else 300), gevonden)
    return gevonden


_korting_cache: dict[str, tuple[float, bool]] = {}
_KORTING_TTL = 300


def heeft_recht_op_vriendenkorting(user_id: str) -> bool:
    """Is deze gebruiker via de link van een andere KLANT binnengekomen en heeft
    hij nog niet betaald? De statuspagina vraagt dit elke minuut, dus het antwoord
    wordt even onthouden."""
    if not user_id:
        return False
    onthouden = _korting_cache.get(user_id)
    if onthouden and onthouden[0] > time.monotonic():
        return onthouden[1]

    antwoord = False
    try:
        db = get_db()
        rij = execute_with_retry(
            db.table("referrals").select("code, first_paid_at").eq("user_id", user_id).limit(1)
        )
        verwijzing = (rij.data or [None])[0]
        if verwijzing and not verwijzing.get("first_paid_at"):
            code = eigenaar_van_code(verwijzing.get("code"))
            antwoord = bool(code and code.get("owner_user_id"))
    except Exception:
        # Niet luidruchtig: zolang de tabellen er nog niet zijn hoort dit gewoon
        # "nee" te zijn, zonder dat de statuspagina erop stukloopt.
        logger.debug("Kon vriendenkorting niet bepalen voor %s", user_id, exc_info=True)
        antwoord = False
    _korting_cache[user_id] = (time.monotonic() + _KORTING_TTL, antwoord)
    return antwoord


def vergeet_kortingsrecht(user_id: str | None = None) -> None:
    if user_id:
        _korting_cache.pop(user_id, None)
    else:
        _korting_cache.clear()


# ── De gratis maand toekennen ────────────────────────────────────────────────

def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _lees_ts(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        dt = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _maandprijs_cents(stripe_sub) -> int:
    """Wat deze klant echt per maand betaalt. Bewust uit zijn eigen abonnement en
    niet uit een vast bedrag: wie ooit met korting is ingestapt zou anders meer of
    minder dan één maand terugkrijgen."""
    try:
        items = (stripe_sub.get("items") or {}).get("data") or []
        if items:
            prijs = items[0].get("price") or {}
            bedrag = prijs.get("unit_amount")
            aantal = items[0].get("quantity") or 1
            if bedrag:
                return int(bedrag) * int(aantal)
    except Exception:
        logger.exception("Kon het maandbedrag niet uit het abonnement lezen")
    return STANDAARD_MAANDPRIJS_CENTS


def _verleng_proef_lokaal(sub: dict) -> tuple[str, int, str]:
    """De proefperiode in onze eigen tabel 30 dagen oprekken. Vanaf nu als de
    proef al voorbij was, anders vanaf het oude einde: wie nog twee dagen had,
    houdt die twee dagen."""
    db = get_db()
    nu = _nu()
    oud = _lees_ts(sub.get("trial_ends_at"))
    basis = oud if (oud and oud > nu) else nu
    nieuw = basis + timedelta(days=MAAND_DAGEN)
    velden = {"trial_ends_at": nieuw.isoformat(), "updated_at": nu.isoformat()}
    # Een verlopen proef weer openzetten is de bedoeling: iemand die een
    # betalende klant aanbrengt hoort niet buitengesloten te blijven staan.
    if (sub.get("status") or "trialing") not in ("active", "payment_processing", "complimentary"):
        velden["status"] = "trialing"
    execute_with_retry(db.table("subscriptions").update(velden).eq("user_id", sub["user_id"]))
    invalidate_access_cache(sub["user_id"])
    return ("proef_verlengd", 0, f"Trial runs until {nieuw.date().isoformat()}")


def _ken_toe(referrer_user_id: str) -> tuple[str, int, str]:
    """De maand daadwerkelijk geven. Geeft terug: (manier, bedrag_in_centen,
    uitleg). Gooit een fout als het niet lukte, zodat de rij op 'pending' blijft
    staan en de herstelronde het opnieuw probeert."""
    db = get_db()
    rij = execute_with_retry(
        db.table("subscriptions").select("*").eq("user_id", referrer_user_id).limit(1)
    )
    sub = (rij.data or [None])[0]
    if not sub:
        # Geen abonnementsrij (RLS heeft hier eerder toegeslagen). Bewust een
        # fout en geen uitslag: dan blijft de beloning openstaan en pakt de
        # herstelronde hem zodra de rij er wel is.
        raise RuntimeError("Geen abonnementsrij om de maand aan te hangen")

    if sub.get("status") == "complimentary":
        # Handmatig gegeven gratis toegang zonder einddatum. Daar valt geen maand
        # bij op te tellen, en de proefstatus erop zetten zou die toegang juist
        # WEGNEMEN.
        return ("gratis_account", 0, "Account already has free access")

    stripe_sub_id = sub.get("stripe_subscription_id")
    if stripe_sub_id and settings.stripe_secret_key:
        s = stripe.Subscription.retrieve(stripe_sub_id)
        status = s.get("status")
        if status == "trialing":
            huidig = s.get("trial_end")
            basis = datetime.fromtimestamp(huidig, tz=timezone.utc) if huidig else _nu()
            if basis < _nu():
                basis = _nu()
            nieuw = basis + timedelta(days=MAAND_DAGEN)
            stripe.Subscription.modify(
                stripe_sub_id,
                trial_end=int(nieuw.timestamp()),
                proration_behavior="none",
            )
            execute_with_retry(db.table("subscriptions").update({
                "trial_ends_at": nieuw.isoformat(), "updated_at": _nu().isoformat(),
            }).eq("user_id", referrer_user_id))
            invalidate_access_cache(referrer_user_id)
            return ("stripe_proef", 0, f"First payment moved to {nieuw.date().isoformat()}")

        if status in ("active", "past_due", "unpaid", "incomplete", "paused"):
            klant = sub.get("stripe_customer_id") or s.get("customer")
            if not klant:
                raise RuntimeError("Abonnement zonder klantnummer bij Stripe")
            bedrag = _maandprijs_cents(s)
            txn = stripe.Customer.create_balance_transaction(
                klant,
                amount=-bedrag,          # negatief = tegoed
                currency="eur",
                description="Omnivaleur referral reward: 1 month free",
                metadata={"user_id": referrer_user_id, "bron": "referral"},
            )
            txn_id = txn.get("id") if hasattr(txn, "get") else getattr(txn, "id", "")
            return ("tegoed", bedrag, f"Stripe credit {txn_id}")

    # Geen lopend abonnement (of Stripe staat uit): dan is de proefperiode de
    # plek waar een gratis maand thuishoort.
    return _verleng_proef_lokaal(sub)


def verwerk_beloning(referred_user_id: str) -> str:
    """Kent de gratis maand toe aan wie deze klant heeft aangebracht.

    Veilig om vaak aan te roepen: de unieke sleutel op referred_user_id zorgt
    ervoor dat er hoogstens één beloning per aangebrachte klant bestaat. Geeft
    kort terug wat er gebeurd is, voor het logboek en voor de tests.
    """
    if not referred_user_id:
        return "geen_gebruiker"
    try:
        db = get_db()
        rij = execute_with_retry(
            db.table("referrals").select("user_id, code").eq("user_id", referred_user_id).limit(1)
        )
        verwijzing = (rij.data or [None])[0]
        if not verwijzing:
            return "niet_verwezen"

        code_rij = eigenaar_van_code(verwijzing.get("code"))
        aanbrenger = (code_rij or {}).get("owner_user_id")
        if not aanbrenger:
            # Creatorcode: die loopt via de geldafspraak, niet via gratis maanden.
            return "creatorcode"
        if aanbrenger == referred_user_id:
            return "zelfverwijzing"

        bestaand = execute_with_retry(
            db.table("referral_rewards").select("*").eq("referred_user_id", referred_user_id).limit(1)
        )
        beloning = (bestaand.data or [None])[0]
        if beloning and beloning.get("status") in ("granted", "skipped"):
            return "al_toegekend"
        if beloning and (beloning.get("attempts") or 0) >= MAX_POGINGEN:
            return "opgegeven"

        if not beloning:
            try:
                nieuw = execute_with_retry(db.table("referral_rewards").insert({
                    "referrer_user_id": aanbrenger,
                    "referred_user_id": referred_user_id,
                    "code": verwijzing.get("code"),
                    "status": "pending",
                }))
                beloning = (nieuw.data or [{}])[0]
            except Exception as e:
                # Iemand anders was er net eerder bij (tweede webhook). Dat is
                # precies waar de unieke sleutel voor is.
                if "23505" in str(e) or "duplicate" in str(e).lower():
                    return "al_geclaimd"
                raise

        # De eigenaar heeft geen echt abonnement; hem een maand geven is zinloos.
        if _is_eigenaar(aanbrenger):
            _sluit_af(beloning, "skipped", "eigenaar", 0, "Owner account, nothing to credit")
            return "eigenaar"

        try:
            manier, bedrag, uitleg = _ken_toe(aanbrenger)
        except Exception as e:
            _noteer_mislukking(beloning, e)
            logger.exception("Gratis maand toekennen mislukt voor %s", aanbrenger)
            return "mislukt"

        if manier == "gratis_account":
            _sluit_af(beloning, "skipped", manier, bedrag, uitleg)
            return "gratis_account"

        _sluit_af(beloning, "granted", manier, bedrag, uitleg)
        logger.info("Gratis maand toegekend aan %s via %s (%s)", aanbrenger, manier, uitleg)
        mail_beloning(aanbrenger, manier, uitleg)
        return "toegekend"
    except Exception:
        logger.exception("Beloning verwerken mislukt voor %s", referred_user_id)
        return "fout"


def _is_eigenaar(user_id: str) -> bool:
    """Het eigen account van Daniel heeft geen echt abonnement, dus daar valt
    niets te verlengen of te crediteren."""
    return is_owner_email(email_van(user_id))


def _sluit_af(beloning: dict, status: str, manier: str, bedrag: int, uitleg: str) -> None:
    db = get_db()
    execute_with_retry(db.table("referral_rewards").update({
        "status": status,
        "method": manier,
        "amount_cents": bedrag,
        "detail": uitleg[:500],
        "granted_at": _nu().isoformat(),
        "last_error": None,
    }).eq("referred_user_id", beloning["referred_user_id"]))


def _noteer_mislukking(beloning: dict, fout: Exception) -> None:
    db = get_db()
    try:
        execute_with_retry(db.table("referral_rewards").update({
            "attempts": (beloning.get("attempts") or 0) + 1,
            "last_error": f"{type(fout).__name__}: {fout}"[:500],
        }).eq("referred_user_id", beloning["referred_user_id"]))
    except Exception:
        logger.exception("Kon de mislukte poging niet vastleggen")


# ── De herstelronde ──────────────────────────────────────────────────────────

# Hoe oud een aanmelding mag zijn voordat we er nog een mail over sturen. Zonder
# deze grens zou de eerste ronde na de uitgifte iedereen alsnog mailen over
# aanmeldingen van weken geleden.
MELD_MAX_DAGEN = 14
MAX_MAILS_PER_RONDE = 30


async def verwerk_openstaande_beloningen() -> dict:
    """Draait elk uur en maakt af wat de webhook heeft laten liggen.

    Waarom dit er is: de gratis maand hangt aan een Stripe-webhook, en een
    webhook die niet aankomt (uitrol, storing, een gemiste poging) zou betekenen
    dat iemand zijn beloofde maand nooit krijgt en dat nooit iemand het merkt.
    Deze ronde kijkt zelf wie er betaalt en maakt het alsnog in orde.

    Geeft terug wat er gebeurd is, zodat het logboek iets zinnigs zegt.
    """
    uit = {"toegekend": 0, "gemaild": 0, "mislukt": 0}
    db = get_db()
    try:
        verwijzingen = (execute_with_retry(db.table("referrals").select(
            "user_id, code, created_at, first_paid_at, aanmelding_gemeld_at")).data) or []
        codes = (execute_with_retry(db.table("referral_codes").select(
            "code, owner_user_id")).data) or []
    except Exception as e:
        # Niet stil: zolang de migratie niet gedraaid is hoort dat hier te staan,
        # en niet als een dashboard dat toevallig nul beloningen toont.
        logger.error("Verwijzingsronde overgeslagen (%s). Staat scripts/sql/"
                     "referrals_gebruikers.sql al in Supabase?", e)
        return uit

    eigenaar_per_code = {c["code"]: c.get("owner_user_id") for c in codes}
    van_klanten = [v for v in verwijzingen if eigenaar_per_code.get(v.get("code"))]
    if not van_klanten:
        return uit

    ids = [v["user_id"] for v in van_klanten]
    abos = {r["user_id"]: r for r in ((execute_with_retry(
        db.table("subscriptions").select("user_id, status, stripe_subscription_id")
        .in_("user_id", ids)).data) or [])}
    beloningen = {r["referred_user_id"]: r for r in ((execute_with_retry(
        db.table("referral_rewards").select("referred_user_id, status, attempts")
        .in_("referred_user_id", ids)).data) or [])}

    nu = _nu()
    gemaild = 0
    for v in van_klanten:
        uid = v["user_id"]
        abo = abos.get(uid) or {}
        betaalt = abo.get("status") in BETALEND and bool(abo.get("stripe_subscription_id"))

        if betaalt:
            if not v.get("first_paid_at"):
                # De webhook is deze klant misgelopen. Alsnog stempelen, anders
                # blijft ook de influencer-telling achterlopen.
                try:
                    execute_with_retry(db.table("referrals").update({
                        "first_paid_at": nu.isoformat()
                    }).eq("user_id", uid).is_("first_paid_at", "null"))
                except Exception:
                    logger.exception("Kon eerste betaling niet alsnog stempelen voor %s", uid)
            beloning = beloningen.get(uid)
            openstaand = (beloning is None) or (
                beloning.get("status") == "pending"
                and (beloning.get("attempts") or 0) < MAX_POGINGEN
            )
            if openstaand:
                uitkomst = verwerk_beloning(uid)
                if uitkomst == "toegekend":
                    uit["toegekend"] += 1
                elif uitkomst in ("mislukt", "fout"):
                    uit["mislukt"] += 1

        if not v.get("aanmelding_gemeld_at") and gemaild < MAX_MAILS_PER_RONDE:
            aangemaakt = _lees_ts(v.get("created_at"))
            oud = aangemaakt is None or (nu - aangemaakt) > timedelta(days=MELD_MAX_DAGEN)
            verstuurd = False
            if not oud:
                verstuurd = mail_aanmelding(
                    eigenaar_per_code[v["code"]], email_van(uid), v["code"])
                if verstuurd:
                    gemaild += 1
                    uit["gemaild"] += 1
            # Te oud: wel afvinken, niet mailen. Anders blijft deze ronde elk uur
            # opnieuw over aanmeldingen van vorige maand beginnen.
            if verstuurd or oud:
                try:
                    execute_with_retry(db.table("referrals").update({
                        "aanmelding_gemeld_at": nu.isoformat()
                    }).eq("user_id", uid))
                except Exception:
                    logger.exception("Kon aanmeldmelding niet afvinken voor %s", uid)

    if uit["toegekend"] or uit["mislukt"] or uit["gemaild"]:
        logger.info("Verwijzingsronde: %s", uit)
    return uit
