"""De rubriek van een hele selectie in één keer zetten.

WAAROM DIT ER IS (22-09-2026, Toon van De Juiste Toon). Zonder rubriek weigeren
Marktplaats en 2dehands een artikel, en een import levert er lang niet altijd
een mee. Toon verkoopt vachten, kleden en tafelkleden en zette die tot nu toe
artikel voor artikel goed. Zijn vraag, woordelijk: *"Kan je bij mijn account een
vaste rubriek maken voor alleen home bv."*

Wat deze proef vastlegt:

1. Een onbekende rubriek wordt geweigerd. De extensie vertaalt een rubriek naar
   een vaste Marktplaats-categorie; staat hij daar niet in, dan belandt het
   artikel stil bij damesjeans. Eén verzoek uit de browser mag dus nooit een
   verzonnen rubriek over honderden artikelen zetten.
2. De doelgroep gaat mee. Een kledingrubriek zónder doelgroep is op Marktplaats
   even onpubliceerbaar als een lege rubriek, en een schapenvacht met "heren"
   erop is gewoon fout.
3. Er wordt niets anders aangeraakt. Maat, kleur en materiaal blijven van de
   verkoper.
4. De id's uit de browser gelden nooit als bewijs van eigenaarschap: elke
   schrijfactie blijft op user_id filteren.
"""
import asyncio
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import items as items_api  # noqa: E402


# ── Een nagebootste Supabase ────────────────────────────────────────────────
class _Query:
    def __init__(self, tabel, log):
        self.tabel, self.log = tabel, log
        self.filters, self.velden = {}, None

    def select(self, *_a, **_kw):
        return self

    def update(self, velden):
        self.velden = velden
        return self

    def eq(self, kolom, waarde):
        self.filters[kolom] = waarde
        return self

    def in_(self, kolom, waarden):
        self.filters[kolom] = list(waarden)
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        if self.velden is None:                       # een leesvraag
            rijen = [r for r in self.tabel if r["user_id"] == self.filters.get("user_id")]
            return type("R", (), {"data": [dict(r) for r in rijen]})()
        ids = set(self.filters.get("id") or [])
        geraakt = []
        for rij in self.tabel:
            if rij["id"] in ids and rij["user_id"] == self.filters.get("user_id"):
                rij.update(self.velden)
                geraakt.append(dict(rij))
        self.log.append({"velden": dict(self.velden), "filters": dict(self.filters)})
        return type("R", (), {"data": geraakt})()


class _Db:
    def __init__(self, rijen):
        self.rijen, self.log = rijen, []

    def table(self, _naam):
        return _Query(self.rijen, self.log)


TOON = "96e30080-0000-4000-8000-000000000001"
IEMAND_ANDERS = "11111111-0000-4000-8000-000000000002"


def _voorraad():
    return [
        {"id": "a1", "user_id": TOON, "title": "Schapenvachtjes 2 stuks",
         "category": "", "gender": "heren", "size": "", "color": "wit", "material": None},
        {"id": "a2", "user_id": TOON, "title": "2 stuks Originele lamsvachten",
         "category": "", "gender": "dames", "size": "", "color": "wit", "material": None},
        {"id": "b1", "user_id": TOON, "title": "Originele Lederhosen maat 3XL",
         "category": "", "gender": "", "size": "XXXL", "color": "bruin", "material": "leer"},
        {"id": "x1", "user_id": IEMAND_ANDERS, "title": "Niet van Toon",
         "category": "", "gender": "", "size": "", "color": "", "material": None},
    ]


@pytest.fixture
def db(monkeypatch):
    d = _Db(_voorraad())
    monkeypatch.setattr(items_api, "get_db", lambda: d)
    monkeypatch.setattr(items_api, "execute_with_retry", lambda q, **kw: q.execute())
    monkeypatch.setattr(items_api, "fetch_all", lambda maak: maak().execute().data)
    return d


# De hele testmap draait zonder pytest-asyncio; asyncio.run is hier de afspraak.
def _roep(body, user_id=TOON):
    return asyncio.run(items_api.bulk_category(body, user_id=user_id))


def _rij(db, rij_id):
    return next(r for r in db.rijen if r["id"] == rij_id)


