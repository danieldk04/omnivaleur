"""
Opvolging voor doodgelopen leads, reeks C (Daniel, 19-11-2026).

Wie drie koude mails kreeg en nooit iets liet horen, wordt na minstens 35 dagen
nog een keer benaderd, als ANTWOORD in de draad van de eerste mail, zodat het niet
uit de lucht komt vallen. De eerste mail staat eronder geciteerd.

Wat er nooit gebeurt, en waarom dat hier zo streng staat:
  - Wie zich afmeldde, afgewezen heeft, een concurrent gebruikt, bounced of een
    automatisch antwoord gaf: nooit.
  - Wie OOIT iets terugstuurde (in welke map dan ook, ook op een ander adres van
    hetzelfde bedrijf): nooit. Een reactie is een gesprek, geen doodgelopen lead.
  - Wie Daniel zelf mailde na de laatste machinemail, wie klant is, wie op "Niet
    meer mailen" staat in het leadsheet, wie de video kreeg: nooit.
  - Elke mail draagt een afmeldregel ("stop" terugsturen) en de List-Unsubscribe-kop;
    dat antwoord gaat door dezelfde afmeldherkenning als de rest van de machine.
  - Noodrem: lopen de afmeldingen of bounces uit de pas, dan stopt het script zelf.

Twee varianten, 50/50 per adres, vast per adres (hash): "link" (de demo staat er als
link in, geteld via /t/k) en "vraag" ("zal ik het filmpje sturen?", geteld via
antwoorden). Zo is meetbaar wat beter werkt. `meting` toont de uitkomst.

De lijst met wie al verstuurd is staat NIET in de repo (die is publiek) maar in
Supabase, tabel leadgen_opslag, naam "doodgelopen_opvolging".

Gebruik:
    python scripts/doodgelopen_opvolging.py                # alleen kijken (1 voorbeeld)
    python scripts/doodgelopen_opvolging.py --aantal 5     # alleen kijken, 5 voorbeelden
    python scripts/doodgelopen_opvolging.py --echt         # versturen (1 per beurt, 25 per dag)
    python scripts/doodgelopen_opvolging.py meting         # uitkomst per variant
"""
from __future__ import annotations

import base64
import collections
import hashlib
import imaplib
import os
import re
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.leadgen_mail as lm  # noqa: E402

NAAM = "doodgelopen_opvolging"
LAAG = "doodgelopen"            # laagnaam in mail_opens en mail_kliks
# De klik gaat rechtstreeks naar het productdomein: omnivaleur.nl stuurt /t/ eerst nog
# door naar .com, een extra stap die een mailprogramma kritischer maakt.
KLIK_HOST = "https://omnivaleur.com"
WACHT_DAGEN = 35                # na de laatste machinemail
DAGMAX = 25
PER_BEURT = 1                   # de machine draait zo'n 26 keer per dag
VENSTER = ("08:30", "20:30")
EIGEN_MAIL_MARGE = 600          # seconden; onze eigen mail telt niet als "Daniel schreef zelf"
NOODREM_MIN_VERSTUURD = 20

# Elke vlag in de administratie die betekent: laat deze persoon met rust.
VLAGGEN_NOOIT = ("afgemeld", "afgewezen", "concurrent", "bounce", "auto_antwoord",
                 "beantwoord", "met_de_hand", "daniel_antwoordde", "laatste_inkomend",
                 "soort", "video_op", "video_gemeld", "video_opvolg", "video_opvolg_op",
                 "concept_klaar", "concept_opnieuw")

INKOMENDE_MAPPEN = ("INBOX", lm.MAP_BEANTWOORD, "Afval", "Spam", "Archive",
                    lm.MAP_AUTOMATISCH, "Klanten")
GRATIS_MAIL = {"gmail", "hotmail", "outlook", "live", "icloud", "yahoo", "ziggo", "kpnmail",
               "planet", "telenet", "skynet", "proximus", "msn", "me", "protonmail", "xs4all",
               "home", "online", "casema", "chello", "upcmail", "duck", "pm"}

AFMELDREGEL = 'Liever geen mail meer van me? Stuur gewoon "stop", dan hoor je niets meer.'

