"""
Eenmalige terughaalcampagne: oud-klanten die zijn afgehaakt of nooit begonnen,
opnieuw uitnodigen nu de grootste storingen weg zijn.

Bewust een apart bestand met de teksten erin, net als bij announcement.py: de mail
gaat naar echte mensen in Daniels naam, dus hij moet leesbaar in de code staan en
niet in elkaar gezet worden uit losse regels.

Drie groepen (besluit 2, docs/team-notes.md 06-09-2026):
  A  probeerde het serieus, liep vast, vertrok      -> persoonlijk, eigen cijfer, excuus
  B  op dag een ging alles mis, nooit teruggekomen  -> "55 procent naar 7 procent"-verhaal
  C  meldde zich aan, deed nul opdrachten           -> lichte vraag, geen excuus

De campagne richt zich eerst op sieraden + antiek zilver (bewijscategorie); dat is
een keuze over WIE op de lijst komt, niet iets wat deze code afdwingt. De lijst
wordt met de hand aangeleverd.

Proefverlenging kan niet vanuit deze code: de server draait op de publieke
Supabase-sleutel en mag geen klantrijen schrijven. Elke mail belooft een verlengde
proef, dus Daniel zet die met de hand in het Supabase-dashboard (of per persoon via
/admin/comp-account) voordat hij op echt verstuurt. De proefronde herinnert daaraan.
"""
import logging

logger = logging.getLogger(__name__)

# Geen kortingspercentage, euroteken of uitroepteken in de onderwerpregel: daar
# sorteert Gmail op, en dan belandt de mail in Promoties in plaats van de inbox.
SUBJECT_A = "Het lag aan ons, van Daniel"
SUBJECT_B = "Omnivaleur werkt nu wel, van Daniel"
SUBJECT_C = "Zal ik even met je meekijken? Van Daniel"

# In groep A komt de zin over wat er bij die persoon misging op {detail}. Lever je
# geen eigen zin aan, dan valt hij terug op deze neutrale formulering.
DETAIL_FALLBACK = (
    "een deel van je publicaties liep vast op een valse melding \"je bent niet "
    "ingelogd bij Marktplaats\", en er is weinig tot niets geplaatst"
)

BODY_A = """Hi,

Daniel hier, van Omnivaleur.

Toen jij het probeerde, werkte het niet. Bij jou specifiek: {detail}. Dat was geen instelling aan jouw kant, dat lag aan ons.

Die valse inlogmelding is opgespoord en gerepareerd. Het mislukkingspercentage over alle klanten is deze week 7 procent, van 55 procent een maand terug. Ik verkoop zelf kleding en sieraden en loop er zelden meer tegenaan.

Ik wil je vragen het nog een keer te proberen, met een verlengde proefperiode zodat het je niks kost. Antwoord op deze mail als je wilt dat ik meekijk terwijl je je eerste tien advertenties doet.

Daniel van Omnivaleur
"""

BODY_B = """Hi,

Daniel hier, van Omnivaleur.

Jij hebt het product nooit een keer zien werken. Op de dag dat je je aanmeldde ging vrijwel elke publicatie mis, en daarna heb je het niet meer geopend. Logisch.

Sindsdien is er veel gerepareerd: de gekoppelde verwijdering, lege velden, de valse melding dat je niet was ingelogd. Deze week mislukt 7 procent van de opdrachten, tegen 55 procent toen jij het probeerde.

Je proefperiode staat weer open, verlengd, zodat je rustig opnieuw kunt kijken. Werkt iets niet, antwoord dan op deze mail, die komt bij mij.

Daniel van Omnivaleur
"""

BODY_C = """Hi,

Daniel hier, van Omnivaleur.

Je hebt een account aangemaakt maar bent nooit begonnen. Geen verwijt, het eerste zetje is het lastigste, zeker met een grote voorraad.

Heb je behoefte om even hier samen naar te kijken? Daarna weet je of het bij jou past. Je proefperiode is verlengd zodat je de tijd hebt.

Antwoord op deze mail met een dag en tijd die je schikt.

Daniel van Omnivaleur
"""

GROEPEN = {
    "A": {"subject": SUBJECT_A, "body": BODY_A, "heeft_detail": True},
    "B": {"subject": SUBJECT_B, "body": BODY_B, "heeft_detail": False},
    "C": {"subject": SUBJECT_C, "body": BODY_C, "heeft_detail": False},
}


