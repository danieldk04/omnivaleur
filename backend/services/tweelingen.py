"""Twee items die hetzelfde product zijn, als één product behandelen.

WAAROM DIT BESTAAT (30-08-2026)
Bij het importeren ontstaan tweelingen: dezelfde trui komt één keer binnen via
Marktplaats en één keer via Vinted, en dat worden twee rijen in `items`. Ze zijn
herkenbaar aan het nummer dat de verkoper zelf voor de titel zet — "(1237) Navy
Suitsupply Half Zip" — maar ze worden nooit samengevoegd.

Gemeten bij Daniel: item A stond op Vinted VERKOCHT (21-08), item B was dezelfde
trui en werd daarna gewoon opnieuw op Marktplaats gezet. Elke controle keek naar
één rij en zag geen verkoop. Datzelfde nummer zorgde er ook voor dat een live
Vinted-advertentie aan geen van beide rijen gekoppeld kon worden — twee kandidaten
is geen koppeling — waardoor het dashboard "staat niet op Vinted" toonde terwijl
de advertentie er gewoon stond.

Deze module levert het nummer van een item en alle item-id's die datzelfde
nummer dragen.

AANVULLING 30-08-2026 — WAAROM HIER MEER IN ZIT DAN ALLEEN VERWIJDEREN
----------------------------------------------------------------------
Het weghalen van de advertenties van een tweeling bij verkoop was maar de helft.
De andere helft is dat het dashboard bij elk van die rijen "staat niet op Vinted"
bleef zeggen, en dat "Publish" dan een TWEEDE advertentie aanmaakte voor iets dat
er al stond. Daarom levert deze module nu ook: het groeperen van de hele voorraad
(`groepeer`), de zusterrijen van één item (`zusters`), en de harde kleur-, maat-,
merk- en prijscontrole (`plausibel`) die voorkomt dat een hergebruikt nummer twee
verschillende artikelen aan elkaar plakt.

Gemeten op de voorraad van 30-08-2026: 440 items waarvan er 46 in werkelijkheid
13 artikelen waren. Eén paar schoenen was al op Vinted verkocht terwijl de dubbele
rij gewoon op Marktplaats bleef staan — een verkoop die niet te leveren was.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Alleen een nummer waar veilig op te zoeken valt. Alles daarbuiten (spaties,
# haakjes, komma's) laten we lopen: dan is er gewoon geen familie.
_VEILIG = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def nummer_van(item: dict) -> str:
    """Het eigen nummer van de verkoper: uit de TITEL, anders uit het SKU-veld.

    De titel gaat voor, en dat is geen smaakkwestie. Het SKU-veld wordt bij het
    importeren zelf gevuld en krijgt per bron een eigen waarde ("imp-4eb880ca",
    "rev-2e6d54b5"), dus twee rijen van hetzelfde product hebben daar juist
    VERSCHILLENDE waarden. Het nummer dat de verkoper zelf voor de titel zet —
    "(1237)" — is het enige dat bij beide rijen gelijk is.
    """
    uit_titel = (advertentiecode(str((item or {}).get("title") or "")) or "").lower()
    if uit_titel and _VEILIG.match(uit_titel):
        return uit_titel
    sku = str((item or {}).get("sku") or "").strip().lower()
    return sku if sku and _VEILIG.match(sku) else ""


def familie_ids(db, item: dict) -> list[str]:
    """Alle item-id's van deze verkoper met hetzelfde nummer, inclusief dit item.

    Eén gerichte vraag aan de database, geen volledige voorraad ophalen: dit
    draait in de uitdeelronde en bij elke verkoop.
    """
    eigen = (item or {}).get("id")
    nummer = nummer_van(item)
    user_id = (item or {}).get("user_id")
    if not (eigen and nummer and user_id):
        return [eigen] if eigen else []
    try:
        # De aanhalingstekens om het zoekpatroon zijn niet cosmetisch. Zonder
        # die tekens leest PostgREST de haakjes van "(1032)%" als zijn eigen
        # groepering, en dan komt er GEEN fout terug maar een lege lijst.
        # Gemeten op 30-08-2026: 1 van de 8 rijen gevonden, waardoor het
        # weghalen van de advertenties van een tweeling nooit heeft gewerkt.
        rijen = (db.table("items").select("id,brand,title")
                 .eq("user_id", user_id)
                 .or_(f'sku.eq.{nummer},title.ilike."({nummer})%"')
                 .limit(50).execute().data or [])
    except Exception as e:  # noqa: BLE001 — bij twijfel alleen het item zelf
        logger.warning("tweelingen: kon familie van %s niet lezen: %s", eigen, e)
        return [eigen]

    # Zelfde nummer is een sterk signaal, maar niet genoeg om een advertentie op
    # weg te halen: een verkoper kan een nummer hergebruiken. Staat er een merk
    # bij, dan moet dat overeenkomen. Titels vergelijken heeft hier geen zin —
    # de tweelingen zijn juist vertalingen van elkaar ("Suitable Half Zip" en
    # "Geschikte Halve Rits").
    eigen_merk = str((item or {}).get("brand") or "").strip().lower()
    ids = []
    for r in rijen:
        if not r.get("id"):
            continue
        merk = str(r.get("brand") or "").strip().lower()
        if eigen_merk and merk and merk != eigen_merk:
            continue
        ids.append(r["id"])
    return list(dict.fromkeys([eigen, *ids]))


# Een prijsverschil van meer dan dit is nooit hetzelfde voorwerp.
_TWIN_PRICE_FACTOR = 2.5

# Minimaal drie tekens en minstens twee cijfers. Zo valt "(XL)", "(new)" en
# "(2x)" af, terwijl "(1032)", "(REV-36689077)" en "(IMP-B73A940F)" blijven.
_CODE_RE = re.compile(r"^\s*[\(\[\{]\s*([A-Za-z0-9][A-Za-z0-9\-_.]{1,23})\s*[\)\]\}]")


def advertentiecode(titel: str | None, sku: str | None = None) -> str | None:
    """Het artikelnummer waarmee de verkoper deze advertentie zelf nummert.

    Uit de titel, want dat is het enige veld dat op élk platform hetzelfde
    begin heeft. Staat er niets, dan telt een sku die zelf al een kaal nummer
    is (zoals "1327") — die komt uit een eerdere eigen nummering.
    """
    m = _CODE_RE.match(titel or "")
    if m:
        code = m.group(1).strip().upper()
        if len(code) >= 3 and sum(c.isdigit() for c in code) >= 2:
            return code
    s = (sku or "").strip()
    if len(s) >= 3 and s.isdigit():
        return s.upper()
    return None


def _prijs(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# Kleurwoorden die in beide talen hetzelfde betekenen. Alles wat hier niet in
# staat wordt zichzelf, zodat een onbekende kleur nooit met een andere matcht.
_COLOR_CANON = {
    "zwart": "black", "zwarte": "black", "black": "black",
    "wit": "white", "witte": "white", "white": "white",
    "gebroken wit": "offwhite", "off white": "offwhite", "ecru": "offwhite", "crème": "cream",
    "creme": "cream", "cream": "cream",
    "grijs": "grey", "grijze": "grey", "grey": "grey", "gray": "grey",
    "lichtgrijs": "lightgrey", "lichtgrijze": "lightgrey", "light grey": "lightgrey",
    "donkergrijs": "darkgrey", "donkergrijze": "darkgrey", "dark grey": "darkgrey",
    "blauw": "blue", "blauwe": "blue", "blue": "blue", "royal blue": "blue",
    "lichtblauw": "lightblue", "lichtblauwe": "lightblue", "light blue": "lightblue",
    "donkerblauw": "navy", "donkerblauwe": "navy", "dark blue": "navy",
    "marine": "navy", "marineblauw": "navy", "marineblauwe": "navy", "navy": "navy",
    "rood": "red", "rode": "red", "red": "red",
    "bordeaux": "burgundy", "burgundy": "burgundy", "maroon": "burgundy", "wine": "burgundy",
    "groen": "green", "groene": "green", "green": "green",
    "lichtgroen": "lightgreen", "lichtgroene": "lightgreen", "light green": "lightgreen",
    "donkergroen": "darkgreen", "donkergroene": "darkgreen", "dark green": "darkgreen",
    "olijfgroen": "olive", "olijfgroene": "olive", "olive": "olive", "kaki": "khaki", "khaki": "khaki",
    "bruin": "brown", "bruine": "brown", "brown": "brown", "cognac": "cognac", "camel": "camel",
    "taupe": "taupe", "beige": "beige", "tan": "beige",
    "geel": "yellow", "gele": "yellow", "yellow": "yellow", "mustard": "mustard",
    "oranje": "orange", "orange": "orange",
    "roze": "pink", "pink": "pink", "zalm": "salmon",
    "paars": "purple", "paarse": "purple", "purple": "purple",
    "lila": "lilac", "lilac": "lilac", "lavender": "lilac",
    "zilver": "silver", "zilveren": "silver", "silver": "silver",
    "goud": "gold", "gouden": "gold", "gold": "gold",
    "mint": "mint", "teal": "teal", "turquoise": "turquoise", "multi": "multi",
}

_SIZE_WORDS = {
    "small": "S", "medium": "M", "large": "L",
    "extra small": "XS", "extra large": "XL",
}
_SIZE_TOKEN = re.compile(r"^(xxxs|xxs|xs|s|m|l|xl|xxl|xxxl|w\d{2}|\d{2})$", re.I)


def kleuren(text: str | None) -> set:
    """Elke kleur in een titel, in één taalneutrale woordenschat."""
    s = f" {' '.join((text or '').lower().split())} "
    found = set()
    for word in sorted(_COLOR_CANON, key=len, reverse=True):
        if f" {word} " in s or f" {word}e " in s:
            found.add(_COLOR_CANON[word])
    return found


def maten(text: str | None) -> set:
    """Maataanduidingen in een titel — 'Heren XXL', 'Men XXL', 'W36', 'maat 42'."""
    s = " ".join((text or "").lower().split())
    out = set()
    for word, canon in _SIZE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", s):
            out.add(canon)
    for tok in re.split(r"[^a-z0-9]+", s):
        if not tok or not _SIZE_TOKEN.match(tok):
            continue
        if tok.isdigit() and not (28 <= int(tok) <= 52):
            continue      # een getal dat geen geloofwaardige kleding- of schoenmaat is
        out.add(tok.upper())
    return out


def merken(text: str | None, bekend: set) -> set:
    """Welke van de eigen merknamen van de verkoper in een titel voorkomen."""
    s = " ".join((text or "").lower().split())
    return {b for b in bekend if b and re.search(rf"\b{re.escape(b)}\b", s)}


def plausibel(a: dict, b: dict, bekende_merken: set | None = None) -> str | None:
    """
    Harde controles waar geen taalmodel en geen nummer omheen praat. Geeft de
    reden van afwijzing terug, of None als het paar overeind blijft.

    Gemeten op echte voorraad: het model koppelde op eigen kracht grijs aan
    blauw, Profuomo aan Suitsupply en een M aan een XL. Kleur, maat en merk
    staan gewoon in de titel, dus die worden door regels beslist.
    """
    bekende_merken = bekende_merken or set()
    pa, pb = _prijs(a.get("price")), _prijs(b.get("price"))
    if pa and pb and pa > 0 and pb > 0 and max(pa, pb) / min(pa, pb) > _TWIN_PRICE_FACTOR:
        return "price"

    ca, cb = kleuren(a.get("title")), kleuren(b.get("title"))
    if ca and cb and not (ca & cb):
        return "colour"

    sa, sb = maten(a.get("title")), maten(b.get("title"))
    if sa and sb and not (sa & sb):
        return "size"

    ba = merken(a.get("title"), bekende_merken) | ({(a.get("brand") or "").lower()} - {""})
    bb = merken(b.get("title"), bekende_merken) | ({(b.get("brand") or "").lower()} - {""})
    if ba and bb and not (ba & bb):
        return "brand"

    return None


def zelfde_artikel(a: dict, b: dict, bekende_merken: set | None = None) -> bool:
    """Zijn dit twee advertenties van hetzelfde fysieke voorwerp?

    Alleen ja bij hetzelfde advertentienummer én een kleur, maat, merk en prijs
    die elkaar niet tegenspreken. Nooit ja op titelgelijkenis alleen: twee
    truien die op één maat na identiek heten scoren bijna 1,0 op tekstgelijkenis
    en zijn toch twee verschillende truien.
    """
    ca = advertentiecode(a.get("title"), a.get("sku"))
    if not ca:
        return False
    if ca != advertentiecode(b.get("title"), b.get("sku")):
        return False
    return plausibel(a, b, bekende_merken) is None


def bekende_merken_van(items) -> set:
    """De eigen merkenwoordenschat van deze verkoper."""
    uit = {(i.get("brand") or "").strip().lower() for i in items}
    uit.discard("")
    return uit


def groepeer(items: list[dict]) -> list[list[dict]]:
    """
    Deel de voorraad op in groepen die hetzelfde artikel zijn. Alleen groepen
    met meer dan één item komen terug, oudste item eerst — dat is het item dat
    de andere opslokt bij samenvoegen, want daar hangt de langste geschiedenis
    aan.
    """
    bekend = bekende_merken_van(items)
    per_code: dict[str, list[dict]] = {}
    for it in items:
        code = advertentiecode(it.get("title"), it.get("sku"))
        if code:
            per_code.setdefault(code, []).append(it)

    groepen: list[list[dict]] = []
    for kandidaten in per_code.values():
        if len(kandidaten) < 2:
            continue
        # Binnen één nummer kan nog steeds meer dan één artikel zitten (een
        # verkoper die zijn nummering hergebruikt). Dus opnieuw bundelen op
        # plausibiliteit, en wat alleen overblijft valt vanzelf af.
        open_lijst = list(kandidaten)
        while open_lijst:
            eerste = open_lijst.pop(0)
            bij_elkaar = [eerste]
            rest = []
            for ander in open_lijst:
                if plausibel(eerste, ander, bekend) is None:
                    bij_elkaar.append(ander)
                else:
                    rest.append(ander)
            open_lijst = rest
            if len(bij_elkaar) > 1:
                bij_elkaar.sort(key=lambda i: (i.get("created_at") or "", i.get("id") or ""))
                groepen.append(bij_elkaar)
    groepen.sort(key=lambda g: -len(g))
    return groepen


def zusters(item: dict, items: list[dict], bekende_merken: set | None = None) -> list[dict]:
    """De andere items die hetzelfde artikel zijn als dit item."""
    bekend = bekende_merken if bekende_merken is not None else bekende_merken_van(items)
    return [i for i in items
            if i.get("id") != item.get("id") and zelfde_artikel(item, i, bekend)]