# Eén tekst per (variant, je/jullie). Geen streepjes als leesteken, geen opmaaktekens.
KERN_JE = ("Ik mailde je eerder over Omnivaleur, de mail staat hieronder. Tik je elke "
           "advertentie nog steeds per platform apart over? Sinds die mail gaat een verkocht artikel "
           "vanzelf overal offline, ook bij Shopify en WooCommerce, en ik kijk zelf mee bij "
           "elk nieuw account. De eerste 7 dagen zijn gratis.")
KERN_JULLIE = ("Ik mailde jullie eerder over Omnivaleur, de mail staat hieronder. Tikken jullie "
               "elke advertentie nog steeds per platform apart over? Sinds die mail gaat "
               "een verkocht artikel vanzelf overal offline, ook bij Shopify en WooCommerce, en "
               "ik kijk zelf mee bij elk nieuw account. De eerste 7 dagen zijn gratis.")
VRAAG_JE = "Zal ik je het filmpje van een minuut sturen? :)"
VRAAG_JULLIE = "Zal ik jullie het filmpje van een minuut sturen? :)"
LINK_JE = "Het filmpje van een minuut staat hier:"
LINK_JULLIE = "Het filmpje van een minuut staat hier:"


# ---------------------------------------------------------------- pure regels

def variant_van(adres: str) -> str:
    """Vast per adres, 50/50."""
    h = hashlib.sha256(("doodgelopen|" + adres.lower()).encode()).digest()[0]
    return "link" if h % 2 == 0 else "vraag"


def domeinstam(adres: str) -> str | None:
    """Het bedrijfsdeel van een adres, of None bij gratis mail (dan zegt het niets)."""
    dom = adres.lower().rpartition("@")[2]
    stam = dom.split(".")[0] if dom else ""
    if not stam or stam in GRATIS_MAIL:
        return None
    return stam


def waarom_niet(adres: str, st: dict, nu: datetime, *, antwoorden_adressen: set[str],
                antwoorden_stammen: set[str], eigen_na: dict[str, float],
                gestopt: set[str], al_verstuurd: set[str]) -> str | None:
    """Geeft de reden waarom dit adres GEEN mail krijgt, of None als het mag.
    Elke poort is bewust een uitsluiting; bij twijfel niet mailen."""
    adres = adres.lower()
    if adres in al_verstuurd:
        return "al verstuurd"
    if not lm._bruikbaar(adres):
        return "onbruikbaar adres"
    if not st.get("afgesloten"):
        return "niet doodgelopen"
    for v in VLAGGEN_NOOIT:
        if st.get(v):
            return f"vlag {v}"
    if len(st.get("verstuurd") or []) < 3:
        return "reeks nog niet af"
    try:
        laatste = datetime.fromisoformat(st["laatste"])
    except Exception:  # noqa: BLE001
        return "laatste mail onbekend"
    if (nu - laatste) < timedelta(days=WACHT_DAGEN):
        return "nog geen 35 dagen"
    if adres in gestopt:
        return "niet meer mailen (sheet)"
    if adres in antwoorden_adressen:
        return "heeft ooit teruggeschreven"
    stam = domeinstam(adres)
    if stam and stam in antwoorden_stammen:
        return "ander adres van dit bedrijf schreef terug"
    if eigen_na.get(adres, 0) > laatste.timestamp() + EIGEN_MAIL_MARGE:
        return "Daniel schreef zelf daarna"
    return None


def noodrem(rec: dict, state: dict) -> str | None:
    """Stopt de reeks zodra het mis lijkt te gaan."""
    adressen = list((rec.get("verstuurd") or {}).keys())
    n = len(adressen)
    if n < NOODREM_MIN_VERSTUURD:
        return None
    af = sum(1 for a in adressen if state.get(a, {}).get("afgemeld"))
    bo = sum(1 for a in adressen if state.get(a, {}).get("bounce"))
    if af >= 3 and af / n >= 0.08:
        return f"{af} afmeldingen op {n} verstuurd (8% of meer)"
    if bo >= 4 and bo / n >= 0.15:
        return f"{bo} bounces op {n} verstuurd (15% of meer)"
    return None


