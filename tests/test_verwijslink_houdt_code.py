"""Een verwijslink (/r/CODE) moet de code tot op de landingspagina houden.

Waarom (14-11-2026, creator Janina, code janina_no): /r/CODE stuurde door naar
/index.html?ref=CODE. Sinds 24-09-2026 stuurt /index.html met een vaste 301 door
naar "/", zonder de zoekstring. ref.js zag dus nooit een ?ref=, het aanmelden
stuurde nooit een code mee, en de tabel referrals bleef leeg: 0 koppelingen op
92 kliks, ook de klik van Janina een minuut voor haar aanmelding.

Voor-en-na: op de oude code eindigt de keten op "/" zonder ref.
"""
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient


class _NepTabel:
    def insert(self, *_a, **_k):
        return self


class _NepDb:
    def table(self, _naam):
        return _NepTabel()


@pytest.fixture
def client(monkeypatch):
    from backend import main
    from backend.api import referrals
    monkeypatch.setattr(referrals, "get_db", lambda: _NepDb())
    monkeypatch.setattr(referrals, "execute_with_retry", lambda q: None)
    return TestClient(main.app, base_url="https://omnivaleur.com")


def _volg(client, pad, taal):
    """Volg de doorverwijzingen zelf, tot een pagina die geen 30x meer geeft."""
    url = pad
    for _ in range(5):
        r = client.get(url, headers={"accept-language": taal}, follow_redirects=False)
        if r.status_code not in (301, 302, 307, 308):
            return url
        loc = r.headers["location"]
        u = urlparse(loc)
        url = u.path + (f"?{u.query}" if u.query else "")
    raise AssertionError("te veel doorverwijzingen")


@pytest.mark.parametrize("taal,pad", [("de-DE,de;q=0.9", "/"), ("nl-NL,nl;q=0.9", "/nl")])
def test_creatorlink_houdt_code_tot_de_landingspagina(client, taal, pad):
    eind = _volg(client, "/r/janina_no", taal)
    u = urlparse(eind)
    assert u.path == pad
    assert parse_qs(u.query).get("ref") == ["janina_no"]


def test_oude_html_adressen_houden_de_zoekstring(client):
    r = client.get("/index.html?ref=abc&utm_source=x", follow_redirects=False)
    assert r.status_code == 301
    u = urlparse(r.headers["location"])
    assert u.path == "/"
    assert parse_qs(u.query) == {"ref": ["abc"], "utm_source": ["x"]}
