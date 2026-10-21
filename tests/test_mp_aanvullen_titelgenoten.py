"""Aanvullen vanaf Marktplaats bij twee sieraden met dezelfde titel.

21-10-2026, Voordeelsieraden (09e089ec): vier kettingen heetten allemaal
"Bloedkoraal antieke ketting fraai 14k slot goud dame vintage" (295 tot 795
euro). De aanvulronde zocht per titel en nam de eerste advertentie die zo heette,
dus elke ketting kreeg de foto's en tekst van dezelfde ene. Gemeten: 11 van haar
856 sieraden droegen de foto's van een ander stuk.
"""
import asyncio
import types

from backend.services import mp_enrich

TITEL = "Bloedkoraal antieke ketting fraai 14k slot goud dame vintage"


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.ids = db, tabel, None

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def or_(self, *_a, **_k):
        self.alleen_leeg = True
        return self

    def in_(self, _veld, ids):
        self.ids = set(ids)
        return self

    def execute(self):
        rijen = self.db.rijen[self.tabel]
        if self.tabel == "listings" and self.ids is not None:
            rijen = [r for r in rijen if r["item_id"] in self.ids]
        elif self.ids is not None:
            rijen = [r for r in rijen if r["id"] in self.ids]
        if getattr(self, "alleen_leeg", False):
            rijen = [r for r in rijen if not r.get("description")]
        return types.SimpleNamespace(data=[dict(r) for r in rijen])


class _DB:
    def __init__(self, items, listings):
        self.rijen = {"items": items, "listings": listings}
        self.updates = {}

    def table(self, naam):
        db = self

        class _T(_Q):
            def update(self, patch):
                self.patch = patch
                return self

            def eq(self, veld, waarde):
                if hasattr(self, "patch") and veld == "id":
                    db.updates[waarde] = self.patch
                return self
        return _T(self, naam)


def _advertentie(item_id, prijs):
    return {"itemId": item_id, "title": TITEL, "vipUrl": f"/v/{item_id}",
            "priceInfo": {"priceCents": prijs * 100, "priceType": "FIXED"},
            "sellerInformation": {"sellerId": 7}}


def _draai(monkeypatch, items, listings):
    db = _DB(items, listings)
    advertenties = [_advertentie("m1", 295), _advertentie("m2", 795)]

    async def _json(_client, _url, params=None):
        if (params or {}).get("offset", 0) > 0:
            return {"listings": []}
        return {"listings": advertenties}

    async def _volledig(_client, url):
        nr = url.rsplit("/", 1)[-1]
        return {"description": f"tekst van {nr}", "photo_urls": [f"{nr}-a", f"{nr}-b"]}

    async def _naast(f):
        return f()

    async def _verkoper(*_a, **_k):
        return 7

    async def _kanalen(_db, ids):
        return {i: {"marktplaats"} for i in ids}

    monkeypatch.setattr(mp_enrich, "_json", _json)
    monkeypatch.setattr(mp_enrich, "volledige_advertentie", _volledig)
    monkeypatch.setattr(mp_enrich, "naast_de_lus", _naast)
    monkeypatch.setattr(mp_enrich, "fetch_all", lambda q: q().execute().data)
    monkeypatch.setattr(mp_enrich, "zoek_verkoper_id", _verkoper)
    monkeypatch.setattr(mp_enrich, "_kanaal_per_item", _kanalen)
    monkeypatch.setattr(mp_enrich.asyncio, "sleep", lambda *_a: _naast(lambda: None))
    mp_enrich._beurt_per_verkoper.clear()
    asyncio.run(mp_enrich.verrijk(db, "u1", budget_seconden=60))
    return db.updates


def _items():
    return [{"id": "A", "title": TITEL, "price": 295, "photo_urls": ["x"], "description": ""},
            {"id": "B", "title": TITEL, "price": 795, "photo_urls": ["y"], "description": ""}]


def test_elke_ketting_krijgt_zijn_eigen_advertentie(monkeypatch):
    listings = [{"item_id": "A", "platform": "marktplaats", "platform_listing_id": "m1"},
                {"item_id": "B", "platform": "marktplaats", "platform_listing_id": "m2"}]
    updates = _draai(monkeypatch, _items(), listings)
    assert updates["A"]["description"] == "tekst van m1"
    assert updates["B"]["description"] == "tekst van m2"
    assert updates["B"]["photo_urls"] == ["m2-a", "m2-b"]


def test_zonder_eigen_nummer_wordt_er_niet_geraden(monkeypatch):
    updates = _draai(monkeypatch, _items(), [])
    assert updates == {}
