"""familie_ids_veel geeft precies wat familie_ids per artikel geeft, in één vraag.

11-10-2026, Egbert (bcdf9aa4): de uitdeelronde vroeg per wachtende plaatsing
het artikel en zijn tweelingen los op. Met 24 plaatsingen in de rij waren dat
48 vragen en 10 tot 11 seconden per uitgifte (Railway-verzoeklog: /pending
10,2 tot 10,9 s), ook als er alleen een verlenging uitging.

De nagebouwde database begrijpt de twee voorwaarden die de echte krijgt
(sku.eq en title.ilike met % en _), zodat beide routes langs dezelfde regels
lopen. Draaien: python3 -m pytest -q tests/test_tweelingen_gebundeld.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.tweelingen import familie_ids, familie_ids_veel  # noqa: E402


def _ilike(p, t):
    rx = "".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in p)
    return re.fullmatch(rx, t or "", re.I | re.S) is not None


class Vraag:
    def __init__(self, db):
        self.db, self.filters, self.of, self.grens = db, [], None, None

    def select(self, *_):
        return self

    def eq(self, k, v):
        self.filters.append((k, v)); return self

    def or_(self, s):
        self.of = re.findall(r'(sku)\.eq\.([^,]+)|(title)\.ilike\."([^"]+)"', s); return self

    def limit(self, n):
        self.grens = n; return self

    def execute(self):
        self.db.vragen += 1
        if self.db.kapot:
            raise RuntimeError("database weg")
        uit = []
        for r in self.db.rijen:
            if any(r.get(k) != v for k, v in self.filters):
                continue
            if self.of is not None and not any(
                    (a and r.get("sku") == b) or (c and _ilike(d, r.get("title") or ""))
                    for a, b, c, d in self.of):
                continue
            uit.append(r)
        return type("R", (), {"data": uit[: self.grens] if self.grens else uit})()


class DB:
    def __init__(self, rijen, kapot=False):
        self.rijen, self.vragen, self.kapot = rijen, 0, kapot

    def table(self, _):
        return Vraag(self)


U = "u1"
RIJEN = [
    {"id": "a1", "user_id": U, "title": "(1237) Lilac Shirt - Men L", "sku": "imp-4eb880ca", "brand": "Profuomo"},
    {"id": "a2", "user_id": U, "title": "(1237) Lila Overhemd - Heren L", "sku": "rev-2e6d54b5", "brand": "Profuomo"},
    {"id": "a3", "user_id": U, "title": "(1237) Ander merk", "sku": None, "brand": "Zara"},
    {"id": "b1", "user_id": U, "title": "(1349) Jas", "sku": "1349 - 2", "brand": ""},
    {"id": "b2", "user_id": U, "title": "(1349) Jas", "sku": "1349", "brand": ""},
    {"id": "c1", "user_id": U, "title": "(A_1) Trui", "sku": None, "brand": ""},
    {"id": "c2", "user_id": U, "title": "(AB1) Trui", "sku": None, "brand": ""},
    {"id": "d1", "user_id": U, "title": "Zonder nummer", "sku": "x9", "brand": ""},
    {"id": "e1", "user_id": U, "title": "Alleen sku", "sku": "77ab", "brand": ""},
    {"id": "e2", "user_id": U, "title": "(77ab) Zelfde", "sku": None, "brand": ""},
    {"id": "z1", "user_id": "ander", "title": "(1237) Van iemand anders", "sku": None, "brand": "Profuomo"},
]


def test_zelfde_uitkomst_als_per_artikel():
    los = {r["id"]: sorted(familie_ids(DB(RIJEN), r)) for r in RIJEN}
    db = DB(RIJEN)
    veel = familie_ids_veel(db, RIJEN)
    assert {k: sorted(v) for k, v in veel.items()} == los
    # Echte tweelingen zitten erin, iemand anders nooit.
    assert sorted(veel["a1"]) == ["a1", "a2"]
    assert "z1" not in veel["a1"]
    # Twee gebruikers, dus twee vragen; per artikel waren het er elf.
    assert db.vragen == 2


def test_database_weg_dan_per_artikel_zoals_vroeger():
    veel = familie_ids_veel(DB(RIJEN, kapot=True), RIJEN[:3])
    assert veel == {"a1": ["a1"], "a2": ["a2"], "a3": ["a3"]}


def test_volle_bundel_valt_terug_op_per_artikel():
    rijen = [{"id": f"r{i}", "user_id": U, "title": "(555) Stuk", "sku": None, "brand": ""}
             for i in range(60)]
    db = DB(rijen)
    veel = familie_ids_veel(db, rijen[:1])
    assert len(veel["r0"]) == 50          # zoals familie_ids: hooguit 50 rijen
    assert db.vragen == 2                 # gebundeld kwam vol terug, daarna per artikel
