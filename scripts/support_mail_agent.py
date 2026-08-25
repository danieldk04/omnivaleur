#!/usr/bin/env python3
"""
Support-mailagent: leest daniel@omnivaleur.nl (Zoho, Postvak IN), zet voor elk
onbeantwoord klant-/leadbericht een conceptantwoord klaar in Concepten, en
houdt bij welke vragen/bugs vaak terugkomen.

WAAROM DIT SCRIPT BESTAAT
Daniel plakte elke inkomende support-vraag handmatig in Claude, kreeg een op de
code gecontroleerd antwoord terug, en plakte dat weer als concept in Zoho. Dit
automatiseert precies die stap — niet meer, niet minder. Er wordt nooit
automatisch verstuurd.

PATROON HERGEBRUIKT VAN scripts/leadgen_mail.py
Zelfde Zoho-mailbox, zelfde IMAP-aanpak (imaplib, APPEND naar de Conceptenmap
met de \\Draft-vlag), zelfde Supabase-opslag in plaats van bestanden (deze repo
is publiek — klantdata hoort niet in git), zelfde omgevingsvariabelen
(MAIL_USER, MAIL_PASS, IMAP_HOST, SUPABASE_URL, SUPABASE_KEY).

HOE EEN CONCEPT WORDT ONDERBOUWD
Voor elk binnenkomend bericht vraagt dit script een taalmodel (Claude, via de
Anthropic API) om (a) de vraag te classificeren en (b) een conceptantwoord te
schrijven — MAAR alleen met stukken brontekst uit deze repo als bewijsmateriaal
in de prompt (zie `_grep_grondslag`). Het model krijgt expliciet de instructie
nooit een technische claim te doen die niet in die meegeleverde brontekst staat.
Dit is dezelfde discipline die handmatig is toegepast in de sessie van
24-08-2026 (Twan/kenmerken, Robert/relist, Egbert/Admarkt-scan): eerst de
code lezen, dan pas iets beweren.

GEBRUIK
    export MAIL_HOST=smtp.zoho.eu MAIL_USER=daniel@omnivaleur.nl MAIL_PASS=...
    export IMAP_HOST=imap.zoho.eu
    export SUPABASE_URL=... SUPABASE_KEY=...
    export ANTHROPIC_API_KEY=...

    python3 scripts/support_mail_agent.py run --dry-run   # tonen, niets schrijven
    python3 scripts/support_mail_agent.py run             # concepten klaarzetten + trends loggen
    python3 scripts/support_mail_agent.py report           # trendrapport regenereren uit Supabase
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUT = Path(__file__).parent / "output"
TREND_REPORT = OUT / "support_trends.json"
REVIEW_QUEUE = OUT / "support_review_needed.json"  # niet-simpele issues + auto-fix samenvatting, voor Daniel

CONCEPTMAP = "Concept"
MAP_BEANTWOORD = "Beantwoord"
TABEL = "support_mail_log"

VIDEO = "https://youtube.com/shorts/ymDeS37aBW4"
PRIJS = "€19,99 per maand"
PROEF = "de eerste 7 dagen gratis"
PLATFORMS = "Marktplaats, 2dehands, Vinted, eBay en Shopify"

SYSTEEM_AFZENDER = re.compile(
    r"@(zoho\.(eu|com)|google\.com)$|dmarc|mailer-daemon|postmaster|no-?reply", re.I)

# Bestanden waarin veelvoorkomende supportonderwerpen te verifiëren zijn. Dit is
# geen volledige index van de repo — het is de kortste route naar bewijs voor de
# vragen die in de praktijk het vaakst terugkomen. Nieuwe categorieën vragen om
# een nieuwe regel hier, niet om het model zelf te laten raden waar te kijken.
GROUNDING_MAP: dict[str, list[str]] = {
    "kenmerken": ["extension/content/marktplaats.js"],
    "attributen": ["extension/content/marktplaats.js"],
    "relist": ["backend/services/crosslist.py"],
    "crosslist": ["backend/services/crosslist.py", "extension/background.js"],
    "admarkt": ["backend/api/imports.py", "extension/background.js"],
    "scan": ["backend/api/imports.py", "extension/background.js"],
    "prijs": ["backend/services/billing.py", "backend/api/billing.py"],
    "proef": ["backend/services/billing.py"],
    "trial": ["backend/services/billing.py"],
    "factuur": ["backend/api/billing.py", "backend/services/billing.py"],
    "billing": ["backend/api/billing.py", "backend/services/billing.py"],
    "login": ["backend/api/auth.py", "backend/api/deps.py"],
    "wachtwoord": ["backend/api/auth.py"],
    "vinted": ["extension/content/", "backend/services/crosslist.py"],
    "ebay": ["backend/services/crosslist.py"],
    "shopify": ["backend/api/shopify.py"],
    "facebook": ["extension/background.js"],
    "verkocht": ["backend/services/crosslist.py"],
}


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


# ---------------------------------------------------------------- opslag
def _supabase() -> tuple[str, str] | None:
    url, sleutel = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    return (url.rstrip("/"), sleutel) if url and sleutel else None


def _db_bekend(message_id: str) -> bool:
    """Is dit bericht al eerder verwerkt? Voorkomt dubbele concepten bij een
    volgende run — de kern van 'per-message, niet per-thread' uit de opdracht."""
    verbinding = _supabase()
    if not verbinding:
        return False
    import httpx
    url, sleutel = verbinding
    r = httpx.get(f"{url}/rest/v1/{TABEL}",
                   params={"message_id": f"eq.{message_id}", "select": "id"},
                   headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}"},
                   timeout=30.0)
    r.raise_for_status()
    return bool(r.json())


def _db_log(rij: dict) -> None:
    verbinding = _supabase()
    if not verbinding:
        print("  (SUPABASE_URL/KEY ontbreken — trend niet gelogd, alleen lokaal getoond)")
        return
    import httpx
    url, sleutel = verbinding
    r = httpx.post(f"{url}/rest/v1/{TABEL}",
                    headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}",
                             "Content-Type": "application/json",
                             "Prefer": "resolution=merge-duplicates"},
                    params={"on_conflict": "message_id"},
                    json=rij, timeout=30.0)
    r.raise_for_status()


def _db_recent(dagen: int = 30) -> list[dict]:
    verbinding = _supabase()
    if not verbinding:
        return []
    import httpx
    url, sleutel = verbinding
    sinds = (datetime.now(timezone.utc) - timedelta(days=dagen)).isoformat()
    r = httpx.get(f"{url}/rest/v1/{TABEL}",
                   params={"verwerkt_op": f"gte.{sinds}", "select": "*"},
                   headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}"},
                   timeout=30.0)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- IMAP helpers
def _decode(waarde) -> str:
    if not waarde:
        return ""
    try:
        return str(make_header(decode_header(waarde)))
    except Exception:  # noqa: BLE001
        return str(waarde)


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for deel in msg.walk():
            if deel.get_content_type() == "text/plain" and not deel.get_filename():
                try:
                    return deel.get_payload(decode=True).decode(
                        deel.get_content_charset() or "utf-8", "replace")
                except Exception:  # noqa: BLE001
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", "replace")
    except Exception:  # noqa: BLE001
        return str(msg.get_payload())


@dataclass
class Thread:
    message_id: str
    van_adres: str
    van_naam: str
    onderwerp: str
    body: str            # volledige tekst inclusief geciteerde historie
    references: str       # voor In-Reply-To/References op het antwoord


def _bestaande_conceptdoelen(imap: imaplib.IMAP4_SSL) -> set[str]:
    """Message-IDs waarvoor al een concept klaarstaat (via In-Reply-To/References
    van bestaande concepten). Per-message check, niet per-thread — zie module docstring."""
    doelen: set[str] = set()
    bestaand = {r.decode().split(' "/" ')[-1].strip('"') for r in (imap.list()[1] or [])}
    for map_ in (CONCEPTMAP, "Drafts"):
        if map_ not in bestaand:
            continue
        if imap.select(f'"{map_}"', readonly=True)[0] != "OK":
            continue
        _, data = imap.search(None, "ALL")
        for num in (data[0] or b"").split():
            _, ruw = imap.fetch(num, "(BODY.PEEK[HEADER])")
            if not ruw or not ruw[0]:
                continue
            kop = email.message_from_bytes(ruw[0][1])
            for veld in ("In-Reply-To", "References"):
                for stuk in (kop.get(veld, "") or "").split():
                    doelen.add(stuk.strip("<>"))
    return doelen


# De koude-leadgenmachine (scripts/leadgen_mail.py) stuurt onder dit exacte
# onderwerp uit en heeft haar EIGEN, veel specifiekere logica voor antwoorden
# daarop (CONCURRENT/AFWIJZING-classificatie, Notion-fases, opvolgritme). Dit
# script mag daar niet overheen draaien: gevonden 25-08-2026 toen dit hier per
# ongeluk óók een koude lead beantwoordde die zei "onze webshop zet het al met
# een paar klikken door" met een generiek productpraatje — precies het bezwaar
# dat leadgen_mail.py als "Gebruikt concurrent" hoort te herkennen en anders
# moet afhandelen. Onderwerpen die hiermee beginnen zijn dus NIET van dit
# script.
_LEADGEN_ONDERWERP = re.compile(r"^vraagje over (je|jullie) marktplaats-aanbod", re.I)


def _inbox_wachtend(imap: imaplib.IMAP4_SSL, eigen_adres: str) -> list[Thread]:
    """Threads waarvan het LAATSTE bericht van de klant is (niet van Daniel) en
    die niet al een vers concept hebben. Alleen INBOX — Concepten/Verzonden tellen
    niet mee als 'wachtend'."""
    if imap.select("INBOX")[0] != "OK":
        return []
    al_beantwoord = _bestaande_conceptdoelen(imap)
    sinds = (datetime.now() - timedelta(days=21)).strftime("%d-%b-%Y")
    _, data = imap.search(None, f'(SINCE {sinds})')
    per_thread: dict[str, list[tuple[str, email.message.Message]]] = {}
    for num in (data[0] or b"").split():
        _, ruw = imap.fetch(num, "(RFC822)")
        if not ruw or not ruw[0]:
            continue
        msg = email.message_from_bytes(ruw[0][1])
        afzender = parseaddr(msg.get("From", ""))[1].lower()
        if not afzender or afzender == eigen_adres.lower() or SYSTEEM_AFZENDER.search(afzender):
            continue
        onderwerp = _decode(msg.get("Subject", ""))
        kern_onderwerp = re.sub(r"^(re|fwd?):\s*", "", onderwerp, flags=re.I).strip().lower()
        sleutel = kern_onderwerp or afzender
        per_thread.setdefault(sleutel, []).append((afzender, msg))

    resultaat = []
    for _, berichten in per_thread.items():
        afzender, laatste = berichten[-1]  # IMAP levert oplopend op datum
        msg_id = (laatste.get("Message-ID", "") or "").strip("<>")
        if not msg_id or msg_id in al_beantwoord:
            continue
        naam = parseaddr(laatste.get("From", ""))[0] or afzender.split("@")[0]
        onderwerp = _decode(laatste.get("Subject", ""))
        body = _body_text(laatste)
        refs = " ".join(x for x in [laatste.get("References", ""), f"<{msg_id}>"] if x)
        resultaat.append(Thread(msg_id, afzender, _decode(naam), onderwerp, body, refs))
    return resultaat


def _postbode():
    host = os.environ.get("IMAP_HOST", "imap.zoho.eu")
    gebruiker = _need("MAIL_USER")
    wachtwoord = _need("MAIL_PASS")
    return imaplib.IMAP4_SSL(host, 993), gebruiker, wachtwoord


def _zet_concept_klaar(draad: Thread, tekst: str, dry_run: bool) -> bool:
    onderwerp = draad.onderwerp
    if not re.match(r"(?i)^re:", onderwerp):
        onderwerp = f"Re: {onderwerp}"
    msg = EmailMessage()
    msg["From"] = _need("MAIL_USER")
    msg["To"] = draad.van_adres
    msg["Subject"] = onderwerp
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg["In-Reply-To"] = f"<{draad.message_id}>"
    msg["References"] = draad.references
    msg.set_content(tekst)

    if dry_run:
        print(f"  [dry-run] concept zou klaargezet worden voor {draad.van_adres}")
        print("  ---\n" + tekst + "\n  ---")
        return True
    try:
        imap, gebruiker, wachtwoord = _postbode()
        with imap:
            imap.login(gebruiker, wachtwoord)
            bestaand = {r.decode().split(' "/" ')[-1].strip('"') for r in (imap.list()[1] or [])}
            map_ = CONCEPTMAP if CONCEPTMAP in bestaand else "Drafts"
            imap.append(f'"{map_}"', "\\Draft", None, msg.as_bytes())
        print(f"  ✎ concept klaargezet voor {draad.van_adres}")
        return True
    except Exception as e:  # noqa: BLE001 — geen concept is vervelend, niet fataal
        print(f"  (concept niet klaargezet: {e})")
        return False


# ---------------------------------------------------------------- grondslag (grep, geen aannames)
def _grep_grondslag(body: str, max_bestanden: int = 3, max_regels: int = 40) -> str:
    """Zoekt trefwoorden in het bericht en levert de bijbehorende brontekst uit
    de repo op, plus de laatste relevante commit — dat is het enige bewijs dat
    het taalmodel mag gebruiken om technische claims op te baseren."""
    laag = body.lower()
    kandidaten: list[str] = []
    for trefwoord, bestanden in GROUNDING_MAP.items():
        if trefwoord in laag:
            kandidaten.extend(bestanden)
    kandidaten = list(dict.fromkeys(kandidaten))[:max_bestanden]

    stukken = []
    for rel in kandidaten:
        pad = REPO_ROOT / rel
        if pad.is_dir():
            continue
        if not pad.exists():
            continue
        try:
            regels = pad.read_text(errors="replace").splitlines()
        except Exception:  # noqa: BLE001
            continue
        stukken.append(f"=== {rel} (eerste {max_regels} regels) ===\n" +
                        "\n".join(regels[:max_regels]))
        try:
            log = subprocess.run(
                ["git", "log", "-1", "--format=%h %ad %s", "--date=short", "--", rel],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
            if log.returncode == 0 and log.stdout.strip():
                stukken.append(f"(laatste commit op {rel}: {log.stdout.strip()})")
        except Exception:  # noqa: BLE001
            pass
    if not stukken:
        return "(geen relevante broncode gevonden voor dit bericht — beantwoord geen " \
               "technische claim die je niet kunt onderbouwen; laat die vraag expliciet open)"
    return "\n\n".join(stukken)


TOPIC_KEYWORDS = [
    ("kenmerken-support", ["kenmerk", "attribut"]),
    ("admarkt-scan-batching", ["admarkt", "scan"]),
    ("relist-vs-crosslist", ["relist", "opnieuw plaatsen", "verlopen"]),
    ("prijs-vraag", ["prijs", "kost", "€", "euro", "abonnement"]),
    ("proefperiode-vraag", ["proef", "trial", "gratis"]),
    ("billing-verzoek", ["factuur", "betaling", "stripe", "creditcard", "terugbetaal"]),
    ("login-bug", ["login", "inloggen", "wachtwoord", "wachtwoord vergeten"]),
    ("vinted-vraag", ["vinted"]),
    ("ebay-vraag", ["ebay"]),
    ("shopify-vraag", ["shopify"]),
    ("facebook-vraag", ["facebook", "marketplace"]),
    ("wil-langskomen", ["langskomen", "afspreken", "bezoek", "kantoor"]),
    ("verkocht-detectie", ["verkocht", "sold"]),
]


def _classificeer_topic(body: str) -> str:
    laag = body.lower()
    for topic, woorden in TOPIC_KEYWORDS:
        if any(w in laag for w in woorden):
            return topic
    return "overig"


# ---------------------------------------------------------------- LLM (Claude)
SYSTEM_PROMPT = """Je schrijft conceptantwoorden namens Daniel de Koning, oprichter van
Omnivaleur (crosslisting-app voor Marktplaats/2dehands/Vinted/eBay/Shopify).