def parse_ontvangers(raw: str) -> list[dict]:
    """Adressen uit een geplakte lijst halen. Per regel een adres; voor groep A mag
    er een eigen zin achter met een liggend streepje ervoor:

        henk@voorbeeld.nl | 14 van je 18 publicaties liepen vast, niets geplaatst
        anna@voorbeeld.be

    Regels zonder @ vallen af (kolomkop, datum). Dubbele adressen eruit, eerste
    wint. Retour: [{"email": ..., "detail": ... of None}, ...].
    """
    import re

    seen: set[str] = set()
    out: list[dict] = []
    for regel in raw.splitlines():
        # Eerst op het streepje splitsen: staat er een eigen zin achter (groep A),
        # dan is de hele regel een ontvanger en blijft de zin met komma's heel.
        if "|" in regel:
            stukken = [regel]
        else:
            stukken = re.split(r"[,;]+", regel)
        for stuk in stukken:
            deel = stuk.strip()
            if not deel:
                continue
            detail = None
            if "|" in deel:
                adres, _, rest = deel.partition("|")
                detail = rest.strip() or None
                deel = adres.strip()
            email = deel.strip().strip('"\'<>()').lower()
            if "@" not in email or "." not in email.split("@")[-1]:
                continue
            if email in seen:
                continue
            seen.add(email)
            out.append({"email": email, "detail": detail})
    return out


def render(groep: str, ontvanger: dict) -> tuple[str, str]:
    """(onderwerp, tekst) voor een ontvanger. Groep A vult de eigen zin in."""
    g = GROEPEN[groep]
    body = g["body"]
    if g["heeft_detail"]:
        body = body.replace("{detail}", ontvanger.get("detail") or DETAIL_FALLBACK)
    return g["subject"], body


# Categorieën die als "sieraden of antiek zilver" tellen voor de eerste ronde.
# De import raadt de categorie en schrijft hem in kleine letters in items.category;
# de taxonomie kent twee lagen (oude Vinted-achtige en de huidige MP-laag), dus
# hier op deelwoord matchen, niet op exacte naam.
SIERADEN_PATRONEN = (
    "sieraden", "ketting", "armband", "ring", "broche", "oorbel", "oorbell",
    "horloge", "antiek", "zilver", "goud", "bestek", "munt",
)


def _is_sieraden(categorie: str) -> bool:
    c = (categorie or "").lower()
    return any(p in c for p in SIERADEN_PATRONEN)


# Eigen test- en beoordelaarsaccounts horen niet in een terughaalmail. Herkenbaar
# aan plus-adressering, aan de eigen domeinen, of aan een woord als test/demo/
# reviewer in het adres.
_TEST_DOMEINEN = ("omnivaleur.nl", "omnivaleur.com", "omnivaleur.eu", "crosslisteu.com", "crosslist.eu")
_TEST_WOORDEN = ("test", "demo", "reviewer", "rebrandtest", "checkout-test", "ga4test", "+demo", "+ga")


def _is_testaccount(email: str) -> bool:
    e = (email or "").lower()
    if "+" in e.split("@")[0]:
        return True
    domein = e.split("@")[-1]
    if any(domein == d or domein.endswith("." + d) for d in _TEST_DOMEINEN):
        return True
    return any(w in e for w in _TEST_WOORDEN)


def _suggereer_groep(jobs_totaal: int, geplaatst: int, mislukt: int) -> str:
    """Ruwe indeling; de eigenaar corrigeert hem met de hand.
    C = nooit begonnen. A = het serieus geprobeerd maar niets geplaatst gekregen.
    B = wel opdrachten, grotendeels mislukt. rest = grijs gebied, eigenaar beslist.
    """
    if jobs_totaal == 0:
        return "C"
    if geplaatst == 0 and jobs_totaal >= 8:
        return "A"
    if jobs_totaal and mislukt / jobs_totaal >= 0.6:
        return "B"
    return "rest"


