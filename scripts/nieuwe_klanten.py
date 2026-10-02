#!/usr/bin/env python3
"""Nieuwe klanten in hun eerste week: wie zijn het, wat verkopen ze, waar lopen ze tegenaan.

WAAROM DIT BESTAAT (29-09-2026)
De eerste uren beslissen of iemand blijft. Gemeten op 27-09-2026 (kennisbank,
trechter-aanmelding-tot-betalend-27-09): wie onder de 30 artikelen inlas betaalde
nooit, en de afhakers die wél voorraad inlazen vertrokken vaak na een
publicatiefout. Daniel wil dat elke ochtend iemand per nieuwe klant nagaat of
alles loopt, en dat repareert voor de klant zelf weer opstart.

Dit script is de meting daarvoor, niet de reparatie. Het telt alleen (geen AI,
geen tokens). De ochtendroutine (docs/routines/onboarding-nieuwe-klanten.md)
leest de uitkomst, zoekt de oorzaken en repareert.

LICHT OP DE DATABASE
De productiedatabase viel twee keer om op een meting over meerdere klanten
(kennisbank, meten-op-de-productiedatabase). Daarom alles per user_id, alleen
kleine kolommen, gepagineerd op id, en `result` alleen op de foutrijen, per id.
Gemeten op het grootste account: 0,1 tot 0,2 seconde per vraag.

GEBRUIK
    python3 scripts/nieuwe_klanten.py                    # klanten van de laatste 7 dagen
    python3 scripts/nieuwe_klanten.py --dagen 2
    python3 scripts/nieuwe_klanten.py --klant <user_id>  # één klant, ook als hij ouder is
    python3 scripts/nieuwe_klanten.py --json
    python3 scripts/nieuwe_klanten.py gezien <user_id> "wat de routine deed"
"""
from __future__ import annotations

import argparse
import email
import email.header
import email.utils
import functools
import imaplib
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mail_analyse as A  # noqa: E402
import klantfouten as K  # noqa: E402
import tel_extensieversies as V  # noqa: E402

STAAT_SLEUTEL = "onboarding_klanten"
FASE_DAGEN = 7            # de proefweek: zolang volgen we een klant dagelijks
MAX_RIJEN = 5000          # per tabel per klant; daarboven zegt het rapport dat het afgekapt is
MAX_FOUTTEKSTEN = 60      # hoeveel foutrijen we per klant op id nalezen
VAST_NA_MIN = 60
WEINIG_ARTIKELEN = 30     # 0 tot 29 ingelezen: nul betalend (gemeten 27-09-2026)
EIGEN_DOMEINEN = ("omnivaleur.com", "crosslisteu.com")
AMS = ZoneInfo("Europe/Amsterdam")
# Daniels postvak, zoals in leadgen-mail.yml. Alleen het wachtwoord (MAIL_PASS) is geheim.
POSTVAK = ("imap.zoho.eu", "daniel@omnivaleur.nl")
SLEUTELHANGER = ("daniel@omnivaleur.nl", "omnivaleur-leadgen-mail")
# "Klanten": sinds 01-10-2026 zet een Zoho-filter alle mail aan info@omnivaleur.com daar.
POSTVAK_MAPPEN = ("INBOX", "Klanten", "Beantwoord", "Verzonden")
# Waar eerdere sessies over klanten schreven. Het geheugen is per account; ontbreekt
# het op deze machine, dan zegt het rapport dat.
GEHEUGEN = Path.home() / ".claude" / "projects" / "-Users-Danie-Documents-omnivaleur" / "memory"


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _tijd(s) -> datetime | None:
    return K._tijd(s) if s else None


def _lokaal(t: datetime | None) -> str:
    return t.astimezone(AMS).strftime("%d-%m %H:%M") if t else "nooit"


def _versie(v: str | None) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except (TypeError, ValueError):
        return ()


def nieuwste_extensie() -> str:
    """De versie die in de repo klaarstaat. De Web Store loopt daar vaak op achter."""
    try:
        return json.loads((REPO / "extension" / "manifest.json").read_text())["version"]
    except (OSError, ValueError, KeyError):
        return ""


