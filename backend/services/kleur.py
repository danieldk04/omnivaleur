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
    # "Meerkleurig", niet "Multicolour": gemeten 03-09-2026 op Toons eigen
    # advertentie in "plaids en woondekens" (plaidsKleur: "Meerkleurig").
    "multicolour": "Meerkleurig",
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
    "yellow": "Geel", "gold": "Goud", "multi": "Multicolour", "various": "Meerkleurig", "clear": "Wit",
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
    # Woord voor woord en in de geschreven volgorde: bij "Beige bruin" bedoelt de
    # verkoper eerst beige. Pas als geen enkel los woord iets oplevert, de hele
    # tekst als één woord — die pikt het laatste stuk op ("lichtblauw" → blauw).
    for woord in re.split(r"[\s,/&+·-]+", rauw):
        stam = _kleur_stam(woord)
        if stam:
            return KLEUR_BASIS.get(stam, "")
    stam = _kleur_stam(rauw)
    return KLEUR_BASIS.get(stam, "") if stam else ""


# ---------------------------------------------------------------------------
# DE ENE KLEURENLIJST VOOR ALLE KANALEN (30-09-2026)
#
# Dezelfde 29 kleuren als Vinted (opgehaald bij Vinted zelf, zie
# tests/vinted-kleur-afwerking-test.js): Vinted heeft de strengste lijst, en
# elke kleur daarvan is voor Marktplaats en 2dehands terug te brengen tot hun
# grondvorm. Het keuzemenu in het dashboard bewaart de Engelse naam (eerste
# kolom); de tweede is wat een Nederlandse klant ziet; de derde is Vinteds
# eigen code, waarmee tests/kleurenlijst-alle-kanalen-test.js controleert dat de
# extensie de kleur ook echt op zijn tegel legt.
# ---------------------------------------------------------------------------
KLEUREN = [
    ("Black", "Zwart", "BLACK"), ("Grey", "Grijs", "GREY"), ("White", "Wit", "WHITE"),
    ("Cream", "Crème", "CREAM"), ("Beige", "Beige", "BODY"),
    ("Apricot", "Pasteloranje", "APRICOT"), ("Orange", "Oranje", "ORANGE"),
    ("Coral", "Koraal", "CORAL"), ("Red", "Rood", "RED"),
    ("Burgundy", "Wijnrood", "BURGUNDY"), ("Pink", "Roze", "PINK"),
    ("Rose", "Lichtroze", "ROSE"), ("Purple", "Paars", "PURPLE"),
    ("Lilac", "Lila", "LILAC"), ("Light blue", "Lichtblauw", "LIGHT-BLUE"),
    ("Blue", "Blauw", "BLUE"), ("Navy", "Marineblauw", "NAVY"),
    ("Turquoise", "Turquoise", "TURQUOISE"), ("Mint", "Mintgroen", "MINT"),
    ("Green", "Groen", "GREEN"), ("Dark green", "Donkergroen", "DARK-GREEN"),
    ("Khaki", "Khaki", "KHAKI"), ("Brown", "Bruin", "BROWN"),
    ("Mustard", "Mosterdgeel", "MUSTARD"), ("Yellow", "Geel", "YELLOW"),
    ("Silver", "Zilver", "SILVER"), ("Gold", "Goud", "GOLD"),
    ("Various", "Meerkleurig", "VARIOUS"), ("Clear", "Transparant", "CLEAR"),
]
_CANON = {en.lower(): en for en, _, _ in KLEUREN}
_CANON.update({nl.lower().translate(_ACCENTEN): en for en, nl, _ in KLEUREN})

