"""
Overzicht van de warme leads voor het marketingdashboard (Daniel, 07-10-2026).

Warm = iemand die op onze mail reageerde of om de video vroeg. Per persoon: wat is
de status, bij wie ligt de bal, hoe vaak is opgevolgd. Dit script leest alleen
(Zoho Verzonden en inbox, Supabase accounts en mail_state) en schrijft één
momentopname naar leadgen_opslag, naam "warme_leads". Het dashboard
(/api/content/analytics) leest die momentopname.

Draait in elke beurt van de leadmachine, maar hooguit eens per 3 uur.
Gebruik: python scripts/warme_leads.py [--nu]
"""
from __future__ import annotations

import collections
import email
import imaplib
import os
import sys
import time
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.leadgen_mail as lm  # noqa: E402

NAAM = "warme_leads"
HOOGSTENS_ELKE_UUR = 3
GENEGEERD = ("mail-tester.com", "brevo-mail.com", "omnivaleur.nl", "omnivaleur.com")
INKOMEND = ("INBOX", "Beantwoord", "Archive", "Klanten", "Automatisch")
DOODGELOPEN_NA_DAGEN = 14


def _ts(m):
    try:
        return parsedate_to_datetime(m.get("Date", "")).timestamp()
    except Exception:  # noqa: BLE001
        return None


def _koppen(imap, ids, velden):
    uit = []
    ids = list(ids)
    for i in range(0, len(ids), 100):
        _, d = imap.fetch(b",".join(ids[i:i + 100]), f"(BODY.PEEK[HEADER.FIELDS ({velden})])")
        uit += [email.message_from_bytes(x[1]) for x in d if isinstance(x, tuple)]
    return uit


def _status(l: dict, nu: float) -> tuple[str, str]:
    """(status, bal) uit de gebeurtenissen van één lead."""
    if l["account"]:
        return "Account genomen", "klaar"
    if l["afgehaakt"]:
        return "Afgehaakt (niet meer mailen of nee)", "klaar"
    if l["laatst_in"] and l["laatst_in"] > (l["laatst_uit"] or 0):
        return "Wacht op jou: ze schreven terug", "jij"
    dagen = (nu - (l["laatst_uit"] or nu)) / 86400
    if l["video_op"]:
        n = l["opvolgingen"]
        if dagen > DOODGELOPEN_NA_DAGEN and n >= 1:
            return "Doodgelopen: geen reactie na opvolging", "klaar"
        if n == 0:
            return ("Video gestuurd, opvolging volgt" if dagen < 3
                    else "Video gestuurd, nog nooit opgevolgd"), "hen" if dagen < 10 else "jij"
        return (f"Opvolging {n} gestuurd" if n == 1 else "Laatste opvolging gestuurd"), "hen"
    return "Gesprek loopt, wacht op hun antwoord", "hen"


