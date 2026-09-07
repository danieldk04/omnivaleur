"""Herinnering per mail als een mogelijke verkoop wacht op bevestiging.

WAAROM DIT ER IS
Sinds we een verkoop die niet keihard vaststaat (advertentie verdwenen, een
'verkocht'-label op Marktplaats, de berichtenbadge) niet meer automatisch overal
afmelden maar eerst vrágen, ligt er een risico: reageert de verkoper niet, dan
blijft het artikel op de andere kanalen te koop en kan het dubbel verkocht
worden. De vraag staat in het dashboard, maar niet iedereen kijkt daar dagelijks.

Daarom: staat er een onbevestigde verkoop langer dan een paar uur, dan één
mailtje. Zelfde terughoudendheid als de offline-waarschuwing: alleen overdag,
hoogstens één keer per dag per klant, en alleen bij een lopende proef of
abonnement.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

WACHT_MINSTENS = timedelta(hours=4)      # zo lang mag een vraag onbeantwoord staan
STILTE_NA_MAIL = timedelta(hours=24)     # hoogstens één herinnering per dag per klant
VROEGSTE_UUR = 10
LAATSTE_UUR = 22
NL = ZoneInfo("Europe/Amsterdam")
LEVENDE_ABONNEMENTEN = ("trialing", "active")
MAX_RIJEN = 4000

_gemaild_uit_geheugen: dict[str, datetime] = {}
_kolom_ontbreekt = False


def _parse_ts(waarde) -> datetime | None:
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def herinnering_mail(aantal: int) -> tuple[str, str]:
    from backend.services.billing import CONTACT_EMAIL

    onderwerp = ("You may have sold an item — confirm it in Omnivaleur" if aantal == 1
                 else f"You may have sold {aantal} items — confirm them in Omnivaleur")
    tekst = f"""Hi,

Omnivaleur noticed {'an item that looks' if aantal == 1 else f'{aantal} items that look'} sold, but we did not remove {'it' if aantal == 1 else 'them'} from your
other platforms yet. We never take a listing down until you confirm the sale,
so nothing has changed anywhere.

Open your dashboard and answer the "Is this sold?" question:
 - Yes, sold  -> we take it off every other platform and count it in your revenue.
 - No         -> it moves to Archived and stays for sale everywhere else.

Until you answer, the item stays live on your other platforms and could sell
twice. It only takes a moment.

Best regards,

Daniel
Founder, Omnivaleur
{CONTACT_EMAIL}
"""
    return onderwerp, tekst


def _onbevestigd(db):
    """Alle advertentierijen die op bevestiging wachten. Klein genoeg voor één
    haal: het zijn er per definitie weinig."""
    global _kolom_ontbreekt
    velden = "item_id,status,last_checked,sold_unconfirmed_notified_at"
    if not _kolom_ontbreekt:
        try:
            return (db.table("listings").select(velden)
                    .eq("status", "sold_unconfirmed").limit(MAX_RIJEN).execute().data or [])
        except Exception as e:
            tekst = str(e)
            if "42703" in tekst or "does not exist" in tekst.lower():
                _kolom_ontbreekt = True
                logger.error(
                    "Kolom sold_unconfirmed_notified_at ontbreekt nog in listings. De "
                    "herinnering draait nu op servergeheugen en kan zich na een herstart "
                    "herhalen. Zet hem erbij met: ALTER TABLE listings "
                    "ADD COLUMN sold_unconfirmed_notified_at timestamptz;"
                )
            else:
                raise
    return (db.table("listings").select("item_id,status,last_checked")
            .eq("status", "sold_unconfirmed").limit(MAX_RIJEN).execute().data or [])


def _al_gemaild(user_id: str, rijen: list[dict], now: datetime) -> bool:
    uit_geheugen = _gemaild_uit_geheugen.get(user_id)
    if uit_geheugen and now - uit_geheugen < STILTE_NA_MAIL:
        return True
    stempels = [_parse_ts(r.get("sold_unconfirmed_notified_at")) for r in rijen]
    stempels = [s for s in stempels if s]
    # Al gemaild over ALLES wat er nu staat, en recent? Dan niet opnieuw.
    return bool(stempels) and len(stempels) == len(rijen) and all(
        now - s < STILTE_NA_MAIL for s in stempels
    )


def _markeer(db, item_ids: list[str], user_id: str, now: datetime) -> None:
    _gemaild_uit_geheugen[user_id] = now
    if _kolom_ontbreekt or not item_ids:
        return
    try:
        for i in range(0, len(item_ids), 50):
            (db.table("listings")
             .update({"sold_unconfirmed_notified_at": now.isoformat()})
             .eq("status", "sold_unconfirmed")
             .in_("item_id", item_ids[i:i + 50]).execute())
    except Exception as e:
        logger.error(f"Kon verkoop-herinnering niet afvinken voor {user_id}: {e}")


async def herinner_onbevestigde_verkopen(now: datetime | None = None) -> int:
    """Draait elk uur. Geeft terug hoeveel mails er zijn verstuurd."""
    from backend.database import get_admin_db, get_db
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    now = now or datetime.now(timezone.utc)
    if not VROEGSTE_UUR <= now.astimezone(NL).hour < LAATSTE_UUR:
        return 0

    db = get_db()
    rijen = _onbevestigd(db)
    if not rijen:
        return 0

    # Rij hoort bij een artikel; het artikel hoort bij een gebruiker.
    item_ids = sorted({r["item_id"] for r in rijen if r.get("item_id")})
    eigenaar: dict[str, str] = {}
    for i in range(0, len(item_ids), 50):
        brok = item_ids[i:i + 50]
        for row in (db.table("items").select("id,user_id").in_("id", brok).execute().data or []):
            eigenaar[row["id"]] = row["user_id"]

    per_klant: dict[str, list[dict]] = {}
    grens = now - WACHT_MINSTENS
    for r in rijen:
        uid = eigenaar.get(r.get("item_id"))
        if not uid:
            continue
        # De vraag staat er pas echt sinds last_checked; jonger dan een paar uur
        # laten we met rust zodat een verse detectie geen directe mail oplevert.
        gezet = _parse_ts(r.get("last_checked"))
        if gezet and gezet > grens:
            continue
        per_klant.setdefault(uid, []).append(r)

    if not per_klant:
        return 0

    levend = {row["user_id"] for row in (db.table("subscriptions").select("user_id,status")
              .in_("status", list(LEVENDE_ABONNEMENTEN)).execute().data or []) if row.get("user_id")}

    verstuurd = 0
    for uid, klant_rijen in per_klant.items():
        if uid not in levend:
            continue
        if _al_gemaild(uid, klant_rijen, now):
            continue
        try:
            gebruiker = get_admin_db().auth.admin.get_user_by_id(uid)
            adres = gebruiker.user.email if gebruiker and gebruiker.user else None
        except Exception as e:
            logger.error(f"Verkoop-herinnering niet verstuurd aan {uid}: adres niet op te "
                         f"vragen ({e}). Draait de server op de anon-sleutel?")
            continue
        if not adres:
            continue

        klant_items = sorted({r["item_id"] for r in klant_rijen if r.get("item_id")})
        onderwerp, tekst = herinnering_mail(len(klant_items))
        if send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL):
            _markeer(db, klant_items, uid, now)
            verstuurd += 1
            logger.info(f"Verkoop-herinnering naar {adres}: {len(klant_items)} onbevestigd")
    return verstuurd
