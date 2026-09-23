"""Gemini eerst, Claude als reserve, en nooit een half antwoord (23-09-2026).

Daniel: "zet alles op Gemini". Het Anthropic-tegoed liep leeg en daarmee stonden
rubriekkeuze, tweelingzoeker, Shopify-collecties, eBay-rubrieknamen en de blog
stil. backend/services/taalmodel.py is sindsdien de ene ingang.
"""
import sys
import types

import pytest

from backend.services import gemini_vertaling as gv
from backend.services import taalmodel


class _Bericht:
    def __init__(self, tekst, stop="end_turn"):
        self.content = [types.SimpleNamespace(text=tekst)]
        self.stop_reason = stop


def _claude(monkeypatch, gedrag, teller):
    class _Messages:
        def create(self, **_kw):
            teller.append(1)
            return gedrag()

    class _Client:
        def __init__(self, **_kw):
            self.messages = _Messages()

    mod = types.ModuleType("anthropic")
    mod.Anthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)


@pytest.fixture
def gemini(monkeypatch):
    def zet(antwoord):
        gevraagd = []
        monkeypatch.setattr(gv.settings, "google_api_key", "test-sleutel")
        monkeypatch.setattr(gv, "vraag", lambda o, **kw: gevraagd.append(kw) or antwoord)
        return gevraagd
    return zet


def test_gemini_antwoordt_en_claude_wordt_niet_gevraagd(monkeypatch, gemini):
    claude = []
    _claude(monkeypatch, lambda: _Bericht("claude"), claude)
    gemini("gemini")
    assert taalmodel.vraag("vraag") == "gemini"
    assert claude == []


def test_gemini_plat_dan_antwoordt_claude(monkeypatch, gemini):
    claude = []
    _claude(monkeypatch, lambda: _Bericht("claude"), claude)
    gemini(None)
    assert taalmodel.vraag("vraag") == "claude"
    assert claude == [1]


def test_allebei_plat_geeft_een_fout_en_geen_lege_tekst(monkeypatch, gemini):
    def plat():
        raise RuntimeError("Your credit balance is too low")
    _claude(monkeypatch, plat, [])
    gemini(None)
    with pytest.raises(taalmodel.TaalmodelOnbeschikbaar):
        taalmodel.vraag("vraag")


def test_een_afgekapt_claude_antwoord_telt_niet(monkeypatch, gemini):
    _claude(monkeypatch, lambda: _Bericht('{"gender', stop="max_tokens"), [])
    gemini(None)
    with pytest.raises(taalmodel.TaalmodelOnbeschikbaar):
        taalmodel.vraag("vraag")


def test_de_denkstap_gaat_mee_naar_gemini(monkeypatch, gemini):
    gevraagd = gemini("ok")
    taalmodel.vraag("vraag", denken=False, max_tokens=200)
    assert gevraagd[0]["denken"] is False and gevraagd[0]["max_tokens"] == 200


def test_een_afgekapt_gemini_antwoord_wordt_verworpen():
    """Gemeten: met 200 tokens ging 194 op aan denken en kwam '{"gender' terug."""
    class A:
        def json(self):
            return {"candidates": [{"finishReason": "MAX_TOKENS",
                                    "content": {"parts": [{"text": '{"gender'}]}}]}
    assert gv._lees_antwoord(A()) is None


def test_zonder_denkstap_krijgt_flash_lite_de_instelling_niet(monkeypatch):
    """Flash-Lite weigert thinkingBudget 0 met een 400 (gemeten 23-09-2026)."""
    verzonden = []

    class A:
        status_code = 200

    monkeypatch.setattr(gv.httpx, "post", lambda url, **kw: verzonden.append(
        (url, kw["json"]["generationConfig"])) or A())
    gv._vraag("gemini-flash-lite-latest", "x", denken=False)
    gv._vraag("gemini-flash-latest", "x", denken=False)
    assert "thinkingConfig" not in verzonden[0][1]
    assert verzonden[1][1]["thinkingConfig"] == {"thinkingBudget": 0}


def test_een_model_dat_de_denkinstelling_weigert_krijgt_een_tweede_kans(monkeypatch):
    verzonden = []

    class A:
        def __init__(self, code): self.status_code = code

    def post(url, **kw):
        verzonden.append(dict(kw["json"]["generationConfig"]))
        return A(400 if "thinkingConfig" in kw["json"]["generationConfig"] else 200)

    monkeypatch.setattr(gv.httpx, "post", post)
    assert gv._vraag("gemini-9-flash", "x", denken=False).status_code == 200
    assert "thinkingConfig" in verzonden[0] and "thinkingConfig" not in verzonden[1]
