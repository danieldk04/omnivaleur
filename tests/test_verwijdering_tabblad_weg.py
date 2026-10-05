"""Verwijdering bevestigd, daarna was het tabblad weg: de server kijkt zelf na.

05-10-2026, klant 26cf5471. De extensie beantwoordde "Niet verkocht via
Marktplaats", het venster ging dicht, en daarna gaven alle drie de controles
"No tab with id". Geboekt als mislukt, de herplaatsing werd overgeslagen, en de
advertentie stond nergens meer (Marktplaats gaf 404/410).

De foutmelding hieronder is letterlijk die uit productie.

Draaien:  python3 -m pytest tests/test_verwijdering_tabblad_weg.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pytest

from backend.api import jobs

ECHT = (
    'Error: "Gouden oorbellen met granaat, 7 gram." cannot be found in your marktplaats listings '
    'overview, and the delete button on its own page (https://www.marktplaats.nl/seller/view/'
    'm2438638431) could not be used either. Nothing was removed — delete it by hand, or check '
    'that you are signed in to the right account. | Buttons on that page: niet gekeken | Diag: '
    '[{"fase":"bevestigen","stap":0,"clicked":true,"labels":["Close","Niet verkocht via Marktplaats",'
    '"Verkocht via Marktplaats"],"open":true,"picked":"Niet verkocht via Marktplaats","venstertekst":'
    '"Advertentie verwijderen Heb je \\"Gouden oorbellen met granaat, 7 gram.\\" verkocht via '
    'Marktplaats? Niet verkocht via Marktplaats Verkocht via Marktplaats"},{"fase":"bevestigen",'
    '"stap":1,"open":false},{"fase":"fetch-check","poging":0,"weg":false,"via":"exec-error","error":'
    '"Error: No tab with id: 2127177073"},{"fase":"fetch-check","poging":1,"weg":false,"via":'
    '"exec-error","error":"Error: No tab with id: 2127177073"},{"fase":"fetch-check","poging":2,'
    '"weg":false,"via":"exec-error","error":"Error: No tab with id: 2127177073"}] [extensie 1.0.368]'
)
JOB = {"action": "delete", "platform": "marktplaats",
       "payload": {"platform_listing_id": "m2438638431"}}


class _Antwoord:
    def __init__(self, status):
        self.status_code = status


@pytest.fixture
def kanaal(monkeypatch):
    def zet(status):
        gevraagd = []

        def get(url, **kw):
            gevraagd.append(url)
            if isinstance(status, Exception):
                raise status
            return _Antwoord(status)
        monkeypatch.setattr(httpx, "get", get)
        return gevraagd
    return zet


def test_echte_fout_en_pagina_weg_is_gelukt(kanaal):
    for status in (404, 410):
        gevraagd = kanaal(status)
        assert jobs._verwijdering_openbaar_bewezen(JOB, ECHT) is True
        assert gevraagd == ["https://www.marktplaats.nl/m2438638431"]


def test_pagina_staat_er_nog_blijft_mislukt(kanaal):
    kanaal(200)
    assert jobs._verwijdering_openbaar_bewezen(JOB, ECHT) is False


def test_storing_of_blokkade_is_geen_bewijs(kanaal):
    for status in (403, 429, 500, httpx.ConnectError("weg")):
        kanaal(status)
        assert jobs._verwijdering_openbaar_bewezen(JOB, ECHT) is False


def test_zonder_beantwoord_venster_niet_nakijken(kanaal):
    gevraagd = kanaal(404)
    assert jobs._verwijdering_openbaar_bewezen(JOB, ECHT.replace('"clicked":true', '"clicked":false')) is False
    assert gevraagd == []


def test_extensie_kreeg_zelf_een_antwoord_dan_telt_dat(kanaal):
    # Gaf het kanaal de extensie een 200, dan stond hij er nog: niet overrulen.
    gevraagd = kanaal(404)
    fout = ECHT.replace('"via":"exec-error","error":"Error: No tab with id: 2127177073"}]',
                        '"status":200,"via":"no-match"}]')
    assert jobs._verwijdering_openbaar_bewezen(JOB, fout) is False
    assert gevraagd == []


def test_alleen_verwijderingen_op_mp_en_2dehands(kanaal):
    kanaal(404)
    assert jobs._verwijdering_openbaar_bewezen({**JOB, "action": "create"}, ECHT) is False
    assert jobs._verwijdering_openbaar_bewezen({**JOB, "platform": "vinted"}, ECHT) is False
    assert jobs._verwijdering_openbaar_bewezen({**JOB, "payload": {}}, ECHT) is False
    assert jobs._verwijdering_openbaar_bewezen(JOB, "geen diagnostiek") is False


class _Vraag:
    """Een nep-database die elke vraag beantwoordt en elke wijziging onthoudt."""

    def __init__(self, db, tabel):
        self.db, self.tabel, self.wijziging = db, tabel, None

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def execute(self):
        if self.wijziging is not None:
            self.db.wijzigingen.append((self.tabel, self.wijziging))
            return type("R", (), {"data": []})()
        if self.tabel == "jobs":
            return type("R", (), {"data": [{"item_id": "i1", **JOB}]})()
        return type("R", (), {"data": []})()

    def __getattr__(self, _naam):
        return lambda *a, **kw: self


class _Db:
    def __init__(self):
        self.wijzigingen = []

    def table(self, naam):
        return _Vraag(self, naam)

    def rpc(self, *a, **kw):
        return _Vraag(self, "rpc")


def test_fail_job_boekt_de_echte_melding_als_gelukt(kanaal, monkeypatch):
    kanaal(410)
    db = _Db()
    monkeypatch.setattr(jobs, "get_db", lambda: db)
    monkeypatch.setattr(jobs, "_record_extension_heartbeat", lambda *a, **kw: None)
    try:
        jobs.fail_job("j1", {"error": ECHT}, user_id="26cf5471")
    except Exception:  # noqa: BLE001 — oude code mag verderop struikelen; de status telt
        pass
    statussen = [w.get("status") for t, w in db.wijzigingen if t == "jobs" and "status" in w]
    assert statussen and statussen[0] == "done", statussen
