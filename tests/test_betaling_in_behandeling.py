"""Een eerste SEPA-incasso na de proef duurt werkdagen. Zolang die betaling bij
Stripe op "processing" staat houdt Omnivaleur de toegang aan en toont het de
rustige melding in plaats van het slot.

Gemeten geval 07-09-2026 (amandahaas1979@gmail.com): proef afgelopen 5 sep,
eerste SEPA-incasso "in behandeling" bij Stripe met verwachte succesdatum 14 sep,
"Reden van weigering" leeg. Het account viel na 2 dagen bedenktijd op slot
terwijl de betaling gewoon onderweg was.
"""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone

from backend.services import billing as sb

NOW = datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def test_status_processing_geeft_toegang():
    sub = {
        "status": "payment_processing",
        "updated_at": _iso(NOW - timedelta(days=6)),
        "stripe_subscription_id": "sub_1",
    }
    verdict = sb.evaluate_access(sub)
    assert verdict["allowed"] is True
    assert verdict["reason"] == "payment_processing"


def test_processing_valt_na_de_bovengrens_alsnog_dicht():
    """Mist de afloop-webhook, dan mag de rij niet eeuwig gratis toegang geven."""
    sub = {
        "status": "payment_processing",
        "updated_at": _iso(NOW - timedelta(days=sb.PROCESSING_GRACE_DAYS + 3)),
        "stripe_subscription_id": "sub_1",
    }
    assert sb.evaluate_access(sub)["allowed"] is False


def test_zelfheling_bij_lopende_incasso(monkeypatch):
    """Verlopen proef, afloop-webhook nog niet aangekomen: check_access vraagt
    Stripe na en laat de klant er alsnog door."""
    verlopen = {
        "status": "trialing",
        "trial_ends_at": _iso(NOW - timedelta(days=4)),
        "stripe_subscription_id": "sub_1",
    }
    monkeypatch.setattr(sb, "_fetch_subscription", lambda uid: verlopen)
    monkeypatch.setattr(sb, "_subscription_awaiting_incasso", lambda sid: True)

    verdict = asyncio.run(sb.check_access("u1", "klant@example.nl"))
    assert verdict["allowed"] is True
    assert verdict["reason"] == "payment_processing"


def test_zonder_lopende_incasso_blijft_het_slot(monkeypatch):
    verlopen = {
        "status": "trialing",
        "trial_ends_at": _iso(NOW - timedelta(days=9)),
        "stripe_subscription_id": "sub_1",
    }
    monkeypatch.setattr(sb, "_fetch_subscription", lambda uid: verlopen)
    monkeypatch.setattr(sb, "_subscription_awaiting_incasso", lambda sid: False)

    assert asyncio.run(sb.check_access("u1", "klant@example.nl"))["allowed"] is False


def _fake_stripe(monkeypatch, pi_status):
    class Subscription:
        @staticmethod
        def retrieve(sid, **kw):
            return {"latest_invoice": {"payment_intent": {"status": pi_status}}}

    monkeypatch.setitem(sys.modules, "stripe", types.SimpleNamespace(Subscription=Subscription))
    monkeypatch.setattr(sb.settings, "stripe_secret_key", "sk_test", raising=False)
    sb._processing_cache.clear()


def test_stripe_navraag_herkent_processing(monkeypatch):
    _fake_stripe(monkeypatch, "processing")
    assert sb._subscription_awaiting_incasso("sub_1") is True


def test_stripe_navraag_herkent_mislukte_incasso(monkeypatch):
    _fake_stripe(monkeypatch, "requires_payment_method")
    assert sb._subscription_awaiting_incasso("sub_1") is False


def test_webhook_zet_lopende_incasso_niet_op_wanbetaling(monkeypatch):
    import backend.api.billing as bapi

    stripe_sub = {
        "id": "sub_1",
        "status": "past_due",
        "latest_invoice": {"payment_intent": {"status": "processing"}},
    }
    assert bapi._incasso_loopt_nog(stripe_sub) is True

    stripe_sub["latest_invoice"]["payment_intent"]["status"] = "requires_payment_method"
    assert bapi._incasso_loopt_nog(stripe_sub) is False
