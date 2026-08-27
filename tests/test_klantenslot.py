"""Een klant mag nooit koude mail of een afscheidsmail krijgen.

Aanleiding: Jaap van Zilverwebsite was al dagen betalende klant toen hij vroeg of
het herplaatsen bij zijn oudste advertenties kon beginnen. De machine zag alleen
een adres uit haar leadlijst en stuurde "veel succes met de winkel".

De rem daartegen is is_klant(). Die haalt de accountlijst bij Supabase op, en de
vraag die deze test stelt is: wat doet hij als dat NIET lukt? Tot 27-08-2026 gaf
hij dan een lege lijst terug — én onthield die — waarmee iedereen weer prospect
werd. Precies de situatie waarin het fout ging, want met de anon-sleutel faalt
auth/admin altijd.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import leadgen_mail as lm  # noqa: E402


@pytest.fixture(autouse=True)
def _schoon():
    lm._klanten_kas = None
    lm.klantenlijst_kapot = ""
    yield
    lm._klanten_kas = None
    lm.klantenlijst_kapot = ""


def test_zonder_verbinding_geldt_iedereen_als_klant(monkeypatch):
    monkeypatch.setattr(lm, "_supabase", lambda: None)
    assert lm.is_klant("wiedanook@example.com") is True
    assert lm.klantenlijst_kapot, "de storing moet gemeld worden, niet stil blijven"


def test_een_lege_lijst_is_een_storing_en_geen_antwoord(monkeypatch):
    """De anon-sleutel geeft netjes HTTP 200 met nul gebruikers terug. Dat mag
    nooit als 'er zijn geen klanten' gelezen worden — er is er altijd minstens
    een."""
    monkeypatch.setattr(lm, "_supabase", lambda: ("https://x.supabase.co", "anon"))

    class _Antwoord:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"users": []}

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwoord())
    with pytest.raises(lm.KlantenlijstOnbekend):
        lm._klanten()
    assert lm.is_klant("jaap@zilverwebsite.nl") is True


def test_een_mislukking_wordt_niet_onthouden(monkeypatch):
    """Eén hapering mocht niet de hele run vergiftigen: als het later wel lukt,
    moet de echte lijst alsnog gebruikt worden."""
    monkeypatch.setattr(lm, "_supabase", lambda: None)
    assert lm.is_klant("a@b.nl") is True
    assert lm._klanten_kas is None, "een mislukte poging mag niets in de cache zetten"


def test_bij_een_goede_lijst_werkt_het_gewoon(monkeypatch):
    monkeypatch.setattr(lm, "_supabase", lambda: ("https://x.supabase.co", "service"))

    class _Antwoord:
        def raise_for_status(self): pass
        def json(self): return {"users": [{"email": "Jaap@Zilverwebsite.nl"},
                                          {"email": "iemand@anders.nl"}]}

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwoord())
    assert lm.is_klant("jaap@zilverwebsite.nl") is True     # klant, hoofdletters egaal
    assert lm.is_klant("vreemde@lead.nl") is False          # prospect, mag gemaild
    assert not lm.klantenlijst_kapot


def test_een_klant_krijgt_geen_enkele_beurt(monkeypatch):
    """De rem zit in _beurt(): geeft die None, dan gaat er niets uit."""
    monkeypatch.setattr(lm, "is_klant", lambda adres: True)
    assert lm._beurt({"email": "jaap@zilverwebsite.nl"}, None) is None
    assert lm._beurt({"email": "jaap@zilverwebsite.nl"}, {"verstuurd": 1}) is None
