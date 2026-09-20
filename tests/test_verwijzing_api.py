"""De verwijspagina over de echte HTTP-weg, niet alleen de losse functies.

Een unittest kan slagen terwijl het scherm een 500 krijgt: een vergeten route,
een veld dat anders heet dan de app verwacht, een afhankelijkheid die alleen in
de server bestaat. Daarom gaan deze proeven door FastAPI heen, precies zoals de
browser dat doet.
"""
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_verwijzing_gratis_maand import NepDb


GEBRUIKER = types.SimpleNamespace(id="u1", email="daniel@gmail.com")


@pytest.fixture()
def klant(monkeypatch):
    from backend.api import referrals
    from backend.services import referral_codes, referral_rewards

    db = NepDb(referral_codes=[], referrals=[], referral_clicks=[],
               referral_rewards=[], subscriptions=[{"user_id": "u1", "status": "trialing"}])
    for mod in (referrals, referral_codes, referral_rewards):
        monkeypatch.setattr(mod, "get_db", lambda: db, raising=False)
    monkeypatch.setattr(referrals, "email_van", lambda uid: f"{uid}@example.nl")
    monkeypatch.setattr(referrals, "_tegoed_eur", lambda uid: None)

    app = FastAPI()
    app.include_router(referrals.router)
    app.dependency_overrides[referrals.get_current_user_full] = lambda: GEBRUIKER
    return TestClient(app), db


def test_eigen_link_komt_terug_met_alles_erop(klant):
    client, db = klant
    r = client.get("/api/referrals/me")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert body["code"] == "daniel"
    assert body["link"] == "https://omnivaleur.com/r/daniel"
    assert body["reward_months"] == 1
    assert body["friend_discount_percent"] == 50
    assert body["stats"] == {"clicks": 0, "signups": 0, "trial": 0, "paying": 0, "months_earned": 0}
    assert body["friends"] == []


def test_de_hele_keten_klik_aanmelding_status(klant, monkeypatch):
    """Klik geteld, aanmelding gekoppeld, en de aanbrenger ziet het terug."""
    client, db = klant
    client.get("/api/referrals/me")                      # code aanmaken

    # 1. iemand klikt op de link
    klik = client.get("/r/daniel", follow_redirects=False,
                      headers={"accept-language": "en-GB,en;q=0.9"})
    assert klik.status_code == 302
    assert klik.headers["location"] == "https://omnivaleur.com/index.html?ref=daniel"
    assert len(db.data["referral_clicks"]) == 1

    # een Nederlandse bezoeker krijgt de Nederlandse pagina
    nl = client.get("/r/daniel", follow_redirects=False,
                    headers={"accept-language": "nl-NL,nl;q=0.9"})
    assert nl.headers["location"] == "https://omnivaleur.com/nl.html?ref=daniel"

    # 2. hij meldt zich aan met die code (dit doet /api/auth/register)
    from backend.api import referrals
    referrals.registreer_verwijzing("u2", "daniel")
    assert db.data["referrals"][0]["user_id"] == "u2"

    # 3. hij gaat betalen
    db.data["subscriptions"].append({"user_id": "u2", "status": "active",
                                     "stripe_subscription_id": "sub_2"})

    body = client.get("/api/referrals/me").json()
    assert body["stats"]["clicks"] == 2
    assert body["stats"]["signups"] == 1
    assert body["stats"]["paying"] == 1
    assert body["friends"][0]["status"] == "paying"
    assert body["friends"][0]["name"] == "u***@example.nl", "nooit het hele adres"


def test_onbekende_code_koppelt_niemand(klant):
    """Een verzonnen code mag geen aanmelding aan iemand hangen."""
    client, db = klant
    from backend.api import referrals
    referrals.registreer_verwijzing("u9", "bestaat-niet")
    assert db.data["referrals"] == []


def test_eigen_naam_kiezen_over_de_http_weg(klant):
    client, db = klant
    client.get("/api/referrals/me")
    r = client.post("/api/referrals/me/code", json={"code": "DK-Resell"})
    assert r.status_code == 200, r.text
    assert r.json()["link"] == "https://omnivaleur.com/r/dk-resell"

    # en de oude link blijft werken
    oud = client.get("/r/daniel", follow_redirects=False)
    assert oud.status_code == 302
    assert client.get("/api/referrals/me").json()["code"] == "dk-resell"


def test_een_onmogelijke_naam_geeft_een_leesbare_fout(klant):
    client, _ = klant
    r = client.post("/api/referrals/me/code", json={"code": "login"})
    assert r.status_code == 400
    assert "reserved" in r.json()["detail"].lower()


def test_zonder_tabellen_zegt_het_scherm_wat_eraan_scheelt(monkeypatch):
    """Draait de migratie nog niet, dan mag de pagina geen nullen tonen: dat
    leest als "er heeft nog nooit iemand geklikt"."""
    from backend.api import referrals
    from backend.services import referral_codes

    class Stuk:
        def table(self, _naam):
            raise RuntimeError('relation "referral_codes" does not exist')

    monkeypatch.setattr(referral_codes, "get_db", lambda: Stuk())
    monkeypatch.setattr(referrals, "get_db", lambda: Stuk())

    app = FastAPI()
    app.include_router(referrals.router)
    app.dependency_overrides[referrals.get_current_user_full] = lambda: GEBRUIKER
    r = TestClient(app).get("/api/referrals/me")

    assert r.status_code == 503
    assert "referrals_gebruikers.sql" in r.json()["detail"]


def test_de_korte_vraag_van_de_dashboardkaart_doet_geen_extra_werk(klant, monkeypatch):
    """De kaart wordt bij ELKE keer openen van de app opgehaald. Zou die ook de
    namen en het Stripe-tegoed ophalen, dan betaalt iedereen bij elke start voor
    iets wat alleen op het verwijsscherm te zien is."""
    from backend.api import referrals

    client, db = klant
    client.get("/api/referrals/me")
    referrals.registreer_verwijzing("u2", "daniel")

    gevraagd = []
    monkeypatch.setattr(referrals, "email_van", lambda uid: gevraagd.append(uid) or "x@y.nl")
    monkeypatch.setattr(referrals, "_tegoed_eur",
                        lambda uid: pytest.fail("Stripe hoort hier niet gevraagd te worden"))

    body = client.get("/api/referrals/me?compact=1").json()

    assert body["compact"] is True
    assert body["stats"]["signups"] == 1, "de tellers moeten er wel staan"
    assert body["link"].endswith("/r/daniel")
    assert body["friends"] == []
    assert gevraagd == [], "geen enkele naam opgezocht"
