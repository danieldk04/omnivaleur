"""scripts/gratis_toegang.py: de beslisregel en dat het resultaat echt onbeperkt toegang geeft."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gratis_toegang as g  # noqa: E402
from backend.services.billing import evaluate_access  # noqa: E402

VERLOPEN = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()


def test_nog_geen_rij_wordt_gemaakt_en_geeft_toegang():
    wat, nieuw = g.plan(None)
    assert wat == "maak"
    assert evaluate_access(nieuw)["allowed"] is True


def test_verlopen_proef_wordt_gezet_en_geeft_toegang():
    rij = {"status": "trialing", "trial_ends_at": VERLOPEN, "stripe_subscription_id": None}
    assert evaluate_access(rij)["allowed"] is False          # voor: op slot
    wat, nieuw = g.plan(rij)
    assert wat == "zet"
    na = evaluate_access({**rij, **nieuw})
    assert na["allowed"] is True and na["reason"] == "complimentary"   # na


def test_betalend_account_wordt_geweigerd_en_complimentary_blijft_staan():
    assert g.plan({"status": "active", "stripe_subscription_id": "sub_1"})[0] == "weiger"
    assert g.plan({"status": "complimentary", "stripe_subscription_id": None})[0] == "niets"