@functools.cache
def winkelversie() -> str:
    """Wat Chrome bij een update echt binnenkrijgt. Leeg als de Web Store niet antwoordt."""
    return V.winkelversie() or ""


def categoriegroep(categorie: str | None) -> str:
    """Dezelfde indeling als het beheerdashboard; één plek, zodat ze niet uit elkaar groeien."""
    sys.path.insert(0, str(REPO))
    from backend.api.beheer import _categoriegroep
    return _categoriegroep(categorie)


def _alle(vraag_maker, kolom_order: str = "id") -> tuple[list[dict], bool]:
    """Pagineert op id (zonder volgorde mist PostgREST rijen). Geeft (rijen, afgekapt)."""
    rijen: list[dict] = []
    while len(rijen) < MAX_RIJEN:
        stuk = vraag_maker().order(kolom_order).range(len(rijen), len(rijen) + 999).execute().data or []
        rijen.extend(stuk)
        if len(stuk) < 1000:
            return rijen, False
    return rijen[:MAX_RIJEN], True


# ---------------------------------------------------------------- meten

def accounts(db_admin) -> dict[str, dict]:
    """Alle accounts met aanmeldmoment. Vereist de service-rolsleutel."""
    uit: dict[str, dict] = {}
    for pagina in range(1, 21):
        gevonden = db_admin.auth.admin.list_users(page=pagina, per_page=200)
        for u in gevonden or []:
            uit[u.id] = {"email": u.email or "", "aangemeld": _tijd(str(u.created_at)),
                         "laatste_login": _tijd(str(u.last_sign_in_at)) if u.last_sign_in_at else None}
        if not gevonden or len(gevonden) < 200:
            break
    if not uit:
        raise RuntimeError("Nul accounts gelezen: dat is een kapotte meting, geen lege klantenlijst.")
    return uit


def nieuwe(alle: dict[str, dict], dagen: int, nu: datetime) -> list[str]:
    grens = nu - timedelta(days=dagen)
    return sorted((uid for uid, a in alle.items()
                   if a["aangemeld"] and a["aangemeld"] >= grens
                   and not a["email"].lower().endswith(EIGEN_DOMEINEN)),
                  key=lambda uid: alle[uid]["aangemeld"], reverse=True)


