"""Omnivaleur Light: EUR 9,99 incl. btw, tot 20 actieve artikelen.

De limiet moet op elk pad gelden waarlangs een artikel live kan gaan, en mag nooit
iemand beperken die Pro betaalt of bij wie onze eigen telling haperde.
"""
import types

import pytest

from backend.services import light


def _fake_db():
    """Legt vast wat er naar de database wordt weggeschreven."""
    geschreven = []

    class Q:
        def __init__(self, tabel):
            self.tabel = tabel

        def update(self, velden):
            geschreven.append((self.tabel, velden))
            return self

        def __getattr__(self, naam):
            return lambda *a, **k: self

        def execute(self):
            return types.SimpleNamespace(data=[])

    db = types.SimpleNamespace(table=lambda t: Q(t))
    db.geschreven = geschreven
    return db


def _met_artikelen(monkeypatch, plan, levend, online=None):
    monkeypatch.setattr(light, "plan_van_gebruiker", lambda uid: plan)

    def actief(db, uid, statussen=None):
        return set(online if statussen == light.ONLINE_STATUS and online is not None else levend)

    monkeypatch.setattr(light, "actieve_artikelen", actief)


def _vol(n):
    return {f"item{i}" for i in range(n)}


# ── plan uit Stripe ──────────────────────────────────────────────────────────

def test_light_prijs_geeft_plan_light(monkeypatch):
    monkeypatch.setattr(light.settings, "stripe_price_id_light", "price_light", raising=False)
    sub = {"items": {"data": [{"price": {"id": "price_light"}}]}}
    assert light.plan_uit_stripe(sub) == "light"


def test_pro_prijs_geeft_plan_pro(monkeypatch):
    monkeypatch.setattr(light.settings, "stripe_price_id_light", "price_light", raising=False)
    sub = {"items": {"data": [{"price": {"id": "price_pro"}}]}}
    assert light.plan_uit_stripe(sub) == "pro"


def test_zonder_ingestelde_light_prijs_is_iedereen_pro(monkeypatch):
    monkeypatch.setattr(light.settings, "stripe_price_id_light", "", raising=False)
    sub = {"items": {"data": [{"price": {"id": ""}}]}}
    assert light.plan_uit_stripe(sub) == "pro"


# ── publiceren ───────────────────────────────────────────────────────────────

def test_light_met_ruimte_mag_publiceren(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(19))
    assert light.publicatie_geblokkeerd(None, "u1", "nieuw") is None


def test_light_op_de_limiet_mag_geen_nieuw_artikel(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20))
    assert light.publicatie_geblokkeerd(None, "u1", "nieuw") == light.LIGHT_LIMIET_MELDING


def test_light_op_de_limiet_mag_bestaand_artikel_naar_extra_kanaal(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20))
    assert light.publicatie_geblokkeerd(None, "u1", "item3") is None


def test_pro_heeft_geen_limiet(monkeypatch):
    _met_artikelen(monkeypatch, "pro", _vol(500))
    assert light.publicatie_geblokkeerd(None, "u1", "nieuw") is None
    assert light.ruimte_over(None, "u1") is None


def test_storing_bij_het_tellen_laat_door(monkeypatch):
    monkeypatch.setattr(light, "plan_van_gebruiker", lambda uid: "light")

    def stuk(*a, **k):
        raise RuntimeError("database plat")

    monkeypatch.setattr(light, "actieve_artikelen", stuk)
    assert light.publicatie_geblokkeerd(None, "u1", "nieuw") is None
    assert light.ruimte_over(None, "u1") is None


def test_ruimte_over_telt_af(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(12))
    assert light.ruimte_over(None, "u1") == 8
    _met_artikelen(monkeypatch, "light", _vol(30))
    assert light.ruimte_over(None, "u1") == 0


# ── laatste zeef voor de extensie ────────────────────────────────────────────

