"""Commerciële herinneringen krijgen één kleine afmeldregel (zonder inlog), en
wie zich afmeldde krijgt ze niet meer. Dienstmail blijft onaangeroerd.
Aanleiding: 09-11-2026 vroeg een klant na de terughaalmail te stoppen en vond geen link."""
from types import SimpleNamespace

import pytest

from backend.services import email as email_mod


class _Tabel:
    def __init__(self, rijen):
        self.rijen = rijen

    def select(self, *_a, **_k):
        return self

    def eq(self, kolom, waarde):
        self.rijen = [r for r in self.rijen if r.get(kolom) == waarde]
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rijen)


def _nep_db(afgemeld):
    return SimpleNamespace(table=lambda naam: _Tabel([{"user_id": u} for u in afgemeld]))


@pytest.fixture
def verstuurd(monkeypatch):
    uit = []
    monkeypatch.setattr(email_mod.settings, "resend_api_key", "x")
    monkeypatch.setattr(email_mod.settings, "resend_from", "daniel@omnivaleur.nl")
    monkeypatch.setattr(email_mod.settings, "secret_key", "geheim-voor-test")

    def _nep(subject, body, recipient, reply_to, html=None, unsubscribe_url=None):
        uit.append({"body": body, "html": html, "link": unsubscribe_url})
        return "id1"

    monkeypatch.setattr(email_mod, "_send_via_resend", _nep)
    return uit


def test_commerciele_mail_krijgt_regel_en_header_link(verstuurd, monkeypatch):
    monkeypatch.setattr("backend.database.get_admin_db", lambda: _nep_db([]))
    assert email_mod.send_email("Onderwerp", "Hallo", to="a@b.nl", afmelden_user_id="u1") is True
    m = verstuurd[0]
    assert "Afmelden / Unsubscribe: https://omnivaleur.com/api/mail-verbinding/unsubscribe?u=u1&t=" in m["body"]
    assert m["link"].startswith("https://omnivaleur.com/api/mail-verbinding/unsubscribe?u=u1&t=")
    assert "inlog" not in m["body"].lower() and "login" not in m["body"].lower()


def test_afgemelde_gebruiker_krijgt_niets(verstuurd, monkeypatch):
    monkeypatch.setattr("backend.database.get_admin_db", lambda: _nep_db(["u1"]))
    assert email_mod.send_email("Onderwerp", "Hallo", to="a@b.nl", afmelden_user_id="u1") is False
    assert verstuurd == []


def test_dienstmail_zonder_user_id_blijft_ongewijzigd(verstuurd):
    assert email_mod.send_email("Onderwerp", "Hallo", to="a@b.nl") is True
    assert verstuurd[0]["body"] == "Hallo" and verstuurd[0]["link"] is None


def test_html_krijgt_regel_voor_de_body_sluit(verstuurd, monkeypatch):
    monkeypatch.setattr("backend.database.get_admin_db", lambda: _nep_db([]))
    email_mod.send_email("O", "Hallo", to="a@b.nl", html="<html><body><p>Hoi</p></body></html>",
                         afmelden_user_id="u1")
    h = verstuurd[0]["html"]
    assert h.index("Afmelden / Unsubscribe") < h.index("</body>")
