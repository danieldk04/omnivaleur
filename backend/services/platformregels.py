"""
Wat mag er op welk platform.

WAAROM DIT BESTAAT
Jaap Zilverwebsite verkoopt zilverwerk, antiek en sieraden door elkaar. Op
Vinted is alleen dat laatste bruikbaar: Vinted is een modeplatform en heeft
domweg geen plek voor een zilveren bestekcassette of een schilderij. Zonder een
rem hierop is een misklik in een bulkselectie genoeg om honderden zoekertjes te
proberen te plaatsen die daar niet thuishoren — dat is niet alleen zinloos werk,
het is ook precies het gedrag waar een platform accounts op sluit.

TWEE SOORTEN OORDEEL, EN HET VERSCHIL IS BELANGRIJK
- "blokkade": we weten het zeker, omdat het niet over beleid gaat maar over
  structuur. Vinted heeft geen categorie voor antiek, kunst, muziek, games of
  elektronica. Zo'n artikel kán daar niet staan; het formulier heeft er geen
  plek voor. Dat weigeren we.
- "twijfel": we vermoeden iets, maar het hangt af van de regels van het platform
  en die kunnen wij niet met zekerheid nalezen. Edelmetaal is het geval dat
  Daniel noemde: een zilveren ring is een sieraad, maar een zilverbaar of een
  zilveren munt is een belegging, en daar is Vinted niet voor. Dat wordt een
  waarschuwing, NOOIT een weigering.

Dat onderscheid is het hele punt. Een verkeerde blokkade houdt iemand tegen bij
iets dat gewoon mag, en dat is erger dan een gemiste waarschuwing: hij kan de
waarschuwing negeren, een blokkade niet.
"""
from __future__ import annotations

import re

# Categoriegroepen die op Vinted bestaan. Vinted is een modeplatform: kleding,
# schoenen, tassen, accessoires, sieraden en horloges. De groep "sieraden" in
# onze eigen boom bevat naast sieraden ook tassen, portemonnees en zonnebrillen
# — allemaal mode, dus die hoort er in zijn geheel bij.
_VINTED_GROEPEN_OK = ("dames ", "heren ", "kinderen ", "unisex ", "sieraden ")

# Categoriegroepen die Vinted niet kent. Dit is geen beleidsoordeel maar de
# indeling van hun eigen catalogus.
_VINTED_GROEPEN_NIET = {
    "antiek ": "antiek en curiosa",
    "kunst ": "kunst",
    "muziek ": "muziek en platen",
    "games ": "games en consoles",
    "electronics ": "elektronica",
}

# Edelmetaal als bélegging in plaats van als sieraad. Munten, baren, penningen
# en losse edelstenen. Bewust smal gehouden: "zilveren ring" mag hier niet in
# lopen, want dat is precies wat wél gewoon op Vinted kan.
_BELEGGING_RE = re.compile(
    r"\b(munt(en|stuk)?|baar|baren|bullion|troy\s*ounce|ounce\s*zilver|"
    r"gouden\s*tientje|zilveren\s*dukaat|penning(en)?|"
    r"beleggings(goud|zilver)|edelsteen|edelstenen|losse\s*diamant)\b",
    re.I,
)

# Zilverwerk voor op tafel of in de kast: geen mode, ook niet als het van zilver
# is. Dit is de hoofdmoot van Jaaps voorraad en de reden dat hij het vroeg.
_TAFELZILVER_RE = re.compile(
    r"\b(bestek(cassette)?|couvert|servies|theepot|koffiekan|dienblad|"
    r"kandelaar(s)?|kandelaber|schaal|schotel|suikerpot|melkkan|"
    r"tafelzilver|zilverwerk|beker(s)?|bonbonniere|sigarenkoker)\b",
    re.I,
)

OK = "ok"
TWIJFEL = "twijfel"
BLOKKADE = "blokkade"


def _tekst(item: dict) -> str:
    return f"{item.get('title') or ''} {item.get('description') or ''}"


def beoordeel(item: dict, platform: str) -> tuple[str, str]:
    """Geeft (oordeel, reden). De reden is de tekst die de verkoper te zien
    krijgt, dus die zegt wát er aan de hand is en niet welke regel er afging."""
    if platform != "vinted":
        return OK, ""

    categorie = str(item.get("category") or "").strip().lower()
    tekst = _tekst(item)

    for prefix, naam in _VINTED_GROEPEN_NIET.items():
        if categorie.startswith(prefix):
            return BLOKKADE, (
                f"Vinted is een modeplatform en heeft geen categorie voor {naam}. "
                f"Dit artikel is daar niet te plaatsen."
            )

    if _TAFELZILVER_RE.search(tekst):
        return TWIJFEL, (
            "Dit lijkt tafelzilver of servies in plaats van iets om te dragen. "
            "Vinted is een modeplatform; controleer of dit er thuishoort."
        )

    if _BELEGGING_RE.search(tekst):
        return TWIJFEL, (
            "Dit lijkt edelmetaal als belegging (munt, baar of losse steen) in "
            "plaats van een sieraad. Vinted staat dat niet overal toe — "
            "controleer dit er even zelf op."
        )

    # Geen categorie ingevuld: niets beweren. Een leeg veld is geen bewijs dat
    # het artikel ergens niet hoort, en blokkeren op onwetendheid is het
    # slechtste van twee werelden.
    if not categorie:
        return OK, ""

    if categorie.startswith(_VINTED_GROEPEN_OK):
        return OK, ""

    return OK, ""


def geblokkeerde_platforms(item: dict, platforms: list[str]) -> dict[str, str]:
    """De platforms uit `platforms` waar dit artikel niet op kan, met reden."""
    uit = {}
    for p in platforms:
        oordeel, reden = beoordeel(item, p)
        if oordeel == BLOKKADE:
            uit[p] = reden
    return uit
