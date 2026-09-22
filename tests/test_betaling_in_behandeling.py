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


# ── De vorm van het antwoord van Stripe (gemeten 18-09-2026) ─────────────────
#
# Sinds API-versie 2026-06-24.dahlia staat `payment_intent` NIET meer op de
# factuur: hij hangt onder `payments`. Een `expand[]` van het oude veld geeft
# geen fout, het veld ontbreekt gewoon. Daarom draagt de nagebootste factuur
# hieronder dat oude veld met opzet niet: een kopie die het nog leest krijgt
# None en concludeert "geen incasso", en dan valt een klant die gewoon betaalt
# alsnog buiten de deur. Zie docs/kennisbank.md,
# "stripe-api-versie-verplaatst-velden".


def _fake_stripe(monkeypatch, pi_status):
    class Subscription:
        @staticmethod
        def retrieve(sid, **kw):
            return {"id": sid, "status": "past_due", "latest_invoice": "in_1"}

    class Invoice:
        @staticmethod
        def retrieve(iid, **kw):
            assert iid == "in_1", f"factuur zonder nummer opgevraagd: {iid!r}"
            return {"id": iid, "status": "open",
                    "payments": {"data": [{"payment": {"payment_intent": "pi_1"}}]}}

    class PaymentIntent:
        @staticmethod
        def retrieve(pid, **kw):
            return {"id": pid, "status": pi_status}

    nep = types.SimpleNamespace(Subscription=Subscription, Invoice=Invoice,
                                PaymentIntent=PaymentIntent)
    _zet_nep_stripe(monkeypatch, nep)


def _zet_nep_stripe(monkeypatch, nep):
    """Ook backend.api.billing zelf: die doet `import stripe` bovenin, en dan
    wijst zijn eigen naam nog naar de echte SDK als je alleen sys.modules
    omzet. Zonder dit meet een proef op de webhook de echte Stripe."""
    import backend.api.billing as bapi
    monkeypatch.setitem(sys.modules, "stripe", nep)
    monkeypatch.setattr(bapi, "stripe", nep, raising=False)
    monkeypatch.setattr(sb.settings, "stripe_secret_key", "sk_test", raising=False)
    sb._processing_cache.clear()


def test_stripe_navraag_herkent_processing(monkeypatch):
    _fake_stripe(monkeypatch, "processing")
    assert sb._subscription_awaiting_incasso("sub_1") is True


def test_stripe_navraag_herkent_mislukte_incasso(monkeypatch):
    _fake_stripe(monkeypatch, "requires_payment_method")
    assert sb._subscription_awaiting_incasso("sub_1") is False


def test_het_slot_vraagt_het_op_de_nieuwe_plek(monkeypatch):
    """DE MEETPROEF, 22-09-2026.

    `_subscription_awaiting_incasso` is de vraag die op het weiger-pad van
    check_access staat: zegt hij nee, dan ziet de klant het slot. Tot vandaag
    las hij `latest_invoice.payment_intent`, en dat veld bestaat sinds
    18-09-2026 niet meer. Uitkomst: altijd False, dus iedereen met een lopende
    SEPA-incasso werd buitengesloten terwijl het geld onderweg was.

    Deze proef geeft precies terug wat de echte API teruggeeft. Tegen de code
    van vóór de reparatie (commit 6765d602) valt hij om.
    """
    _fake_stripe(monkeypatch, "processing")
    assert sb._subscription_awaiting_incasso("sub_1") is True, (
        "een lopende incasso wordt niet meer herkend; de klant ziet het slot")


def test_webhook_en_slot_stellen_dezelfde_vraag(monkeypatch):
    """Eén functie voor allebei, zodat ze niet opnieuw uit elkaar lopen."""
    import backend.api.billing as bapi
    assert bapi.incasso_loopt_nog is sb.incasso_loopt_nog

    _fake_stripe(monkeypatch, "processing")
    stripe_sub = {"id": "sub_1", "status": "past_due", "latest_invoice": "in_1"}
    assert bapi._incasso_loopt_nog(stripe_sub) is True
    assert sb._subscription_awaiting_incasso("sub_1") is True


def test_webhook_zet_lopende_incasso_niet_op_wanbetaling(monkeypatch):
    import backend.api.billing as bapi

    _fake_stripe(monkeypatch, "processing")
    stripe_sub = {"id": "sub_1", "status": "past_due", "latest_invoice": "in_1"}
    assert bapi._incasso_loopt_nog(stripe_sub) is True

    _fake_stripe(monkeypatch, "requires_payment_method")
    assert bapi._incasso_loopt_nog(stripe_sub) is False


def test_een_storing_bij_stripe_blijft_een_nee(monkeypatch):
    """Kan de vraag niet gesteld worden, dan mag hij niet stil 'ja' worden: een
    Stripe-storing zou anders iedereen gratis toegang geven. Hij mag ook niet
    omvallen, want dan sneuvelt de hele webhook."""
    import backend.api.billing as bapi

    class Kapot:
        @staticmethod
        def retrieve(*a, **kw):
            raise RuntimeError("Stripe ligt plat")

    _zet_nep_stripe(monkeypatch, types.SimpleNamespace(
        Subscription=Kapot, Invoice=Kapot, PaymentIntent=Kapot))

    assert bapi._incasso_loopt_nog({"id": "sub_1", "latest_invoice": "in_1"}) is False
    assert sb._subscription_awaiting_incasso("sub_1") is False