def profiel(db, uid: str, account: dict, nu: datetime) -> dict:
    """Alles wat we van één klant weten, per user_id gelezen."""
    p: dict = {"user_id": uid, "email": account["email"],
               "aangemeld": account["aangemeld"], "laatste_login": account["laatste_login"],
               "afgekapt": []}

    abo = (db.table("subscriptions").select("status,trial_ends_at,stripe_subscription_id")
           .eq("user_id", uid).limit(1).execute().data or [{}])[0]
    p["abonnement"] = {"status": abo.get("status") or "geen", "proef_tot": _tijd(abo.get("trial_ends_at")),
                       "kaart": bool(abo.get("stripe_subscription_id"))}

    hart = (db.table("extension_heartbeat").select("last_seen,ext_version")
            .eq("user_id", uid).limit(1).execute().data or [{}])[0]
    p["extensie"] = {"versie": hart.get("ext_version"), "laatst": _tijd(hart.get("last_seen"))}

    items, kap = _alle(lambda: db.table("items").select(
        "id,category,brand,size,price,created_at").eq("user_id", uid))
    if kap:
        p["afgekapt"].append("artikelen")
    zonder_foto = (db.table("items").select("id", count="exact").eq("user_id", uid)
                   .eq("photo_urls", "{}").limit(1).execute().count or 0)
    prijzen = [float(i["price"]) for i in items if i.get("price")]
    groepen = Counter(categoriegroep(i.get("category")) for i in items)
    p["voorraad"] = {
        "aantal": len(items),
        "eerste": min((_tijd(i["created_at"]) for i in items if i.get("created_at")), default=None),
        "groepen": groepen.most_common(4),
        "rubrieken": Counter(i.get("category") or "(geen)" for i in items).most_common(5),
        "merken": Counter(i["brand"] for i in items if i.get("brand")).most_common(5),
        "prijs": (min(prijzen), statistics.median(prijzen), max(prijzen)) if prijzen else None,
        "zonder_prijs": sum(1 for i in items if not i.get("price")),
        "zonder_foto": zonder_foto,
        "maat_overige": sum(1 for i in items if str(i.get("size") or "").strip().lower()
                            in ("overige", "other", "anders")
                            and categoriegroep(i.get("category")) in ("Kleding", "Schoenen")),
    }

    kandidaten, kap = _alle(lambda: db.table("import_candidates").select("id,platform,status")
                            .eq("user_id", uid))
    if kap:
        p["afgekapt"].append("importkandidaten")
    p["import"] = Counter(f"{k['platform']}:{k['status']}" for k in kandidaten).most_common()

    advertenties, kap = _alle(lambda: db.table("listings").select(
        "id,platform,status,items!inner(user_id)").eq("items.user_id", uid))
    if kap:
        p["afgekapt"].append("advertenties")
    p["advertenties"] = Counter(f"{a['platform']}:{a['status']}" for a in advertenties).most_common()

    kanalen = (db.table("platform_credentials").select("platform").eq("user_id", uid)
               .execute().data or [])
    # `_settings` is geen kanaal maar de rij met zijn Preferences (locatie, levering).
    p["koppelingen"] = sorted({k["platform"] for k in kanalen if not k["platform"].startswith("_")})
    p["voorkeuren_ingevuld"] = any(k["platform"] == "_settings" for k in kanalen)

    grens = (account["aangemeld"] or nu - timedelta(days=FASE_DAGEN)).isoformat()
    jobs, kap = _alle(lambda: db.table("jobs").select(
        "id,platform,action,status,created_at,done_at,scheduled_for")
        .eq("user_id", uid).gte("created_at", grens))
    if kap:
        p["afgekapt"].append("opdrachten")
    p["opdrachten"] = Counter(f"{j['platform']} {j['action']}:{j['status']}" for j in jobs).most_common()
    eerste_gelukt: dict[str, datetime] = {}
    for j in jobs:
        t = _tijd(j.get("done_at"))
        if j["action"] == "create" and j["status"] == "done" and t:
            if j["platform"] not in eerste_gelukt or t < eerste_gelukt[j["platform"]]:
                eerste_gelukt[j["platform"]] = t
    p["eerste_gelukt"] = eerste_gelukt

    vast = []
    for j in jobs:
        if j["status"] not in ("pending", "claimed"):
            continue
        sinds = max(filter(None, [_tijd(j.get("created_at")), _tijd(j.get("scheduled_for"))]),
                    default=None)
        if sinds and sinds <= nu and nu - sinds > timedelta(minutes=VAST_NA_MIN):
            vast.append((j["platform"], j["action"], j["status"], sinds))
    p["vast"] = Counter(f"{v[0]} {v[1]}:{v[2]}" for v in vast).most_common()
    p["vast_oudste"] = min((v[3] for v in vast), default=None)

    fout_jobs = sorted((j for j in jobs if j["status"] == "error"),
                       key=lambda j: j.get("done_at") or "", reverse=True)[:MAX_FOUTTEKSTEN]
    p["fouten"] = foutsoorten(db, fout_jobs)
    p["signalen"] = signalen(p, nu)
    return p


def foutsoorten(db, fout_jobs: list[dict]) -> list[dict]:
    """Fouttekst per id nalezen (nooit `result` over een bereik) en groeperen per soort."""
    per_id = {j["id"]: j for j in fout_jobs}
    teksten: dict[str, str] = {}
    ids = list(per_id)
    for i in range(0, len(ids), 20):
        for r in (db.table("jobs").select("id,fout:result->>error").in_("id", ids[i:i + 20])
                  .execute().data or []):
            teksten[r["id"]] = r.get("fout") or "(geen fouttekst)"
    soorten: dict[str, dict] = {}
    for jid, j in per_id.items():
        tekst = teksten.get(jid, "(niet gelezen)")
        s = soorten.setdefault(K.soort(j["platform"], j["action"], tekst),
                               {"kanaal": j["platform"], "handeling": j["action"],
                                "tekst": tekst[:240], "aantal": 0, "voorbeeld_job": jid})
        s["aantal"] += 1
    return sorted(({"soort": k, **v} for k, v in soorten.items()), key=lambda s: -s["aantal"])


