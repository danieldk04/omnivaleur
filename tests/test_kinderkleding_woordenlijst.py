"""Janneke (31d28378), 08-10-2026: 1.755 van haar 1.917 artikelen zonder rubriek.

Ze verkoopt kinder- en babykleding met titels als "Babypakje / romper",
"Longsleeve Noppies maat 44/50" en "Schoenen Jopper schoenmaat 31", zonder
"kids", "jongens" of "meisjes" erin. Het model dat zulke titels indeelt had geen
tegoed, en de nachtronde doet er 200 per keer. Zonder rubriek zet het dashboard
elk kanaal op slot.

Deze proef legt vast:
1. de woordenlijst herkent kindermaten, babywoorden en kindermerken;
2. herenkleding met dezelfde getallen (colbert 50, pantalon 98, overhemd 110)
   blijft volwassen: Revaleur en andere verkopers van herenkleding mogen hier
   niets van merken;
3. de woordenlijstronde vult in één keer alle lege rubrieken, en schrijft nooit
   over iets wat er al staat.
"""
import asyncio

import pytest

from backend.api.imports import _infer_attributes
from backend.services import categorie_herstel as ch


@pytest.mark.parametrize("titel,rubriek", [
    ("Babypakje / romper", "babykleding"),
    ("Longsleeve Noppies maat 44/50", "babykleding"),
    ("Rompertje Feetje 62/68", "babykleding"),
    ("Slabbetjes set van 3", "babykleding"),
    ("Trui maat 92", "peuterkleding"),
    ("Broek maat 98/104", "peuterkleding"),
    ("Jurk / rok maat 116", "meisjes kleding"),
    ("Schoenen Jopper schoenmaat 31", "kinderen schoenen"),
    ("Schoenen | Regenlaarzen Bergstein schoenmaat 27", "kinderen schoenen"),
])
def test_kinderkleding_krijgt_een_rubriek(titel, rubriek):
    uit = _infer_attributes(titel)
    assert uit.get("gender") == "kinderen", (titel, uit)
    assert uit.get("category") == rubriek, (titel, uit)


@pytest.mark.parametrize("titel", [
    "Suitsupply colbert maat 50",
    "Profuomo colbert maat 56",
    "Cavallaro colbert maat 106",
    "Suitsupply pantalon maat 98",
    "Ralph Lauren overhemd maat 110",
    "Colbert 50/52",
    "Herenjas maat 164 cm lang",
    "Damesblazer maat 104",
    "Damesschoenen maat 38",
    "Levi's 501 jeans maat 28",
    "Stone Island trui maat L",
])
def test_volwassen_kleding_blijft_volwassen(titel):
    uit = _infer_attributes(titel)
    assert uit.get("gender") != "kinderen", (titel, uit)
    assert not str(uit.get("category") or "").startswith(
        ("baby", "peuter", "jongens", "meisjes", "kinderen")), (titel, uit)


def test_kindermerk_zonder_maat_geeft_wel_kinderen_maar_raadt_geen_jongen_of_meisje():
    uit = _infer_attributes("Broek Vingino maat 140")
    assert uit.get("gender") == "kinderen"
    assert "category" not in uit


class _Db:
    def __init__(self, rijen):
        self.rijen = rijen
        self.updates = []

    def table(self, naam):
        assert naam == "items"
        return _Q(self)


class _Q:
    def __init__(self, db):
        self.db, self.gt_id, self.n, self.patch, self.eq_ = db, None, None, None, {}

    def select(self, *_a, **_k): return self
    def or_(self, *_a): return self
    def order(self, *_a, **_k): return self
    def gt(self, k, v): self.gt_id = v; return self
    def limit(self, n): self.n = n; return self
    def update(self, patch): self.patch = patch; return self
    def eq(self, k, v): self.eq_[k] = v; return self

    def execute(self):
        class A: pass
        a = A()
        if self.patch is not None:
            rij = next(r for r in self.db.rijen if r["id"] == self.eq_["id"])
            rij.update(self.patch)
            self.db.updates.append((self.eq_["id"], self.patch))
            a.data = [rij]
            return a
        rijen = sorted((r for r in self.db.rijen if not (r.get("category") or "").strip()
                        and (self.eq_.get("user_id") in (None, r["user_id"]))),
                       key=lambda r: r["id"])
        if self.gt_id:
            rijen = [r for r in rijen if r["id"] > self.gt_id]
        a.data = [dict(r) for r in rijen[: self.n]]
        return a


def test_woordenlijstronde_vult_alles_in_een_keer_en_overschrijft_niets(monkeypatch):
    rijen = [{"id": f"{i:05d}", "user_id": "j", "title": "Longsleeve Noppies maat 44/50",
              "description": "", "category": None, "gender": None, "color": None}
             for i in range(1200)]  # meer dan twee pagina's van 500
    rijen.append({"id": "99998", "user_id": "j", "title": "Onbekend ding", "description": "",
                  "category": None, "gender": None, "color": None})
    rijen.append({"id": "99999", "user_id": "j", "title": "Trui maat 92", "description": "",
                  "category": "", "gender": "dames", "color": "rood"})
    db = _Db(rijen)
    monkeypatch.setattr(ch, "get_db", lambda: db)

    uit = asyncio.run(ch.vul_rubrieken_uit_woordenlijst(user_id="j"))

    assert uit["gevuld"] == 1201
    assert all(r["category"] for r in rijen if r["id"] != "99998")
    assert rijen[-2]["category"] is None          # onbekend blijft leeg
    assert rijen[-1]["gender"] == "dames"          # bestaande waarde blijft staan
    assert rijen[-1]["color"] == "rood"
    assert rijen[-1]["category"] == "peuterkleding"
