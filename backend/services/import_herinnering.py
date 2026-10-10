"""Eén herinnering voor wie zijn advertenties liet scannen maar nooit importeerde.

WAAROM DIT ER IS (29-09-2026)
Matthijs liet op 22-09 zijn Marktplaats scannen: 22 advertenties gevonden. Daarna
klikte hij nooit op "Alles importeren", had een week lang nul artikelen, kon dus
ook niets plaatsen, en zijn proef liep af zonder dat hij het product ooit zag
werken. Niemand gaf hem een seintje. Daniel koos op 29-09-2026: na 24 uur één
automatische herinnering, één keer.

WIE
- een lopende proef of abonnement, aangemaakt in de laatste 14 dagen: dit is
  onboarding, geen terughaalcampagne voor oude accounts;
- minstens één importkandidaat die al 24 uur op 'pending' staat;
- nog nooit iets geïmporteerd of gekoppeld: wie dat deed, weet hoe het werkt;
- proef plus respijt nog niet voorbij, anders loopt hij na de klik op het slot.
Alleen overdag, zoals de andere herinneringen.

ÉÉN KEER, ECHT
Wie een herinnering kreeg staat in leadgen_opslag onder 'import_herinnering'. Het
adres wordt daar vastgelegd vóór de mail uitgaat; mislukt het versturen, dan gaat
het er weer af zodat het volgende uur opnieuw kan. Is de opslag niet te lezen of
te schrijven, dan mailt dit niemand: liever een dag geen herinnering dan dezelfde
mail elk uur.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

OPSLAG = "import_herinnering"
WACHT_MINSTENS = timedelta(hours=24)
NIEUW_BINNEN = timedelta(days=14)
VROEGSTE_UUR = 10
LAATSTE_UUR = 22
NL = ZoneInfo("Europe/Amsterdam")
LEVENDE_ABONNEMENTEN = ("trialing", "active")
IMPORT_LINK = "https://omnivaleur.com/app#import"
KANAALNAMEN = {"marktplaats": "Marktplaats", "2dehands": "2dehands", "vinted": "Vinted",
               "ebay": "eBay", "shopify": "Shopify", "woocommerce": "WooCommerce", "etsy": "Etsy", "facebook": "Facebook"}

_gemaild_uit_geheugen: set[str] = set()


def _parse_ts(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _opsomming(namen: list[str], en: str) -> str:
    return namen[0] if len(namen) == 1 else f"{', '.join(namen[:-1])} {en} {namen[-1]}"


def herinnering_mail(aantal: int, kanalen: list[str]) -> tuple[str, str]:
    """Nederlands eerst, Engels eronder: de server weet niet welke taal de klant leest."""
    from backend.services.billing import CONTACT_EMAIL

    namen = [KANAALNAMEN.get(k, k) for k in kanalen] or ["je kanaal"]
    een = aantal == 1
    onderwerp = ("Je advertenties staan klaar om te importeren / "
                 "Your listings are ready to import")
    tekst = f"""Hoi,

Omnivaleur vond {aantal} {'advertentie' if een else 'advertenties'} van je op {_opsomming(namen, 'en')}, maar {'die staat' if een else 'ze staan'} nog niet
in je voorraad. Pas daarna kan Omnivaleur {'hem' if een else 'ze'} ook op je andere kanalen zetten.

Het is één klik: open {IMPORT_LINK} en klik op Alles importeren.
Daarna kies je zelf waar {'hij' if een else 'ze'} nog meer moet{'' if een else 'en'} komen.

Loop je ergens op vast? Beantwoord gewoon deze mail, dan kijk ik mee.

Groet,

Daniel
Oprichter, Omnivaleur
{CONTACT_EMAIL}


In English:

Hi,

Omnivaleur found {aantal} of your listings on {_opsomming(namen, 'and')}, but {'it is' if een else 'they are'} not in your
inventory yet. Only then can Omnivaleur post {'it' if een else 'them'} to your other platforms.

It takes one click: open {IMPORT_LINK} and click Import all.
You then choose where else {'it' if een else 'they'} should go.

Stuck somewhere? Just reply to this email and I will take a look.

Best regards,

