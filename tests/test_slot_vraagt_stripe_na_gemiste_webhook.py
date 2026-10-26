"""Een gemiste Stripe-webhook mag een betalende klant niet buitensluiten.

Zilverwebsite (26cf5471, 26-10-2026): Stripe verlengde het abonnement op 24-10
tot 24-11, maar onze server weigerde elke aflevering met 400. De rij bleef op
current_period_end 24-10 staan en na de bedenktijd zei het slot "geen betaling".
"""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone

from backend.services import billing as sb

NOW = datetime.now(timezone.utc)


def _rij():
    # Zoals de echte rij van 26cf5471: active, periode drie dagen voorbij.
    return {"id": "r1", "user_id": "u1", "status": "active", "plan": "pro",
            "stripe_subscription_id": "sub_1",
            "current_period_end": (NOW - timedelta(days=3)).isoformat()}


class _NepDb:
    def __init__(self):
        self.updates = []

    def table(self, naam):
        db = self

        class Q:
            def update(self, velden):
                db.updates.append((naam, velden))
                return self

            def eq(self, *a):
                return self

            def execute(self):
                return types.SimpleNamespace(data=[])
        return Q()


def _zet(monkeypatch, stripe_status, einde):
    class Subscription:
        @staticmethod
        def retrieve(sid, **kw):
            # Vorm van API-versie 2026-06-24.dahlia: einde op het item.
            return {"id": sid, "status": stripe_status, "latest_invoice": None,
                    "items": {"data": [{"current_period_end": int(einde.timestamp()),
                                        "price": {"id": "price_pro"}}]}}
    monkeypatch.setitem(sys.modules, "stripe", types.SimpleNamespace(Subscription=Subscription))
    monkeypatch.setattr(sb.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(sb, "_fetch_subscription", lambda uid: _rij())
    monkeypatch.setattr(sb, "_subscription_awaiting_incasso", lambda sid: False)
    db = _NepDb()
    monkeypatch.setattr(sb, "get_db", lambda: db)
    sb._bevestigd_cache.clear()
    return db


def test_stripe_zegt_loopt_dus_toegang_en_rij_rechtgezet(monkeypatch):
    db = _zet(monkeypatch, "active", NOW + timedelta(days=29))
    verdict = asyncio.run(sb.check_access("u1", "klant@example.nl"))
    assert verdict["allowed"] is True
    assert db.updates and db.updates[0][0] == "subscriptions"
    assert db.updates[0][1]["current_period_end"] > NOW.isoformat()


def test_stripe_zegt_opgezegd_dus_slot_blijft(monkeypatch):
    db = _zet(monkeypatch, "canceled", NOW + timedelta(days=29))
    assert asyncio.run(sb.check_access("u1", "klant@example.nl"))["allowed"] is False
    assert db.updates == []


def test_stripe_periode_ook_voorbij_dus_slot_blijft(monkeypatch):
    db = _zet(monkeypatch, "active", NOW - timedelta(days=1))
    assert asyncio.run(sb.check_access("u1", "klant@example.nl"))["allowed"] is False
    assert db.updates == []