def _plat(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def klik_link(adres: str) -> str:
    code = base64.urlsafe_b64encode(f"{adres.lower()}|{LAAG}".encode()).rstrip(b"=").decode()
    return f"{KLIK_HOST}/t/k/{code}"


def maak_tekst(adres: str, variant: str, jullie: bool, eerste: dict, gebruiker: str) -> tuple[str, str]:
    """(platte tekst, html). De eerste mail staat geciteerd onder de afmeldregel."""
    kern = KERN_JULLIE if jullie else KERN_JE
    if variant == "link":
        link = klik_link(adres)
        regel_plat = f"{LINK_JULLIE if jullie else LINK_JE} {link}"
    else:
        link = ""
        regel_plat = VRAAG_JULLIE if jullie else VRAAG_JE
    kop = f"Op {eerste['datum']} schreef {lm.AFZENDER_NAAM} <{gebruiker}>:"
    citaat = "\n".join("> " + r if r.strip() else ">" for r in (eerste["tekst"] or "").strip().splitlines())
    bovenaan = f"Hi,\n\n{kern}\n\n{regel_plat}\n\nGroetjes,\n\nDaniel\n\n{AFMELDREGEL}"
    plat = f"{bovenaan}\n\n{kop}\n{citaat}\n"
    # HTML: dezelfde tekst, de link als gewone zin met een klikbaar woord, plus de
    # onzichtbare pixel. Regeleindes letterlijk, zodat het eruitziet als de platte versie.
    veilig = escape(plat)
    if link:
        zin = escape(regel_plat)
        veilig = veilig.replace(zin, f'{escape(LINK_JULLIE if jullie else LINK_JE)} '
                                     f'<a href="{link}">bekijk het filmpje</a>')
    code = base64.urlsafe_b64encode(f"{adres.lower()}|{LAAG}".encode()).rstrip(b"=").decode()
    html = (f'<html><body style="font-family:sans-serif;white-space:pre-wrap">'
            f'{veilig.replace(chr(10), "<br>")}'
            f'<img src="{lm.PIXEL_HOST}/t/o/{code}" width="1" height="1" '
            f'style="display:none" alt=""></body></html>')
    return plat, html


def maak_bericht(adres: str, variant: str, eerste: dict, gebruiker: str) -> EmailMessage:
    onderwerp = _plat(eerste["onderwerp"])
    if not onderwerp.lower().startswith("re:"):
        onderwerp = "Re: " + onderwerp
    jullie = "jullie" in _plat(eerste["onderwerp"]).lower()
    plat, html = maak_tekst(adres, variant, jullie, eerste, gebruiker)
    msg = EmailMessage()
    msg["From"] = f"{lm.AFZENDER_NAAM} <{gebruiker}>"
    msg["To"] = adres
    msg["Subject"] = onderwerp
    msg["List-Unsubscribe"] = f"<mailto:{gebruiker}?subject=stop>"
    msg["X-Omnivaleur-Reeks"] = "C"
    mid = _plat(eerste.get("message_id"))
    if mid:
        msg["In-Reply-To"] = mid
        msg["References"] = (_plat(eerste.get("references")) + " " + mid).strip()
    msg.set_content(plat)
    msg.add_alternative(html, subtype="html")
    return msg


# ------------------------------------------------------------------ postbus

def _koppen(imap, map_: str, zoek: str = "ALL") -> list:
    if imap.select(f'"{map_}"', readonly=True)[0] != "OK":
        return []
    _, d = imap.search(None, zoek)
    return list(lm._koppen_in_bulk(imap, (d[0] or b"").split()).values())


def inkomende_adressen(imap) -> tuple[set[str], set[str]]:
    """Iedereen die ooit iets terugstuurde, in alle mappen waar dat landt. Systeemmail
    (bounces, no-reply) telt niet: die zegt niets over een gesprek."""
    adressen: set[str] = set()
    for map_ in INKOMENDE_MAPPEN:
        for msg in _koppen(imap, map_):
            van = parseaddr(str(msg.get("From", "")))[1].lower()
            if van and not lm.SYSTEEM_AFZENDER.search(van) and not lm.BOUNCE_AFZENDERS.search(van):
                adressen.add(van)
    stammen = {s for s in (domeinstam(a) for a in adressen) if s}
    return adressen, stammen


def eigen_mail_na(imap, sinds: str = "01-Aug-2026") -> dict[str, float]:
    """Per adres het laatste tijdstip waarop Daniel (of de machine) schreef, sinds augustus."""
    laatste: dict[str, float] = {}
    for msg in _koppen(imap, "Verzonden", f"(SINCE {sinds})"):
        try:
            ts = parsedate_to_datetime(str(msg.get("Date", ""))).timestamp()
        except Exception:  # noqa: BLE001
            continue
        for _, a in getaddresses([str(msg.get("To", ""))]):
            a = a.lower()
            if a and ts > laatste.get(a, 0):
                laatste[a] = ts
    return laatste


def eerste_mail(imap, adres: str) -> dict | None:
    """De eerste koude mail aan dit adres (niet een Re: en niet 'Laatste bericht')."""
    try:
        imap.select('"Verzonden"', readonly=True)
        _, d = imap.search(None, f'(TO "{adres}")')
        nums = (d[0] or b"").split()
        kandidaten = []
        for n in nums[:12]:
            _, ruw = imap.fetch(n, "(RFC822)")
            if not ruw or not ruw[0]:
                continue
            import email as _email
            msg = _email.message_from_bytes(ruw[0][1])
            onderwerp = str(lm._leesbaar(msg.get("Subject")))
            if onderwerp.lower().startswith("re:") or onderwerp.lower().startswith("laatste bericht"):
                continue
            try:
                dt = parsedate_to_datetime(str(msg.get("Date", "")))
            except Exception:  # noqa: BLE001
                continue
            kandidaten.append((dt, msg, onderwerp))
        if not kandidaten:
            return None
        dt, msg, onderwerp = min(kandidaten, key=lambda k: k[0])
        return {"onderwerp": onderwerp, "message_id": lm._leesbaar(msg.get("Message-ID")),
                "references": lm._leesbaar(msg.get("References")),
                "datum": dt.strftime("%d-%m-%Y om %H:%M"), "tekst": lm._platte_tekst(msg)}
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------- draaien

def draai(echt: bool, aantal_voorbeeld: int = 1) -> int:
    nu = datetime.now()
    if nu.weekday() == 6 and echt:       # zondag: niet
        return 0
    if echt and not (VENSTER[0] <= nu.strftime("%H:%M") <= VENSTER[1]):
        return 0
    gebruiker, host = lm._need("MAIL_USER"), os.environ.get("MAIL_HOST", "")
    rec = lm._db_lees(NAAM, {}) or {}
    rec.setdefault("verstuurd", {})
    m = lm._sheets_module()
    try:
        gestopt = {a.lower() for a in lm.Leadboek().gestopt()}
    except (m.TekstenFout, m.SheetsFout) as e:
        print(f"  (doodgelopen-opvolging overgeslagen, spreadsheet niet bruikbaar: {e})")
        return 0
    state = lm._state()
    rem = noodrem(rec, state)
    if rem:
        print(f"  !! NOODREM: {rem}. Er gaat niets meer uit tot dit is nagekeken.")
        return 0
    vandaag = nu.strftime("%Y-%m-%d")
    al_vandaag = sum(1 for v in rec["verstuurd"].values() if str(v.get("op", "")).startswith(vandaag))
    if echt and al_vandaag >= DAGMAX:
        return 0
    gedaan = 0
    redenen: collections.Counter = collections.Counter()
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(gebruiker, os.environ["MAIL_PASS"])
        antw_a, antw_s = inkomende_adressen(imap)
        eigen = eigen_mail_na(imap)
        al = set(rec["verstuurd"])
        kandidaten = sorted((a for a in state if state[a].get("afgesloten")),
                            key=lambda a: state[a].get("laatste", ""))
        for adres in kandidaten:
            if gedaan >= (PER_BEURT if echt else aantal_voorbeeld):
                break
            reden = waarom_niet(adres, state[adres], nu, antwoorden_adressen=antw_a,
                                antwoorden_stammen=antw_s, eigen_na=eigen, gestopt=gestopt,
                                al_verstuurd=al)
            if not reden and lm.is_klant(adres):
                reden = "heeft een account"
            if reden:
                redenen[reden] += 1
                continue
            eerste = eerste_mail(imap, adres)
            if not eerste or not eerste["message_id"]:
                redenen["eerste mail niet teruggevonden"] += 1
                continue
            variant = variant_van(adres)
            msg = maak_bericht(adres, variant, eerste, gebruiker)
            if not echt:
                print(f"\n  ZOU VERSTUREN [{variant}] aan {adres}\n  Onderwerp: {msg['Subject']}\n"
                      f"  In-Reply-To: {msg['In-Reply-To']}\n\n{msg.get_body(('plain',)).get_content()}")
                gedaan += 1
                continue
            with lm._postbode(gebruiker, host) as stuur:
                stuur(msg)
            rec["verstuurd"][adres] = {"op": datetime.now().isoformat(timespec="seconds"),
                                       "variant": variant}
            if not lm._db_schrijf(NAAM, rec):
                print(f"!! administratie niet bijgewerkt na {adres}; de beurt stopt hier")
                return gedaan + 1
            al.add(adres)
            gedaan += 1
            print(f"  → doodgelopen-opvolging [{variant}] aan {adres}", flush=True)
    top = ", ".join(f"{k}: {v}" for k, v in redenen.most_common(6))
    if top:
        print(f"  (overgeslagen tot hier: {top})")
    return gedaan


def kandidaten_tellen() -> dict:
    """Hoeveel doodgelopen leads mogen nu, en waarom de rest niet. Alleen lezen."""
    nu = datetime.now()
    gebruiker = lm._need("MAIL_USER")
    rec = lm._db_lees(NAAM, {}) or {}
    m = lm._sheets_module()
    gestopt = {a.lower() for a in lm.Leadboek().gestopt()}
    state = lm._state()
    redenen: collections.Counter = collections.Counter()
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(gebruiker, os.environ["MAIL_PASS"])
        antw_a, antw_s = inkomende_adressen(imap)
        eigen = eigen_mail_na(imap)
    al = set(rec.get("verstuurd") or {})
    mag = []
    for adres, st in state.items():
        r = waarom_niet(adres, st, nu, antwoorden_adressen=antw_a, antwoorden_stammen=antw_s,
                        eigen_na=eigen, gestopt=gestopt, al_verstuurd=al)
        if not r and lm.is_klant(adres):
            r = "heeft een account"
        if r:
            redenen[r] += 1
        else:
            mag.append(adres)
    # Alleen wie ook in de draad van de eerste mail kan antwoorden: koude mails van
    # 06-09 tot 26-09 gingen via Resend en staan niet in Zoho, die kunnen niet.
    met_draad = 0
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(gebruiker, os.environ["MAIL_PASS"])
        for a in mag:
            e = eerste_mail(imap, a)
            if e and e["message_id"]:
                met_draad += 1
    return {"mag_nu": len(mag), "met_draad": met_draad, "redenen": dict(redenen.most_common())}


def meting() -> None:
    rec = lm._db_lees(NAAM, {}) or {}
    verstuurd = rec.get("verstuurd") or {}
    state = lm._state()
    opens = lm._db_lees("mail_opens", {}) or {}
    kliks = lm._db_lees("mail_kliks", {}) or {}
    cijfers: dict = collections.defaultdict(lambda: collections.Counter())
    for adres, v in verstuurd.items():
        c = cijfers[v.get("variant", "?")]
        st = state.get(adres, {})
        c["verstuurd"] += 1
        if opens.get(adres, {}).get(LAAG):
            c["geopend"] += 1
        if kliks.get(adres, {}).get(LAAG):
            c["geklikt"] += 1
        if st.get("afgemeld"):
            c["afgemeld"] += 1
        if st.get("bounce"):
            c["bounce"] += 1
        if st.get("afgewezen") or st.get("concurrent"):
            c["nee"] += 1
        if st.get("beantwoord") and not (st.get("afgemeld") or st.get("afgewezen") or st.get("concurrent")):
            c["gereageerd"] += 1
    print(f"Doodgelopen-opvolging: {len(verstuurd)} verstuurd")
    for variant in sorted(cijfers):
        c = cijfers[variant]
        n = c["verstuurd"]
        pct = lambda k: f"{100 * c[k] / n:.1f}%" if n else "-"  # noqa: E731
        print(f"  {variant:6} n={n:3} geopend {c['geopend']} ({pct('geopend')}), "
              f"geklikt {c['geklikt']} ({pct('geklikt')}), gereageerd {c['gereageerd']} ({pct('gereageerd')}), "
              f"nee {c['nee']}, afgemeld {c['afgemeld']}, bounce {c['bounce']}")
    print("  Let op: opens tellen Apple Mail mee (te hoog); klikken en reacties zijn betrouwbaar.")
    rem = noodrem(rec, state)
    if rem:
        print(f"  NOODREM ACTIEF: {rem}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "meting" in args:
        meting()
    elif "tellen" in args:
        print(kandidaten_tellen())
    else:
        aantal = int(args[args.index("--aantal") + 1]) if "--aantal" in args else 1
        n = draai("--echt" in args, aantal)
        print(f"{n} doodgelopen-opvolgmail(s) {'verstuurd' if '--echt' in args else 'zouden nu uitgaan'}.")
