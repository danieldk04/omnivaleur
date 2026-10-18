"""Jongen of meisje uit de labels van de winkel (18-10-2026, Janneke 31d28378).

Haar titels noemen nooit een geslacht, haar Shopify-labels wel ("meisje",
"jongen", "unisex"). Wij lazen die labels niet: babykleding en peuterkleding
stonden geslachtsloos (Vinted koos dan Boys clothing), en de jongens- en
meisjesrubrieken waren een gok (140 van 474 verkeerd om). Kinderschoenen maat
35 tot 41 stonden als damesschoen.

De extensiedelen draaien de echte code uit background.js en vinted.js, nu en
van vóór deze reparatie (735ee620).
"""
import json
import subprocess
from pathlib import Path

import pytest

from backend.api import imports as I
from backend.api import jobs as jobs_api
from backend.services.shopify_scan import naar_scanregel

ROOT = Path(__file__).resolve().parents[1]
OUD = "735ee620"


# ── Het label lezen ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("labels,verwacht", [
    ("meisje, najaar, winter, Noppies", "meisje"),
    ("Out of stock, jongen, maat 116", "jongen"),
    ("jongen, meisje", None),             # beide: geen keuze
    ("meisje, unisex", None),             # unisex: geen keuze
    ("Sissy-Boy, maat 116, meisje 122", None),   # alleen hele labels tellen
    ("", None),
    (None, None),
    (["Meisjes", "zomer"], "meisje"),
])
def test_geslacht_uit_labels(labels, verwacht):
    assert I.geslacht_uit_labels(labels) == verwacht


def test_producttype_telt_als_label():
    assert I.geslacht_uit_labels("zomer", "Jongens") == "jongen"


# ── De rubriek met geslacht ──────────────────────────────────────────────────
# Echte titels van Janneke, met haar label.
@pytest.mark.parametrize("titel,label,verwacht", [
    ("Longsleeve Noppies maat 56", "jongen", "babykleding jongens"),
    ("Babypakje / romper", "meisje", "babykleding meisjes"),
    ("Trui maat 92", "meisje", "peuterkleding meisjes"),
    ("Broek maat 98/104", "jongen", "peuterkleding jongens"),
    ("Tussenjas Name it maat 128", "meisje", "meisjes kleding"),
    ("Jurk Your Wishes maat 116", "jongen", "jongens kleding"),   # label wint van "jurk"
    ("Schoenen Hip schoenmaat 37", "jongen", "kinderen schoenen"),   # was een damesschoen
    ("Set Lyle & Scott met 134-140", "jongen", "jongens kleding"),
])
def test_label_geeft_de_kinderrubriek_met_geslacht(titel, label, verwacht):
    uit = I._infer_attributes(titel, "", label)
    assert (uit.get("gender"), uit.get("category")) == ("kinderen", verwacht)


def test_zonder_label_blijft_alles_zoals_het_was():
    assert I._infer_attributes("Longsleeve Noppies maat 56", "").get("category") == "babykleding"
    assert I._infer_attributes("Schoenen Hip schoenmaat 37", "").get("gender") is None


def test_tekst_die_het_andere_geslacht_noemt_wint_van_het_label():
    uit = I._infer_attributes("Jongens jas maat 128", "", "meisje")
    assert uit["category"] == "jongens kleding"


def test_omschrijving_en_merknaam_houden_het_label_niet_tegen():
    """Echte producten van Janneke met label meisje."""
    uit = I._infer_attributes("Jas Babyface maat 110*", "Een meisjesjas, maar kan ook heel goed voor jongens!", "meisje")
    assert uit["category"] == "meisjes kleding"
    assert I._infer_attributes("Trui Sissy-Boy maat 122-128", "", "meisje")["category"] == "meisjes kleding"


@pytest.mark.parametrize("titel", ["Sokken Ewers schoenmaat 35-36, schoenmaat 37-38",
                                   "Huissokken Ewers schoenmaat 23-24",
                                   "Chelseaboot Bergstein schoenmaat 27"])
