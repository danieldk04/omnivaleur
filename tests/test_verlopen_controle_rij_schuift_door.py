"""De verlopen-controle moet ook nieuwere verkoopvragen bereiken.

13-11-2026, nickspijkers (17e5c638): 9 platen stonden op Marktplaats als
"verlopen" (HTTP 410), maar bleven "is dit verkocht?" vragen. De controle las
de oudste 100 openstaande vragen en filterde pas daarna op reden; vragen die
niet verlopen krijgen geen nieuwe last_checked, dus elke ronde dezelfde 100.
Deze nagebootste database houdt zich wel aan order, limit en like.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api import listings as api  # noqa: E402
from backend.services import verlopen_controle as vc  # noqa: E402

VERLOPEN = "<div>Deze advertentie is helaas verlopen</div>"
LEVEND = "<html><h1>Mooie plaat</h1><button>Bericht</button></html>"


class _Q:
    def __init__(self, db):
        self.db, self.f, self.inn, self.lk, self.op, self.v, self.n, self.o = db, {}, {}, None, None, None, None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.v = "update", v; return self
    def eq(self, k, v): self.f[k] = v; return self
    def in_(self, k, v): self.inn[k] = list(v); return self
    def like(self, k, patroon): self.lk = (k, patroon.rstrip("%")); return self
    def order(self, k, **_k): self.o = k; return self
    def limit(self, n): self.n = n; return self

    def execute(self):
        r = [x for x in self.db.rijen if all(x.get(k) == v for k, v in self.f.items())
             and all(x.get(k) in v for k, v in self.inn.items())
             and (not self.lk or str(x.get(self.lk[0]) or "").startswith(self.lk[1]))]
        if self.o:
            r.sort(key=lambda x: x.get(self.o) or "")
        if self.n:
            r = r[:self.n]
        if self.op == "update":
            for x in r:
                x.update(self.v)
        return type("R", (), {"data": r})()


class _DB:
    def __init__(self, rijen): self.rijen = rijen
    def table(self, _n): return _Q(self)


class _A:
    def __init__(self, s, t): self.status_code, self.text = s, t


class _Client:
    def __init__(self, per_url): self.per_url, self.gevraagd = per_url, []
    async def __aenter__(self): return self
    async def __aexit__(self, *_a): return False
    async def get(self, url, **_k):
        self.gevraagd.append(url)
        return self.per_url.get(url, _A(200, LEVEND))


def _rij(i, reden, dag):
    return {"id": f"l{i}", "item_id": "it", "platform": "marktplaats", "status": "sold_unconfirmed",
            "platform_listing_id": f"m{i}", "platform_listing_url": f"https://www.marktplaats.nl/v/a/b/m{i}-x",
            "error_message": reden, "last_checked": dag}


def _rondes(monkeypatch, rijen, per_url, aantal):
    db, client = _DB(rijen), _Client(per_url)
    monkeypatch.setattr(vc, "get_db", lambda: db)
    monkeypatch.setattr(vc, "PAUZE_SECONDEN", 0)
    monkeypatch.setattr(vc, "HERKANSING_SECONDEN", 0)

    async def _direct(fn): return fn()
    monkeypatch.setattr(vc, "naast_de_lus", _direct)
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: client)
    for _ in range(aantal):
        asyncio.run(vc.controleer_verlopen_verkoopvragen())
    return db, client


def test_verlopen_vraag_achter_140_oudere_vragen_wordt_ingetrokken(monkeypatch):
    oud = [_rij(i, api.VERDENKING_REDENEN["badge"], f"2026-10-{1 + i % 28:02d}") for i in range(140)]
    nieuw = _rij(999, api.VERDENKING_REDENEN["weg"], "2026-11-12T16:33")
    db, _ = _rondes(monkeypatch, oud + [nieuw], {nieuw["platform_listing_url"]: _A(410, VERLOPEN)}, 1)
    assert nieuw["status"] == "delisted", "de verlopen plaat achteraan moet aan de beurt komen"
    assert all(r["status"] == "sold_unconfirmed" for r in oud), "verkocht-labels blijven staan"


def test_ook_de_kandidaat_na_de_eerste_25_komt_aan_de_beurt(monkeypatch):
    levend = [_rij(i, api.VERDENKING_REDENEN["weg"], f"2026-10-{1 + i:02d}") for i in range(25)]
    laatste = _rij(500, api.VERDENKING_REDENEN["weg"], "2026-11-12")
    _db, _ = _rondes(monkeypatch, levend + [laatste], {laatste["platform_listing_url"]: _A(410, VERLOPEN)}, 30)
    assert laatste["status"] == "delisted", "25 levende advertenties mogen de rij niet voor altijd bezetten"