def signalen(p: dict, nu: datetime) -> list[str]:
    """Wat een mens meteen moet zien. Elk signaal is een feit uit de meting, geen gok."""
    uit = []
    uren = (nu - p["aangemeld"]).total_seconds() / 3600 if p["aangemeld"] else 0
    ext, v = p["extensie"], p["voorraad"]
    if not ext["laatst"]:
        uit.append("GEEN_EXTENSIE: de extensie heeft zich nooit gemeld; zonder extensie plaatst er niets.")
    elif nu - ext["laatst"] > timedelta(hours=24) and p["vast"]:
        uit.append(f"EXTENSIE_STIL: laatst gezien {_lokaal(ext['laatst'])} terwijl er werk wacht.")
    elif nu - ext["laatst"] > timedelta(hours=24):
        uit.append(f"NIET_ACTIEF: extensie laatst gezien {_lokaal(ext['laatst'])}, "
                   f"{(nu - ext['laatst']).days} dag(en) geleden.")
    winkel, repo = winkelversie(), nieuwste_extensie()
    if ext["versie"] and winkel and _versie(ext["versie"]) < _versie(winkel):
        uit.append(f"OUDE_EXTENSIE: draait {ext['versie']}, de Web Store levert {winkel}; "
                   "zijn Chrome heeft de update nog niet binnen.")
    elif ext["versie"] and repo and _versie(ext["versie"]) < _versie(repo):
        uit.append(f"WACHT_OP_WEB_STORE: draait {ext['versie']}, de Web Store levert "
                   f"{winkel or '(niet te meten)'}; wat in {repo} gerepareerd is komt pas als Google het vrijgeeft.")
    if v["aantal"] == 0 and uren >= 2:
        uit.append(f"NIETS_INGELEZEN: {uren:.0f} uur na aanmelding nog nul artikelen.")
    elif 0 < v["aantal"] < WEINIG_ARTIKELEN:
        uit.append(f"WEINIG_INGELEZEN: {v['aantal']} artikelen; onder {WEINIG_ARTIKELEN} betaalde nog nooit iemand.")
    creates = sum(n for k, n in p["opdrachten"] if " create:" in k)
    if v["aantal"] and not creates and uren >= 2:
        uit.append("NOG_NIETS_GEPLAATST: wel voorraad, nog geen enkele plaatsopdracht.")
    if creates and not p["eerste_gelukt"]:
        uit.append("NOG_NIETS_GELUKT: plaatsopdrachten wel, nog geen enkele geslaagd.")
    if p["fouten"]:
        uit.append(f"FOUTEN: {sum(f['aantal'] for f in p['fouten'])} mislukte opdrachten in "
                   f"{len(p['fouten'])} soort(en).")
    if p["vast"]:
        uit.append(f"VASTGELOPEN: {sum(n for _, n in p['vast'])} opdrachten langer dan "
                   f"{VAST_NA_MIN} min open, oudste sinds {_lokaal(p['vast_oudste'])}.")
    if v["maat_overige"]:
        uit.append(f"MAAT_OVERIGE: {v['maat_overige']} kledingstukken met maat 'Overige'; "
                   "Marktplaats en 2dehands weigeren die.")
    if v["zonder_prijs"]:
        uit.append(f"ZONDER_PRIJS: {v['zonder_prijs']} artikelen zonder prijs.")
    if v["zonder_foto"]:
        uit.append(f"ZONDER_FOTO: {v['zonder_foto']} artikelen zonder foto.")
    abo = p["abonnement"]
    if (abo["status"] == "trialing" and not abo["kaart"] and abo["proef_tot"]
            and abo["proef_tot"] - nu < timedelta(days=2)):
        uit.append(f"PROEF_BIJNA_OM: proef loopt af {_lokaal(abo['proef_tot'])}, nog geen betaalmethode.")
    if p["afgekapt"]:
        uit.append(f"AFGEKAPT: meer dan {MAX_RIJEN} rijen bij {', '.join(p['afgekapt'])}; tellingen zijn een ondergrens.")
    return uit


