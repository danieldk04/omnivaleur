"""Aanmelden: het optionele antwoord op 'Waar hoorde je van ons?' gaat mee als
user_metadata.signup_bron, maar alleen als het een bekende waarde is."""
import asyncio
from types import SimpleNamespace

from backend.api import auth


class _Auth:
    def __init__(self, opgeslagen):
        self.opgeslagen = opgeslagen

    def sign_up(self, payload):
        self.opgeslagen.append(payload)
        return SimpleNamespace(user=SimpleNamespace(id="u1"))


def _draai(monkeypatch, bron):
    opgeslagen = []
    client = SimpleNamespace(auth=_Auth(opgeslagen))
    monkeypatch.setattr(auth, "get_db", lambda: None)
    monkeypatch.setattr(auth, "verse_auth_client", lambda: client)
    monkeypatch.setattr(auth, "registreer_verwijzing", lambda *a, **k: None)
    asyncio.run(auth.register(auth.AuthRequest(email="a@b.nl", password="x" * 8, bron=bron)))
    return opgeslagen[0]


def test_bekende_bron_wordt_bewaard(monkeypatch):
    p = _draai(monkeypatch, "tiktok")
    assert p["options"]["data"] == {"signup_bron": "tiktok"}


def test_onbekende_of_lege_bron_wordt_genegeerd(monkeypatch):
    assert "data" not in _draai(monkeypatch, "iets-verzonnens")["options"]
    assert "data" not in _draai(monkeypatch, None)["options"]