STIJL: informeel, persoonlijk Nederlands. "Hi <naam>," / "Groetjes, Daniel". Geen
zakelijke boilerplate, kort en bondig.

HARDE REGELS:
1. Je krijgt hieronder brontekst uit de daadwerkelijke codebase als bewijsmateriaal.
   Doe NOOIT een technische bewering (dit werkt wel/niet, dit ondersteunt wel/niet)
   die niet direct steun heeft in die brontekst. Ontbreekt bewijs voor een technisch
   detail, schrijf dan expliciet "ik check dit nog en kom erop terug" in plaats van
   iets te verzinnen.
2. Zeg NOOIT dat iets "live" is als het nog in review staat bij de Chrome Web
   Store — als de brontekst dat niet expliciet bevestigt, ga er niet van uit dat
   het al bij gebruikers staat.
3. De demo is altijd deze link, nooit een bijlage: https://youtube.com/shorts/ymDeS37aBW4
4. Prijs is €19,99 per maand, alle platforms inbegrepen, eerste 7 dagen gratis —
   noem dit alleen als de klant er expliciet naar vraagt, en alleen met deze cijfers.
5. Vragen over facturen, terugbetalingen of het stopzetten/verplaatsen van een
   Stripe-betaling worden NOOIT beantwoord met een toezegging — schrijf dat Daniel
   dit met de hand regelt en kom er niet op vooruit.