# ---------------------------------------------------------------- wat Daniel al met hem had
# Een mailtje aan iemand met wie Daniel al mailde of vanmiddag belt, moet daarop
# aansluiten of wegblijven. Op 29-09-2026 schreef de eerste ronde Vagif aan alsof hij
# een vreemde was, terwijl hij via de koude mail kwam, terugschreef, en er die middag
# een gesprek stond. Elke bron die niet te lezen is zegt dat hardop: niet gelezen is
# niet hetzelfde als geen contact.

def _moment(w) -> datetime | None:
    if isinstance(w, (int, float)):
        return datetime.fromtimestamp(w, timezone.utc)
    return _tijd(w)


def koude_mail(adressen: list[str]) -> dict[str, dict] | str:
    """Wat de koude-mailmachine deze adressen stuurde en wat ze terugschreven."""
    state, reacties = A._lees("mail_state", None), A._lees("mail_reacties", None)
    if not isinstance(state, dict) or not isinstance(reacties, list):
        return "koude-mailgeschiedenis niet te lezen"
    uit = {}
    for adres in adressen:
        s = state.get(adres) or state.get(adres.lower()) or {}
        uit[adres] = {
            "verstuurd": [(m.get("beurt"), _tijd(m.get("op"))) for m in s.get("verstuurd") or []
                          if isinstance(m, dict)],
            "antwoorden": [(_tijd(r.get("op")), r.get("soort"),
                            " ".join(str(r.get("tekst") or "").split())[:160])
                           for r in reacties if isinstance(r, dict)
                           and str(r.get("adres") or "").lower() == adres.lower()],
            "daniel_antwoordde": _moment(s.get("daniel_antwoordde")),
        }
    return uit


def _mailwachtwoord() -> str | None:
    """MAIL_PASS uit de omgeving, anders uit de Mac-sleutelhanger waar de oude
    mailmachine (scripts/leadgen_tick.sh) het al bewaarde. Nooit printen."""
    if os.environ.get("MAIL_PASS"):
        return os.environ["MAIL_PASS"]
    try:
        r = subprocess.run(["security", "find-generic-password", "-a", SLEUTELHANGER[0],
                            "-s", SLEUTELHANGER[1], "-w"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def postvak(adressen: list[str]) -> dict[str, list[dict]] | str:
    """Mail tussen Daniel en deze adressen, heen en terug."""
    wachtwoord = _mailwachtwoord()
    if not wachtwoord:
        return "postvak niet gelezen: geen MAIL_PASS in .env en niets in de sleutelhanger van deze machine"
    uit: dict[str, list[dict]] = {a: [] for a in adressen}
    geopend = []
    try:
        with imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST") or POSTVAK[0], 993, timeout=30) as imap:
            imap.login(os.environ.get("MAIL_USER") or POSTVAK[1], wachtwoord)
            for map_ in POSTVAK_MAPPEN:
                if imap.select(f'"{map_}"', readonly=True)[0] != "OK":
                    continue
                geopend.append(map_)
                for adres in adressen:
                    _, d = imap.search(None, f'(OR FROM "{adres}" TO "{adres}")')
                    for num in (d[0] or b"").split()[-5:]:
                        _, delen = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (DATE SUBJECT)])")
                        kop = email.message_from_bytes(delen[0][1])
                        uit[adres].append({"map": map_, "datum": _maildatum(kop.get("Date")),
                                           "onderwerp": str(email.header.make_header(
                                               email.header.decode_header(kop.get("Subject") or "")))[:90]})
    except (OSError, imaplib.IMAP4.error) as e:
        return f"postvak niet gelezen: {e}"
    if not geopend:
        return "postvak niet gelezen: geen van de mappen te openen"
    for lijst in uit.values():
        lijst.sort(key=lambda m: m["datum"] or datetime.min.replace(tzinfo=timezone.utc))
    return uit


def _maildatum(w) -> datetime | None:
    try:
        return email.utils.parsedate_to_datetime(w)
    except (TypeError, ValueError):
        return None


