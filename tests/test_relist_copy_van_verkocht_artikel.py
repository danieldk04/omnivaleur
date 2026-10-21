"""Relist op een verkocht artikel maakt een nieuwe kopie en laat de verkoop staan.

21-10-2026, Janneke: ze heeft van veel artikelen meer stuks en plaatst na een
verkoop zelf het volgende. Een verkocht artikel wordt bewust niet opnieuw
geplaatst, dus dat stuk is een nieuwe rij (zoals Daniel op 18-09 deed).
"""
import asyncio
import types

import backend.api.items as items


ORIGINEEL = {
    "id": "o1", "user_id": "u1", "sku": "IMP-O1", "title": "Winterjas Noppies maat 128",
    "description": "Nieuw met labels.", "price": 50.0, "brand": "Noppies", "size": "128",
    "condition": "new", "category": "jongens kleding", "color": "Dark green",
    "photo_urls": ["https://img/x.jpg"], "created_at": "2026-10-09T14:38:12+00:00",
    "updated_at": "2026-10-18T12:02:40+00:00", "rubriek_pogingen": 1,
    "rubriek_gepoogd_op": "2026-10-10T03:47:10+00:00",
}


class Q:
    def __init__(self, db, naam):
        self.db, self.naam, self.f, self.ins = db, naam, [], None

    def select(self, *a, **kw): return self
    def order(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    def eq(self, k, v): self.f.append(("eq", k, v)); return self
    def neq(self, k, v): self.f.append(("neq", k, v)); return self
    def gt(self, k, v): self.f.append(("gt", k, v)); return self
    def in_(self, k, v): self.f.append(("in", k, list(v))); return self
    def insert(self, rij): self.ins = rij; return self

    def execute(self):
        if self.ins is not None:
            self.db.items.append(dict(self.ins, created_at="2026-10-21T19:00:00+00:00"))
            return types.SimpleNamespace(data=[self.db.items[-1]])
        bron = self.db.items if self.naam == "items" else self.db.listings
        uit = []
        for r in bron:
            ok = True
            for soort, k, v in self.f:
                if soort == "eq" and r.get(k) != v: ok = False
                if soort == "neq" and r.get(k) == v: ok = False
                if soort == "gt" and not (r.get(k) or "") > v: ok = False
                if soort == "in" and r.get(k) not in v: ok = False
            if ok:
                uit.append(r)
        return types.SimpleNamespace(data=uit)


class Db:
    def __init__(self, listings):
        self.items, self.listings = [dict(ORIGINEEL)], listings

    def table(self, naam): return Q(self, naam)


VERKOCHT = [{"item_id": "o1", "platform": "vinted", "status": "sold",
             "sold_at": "2026-10-21T18:16:55+00:00"}]


def _roep(monkeypatch, db, item_id="o1"):
    monkeypatch.setattr(items, "get_db", lambda: db)
    return asyncio.run(items.relist_copy(item_id, "u1"))


def test_verkocht_artikel_krijgt_een_kopie_en_blijft_zelf_ongemoeid(monkeypatch):
    db = Db(list(VERKOCHT))
    uit = _roep(monkeypatch, db)
    kopie = uit["item"]
    assert uit["copy_made"] is True and kopie["id"] != "o1"
    assert kopie["sku"].startswith("REV-") and kopie["sku"] != "IMP-O1"
    assert (kopie["title"], kopie["price"], kopie["photo_urls"], kopie["brand"]) == (
        ORIGINEEL["title"], 50.0, ORIGINEEL["photo_urls"], "Noppies")
    assert "rubriek_pogingen" not in kopie
    assert db.items[0] == ORIGINEEL            # origineel niet aangeraakt
    assert db.listings == VERKOCHT              # verkoop blijft staan


def test_twee_keer_klikken_maakt_geen_tweede_kopie(monkeypatch):
    db = Db(list(VERKOCHT))
    eerste = _roep(monkeypatch, db)["item"]
    tweede = _roep(monkeypatch, db)
    assert tweede["reused"] is True and tweede["copy_made"] is False
    assert tweede["item"]["id"] == eerste["id"]
    assert len(db.items) == 2


def test_kopie_die_al_ergens_staat_wordt_niet_hergebruikt(monkeypatch):
    db = Db(list(VERKOCHT))
    eerste = _roep(monkeypatch, db)["item"]
    db.listings.append({"item_id": eerste["id"], "platform": "vinted", "status": "active"})
    tweede = _roep(monkeypatch, db)
    assert tweede["copy_made"] is True and tweede["item"]["id"] != eerste["id"]


def test_niet_verkocht_artikel_geeft_zichzelf_terug(monkeypatch):
    db = Db([{"item_id": "o1", "platform": "vinted", "status": "active"}])
    uit = _roep(monkeypatch, db)
    assert uit["copy_made"] is False and uit["item"]["id"] == "o1"
    assert len(db.items) == 1


def test_andermans_artikel_is_een_404(monkeypatch):
    db = Db(list(VERKOCHT))
    monkeypatch.setattr(items, "get_db", lambda: db)
    try:
        asyncio.run(items.relist_copy("o1", "andere-gebruiker"))
    except items.HTTPException as e:
        assert e.status_code == 404
    else:
        raise AssertionError("had 404 moeten geven")
