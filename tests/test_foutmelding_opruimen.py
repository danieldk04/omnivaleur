"""Een rode balk moet weg kunnen.

WAAROM DIT ER IS (03-09-2026, Egbert Brouwer / papas-plectrums)

Zijn wachtrij voor 2dehands werd terecht teruggenomen: 279 opdrachten van elk
drie en een halve minuut zijn zestien uur waarin hij verder niets kan. Maar elke
teruggenomen opdracht liet een rode balk achter op de artikelrij, en zo'n balk
verdween alleen door alsnog met succes te publiceren — precies wat er niet
lukte. Hij keek dus tegen zes bladzijden rood aan zonder één knop die ergens
heen leidde: "Ik kom niet verder."

Een advertentie die nooit is aangemaakt is geen mislukte advertentie maar een
niet-geplaatste. Dus verdwijnt zo'n rij hier echt, en gaat het artikel gewoon
terug naar "nog plaatsen".
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters = {}, {}
        self.op, self.velden = None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self

    def _raak(self):
        bron = self.db.tabellen[self.tabel]
        return [r for r in bron
                if all(r.get(k) == v for k, v in self.filters.items())
                and all(r.get(k) in v for k, v in self.in_filters.items())]

    def execute(self):
        rijen = self._raak()
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        elif self.op == "delete":
            self.db.tabellen[self.tabel] = [r for r in self.db.tabellen[self.tabel] if r not in rijen]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, **tabellen):
        self.tabellen = tabellen

    def table(self, naam): return _Q(self, naam)


def _opzet(monkeypatch, listings):
    db = _DB(
        items=[{"id": f"i{i}", "user_id": "u"} for i in range(5)] + [{"id": "vreemd", "user_id": "ander"}],
        listings=listings,
    )
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "fetch_all", lambda maak, *a, **k: maak().execute().data)
    return db


def _mislukt(n, platform="2dehands", met_nummer=False):
    return [{"id": f"l{platform[:2]}{i}", "item_id": f"i{i}", "platform": platform, "status": "error",
             "error_message": "form never opened",
             "platform_listing_id": (f"m{i}" if met_nummer else None)} for i in range(n)]


def test_een_nooit_geplaatste_advertentie_verdwijnt_echt(monkeypatch):
    db = _opzet(monkeypatch, _mislukt(3))
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 3 and uit["removed"] == 3
    # Geen rij meer, dus geen rode balk, dus het artikel staat weer op "nog plaatsen".
    assert db.tabellen["listings"] == []


def test_een_advertentie_met_nummer_blijft_bestaan(monkeypatch):
    """Zo'n nummer geeft het platform alleen terug als de advertentie er echt
    kwam. Die rij weggooien maakt de link kwijt die auto-delist later nodig heeft."""
    db = _opzet(monkeypatch, _mislukt(2, met_nummer=True))
    uit = api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    assert uit["cleared"] == 2 and uit["removed"] == 0
    assert len(db.tabellen["listings"]) == 2
    assert all(r["status"] == "active" and r["error_message"] is None
               for r in db.tabellen["listings"])


def test_alleen_het_gevraagde_kanaal(monkeypatch):
    """Marktplaats werkt bij hem wél. Daar mag niets van verdwijnen."""
    db = _opzet(monkeypatch, _mislukt(2) + _mislukt(2, platform="marktplaats"))
    api.clear_listing_errors({"platform": "2dehands"}, user_id="u")
    over = db.tabellen["listings"]
    assert len(over) == 2 and all(r["platform"] == "marktplaats" for r in over)


def test_een_enkel_artikel_laat_de_rest_staan(monkeypatch):
    db = _opzet(monkeypatch, _mislukt(3))
    uit = api.clear_listing_errors({"platform": "2dehands", "item_id": "i1"}, user_id="u")
    assert uit["cleared"] == 1
    assert sorted(r["item_id"] for r in db.tabellen["listings"]) == ["i0", "i2"]


def test_andermans_artikel_kan_niet(monkeypatch):
    _opzet(monkeypatch, _mislukt(1))
    with pytest.raises(api.HTTPException) as e:
        api.clear_listing_errors({"platform": "2dehands", "item_id": "vreemd"}, user_id="u")
    assert e.value.status_code == 404


def test_zonder_kanaal_doen_we_niets(monkeypatch):
    _opzet(monkeypatch, _mislukt(1))
    with pytest.raises(api.HTTPException) as e:
        api.clear_listing_errors({}, user_id="u")
    assert e.value.status_code == 400


def test_niets_te_wissen_is_geen_fout(monkeypatch):
    _opzet(monkeypatch, [])
    assert api.clear_listing_errors({"platform": "2dehands"}, user_id="u")["cleared"] == 0
