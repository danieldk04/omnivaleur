"""/api/jobs/onboarding vinkt af op feiten, nooit op klikken.

AANLEIDING 17-09-2026, Johan Kist: 83 kanaaliconen aangeklikt en nergens iets
geplaatst. Een aangeklikt icoon maakt een listings-rij op 'active' zonder opdracht;
daar mag "gepubliceerd" dus nooit op afgaan. Alleen een gelukte opdracht telt, of
een actieve advertentie op eBay/Shopify (die lopen niet via opdrachten en zijn niet
te importeren).
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402


class _DB:
    def __init__(self, tabellen):
        self.tabellen = tabellen

    def table(self, naam):
        rijen = self.tabellen.get(naam, [])

        class Q:
            def __init__(self):
                self.filters = []

            def select(self, *_a): return self
            def order(self, *_a, **_k): return self
            def limit(self, *_a): return self

            def eq(self, k, v):
                self.filters.append(lambda r: r.get(k) == v); return self

            def in_(self, k, v):
                v = list(v); self.filters.append(lambda r: r.get(k) in v); return self

            def execute(self):
                return types.SimpleNamespace(data=[r for r in rijen if all(f(r) for f in self.filters)])
        return Q()


def _status(monkeypatch, **tabellen):
    monkeypatch.setattr(J, "get_db", lambda: _DB(tabellen))
    return J.onboarding_status(user_id="u")


def test_nieuw_account_heeft_niets(monkeypatch):
    assert _status(monkeypatch) == {"extensie": False, "kanaal": False, "gepubliceerd": False}


def test_aangeklikte_iconen_tellen_niet_als_gepubliceerd(monkeypatch):
    # Johans situatie: extensie gezien, items, actieve rijen zonder opdracht erachter.
    uit = _status(monkeypatch,
                  extension_heartbeat=[{"user_id": "u"}],
                  items=[{"id": "i1", "user_id": "u"}],
                  listings=[{"id": "l", "item_id": "i1", "platform": "2dehands", "status": "active"}],
                  jobs=[{"user_id": "u", "status": "done", "platform": "marktplaats", "action": "scan", "result": {}}])
    assert uit == {"extensie": True, "kanaal": True, "gepubliceerd": False}


def test_gelukte_plaatsing_of_bevestigde_facebook_telt(monkeypatch):
    plaatsing = {"user_id": "u", "status": "done", "platform": "2dehands", "action": "create",
                 "result": {"platform_listing_id": "m2443585691"}}
    assert _status(monkeypatch, jobs=[plaatsing])["gepubliceerd"] is True
    fb = {**plaatsing, "platform": "facebook", "result": {"platform_listing_id": None, "bevestigd": "jouw-advertenties"}}
    assert _status(monkeypatch, jobs=[fb])["gepubliceerd"] is True
    fb_oud = {**fb, "result": {"platform_listing_id": None}}   # oude kopie: niet bevestigd
    assert _status(monkeypatch, jobs=[fb_oud])["gepubliceerd"] is False


def test_ebay_of_shopify_advertentie_telt(monkeypatch):
    uit = _status(monkeypatch, items=[{"id": "i1", "user_id": "u"}],
                  listings=[{"id": "l", "item_id": "i1", "platform": "ebay", "status": "active"}])
    assert uit["gepubliceerd"] is True


def test_scanresultaten_worden_niet_meegelezen(monkeypatch):
    """06-10-2026: dit antwoord las tot 50 afgeronde opdrachten MET hun resultaat,
    scans erbij (honderden kB elk, 11,9 MB gemeten bij één verkoper) op een
    database van 0,5 GB geheugen. Een vraag die scans meeneemt mag `result` niet
    selecteren."""
    gezien = []

    class Q:
        def __init__(self, kolommen): self.kolommen = kolommen; self.acties = None
        def select(self, kolommen, *_a, **_k): self.kolommen = kolommen; return self
        def eq(self, k, v):
            if k == "action": self.acties = [v]
            return self
        def in_(self, k, v):
            if k == "action": self.acties = list(v)
            return self
        def order(self, *_a, **_k): return self
        def limit(self, *_a): return self
        def execute(self):
            gezien.append((self.kolommen, self.acties))
            return types.SimpleNamespace(data=[])

    class DB:
        def table(self, naam): return Q("")

    monkeypatch.setattr(J, "get_db", lambda: DB())
    J.onboarding_status(user_id="u")
    for kolommen, acties in gezien:
        if acties and "scan" in acties:
            assert "result" not in kolommen, (kolommen, acties)
