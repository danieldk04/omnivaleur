"""Een prijswijziging in Omni gaat ook naar 2dehands (02-11-2026, Toon).

Voor de wijziging stond 2dehands op 'unsupported': de klant moest de prijs daar met
de hand aanpassen. Nu zet de server een content_refresh klaar met _prijs_bijwerken,
en een tweede wijziging terwijl de eerste nog wacht past dezelfde opdracht aan.
De oude code (f53be0d3) wordt als voor-en-na-proef ingelezen.
"""
import asyncio
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

WORTEL = Path(__file__).resolve().parent.parent


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.actie, self.waarden = db, tabel, [], "select", None

    def select(self, *_a, **_k): return self
    def eq(self, k, v): self.filters.append((k, "eq", v)); return self
    def in_(self, k, v): self.filters.append((k, "in", v)); return self
    def limit(self, *_a): return self
    def insert(self, w): self.actie, self.waarden = "insert", w; return self
    def update(self, w): self.actie, self.waarden = "update", w; return self

    def _past(self, rij):
        for k, soort, v in self.filters:
            if soort == "eq" and rij.get(k) != v: return False
            if soort == "in" and rij.get(k) not in v: return False
        return True

    def execute(self):
        rijen = self.db.tabellen.setdefault(self.tabel, [])
        if self.actie == "insert":
            rij = {"id": f"{self.tabel}-{len(rijen) + 1}", **self.waarden}
            rijen.append(rij)
            return types.SimpleNamespace(data=[rij])
        gevonden = [r for r in rijen if self._past(r)]
        if self.actie == "update":
            for r in gevonden: r.update(self.waarden)
        return types.SimpleNamespace(data=[dict(r) for r in gevonden])


class FakeDb:
    def __init__(self):
        self.tabellen = {
            "items": [{"id": "i1", "user_id": "u1", "title": "Tapijt", "price": 65.0, "sku": "TL03"}],
            "listings": [{"id": "l1", "item_id": "i1", "platform": "2dehands", "status": "active",
                          "platform_listing_id": "m2446468449",
                          "platform_listing_url": "https://www.2dehands.be/v/x/m2446468449-a"}],
            "jobs": [], "platform_credentials": [],
        }

    def table(self, naam): return _Vraag(self, naam)


def _laad(bron_commit=None):
    naam = "backend.services.crosslist_proef" + (bron_commit or "nieuw")
    if bron_commit:
        tekst = subprocess.check_output(["git", "show", f"{bron_commit}:backend/services/crosslist.py"],
                                        cwd=WORTEL, text=True)
        spec = importlib.util.spec_from_loader(naam, loader=None)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "backend.services"
        sys.modules[naam] = mod
        exec(compile(tekst, f"crosslist@{bron_commit}", "exec"), mod.__dict__)
    else:
        import backend.services.crosslist as mod
    return mod


def _draai(mod, db):
    mod.get_db = lambda: db
    return asyncio.run(mod.sync_price_to_platforms("i1", "u1"))


def test_prijs_wordt_voor_2dehands_klaargezet():
    mod, db = _laad(), FakeDb()
    uit = _draai(mod, db)
    assert uit == [{"platform": "2dehands", "status": "queued",
                    "message": "Price edit queued — Chrome extension will apply it"}]
    [job] = db.tabellen["jobs"]
    assert (job["platform"], job["action"], job["status"]) == ("2dehands", "content_refresh", "pending")
    assert job["payload"]["_prijs_bijwerken"] is True
    assert job["payload"]["price"] == 65.0
    assert job["payload"]["platform_listing_id"] == "m2446468449"


def test_tweede_wijziging_past_de_wachtende_opdracht_aan():
    mod, db = _laad(), FakeDb()
    _draai(mod, db)
    db.tabellen["items"][0]["price"] = 59.0
    _draai(mod, db)
    assert len(db.tabellen["jobs"]) == 1
    assert db.tabellen["jobs"][0]["payload"]["price"] == 59.0


def test_een_opdracht_die_al_loopt_wordt_niet_overschreven():
    mod, db = _laad(), FakeDb()
    _draai(mod, db)
    db.tabellen["jobs"][0]["status"] = "claimed"
    db.tabellen["items"][0]["price"] = 59.0
    _draai(mod, db)
    assert [(j["status"], j["payload"]["price"]) for j in db.tabellen["jobs"]] == [("claimed", 65.0), ("pending", 59.0)]


def test_eigen_prijs_voor_2dehands_wint():
    mod, db = _laad(), FakeDb()
    db.tabellen["items"][0]["price_2dehands"] = 70.0
    _draai(mod, db)
    assert db.tabellen["jobs"][0]["payload"]["price"] == 70.0


def test_voor_de_wijziging_was_2dehands_unsupported():
    mod, db = _laad("f53be0d3"), FakeDb()
    uit = _draai(mod, db)
    assert uit[0]["status"] == "unsupported" and db.tabellen["jobs"] == []


def test_ondergrenzen():
    from backend.api.jobs import MINIMALE_2DH_BIJWERK_VERSIE, MINIMALE_2DH_PRIJS_VERSIE
    assert MINIMALE_2DH_BIJWERK_VERSIE == (1, 0, 354)   # verzendkosten blijven kunnen
    assert MINIMALE_2DH_PRIJS_VERSIE == (1, 0, 417)


def test_prijs_gaat_ook_naar_marktplaats():
    mod, db = _laad(), FakeDb()
    db.tabellen["listings"][0].update(platform="marktplaats", platform_listing_id="m2459776391")
    uit = _draai(mod, db)
    assert uit[0]["status"] == "queued"
    [job] = db.tabellen["jobs"]
    assert (job["platform"], job["action"]) == ("marktplaats", "content_refresh")
    assert job["payload"]["_prijs_bijwerken"] and job["payload"]["platform_listing_id"] == "m2459776391"


def test_voor_de_wijziging_was_marktplaats_unsupported():
    mod, db = _laad("f53be0d3"), FakeDb()
    db.tabellen["listings"][0].update(platform="marktplaats", platform_listing_id="m2459776391")
    assert _draai(mod, db)[0]["status"] == "unsupported" and db.tabellen["jobs"] == []


def test_marktplaats_prijsopdracht_is_achtergrondwerk_en_wacht_op_de_versie():
    from backend.api.jobs import _is_2dh_bijwerking
    prijs = {"action": "content_refresh", "platform": "marktplaats", "payload": {"_prijs_bijwerken": True}}
    licht = {"action": "content_refresh", "platform": "marktplaats", "prijs_bijwerken": "true"}
    assert _is_2dh_bijwerking(prijs) and _is_2dh_bijwerking(licht)
    # een gewone herplaatsing/verversing op Marktplaats blijft gewoon werk
    assert not _is_2dh_bijwerking({"action": "content_refresh", "platform": "marktplaats", "payload": {}})
    assert not _is_2dh_bijwerking({"action": "create", "platform": "marktplaats", "payload": {"_prijs_bijwerken": True}})
