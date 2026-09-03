"""Geschreven kleurnamen terugbrengen tot de vorm die Marktplaats aanbiedt.

WAAROM DIT OP DE SERVER STAAT EN NIET ALLEEN IN DE EXTENSIE
------------------------------------------------------------
Marktplaats en 2dehands bieden in het Kleur-veld alleen de kale grondvorm aan:
Zwart, Wit, Grijs, Beige, Bruin, Rood, Bordeaux, Roze, Oranje, Geel, Groen,
Blauw, Paars, Goud, Multicolour. Verkopers schrijven iets anders op. Geteld in
Toons kast op 03-09-2026: 59 verschillende kleurwaarden over 1.024 artikelen,
waarvan "bruine" 41x, "zwarte" 20x, "rode" 16x, "crème" 13x, plus "lichtblauw",
"olijfgroene", "Beige bruin" en "divers".

Zo'n woord matcht op geen enkele optie, het verplichte veld blijft leeg, en dan
doet de plaatsknop van Marktplaats stil niets (gemeten 21-08-2026). Gemeten met
de echte extensiecode van 1.0.280 raakte dat 175 van zijn 1.024 artikelen.

De extensie kan dit sinds 1.0.282 zelf, maar een extensie bereikt de verkoper pas
nadat de Chrome Web Store hem heeft goedgekeurd en Chrome hem heeft opgehaald —
dagen, soms weken (Egbert draaide drie weken lang een versie eenentwintig stappen
achter). De server bereikt hem bij de eerstvolgende opdracht. Daarom zetten we de
kleur hier goed op het moment dat de opdracht de deur uit gaat: dan werkt het ook
op de kopie die hij vandaag draait, en op elke versie daarna.

Deze tabellen zijn met opzet identiek aan die in extension/content/shared.js.
tests/test_kleur_normalisatie.py leest beide en laat de test vallen zodra ze uit
elkaar lopen.
"""

from __future__ import annotations

import re

# De namen zoals Marktplaats ze in de keuzelijst schrijft.
KLEUR_BASIS = {
    "zwart": "Zwart", "wit": "Wit", "grijs": "Grijs", "beige": "Beige",
    "bruin": "Bruin", "rood": "Rood", "bordeaux": "Bordeaux", "roze": "Roze",
    "oranje": "Oranje", "geel": "Geel", "groen": "Groen", "blauw": "Blauw",
    "paars": "Paars", "goud": "Goud", "zilver": "Zilver",
    "multicolour": "Multicolour",
}

# Namen die geen grondvorm zijn maar wel iedereen bekend.
KLEUR_SYNONIEM = {
    "ecru": "wit", "creme": "wit", "ivoor": "wit", "gebroken": "wit",
    "offwhite": "wit",
    "taupe": "beige", "camel": "beige", "zand": "beige", "naturel": "beige",
    "cognac": "bruin", "chocolade": "bruin", "koffie": "bruin", "brique": "bruin",
    "marine": "blauw", "navy": "blauw", "turquoise": "blauw", "aqua": "blauw",
    "petrol": "blauw", "jeans": "blauw", "denim": "blauw", "kobalt": "blauw",
    "lila": "paars", "lavendel": "paars", "mauve": "paars", "aubergine": "paars",
    "kaki": "groen", "khaki": "groen", "olijf": "groen", "mint": "groen",
    "legergroen": "groen", "army": "groen", "jade": "groen",
    "zalm": "roze", "fuchsia": "roze", "framboos": "roze", "oudroze": "roze",
    "koraal": "rood", "terracotta": "rood", "robijn": "rood",
    "wijn": "bordeaux", "wijnrood": "bordeaux", "burgundy": "bordeaux",
    "oker": "geel", "okergeel": "geel", "mosterd": "geel", "limoen": "geel",
    "antraciet": "grijs", "muisgrijs": "grijs", "grafiet": "grijs",
    "brons": "goud", "messing": "goud",
    "divers": "multicolour", "diverse": "multicolour", "kleurrijk": "multicolour",
    "meerkleurig": "multicolour", "veelkleurig": "multicolour",
    "bont": "multicolour", "gemengd": "multicolour", "multi": "multicolour",
    "print": "multicolour", "gekleurd": "multicolour", "regenboog": "multicolour",
}