# ── 1. Wat Toon vroeg: vier vachten in één keer naar Home ───────────────────
def test_home_rubriek_over_een_selectie(db):
    uit = _roep({"category": "wonen vachten", "ids": ["a1", "a2"]})
    assert uit["updated"] == 2
    for rij_id in ("a1", "a2"):
        assert _rij(db, rij_id)["category"] == "wonen vachten"


def test_een_vacht_houdt_geen_doelgroep_over(db):
    _roep({"category": "wonen vachten", "ids": ["a1", "a2"]})
    assert _rij(db, "a1")["gender"] == ""
    assert _rij(db, "a2")["gender"] == ""


# ── 2. Zijn lederhosen: kleding, dus mét doelgroep ─────────────────────────
def test_een_kledingrubriek_vult_de_doelgroep_in(db):
    uit = _roep({"category": "heren verkleedkleding", "ids": ["b1"]})
    assert uit["gender"] == "heren"
    assert _rij(db, "b1")["gender"] == "heren"
    assert _rij(db, "b1")["category"] == "heren verkleedkleding"


def test_maat_kleur_en_materiaal_blijven_staan(db):
    _roep({"category": "heren verkleedkleding", "ids": ["b1"]})
    rij = _rij(db, "b1")
    assert rij["size"] == "XXXL"
    assert rij["color"] == "bruin"
    assert rij["material"] == "leer"


# ── 3. Een verzonnen rubriek komt er niet in ───────────────────────────────
@pytest.mark.parametrize("rubriek", ["", "   ", "home", "Wonen Vachten", "kleding algemeen"])
def test_onbekende_rubriek_wordt_geweigerd(db, rubriek):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as fout:
        _roep({"category": rubriek, "ids": ["a1"]})
    assert fout.value.status_code == 400
    assert _rij(db, "a1")["category"] == ""


def test_zonder_selectie_gebeurt_er_niets(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as fout:
        _roep({"category": "wonen vachten"})
    assert fout.value.status_code == 400
    assert not db.log


# ── 4. Id's uit de browser zijn geen eigendomsbewijs ───────────────────────
def test_een_artikel_van_iemand_anders_blijft_onaangeroerd(db):
    uit = _roep({"category": "wonen vachten", "ids": ["a1", "x1"]})
    assert uit["updated"] == 1
    assert _rij(db, "x1")["category"] == ""
    for schrijfactie in db.log:
        assert schrijfactie["filters"].get("user_id") == TOON


def test_all_items_blijft_binnen_het_eigen_account(db):
    uit = _roep({"category": "wonen tapijten en kleden", "all_items": True})
    assert uit["updated"] == 3
    assert _rij(db, "x1")["category"] == ""


# ── 5. De lijst waar de server op controleert is de lijst van het dashboard ─
# Zonder deze proef kan de keuzelijst in app.html uitbreiden terwijl de server
# de nieuwe rubriek weigert — dan werkt de knop voor precies die rubriek niet.
def test_de_serverlijst_is_exact_de_dashboardlijst():
    from backend.platforms.ebay import _EBAY_CATEGORY_HINTS

    app = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    start = app.index("const CATEGORIES = {")
    einde = app.index("\n};", start)
    dashboard = set(re.findall(r'\["([^"]+)"\s*,\s*"[^"]*"\]', app[start:einde]))

    assert dashboard, "geen rubrieken gevonden in frontend/app.html"
    assert dashboard == set(_EBAY_CATEGORY_HINTS), (
        "de rubrieken van het dashboard en die van de server lopen uiteen: "
        f"alleen in het dashboard {sorted(dashboard - set(_EBAY_CATEGORY_HINTS))}, "
        f"alleen op de server {sorted(set(_EBAY_CATEGORY_HINTS) - dashboard)}"
    )


def test_alleen_kledingtakken_houden_een_doelgroep():
    assert items_api._doelgroep_bij_rubriek("heren verkleedkleding") == "heren"
    assert items_api._doelgroep_bij_rubriek("verkleedkleding") == "dames"
    assert items_api._doelgroep_bij_rubriek("kinderen schoenen") == "kinderen"
    assert items_api._doelgroep_bij_rubriek("unisex jassen") == "unisex"
    for niet_kleding in ("wonen vachten", "antiek klokken", "muziek orgels",
                         "sieraden ringen", "games pc", "audio luidsprekers"):
        assert items_api._doelgroep_bij_rubriek(niet_kleding) == "", niet_kleding