def meet() -> dict:
    gebruiker = lm._need("MAIL_USER")
    state = lm._state()
    try:
        klanten = lm._klanten()
    except Exception:  # noqa: BLE001 — onbekend, dan niemand als klant markeren
        klanten = None
    gestopt = set()
    try:
        gestopt = lm.Leadboek().gestopt()
    except Exception:  # noqa: BLE001
        pass
    nu = time.time()
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(gebruiker, os.environ["MAIL_PASS"])
        imap.select('"Verzonden"', readonly=True)
        uit = collections.defaultdict(list)
        for m in _koppen(imap, imap.search(None, "ALL")[1][0].split(), "TO DATE"):
            a, t = parseaddr(m.get("To", ""))[1].lower(), _ts(m)
            if a and t:
                uit[a].append(t)
        video = {}
        ids = set()
        for q in ("omnivaleur.com/mp", "ymDeS37aBW4"):
            ids |= set(imap.search(None, "BODY", f'"{q}"')[1][0].split())
        for m in _koppen(imap, ids, "TO DATE"):
            a, t = parseaddr(m.get("To", ""))[1].lower(), _ts(m)
            if a and t and (a not in video or t < video[a]):
                video[a] = t
        warm = set(video) | {a for a, s in state.items() if isinstance(s, dict) and s.get("beantwoord")}
        warm = {a for a in warm if a and not a.endswith(GENEGEERD)}
        # inkomend sinds 70 dagen voor de oudste video of ons eerste contact
        eerste = min([t for a in warm for t in uit.get(a, [])] or [nu])
        sinds = datetime.fromtimestamp(eerste - 86400).strftime("%d-%b-%Y")
        inn, naam = collections.defaultdict(list), {}
        for map_ in INKOMEND:
            if imap.select(f'"{map_}"', readonly=True)[0] != "OK":
                continue
            ids = imap.search(None, "SINCE", sinds)[1][0].split()
            for m in _koppen(imap, ids, "FROM DATE"):
                nm, a = parseaddr(m.get("From", ""))
                a, t = a.lower(), _ts(m)
                if a in warm and t:
                    inn[a].append(t)
                    naam.setdefault(a, nm)

    leads = []
    for a in warm:
        s = state.get(a, {}) if isinstance(state.get(a), dict) else {}
        t0 = video.get(a)
        # opvolging = onze mail direct na onze eigen mail, zonder antwoord ertussen, na de video
        ev = sorted([(t, "u") for t in uit.get(a, []) if t0 and t > t0 + 60] +
                    [(t, "i") for t in inn.get(a, []) if t0 and t > t0])
        n, vorige = 0, "u"
        for _, soort in ev:
            if soort == "u" and vorige == "u":
                n += 1
            elif soort == "u" and vorige == "i":
                n = 0
            vorige = soort
        l = {
            "adres": a,
            "naam": (s.get("bedrijf") or naam.get(a) or a.split("@")[0])[:60],
            "video_op": t0,
            "eerste_in": min(inn[a]) if inn.get(a) else None,
            "laatst_in": max(inn[a]) if inn.get(a) else None,
            "laatst_uit": max(uit[a]) if uit.get(a) else None,
            "opvolgingen": n,
            "account": (a in klanten) if klanten is not None else False,
            "afgehaakt": bool(a in gestopt or any(s.get(k) for k in
                              ("afgemeld", "afgewezen", "concurrent", "bounce"))),
        }
        l["status"], l["bal"] = _status(l, nu)
        l["dagen_stil"] = round((nu - max(l["laatst_in"] or 0, l["laatst_uit"] or 0)) / 86400)
        leads.append(l)
    volgorde = {"jij": 0, "hen": 1, "klaar": 2}
    leads.sort(key=lambda l: (volgorde[l["bal"]], -l["dagen_stil"] if l["bal"] == "jij" else l["dagen_stil"]))
    v = [l for l in leads if l["video_op"]]
    mailden = len(state)
    ant = sum(1 for s in state.values() if isinstance(s, dict) and s.get("beantwoord"))
    return {
        "tijd": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "klanten_bekend": klanten is not None,
        "samenvatting": {
            "warm": len(leads),
            "wacht_op_jou": sum(1 for l in leads if l["status"].startswith("Wacht op jou")),
            "in_opvolging": sum(1 for l in leads if l["status"].startswith(("Opvolging", "Laatste", "Video gestuurd"))),
            "doodgelopen": sum(1 for l in leads if l["status"].startswith("Doodgelopen")),
            "account": sum(1 for l in leads if l["account"]),
            "video": len(v),
            "video_reactie": sum(1 for l in v if l["laatst_in"] and l["laatst_in"] > l["video_op"]),
            "video_account": sum(1 for l in v if l["account"]),
            "video_nooit_opgevolgd": sum(1 for l in v if l["status"] == "Video gestuurd, nog nooit opgevolgd"),
            "koud_aangeschreven": mailden,
            "koud_beantwoord": ant,
        },
        "leads": leads,
    }


def main(nu: bool) -> None:
    oud = lm._db_lees(NAAM, None)
    if oud and not nu:
        try:
            leeftijd = (datetime.now(timezone.utc) - datetime.fromisoformat(oud["tijd"])).total_seconds() / 3600
            if leeftijd < HOOGSTENS_ELKE_UUR:
                return
        except (KeyError, ValueError):
            pass
    uit = meet()
    lm._db_schrijf(NAAM, uit)
    print(f"warme leads bijgewerkt: {uit['samenvatting']}")


if __name__ == "__main__":
    main("--nu" in sys.argv)
