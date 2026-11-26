"""Verkoop op Vinted herkennen aan de mail die Vinted de verkoper zelf stuurt.

WAAROM (Daniel, 22-11-2026): Vinted verbiedt externe software op het account. Een
verkoop herkennen zonder ooit Vinted zelf aan te raken kan wel: Vinted mailt de
verkoper bij elke verkoop. De klant zet in zijn eigen mailprogramma een
doorstuurregel naar een persoonlijk adres bij ons, wij lezen alleen die mail.

Dit is ALLEEN een extra, snellere bron. De bestaande detectie blijft staan; deze
module boekt alleen als alles zeker klopt en laat anders met opzet niets gebeuren.

De regels, in volgorde van belang:
1. Echt van Vinted: de ontvangende server meldt DKIM "pass" en de afzender is een
   Vinted-domein. Een doorgestuurde mail van de klant zelf telt niet.
2. Eén eenduidig artikel: de titel in de mail hoort bij precies één actieve
   Vinted-advertentie van die klant. Bij twijfel (titelgenoten) niets doen.
3. De prijs uit de mail is wat de koper echt betaalde. Hij hoeft niet gelijk te zijn
   aan de vraagprijs (biedingen), dus de prijs beslist nooit WELK artikel het is,
   alleen als er meerdere titelgenoten zijn.
4. Van de mail bewaren we alleen titel en prijs. Naam en adres van de koper staan
   in de mail maar worden nooit opgeslagen.

Alleen Nederlandse en Engelse mails zijn gemeten (echte voorbeelden van 30-10 en
21-11-2026). Andere talen worden niet geraden maar overgeslagen.
"""
import html as _html
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VINTED_AFZENDER_DOMEINEN = ("vinted.nl", "vinted.com", "vinted.be", "vinted.fr", "vinted.de",
                            "vinted.co.uk", "vinted.es", "vinted.it", "vinted.pl", "vinted.lt")

# Onderwerp en de zin vóór de titel. Alleen talen waarvan een echt voorbeeld is bekeken.
_ONDERWERPEN = ("you've sold an item on vinted", "je hebt een artikel verkocht op vinted")
_MARKERINGEN = (r"has bought", r"heeft gekocht")

# Bedragen in de mail hebben altijd twee decimalen: "€29.99" en "€ 12,00".
_PRIJS = re.compile(r"€\s?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2})(?!\d)")


def _prijs_naar_getal(tekst: str) -> float | None:
    """'29.99' -> 29.99, '12,00' -> 12.0, '1.234,50' -> 1234.5.

    Het scheidingsteken met precies twee cijfers erachter is de komma of punt van de
    centen; alles ervoor is een duizendtalteken. Zo wordt '1.360,00' nooit 1,36
    (zie bedragveld-leest-duizendtalpunt-als-komma in de kennisbank).
    """
    m = re.fullmatch(r"(.*)[.,](\d{2})", tekst.strip())
    if not m:
        return None
    hele = re.sub(r"[.,]", "", m.group(1))
    if not hele.isdigit():
        return None
    return float(f"{hele}.{m.group(2)}")


def normaliseer_titel(titel: str) -> str:
    t = _html.unescape(titel or "")
    # Vinted schrijft "You’ve" met een gekrulde apostrof (echte mail 26-11-2026).
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def _zichtbare_tekst(tekst: str | None, html: str | None) -> str:
    if tekst and tekst.strip():
        return tekst
    if html:
        zonder = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
        zonder = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", zonder)
        zonder = re.sub(r"<[^>]+>", " ", zonder)
        return _html.unescape(zonder)
    return ""


def lees_verkoopmail(onderwerp: str | None, tekst: str | None, html: str | None) -> dict | None:
    """Geeft {'titel', 'prijs'} of None. None betekent: geen (herkenbare) verkoopmail."""
    if not onderwerp:
        return None
    onderwerp_n = normaliseer_titel(onderwerp)
    if not any(o in onderwerp_n for o in _ONDERWERPEN):
        return None
    body = _zichtbare_tekst(tekst, html)
    if not body:
        return None
    markering = re.search("|".join(_MARKERINGEN), body, flags=re.IGNORECASE)
    if not markering:
        return None
    rest = body[markering.end():]
    prijs_m = _PRIJS.search(rest)
    if not prijs_m:
        return None
    titel = re.sub(r"\s+", " ", rest[:prijs_m.start()]).strip()
    prijs = _prijs_naar_getal(prijs_m.group(1))
    if not titel or prijs is None or prijs <= 0 or len(titel) > 200:
        return None
    return {"titel": titel, "prijs": prijs}


def waarom_niet_herkend(onderwerp: str | None, tekst: str | None, html: str | None) -> str:
    """Welke stap van lees_verkoopmail faalde. Alleen een stapnaam, nooit mailinhoud."""
    if not onderwerp or not any(o in normaliseer_titel(onderwerp) for o in _ONDERWERPEN):
        return "onderwerp_onbekend"
    body = _zichtbare_tekst(tekst, html)
    if not body:
        return "geen_tekst"
    markering = re.search("|".join(_MARKERINGEN), body, flags=re.IGNORECASE)
    if not markering:
        return "zin_voor_de_titel_niet_gevonden"
    if not _PRIJS.search(body[markering.end():]):
        return "geen_prijs_na_de_titel"
    return "titel_of_prijs_onbruikbaar"


