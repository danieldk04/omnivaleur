"""
Wekelijkse momentopname van de marketing- en bezorgcijfers.

WAAROM DIT BESTAAT
De open-, bounce- en bezorgcijfers van de koude mail stonden alleen in het
Resend-dashboard en in mail_state/mail_opens. Resend moet je openen, en
mail_state wordt opgeschoond, dus er was geen historie en geen vergelijking met
vorige weken. Deze module legt één rij per week vast in `week_metingen`:
aanmeldingen, de mailtrechter per mail 1/2/3, en de bezorging uit `mail_events`
(gevuld door de Resend-webhook).

Wat retroactief kan (aanmeldingen uit auth.users, verzonden/geopend uit
mail_state/mail_opens zolang die er nog staan) vult `backfill` met terugwerkende
kracht. De Resend-velden blijven leeg voor weken vóór de webhook aanstond.

Faalt zacht: een bron die eruit ligt levert None voor dat veld, niet een nul die
als "geen mail verstuurd" leest.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from backend.database import get_admin_db

logger = logging.getLogger(__name__)

_PIXEL_LAGEN = ("mail2", "mail3")


def _maandag_van(d: date) -> date:
    return d - timedelta(days=d.weekday())


def vorige_week_maandag(vandaag: date | None = None) -> date:
    """De maandag van de zojuist afgelopen volle week (ma..zo)."""
    vandaag = vandaag or date.today()
    return _maandag_van(vandaag) - timedelta(days=7)


def _leadgen(naam: str):
    try:
        rijen = get_admin_db().table("leadgen_opslag").select("inhoud").eq("naam", naam).execute().data or []
    except Exception as e:  # noqa: BLE001
        logger.info("leadgen_opslag/%s niet leesbaar: %s", naam, e)
        return None
    return rijen[0].get("inhoud") if rijen else None


def _in_week(iso: str, lo: str, hi: str) -> bool:
    return bool(iso) and lo <= iso[:10] <= hi


def _signups(lo: str, hi: str) -> dict:
    try:
        res = get_admin_db().auth.admin.list_users(page=1, per_page=1000)
        users = res if isinstance(res, list) else getattr(res, "users", []) or []
    except Exception as e:  # noqa: BLE001
        logger.info("Aanmeldingen niet telbaar: %s", e)
        return {"nieuw": None, "bevestigd": None}
    nieuw = bevestigd = 0
    for u in users:
        g = (lambda k: getattr(u, k, None) if not isinstance(u, dict) else u.get(k))
        created = str(g("created_at") or "")
        if _in_week(created, lo, hi):
            nieuw += 1
            if g("email_confirmed_at") or g("confirmed_at"):
                bevestigd += 1
    return {"nieuw": nieuw, "bevestigd": bevestigd}


def _koude_mail(lo: str, hi: str) -> dict:
    state = _leadgen("mail_state")
    opens = _leadgen("mail_opens") or {}
    reacties = _leadgen("mail_reacties") or []

    verzonden = {"mail1": 0, "mail2": 0, "mail3": 0}
    if state is not None:
        for v in state.values():
            for m in (v.get("verstuurd") or []):
                if not isinstance(m, dict):
                    continue
                if _in_week(str(m.get("op") or ""), lo, hi):
                    beurt = str(m.get("beurt") or "")
                    if beurt in verzonden:
                        verzonden[beurt] += 1

    geopend = {"mail2": 0, "mail3": 0}
    for per in opens.values():
        if not isinstance(per, dict):
            continue
        for laag in _PIXEL_LAGEN:
            o = per.get(laag)
            if isinstance(o, dict) and _in_week(str(o.get("eerst") or ""), lo, hi):
                geopend[laag] += 1

    antwoorden = positief = 0
    for r in reacties:
        if isinstance(r, dict) and _in_week(str(r.get("op") or ""), lo, hi):
            antwoorden += 1
            if r.get("soort") == "warm":
                positief += 1

    def pct(deel, geheel):
        return round(100 * deel / geheel, 1) if geheel else None

    return {
        "verstuurd": sum(verzonden.values()) if state is not None else None,
        "mail1": verzonden["mail1"], "mail2": verzonden["mail2"], "mail3": verzonden["mail3"],
        "geopend_mail2": geopend["mail2"], "geopend_mail3": geopend["mail3"],
        "open_pct_mail2": pct(geopend["mail2"], verzonden["mail2"]),
        "open_pct_mail3": pct(geopend["mail3"], verzonden["mail3"]),
        "antwoorden": antwoorden if reacties else None,
        "positief": positief if reacties else None,
        "_gekoppeld": state is not None,
    }


def _bezorging(lo: str, hi: str) -> dict:
    """Uit mail_events (Resend-webhook). Leeg als de webhook die week nog niet liep."""
    hi_ts = f"{hi}T23:59:59+00:00"
    lo_ts = f"{lo}T00:00:00+00:00"
    try:
        rijen = (get_admin_db().table("mail_events")
                 .select("type,domein,gebeurd_op")
                 .gte("gebeurd_op", lo_ts).lte("gebeurd_op", hi_ts)
                 .limit(50000).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.info("mail_events niet leesbaar: %s", e)
        return {}
    if not rijen:
        return {}

    def tel(domein_prefix: str, soort: str) -> int:
        return sum(1 for r in rijen
                   if r.get("type") == soort
                   and str(r.get("domein") or "").startswith(domein_prefix))

    km_afg = tel("omnivaleur.nl", "email.delivered")
    km_bounce = tel("omnivaleur.nl", "email.bounced")
    km_klacht = tel("omnivaleur.nl", "email.complained")
    app_afg = tel("omnivaleur.com", "email.delivered")
    app_bounce = tel("omnivaleur.com", "email.bounced")
    app_sent = tel("omnivaleur.com", "email.sent") or (app_afg + app_bounce)
    noemer = km_afg + km_bounce
    return {
        "km_afgeleverd": km_afg,
        "km_bounced": km_bounce,
        "km_geklaagd": km_klacht,
        "km_bounce_pct": round(100 * km_bounce / noemer, 1) if noemer else None,
        "app_verstuurd": app_sent,
        "app_afgeleverd": app_afg,
        "app_bounced": app_bounce,
    }


def meet_week(maandag: date) -> dict:
    maandag = _maandag_van(maandag)
    zondag = maandag + timedelta(days=6)
    lo, hi = maandag.isoformat(), zondag.isoformat()

    s = _signups(lo, hi)
    km = _koude_mail(lo, hi)
    bez = _bezorging(lo, hi)

    rij = {
        "week_maandag": lo,
        "signups_nieuw": s["nieuw"],
        "signups_bevestigd": s["bevestigd"],
        "km_verstuurd": km["verstuurd"],
        "km_mail1": km["mail1"], "km_mail2": km["mail2"], "km_mail3": km["mail3"],
        "km_geopend_mail2": km["geopend_mail2"], "km_geopend_mail3": km["geopend_mail3"],
        "km_open_pct_mail2": km["open_pct_mail2"], "km_open_pct_mail3": km["open_pct_mail3"],
        "km_antwoorden": km["antwoorden"], "km_positief": km["positief"],
        "km_afgeleverd": bez.get("km_afgeleverd"),
        "km_bounced": bez.get("km_bounced"),
        "km_geklaagd": bez.get("km_geklaagd"),
        "km_bounce_pct": bez.get("km_bounce_pct"),
        "app_verstuurd": bez.get("app_verstuurd"),
        "app_afgeleverd": bez.get("app_afgeleverd"),
        "app_bounced": bez.get("app_bounced"),
        "details": {"venster": [lo, hi], "resend_webhook_liep": bool(bez)},
    }
    return rij


def sla_op(maandag: date) -> dict:
    rij = meet_week(maandag)
    rij["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
    try:
        get_admin_db().table("week_metingen").upsert(rij, on_conflict="week_maandag").execute()
    except Exception as e:  # noqa: BLE001
        logger.error("week_metingen niet opgeslagen (tabel ontbreekt?): %s", e)
        return {"ok": False, "reden": str(e), "rij": rij}
    return {"ok": True, "rij": rij}


def backfill(weken: int = 12, tot: date | None = None) -> list[dict]:
    """De laatste N volle weken opnieuw meten en wegschrijven. Veilig om vaker te
    draaien: het is een upsert op de maandag."""
    laatste = vorige_week_maandag(tot)
    uit = []
    for i in range(weken - 1, -1, -1):
        r = sla_op(laatste - timedelta(days=7 * i))
        uit.append(r)
    return uit


def snapshot_vorige_week() -> dict:
    """Voor de wekelijkse cron: leg de zojuist afgelopen week vast."""
    return sla_op(vorige_week_maandag())


def historie(weken: int = 14) -> list[dict]:
    try:
        rijen = (get_admin_db().table("week_metingen").select("*")
                 .order("week_maandag", desc=True).limit(weken).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.info("week_metingen niet leesbaar: %s", e)
        return []
    return list(reversed(rijen))
