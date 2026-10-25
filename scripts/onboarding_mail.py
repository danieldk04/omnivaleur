"""Onboardingmail aan een nieuwe klant: zelf versturen, en meten wat er daarna gebeurt.

Daniel, 25-10-2026: de onboardingroutine zette mailtjes klaar die hij met de hand
verstuurde, waardoor niets te meten viel en hij het gevoel had dat niemand ze las.
Nu verstuurt de routine zelf, vanaf daniel@omnivaleur.nl via Zoho (zelfde route als
zijn eigen mail, SPF en DKIM zmail kloppen), en meet de volgende ochtend wie opende,
klikte, antwoordde of daarna iets deed.

Alles wat mis kan gaan wordt hier in code tegengehouden, niet alleen in de opdracht:
het adres komt uit het account zelf (nooit als argument), alleen accounts in hun
eerste week, nooit eigen domeinen, nooit tijdens een mailpauze, nooit als Daniel de
laatste 44 uur zelf mailde of de klant nog op antwoord wacht, hooguit drie per klant
en tien per dag, en de tekst moet in de juiste taal en in Daniels vorm zijn.

    PY scripts/onboarding_mail.py stuur <user_id> --taal nl --onderwerp "..." < tekst   (proef)
    PY scripts/onboarding_mail.py stuur <user_id> --taal nl --onderwerp "..." --echt < tekst
    PY scripts/onboarding_mail.py stuur --test-naar daniel@omnivaleur.nl --taal nl --onderwerp "..." --echt < tekst
    PY scripts/onboarding_mail.py rapport
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mail_analyse as A  # noqa: E402
import nieuwe_klanten as N  # noqa: E402

LOG_SLEUTEL = "onboarding_mails"
AFZENDER = ("Daniel de Koning", "daniel@omnivaleur.nl")
SMTP = ("smtp.zoho.eu", 465)
MEET_HOST = "https://omnivaleur.nl"      # verzenddomein, zie pixel-op-verzenddomein
TEST_ADRESSEN = {"daniel@omnivaleur.nl", "info@omnivaleur.com"}
RUST_UREN = 44                            # geen tweede mail binnen twee dagen
MAX_PER_KLANT = 3
MAX_PER_DAG = 10
WOORDEN = (40, 250)
NL = {"je", "de", "het", "een", "en", "van", "op", "dat", "met", "voor", "niet", "jouw",
      "ik", "naar", "ook", "zijn", "maar", "kun", "staat", "nog", "als", "wat"}
EN = {"you", "the", "and", "your", "to", "of", "on", "that", "with", "for", "not", "i",
      "it", "are", "but", "can", "have", "will", "just", "if", "what"}


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _log() -> list[dict]:
    rijen = A._lees(LOG_SLEUTEL, [])
    return rijen if isinstance(rijen, list) else []


def taal_van(tekst: str) -> str | None:
    woorden = re.findall(r"[a-zà-ÿ]+", tekst.lower())
    nl, en = sum(w in NL for w in woorden), sum(w in EN for w in woorden)
    if nl >= 2 * max(en, 1):
        return "nl"
    if en >= 2 * max(nl, 1):
        return "en"
    return None


def verwachte_taal(adres: str, p: dict | None) -> str | None:
    """Nederlands bij een .nl of .be adres of wie op Marktplaats of 2dehands verkoopt.
    Anders zegt alleen de routine het, met --taal."""
    if adres.lower().rsplit(".", 1)[-1] in ("nl", "be"):
        return "nl"
    bronnen = [k for k, _ in (p or {}).get("import", []) + (p or {}).get("advertenties", [])]
    if any(b.startswith(("marktplaats:", "2dehands:")) for b in bronnen):
        return "nl"
    return None


def tekstfouten(onderwerp: str, tekst: str, taal: str) -> list[str]:
    fouten = []
    if not onderwerp.strip() or len(onderwerp) > 80:
        fouten.append("onderwerp leeg of langer dan 80 tekens")
    if re.search(r"\s[-–—]\s|[–—]", onderwerp + "\n" + tekst):
        fouten.append("gedachtestreepje als leesteken")
    if re.search(r"[*#`<>{}\[\]]", onderwerp + tekst):
        fouten.append("opmaakteken of invulplek (*, #, <, {, [) in de tekst")
    eerste = tekst.strip().splitlines()[0] if tekst.strip() else ""
    if not re.match(r"^(Hoi|Hi|Hey)\b", eerste):
        fouten.append("aanhef begint niet met Hoi of Hi")
    if not tekst.strip().endswith("Daniel"):
        fouten.append("laatste regel is niet 'Daniel'")
    n = len(tekst.split())
    if not WOORDEN[0] <= n <= WOORDEN[1]:
        fouten.append(f"{n} woorden, hoort tussen {WOORDEN[0]} en {WOORDEN[1]}")
    if "dashboard" not in tekst.lower():
        fouten.append("het woord 'dashboard' ontbreekt (daar komt de meetbare link op)")
    gemeten = taal_van(tekst)
    if gemeten != taal:
        fouten.append(f"tekst leest als {gemeten or 'onduidelijk'}, gevraagd is {taal}")
    return fouten


def klantfouten(uid: str, account: dict | None, p: dict | None, post, taal: str,
                log: list[dict], nu: datetime) -> list[str]:
    """Mag deze klant nu een onboardingmail krijgen? Elke reden om niet te sturen."""
    from backend.services.email import _pauze_actief
    if not account:
        return ["onbekend account"]
    adres = (account.get("email") or "").strip().lower()
    fouten = []
    if "@" not in adres:
        fouten.append("account zonder e-mailadres")
    if adres.endswith(N.EIGEN_DOMEINEN) or adres in TEST_ADRESSEN:
        fouten.append("eigen adres, geen klant")
    if not account.get("aangemeld") or account["aangemeld"] < nu - timedelta(days=N.FASE_DAGEN):
        fouten.append(f"niet nieuw: aangemeld {account.get('aangemeld')}, langer dan {N.FASE_DAGEN} dagen")
    if _pauze_actief(adres):
        fouten.append(f"mailpauze tot {_pauze_actief(adres)}")
    eigen = [r for r in log if r.get("user_id") == uid]
    if len(eigen) >= MAX_PER_KLANT:
        fouten.append(f"al {len(eigen)} onboardingmails, maximum {MAX_PER_KLANT}")
    if any(N._tijd(r["op"]) > nu - timedelta(hours=RUST_UREN) for r in eigen):
        fouten.append(f"binnen {RUST_UREN} uur al een onboardingmail")
    vandaag = nu.astimezone(N.AMS).date()
    if sum(1 for r in log if N._tijd(r["op"]).astimezone(N.AMS).date() == vandaag
           and not r.get("test")) >= MAX_PER_DAG:
        fouten.append(f"dagmaximum van {MAX_PER_DAG} bereikt")
    if isinstance(post, str):
        fouten.append(f"postvak niet te controleren ({post})")
    else:
        weg = [m["datum"] for m in post if m["map"] == "Verzonden" and m["datum"]]
        binnen = [m["datum"] for m in post if m["map"] != "Verzonden" and m["datum"]]
        if any(d > nu - timedelta(hours=RUST_UREN) for d in weg):
            fouten.append(f"Daniel mailde dit adres de laatste {RUST_UREN} uur al")
        if binnen and (not weg or max(binnen) > max(weg)):
            fouten.append("klant mailde en wacht op antwoord van Daniel zelf")
    verwacht = verwachte_taal(adres, p)
    if verwacht and verwacht != taal:
        fouten.append(f"klant is {verwacht}-talig (adres of kanalen), gevraagd is {taal}")
    return fouten


def _code(adres: str, laag: str) -> str:
    return base64.urlsafe_b64encode(f"{adres.lower()}|{laag}".encode()).rstrip(b"=").decode()


def bericht(adres: str, onderwerp: str, tekst: str, laag: str) -> EmailMessage:
    """Platte tekst zoals Daniel hem typt, plus dezelfde tekst als HTML met een
    pixel en de link op het woord dashboard. Geen afmeldkop of opmaak: het moet een
    persoonlijke mail blijven en niet als nieuwsbrief tellen."""
    msg = EmailMessage()
    msg["From"] = f"{AFZENDER[0]} <{AFZENDER[1]}>"
    msg["To"] = adres
    msg["Subject"] = onderwerp.strip()
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="omnivaleur.nl")
    msg.set_content(tekst.strip() + "\n")
    code = _code(adres, laag)
    veilig = html.escape(tekst.strip()).replace("\n", "<br>")
    veilig = re.sub(r"(?i)\b(dashboard)\b", rf'<a href="{MEET_HOST}/t/k/{code}">\1</a>', veilig, count=1)
    msg.add_alternative(
        f'<html><body style="font-family:sans-serif">{veilig}'
        f'<img src="{MEET_HOST}/t/o/{code}" width="1" height="1" style="display:none" alt="">'
        f"</body></html>", subtype="html")
    return msg


def _verstuur(msg: EmailMessage) -> None:
    wachtwoord = N._mailwachtwoord()
    if not wachtwoord:
        raise RuntimeError("geen MAIL_PASS in .env of sleutelhanger")
    import os
    with smtplib.SMTP_SSL(*SMTP, context=ssl.create_default_context(), timeout=60) as smtp:
        smtp.login(os.environ.get("MAIL_USER") or AFZENDER[1], wachtwoord)
        smtp.send_message(msg)


def stuur(args) -> int:
    sys.path.insert(0, str(N.REPO))
    from backend.database import get_admin_db, get_db
    onderwerp, tekst = args.onderwerp, sys.stdin.read().strip()
    nu, log = _nu(), _log()
    fouten = tekstfouten(onderwerp, tekst, args.taal)
    if args.test_naar:
        adres, uid, p = args.test_naar.lower(), None, None
        if adres not in TEST_ADRESSEN:
            fouten.append(f"--test-naar mag alleen naar {sorted(TEST_ADRESSEN)}")
    else:
        alle = N.accounts(get_admin_db())
        uid, account = args.user_id, alle.get(args.user_id)
        adres = (account or {}).get("email", "").lower()
        p = N.profiel(get_db(), uid, account, nu) if account else None
        post = N.postvak([adres]) if adres else "geen adres"
        fouten += klantfouten(uid, account, p, post if isinstance(post, str) else post.get(adres, []),
                              args.taal, log, nu)
    print(f"Aan: {adres or '?'}  taal {args.taal}  onderwerp: {onderwerp}")
    if fouten:
        print("NIET VERSTUURD:\n  " + "\n  ".join(fouten))
        return 2
    laag = "onboarding-test" if args.test_naar else f"onboarding{1 + sum(r.get('user_id') == uid for r in log)}"
    msg = bericht(adres, onderwerp, tekst, laag)
    if not args.echt:
        print("Alle controles goed. Proef: niets verstuurd (gebruik --echt).")
        return 0
    if A._bereikbaar():
        print(f"NIET VERSTUURD: gedeelde opslag niet bereikbaar ({A._bereikbaar()}), dan meet niets.")
        return 2
    _verstuur(msg)
    rij = {"user_id": uid, "adres": adres, "onderwerp": onderwerp, "taal": args.taal, "laag": laag,
           "op": nu.isoformat(timespec="seconds"), "message_id": msg["Message-ID"],
           "tekst": tekst[:3000], "test": bool(args.test_naar)}
    if p:
        rij["voor"] = {"artikelen": p["voorraad"]["aantal"],
                       "actief": sum(n for k, n in p["advertenties"] if k.endswith(":active")),
                       "extensie": p["extensie"]["versie"]}
    vastgelegd = A._schrijf(LOG_SLEUTEL, log + [rij])
    if uid:
        N.mailtje(uid, tekst)
    print(f"VERSTUURD {msg['Message-ID']}" + ("" if vastgelegd else "  (LET OP: niet vastgelegd)"))
    return 0 if vastgelegd else 1


def _agent(item: dict) -> str:
    a = (item.get("agent") or "").lower()
    if "googleimageproxy" in a:
        return "Gmail"
    if "microsoft" in a or "outlook" in a:
        return "Outlook"
    return "Apple of onbekend" if a else "onbekend"


def rapport(args) -> int:
    sys.path.insert(0, str(N.REPO))
    from backend.database import get_admin_db, get_db
    nu = _nu()
    rijen = [r for r in _log() if not r.get("test") and N._tijd(r["op"]) > nu - timedelta(days=args.dagen)]
    if not rijen:
        print(f"Geen onboardingmails verstuurd in de laatste {args.dagen} dagen.")
        return 0
    opens, kliks = A._lees("mail_opens", {}) or {}, A._lees("mail_kliks", {}) or {}
    alle, db = N.accounts(get_admin_db()), get_db()
    post = N.postvak(sorted({r["adres"] for r in rijen}))
    tel = {"geopend": 0, "geklikt": 0, "antwoord": 0, "actie": 0}
    for r in rijen:
        op, adres = N._tijd(r["op"]), r["adres"]
        o = (opens.get(adres) or {}).get(r["laag"])
        k = (kliks.get(adres) or {}).get(r["laag"])
        mails = [] if isinstance(post, str) else post.get(adres, [])
        antw = [m for m in mails if m["map"] != "Verzonden" and m["datum"] and m["datum"] > op]
        in_verzonden = any(m["map"] == "Verzonden" and m["datum"] and abs((m["datum"] - op).total_seconds()) < 600
                           for m in mails)
        acties = []
        acc = alle.get(r["user_id"])
        if acc:
            p = N.profiel(db, r["user_id"], acc, nu)
            voor = r.get("voor") or {}
            if acc.get("laatste_login") and acc["laatste_login"] > op:
                acties.append("logde in")
            if p["extensie"]["laatst"] and p["extensie"]["laatst"] > op:
                acties.append("extensie actief" if voor.get("extensie") else "extensie geïnstalleerd")
            if p["voorraad"]["aantal"] > voor.get("artikelen", 0):
                acties.append(f"+{p['voorraad']['aantal'] - voor.get('artikelen', 0)} artikelen")
            actief = sum(n for kk, n in p["advertenties"] if kk.endswith(":active"))
            if actief > voor.get("actief", 0):
                acties.append(f"+{actief - voor.get('actief', 0)} live")
        snel = o and (N._tijd(o["eerst"]) - op).total_seconds() < 120 and _agent(o) != "Gmail"
        geopend = (f"geopend {N._lokaal(N._tijd(o['eerst']))} ({_agent(o)}"
                   + (", mogelijk automatisch" if snel else "") + ")") if o else "niet geopend gemeten"
        tel["geopend"] += bool(o and not snel)
        tel["geklikt"] += bool(k)
        tel["antwoord"] += bool(antw)
        tel["actie"] += bool(acties)
        print(f"{N._lokaal(op)} {adres}: {geopend}; {'klikte' if k else 'geen klik'}; "
              f"{'antwoordde' if antw else 'geen antwoord'}; "
              f"{', '.join(acties) or 'daarna niets gedaan'}"
              + ("" if in_verzonden or isinstance(post, str) else "; ! niet in Verzonden"))
    print(f"\nTotaal {len(rijen)} mails: {tel['geopend']} echt geopend, {tel['geklikt']} geklikt, "
          f"{tel['antwoord']} antwoord, {tel['actie']} deden daarna iets."
          + (f" Postvak: {post}" if isinstance(post, str) else ""))
    return 0


def main() -> None:
    A._omgeving_uit_env_bestand()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stuur")
    s.add_argument("user_id", nargs="?")
    s.add_argument("--taal", choices=("nl", "en"), required=True)
    s.add_argument("--onderwerp", required=True)
    s.add_argument("--echt", action="store_true")
    s.add_argument("--test-naar")
    r = sub.add_parser("rapport")
    r.add_argument("--dagen", type=int, default=8)
    args = ap.parse_args()
    if args.cmd == "stuur" and not (args.user_id or args.test_naar):
        ap.error("user_id of --test-naar is nodig")
    sys.exit(stuur(args) if args.cmd == "stuur" else rapport(args))


if __name__ == "__main__":
    main()
