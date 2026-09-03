"""Waarschuwen als de computer van een klant uit staat terwijl er werk wacht.

WAAROM DIT ER IS (03-09-2026, Toon van dejuistetoon)
Toon klikte 50 advertenties klaar en meldde uren later "er gebeurt eigenlijk
niets". Nagemeten: zijn extensie had zich al 196 minuten niet gemeld en er
stonden 62 opdrachten te wachten. Alles werkte, alleen stond zijn computer uit.
Hij kon dat nergens zien, want hij kijkt niet op het dashboard: hij merkte het
pas toen hij dacht dat het product stuk was.

De extensie doet het echte plaatsen, dus zonder een draaiende Chrome gebeurt er
niets. Dat is een gegeven. Wat we wél kunnen: het meteen zeggen, in plaats van
de klant het zelf te laten ontdekken.

Bewust terughoudend:
* alleen tussen 10:00 en 20:00 (NL), want de nachtelijke herplaatsronde zet bij
  iedereen rond 02:30 werk klaar en niemand wil daar om drie uur 's nachts een
  mail over;
* alleen als het werk al minstens drie uur staat te wachten, zodat een verse
  klik van net nooit een mail oplevert;
* hoogstens één mail per 24 uur per klant;
* alleen bij klanten die de extensie ooit hebben gebruikt (er is een hartslag)
  en die een lopende proef of abonnement hebben.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# De extensie meldt zich bij elke poll (elke 15 seconden) en bij elke stap van
# een opdracht. Drie uur stilte is dus geen hikje maar een computer die uit staat.
STIL_NA = timedelta(hours=3)
WACHT_MINSTENS = timedelta(hours=3)
STILTE_NA_MAIL = timedelta(hours=24)
VROEGSTE_UUR = 10
LAATSTE_UUR = 20
NL = ZoneInfo("Europe/Amsterdam")

SCHRIJVEND = ("create", "delete", "content_refresh")
LEVENDE_ABONNEMENTEN = ("trialing", "active")
MAX_WACHTRIJ = 5000

# Vangnet voor het geval de markeerkolom nog niet in Supabase staat: dan onthoudt
# de server het zelf. Dat overleeft geen herstart, dus de kolom blijft beter.
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


def _stilte_in_woorden(uren: int) -> str:
    """"591 hours" leest als een computerfout, niet als een mededeling. Gemeten op
    echte gegevens: een stille extensie staat al snel weken stil, dus boven de twee
    dagen tellen we in dagen."""
    if uren < 48:
        return f"{uren} hours" if uren != 1 else "1 hour"
    dagen = uren // 24
    return f"{dagen} days"


def offline_mail(aantal: int, uren: int) -> tuple[str, str]:
    """De mail zelf. Kort, gevolg vooraan, geen verwijt en geen jargon."""
    from backend.services.billing import CONTACT_EMAIL

    onderwerp = (f"{aantal} listing is waiting for your computer" if aantal == 1
                 else f"{aantal} listings are waiting for your computer")
    tekst = f"""Hi,

Omnivaleur has {aantal} listing{'' if aantal == 1 else 's'} queued for you, but we have not heard from
your computer for {_stilte_in_woorden(uren)}.

The Omnivaleur extension does the actual posting, so Chrome needs to be running
on the computer where you installed it. Open Chrome again and the queue starts
on its own. You do not have to click anything, and nothing is lost in the
meantime: everything stays in the queue until your computer is back.

If this keeps happening, just reply to this email and I will help you set it up
so you no longer have to think about it.

Best regards,

