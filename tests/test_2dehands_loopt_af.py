"""De server plant verlengingen op aanwijzing van 2dehands zelf (Lynn, 11-10-2026).

listed_at is bij een geimporteerd 2dehands-zoekertje de importdatum. Het
verlengvenster (dag 22 tot 45) kwam daardoor te laat: bij Lynn (96e30080) waren
4 van 11 oude rijen al verlopen en gaf verlengen tien rode fouten. Sinds
extensie 1.0.383 stuurt elke verlenging de lijst "Loopt af" mee; de server zet
daar meteen verlengingen voor klaar en lijnt listed_at uit op het echte einde.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services import crosslist as cl  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.f, self.inn, self.op, self.v, self.gte_ = {}, {}, "select", None, {}

    def select(self, *_a, **_k): return self
    def update(self, v): self.op, self.v = "update", v; return self
    def insert(self, v): self.op, self.v = "insert", v; return self
    def eq(self, k, v): self.f[k] = v; return self
    def in_(self, k, v): self.inn[k] = list(v); return self
    def gte(self, k, v): self.gte_[k] = v; return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self

    def _waarde(self, r, k):
        if "." in k:
            a, b = k.split(".", 1)
            return (r.get(a) or {}).get(b)
        return r.get(k)

    def execute(self):
        bron = self.db.t.setdefault(self.tabel, [])
        if self.op == "insert":
            bron.append(dict(self.v))
            return type("R", (), {"data": [self.v]})()
        rijen = [r for r in bron
                 if all(self._waarde(r, k) == v for k, v in self.f.items())
                 and all(self._waarde(r, k) in v for k, v in self.inn.items())
                 and all(str(self._waarde(r, k) or "") >= v for k, v in self.gte_.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.v)
        return type("R", (), {"data": list(rijen)})()


class _DB:
    def __init__(self, **t): self.t = t
    def table(self, n): return _Q(self, n)


def _rij(nummer, item, uid="lynn", listed="2026-09-05T14:15:00+00:00"):
    return {"id": f"r-{nummer}", "item_id": item, "platform": "2dehands", "status": "active",
            "platform_listing_id": nummer, "platform_listing_url": f"https://www.2dehands.be/v/x/{nummer}",
            "listed_at": listed, "items": {"user_id": uid}}


def test_aflopend_zoekertje_krijgt_meteen_een_verlenging(monkeypatch):
    einde = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    db = _DB(listings=[_rij("m2229805595", "i1"), _rij("m2400000003", "i2")], jobs=[])
    monkeypatch.setattr(cl, "get_db", lambda: db)
    n = cl.verleng_aflopende_2dehands("lynn", [{"id": "m2229805595", "close": einde}], "i9")
    assert n == 1
    job = db.t["jobs"][0]
    assert (job["action"], job["item_id"], job["payload"]["_listing_row_id"]) == ("extend", "i1", "r-m2229805595")
    # listed_at volgt nu het echte einde: 25 dagen geleden, dus in het venster.
    start = datetime.fromisoformat(db.t["listings"][0]["listed_at"])
    assert abs((datetime.fromisoformat(einde) - start).days - 28) <= 0
    assert db.t["listings"][1]["listed_at"].startswith("2026-09-05"), "niet aflopend: ongemoeid"


def test_geen_dubbele_verlenging_en_niet_van_een_ander(monkeypatch):
    db = _DB(listings=[_rij("m1111111", "i1"), _rij("m2222222", "i2", uid="ander")],
             jobs=[{"user_id": "lynn", "item_id": "i1", "platform": "2dehands",
                    "action": "extend", "status": "pending"}])
    monkeypatch.setattr(cl, "get_db", lambda: db)
    n = cl.verleng_aflopende_2dehands("lynn", [{"id": "m1111111"}, {"id": "m2222222"}])
    assert n == 0
    assert len(db.t["jobs"]) == 1


def test_verkocht_artikel_wordt_niet_verlengd(monkeypatch):
    db = _DB(listings=[_rij("m1111111", "i1"),
                       {"item_id": "i1", "platform": "vinted", "status": "sold"}], jobs=[])
    monkeypatch.setattr(cl, "get_db", lambda: db)
    assert cl.verleng_aflopende_2dehands("lynn", [{"id": "m1111111"}]) == 0


def test_echt_einde_lijnt_listed_at_uit(monkeypatch):
    db = _DB(listings=[_rij("m1111111", "i1")])
    monkeypatch.setattr(cl, "get_db", lambda: db)
    assert cl.lijn_looptijd_uit("r-m1111111", "2026-11-01T10:00:00Z")
    assert db.t["listings"][0]["listed_at"] == "2026-10-04T10:00:00+00:00"
    assert not cl.lijn_looptijd_uit("r-m1111111", None)


def test_peiling_alleen_voor_nieuwe_extensie_en_een_keer_per_dag(monkeypatch):
    nu = datetime.now(timezone.utc).isoformat()
    db = _DB(extension_heartbeat=[
                 {"user_id": "lynn", "ext_version": "1.0.383", "last_seen": nu},
                 {"user_id": "oud", "ext_version": "1.0.380", "last_seen": nu}],
             listings=[_rij("m1111111", "i1"), _rij("m3333333", "i3", uid="oud")], jobs=[])
    monkeypatch.setattr(cl, "get_db", lambda: db)
    monkeypatch.setattr(cl, "_mag_nog_werken", lambda _u: True)
    from backend.services import instellingen
    monkeypatch.setattr(instellingen, "lees", lambda _u: {})
    assert cl._peil_aflopende_2dehands() == 1
    assert db.t["jobs"][0]["user_id"] == "lynn" and db.t["jobs"][0]["payload"]["_peiling"]
    db.t["jobs"][0]["created_at"] = nu
    assert cl._peil_aflopende_2dehands() == 0, "vandaag al een verlenging: geen tweede peiling"
