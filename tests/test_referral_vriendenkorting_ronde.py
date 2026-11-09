"""De uurronde van de vriendenkorting: welke vrienden worden verwerkt en welke niet.

De Stripe-kant zelf (tegoed boeken, niet dubbel, terugdraaien) is bewezen in
testmodus: tests/proeven/stripe_proef_vriendenkorting.py. Deze tests bewijzen het
tussenstuk: de juiste mensen, de vlag, en dat één kapotte vriend de rest niet stopt.
"""
import asyncio

import pytest

from backend.services import referral_vriendenkorting as rv
from tests.test_verwijzing_gratis_maand import NepDb


def _db(extra_abos=None, code_eigenaar="u-a"):
    abos = [
        {"user_id": "u-a", "status": "active", "stripe_customer_id": "cus_a", "stripe_subscription_id": "sub_a"},
        {"user_id": "u-v", "status": "active", "stripe_customer_id": "cus_v", "stripe_subscription_id": "sub_v"},
    ] + (extra_abos or [])
    return NepDb(
        referrals=[{"user_id": "u-v", "code": "daniel"}],
        referral_codes=[{"code": "daniel", "kind": "user", "owner_user_id": code_eigenaar}],
        subscriptions=abos,
    )


class _Stripe:
    class Subscription:
        @staticmethod
        def retrieve(sub_id, **_kw):
            return {"items": {"data": [{"price": {"id": "price_pro", "unit_amount": 1999}, "quantity": 1}]}}


@pytest.fixture()
def ronde(monkeypatch):
    aanroepen = []
    monkeypatch.setattr(rv.settings, "referral_korting_aan", True, raising=False)
    monkeypatch.setattr(rv.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(rv.settings, "stripe_price_id_light", "price_light", raising=False)
    monkeypatch.setattr(rv, "stripe", _Stripe)
    monkeypatch.setattr(rv, "facturen_van_klant", lambda klant: [{"id": "in_1"}])
    monkeypatch.setattr(rv, "verwerk_vriend",
                        lambda **kw: aanroepen.append(kw) or {"toegekend": 999, "teruggedraaid": 0, "overgeslagen": 0})
    from backend.services import referral_rewards
    monkeypatch.setattr(referral_rewards, "_is_eigenaar", lambda uid: False)

    def zet(db):
        import backend.database as d
        monkeypatch.setattr(d, "get_db", lambda: db)
        return aanroepen
    return zet


def _draai():
    return asyncio.run(rv.verwerk_vriendenkorting())


def test_vlag_uit_doet_niets(ronde, monkeypatch):
    aanroepen = ronde(_db())
    monkeypatch.setattr(rv.settings, "referral_korting_aan", False, raising=False)
    assert _draai()["vrienden"] == 0 and aanroepen == []


def test_betalende_vriend_van_een_klant_wordt_verwerkt(ronde):
    aanroepen = ronde(_db())
    uit = _draai()
    assert uit["vrienden"] == 1 and uit["toegekend"] == 999
    kw = aanroepen[0]
    assert kw["aanbrenger_klant_id"] == "cus_a" and kw["vriend_id"] == "u-v"
    assert kw["vriend_plan"] == "pro" and kw["eigen_maandprijs_cents"] == 1999


def test_creatorcode_zonder_eigenaar_doet_niet_mee(ronde):
    aanroepen = ronde(_db(code_eigenaar=None))
    assert _draai()["vrienden"] == 0 and aanroepen == []


def test_zelfverwijzing_doet_niet_mee(ronde):
    aanroepen = ronde(_db(code_eigenaar="u-v"))
    assert _draai()["vrienden"] == 0 and aanroepen == []


def test_gratis_account_als_aanbrenger_krijgt_niets(ronde):
    db = _db()
    db.data["subscriptions"][0]["status"] = "complimentary"
    aanroepen = ronde(db)
    uit = _draai()
    assert uit["vrienden"] == 0 and uit["overgeslagen"] == 1 and aanroepen == []


def test_aanbrenger_zonder_stripe_klant_wordt_overgeslagen(ronde):
    db = _db()
    db.data["subscriptions"][0]["stripe_customer_id"] = None
    aanroepen = ronde(db)
    assert _draai()["overgeslagen"] == 1 and aanroepen == []


def test_light_vriend_wordt_als_light_doorgegeven(ronde, monkeypatch):
    class Light(_Stripe):
        class Subscription:
            @staticmethod
            def retrieve(sub_id, **_kw):
                prijs = "price_light" if sub_id == "sub_v" else "price_pro"
                return {"items": {"data": [{"price": {"id": prijs, "unit_amount": 999}, "quantity": 1}]}}
    aanroepen = ronde(_db())
    monkeypatch.setattr(rv, "stripe", Light)
    _draai()
    assert aanroepen[0]["vriend_plan"] == "light"


def test_een_kapotte_vriend_stopt_de_rest_niet(ronde, monkeypatch):
    db = _db(extra_abos=[{"user_id": "u-w", "status": "active", "stripe_customer_id": "cus_w",
                          "stripe_subscription_id": "sub_w"}])
    db.data["referrals"].append({"user_id": "u-w", "code": "daniel"})
    aanroepen = ronde(db)
    echte = rv.verwerk_vriend

    def soms_stuk(**kw):
        if kw["vriend_id"] == "u-v":
            raise RuntimeError("Stripe valt weg")
        return echte(**kw)
    monkeypatch.setattr(rv, "verwerk_vriend", soms_stuk)
    uit = _draai()
    assert uit["fout"] == 1 and uit["vrienden"] == 1
    assert [a["vriend_id"] for a in aanroepen] == ["u-w"]