def test_sokken_en_laarsjes_worden_geen_meisjeskleding(titel):
    """Echte titels van Janneke: zonder dit werden ze 'meisjes kleding'; nu beslist de import."""
    uit = I._infer_attributes(titel, "", "meisje")
    assert uit.get("category") not in ("meisjes kleding", "jongens kleding")


def test_label_maakt_geen_kinderkleding_van_iets_wat_geen_kleding_is():
    assert I._infer_attributes("Playmobil brandweerkazerne", "", "jongen").get("gender") is None


def test_label_maakt_van_een_volwassen_woord_geen_kind():
    assert I._infer_attributes("Jas heren maat L", "", "jongen").get("gender") == "heren"


def test_rubriekvraag_biedt_het_geslacht_bij_baby_niet_aan():
    """Het model zou bij baby en peuter jongen of meisje raden; dat komt alleen uit het label."""
    vraag = I._kledingprompt("Longsleeve maat 56", "", None)
    assert "babykleding jongens" not in vraag and "peuterkleding meisjes" not in vraag
    assert "babykleding" in vraag


# ── Van Shopify-product tot artikel ──────────────────────────────────────────
def _product(tags, titel="Longsleeve Noppies maat 56"):
    return {"id": 16253241459013, "title": titel, "body_html": "<p>Mooi</p>",
            "vendor": "Kinderwinkel", "handle": "x", "images": [],
            "variants": [{"price": "12.50", "sku": "A1"}], "options": [],
            "tags": tags, "product_type": "", "status": "active"}


def test_scanregel_draagt_de_rubriek_met_geslacht():
    rij = naar_scanregel(_product("meisje, winter"), "x.myshopify.com", "Kinderwinkel")
    assert (rij["gender"], rij["category"]) == ("kinderen", "babykleding meisjes")


def test_scanregel_zonder_eenduidig_label_laat_het_aan_de_import():
    for tags in ("jongen, meisje", "unisex", "winter"):
        rij = naar_scanregel(_product(tags), "x.myshopify.com", "Kinderwinkel")
        assert rij["gender"] is None and rij["category"] is None


def test_rubriek_uit_het_label_wint_van_de_rubriekvraag():
    rij = naar_scanregel(_product("jongen", "Schoenen Hip schoenmaat 37"),
                         "x.myshopify.com", "Kinderwinkel")
    model = {"gender": "dames", "category": "schoenen dames"}   # wat het model bij haar koos
    uit = I._item_data_from_candidate(rij, None, inferred=model)
    assert (uit["gender"], uit["category"]) == ("kinderen", "kinderen schoenen")


# ── De uitgifte: een oude extensie krijgt de rubriek zonder geslacht ─────────
def _opdracht(cat):
    return {"id": "j1", "platform": "vinted", "action": "create",
            "payload": {"category": cat, "title": "Longsleeve"}}


def test_oude_kopie_krijgt_babykleding_zonder_geslacht():
    jobs = [_opdracht("babykleding jongens"), _opdracht("peuterkleding meisjes"),
            _opdracht("meisjes kleding")]
    assert jobs_api._rubriek_voor_de_kopie(jobs, (1, 0, 396)) == 2
    assert [j["payload"]["category"] for j in jobs] == [
        "babykleding", "peuterkleding", "meisjes kleding"]


def test_onbekende_versie_krijgt_ook_de_terugval():
    jobs = [_opdracht("babykleding meisjes")]
    jobs_api._rubriek_voor_de_kopie(jobs, None)
    assert jobs[0]["payload"]["category"] == "babykleding"


def test_nieuwe_kopie_krijgt_het_geslacht():
    jobs = [_opdracht("babykleding meisjes")]
    assert jobs_api._rubriek_voor_de_kopie(jobs, (1, 0, 397)) == 0
    assert jobs[0]["payload"]["category"] == "babykleding meisjes"


def test_terugval_geldt_voor_precies_de_nieuwe_rubrieken():
    assert set(jobs_api._KIND_GESLACHT_TERUGVAL) == I._ALLEEN_UIT_LABEL


