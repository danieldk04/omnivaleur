"""De Juiste Toon (dejuistetoon), 07-09-2026: 103 artikelen zonder rubriek.

Van de 294 artikelen die hij op 05-09 importeerde kwamen er 103 binnen zonder
rubriek, bij een tweede verkoper 42 van de 59, en over alle accounts staan er
959 zo in de voorraad. Zonder rubriek weigert het publicatiepad een artikel, en
dat gebeurt stil.

Gemeten met dezelfde titels, één voor één gevraagd: 20 van de 20 leveren wél een
rubriek op. De gegevens waren dus prima. Wat het liet vallen was de lopende band:
bulk-import vuurt de hele lading in één klap af, elke vraag draagt de volledige
taxonomie mee (bijna 5.000 tokens), en een geweigerde vraag werd stil {} en viel
terug op de woordenlijst — die zonder omschrijving niets vindt.

Deze proef legt de twee remmen vast, mét de tegenproef: zet het aantal pogingen
terug op één en dezelfde storing levert weer een lege rubriek op.

Draaien: python -m pytest tests/test_rubriek_valt_niet_stil.py
"""
import asyncio
import sys
import types

import pytest

from backend.api import imports as imp


class _Antwoord:
    """Wat de Anthropic-client teruggeeft: één tekstblok."""
    def __init__(self, tekst):
        self.content = [types.SimpleNamespace(text=tekst)]


GOED = '{"gender":"wonen","category":"wonen tapijten en kleden","confidence":"high"}'


def _neppe_anthropic(gedrag):
    """Zet een nep-`anthropic` in sys.modules; `gedrag()` levert het antwoord."""
    class _Messages:
        def create(self, **_kw):
            return gedrag()

    class _Client:
        def __init__(self, **_kw):
            self.messages = _Messages()

    module = types.ModuleType("anthropic")
    module.Anthropic = _Client
    return module


@pytest.fixture
def nep_anthropic(monkeypatch):
    def zetten(gedrag):
        monkeypatch.setitem(sys.modules, "anthropic", _neppe_anthropic(gedrag))
        monkeypatch.setattr(imp, "_CLASSIFY_WACHT_S", (0.0, 0.0))
    return zetten


def test_twee_haperingen_kosten_de_rubriek_niet(nep_anthropic):
    pogingen = {"n": 0}

    def gedrag():
        pogingen["n"] += 1
        if pogingen["n"] < 3:
            raise RuntimeError("429 rate_limit_error")
        return _Antwoord(GOED)

    nep_anthropic(gedrag)
    uitkomst = asyncio.run(imp._classify_with_claude("Perzisch tapijtje 127/68", None, None))
    assert uitkomst == {"gender": "wonen", "category": "wonen tapijten en kleden"}
    assert pogingen["n"] == 3


def test_tegenproef_zonder_herkansing_blijft_de_rubriek_leeg(nep_anthropic, monkeypatch):
    """Het oude gedrag: één poging, en dezelfde hapering levert niets op."""
    pogingen = {"n": 0}

    def gedrag():
        pogingen["n"] += 1
        if pogingen["n"] < 3:
            raise RuntimeError("429 rate_limit_error")
        return _Antwoord(GOED)

    nep_anthropic(gedrag)
    monkeypatch.setattr(imp, "_CLASSIFY_POGINGEN", 1)
    assert asyncio.run(imp._classify_with_claude("Perzisch tapijtje 127/68", None, None)) == {}


def test_een_blijvende_storing_geeft_nog_steeds_netjes_op(nep_anthropic):
    def gedrag():
        raise RuntimeError("overloaded_error")

    nep_anthropic(gedrag)
    assert asyncio.run(imp._classify_with_claude("Perzisch tapijtje", None, None)) == {}


def test_de_lading_gaat_niet_in_een_klap_de_deur_uit(nep_anthropic):
    """Twintig tegelijk aanbieden mag hoogstens een handvol tegelijk worden."""
    staat = {"nu": 0, "hoogste": 0}

    def gedrag():
        staat["nu"] += 1
        staat["hoogste"] = max(staat["hoogste"], staat["nu"])
        # De echte aanroep draait in een worker-thread; even blijven staan zodat
        # de vragen elkaar kunnen overlappen als de rem er niet is.
        import time
        time.sleep(0.05)
        staat["nu"] -= 1
        return _Antwoord(GOED)

    nep_anthropic(gedrag)

    async def alles():
        return await asyncio.gather(*(
            imp._classify_with_claude(f"Perzisch tapijtje {i}", None, None)
            for i in range(20)
        ))

    uitkomsten = asyncio.run(alles())
    assert all(u.get("category") == "wonen tapijten en kleden" for u in uitkomsten)
    assert staat["hoogste"] <= 5, f"er gingen er {staat['hoogste']} tegelijk uit"  # semafoor = 5


def test_goede_rubriek_met_verkeerd_etiket_wordt_niet_weggegooid(nep_anthropic):
    """Rubriek klopt, doelgroep niet: dan telt de rubriek en volgt de tak.

    Gemeten op de eerste vijf artikelen van de hersteldraaiing: één van de vijf
    kwam terug als "unisex" + "wonen plaids en woondekens". Vroeger ging dat hele
    antwoord weg en bleef het artikel zonder rubriek staan.
    """
    nep_anthropic(lambda: _Antwoord(
        '{"gender":"unisex","category":"wonen plaids en woondekens","confidence":"high"}'))
    assert asyncio.run(imp._classify_with_claude("Granny woondeken", None, None)) == {
        "gender": "wonen", "category": "wonen plaids en woondekens"}


def test_een_verzonnen_rubriek_wordt_nog_steeds_geweigerd(nep_anthropic):
    nep_anthropic(lambda: _Antwoord(
        '{"gender":"dames","category":"kinderen kleding","confidence":"high"}'))
    assert asyncio.run(imp._classify_with_claude("Iets", None, None)) == {}