# Engels naar Nederlands — Vinted levert zijn kleuren in het Engels aan.
COLOUR_NL = {
    "black": "Zwart", "grey": "Grijs", "gray": "Grijs",
    "light grey": "Grijs", "light gray": "Grijs",
    "dark grey": "Grijs", "dark gray": "Grijs",
    "silver": "Grijs", "white": "Wit", "off white": "Wit", "cream": "Wit",
    "ecru": "Wit", "beige": "Beige", "camel": "Beige", "tan": "Beige",
    "taupe": "Beige", "apricot": "Oranje", "orange": "Oranje",
    "coral": "Rood", "red": "Rood", "burgundy": "Bordeaux", "maroon": "Bordeaux",
    "wine": "Bordeaux", "pink": "Roze", "rose": "Roze", "purple": "Paars",
    "lilac": "Paars", "lavender": "Paars", "blue": "Blauw", "light blue": "Blauw",
    "dark blue": "Blauw", "navy": "Blauw", "royal blue": "Blauw",
    "turquoise": "Blauw", "teal": "Blauw", "mint": "Groen", "green": "Groen",
    "light green": "Groen", "dark green": "Groen", "olive": "Groen",
    "khaki": "Groen", "brown": "Bruin", "cognac": "Bruin", "mustard": "Geel",
    "yellow": "Geel", "gold": "Goud", "multi": "Multicolour", "clear": "Wit",
}

_ACCENTEN = str.maketrans("àáâäèéêëìíîïòóôöùúûü", "aaaaeeeeiiiioooouuuu")


def _kleur_stam(woord: str) -> str:
    """Van één geschreven woord naar de basiskleur die erin zit, of ""."""
    w = re.sub(r"[^a-z]", "", str(woord or "").lower().translate(_ACCENTEN))
    if not w:
        return ""
    kandidaten = [w]
    if w.endswith("en") and len(w) > 4:
        kandidaten.append(w[:-2])                       # gouden → goud
    if w.endswith("e"):
        kaal = w[:-1]
        kandidaten.append(kaal)                         # bruine → bruin
        if len(kaal) >= 2 and kaal[-1] == kaal[-2]:
            kandidaten.append(kaal[:-1])                # witte → witt → wit
        if kaal.endswith("z"):
            kandidaten.append(kaal[:-1] + "s")          # grijze → grijs
        # Korte klinker wordt lang zodra de -e wegvalt: rode → rod → rood.
        kandidaten.append(re.sub(r"([aeiou])([a-z])$", r"\1\1\2", kaal))
    for k in kandidaten:
        if k in KLEUR_BASIS:
            return k
        if k in KLEUR_SYNONIEM:
            return KLEUR_SYNONIEM[k]
        if k in COLOUR_NL:
            return COLOUR_NL[k].lower()
    # Samenstelling: het laatste stuk is de kleur ("lichtblauw", "olijfgroen").
    # Het langste achtervoegsel wint, zodat "donkergroen" op groen uitkomt.
    for k in kandidaten:
        beste = ""
        for basis in KLEUR_BASIS:
            if len(k) > len(basis) and k.endswith(basis) and len(basis) > len(beste):
                beste = basis
        if beste:
            return beste
        for syn, doel in KLEUR_SYNONIEM.items():
            if len(k) > len(syn) and k.endswith(syn) and len(syn) > len(beste):
                beste = doel
        if beste:
            return beste
    return ""


def kleur_kandidaten(waarde) -> list[str]:
    """Alles wat voor deze kleur geprobeerd mag worden, nauwkeurigste eerst."""
    rauw = str(waarde or "").strip()
    if not rauw:
        return []
    uit: list[str] = []

    def voeg_toe(v: str) -> None:
        if v and not any(x.lower() == v.lower() for x in uit):
            uit.append(v)

    voeg_toe(rauw)
    # Woord voor woord en in de geschreven volgorde: bij "Beige bruin" bedoelt de
    # verkoper eerst beige. De hele tekst als één woord pikt juist het laatste
    # stuk op, dus die komt daarna.
    for woord in re.split(r"[\s,/&+·-]+", rauw):
        stam = _kleur_stam(woord)
        if stam:
            voeg_toe(KLEUR_BASIS.get(stam, stam))
    heel = _kleur_stam(rauw)
    if heel:
        voeg_toe(KLEUR_BASIS.get(heel, heel))
    return uit


def normaliseer_kleur(waarde) -> str:
    """De kleurnaam zoals Marktplaats hem schrijft, of "" als we hem niet kennen.

    Geeft met opzet "" terug bij een onbekende waarde, zodat de aanroeper de
    eigen tekst van de verkoper laat staan. Een kleur die wij niet begrijpen mag
    nooit door een verzonnen kleur worden vervangen.
    """
    rauw = str(waarde or "").strip()
    if not rauw:
        return ""
    if rauw.lower() in COLOUR_NL:
        return COLOUR_NL[rauw.lower()]
    kandidaten = kleur_kandidaten(rauw)
    # kandidaten[0] is de waarde zelf; de eerste afgeleide is wat we ervan
    # begrijpen. Begrijpen we er niets van, dan is er niets te normaliseren.
    return kandidaten[1] if len(kandidaten) > 1 else ""
