from unittest.mock import MagicMock, patch

from backend.api import billing


def _db(referral_rows):
    db = MagicMock()
    res = MagicMock()
    res.data = referral_rows
    return db, res


def _run(rows, code_rij):
    db, res = _db(rows)
    with patch.object(billing, "get_db", return_value=db), \
         patch("backend.database.execute_with_retry", return_value=res), \
         patch("backend.services.referral_codes.eigenaar_van_code", return_value=code_rij):
        return billing.proefdagen_voor("u1")


def test_vriend_krijgt_14():
    assert _run([{"code": "abc"}], {"kind": "user", "owner_user_id": "u2"}) == 14


def test_creatorcode_blijft_7():
    assert _run([{"code": "abc"}], {"kind": "creator", "owner_user_id": None}) == 7


def test_geen_verwijzing_is_7():
    assert _run([], None) == 7


def test_eigen_code_is_7():
    assert _run([{"code": "abc"}], {"kind": "user", "owner_user_id": "u1"}) == 7


def test_fout_is_7():
    with patch.object(billing, "get_db", side_effect=RuntimeError("x")):
        assert billing.proefdagen_voor("u1") == 7
