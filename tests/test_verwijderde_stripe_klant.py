"""Een klant die in Stripe is verwijderd mag het afrekenen niet blokkeren.

Gemeten 01-10-2026: de eigenaar ruimde zijn testklant op in Stripe, onze tabel
bewaarde het dode nummer en Pro activeren gaf "No such customer".
"""
import types

import pytest


@pytest.fixture()
def billing():
    import backend.api.billing as b
    return b


def _stripe(monkeypatch, billing, retrieve):
    class Customer:
        gemaakt = []

        @staticmethod
        def retrieve(cid):
            return retrieve(cid)

        @staticmethod
        def create(**kw):
            Customer.gemaakt.append(kw)
            return types.SimpleNamespace(id="cus_NIEUW")

    class Sessions:
        args = []

        @staticmethod
        def create(**kw):
            Sessions.args.append(kw)
            if kw["customer"] != "cus_NIEUW":
                raise RuntimeError("No such customer: '%s'" % kw["customer"])
            return types.SimpleNamespace(url="https://checkout.example/nieuw")

    monkeypatch.setattr(billing.stripe, "Customer", Customer, raising=False)
    monkeypatch.setattr(billing.stripe, "Subscription",
                        types.SimpleNamespace(list=lambda **kw: types.SimpleNamespace(data=[])),
                        raising=False)
    monkeypatch.setattr(billing.stripe.checkout, "Session", Sessions, raising=False)
    return Customer, Sessions


def test_verwijderde_klant_telt_als_weg(billing, monkeypatch):
    _stripe(monkeypatch, billing, lambda cid: {"id": cid, "deleted": True})
    assert billing._levende_klant("cus_dood") is None


def test_onbekende_klant_telt_als_weg(billing, monkeypatch):
    def weg(cid):
        raise RuntimeError("No such customer: '%s'" % cid)
    _stripe(monkeypatch, billing, weg)
    assert billing._levende_klant("cus_dood") is None


def test_levende_klant_blijft(billing, monkeypatch):
    _stripe(monkeypatch, billing, lambda cid: {"id": cid})
    assert billing._levende_klant("cus_ok") == "cus_ok"


def test_storing_bij_stripe_houdt_nummer(billing, monkeypatch):
    def plat(cid):
        raise RuntimeError("timeout")
    _stripe(monkeypatch, billing, plat)
    assert billing._levende_klant("cus_ok") == "cus_ok"


def test_checkout_maakt_nieuwe_klant_bij_dood_nummer(billing, monkeypatch):
    klant, sessies = _stripe(monkeypatch, billing, lambda cid: {"id": cid, "deleted": True})
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_1", raising=False)
    monkeypatch.setattr(billing, "_get_or_create_subscription",
                        lambda uid: {"user_id": uid, "stripe_customer_id": "cus_dood",
                                     "status": "canceled", "trial_ends_at": None})
    monkeypatch.setattr(billing, "get_db", lambda: types.SimpleNamespace(
        table=lambda n: types.SimpleNamespace(
            update=lambda d: types.SimpleNamespace(
                eq=lambda *a: types.SimpleNamespace(execute=lambda: None)))))
    monkeypatch.setattr(billing, "find_active_promo", lambda: None)
    monkeypatch.setattr(billing, "heeft_recht_op_vriendenkorting", lambda uid: False)
    user = types.SimpleNamespace(id="u1", email="a@b.nl")
    out = billing.create_checkout(user=user, body={})
    assert out == {"url": "https://checkout.example/nieuw"}
    assert klant.gemaakt and sessies.args[-1]["customer"] == "cus_NIEUW"
