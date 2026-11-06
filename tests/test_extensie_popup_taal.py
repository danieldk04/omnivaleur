"""Elke tekst in het uitklapvenster van de extensie heeft een Nederlandse versie.

Daniel, 06-11-2026: de extensie ook in Nederlands en Engels. Deze proef faalt zodra
iemand een tekst toevoegt met data-t of t("...") zonder vertaling.
"""
import re
from pathlib import Path

EXT = Path(__file__).resolve().parent.parent / "extension"
HTML = (EXT / "popup.html").read_text(encoding="utf-8")
JS = (EXT / "popup.js").read_text(encoding="utf-8")
TAAL = (EXT / "popup-taal.js").read_text(encoding="utf-8")


def _heeft(tekst):
    return (repr(tekst)[1:-1] in TAAL or tekst.replace('"', '\\"') in TAAL)


def test_vaste_tekst_heeft_nederlands():
    teksten = re.findall(r"<[a-z0-9]+[^>]*\bdata-t\b[^>]*>(.*?)</(?:div|span|b|label|button|strong)>", HTML, re.S)
    assert len(teksten) >= 15
    for t in teksten:
        assert _heeft(t.strip()), t


def test_tekst_uit_het_script_heeft_nederlands():
    teksten = re.findall(r'\bt\("((?:[^"\\\\]|\\\\.)+)"', JS)
    assert len(teksten) >= 6
    for t in teksten:
        assert t in TAAL, t


def test_elementen_van_het_script_bestaan_nog():
    for i in ("loginBtn", "logoutBtn", "email", "password", "authStatus", "loggedIn", "loggedOut",
              "readyBadge", "userInfo", "kanaalUit", "calmModeToggle", "admarktToggle", "toetsToggle",
              "admarktUitleg", "siteToegangBlok", "siteToegangKnop"):
        assert f'id="{i}"' in HTML, i
