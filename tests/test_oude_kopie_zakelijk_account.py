"""Een extensiekopie van vóór 1.0.332 krijgt bij een zakelijk account geen plaatsopdrachten.

GEMETEN 16-09-2026 (De Juiste Toon): Edge draaide 1.0.327 naast een bijgewerkte
browser. Die oude kopie leest zijn zakelijke 2dehands-account als uitgelogd, zette
de rij op pauze en annuleerde een lederhose die nooit geprobeerd was. Zie
_oude_kopie_leest_zakelijk_als_uitgelogd in backend/api/jobs.py.
"""
import pytest

from backend.api import jobs as J

CREATE_2DH = {"action": "create", "platform": "2dehands", "id": "x"}


@pytest.fixture
def zakelijk(monkeypatch):
    gevraagd = []

    def soort(db, user_id, platform):
        gevraagd.append(platform)
        return "TRADER"
    monkeypatch.setattr(J, "_verkoper_soort", soort)
    return gevraagd


def test_oude_kopie_krijgt_geen_plaatsing_bij_zakelijk_account(zakelijk):
    assert J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, (1, 0, 327))
    assert J._oude_kopie_leest_zakelijk_als_uitgelogd(
        None, "u", {**CREATE_2DH, "platform": "marktplaats", "action": "content_refresh"}, (1, 0, 331))


def test_bijgewerkte_of_onbekende_kopie_krijgt_hem_wel(zakelijk):
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, (1, 0, 332))
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, (1, 0, 336))
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, None)


def test_verwijderen_vinted_en_particulier_blijven_gewoon_lopen(zakelijk, monkeypatch):
    oud = (1, 0, 327)
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", {**CREATE_2DH, "action": "delete"}, oud)
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", {**CREATE_2DH, "platform": "vinted"}, oud)
    # Zonder reden geen opzoekwerk: dat is een netwerkvraag in de uitgifte.
    assert zakelijk == []
    monkeypatch.setattr(J, "_verkoper_soort", lambda db, u, p: "CONSUMER")
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, oud)
    monkeypatch.setattr(J, "_verkoper_soort", lambda db, u, p: None)
    assert not J._oude_kopie_leest_zakelijk_als_uitgelogd(None, "u", CREATE_2DH, oud)