def vermeldingen(adres: str, uid: str) -> list[str]:
    """Kopjes in team-notes en kennisbank, en geheugenbestanden, die deze klant noemen."""
    zoek = [t for t in (adres.lower(), uid[:8].lower()) if t and t != "?"]
    uit: list[str] = []
    for naam in ("team-notes", "kennisbank"):
        kop, gevonden = "", []
        for regel in (REPO / "docs" / f"{naam}.md").read_text(errors="replace").splitlines():
            if regel.startswith("#"):
                kop = regel.lstrip("# ").strip()
            if kop and any(t in regel.lower() for t in zoek) and kop not in gevonden:
                gevonden.append(kop)
        uit += [f"{naam}: {k}" for k in gevonden[-6:]]
    if not GEHEUGEN.is_dir():
        return uit + ["geheugen: niet op deze machine"]
    for pad in sorted(GEHEUGEN.glob("*.md")):
        if pad.name != "MEMORY.md" and any(t in pad.read_text(errors="replace").lower() for t in zoek):
            uit.append(f"geheugen: {pad.stem}")
    return uit


def contact(profielen: list[dict]) -> None:
    """Hangt koude mail, postvak en vermeldingen aan elk profiel."""
    adressen = [p["email"] for p in profielen if "@" in (p["email"] or "")]
    koud, post = koude_mail(adressen), postvak(adressen)
    # De automatische importherinnering (backend/services/import_herinnering.py).
    herinnerd = A._lees("import_herinnering", None)
    for p in profielen:
        p["importherinnering"] = (herinnerd.get(p["user_id"]) if isinstance(herinnerd, dict)
                                  else "niet te lezen")
        p["koude_mail"] = koud if isinstance(koud, str) else koud.get(p["email"])
        p["postvak"] = post if isinstance(post, str) else post.get(p["email"], [])
        p["vermeldingen"] = vermeldingen(p["email"] or "", p["user_id"])


def _contactregels(p: dict) -> list[str]:
    k, post = p.get("koude_mail"), p.get("postvak")
    if isinstance(k, str):
        koud = k
    elif k and (k["verstuurd"] or k["antwoorden"]):
        koud = ", ".join(f"{b} {_lokaal(t)}" for b, t in k["verstuurd"])
        koud += "".join(f"; antwoordde {_lokaal(t)} ({s}): \"{x}\"" for t, s, x in k["antwoorden"])
        if k["daniel_antwoordde"]:
            koud += f"; Daniel antwoordde {_lokaal(k['daniel_antwoordde'])}"
    else:
        koud = "nooit koud gemaild"
    if isinstance(post, str):
        mails = post
    else:
        mails = (f"{len(post)} mail(s): " + "; ".join(
            f"{_lokaal(m['datum'])} {m['map']} \"{m['onderwerp']}\"" for m in post[-5:])) if post else "geen mail"
    herinnerd = p.get("importherinnering")
    herinnering = (_lokaal(_tijd(herinnerd)) if herinnerd and herinnerd != "niet te lezen"
                   else herinnerd or "niet verstuurd")
    return [f"   koude mail: {koud}", f"   postvak: {mails}",
            f"   automatische importherinnering: {herinnering}",
            f"   genoemd in: {' | '.join(p.get('vermeldingen') or []) or 'nergens'}"]


# ---------------------------------------------------------------- staat en uitvoer

def staat() -> dict:
    return A._lees(STAAT_SLEUTEL, {}) or {}


def gezien(uid: str, samenvatting: str) -> bool:
    fout = A._bereikbaar()
    if fout:
        print(f"Gedeelde opslag niet te lezen ({fout}); niets vastgelegd.")
        return False
    alles = staat()
    oud = alles.get(uid) or {}
    alles[uid] = {"eerst_gezien": oud.get("eerst_gezien") or _nu().isoformat(),
                  "laatst": _nu().isoformat(), "rondes": int(oud.get("rondes") or 0) + 1,
                  "samenvatting": samenvatting[:600]}
    return A._schrijf(STAAT_SLEUTEL, alles)


