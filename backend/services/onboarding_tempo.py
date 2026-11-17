"""Hoe snel komt een nieuwe klant van aanmelding tot een echte advertentie online?

WAAROM DIT BESTAAT (17-11-2026)
Op 16-11-2026 is de onboarding versneld (inlezen start vanzelf, snelle import, eerste
plaatsing met een knop). Of dat werkt weet je pas als je de tijd van aanmelding tot
eerste live advertentie voor en na die wijziging naast elkaar legt. Dit script doet
dat, elke keer opnieuw, uit de tijdstempels die er al zijn. Er wordt niets bijgehouden
dat kan zoekraken: draai het op elk moment en je krijgt dezelfde uitkomst.

MEETPUNTEN (per klant, vanaf aanmelding)
  1. eerste_opdracht : eerste gelukte opdracht van welke soort ook (de extensie draait)
  2. eerste_artikel  : eerste artikel in de voorraad (inlezen is begonnen)
  3. eerste_live     : eerste gelukte plaatsing (action create, status done)

GROEPEN
  voor  = aangemeld vóór de wijziging (VOOR_TOT)
  na    = aangemeld erna
  en per aanmeldweek, zodat een trend zichtbaar is.

EERLIJKHEID OVER DE CIJFERS
- Een klant van 3 uur oud kan nog niet "binnen 24 uur live" zijn. Percentages binnen X
  uur tellen daarom alleen klanten die minstens X uur oud zijn.
- De mediaan telt alleen klanten die het punt bereikten. Daarom staat "bereikt" erbij:
  een mediaan van 2 uur bij 10% bereikt zegt weinig.
- Eigen en test-accounts (omnivaleur.com, crosslisteu.com) en onbevestigde aanmeldingen
  tellen niet mee.
- Kleine groepen (minder dan 10 klanten) krijgen een waarschuwing; die cijfers zijn
  richting, geen bewijs.

LICHT OP DE DATABASE: alles per user_id, 1 rij per vraag (kennisbank, meten-op-de-productiedatabase).

GEBRUIK
    Handmatig: python3.13 scripts/onboarding_tempo.py. Automatisch: de zondagsmail
    (backend/services/analytics_report.py) roept meet() aan.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

# Commit 344e3893, "inlezen start vanzelf", 16-11-2026 15:51 NL = 14:51 UTC.
VOOR_TOT = datetime(2026, 11, 16, 14, 51, tzinfo=timezone.utc)
EIGEN_DOMEINEN = ("omnivaleur.com", "crosslisteu.com")
MIN_GROEP = 10
PUNTEN = ("eerste_opdracht", "eerste_artikel", "eerste_live")
DREMPELS_UUR = (1, 24, 72)


def _tijd(s):
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def accounts(admin, sinds):
    uit = {}
    for pagina in range(1, 51):
        gevonden = admin.auth.admin.list_users(page=pagina, per_page=200)
        for u in gevonden or []:
            uit[u.id] = u
        if not gevonden or len(gevonden) < 200:
            break
    if not uit:
        raise RuntimeError("Nul accounts gelezen: kapotte meting, geen lege lijst.")
    lijst = []
    for uid, u in uit.items():
        aangemeld = _tijd(str(u.created_at))
        mail = (u.email or "").lower()
        if (aangemeld and aangemeld >= sinds and u.email_confirmed_at
                and not mail.endswith(EIGEN_DOMEINEN)):
            lijst.append((uid, aangemeld))
    return sorted(lijst, key=lambda x: x[1])


def een(vraag, kolom):
    rij = (vraag.order(kolom).limit(1).execute().data or [{}])[0]
    return _tijd(rij.get(kolom))


def meet_klant(db, uid, aangemeld):
    t_opdracht = een(db.table("jobs").select("done_at").eq("user_id", uid)
                     .eq("status", "done").not_.is_("done_at", "null"), "done_at")
    t_artikel = een(db.table("items").select("created_at").eq("user_id", uid), "created_at")
    t_live = een(db.table("jobs").select("done_at").eq("user_id", uid).eq("action", "create")
                 .eq("status", "done").not_.is_("done_at", "null"), "done_at")
    uit = {"aangemeld": aangemeld}
    for naam, t in zip(PUNTEN, (t_opdracht, t_artikel, t_live)):
        uit[naam] = (t - aangemeld).total_seconds() / 3600 if t and t >= aangemeld else None
    return uit


def samenvat(klanten, nu):
    s = {"klanten": len(klanten), "waarschuwing": len(klanten) < MIN_GROEP}
    for p in PUNTEN:
        uren = [k[p] for k in klanten if k[p] is not None]
        s[p] = {
            "bereikt": len(uren),
            "mediaan_uur": round(statistics.median(uren), 1) if uren else None,
            "binnen": {},
        }
        for u in DREMPELS_UUR:
            oud_genoeg = [k for k in klanten if (nu - k["aangemeld"]).total_seconds() / 3600 >= u]
            goed = [k for k in oud_genoeg if k[p] is not None and k[p] <= u]
            s[p]["binnen"][f"{u}u"] = (
                {"van": len(oud_genoeg), "aantal": len(goed),
                 "pct": round(100 * len(goed) / len(oud_genoeg)) if oud_genoeg else None})
    return s


def maandag(d):
    return (d - timedelta(days=d.weekday())).date().isoformat()


def meet(dagen=90, db=None, admin=None, nu=None):
    nu = nu or datetime.now(timezone.utc)
    if db is None:
        from backend.database import get_admin_db, get_db
        db, admin = get_db(), get_admin_db()
    sinds = nu - timedelta(days=dagen)
    klanten = []
    for uid, aangemeld in accounts(admin, sinds):
        k = meet_klant(db, uid, aangemeld)
        k["uid"] = uid
        klanten.append(k)
    groepen = {
        "voor": [k for k in klanten if k["aangemeld"] < VOOR_TOT],
        "na": [k for k in klanten if k["aangemeld"] >= VOOR_TOT],
    }
    weken = {}
    for k in klanten:
        weken.setdefault(maandag(k["aangemeld"]), []).append(k)
    return {
        "gemeten_op": nu.isoformat(), "wijziging_op": VOOR_TOT.isoformat(),
        "voor": samenvat(groepen["voor"], nu), "na": samenvat(groepen["na"], nu),
        "per_week": {w: samenvat(v, nu) for w, v in sorted(weken.items())},
    }
