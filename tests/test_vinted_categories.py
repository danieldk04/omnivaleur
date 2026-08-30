"""Vastgelegd op de échte formulieren van Vinted en Marktplaats (11 aug 2026).

Alles hieronder is live nagelopen in een ingelogde sessie, niet bedacht. Wijzigt
een platform zijn categorieboom, dan hoort deze test te vallen — dat is precies
het signaal dat er opnieuw gekeken moet worden.

Wat er live is vastgesteld en hier wordt afgedekt:
  1. Vinted zet ALLE sportkleding onder "Activewear". Zoeken op "cycling" levert
     alleen schoenen en fietsONDERDELEN op ("Sports > Cycling").
  2. Het zichtbare categorieveld is niet het zoekveld; de lijst heeft een eigen
     zoekvak ("Find a category"). Typen in het bovenste veld deed niets.
  3. In de zoekresultaten plakken naam en kruimelpad aan elkaar
     ("jerseysWomen"), waardoor de man/vrouw-weging stilletjes wegviel.
  4. Bij spijkerbroeken bestaat geen neutrale optie; zonder regel werd het
     "Ripped jeans" — een gave broek te koop als kapotte broek.
  5. Marktplaats vraagt bij sportkleding om een "Type" (o.a. "Hardlopen of
     Fietsen"); dat veld werd nooit ingevuld.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VINTED = (ROOT / "extension/content/vinted.js").read_text(encoding="utf-8")
MP = (ROOT / "extension/content/marktplaats.js").read_text(encoding="utf-8")
TWEEDEHANDS = (ROOT / "extension/content/tweedehands.js").read_text(encoding="utf-8")

# De bladeren zoals ze op vinted.nl in de kiezer staan.
VINTED_ACTIVEWEAR_LEAVES = {
    "Outerwear", "Tracksuits", "Trousers", "Shorts", "Tops & t-shirts",
    "Team shirts & jerseys", "Pullovers & sweaters", "Sports accessories",
    "Other activewear", "Dresses", "Skirts", "Hoodies & sweatshirts", "Sports bras",
}
VINTED_MENS_CLOTHING = {
    "Jeans", "Outerwear", "Tops & t-shirts", "Suits & blazers", "Jumpers & sweaters",
    "Trousers", "Shorts", "Socks & underwear", "Sleepwear", "Swimwear", "Activewear",
    "Costumes & special outfits", "Other clothing",
}
# Live gezien onder Men/Women > Clothing > Tops & t-shirts.
VINTED_TOPS_LEAVES = {"Shirts", "T-shirts", "Vests & sleeveless t-shirts", "Polo shirts"}
VINTED_WOMENS_CLOTHING = VINTED_MENS_CLOTHING | {
    "Dresses", "Skirts", "Trousers & leggings", "Shorts & cropped trousers",
    "Jumpsuits & playsuits", "Lingerie & nightwear", "Maternity clothes", "Skorts",
}


def _paths() -> dict:
    """De V_KLEDING-tabel uit vinted.js, per gender."""
    blok = VINTED.split("const V_KLEDING = {")[1].split("\n  };")[0]
    uit = {}
    for tak in ("heren", "dames"):
        deel = blok.split(f"{tak}: {{")[1].split("},")[0]
        uit[tak] = {
            m.group(1): re.findall(r'"([^"]+)"', m.group(2))
            for m in re.finditer(r'"([^"]+)":\s*\[([^\]]+)\]', deel)
        }
    return uit


@pytest.fixture(scope="module")
def paden():
    return _paths()


def test_sportcategorieen_gaan_naar_activewear(paden):
    sport = ["wielrenkleding", "voetbalkleding", "trainingspakken", "hardloopkleding",
             "skikleding", "gymkleding", "sportkleding", "sportbroeken", "sport tops"]
    for tak in ("heren", "dames"):
        for cat in sport:
            pad = paden[tak].get(cat)
            if pad is None:
                continue
            assert pad[0] == "Activewear", f"{tak} {cat} hoort onder Activewear, staat op {pad}"


def test_elk_pad_bestaat_echt_op_vinted(paden):
    for tak, geldig in (("heren", VINTED_MENS_CLOTHING), ("dames", VINTED_WOMENS_CLOTHING)):
        for cat, pad in paden[tak].items():
            assert pad[0] in geldig, f"{tak} {cat}: '{pad[0]}' bestaat niet onder {tak} > Clothing"
            if len(pad) > 1:
                toegestaan = {
                    "Activewear": VINTED_ACTIVEWEAR_LEAVES,
                    "Tops & t-shirts": VINTED_TOPS_LEAVES,
                }.get(pad[0])
                assert toegestaan, f"{tak} {cat}: '{pad[0]}' heeft in onze tabel geen bekende subbladeren"
                assert pad[1] in toegestaan, f"{tak} {cat}: '{pad[1]}' bestaat niet onder {pad[0]}"


def test_wielrenkleding_is_geen_fietsonderdeel(paden):
    """Zoeken op "cycling" geeft op Vinted schoenen en fietsen — nooit kleding."""
    for tak in ("heren", "dames"):
        assert paden[tak]["wielrenkleding"] == ["Activewear", "Team shirts & jerseys"]
    hints = VINTED.split("const CAT_HINTS = {")[1].split("\n  };")[0]
    for regel in hints.splitlines():
        if "wielrenkleding" in regel or "skikleding" in regel or "voetbalkleding" in regel:
            assert "cycling" not in regel and '"bike"' not in regel, f"fietsonderdeel-hint blijft staan: {regel.strip()}"


def test_kleding_wordt_uitgesloten_van_schoenen_en_sportmateriaal():
    assert "isClothingCat" in VINTED
    blok = VINTED.split("if (isClothingCat) {")[1].split("}")[0]
    assert "shoes?" in blok and "sports" in blok


def test_er_wordt_in_het_echte_zoekvak_getypt():
    assert "find a category" in VINTED.lower()
    assert "const searchBox = ()" in VINTED
    typeblok = VINTED.split("const typeSearch = (value) => {")[1].split("};")[0]
    assert "searchBox()" in typeblok, "typeSearch moet het zoekvak in de lijst gebruiken, niet het bovenste veld"


def test_naam_en_kruimelpad_worden_gescheiden():
    """Anders matcht \\bwomen\\b niet in 'jerseysWomen' en valt de genderweging weg."""
    assert "const rowText = (row) =>" in VINTED
    blok = VINTED.split("const rowText = (row) =>")[1][:600]
    assert "Cell__title" in blok and "Cell__body" in blok
    assert "([a-z0-9&\\]])([A-Z])" in blok


def test_geen_kapotte_spijkerbroek_bij_twijfel():
    """Zegt het artikel niets over pasvorm, dan het neutrale blad — nooit de eerste.

    Waar dit vandaan komt: op Vinted bestaat onder Jeans geen gewone "Jeans",
    alleen Ripped/Skinny/Slim fit/Straight fit. Zonder deze regel viel de keuze op
    de eerste optie, en dat is "Ripped jeans" — dan staat een gave spijkerbroek te
    koop als kapotte. Live nagelopen op vinted.nl.

    Deze test zocht naar `const neutraal = opties.find`. Die regel bestaat niet
    meer: de keuze is verhuisd naar `kiesBlad`, waar hij nu stap 3 is en `const n
    = namen.findIndex` heet. De bescherming zelf is ongewijzigd — alleen de vorm
    veranderde, en daar liep de test op stuk. Daarom toetst hij nu de garantie in
    plaats van de schrijfwijze: de neutrale woorden moeten in kiesBlad staan, en
    "Other …" mag nooit uit de puntentelling komen rollen (dat is de tweede helft
    van dezelfde bescherming — anders wint "Other" op woordovereenkomst).
    """
    blok = VINTED.split("function kiesBlad(")[1].split("\n  }")[0]
    for woord in ("other", "straight", "regular", "classic", "basic"):
        assert woord in blok, f"neutrale terugval mist '{woord}' in kiesBlad"
    assert re.search(r"/\^other\\b/i\.test\(namen\[i\]\)\)\s*return", blok), \
        "'Other …' hoort uit de puntentelling te blijven"


@pytest.mark.parametrize("bron", [MP, TWEEDEHANDS])
def test_sporttype_wordt_ingevuld(bron):
    assert "function mpSportType(item)" in bron
    assert 'selectDropdown("Type", mpSportType(item))' in bron
    # De exacte optienamen zoals Marktplaats ze toont.
    for optie in ("Hardlopen of Fietsen", "Voetbal", "Fitness of Aerobics", "Yoga",
                  "Wandelen of Outdoor", "Overige typen", "Algemeen"):
        assert optie in bron, f"optie '{optie}' ontbreekt"


def test_foutmelding_aan_de_gebruiker_is_engels():
    """Het dashboard is Engels; een half-Nederlandse melding leest als een storing."""
    blok = VINTED.split("if (gaps.length) {")[1].split("}")[0]
    assert "Vinted wouldn't accept these fields" in blok
    for nl in ("kon deze velden niet", "Vul ze zelf aan", "beschrijving", "kleur ("):
        assert nl not in blok, f"Nederlandse tekst in de gebruikersmelding: {nl}"


def test_dashboard_toont_publicatiefout_zonder_hover():
    app = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
    assert "function publishErrorBadge(item)" in app
    assert "function showPublishError(itemId)" in app
    assert "${errorBadge}" in app, "de foutbalk moet ook echt in de rij gerenderd worden"


def test_geen_hulpwaarden_na_de_hoofdstroom():
    """Een const die ná `await getJob()` staat, bestaat tijdens het invullen nog niet.

    Dat is geen theorie: het kostte eerst de kleurstap, daarna de categoriekeuze
    (V_KLEDING) en de prijscontrole (PRICE_ERR_RE), telkens met een harde fout
    midden in het publiceren. Alles wat de invulstappen gebruiken hoort dus bóven
    die regel te staan.
    """
    regels = VINTED.split("\n")
    na_job = next(i for i, r in enumerate(regels) if "const job = await getJob();" in r)
    # Alles tot en met de `try {` draait nog vóór er iets ingevuld wordt; wat
    # daarna komt, bestaat tijdens het invullen nog niet.
    start = next(i for i, r in enumerate(regels[na_job:], na_job) if r.rstrip() == "  try {")
    laat = [
        (i + 1, r.strip())
        for i, r in enumerate(regels[start:], start)
        if re.match(r"  (const|let) [A-Za-z_$][\w$]*\s*=", r)
    ]
    assert not laat, "hulpwaarden staan na de hoofdstroom en bestaan dan nog niet: " + str(laat[:5])


# ─────────────────────────────────────────────────────────────────────────────
# BROCANTE HOORT NIET BIJ DE KINDERKLEDING (30-08-2026, Amanda)
#
# "Bij het plaatsen op Vinted, wil hij alles in de categorie kinderkleding
# gooien :P". Haar voorraad is tweedehands brocante: lampen, beeldjes, servies,
# rozenkransen — 232 van haar 477 artikelen staan in de tak "antiek", 101 in
# "wonen". Bij zulke artikelen past geen enkele hint op een kledingblad.
#
# Wat er misging: de puntentelling geeft losse bonuspunten ("Other …" is +1,
# "sneakers" is +2) en `best()` neemt élk blad met een score boven nul. Eén
# bonuspunt was dus genoeg om gekozen te worden. Bij een artikel waar niets op
# past won daardoor het eerste blad dat toevallig "Other …" heette — en dat is
# in Vinted's suggestielijst geregeld "Other children's clothing".
#
# Deze proef draait de ECHTE puntentelling uit vinted.js in Node, met de oude
# versie (git HEAD) ernaast als tegenbewijs.

import json
import shutil
import subprocess
import textwrap

NODE = shutil.which("node")


def _snij(bron: str, vanaf: int) -> str:
    """Van `vanaf` tot de bijbehorende sluitaccolade, zonder je te laten foppen
    door strings, commentaar en regex-literals."""
    i = bron.index("{", vanaf)
    start, diepte, vorig = i, 0, ""
    while i < len(bron):
        c, twee = bron[i], bron[i:i + 2]
        if twee == "//":
            i = bron.index("\n", i)
            continue
        if twee == "/*":
            i = bron.index("*/", i) + 2
            continue
        if c in "\"'`":
            q, i = c, i + 1
            while i < len(bron):
                if bron[i] == "\\":
                    i += 2
                    continue
                if bron[i] == q:
                    break
                i += 1
            i, vorig = i + 1, q
            continue
        if c == "/" and (vorig == "" or vorig in "(,=:[!&|?{};+~*%^<>"):
            i += 1
            in_klasse = False
            while i < len(bron):
                if bron[i] == "\\":
                    i += 2
                    continue
                if bron[i] == "[":
                    in_klasse = True
                elif bron[i] == "]":
                    in_klasse = False
                elif bron[i] == "/" and not in_klasse:
                    break
                elif bron[i] == "\n":
                    break
                i += 1
            i, vorig = i + 1, "/"
            continue
        if c == "{":
            diepte += 1
        elif c == "}":
            diepte -= 1
            if diepte == 0:
                return bron[start:i + 1]
        if not c.isspace():
            vorig = c
        i += 1
    raise AssertionError("geen sluitende accolade")


def _kiezer(bron: str) -> str:
    """De puntentelling + de keuze, letterlijk uit vinted.js gesneden."""
    stukken = []
    for anker in ("const NICHE_SHOE = [", "const score = (c) => ", "const best = (choices) => "):
        i = bron.index(anker)
        if anker.endswith("[["[:1]):  # NICHE_SHOE is een lijst, geen blok
            stukken.append(bron[i:bron.index("];", i) + 2])
        else:
            stukken.append(bron[i:bron.index("{", i)] + _snij(bron, i) + ";")
    # itemText/isNietKleding/isClothingCat/hintText/sportNamed staan tussen
    # NICHE_SHOE en score; die nemen we in één keer mee.
    a = bron.index("const itemText = ")
    b = bron.index("const score = (c) => ")
    return stukken[0] + "\n" + bron[a:b] + "\n" + stukken[1] + "\n" + stukken[2]


def _kies(bron_js: str, cat: str, gender: str, hints: list[str],
          titel: str, rijen: list[str]):
    """Draai de echte kiezer op een lijst kandidaatregels; geef de winnaar terug."""
    driver = textwrap.dedent(f"""
        const item = {{ title: {json.dumps(titel)}, description: "" }};
        const cat = {json.dumps(cat)};
        const gender = {json.dumps(gender)};
        const hints = {json.dumps(hints)};
        const wantMen = gender === "heren" || gender === "men";
        const wantWomen = gender === "dames" || gender === "women";
        console.warn = () => {{}};
        {bron_js}
        const keuzes = {json.dumps(rijen)}.map((text) => ({{ text, row: null, radio: null }}));
        const winnaar = best(keuzes);
        console.log(JSON.stringify(winnaar ? winnaar.text : null));
    """)
    r = subprocess.run([NODE, "-e", driver], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip())


# Vastgezet op de laatste versie VÓÓR de reparatie van 30-08-2026. Zou hier
# "HEAD" staan, dan vergelijkt de proef zichzelf zodra dit gecommit is en wordt
# het tegenbewijs stilletjes betekenisloos.
VOOR_DE_REPARATIE = "2561032"


def _oude_vinted() -> str:
    return subprocess.run(
        ["git", "show", f"{VOOR_DE_REPARATIE}:extension/content/vinted.js"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout


# Precies zoals Vinted ze rendert: bladnaam | kruimelpad, in kleine letters
# (zie rowText in vinted.js).
SUGGESTIES_BROCANTE = [
    "other children's clothing | kids > clothing",
    "girls' clothing | kids > clothing",
    "soft toys | kids > toys",
    "home decor | home > home decor",
]


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
@pytest.mark.parametrize("cat,gender,hints,titel", [
    ("antiek lampen", "antiek", ["antique lamp", "lighting"], "Vintage paarse wandlamp met 5 lampjes"),
    ("kunst beelden en houtsnijwerken", "antiek", ["sculpture", "figurine"], "Verzilverd beertje beeldje"),
    ("antiek religie", "antiek", ["religious", "antiques"], "Mini vintage rozenkrans."),
    ("wonen tafellampen", "wonen", ["table lamp", "lighting"], "Spiraalvormige plafondlamp metaal"),
])
def test_brocante_belandt_nooit_meer_bij_de_kinderkleding(cat, gender, hints, titel):
    nu = _kies(_kiezer(VINTED), cat, gender, hints, titel, SUGGESTIES_BROCANTE)
    assert nu is None or "clothing" not in nu, \
        f"{titel!r} kwam bij {nu!r} terecht — dat is een kledingblad"


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_de_oude_versie_koos_wel_kinderkleding():
    """Tegenbewijs: zonder deze reparatie meet de test hierboven niets."""
    oud = _kies(_kiezer(_oude_vinted()), "antiek lampen", "antiek",
                ["antique lamp", "lighting"], "Vintage paarse wandlamp met 5 lampjes",
                SUGGESTIES_BROCANTE)
    assert oud is not None and "clothing" in oud, \
        ("de oude versie koos hier geen kledingblad meer — dan is de proef zijn "
         f"tegenbewijs kwijt (koos: {oud!r})")


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_kleding_wordt_nog_gewoon_gekozen():
    """De rem mag niet ook het gewone werk stilzetten."""
    rijen = [
        "jumpers & sweaters | men > clothing",
        "other clothing | men > clothing",
        "dresses | women > clothing",
    ]
    keuze = _kies(_kiezer(VINTED), "heren truien", "heren",
                  ["jumpers & sweaters"], "Grijze Ralph Lauren trui", rijen)
    assert keuze == "jumpers & sweaters | men > clothing", keuze


@pytest.mark.skipif(NODE is None, reason="node is niet geïnstalleerd")
def test_een_blad_dat_nergens_op_slaat_wint_niet_meer_op_een_bonuspunt():
    """"Other …" en "sneakers" zijn tiebreaks, geen toegangsbewijs."""
    rijen = ["other jeans | women > clothing > jeans", "sneakers | women > shoes"]
    keuze = _kies(_kiezer(VINTED), "muziek gitaren akoestisch", "muziek",
                  ["acoustic guitar", "guitars"], "Yamaha akoestische gitaar", rijen)
    assert keuze is None, f"koos {keuze!r} voor een gitaar"
