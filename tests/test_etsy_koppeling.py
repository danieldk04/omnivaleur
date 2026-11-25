"""Etsy OAuth: ondertekende state, PKCE S256 en niets in de URL dat niet hoort."""
import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest

from backend.config import settings
from backend.platforms import etsy


@pytest.fixture(autouse=True)
def sleutels(monkeypatch):
    monkeypatch.setattr(settings, "etsy_api_keystring", "testkey123")
    monkeypatch.setattr(settings, "etsy_shared_secret", "geheim-voor-test")


def test_state_rondreis_en_vervalsing():
    state = etsy.maak_state("user-1", nu=1000)
    assert etsy.lees_state(state, nu=1100) == "user-1"
    with pytest.raises(ValueError):
        etsy.lees_state(state[:-2] + "xx", nu=1100)
    with pytest.raises(ValueError):
        etsy.lees_state(state.replace("user-1", "user-2"), nu=1100)
    with pytest.raises(ValueError):
        etsy.lees_state(state, nu=1000 + etsy.STATE_GELDIG_SECONDEN + 1)


def test_autorisatie_url_gebruikt_s256_en_toont_geen_secret():
    url = etsy.EtsyPlatform().get_authorization_url("user-1")
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"]
    assert q["client_id"] == ["testkey123"]
    assert "geheim-voor-test" not in url
    verifier = etsy._verifier(q["state"][0])
    verwacht = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert q["code_challenge"] == [verwacht]
    assert 43 <= len(verifier) <= 128
    for scope in ("listings_r", "listings_w", "listings_d", "transactions_r", "shops_r"):
        assert scope in q["scope"][0]


def test_zonder_sleutels_een_duidelijke_fout(monkeypatch):
    monkeypatch.setattr(settings, "etsy_api_keystring", "")
    monkeypatch.setattr(settings, "etsy_shared_secret", "")
    monkeypatch.delenv("ETSY_CLIENT_ID", raising=False)
    with pytest.raises(RuntimeError):
        etsy.EtsyPlatform().get_authorization_url("user-1")