def afzender_is_vinted(van: str | None) -> bool:
    m = re.search(r"@([a-z0-9.\-]+)", (van or "").lower())
    if not m:
        return False
    dom = m.group(1)
    return any(dom == d or dom.endswith("." + d) for d in VINTED_AFZENDER_DOMEINEN)


def is_echt_van_vinted(van: str | None, authenticatie: dict | None) -> bool:
    """De ontvangende server (niet de afzender) meldt dat de DKIM-handtekening klopt."""
    if not afzender_is_vinted(van):
        return False
    return isinstance(authenticatie, dict) and authenticatie.get("dkim") == "pass"


def zelfde_titel(mail_titel: str, advertentie_titel: str) -> bool:
    """Gelijk, of de ene is de ingekorte vorm van de andere (Vinted kapt op 100 af)."""
    a, b = normaliseer_titel(mail_titel), normaliseer_titel(advertentie_titel)
    if not a or not b:
        return False
    if a == b:
        return True
    kort, lang = sorted((a, b), key=len)
    return len(kort) >= 20 and lang.startswith(kort)


def kies_artikel(mail: dict, kandidaten: list[dict]) -> tuple[dict | None, str]:
    """Kandidaten: [{'item_id','titel','prijs'}] van actieve Vinted-advertenties.

    Geeft (kandidaat, reden). Een kandidaat alleen als het ondubbelzinnig is.
    """
    zelfde = [k for k in kandidaten if zelfde_titel(mail["titel"], k["titel"])]
    if not zelfde:
        return None, "geen_actieve_advertentie_met_deze_titel"
    if len(zelfde) == 1:
        return zelfde[0], "unieke_titel"
    op_prijs = [k for k in zelfde if k.get("prijs") is not None and abs(float(k["prijs"]) - mail["prijs"]) < 0.005]
    if len(op_prijs) == 1:
        return op_prijs[0], "titel_en_prijs"
    return None, "meerdere_artikelen_met_deze_titel"


def adres_token(aan: list[str] | str | None) -> str | None:
    """Het geheime deel uit 'vinted-<token>@...'."""
    if isinstance(aan, str):
        aan = [aan]
    for a in aan or []:
        m = re.search(r"vinted-([a-f0-9]{24})@", str(a).lower())
        if m:
            return m.group(1)
    return None


def _ilike_kern(titel: str) -> str:
    kern = normaliseer_titel(titel)[:25]
    return "%" + kern.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"


async def verwerk_ontvangen_mail(*, db, naast_de_lus, handle_item_sold, bewijs, user_id: str,
                                 onderwerp: str | None, van: str | None, tekst: str | None,
                                 html: str | None, authenticatie: dict | None,
                                 ontvangen_op: datetime | None = None) -> dict:
    """Eén doorgestuurde mail. Geeft altijd een korte uitkomst terug, boekt alleen bij zekerheid."""
    if not is_echt_van_vinted(van, authenticatie):
        # Alleen metadata, nooit inhoud: wat de ontvangende server over deze mail zei.
        m = re.search(r"@([a-z0-9.\-]+)", (van or "").lower())
        auth = authenticatie if isinstance(authenticatie, dict) else None
        return {"uitkomst": "genegeerd", "reden": "niet_aantoonbaar_van_vinted",
                "afzender_domein": m.group(1) if m else None,
                "authenticatie": ({k: auth.get(k) for k in ("dkim", "spf", "dmarc")} if auth is not None
                                  else f"geen_veld({type(authenticatie).__name__})")}
    mail = lees_verkoopmail(onderwerp, tekst, html)
    if not mail:
        return {"uitkomst": "genegeerd", "reden": "geen_herkende_verkoopmail",
                "stap": waarom_niet_herkend(onderwerp, tekst, html),
                "onderwerp": (onderwerp or "")[:120]}

    items = (await naast_de_lus(lambda: db.table("items").select("id,title,price")
             .eq("user_id", user_id).ilike("title", _ilike_kern(mail["titel"])).limit(50).execute())).data or []
    if not items:
        return {"uitkomst": "overgeslagen", "reden": "geen_actieve_advertentie_met_deze_titel",
                "titel_in_mail": mail["titel"], "artikelen_met_titel": 0}
    ids = [i["id"] for i in items]
    actief = (await naast_de_lus(lambda: db.table("listings").select("item_id")
              .eq("platform", "vinted").eq("status", "active").in_("item_id", ids).execute())).data or []
    actieve_ids = {r["item_id"] for r in actief}
    kandidaten = [{"item_id": i["id"], "titel": i["title"], "prijs": i.get("price")}
                  for i in items if i["id"] in actieve_ids]
    gekozen, reden = kies_artikel(mail, kandidaten)
    if not gekozen:
        return {"uitkomst": "overgeslagen", "reden": reden, "titel_in_mail": mail["titel"],
                "artikelen_met_titel": len(items), "waarvan_actief_op_vinted": len(kandidaten)}

    await handle_item_sold(gekozen["item_id"], "vinted", sold_price=mail["prijs"],
                           sold_at=ontvangen_op or datetime.now(timezone.utc), bewijs=bewijs)
    return {"uitkomst": "geboekt", "reden": reden, "item_id": gekozen["item_id"], "prijs": mail["prijs"]}
