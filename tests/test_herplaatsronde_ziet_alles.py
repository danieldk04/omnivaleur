"""De herplaatsronde ziet elke advertentie die aan de beurt is, niet de oudste 1.000.

GEMETEN 28-09-2026, Zilverwebsite (1.260 advertenties op Marktplaats). Sinds 20-09
werd er niets meer herplaatst, terwijl 75 advertenties over hun ingestelde 30
dagen waren. De ronde vroeg alle advertenties op die aan de beurt waren met één
gewone select, en PostgREST geeft daar stilzwijgend hooguit 1.000 rijen op terug.
Omdat de oudste voorop stonden waren dat elke ronde dezelfde 1.000: advertenties
die de ronde toch overslaat. Er stonden er 8.775 klaar; de ronde zag alleen die
van vóór 21-08, en zette bij niemand ook maar één herplaatsing klaar.

Deze proef bootst die grens van 1.000 na en zet er 1.200 advertenties vóór van
een verkoper die herplaatsen uit heeft staan.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.services import crosslist, instellingen, relist

MAX_RIJEN = 1000          # PostgREST max-rows: meer komt er per aanroep nooit terug


class _Vraag:
    def __init__(self, db, naam):
        self.db, self.naam, self.filters = db, naam, []
        self.sorteer = self.bereik = self.hoogstens = None

    def select(self, *_a, **_k): return self
    def eq(self, k, v): self.filters.append(lambda r: r.get(k) == v); return self
    def lt(self, k, v): self.filters.append(lambda r: (r.get(k) or "") < v); return self
    def gte(self, k, v): self.filters.append(lambda r: (r.get(k) or "") >= v); return self
    def in_(self, k, v): s = set(v); self.filters.append(lambda r: r.get(k) in s); return self
    def order(self, k, **_k): self.sorteer = k; return self
    def range(self, a, b): self.bereik = (a, b); return self
    def limit(self, n): self.hoogstens = n; return self

    def execute(self):
        rijen = [r for r in self.db[self.naam] if all(f(r) for f in self.filters)]
        if self.sorteer:
            rijen.sort(key=lambda r: r.get(self.sorteer) or "")
        if self.bereik:
            rijen = rijen[self.bereik[0]:self.bereik[1] + 1]
        rijen = rijen[:MAX_RIJEN]
        if self.hoogstens:
            rijen = rijen[:self.hoogstens]
        return SimpleNamespace(data=rijen, count=len(rijen))


class _DB:
    def __init__(self, tabellen): self.tabellen = tabellen
    def table(self, naam): return _Vraag(self.tabellen, naam)


def _advertentie(i, eigenaar, dagen_oud, nu):
    return ({"id": f"l{i}", "item_id": f"i{i}", "platform": "marktplaats", "status": "active",
             "listed_at": (nu - timedelta(days=dagen_oud, minutes=i)).isoformat(),
             "platform_listing_url": f"https://www.marktplaats.nl/v/x/m{i}"},
            {"id": f"i{i}", "user_id": eigenaar})


def _draai(monkeypatch):
    nu = datetime.now(timezone.utc)
    paren = ([_advertentie(i, "herplaatsen-uit", 60, nu) for i in range(1200)] +
             [_advertentie(5000 + i, "zilver", 35, nu) for i in range(5)])
    db = _DB({"listings": [p[0] for p in paren], "items": [p[1] for p in paren], "jobs": []})

    async def niets(*_a, **_k): return None
    monkeypatch.setattr(crosslist, "get_db", lambda: db)
    monkeypatch.setattr(crosslist, "_echte_datums_ophalen", niets)
    monkeypatch.setattr(crosslist, "_mag_nog_werken", lambda _u: True)
    monkeypatch.setattr(crosslist, "_dagelijkse_relist_grens", lambda _db, _u: 25)
    monkeypatch.setattr(instellingen, "alle_relist_dagen", lambda: {"zilver": 30})
    monkeypatch.setattr(instellingen, "lees",
                        lambda u: {"auto_relist": u != "herplaatsen-uit", "relist_dagen": 30})
    klaargezet = []

    async def opnemer(item_id, platform, user_id, strategy, **_k):
        klaargezet.append((user_id, item_id))
        return {"status": "queued"}
    monkeypatch.setattr(relist, "refresh_listing", opnemer)
    asyncio.run(crosslist.relist_expiring_marktplaats())
    return klaargezet


def test_advertenties_achter_de_eerste_1000_komen_aan_de_beurt(monkeypatch):
    klaargezet = _draai(monkeypatch)
    assert sorted(klaargezet) == [("zilver", f"i{5000 + i}") for i in range(5)]


def test_wie_herplaatsen_uit_heeft_krijgt_nog_steeds_niets(monkeypatch):
    assert not [k for k in _draai(monkeypatch) if k[0] == "herplaatsen-uit"]