Daniel
Founder, Omnivaleur
{CONTACT_EMAIL}
"""
    return onderwerp, tekst


def _hartslagen(db) -> list[dict]:
    """De hele hartslagtabel: één rij per klant, dus klein genoeg om in één keer
    op te halen. Bewust geen .in_() op gebruikers-id's: boven de zeshonderd id's
    breekt PostgREST stil af."""
    global _kolom_ontbreekt
    if not _kolom_ontbreekt:
        try:
            return (db.table("extension_heartbeat")
                    .select("user_id,last_seen,offline_mail_sent_at").execute().data or [])
        except Exception as e:
            tekst = str(e)
            if "42703" in tekst or "does not exist" in tekst.lower():
                _kolom_ontbreekt = True
                logger.error(
                    "Kolom offline_mail_sent_at ontbreekt nog in extension_heartbeat. De "
                    "waarschuwing draait nu op servergeheugen en kan zich na een herstart "
                    "herhalen. Zet hem erbij met: ALTER TABLE extension_heartbeat "
                    "ADD COLUMN offline_mail_sent_at timestamptz;"
                )
            else:
                raise
    return (db.table("extension_heartbeat").select("user_id,last_seen").execute().data or [])


def _al_gemaild(rij: dict, now: datetime) -> bool:
    laatst = _parse_ts(rij.get("offline_mail_sent_at")) or _gemaild_uit_geheugen.get(rij["user_id"])
    return bool(laatst and now - laatst < STILTE_NA_MAIL)


def _markeer(db, user_id: str, now: datetime) -> None:
    _gemaild_uit_geheugen[user_id] = now
    if _kolom_ontbreekt:
        return
    try:
        (db.table("extension_heartbeat")
         .update({"offline_mail_sent_at": now.isoformat()}).eq("user_id", user_id).execute())
    except Exception as e:
        logger.error(f"Kon offline-waarschuwing niet afvinken voor {user_id}: {e}")


async def waarschuw_offline_extensies(now: datetime | None = None) -> int:
    """Draait elk uur. Geeft terug hoeveel mails er zijn verstuurd.

    `now` is er alleen zodat een test een tijdstip kan vastzetten."""
    from backend.database import get_admin_db, get_db
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    now = now or datetime.now(timezone.utc)
    uur = now.astimezone(NL).hour
    if not VROEGSTE_UUR <= uur < LAATSTE_UUR:
        return 0

    db = get_db()
    wachtend = (db.table("jobs").select("user_id,created_at")
                .eq("status", "pending").in_("action", list(SCHRIJVEND))
                .limit(MAX_WACHTRIJ).execute().data or [])
    if not wachtend:
        return 0

    per_klant: dict[str, dict] = {}
    for job in wachtend:
        uid = job.get("user_id")
        if not uid:
            continue
        gemaakt = _parse_ts(job.get("created_at"))
        stand = per_klant.setdefault(uid, {"aantal": 0, "oudste": None})
        stand["aantal"] += 1
        if gemaakt and (stand["oudste"] is None or gemaakt < stand["oudste"]):
            stand["oudste"] = gemaakt

    levend = {r["user_id"] for r in (db.table("subscriptions").select("user_id,status")
                                     .in_("status", list(LEVENDE_ABONNEMENTEN))
                                     .execute().data or []) if r.get("user_id")}

    verstuurd = 0
    for rij in _hartslagen(db):
        uid = rij.get("user_id")
        stand = per_klant.get(uid)
        if not stand or uid not in levend:
            continue
        gezien = _parse_ts(rij.get("last_seen"))
        if not gezien or now - gezien < STIL_NA:
            continue
        if not stand["oudste"] or now - stand["oudste"] < WACHT_MINSTENS:
            continue
        if _al_gemaild(rij, now):
            continue

        try:
            gebruiker = get_admin_db().auth.admin.get_user_by_id(uid)
            adres = gebruiker.user.email if gebruiker and gebruiker.user else None
        except Exception as e:
            # Zelfde valkuil als bij de proefherinneringen: met de anon-sleutel
            # geeft Supabase hier "User not allowed" en verstuurt de server stil
            # niets. Zie /health → supabase_key_role.
            logger.error(f"Offline-waarschuwing niet verstuurd aan {uid}: adres niet op te "
                         f"vragen ({e}). Draait de server op de anon-sleutel?")
            continue
        if not adres:
            continue

        uren = int((now - gezien).total_seconds() // 3600)
        onderwerp, tekst = offline_mail(stand["aantal"], uren)
        if send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL):
            _markeer(db, uid, now)
            verstuurd += 1
            logger.info(f"Offline-waarschuwing naar {adres}: {stand['aantal']} wachtend, {uren} uur stil")
    return verstuurd