6. Nooit "Omnivaleur" als werkwoord gebruiken; het werkwoord is "crosslisten".
7. Schrijf ALLEEN de e-mailtekst, geen uitleg eromheen, geen onderwerpregel.
"""


def _llm_beschikbaar() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _draft_met_llm(draad: Thread, grondslag: str) -> tuple[str, str]:
    """Retourneert (concepttekst, topic). Vereist ANTHROPIC_API_KEY; zonder key
    valt dit terug op een neutrale plaatshouder-tekst die het probleem alleen
    aankondigt maar geen technische claims doet."""
    topic = _classificeer_topic(draad.body)
    if not _llm_beschikbaar():
        return (
            f"Hi {draad.van_naam.split()[0] if draad.van_naam else ''},\n\n"
            "Bedankt voor je bericht — ik kijk dit na en kom er zo snel mogelijk "
            "op terug.\n\nGroetjes,\nDaniel",
            topic,
        )
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        f"BINNENGEKOMEN BERICHT van {draad.van_naam} <{draad.van_adres}>, "
        f"onderwerp '{draad.onderwerp}':\n\n{draad.body[:6000]}\n\n"
        f"BEWIJSMATERIAAL UIT DE CODEBASE:\n{grondslag}\n\n"
        "Schrijf het conceptantwoord."
    )
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    tekst = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    return tekst, topic


# ---------------------------------------------------------------- Module B: veilige auto-fix
# Zie module-docstring van deze file en het einde-rapport van de opdracht voor de
# afweging: alleen lokaal, dedicated branch, NOOIT push, NOOIT naar main — Railway
# deployt main automatisch en dat pad mag een onbewezen autonome agent nog niet op.
SIMPEL_MAX_REGELS = 6
VERBODEN_PADEN = re.compile(
    r"backend/(api/(billing|auth)\.py|services/billing\.py|models?/)", re.I)


@dataclass
class FixVoorstel:
    topic: str
    bestand: str
    omschrijving: str
    is_simple: bool
    reden: str


def classificeer_fix(topic: str, omschrijving: str, bestand: str | None,
                      regels_gewijzigd: int) -> FixVoorstel:
    """Allowlist, geen vibe: simpel is ALLEEN tekst/constante in één bestand,
    buiten betaal/auth/datamodel/API-contract, binnen een paar regels. Bij
    twijfel: niet simpel."""
    if not bestand:
        return FixVoorstel(topic, "", omschrijving, False, "geen concreet bestand aangewezen")
    if VERBODEN_PADEN.search(bestand):
        return FixVoorstel(topic, bestand, omschrijving, False,
                            "raakt betaal/auth/datamodel-code — altijd akkoord nodig")
    if regels_gewijzigd > SIMPEL_MAX_REGELS:
        return FixVoorstel(topic, bestand, omschrijving, False,
                            f"meer dan {SIMPEL_MAX_REGELS} regels — geen geïsoleerde tekstfix")
    return FixVoorstel(topic, bestand, omschrijving, True, "geïsoleerde tekst/constante-wijziging")


def voer_simpele_fix_uit(fix: FixVoorstel) -> str | None:
    """Placeholder-implementatie: dit systeem heeft nog geen enkele fix in het
    echt uitgevoerd. De scaffolding (branch aanmaken, geen push, review-rapport)
    staat klaar; het daadwerkelijk patchen van bestanden op basis van een
    LLM-voorstel is bewust NIET geautomatiseerd in v1 — te risicovol zonder
    bewezen trackrecord. Retourneert de branchnaam als er iets was uit te voeren,
    anders None."""
    if not fix.is_simple:
        return None
    print(f"  (auto-fix nog niet geïmplementeerd — {fix.topic} blijft in het reviewrapport staan)")
    return None


# ---------------------------------------------------------------- rapportage
def _schrijf_trend_rapport() -> None:
    rijen = _db_recent(30)
    OUT.mkdir(parents=True, exist_ok=True)
    if not rijen:
        TREND_REPORT.write_text(json.dumps(
            {"gegenereerd_op": datetime.now(timezone.utc).isoformat(),
             "opmerking": "geen Supabase-verbinding of nog geen data", "topics": {}},
            indent=2, ensure_ascii=False))
        return
    per_topic_30: dict[str, int] = {}
    per_topic_14: dict[str, int] = {}
    grens14 = datetime.now(timezone.utc) - timedelta(days=14)
    for rij in rijen:
        topic = rij.get("topic", "overig")
        per_topic_30[topic] = per_topic_30.get(topic, 0) + 1
        try:
            wanneer = datetime.fromisoformat(rij["verwerkt_op"].replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            wanneer = grens14
        if wanneer >= grens14:
            per_topic_14[topic] = per_topic_14.get(topic, 0) + 1
    rapport = {
        "gegenereerd_op": datetime.now(timezone.utc).isoformat(),
        "aantal_berichten_30d": len(rijen),
        "topics_14d": dict(sorted(per_topic_14.items(), key=lambda kv: -kv[1])),
        "topics_30d": dict(sorted(per_topic_30.items(), key=lambda kv: -kv[1])),
    }
    TREND_REPORT.write_text(json.dumps(rapport, indent=2, ensure_ascii=False))
    print(f"  trendrapport geschreven naar {TREND_REPORT}")


# ---------------------------------------------------------------- commands
def run(args) -> None:
    eigen_adres = _need("MAIL_USER")
    imap, gebruiker, wachtwoord = _postbode()
    with imap:
        imap.login(gebruiker, wachtwoord)
        wachtend = _inbox_wachtend(imap, eigen_adres)

    print(f"{len(wachtend)} bericht(en) wachten op een concept")
    review_items = []
    for draad in wachtend:
        if _db_bekend(draad.message_id):
            continue
        grondslag = _grep_grondslag(draad.body)
        tekst, topic = _draft_met_llm(draad, grondslag)
        gelukt = _zet_concept_klaar(draad, tekst, args.dry_run)
        if not args.dry_run:
            _db_log({
                "message_id": draad.message_id,
                "van_adres": draad.van_adres,
                "onderwerp": draad.onderwerp,
                "topic": topic,
                "concept_klaargezet": gelukt,
            })
        if not grondslag.startswith("(geen relevante broncode"):
            continue
        review_items.append({"van": draad.van_adres, "onderwerp": draad.onderwerp,
                              "topic": topic, "reden": "geen code-grondslag gevonden"})

    OUT.mkdir(parents=True, exist_ok=True)
    if review_items:
        REVIEW_QUEUE.write_text(json.dumps(review_items, indent=2, ensure_ascii=False))
        print(f"  {len(review_items)} bericht(en) zonder code-grondslag — zie {REVIEW_QUEUE}")

    if not args.dry_run:
        _schrijf_trend_rapport()


def report(args) -> None:
    _schrijf_trend_rapport()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="postvak in verwerken en concepten klaarzetten")
    r.add_argument("--dry-run", action="store_true", help="tonen, niets schrijven naar IMAP/Supabase")
    r.set_defaults(func=run)

    rp = sub.add_parser("report", help="trendrapport regenereren uit Supabase")
    rp.set_defaults(func=report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