def test_extensieversie_is_minstens_de_grens():
    versie = json.loads((ROOT / "extension/manifest.json").read_text())["version"]
    assert tuple(map(int, versie.split("."))) >= jobs_api.MINIMALE_KIND_GESLACHT_VERSIE


# ── De extensie zelf: Marktplaats en Vinted ──────────────────────────────────
def _bron(rel, commit=None):
    if commit:
        return subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout
    return (ROOT / rel).read_text(encoding="utf-8")


_MP_SCRIPT = r"""
const bron = require("fs").readFileSync(0, "utf8");
const stuk = (begin) => {
  const s = bron.indexOf(begin);
  if (s < 0) throw new Error(begin + " niet gevonden");
  return bron.slice(s, bron.indexOf("\n}", s) + 2);
};
const code = [
  "const importScripts = () => {};",
  bron.slice(0, bron.indexOf("class CategoryUnresolvedError")),
  stuk("class CategoryUnresolvedError"), "let _mpOpNummer = null;",
  stuk("function mpCategorieOpNummer("), stuk("function mpKidsSizeCat3("),
  stuk("function getMpSyiUrl("),
].join("\n");
const f = new Function(code + "\nreturn getMpSyiUrl;")();
const uit = JSON.parse(process.argv[1]).map((pl) => { try { return f("marktplaats", pl); } catch (e) { return "FOUT: " + e.message; } });
console.log(JSON.stringify(uit));
"""


def _mp(bron, payloads):
    return json.loads(subprocess.run(["node", "-e", _MP_SCRIPT, json.dumps(payloads)], input=bron,
                                     capture_output=True, text=True, check=True).stdout)


_MP_PAYLOADS = [{"category": "babykleding", "size": "56"},
                {"category": "babykleding jongens", "size": "56"},
                {"category": "peuterkleding meisjes", "size": "98"}]


def test_marktplaats_kent_de_rubrieken_met_geslacht():
    uit = _mp(_bron("extension/background.js"), _MP_PAYLOADS)
    assert uit[1] == uit[0]   # zelfde babyrubriek en maat, "Bestemd voor" doet het geslacht
    assert uit[2].startswith("https://www.marktplaats.nl/plaats/565/") and "bucketId=153" in uit[2]


def test_voor_de_reparatie_kende_marktplaats_ze_niet():
    uit = _mp(_bron("extension/background.js", OUD), _MP_PAYLOADS)
    assert uit[1].startswith("FOUT") and uit[2].startswith("FOUT")


_VINTED_SCRIPT = r"""
const bron = require("fs").readFileSync(0, "utf8");
const regel = (begin) => { const s = bron.indexOf(begin); return bron.slice(s, bron.indexOf("\n", s)); };
const fn = (begin) => { const s = bron.indexOf(begin); return bron.slice(s, bron.indexOf("\n  }\n", s) + 4); };
const f = new Function(regel("const KIND_KLEDING") + "\n" + fn("function kinderPad(") + "\nreturn kinderPad;")();
console.log(JSON.stringify(JSON.parse(process.argv[1]).map((it) => f(it.category, it))));
"""


def _vinted(bron, items):
    return json.loads(subprocess.run(["node", "-e", _VINTED_SCRIPT, json.dumps(items)], input=bron,
                                     capture_output=True, text=True, check=True).stdout)


_VINTED_ITEMS = [{"category": "babykleding meisjes", "title": "Longsleeve Noppies maat 56"},
                 {"category": "peuterkleding jongens", "title": "Trui maat 92"},
                 {"category": "babykleding", "title": "Longsleeve Noppies maat 56"}]


def test_vinted_kiest_girls_of_boys_uit_de_rubriek():
    assert _vinted(_bron("extension/content/vinted.js"), _VINTED_ITEMS) == [
        ["Kids", "Girls clothing"], ["Kids", "Boys clothing"], ["Kids"]]


def test_voor_de_reparatie_kende_vinted_ze_niet():
    uit = _vinted(_bron("extension/content/vinted.js", OUD), _VINTED_ITEMS)
    assert uit[:2] == [None, None]