def _job(**kw):
    return {"id": "j1", "action": "create", "item_id": "nieuw", "platform": "vinted", "payload": {}, **kw}


def test_zeef_neemt_nieuwe_plaatsing_terug_boven_limiet(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20), online=_vol(20))
    db = _fake_db()
    assert light.neem_plaatsing_terug_boven_limiet(db, "u1", _job()) is True
    assert any(t == "jobs" and v["status"] == "cancelled" for t, v in db.geschreven)


def test_zeef_laat_extra_kanaal_voor_draaiend_artikel_door(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20), online=_vol(20))
    assert light.neem_plaatsing_terug_boven_limiet(_fake_db(), "u1", _job(item_id="item1")) is False


def test_zeef_laat_verversen_door(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20), online=_vol(20))
    job = _job(payload={"_refresh_rollback": True})
    assert light.neem_plaatsing_terug_boven_limiet(_fake_db(), "u1", job) is False


def test_zeef_raakt_verwijderen_en_verlengen_niet_aan(monkeypatch):
    _met_artikelen(monkeypatch, "light", _vol(20), online=_vol(20))
    for actie in ("delete", "extend", "content_refresh"):
        assert light.neem_plaatsing_terug_boven_limiet(_fake_db(), "u1", _job(action=actie)) is False


def test_zeef_laat_pro_ongemoeid(monkeypatch):
    _met_artikelen(monkeypatch, "pro", _vol(500), online=_vol(500))
    assert light.neem_plaatsing_terug_boven_limiet(_fake_db(), "u1", _job()) is False


# ── afrekenen ────────────────────────────────────────────────────────────────

@pytest.fixture()
def billing():
    import backend.api.billing as b
    return b


def test_checkout_kiest_de_light_prijs(billing, monkeypatch):
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_pro", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id_light", "price_light", raising=False)
    assert billing._prijs_voor_plan("light") == ("light", "price_light")
    assert billing._prijs_voor_plan(None) == ("pro", "price_pro")
    assert billing._prijs_voor_plan("onzin") == ("pro", "price_pro")


def test_checkout_light_zonder_ingestelde_prijs_geeft_nooit_stil_pro(billing, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_pro", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id_light", "", raising=False)
    with pytest.raises(HTTPException) as e:
        billing._prijs_voor_plan("light")
    assert e.value.status_code == 503


def test_checkout_stuurt_de_light_prijs_naar_stripe(billing, monkeypatch):
    aangemaakt = []

    class Sessions:
        @staticmethod
        def create(**kw):
            aangemaakt.append(kw)
            return types.SimpleNamespace(url="https://checkout.example/light")

    monkeypatch.setattr(billing.stripe.checkout, "Session", Sessions, raising=False)
    monkeypatch.setattr(billing.stripe, "Subscription",
                        types.SimpleNamespace(list=lambda **kw: types.SimpleNamespace(data=[])), raising=False)
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id", "price_pro", raising=False)
    monkeypatch.setattr(billing.settings, "stripe_price_id_light", "price_light", raising=False)
    monkeypatch.setattr(billing, "_get_or_create_subscription",
                        lambda uid: {"user_id": uid, "stripe_customer_id": "cus_1", "status": "trialing",
                                     "trial_ends_at": None})
    monkeypatch.setattr(billing, "find_active_promo", lambda: None)
    monkeypatch.setattr(billing, "heeft_recht_op_vriendenkorting", lambda uid: False)
    user = types.SimpleNamespace(id="u1", email="klant@example.nl")

    uit = billing.create_checkout(user, {"plan": "light"})
    assert uit["url"] == "https://checkout.example/light"
    assert aangemaakt[0]["line_items"] == [{"price": "price_light", "quantity": 1}]
    assert aangemaakt[0]["metadata"]["plan"] == "light"

    aangemaakt.clear()
    billing.create_checkout(user)
    assert aangemaakt[0]["line_items"] == [{"price": "price_pro", "quantity": 1}]
