"""Een Supabase-storing achter Cloudflare mag niemand uitloggen.

Aanleiding (28-09-2026). In de Railway-logs kregen minstens acht klantadressen
elke ronde een 422 op /api/jobs/pending: de extensie vroeg om werk ZONDER
inlogbewijs, want ze had het zelf weggegooid. Dat doet ze alleen als de server
op het verversen van het bewijs "401 sessie verlopen" zegt.

Die 401 kwam niet altijd van een verlopen sessie. Supabase staat achter
Cloudflare, en ligt het plat (op 28-09 van 13:05 tot 14:20 UTC) dan antwoordt
Cloudflare met een HTML-pagina en code 520 tot 524. De Supabase-bibliotheek
(gotrue 2.12.4 onder supabase 2.7.4, zoals op de server) herkent alleen
502/503/504 als storing; van een 521-pagina maakt ze een AuthUnknownError zonder
statuscode. auth_met_herkansing zag daar "een echt antwoord" in, en de endpoints
maakten er 401 van. Gevolg: elke extensie die tijdens een storing haar bewijs
verversde, logde zichzelf uit en vroeg daarna dagen om werk zonder het te
krijgen; elk dashboard dat toen iets vroeg, stuurde de verkoper naar het
inlogscherm.

De bestaande proeven in test_auth_sessies_gescheiden.py vervangen
auth_met_herkansing zelf en zagen dit dus nooit. Deze proef laat de echte
Supabase-client het echte antwoord van Cloudflare verwerken; alleen het netwerk
eronder is vervangen.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supabase import create_client  # noqa: E402

from backend import database as db_mod  # noqa: E402
from backend.api import auth as auth_api  # noqa: E402
from backend.api import deps as deps_api  # noqa: E402

SUPABASE = "https://abcdefghijklmnopqrst.supabase.co"


def _cloudflare_pagina(code: int) -> str:
    return (f"<!DOCTYPE html><html><head><title>abcdefghijklmnopqrst.supabase.co | "
            f"{code}: Web server is down</title></head><body>Cloudflare Ray ID: "
            f"8c1f2e3d4c5b6a79</body></html>")


@pytest.fixture
def netwerk(monkeypatch):
    """Zet vast wat 'Supabase' antwoordt; de client zelf is de echte."""
    antwoord = {}

    def nep(self, request):
        return antwoord["maak"](request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", nep)
    monkeypatch.setattr(db_mod.time, "sleep", lambda *_: None)
    client = lambda: create_client(SUPABASE, "aaaa.bbbb.cccc")  # noqa: E731
    monkeypatch.setattr(auth_api, "verse_auth_client", client)
    monkeypatch.setattr(auth_api, "get_db", lambda: None)
    monkeypatch.setattr(deps_api, "get_auth_db", client)
    return antwoord


def _storing(code):
    return lambda request: httpx.Response(
        code, text=_cloudflare_pagina(code), headers={"content-type": "text/html"},
        request=request)


CLOUDFLARE_STORINGEN = [500, 520, 521, 522, 523, 524]


@pytest.mark.parametrize("code", CLOUDFLARE_STORINGEN)
def test_verversen_tijdens_storing_laat_de_extensie_ingelogd(netwerk, code):
    """De extensie gooit haar bewijs weg bij 401/403 en houdt het bij 503."""
    netwerk["maak"] = _storing(code)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token=f"rt-storing-{code}")))
    assert e.value.status_code == 503, (
        f"Supabase {code} (Cloudflare) werd {e.value.status_code}: de extensie logt zichzelf uit")


@pytest.mark.parametrize("code", CLOUDFLARE_STORINGEN)
def test_dashboard_tijdens_storing_niet_naar_het_inlogscherm(netwerk, code):
    netwerk["maak"] = _storing(code)
    deps_api.vergeet_inlogbewijs()
    with pytest.raises(HTTPException) as e:
        asyncio.run(deps_api.get_current_user_full(authorization=f"Bearer tok-storing-{code}"))
    assert e.value.status_code == 503, (
        f"Supabase {code} (Cloudflare) werd {e.value.status_code}: het dashboard logt de verkoper uit")


@pytest.mark.parametrize("code", CLOUDFLARE_STORINGEN)
def test_inloggen_tijdens_storing_heet_geen_verkeerd_wachtwoord(netwerk, code):
    netwerk["maak"] = _storing(code)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.login(auth_api.AuthRequest(email="egbert@example.com", password="goed")))
    assert e.value.status_code == 503
    assert "password is fine" in e.value.detail


def test_echt_verlopen_vernieuwsleutel_blijft_401(netwerk):
    """De tegenproef: een echte afwijzing moet gewoon uitloggen, en niet drie keer
    worden overgedaan."""
    pogingen = []

    def afgewezen(request):
        pogingen.append(1)
        return httpx.Response(400, json={
            "code": 400, "error_code": "refresh_token_not_found",
            "msg": "Invalid Refresh Token: Refresh Token Not Found"}, request=request)

    netwerk["maak"] = afgewezen
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth_api.refresh(auth_api.RefreshRequest(refresh_token="rt-echt-dood")))
    assert e.value.status_code == 401
    assert len(pogingen) == 1


def test_ongeldig_bewijs_op_het_dashboard_blijft_401(netwerk):
    netwerk["maak"] = lambda request: httpx.Response(403, json={
        "code": 403, "error_code": "bad_jwt", "msg": "invalid JWT: token is expired"},
        request=request)
    deps_api.vergeet_inlogbewijs()
    with pytest.raises(HTTPException) as e:
        asyncio.run(deps_api.get_current_user_full(authorization="Bearer tok-echt-verlopen"))
    assert e.value.status_code == 401