def tekst(p: dict, vorige: dict | None, nu: datetime) -> str:
    uren = (nu - p["aangemeld"]).total_seconds() / 3600 if p["aangemeld"] else 0
    kop = "NIEUW" if not vorige else f"volgen, ronde {int(vorige.get('rondes') or 0) + 1}"
    v, ext, abo = p["voorraad"], p["extensie"], p["abonnement"]
    regels = [f"== {p['user_id']}  {p['email']}  [{kop}]",
              f"   aangemeld {_lokaal(p['aangemeld'])} ({uren:.0f} uur geleden), "
              f"laatst ingelogd {_lokaal(p['laatste_login'])}",
              f"   abonnement: {abo['status']}, proef tot {_lokaal(abo['proef_tot'])}, "
              f"{'betaalmethode ingesteld' if abo['kaart'] else 'geen betaalmethode'}",
              f"   extensie: {ext['versie'] or '-'}, laatst gezien {_lokaal(ext['laatst'])}"]
    if vorige:
        regels.append(f"   vorige ronde ({str(vorige.get('laatst'))[:16]} UTC): {vorige.get('samenvatting')}")
    if "koude_mail" in p:
        regels += _contactregels(p)
    prijs = (f"prijs {v['prijs'][0]:.0f} tot {v['prijs'][2]:.0f}, mediaan {v['prijs'][1]:.0f}"
             if v["prijs"] else "geen prijzen")
    regels += [f"   voorraad: {v['aantal']} artikelen (eerste {_lokaal(v['eerste'])}), {prijs}",
               f"   verkoopt: {', '.join(f'{g} {n}' for g, n in v['groepen']) or '-'}",
               f"   rubrieken: {', '.join(f'{r} {n}' for r, n in v['rubrieken']) or '-'}",
               f"   merken: {', '.join(f'{m} {n}' for m, n in v['merken']) or '-'}",
               f"   ingelezen uit: {', '.join(f'{k} {n}' for k, n in p['import']) or '-'}",
               f"   koppelingen: {', '.join(p['koppelingen']) or '-'}; Preferences "
               f"{'ingevuld' if p['voorkeuren_ingevuld'] else 'nooit opgeslagen'}",
               f"   advertenties: {', '.join(f'{k} {n}' for k, n in p['advertenties']) or '-'}",
               f"   opdrachten: {', '.join(f'{k} {n}' for k, n in p['opdrachten']) or '-'}",
               "   eerste geslaagde plaatsing: " + (", ".join(
                   f"{k} {_lokaal(t)} ({(t - p['aangemeld']).total_seconds() / 3600:.1f} uur na aanmelding)"
                   for k, t in sorted(p["eerste_gelukt"].items())) or "nog geen")]
    for f in p["fouten"]:
        regels.append(f"   fout {f['aantal']}x {f['kanaal']} {f['handeling']} [{f['soort']}, "
                      f"bv. job {f['voorbeeld_job']}]: {f['tekst']}")
    regels += [f"   ! {s}" for s in p["signalen"]] or ["   geen signalen"]
    return "\n".join(regels)


def _json(o):
    return o.isoformat() if isinstance(o, datetime) else str(o)


def main() -> None:
    A._omgeving_uit_env_bestand()
    if len(sys.argv) >= 3 and sys.argv[1] == "gezien":
        sys.exit(0 if gezien(sys.argv[2], " ".join(sys.argv[3:])) else 1)
    ap = argparse.ArgumentParser(description="Nieuwe klanten in hun eerste week.")
    ap.add_argument("--dagen", type=int, default=FASE_DAGEN)
    ap.add_argument("--klant", help="één user_id, ook ouder dan het venster")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, str(REPO))
    from backend.database import get_admin_db, get_db
    nu = _nu()
    alle = accounts(get_admin_db())
    uids = [args.klant] if args.klant else nieuwe(alle, args.dagen, nu)
    db, vorig = get_db(), staat()
    profielen = [profiel(db, uid, alle.get(uid) or {"email": "?", "aangemeld": None,
                                                   "laatste_login": None}, nu) for uid in uids]
    contact(profielen)
    if args.json:
        print(json.dumps(profielen, default=_json, ensure_ascii=False, indent=1))
        return
    nieuw = sum(1 for p in profielen if p["user_id"] not in vorig)
    print(f"{len(alle)} accounts gelezen; {len(profielen)} in hun eerste {args.dagen} dagen, "
          f"waarvan {nieuw} nog nooit door de routine bekeken. Extensie: repo {nieuwste_extensie()}, "
          f"Web Store levert {winkelversie() or '(niet te meten)'}.\n")
    for p in profielen:
        print(tekst(p, vorig.get(p["user_id"]), nu) + "\n")


if __name__ == "__main__":
    main()
