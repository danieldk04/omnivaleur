from unittest.mock import MagicMock, patch

from backend.config import settings
from backend.services import vriendenvoordeel as v


def _tel(abos, aan=True):
    v.vergeet()
    db = MagicMock()
    res_ref = MagicMock(); res_ref.data = [{"user_id": f"f{i}"} for i in range(len(abos))]
    res_abo = MagicMock(); res_abo.data = abos
    antwoorden = iter([res_ref, res_abo])
    with patch.object(settings, "referral_korting_aan", aan), \
         patch.object(v, "get_db", return_value=db), \
         patch.object(v, "execute_with_retry", side_effect=lambda q: next(antwoorden)), \
         patch("backend.services.referral_codes.codes_van", return_value=[{"code": "c"}]):
        n = v.betalende_vrienden("u1")
        assert v.heeft_ai_via_vrienden("u1") == (n >= 3)
        assert v.heeft_ultra_via_vrienden("u1") == (n >= 5)
        assert v.heeft_etsy_via_vrienden("u1") == (n >= 3)
        return n


def abo(plan="pro", status="active", sid="sub_1"):
    return {"user_id": "x", "status": status, "plan": plan, "stripe_subscription_id": sid}


def test_telt_alleen_betalend_pro_of_hoger():
    assert _tel([abo(), abo("plus"), abo("light"), abo(status="trialing"), abo(sid=None)]) == 2


def test_vlag_uit_is_nul():
    assert _tel([abo()] * 5, aan=False) == 0


def test_drempels():
    assert _tel([abo()] * 5) == 5
    assert v.heeft_ultra_via_vrienden("u1") is False


def test_storing_is_nul():
    v.vergeet()
    with patch.object(settings, "referral_korting_aan", True), \
         patch("backend.services.referral_codes.codes_van", side_effect=RuntimeError("x")):
        assert v.betalende_vrienden("u1") == 0


def test_etsy_op_drie_vrienden():
    assert _tel([abo()] * 2) == 2
    assert _tel([abo()] * 3) == 3
    assert _tel([abo(), abo(), abo("light")]) == 2
