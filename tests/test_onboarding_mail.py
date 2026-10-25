"""De onboardingmail die de routine zelf verstuurt (scripts/onboarding_mail.py).

WAAROM DIT ER IS (25-10-2026)
Daniel liet de routine zelf mailen aan nieuwe klanten, op voorwaarde dat alleen
echte nieuwe klanten mail krijgen, in de juiste taal en in zijn stijl. Elke
voorwaarde staat hier als proef, zodat een latere wijziging er niet stil een
uitzondering in maakt.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL))
sys.path.insert(0, str(WORTEL / "scripts"))
import onboarding_mail as O  # noqa: E402

NU = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)
GOED = """Hoi Anne,

Ik ben Daniel, de oprichter van Omnivaleur. Ik kijk zelf naar elk nieuw account; leuk dat je er bent!

Goed nieuws: je voorraad is binnen en 38 artikelen staan op Vinted. Op Marktplaats lukt het zodra je in Chrome bent ingelogd, dan ben je met dezelfde voorraad op twee plekken zichtbaar.

Loop je ergens tegenaan, stuur me gerust een berichtje of plan via het dashboard een call in.

Groetjes,
Daniel"""


def _account(dagen=1, email="anne@voorbeeld.nl"):
    return {"email": email, "aangemeld": NU - timedelta(days=dagen), "laatste_login": None}


def _fouten(account=None, post=(), log=(), taal="nl", p=None):
    return O.klantfouten("uid-1", account or _account(), p, list(post), taal, list(log), NU)


def test_goede_tekst_en_klant_gaan_door():
    assert O.tekstfouten("Je account op Omnivaleur", GOED, "nl") == []
    assert _fouten() == []


def test_tekstvorm_wordt_afgedwongen():
    assert any("streepje" in f for f in O.tekstfouten("x", GOED.replace("; leuk", " - leuk"), "nl"))
    assert any("opmaak" in f for f in O.tekstfouten("x", GOED.replace("Goed", "**Goed**"), "nl"))
    assert any("aanhef" in f for f in O.tekstfouten("x", "Beste Anne,\n" + GOED, "nl"))
    assert any("Daniel" in f for f in O.tekstfouten("x", GOED + "\nPS", "nl"))
    assert any("leest als nl" in f for f in O.tekstfouten("x", GOED, "en"))


def test_alleen_nieuwe_echte_klanten():
    assert any("niet nieuw" in f for f in _fouten(_account(dagen=8)))
    assert any("eigen adres" in f for f in _fouten(_account(email="x@omnivaleur.com")))
    assert any("onbekend" in f for f in O.klantfouten("u", None, None, [], "nl", [], NU))


def test_nooit_vlak_na_eigen_mail_of_als_klant_wacht():
    zelf = {"map": "Verzonden", "datum": NU - timedelta(hours=10), "onderwerp": ""}
    assert any("44 uur" in f for f in _fouten(post=[zelf]))
    vraag = {"map": "Klanten", "datum": NU - timedelta(days=3), "onderwerp": ""}
    oud = {"map": "Verzonden", "datum": NU - timedelta(days=4), "onderwerp": ""}
    assert any("wacht op antwoord" in f for f in _fouten(post=[oud, vraag]))
    assert any("niet te controleren" in f
               for f in O.klantfouten("uid-1", _account(), None, "postvak kapot", "nl", [], NU))


def test_grenzen_per_klant_en_per_dag():
    eerder = {"user_id": "uid-1", "op": (NU - timedelta(hours=20)).isoformat()}
    assert any("44 uur" in f for f in _fouten(log=[eerder]))
    drie = [{"user_id": "uid-1", "op": (NU - timedelta(days=d)).isoformat()} for d in (2, 4, 6)]
    assert any("maximum" in f for f in _fouten(log=drie))
    vandaag = [{"user_id": f"x{i}", "op": NU.isoformat()} for i in range(O.MAX_PER_DAG)]
    assert any("dagmaximum" in f for f in _fouten(log=vandaag))


def test_mailpauze_telt(monkeypatch):
    from backend.services import email
    monkeypatch.setitem(email.MAIL_PAUZE_TOT, "anne@voorbeeld.nl", "2099-01-01")
    assert any("mailpauze" in f for f in _fouten())


def test_taal_volgt_adres_en_kanalen():
    assert any("nl-talig" in f for f in _fouten(taal="en"))
    p = {"import": [("marktplaats:imported", 3)], "advertenties": []}
    assert any("nl-talig" in f for f in _fouten(_account(email="a@gmail.com"), taal="en", p=p))
    assert _fouten(_account(email="a@gmail.com"), taal="en") == []


def test_bericht_meet_maar_blijft_platte_mail():
    msg = O.bericht("anne@voorbeeld.nl", "Je account", GOED, "onboarding1")
    tekst, opmaak = (d.get_content() for d in msg.iter_parts())
    assert "/t/" not in tekst and "<" not in tekst
    code = O._code("anne@voorbeeld.nl", "onboarding1")
    assert f"/t/k/{code}" in opmaak and f"/t/o/{code}" in opmaak
    assert msg["List-Unsubscribe"] is None and msg["From"].endswith("<daniel@omnivaleur.nl>")
