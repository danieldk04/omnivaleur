"""Eén mail voor wie zich aanmeldde en na een uur nog niets in beeld heeft.

WAAROM DIT ER IS (16-11-2026)
Meting van 22 aanmelders in 30 dagen: 10 kregen nooit een artikel binnen, 8 installeerden
de extensie niet eens. Het dashboard helpt wie blijft, maar wie het tabblad sluit hoort
niets meer. Daniel koos: een mail na een uur stilstand.

WIE
- lopende proef (nog geen betaling), aangemaakt tussen 1 en 48 uur geleden;
- nog geen enkel artikel en nog geen gelukte opdracht: wie al iets heeft snapt het;
- proef plus respijt nog niet voorbij.
De tekst hangt af van wat we meten: heeft de extensie zich nooit gemeld, dan gaat het
over installeren, anders over het eerste artikel. Alleen overdag, één keer per klant.

ÉÉN KEER, ECHT
Zoals bij de importherinnering: het adres wordt in leadgen_opslag onder
'stil_na_aanmelding' vastgelegd vóór de mail uitgaat; mislukt versturen, dan gaat het
er weer af. Is de opslag niet te lezen of te schrijven, dan mailt dit niemand.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

OPSLAG = "stil_na_aanmelding"
WACHT_MINSTENS = timedelta(hours=1)
NIEUW_BINNEN = timedelta(hours=48)
VROEGSTE_UUR = 9
LAATSTE_UUR = 21
NL = ZoneInfo("Europe/Amsterdam")
APP_LINK = "https://omnivaleur.com/app"

_gemaild_uit_geheugen: set[str] = set()


def _parse_ts(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def stil_mail(extensie_gezien: bool) -> tuple[str, str]:
    """Nederlands eerst, Engels eronder. Platte tekst, geen opmaaktekens."""
    onderwerp = "Je eerste advertentie is bijna online / Your first advert is almost online"
    if extensie_gezien:
        nl = f"""Je Omnivaleur staat klaar. Open {APP_LINK} in Chrome: je advertenties worden
vanzelf ingelezen en daarna staat er één artikel klaar met de knop Plaats nu. Dat kost
ongeveer twee minuten."""
        en = f"""Your Omnivaleur is ready. Open {APP_LINK} in Chrome: your adverts are read in
automatically and then one item is waiting with a Place it now button. It takes about
two minutes."""
    else:
        nl = f"""Je account staat klaar, alleen de Chrome-extensie is er nog niet. Die zet je
advertenties namens jou online, in je eigen browser. Open {APP_LINK} in Chrome op je
computer, druk op Add to Chrome en kom terug naar dat tabblad: de rest gaat vanzelf."""
        en = f"""Your account is ready, only the Chrome extension is missing. It places your
adverts for you, in your own browser. Open {APP_LINK} in Chrome on your computer, press
Add to Chrome and come back to that tab: the rest happens by itself."""
    tekst = f"""Hoi,

{nl}

Zit je ergens vast? Beantwoord gewoon deze mail, dan help ik je.

Groet,

Daniel
Oprichter, Omnivaleur


In English:

Hi,

{en}

Stuck somewhere? Just reply to this email and I will help you.

Best regards,

Daniel
Founder, Omnivaleur
"""
    return onderwerp, tekst


def wie_krijgt_hem(db, now: datetime, al_gemaild: dict) -> list[tuple[str, bool]]:
    """(user_id, extensie al gezien) van iedereen die nu de mail krijgt.

    Leest per klant op user_id, nooit een hele tabel.
    """
    from backend.services.billing import GRACE_DAYS

    abos = (db.table("subscriptions")
            .select("user_id,status,trial_ends_at,stripe_subscription_id,created_at")
            .in_("status", ["trialing"])
            .gte("created_at", (now - NIEUW_BINNEN).isoformat()).execute().data or [])
    uit = []
    for a in abos:
        uid = a.get("user_id")
        if not uid or uid in al_gemaild or uid in _gemaild_uit_geheugen or a.get("stripe_subscription_id"):
            continue
        aangemaakt = _parse_ts(a.get("created_at"))
        if not aangemaakt or now - aangemaakt < WACHT_MINSTENS:
            continue
        einde = _parse_ts(a.get("trial_ends_at"))
        if einde and einde + timedelta(days=GRACE_DAYS) <= now:
            continue
        if db.table("items").select("id").eq("user_id", uid).limit(1).execute().data:
            continue
        if db.table("jobs").select("id").eq("user_id", uid).eq("status", "done").limit(1).execute().data:
            continue
        gezien = bool(db.table("extension_heartbeat").select("user_id").eq("user_id", uid)
                      .limit(1).execute().data)
        uit.append((uid, gezien))
    return uit


def _lees_opslag(db) -> dict | None:
    try:
        rij = db.table("leadgen_opslag").select("inhoud").eq("naam", OPSLAG).execute().data
    except Exception as e:  # noqa: BLE001
        logger.error(f"Stilstandmail: opslag niet te lezen ({e}); niemand gemaild.")
        return None
    inhoud = (rij[0].get("inhoud") if rij else {}) or {}
    return inhoud if isinstance(inhoud, dict) else None


def _schrijf_opslag(db, inhoud: dict) -> bool:
    try:
        db.table("leadgen_opslag").upsert({"naam": OPSLAG, "inhoud": inhoud}, on_conflict="naam").execute()
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Stilstandmail: opslag niet te schrijven ({e}).")
        return False


async def mail_wie_stil_zit(now: datetime | None = None) -> int:
    """Draait elk uur. Geeft terug hoeveel mails er zijn verstuurd."""
    from backend.database import get_admin_db, get_db
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    now = now or datetime.now(timezone.utc)
    if not VROEGSTE_UUR <= now.astimezone(NL).hour < LAATSTE_UUR:
        return 0
    opslag_db = get_admin_db()
    al = _lees_opslag(opslag_db)
    if al is None:
        return 0
    verstuurd = 0
    for uid, gezien in wie_krijgt_hem(get_db(), now, al):
        try:
            gebruiker = get_admin_db().auth.admin.get_user_by_id(uid)
            adres = gebruiker.user.email if gebruiker and gebruiker.user else None
        except Exception as e:  # noqa: BLE001
            logger.error(f"Stilstandmail niet verstuurd aan {uid}: adres niet op te vragen ({e}).")
            continue
        if not adres:
            continue
        al[uid] = now.isoformat()
        if not _schrijf_opslag(opslag_db, al):
            return verstuurd
        _gemaild_uit_geheugen.add(uid)
        onderwerp, tekst = stil_mail(gezien)
        if send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL, afmelden_user_id=uid):
            verstuurd += 1
            logger.info(f"Stilstandmail naar {adres} (extensie gezien: {gezien})")
        else:
            al.pop(uid, None)
            _gemaild_uit_geheugen.discard(uid)
            _schrijf_opslag(opslag_db, al)
    return verstuurd
