"""De server start de foto-taak zelf (21-11, De Juiste Toon): zonder token niets,
met token één aanroep per drie minuten, en een fout raakt niemand."""
import asyncio

import httpx

from backend.services import bronfotos_start as b


def _draai(monkeypatch, status=204, token="x"):
    calls = []

    class Cl:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            calls.append((url, json))
            return httpx.Response(status)

    monkeypatch.setattr(b.httpx, "AsyncClient", Cl)
    b._laatste = 0.0
    if token: monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", token)
    else: monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    return calls


def test_zonder_token_niets(monkeypatch):
    calls = _draai(monkeypatch, token=None)
    assert asyncio.run(b.start_bronfotos()) is False and calls == []


def test_met_token_een_keer_per_drie_minuten(monkeypatch):
    calls = _draai(monkeypatch)
    assert asyncio.run(b.start_bronfotos()) is True
    assert asyncio.run(b.start_bronfotos()) is False
    assert len(calls) == 1 and calls[0][0].endswith("/workflows/bronfotos.yml/dispatches")
    assert calls[0][1] == {"ref": "main"}


def test_github_weigert_geeft_false(monkeypatch):
    _draai(monkeypatch, status=403)
    assert asyncio.run(b.start_bronfotos()) is False
