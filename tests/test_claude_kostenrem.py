"""Rubriekvragen mogen nooit naar het betaalde Claude; de rest heeft een dagmaximum (09-10-2026)."""
import asyncio, sys, types
from unittest import mock

from backend.api import imports
from backend.services import taalmodel


def _nep_claude(teller):
    class Client:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(create=self.create)
        def create(self, **k):
            teller.append(1)
            return types.SimpleNamespace(stop_reason="end_turn",
                                         content=[types.SimpleNamespace(text="ok")])
    return types.SimpleNamespace(Anthropic=Client)


def _gemini_429():
    return mock.patch("backend.services.gemini_vertaling.beschikbaar", return_value=True), \
           mock.patch("backend.services.gemini_vertaling.vraag", return_value=None)


def test_rubriekvraag_gaat_niet_naar_claude():
    calls = []
    a, b = _gemini_429()
    with a, b, mock.patch.dict(sys.modules, {"anthropic": _nep_claude(calls)}), \
         mock.patch.object(taalmodel.settings, "anthropic_api_key", "x"), \
         mock.patch.object(imports, "_CLASSIFY_WACHT_S", (0, 0)):
        try:
            asyncio.run(imports._haiku_classificatie(None, "prompt"))
        except Exception:
            pass
    assert calls == []


def test_dagmaximum_stopt_claude():
    calls = []
    a, b = _gemini_429()
    taalmodel._CLAUDE_DAG.update(dag=None, n=0)
    with a, b, mock.patch.dict(sys.modules, {"anthropic": _nep_claude(calls)}), \
         mock.patch.object(taalmodel.settings, "anthropic_api_key", "x"), \
         mock.patch.object(taalmodel, "CLAUDE_MAX_PER_DAG", 3):
        for _ in range(10):
            try:
                taalmodel.vraag("hoi")
            except taalmodel.TaalmodelOnbeschikbaar:
                pass
    assert len(calls) == 3


def test_korte_kledingvraag_mag_wel_naar_claude():
    calls = []
    a, b = _gemini_429()
    taalmodel._CLAUDE_DAG.update(dag=None, n=0)
    with a, b, mock.patch.dict(sys.modules, {"anthropic": _nep_claude(calls)}), \
         mock.patch.object(taalmodel.settings, "anthropic_api_key", "x"):
        asyncio.run(imports._haiku_classificatie(None, "kort", claude_ok=True))
    assert len(calls) == 1
