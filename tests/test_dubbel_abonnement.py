"""Twee keer op 'Activate Pro' drukken mag geen tweede abonnement opleveren.

Gemeten geval 24-08-2026: dezelfde klant kreeg twee actieve abonnementen op
dezelfde rekening en betaalde twee keer 19,99 per maand.
"""
import sys
import types

import pytest


@pytest.fixture()
def billing(monkeypatch):
    import backend.api.billing as b
    return b


def _fake_stripe(monkeypatch, billing, subs):
    class Subscription:
        @staticmethod
        def list(**kw):
            return types.SimpleNamespace(data=subs)

    class Sessions:
        aangemaakt = []

        @staticmethod
        def create(**kw):
            Sessions.aangemaakt.append(kw)
            return types.SimpleNamespace(url="https://checkout.example/nieuw")

    class Portal:
        @staticmethod
        def create(**kw):
            return types.SimpleNamespace(url="https://portal.example/klant")

    monkeypatch.setattr(billing.stripe, "Subscription", Subscription, raising=False)
    monkeypatch.setattr(billing.stripe.checkout, "Session", Sessions, raising=False)
    monkeypatch.setattr(billing.stripe, "billing_portal",
                        types.SimpleNamespace(Session=Portal), raising=False)
    return Sessions


def test_lopend_abonnement_wordt_herkend(billing, monkeypatch):
    _fake_stripe(monkeypatch, billing, [{"id": "sub_1", "status": "active"}])
    assert billing.bestaand_abonnement("cus_1") == "sub_1"


def test_incomplete_telt_ook_mee(billing, monkeypatch):
    """SEPA duurt dagen; juist in dat gat klikte de klant nog eens."""
    _fake_stripe(monkeypatch, billing, [{"id": "sub_2", "status": "incomplete"}])
    assert billing.bestaand_abonnement("cus_1") == "sub_2"


def test_opgezegd_abonnement_blokkeert_niet(billing, monkeypatch):
    _fake_stripe(monkeypatch, billing, [{"id": "sub_3", "status": "canceled"}])
    assert billing.bestaand_abonnement("cus_1") is None


def test_zonder_klantnummer_geen_navraag(billing):
    assert billing.bestaand_abonnement(None) is None


def test_storing_bij_stripe_blokkeert_nieuwe_klant_niet(billing, monkeypatch):
    class Subscription:
        @staticmethod
        def list(**kw):
            raise RuntimeError("stripe plat")

    monkeypatch.setattr(billing.stripe, "Subscription", Subscription, raising=False)
    assert billing.bestaand_abonnement("cus_1") is None


def test_checkout_stuurt_naar_portaal_bij_lopend_abonnement(billing, monkeypatch):
    sessions = _fake_stripe(monkeypatch, billing, [{"id": "sub_1", "status": "active"}])
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_1", raising=False)
    monkeypatch.setattr(billing, "_get_or_create_subscription",
                        lambda uid: {"user_id": uid, "stripe_customer_id": "cus_1",
                                     "status": "active", "trial_ends_at": None})

    user = types.SimpleNamespace(id="u1", email="klant@example.nl")
    uitkomst = billing.create_checkout.__wrapped__(user) if hasattr(
        billing.create_checkout, "__wrapped__") else billing.create_checkout(user)

    assert uitkomst["already_subscribed"] is True
    assert uitkomst["url"] == "https://portal.example/klant"
    assert sessions.aangemaakt == [], "er mag geen tweede betaalpagina gemaakt zijn"
