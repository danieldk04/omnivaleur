"""Boeken, speelgoed, fietsen, sportartikelen, witgoed, klussen en computers.

WAAROM DIT ER IS (24-09-2026, Daniel)
"Die eigen indeling heel graag, maar volledig en juist, niet half." Een tak raakt
tien plekken: dashboard, import, extensie (Marktplaats, Vinted, Facebook), eBay,
Shopify, de Vinted-regels op de server, de Vinted-voorkeuren en de leadgen. Een
plek die achterloopt maakt een artikel stil verkeerd, en dat is precies wat hier
eerder misging (zie de uitleg bij NON_CLOTHING_PREFIXES in frontend/app.html).

Twee dingen zijn live nagelopen en hier vastgelegd als meetpunt:
  * elk Marktplaats-adres (cat1, bucketId, cat3) in het plaatsformulier opgevraagd
    en teruggekregen als precies die rubriek, zonder betaalde plaatsing;
  * elk Vinted-pad stap voor stap in Vinteds eigen categorieboom gevonden.
Deze proef zorgt dat de code niet ongemerkt van die metingen wegdrijft.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NIEUW = ("boeken", "speelgoed", "fietsen", "sportartikelen", "witgoed", "klussen", "computers")


def _lees(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _fixture(naam):
    return json.loads((ROOT / "tests" / "fixtures" / naam).read_text(encoding="utf-8"))


def _mp_categorieen():
    src = _lees("extension/background.js")
    blok = src[src.index("const MP_CATEGORIES = {"):]
    blok = blok[:blok.index("\n};")]
    uit = {}
    for m in re.finditer(r'^\s*"([^"]+)":\s*\{\s*cat1:\s*(\d+),\s*cat3:\s*(\d+)(?:,\s*bucketId:\s*(\d+))?', blok, re.M):
        uit[m.group(1)] = (int(m.group(2)), int(m.group(3)), int(m.group(4)) if m.group(4) else None)
    return uit


def _v_pad():
    src = _lees("extension/content/vinted.js")
    blok = src[src.index("  const V_PAD = {") + len("  const V_PAD = "):]
    blok = blok[:blok.index("\n  };") + len("\n  }")]
    return json.loads(re.sub(r",\s*\}$", "}", blok.strip()))


def _dashboard():
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_category_taxonomy import _frontend_categories
    return _frontend_categories()


def test_marktplaats_nummers_zijn_de_nagelopen_nummers():
    verwacht = _fixture("marktplaats_nieuwe_takken_24-09-2026.json")["rubrieken"]
    mp = _mp_categorieen()
    for sleutel, v in verwacht.items():
        assert sleutel in mp, f"{sleutel} ontbreekt in MP_CATEGORIES"
        assert mp[sleutel] == (v["cat1"], v["cat3"], v["bucketId"]), (sleutel, mp[sleutel], v)


def test_elke_nieuwe_dashboardrubriek_is_nagelopen():
    verwacht = _fixture("marktplaats_nieuwe_takken_24-09-2026.json")["rubrieken"]
    cats = _dashboard()
    for tak in NIEUW:
        assert tak in cats, tak
        for sleutel in cats[tak]:
            assert sleutel in verwacht, f"{sleutel} staat in het dashboard maar is niet nagelopen"


def test_betaalde_rubrieken_zitten_er_niet_in():
    """Zes klusrubrieken zijn op Marktplaats altijd betaald (isPaidAd)."""
    alles = {k for keys in _dashboard().values() for k in keys}
    for betaald in ("klussen bouwliften", "klussen zonnepanelen", "klussen aggregaten",
                    "klussen palletwagens en pompwagens", "klussen bouwketen en schaftketen",
                    "klussen containers"):
        assert betaald not in alles


def test_vinted_paden_bestaan_in_vinteds_eigen_boom():
    nagelopen = set(_fixture("vinted_paden_24-09-2026.json")["paden"])
    for sleutel, pad in _v_pad().items():
        if pad is not None:
            assert ">".join(pad) in nagelopen, f"{sleutel}: {pad} is niet nagelopen"


def test_elke_nieuwe_rubriek_heeft_een_vinted_besluit():
    """Een pad, of uitdrukkelijk null (Vinted kent dit niet). Nooit niets."""
    v = _v_pad()
    cats = _dashboard()
    for tak in NIEUW:
        for sleutel in cats[tak]:
            assert sleutel in v, f"{sleutel} heeft geen Vinted-pad en geen null"


def test_niet_op_vinted_is_overal_dezelfde_lijst():
    from backend.services.platformregels import NIET_OP_VINTED
    uit_vpad = {k for k, p in _v_pad().items() if p is None}
    src = _lees("frontend/app.html")
    fe = set(json.loads(re.search(r"const NIET_OP_VINTED = new Set\((\[.*?\])\);", src, re.S).group(1)))
    assert set(NIET_OP_VINTED) == uit_vpad == fe


def test_server_houdt_vinted_tegen_bij_een_rubriek_die_vinted_niet_kent():
    from backend.services import platformregels as pr
    oordeel, reden = pr.beoordeel({"title": "Wandtegels 20x20", "category": "klussen tegels"}, "vinted")
    assert oordeel == pr.BLOKKADE and "Vinted" in reden
    assert pr.beoordeel({"title": "Wandtegels", "category": "klussen tegels"}, "marktplaats")[0] == pr.OK
    assert pr.beoordeel({"title": "Suske en Wiske 12", "category": "boeken stripboeken"}, "vinted")[0] == pr.OK


def test_de_takken_staan_op_elke_plek():
    from backend.services.crosslist import _NON_CLOTHING_PREFIXES, _is_non_clothing
    from backend.services.platformregels import GROEPEN
    from backend.services.instellingen import VINTED_GROEPEN_GELDIG
    from backend.api.imports import _TAXONOMY
    app = _lees("frontend/app.html")
    vinted = _lees("extension/content/vinted.js")
    facebook = _lees("extension/content/facebook.js")
    leadgen = _lees("scripts/leadgen_marktplaats.py")
    for tak in NIEUW:
        assert f"{tak} " in _NON_CLOTHING_PREFIXES, tak
        assert _is_non_clothing({"category": f"{tak} iets"}), tak
        assert tak in GROEPEN and tak in VINTED_GROEPEN_GELDIG and tak in _TAXONOMY, tak
        assert f"'{tak} ': '{tak}'" in app, f"NON_CLOTHING_PREFIXES mist {tak}"
        assert f'<option value="{tak}">' in app, f"Item type mist {tak}"
        assert f"'{tak}'" in app.split("const VINTED_GROEPEN = ")[1].split(";")[0], tak
        assert f"|{tak}" in vinted.split("const NIET_KLEDING_TAK = ")[1].split(";")[0], tak
        assert f"      {tak}:" in facebook, f"Facebook kent {tak} niet"
        assert f'"{tak}":' in leadgen.split("GROEP_NAMEN = {")[1].split("}")[0], tak


def test_sport_bh_blijft_kleding():
    """De tak heet sportartikelen, niet sport: "sport bh" en "sport tops" zijn
    damesrubrieken en mochten nooit als sportartikel gezien worden."""
    from backend.services.crosslist import _is_non_clothing
    from backend.services.platformregels import _groep
    assert not _is_non_clothing({"category": "sport bh"})
    assert _groep({"category": "sport bh"}) == ""


def test_shopify_type_van_accessoires_is_geen_videogame():
    from backend.platforms.shopify_importer import _english_type_from_category
    assert _english_type_from_category("games accessoires xbox") == "Gaming Accessory"
    assert _english_type_from_category("games controllers playstation") == "Controller"
    assert _english_type_from_category("games playstation 5") == "Video Game"
    assert _english_type_from_category("boeken stripboeken") == "Comic Book"


def test_ebay_blijft_binnen_de_eigen_tak():
    from backend.platforms.ebay import _tak_voor_rubriek
    assert _tak_voor_rubriek("boeken kookboeken") == ("267",)
    assert _tak_voor_rubriek("klussen boormachines") == ("3187", "118570", "29518")
    assert _tak_voor_rubriek("heren jeans") is None
