"""Publish op een al verkocht artikel zegt meteen waarom er niets gebeurt.

21-10-2026, Janneke: twee Noppies-jassen die op Vinted al "Verkocht" stonden. De
uitgifte annuleerde de plaatsing een halve seconde na het klikken, het scherm
zei "Queued" en er opende nooit een tabblad. Nu komt het antwoord al bij Publish.
"""
import asyncio
import types

import backend.services.crosslist as cl


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam, self.f = db, naam, {}

    def select(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    def eq(self, k, v):
        self.f[k] = v
        return self

    def execute(self):
        if self.naam == "items":
            return types.SimpleNamespace(data=[{"id": "i1", "user_id": "u1", "title": "Jas"}])
        if self.naam == "listings":
            return types.SimpleNamespace(data=[r for r in self.db.listings
                                               if r["item_id"] == self.f.get("item_id")
                                               and r["status"] == self.f.get("status")])
        return types.SimpleNamespace(data=[])


class NepDb:
    def __init__(self, listings): self.listings = listings
    def table(self, naam): return NepTabel(self, naam)


async def _niet_geblokkeerd(*a, **kw): return None


def _draai(monkeypatch, listings, platforms):
    monkeypatch.setattr(cl, "get_db", lambda: NepDb(listings))

    async def exec_(q, dubbel_is_ok=False): return q.execute()
    monkeypatch.setattr(cl, "_exec", exec_)

    async def naast(f): return f()
    monkeypatch.setattr(cl, "naast_de_lus", naast)
    monkeypatch.setattr(cl, "publicatie_geblokkeerd", lambda *a, **kw: None)

    async def vul(db, item): raise RuntimeError("voorbij de verkoopcontrole")
    monkeypatch.setattr(cl, "_fill_inferred_gaps", vul)
    return asyncio.run(cl.publish_to_platforms("i1", platforms, "u1"))


def test_verkocht_artikel_krijgt_een_uitleg_en_geen_opdracht(monkeypatch):
    uit = _draai(monkeypatch, [{"item_id": "i1", "platform": "vinted", "status": "sold"}],
                 ["vinted", "marktplaats"])
    assert [u["status"] for u in uit] == ["blocked", "blocked"]
    assert "already sold on Vinted" in uit[0]["error"]
    assert "Not sold" in uit[0]["error"]


def test_artikel_dat_niet_verkocht_is_gaat_door_de_controle(monkeypatch):
    try:
        _draai(monkeypatch, [], ["vinted"])
    except RuntimeError as e:
        assert "voorbij de verkoopcontrole" in str(e)
    else:
        raise AssertionError("de publicatie had verder moeten gaan")
