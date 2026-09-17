"""Verkocht op Marktplaats of 2dehands bij een zakelijk account: toch de vraag "verkocht?".

GEMETEN 17-09-2026 (De Juiste Toon). De extensie zoekt verkopen op "Mijn
advertenties", en die pagina is leeg bij een zakelijk account. Bij hem stond nog
nooit een Marktplaats-verkoop in de boeken; 25 advertenties waren van de openbare
lijst verdwenen, 12 daarvan stonden nog op 2dehands. Zie verdwenen_beslissing in
backend/services/foto_controle.py.
"""
from datetime import datetime, timedelta, timezone

from backend.services import foto_controle as F

NU = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def rij(nummer, dagen=10, teller=0, item=None):
    return {"id": f"l-{nummer}", "item_id": item or f"i-{nummer}", "platform_listing_id": nummer,
            "listed_at": (NU - timedelta(days=dagen)).isoformat(), "not_found_count": teller}


def test_verdwenen_advertentie_telt_als_weg():
    onze = [rij("m1"), rij("m2"), rij("m3")]
    weg, terug, te_veel = F.verdwenen_beslissing(onze, {"m1": {}, "m3": {}}, set(), NU)
    assert [r["platform_listing_id"] for r in weg] == ["m2"]
    assert terug == [] and te_veel is False


def test_nieuwe_advertentie_krijgt_48_uur_voor_de_lijst_hem_toont():
    onze = [rij("m1", dagen=1), rij("m2", dagen=3)]
    weg, _, _ = F.verdwenen_beslissing(onze, {}, set(), NU)
    assert [r["platform_listing_id"] for r in weg] == ["m2"]


def test_open_werk_op_dat_artikel_is_onze_eigen_tussenstand():
    onze = [rij("m1", item="bezig"), rij("m2")]
    weg, _, _ = F.verdwenen_beslissing(onze, {}, {"bezig"}, NU)
    assert [r["platform_listing_id"] for r in weg] == ["m2"]


def test_weer_zichtbaar_zet_de_teller_terug():
    onze = [rij("m1", teller=1), rij("m2", teller=0)]
    weg, terug, _ = F.verdwenen_beslissing(onze, {"m1": {}, "m2": {}}, set(), NU)
    assert weg == [] and [r["platform_listing_id"] for r in terug] == ["m1"]


def test_een_groot_deel_ineens_weg_is_een_meetfout():
    onze = [rij(f"m{i}") for i in range(40)]
    _, _, te_veel = F.verdwenen_beslissing(onze, {f"m{i}": {} for i in range(20)}, set(), NU)
    assert te_veel is True
    # Toons echte verhouding (25 van 869) is geen meetfout.
    onze = [rij(f"m{i}") for i in range(869)]
    _, _, te_veel = F.verdwenen_beslissing(onze, {f"m{i}": {} for i in range(25, 869)}, set(), NU)
    assert te_veel is False


def test_pas_na_twee_rondes_een_vraag(monkeypatch):
    import asyncio

    class Q:
        def __init__(self, db, tabel): self.db, self.tabel, self.v, self.f = db, tabel, None, {}
        def select(self, *_a, **_k): return self
        def update(self, v): self.v = v; return self
        def eq(self, k, w): self.f[k] = w; return self
        def in_(self, *_a): return self
        def neq(self, *_a): return self
        def execute(self):
            class R: data = []
            if self.tabel == "listings" and self.v is None:
                R.data = [{"item_id": i} for i in self.db.elders_verkocht]
            if self.v is not None:
                self.db.updates.append((self.f.get("id"), dict(self.v)))
            return R()

    class DB:
        def __init__(self): self.updates, self.elders_verkocht = [], []
        def table(self, t): return Q(self, t)

    async def direct(fn, *a, **k): return fn()
    monkeypatch.setattr(F, "naast_de_lus", direct)
    db = DB()
    nu = datetime.now(timezone.utc)
    oud = (nu - timedelta(days=10)).isoformat()
    onze = [{"id": "l1", "item_id": "i1", "platform_listing_id": "m1", "listed_at": oud, "not_found_count": 0}]
    assert asyncio.run(F._verdwenen_als_vraag(db, "u", "marktplaats", onze, {})) == 0
    assert db.updates == [("l1", {"not_found_count": 1})]
    onze[0]["not_found_count"] = 1
    assert asyncio.run(F._verdwenen_als_vraag(db, "u", "marktplaats", onze, {})) == 1
    laatste = db.updates[-1][1]
    assert laatste["status"] == "sold_unconfirmed" and laatste["not_found_count"] == 2
    assert "Mogelijk verkocht" in laatste["error_message"]

    # Artikel al verkocht op een ander kanaal: archiveren, geen vraag.
    db2 = DB(); db2.elders_verkocht = ["i1"]
    assert asyncio.run(F._verdwenen_als_vraag(db2, "u", "marktplaats", onze, {})) == 0
    assert db2.updates[-1][1] == {"not_found_count": 2, "status": "delisted", "error_message": None}
