"""De aanmeldpagina belooft 50% korting alleen bij de link van een klant.

Waarom (29-10-2026, Amanda, the_cooking_mommy): register.html toonde "A friend
invited you, your first month is 50% off" bij ELKE opgeslagen code, ook bij een
creatorlink. Een creatorlink heeft geen owner_user_id en geeft dus geen
vriendenkorting (heeft_recht_op_vriendenkorting). Haar volgers kregen een belofte
die niet werd nagekomen.

Voor-en-na: op de oude code bestaat de route niet (404) en toont de pagina het
vak zodra er een code in localStorage staat.
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import referrals

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(referrals.router)
    return TestClient(app)


def _code(monkeypatch, rij):
    monkeypatch.setattr(referrals, "eigenaar_van_code", lambda c: rij)


def test_klantcode_toont_het_vak(client, monkeypatch):
    _code(monkeypatch, {"code": "jan", "kind": "customer", "owner_user_id": "u1", "active": True})
    assert client.get("/api/referrals/uitnodiging/jan").json() == {"korting": True}


def test_creatorcode_toont_het_vak_niet(client, monkeypatch):
    _code(monkeypatch, {"code": "the_cooking_mommy", "kind": "creator", "owner_user_id": None, "active": True})
    assert client.get("/api/referrals/uitnodiging/the_cooking_mommy").json() == {"korting": False}


def test_inactieve_of_onbekende_code_toont_het_vak_niet(client, monkeypatch):
    _code(monkeypatch, {"code": "jan", "kind": "customer", "owner_user_id": "u1", "active": False})
    assert client.get("/api/referrals/uitnodiging/jan").json() == {"korting": False}
    _code(monkeypatch, None)
    assert client.get("/api/referrals/uitnodiging/onbekend").json() == {"korting": False}


def test_ongeldige_code_en_storing_tonen_het_vak_niet(client, monkeypatch):
    assert client.get("/api/referrals/uitnodiging/a%20b!").json() == {"korting": False}

    def stuk(_c):
        raise RuntimeError("database weg")

    monkeypatch.setattr(referrals, "eigenaar_van_code", stuk)
    assert client.get("/api/referrals/uitnodiging/jan").json() == {"korting": False}


def test_pagina_toont_het_vak_alleen_na_antwoord_van_de_server():
    html = (ROOT / "frontend" / "register.html").read_text()
    assert "/api/referrals/uitnodiging/" in html
    # Het vak mag nergens meer direct open gaan op alleen een code in localStorage.
    for regel in html.splitlines():
        if "getElementById('uitnodiging').style.display = 'block'" in regel:
            assert "korting === true" in html.split(regel)[0].splitlines()[-1]