# Wat iemand schrijft en wat de lijst niet letterlijk kent, naar de kleur die hij
# bedoelt. Alleen woorden met een duidelijke bedoeling: onbekend blijft onbekend.
_CANON_EXTRA = {
    "gray": "Grey", "lichtgrijs": "Grey", "donkergrijs": "Grey", "light grey": "Grey",
    "dark grey": "Grey", "light gray": "Grey", "dark gray": "Grey",
    "antraciet": "Grey", "charcoal": "Grey", "anthracite": "Grey",
    "ecru": "Cream", "creme": "Cream", "ivoor": "Cream", "ivory": "Cream",
    "offwhite": "Cream", "off white": "Cream", "gebroken wit": "Cream",
    "taupe": "Beige", "camel": "Beige", "tan": "Beige", "sand": "Beige", "zand": "Beige",
    "oranje": "Orange", "salmon": "Coral", "zalm": "Coral",
    "bordeaux": "Burgundy", "wijn": "Burgundy", "wine": "Burgundy", "maroon": "Burgundy",
    "fuchsia": "Pink", "oudroze": "Rose", "lichtroze": "Rose", "light pink": "Rose",
    "lavendel": "Lilac", "lavender": "Lilac", "violet": "Purple", "paars": "Purple",
    "lichtblauw": "Light blue", "lightblue": "Light blue", "baby blue": "Light blue",
    "babyblauw": "Light blue", "sky blue": "Light blue", "hemelsblauw": "Light blue",
    "marine": "Navy", "marineblauw": "Navy", "navy blue": "Navy", "dark blue": "Navy",
    "donkerblauw": "Navy", "kobalt": "Blue", "cobalt": "Blue", "denim": "Blue",
    "jeans": "Blue", "royal blue": "Blue", "petrol": "Turquoise", "teal": "Turquoise",
    "aqua": "Turquoise", "turkoois": "Turquoise",
    "mintgroen": "Mint", "donkergroen": "Dark green", "darkgreen": "Dark green",
    "olijf": "Khaki", "olive": "Khaki", "kaki": "Khaki", "legergroen": "Khaki",
    "army": "Khaki", "army green": "Khaki", "lichtgroen": "Green", "light green": "Green",
    "cognac": "Brown", "chocolade": "Brown", "chocolate": "Brown", "koffie": "Brown",
    "mosterd": "Mustard", "mosterdgeel": "Mustard", "okergeel": "Mustard", "oker": "Mustard",
    "zilver": "Silver", "goud": "Gold", "brons": "Gold", "bronze": "Gold",
    "multi": "Various", "multicolour": "Various", "multicolor": "Various",
    "meerkleurig": "Various", "divers": "Various", "diverse": "Various",
    "veelkleurig": "Various", "gemengd": "Various", "bont": "Various",
    "transparant": "Clear", "doorzichtig": "Clear", "transparent": "Clear",
}
_BASIS_NAAR_CANON = {
    "zwart": "Black", "wit": "White", "grijs": "Grey", "beige": "Beige", "bruin": "Brown",
    "rood": "Red", "bordeaux": "Burgundy", "roze": "Pink", "oranje": "Orange",
    "geel": "Yellow", "groen": "Green", "blauw": "Blue", "paars": "Purple",
    "goud": "Gold", "zilver": "Silver", "multicolour": "Various",
}


def _een_kleur(woord: str) -> str:
    """Eén geschreven kleur naar de naam uit KLEUREN, of "" als we hem niet kennen."""
    w = re.sub(r"\s+", " ", str(woord or "").strip().lower().translate(_ACCENTEN))
    if not w:
        return ""
    for tabel in (_CANON, _CANON_EXTRA):
        if w in tabel:
            return tabel[w]
    if w.replace(" ", "") in _CANON_EXTRA:
        return _CANON_EXTRA[w.replace(" ", "")]
    # Verbogen of samengesteld ("grijze", "lichtblauw"): alleen voor één los woord.
    # Met een spatie of scheidingsteken erin zou "beige, bruin" op "bruin" eindigen.
    if not re.search(r"[^a-z]", w):
        stam = _kleur_stam(w)
        return _BASIS_NAAR_CANON.get(stam, "") if stam else ""
    return ""


def canonieke_kleur(waarde) -> str:
    """De kleur zoals het keuzemenu hem bewaart ("Grey", "Light blue"), of "".

    Herkent Nederlands, Engels, verbogen vormen ("grijze", "rode") en gewone
    typefouten niet: een woord dat we niet kennen geeft "" terug, zodat de
    aanroeper de tekst van de verkoper laat staan. Twee kleuren ("beige, bruin",
    "blue/white") worden alleen omgezet als BEIDE herkend worden.
    """
    rauw = str(waarde or "").strip()
    if not rauw:
        return ""
    heel = _een_kleur(rauw)
    if heel:
        return heel
    delen = [d for d in re.split(r"\s*(?:,|/|&|\+|;|\ben\b|\band\b)\s*", rauw, flags=re.I) if d.strip()]
    if len(delen) < 2:
        # "Beige bruin": geen scheidingsteken, dan het eerste woord dat we kennen.
        eerste = [_een_kleur(x) for x in rauw.split()]
        eerste = [x for x in eerste if x]
        return eerste[0] if eerste and len(rauw.split()) <= 3 else ""
    uit = [_een_kleur(d) for d in delen]
    if not all(uit):
        return ""
    gezien: list[str] = []
    for k in uit:
        if k not in gezien:
            gezien.append(k)
    return ", ".join(gezien[:2])