Daniel
Founder, Omnivaleur
"""
    return onderwerp, tekst


def wie_krijgt_hem(db, now: datetime, al_gemaild: dict) -> list[tuple[str, int, list[str]]]:
    """(user_id, aantal wachtende advertenties, kanalen) van iedereen die nu een herinnering krijgt.

    Leest per klant op user_id (daar staat een index op), nooit de hele tabel.
    """
    from backend.services.billing import GRACE_DAYS

    abos = (db.table("subscriptions")
            .select("user_id,status,trial_ends_at,stripe_subscription_id,created_at")
            .in_("status", list(LEVENDE_ABONNEMENTEN))
            .gte("created_at", (now - NIEUW_BINNEN).isoformat()).execute().data or [])
    uit = []
    for a in abos:
        uid = a.get("user_id")
        if not uid or uid in al_gemaild or uid in _gemaild_uit_geheugen:
            continue
        einde = _parse_ts(a.get("trial_ends_at"))
        if (a.get("status") == "trialing" and not a.get("stripe_subscription_id")
                and einde and einde + timedelta(days=GRACE_DAYS) <= now):
            continue
        wachtend = (db.table("import_candidates").select("platform,created_at")
                    .eq("user_id", uid).eq("status", "pending")
                    .order("created_at").limit(1000).execute().data or [])
        oudste = _parse_ts(wachtend[0].get("created_at")) if wachtend else None
        if not oudste or now - oudste < WACHT_MINSTENS:
            continue
        gedaan = (db.table("import_candidates").select("id").eq("user_id", uid)
                  .in_("status", ["imported", "linked"]).limit(1).execute().data)
        if gedaan:
            continue
        uit.append((uid, len(wachtend), sorted({w.get("platform") for w in wachtend if w.get("platform")})))
    return uit


def _lees_opslag(db) -> dict | None:
    try:
        rij = db.table("leadgen_opslag").select("inhoud").eq("naam", OPSLAG).execute().data
    except Exception as e:  # noqa: BLE001
        logger.error(f"Importherinnering: opslag niet te lezen ({e}); niemand gemaild.")
        return None
    inhoud = (rij[0].get("inhoud") if rij else {}) or {}
    return inhoud if isinstance(inhoud, dict) else None


def _schrijf_opslag(db, inhoud: dict) -> bool:
    try:
        db.table("leadgen_opslag").upsert({"naam": OPSLAG, "inhoud": inhoud},
                                          on_conflict="naam").execute()
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Importherinnering: opslag niet te schrijven ({e}).")
        return False


async def herinner_niet_geimporteerd(now: datetime | None = None) -> int:
    """Draait elk uur. Geeft terug hoeveel mails er zijn verstuurd."""
    from backend.database import get_admin_db, get_db
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    now = now or datetime.now(timezone.utc)
    if not VROEGSTE_UUR <= now.astimezone(NL).hour < LAATSTE_UUR:
        return 0
    # De opslag via de beheersleutel: met de publieke sleutel geeft leadgen_opslag
    # stil een lege lijst (RLS), en dan lijkt het of nog niemand gemaild is.
    opslag_db = get_admin_db()
    al = _lees_opslag(opslag_db)
    if al is None:
        return 0
    verstuurd = 0
    for uid, aantal, kanalen in wie_krijgt_hem(get_db(), now, al):
        try:
            gebruiker = get_admin_db().auth.admin.get_user_by_id(uid)
            adres = gebruiker.user.email if gebruiker and gebruiker.user else None
        except Exception as e:  # noqa: BLE001
            logger.error(f"Importherinnering niet verstuurd aan {uid}: adres niet op te vragen ({e}).")
            continue
        if not adres:
            continue
        al[uid] = now.isoformat()
        if not _schrijf_opslag(opslag_db, al):
            return verstuurd
        _gemaild_uit_geheugen.add(uid)
        onderwerp, tekst = herinnering_mail(aantal, kanalen)
        if send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL):
            verstuurd += 1
            logger.info(f"Importherinnering naar {adres}: {aantal} wachtend op {kanalen}")
        else:
            al.pop(uid, None)
            _gemaild_uit_geheugen.discard(uid)
            _schrijf_opslag(opslag_db, al)
    return verstuurd
