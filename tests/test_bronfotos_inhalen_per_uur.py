"""De Juiste Toon, 15-10-2026: 239 artikelen met foto's op zijn eigen webshop.
Het uurlijkse inhalen pakt er een paar per ronde en stopt bij de eerste mislukking
(de bron zet na ~25 artikelen een captcha)."""
import asyncio

from backend.services import photo_mirror as pm

BRON = "https://dejuistetoon.eu/{}.jpg"
EIGEN = "https://img.omnivaleur.com/u1/imported/{}.jpg"


class _Db:
    def __init__(self, rijen): self.rijen, self.updates = rijen, []
    def table(self, n): return _T(self)


class _T:
    def __init__(self, db): self.db = db
    def select(self, *a): return self
    def eq(self, *a): self.k = a; return self
    def update(self, d): self.d = d; return self
    def execute(self):
        if hasattr(self, "d"): self.db.updates.append((self.k[1], self.d))
        return type("R", (), {"data": []})()


def _zet(monkeypatch, rijen, mirror):
    import backend.database as bd
    db = _Db(rijen)
    monkeypatch.setattr(bd, "get_db", lambda: db)
    monkeypatch.setattr(bd, "fetch_all", lambda f: rijen)

    async def lus(f): return f()
    monkeypatch.setattr(bd, "naast_de_lus", lus)
    monkeypatch.setattr(pm, "mirror_photos", mirror)
    return db


def test_haalt_een_ronde_en_laat_eigen_artikelen_met_rust(monkeypatch):
    rijen = [{"id": f"i{n}", "photo_urls": [BRON.format(n)]} for n in range(12)]
    rijen.append({"id": "eigen", "photo_urls": [EIGEN.format("x")]})

    async def mirror(urls, uid): return [EIGEN.format(u[-6:-4]) for u in urls]
    db = _zet(monkeypatch, rijen, mirror)
    uit = asyncio.run(pm.bronfotos_inhalen("u1", max_artikelen=8))
    assert uit["achterstand"] == 12 and uit["hersteld"] == 8 and not uit["gestopt"]
    assert len(db.updates) == 8 and all(i != "eigen" for i, _ in db.updates)


def test_stopt_bij_de_eerste_mislukking(monkeypatch):
    rijen = [{"id": f"i{n}", "photo_urls": [BRON.format(n)]} for n in range(5)]
    aantal = []

    async def mirror(urls, uid):
        aantal.append(1)
        return list(urls) if len(aantal) == 2 else [EIGEN.format("a")]
    db = _zet(monkeypatch, rijen, mirror)
    uit = asyncio.run(pm.bronfotos_inhalen("u1"))
    assert uit["gestopt"] and uit["hersteld"] == 1 and len(aantal) == 2 and len(db.updates) == 1
