"""Maat en merk uit de titel (Janneke 31d28378, 08-10-2026).

"Regenlaarzen Bergstein schoenmaat 31*" stond zonder maat en merk in haar
voorraad; het dashboard hield Marktplaats en 2dehands daarom op slot met
"Voeg brand, size toe". Alleen een schoenmaat en alleen een merk dat de
verkoper zelf al gebruikt: een verkeerde waarde is erger dan een lege.
"""
import asyncio

from backend.api.imports import (_schoenmaat_uit_titel, _merk_uit_titel, merken_uit_voorraad,
                                 _item_data_from_candidate, _backfill_patch)
from backend.platforms.shopify_importer import _convert


def test_schoenmaat_uit_jannekes_titels():
    assert _schoenmaat_uit_titel("Regenlaarzen Bergstein schoenmaat 31*") == "31"
    assert _schoenmaat_uit_titel("Schoenen | Regenlaarzen Bergstein schoenmaat 24") == "24"
    assert _schoenmaat_uit_titel("Schoenen Jopper schoenmaat 31") == "31"
    assert _schoenmaat_uit_titel("Sneakers Nike maat 38,5") == "38.5"


def test_geen_schoenmaat_bij_kleding_of_twijfel():
    # Kleding: "maat 98" of "44/50" is geen eenduidige maat voor elk kanaal.
    assert _schoenmaat_uit_titel("Longsleeve Noppies maat 44/50") is None
    assert _schoenmaat_uit_titel("Broek maat 98") is None
    assert _schoenmaat_uit_titel("Colbert Suitsupply maat 50") is None
    # Twee maten in één titel: dan weten we het niet.
    assert _schoenmaat_uit_titel("Laarzen maat 27 en maat 28") is None
    # Geen maat in de titel.
    assert _schoenmaat_uit_titel("Regenlaarzen Bergstein") is None


def test_merk_alleen_uit_eigen_woordenschat():
    merken = merken_uit_voorraad([{"brand": "Bergstein"}, {"brand": "Bergstein"},
                                  {"brand": "Jopper"}, {"brand": "Jopper"},
                                  {"brand": "Only"}, {"brand": "Only"},
                                  {"brand": "Eenmalig"}])
    assert _merk_uit_titel("Regenlaarzen Bergstein schoenmaat 31*", merken) == "Bergstein"
    # Merk dat ook een gewoon woord is: nooit uit de titel.
    assert _merk_uit_titel("Jurk only worn once", merken) is None
    # Een merk dat maar één keer voorkomt telt niet als woordenschat.
    assert _merk_uit_titel("Trui Eenmalig", merken) is None
    # Twee merken in de titel: geen keuze.
    assert _merk_uit_titel("Bergstein en Jopper laarzen", merken) is None
    # Een deel van een woord is geen merk.
    assert _merk_uit_titel("Bergsteiner laarzen", merken) is None


def test_import_vult_lege_maat_uit_titel():
    data = _item_data_from_candidate({"title": "Regenlaarzen Bergstein schoenmaat 31*", "price": 25})
    assert data["size"] == "31"
    # Een maat die de bron meegaf gaat altijd voor.
    data = _item_data_from_candidate({"title": "Regenlaarzen schoenmaat 31", "size": "30"})
    assert data["size"] == "30"


def test_herscan_vult_lege_maat_maar_overschrijft_niets():
    assert _backfill_patch({"size": None}, {"title": "Laarzen schoenmaat 27"}).get("size") == "27"
    assert "size" not in _backfill_patch({"size": "30"}, {"title": "Laarzen schoenmaat 27"})


def test_shopify_nederlandse_optienamen():
    p = {"id": 1, "title": "Laarzen", "options": [
        {"name": "Maat", "values": ["24"]}, {"name": "Kleur", "values": ["Zilver"]},
        {"name": "Materiaal", "values": ["Rubber"]}], "variants": [{"price": "25"}]}
    out = _convert(p)
    assert (out["size"], out["color"], out["material"]) == ("24", "Zilver", "Rubber")


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.gt_id, self.patch = db, tabel, [], None, None
        self._range = None
    def select(self, *_a, **_k): return self
    def or_(self, *_a): self.f.append(("leeg",)); return self
    def order(self, *_a, **_k): return self
    def eq(self, k, v): self.f.append(("eq", k, v)); return self
    def neq(self, k, v): self.f.append(("neq", k, v)); return self
    def gt(self, k, v): self.gt_id = v; return self
    def limit(self, *_a): return self
    def range(self, a, b): self._range = (a, b); return self
    def update(self, patch): self.patch = patch; return self
    def _rijen(self):
        rijen = list(self.db.items)
        for f in self.f:
            if f[0] == "leeg":
                rijen = [r for r in rijen if not r.get("size") or not r.get("brand")]
            elif f[0] == "eq":
                rijen = [r for r in rijen if r.get(f[1]) == f[2]]
            elif f[0] == "neq":
                rijen = [r for r in rijen if r.get(f[1]) not in (None, f[2])]
        if self.gt_id:
            rijen = [r for r in rijen if r["id"] > self.gt_id]
        rijen.sort(key=lambda r: r["id"])
        if self._range:
            rijen = rijen[self._range[0]:self._range[1] + 1]
        return rijen
    def execute(self):
        if self.patch is not None:
            for r in self._rijen():
                r.update(self.patch)
            return type("R", (), {"data": []})()
        return type("R", (), {"data": [dict(r) for r in self._rijen()]})()


class _DB:
    def __init__(self, items): self.items = items
    def table(self, naam): return _Q(self, naam)


def test_ronde_vult_bestaande_voorraad(monkeypatch):
    from backend.services import categorie_herstel
    import backend.database as database
    db = _DB([
        {"id": "a1", "user_id": "j", "title": "Regenlaarzen Bergstein schoenmaat 31*", "size": None, "brand": None},
        {"id": "a2", "user_id": "j", "title": "Schoenen | Regenlaarzen Bergstein schoenmaat 27", "size": "30", "brand": "Bergstein"},
        {"id": "a3", "user_id": "j", "title": "Laarzen Bergstein schoenmaat 25", "size": "25", "brand": "Bergstein"},
        {"id": "a4", "user_id": "j", "title": "Babypakje / romper", "size": None, "brand": None},
        # Ander account: zijn eigen woordenschat, niet die van Janneke.
        {"id": "b1", "user_id": "x", "title": "Laarzen Bergstein schoenmaat 40", "size": None, "brand": None},
    ])
    monkeypatch.setattr(categorie_herstel, "get_db", lambda: db)
    monkeypatch.setattr(database, "execute_with_retry", lambda q: q.execute())
    uit = asyncio.run(categorie_herstel.vul_maat_en_merk_uit_titel())
    per_id = {r["id"]: r for r in db.items}
    assert (per_id["a1"]["size"], per_id["a1"]["brand"]) == ("31", "Bergstein")
    assert per_id["a2"]["size"] == "30"                       # bestaande maat blijft staan
    assert (per_id["a4"]["size"], per_id["a4"]["brand"]) == (None, None)
    assert (per_id["b1"]["size"], per_id["b1"]["brand"]) == ("40", None)
    assert uit["gevuld"] == 2 and uit["mislukt"] == 0