def kandidaten() -> dict:
    """Slapende oud-klanten opzoeken en per vermoedelijke groep indelen.

    Leest uitsluitend met de service-sleutel (get_admin_db): de server mag jobs en
    items met de publieke sleutel niet lezen en dat wordt stil een lege lijst.
    Schrijft niets.
    """
    from datetime import datetime, timedelta, timezone

    from backend.database import get_admin_db

    db = get_admin_db()

    # 1. Alle gebruikers: id -> e-mail en aanmelddatum.
    users: dict[str, dict] = {}
    page = 1
    while True:
        batch = db.auth.admin.list_users(page=page, per_page=200)
        if not batch:
            break
        for u in batch:
            users[u.id] = {
                "email": (getattr(u, "email", None) or "").strip().lower(),
                "aangemeld": getattr(u, "created_at", None),
            }
        if len(batch) < 200:
            break
        page += 1

    # 2. Abonnementen: wie betaalt niet en zit dus in de doelgroep.
    subs = db.table("subscriptions").select(
        "user_id,status,plan,stripe_subscription_id,trial_ends_at"
    ).execute().data or []
    sub_van = {s["user_id"]: s for s in subs}

    grens = datetime.now(timezone.utc) - timedelta(days=10)

    def _naar_dt(waarde) -> "datetime | None":
        # gotrue geeft created_at soms als datetime terug, PostgREST als string.
        if waarde is None:
            return None
        if isinstance(waarde, datetime):
            return waarde if waarde.tzinfo else waarde.replace(tzinfo=timezone.utc)
        try:
            d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _te_vers(waarde) -> bool:
        d = _naar_dt(waarde)
        return bool(d and d > grens)

    kandidaat_ids: list[str] = []
    for uid, info in users.items():
        s = sub_van.get(uid)
        if s and s.get("stripe_subscription_id"):
            continue  # betaalt
        if not info["email"] or _te_vers(info.get("aangemeld")):
            continue  # net aangemeld, nog in de gewone proef
        kandidaat_ids.append(uid)

    # 3. Opdrachtgeschiedenis per kandidaat.
    jobs_agg: dict[str, dict] = {uid: {"totaal": 0, "mislukt": 0, "geplaatst": 0} for uid in kandidaat_ids}
    for i in range(0, len(kandidaat_ids), 200):
        brok = kandidaat_ids[i:i + 200]
        rijen = db.table("jobs").select("user_id,action,status").in_("user_id", brok).execute().data or []
        for r in rijen:
            a = jobs_agg.get(r["user_id"])
            if a is None:
                continue
            a["totaal"] += 1
            if r.get("status") == "error":
                a["mislukt"] += 1
            if r.get("action") == "create" and r.get("status") == "done":
                a["geplaatst"] += 1

    # 4. Wat verkopen ze: categorieën uit items.
    cats: dict[str, set] = {uid: set() for uid in kandidaat_ids}
    for i in range(0, len(kandidaat_ids), 200):
        brok = kandidaat_ids[i:i + 200]
        rijen = db.table("items").select("user_id,category").in_("user_id", brok).execute().data or []
        for r in rijen:
            c = (r.get("category") or "").strip()
            if c and r["user_id"] in cats:
                cats[r["user_id"]].add(c)

    groepen: dict[str, list] = {"A": [], "B": [], "C": [], "rest": []}
    for uid in kandidaat_ids:
        a = jobs_agg[uid]
        categorien = sorted(cats[uid])
        rij = {
            "email": users[uid]["email"],
            "aangemeld": users[uid]["aangemeld"],
            "opdrachten": a["totaal"],
            "mislukt": a["mislukt"],
            "geplaatst": a["geplaatst"],
            "categorien": categorien,
            "sieraden": any(_is_sieraden(c) for c in categorien),
            "proef_tot": (sub_van.get(uid) or {}).get("trial_ends_at"),
        }
        groepen[_suggereer_groep(a["totaal"], a["geplaatst"], a["mislukt"])].append(rij)

    for lijst in groepen.values():
        lijst.sort(key=lambda r: (not r["sieraden"], -r["opdrachten"]))
    return {"aantal": len(kandidaat_ids), "groepen": groepen}


def verleng_proef(emails: list[str], dagen: int) -> dict:
    """Zet de proefperiode van deze mensen op nu + `dagen` en hun status weer op
    'trialing'. Met de service-sleutel, want dit schrijft in andermans rij.
    Retour: welke adressen gelukt zijn en welke niet gevonden.
    """
    from datetime import datetime, timedelta, timezone

    from backend.database import get_admin_db
    from backend.services.billing import invalidate_access_cache

    db = get_admin_db()
    wil = {e.strip().lower() for e in emails if e.strip()}

    id_van: dict[str, str] = {}
    page = 1
    while wil and True:
        batch = db.auth.admin.list_users(page=page, per_page=200)
        if not batch:
            break
        for u in batch:
            e = (getattr(u, "email", None) or "").strip().lower()
            if e in wil:
                id_van[e] = u.id
        if len(batch) < 200 or len(id_van) == len(wil):
            break
        page += 1

    nieuw = (datetime.now(timezone.utc) + timedelta(days=dagen)).isoformat()
    gelukt: list[str] = []
    for email, uid in id_van.items():
        db.table("subscriptions").update({
            "status": "trialing",
            "plan": "pro",
            "trial_ends_at": nieuw,
        }).eq("user_id", uid).execute()
        invalidate_access_cache(uid)
        gelukt.append(email)

    return {
        "verlengd_tot": nieuw,
        "gelukt": gelukt,
        "niet_gevonden": sorted(wil - set(gelukt)),
    }
