"""Link naar de computer mailen en om hulp vragen (Daniel, 16-11-2026).

Meting: 36% van de aanmelders installeerde de extensie nooit. De mail moet bij de
klant zelf aankomen, niet te vaak, en een hulpvraag moet Daniel bereiken met het
adres van de klant als antwoordadres.
"""
import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api import account as A  # noqa: E402
from backend.services import email as E  # noqa: E402


def _user(uid="u1", mail="klant@example.com"):
    return types.SimpleNamespace(id=uid, email=mail, created_at="2026-11-16T10:00:00Z")


@pytest.fixture(autouse=True)
def schoon(monkeypatch):
    A._LINK_MAILS.clear(); A._HULP_VRAGEN.clear()
    verstuurd = []
    monkeypatch.setattr(E, "send_email_checked", lambda *a, **k: verstuurd.append((a, k)) or "id")
    return verstuurd


def test_link_gaat_naar_de_klant_zelf(schoon):
    asyncio.run(A.link_naar_computer(_user()))
    (a, _), = schoon
    assert a[2] == "klant@example.com" and "https://omnivaleur.com/app" in a[1]
    assert " - " not in a[1] and "—" not in a[1] and "*" not in a[1]


def test_link_hooguit_drie_per_uur(schoon):
    for _ in range(3):
        asyncio.run(A.link_naar_computer(_user()))
    with pytest.raises(A.HTTPException) as e:
        asyncio.run(A.link_naar_computer(_user()))
    assert e.value.status_code == 429 and len(schoon) == 3
    asyncio.run(A.link_naar_computer(_user("u2")))  # een andere klant is niet geblokkeerd


def test_mislukte_mail_telt_niet_mee(monkeypatch):
    def kapot(*a, **k): raise RuntimeError("smtp weg")
    monkeypatch.setattr(E, "send_email_checked", kapot)
    with pytest.raises(A.HTTPException) as e:
        asyncio.run(A.link_naar_computer(_user()))
    assert e.value.status_code == 502 and A._LINK_MAILS.get("u1") == []


def test_hulpvraag_bereikt_daniel_met_antwoordadres(schoon):
    asyncio.run(A.hulp_vragen(A.HulpVraag(fase="extensie", sub="installeren"), _user()))
    (a, _), = schoon
    assert a[2] is None and a[3] == "klant@example.com"  # to=None is de eigenaar, reply_to de klant
    assert "extensie installeren" in a[1] and "klant@example.com" in a[1]


def test_hulpvraag_maar_een_keer_per_zes_uur(schoon):
    asyncio.run(A.hulp_vragen(A.HulpVraag(fase="kanalen"), _user()))
    uit = asyncio.run(A.hulp_vragen(A.HulpVraag(fase="kanalen"), _user()))
    assert uit["al_gevraagd"] is True and len(schoon) == 1
