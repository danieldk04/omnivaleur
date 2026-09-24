"""Het meldpunt voor ontbrekende vertalingen: bewaart, telt, en loopt nooit vol.

frontend/i18n.js meldt Engelse zinnen die het woordenboek niet kent aan
/api/i18n/ontbrekend. Dat mag de gebruiker nooit iets kosten (geen fout, geen
wachttijd) en mag de tabel niet onbegrensd laten groeien.
"""
from fastapi.testclient import TestClient

from backend.api import i18n as meldpunt
from backend.main import app


class _Tabel:
    def __init__(self, opslag):
        self.opslag = opslag
        self._naam = None

    def select(self, *_):
        return self

    def eq(self, _veld, naam):
        self._naam = naam
        return self

    def upsert(self, rij, on_conflict=None):
        self.opslag[rij["naam"]] = rij["inhoud"]
        return self

    def execute(self):
        class R:
            data = []
        r = R()
        if self._naam in self.opslag:
            r.data = [{"inhoud": self.opslag[self._naam]}]
        return r


class _Db:
    def __init__(self):
        self.opslag = {}

    def table(self, _naam):
        return _Tabel(self.opslag)


def _client(monkeypatch, db):
    monkeypatch.setattr(meldpunt, "get_admin_db", lambda: db)
    monkeypatch.setattr(meldpunt, "execute_with_retry", lambda q: q.execute())
    return TestClient(app)


def test_meldt_en_telt(monkeypatch):
    db = _Db()
    c = _client(monkeypatch, db)
    body = {"taal": "nl", "pagina": "/app", "teksten": [{"tekst": "Something new here", "plek": "item-meta"}]}
    assert c.post("/api/i18n/ontbrekend", json=body).status_code == 204
    assert c.post("/api/i18n/ontbrekend", json=body).status_code == 204
    rij = db.opslag[meldpunt.SLEUTEL]["Something new here"]
    assert rij["aantal"] == 2 and rij["pagina"] == "/app" and rij["plek"] == "item-meta"


def test_loopt_niet_vol(monkeypatch):
    db = _Db()
    db.opslag[meldpunt.SLEUTEL] = {f"zin {i}": {"aantal": 1} for i in range(meldpunt.MAX_ZINNEN)}
    c = _client(monkeypatch, db)
    c.post("/api/i18n/ontbrekend", json={"teksten": [{"tekst": "Nog een zin"}]})
    assert "Nog een zin" not in db.opslag[meldpunt.SLEUTEL]
    assert len(db.opslag[meldpunt.SLEUTEL]) == meldpunt.MAX_ZINNEN


def test_database_weg_is_geen_fout(monkeypatch):
    def kapot():
        raise RuntimeError("database weg")
    monkeypatch.setattr(meldpunt, "get_admin_db", kapot)
    c = TestClient(app)
    r = c.post("/api/i18n/ontbrekend", json={"teksten": [{"tekst": "Iets"}]})
    assert r.status_code == 204


def test_te_veel_in_een_keer_wordt_geweigerd(monkeypatch):
    c = _client(monkeypatch, _Db())
    r = c.post("/api/i18n/ontbrekend", json={"teksten": [{"tekst": f"z{i}"} for i in range(41)]})
    assert r.status_code == 422
