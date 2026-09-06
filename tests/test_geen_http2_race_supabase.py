"""Gebruikt elke Supabase-verbinding HTTP/1.1, niet de racende HTTP/2-standaard?

WAAROM DIT ER IS (06-09-2026, storing "publiceren-mislukt", site-breed plat)

Drie klanten (amandahaas1979@gmail.com, info@zilverwebsite.nl,
info@papas-plectrums.nl) meldden terugkerende "Publishing failed (HTTP 500)"
en "Relist failed", laatst op 04-09-2026. In `server_fouten` op 05/06-09 stond
een reeks kale protocolfouten tegen Supabase: `RuntimeError: deque mutated
during iteration` in hpack, `RemoteProtocolError: <ConnectionTerminated>`,
`LocalProtocolError: Received pseudo-header in trailer`. Allemaal HTTP/2.

postgrest en gotrue (de versies achter de pin supabase==2.7.4 op Railway)
zetten in hun eigen broncode `http2=True` op de httpx-client die ze aanmaken.
Die ene client wordt over alle gelijktijdige verzoeken gedeeld (FastAPI draait
de synchrone routes in een threadpool), en de HTTP/2-verbindingsstaat in
httpcore is niet thread-safe. Een lezing wordt bij zo'n fout automatisch
herhaald, een schrijfactie nooit — dat zou dubbele rijen geven — dus komt die
als kale 500 bij de klant terecht.

supabase==2.7.4 kent geen `httpx_client`-optie (`ClientOptions` heeft het veld
niet, `_init_postgrest_client` geeft niets door). De vorige poging dat toch te
doen gooide `TypeError: unexpected keyword argument 'httpx_client'` op élke
verbinding en legde de hele site plat. `backend.database._forceer_http1` zet
daarom `http2=False` af op `httpx.Client` zelf.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as D  # noqa: E402  (importeren draait _forceer_http1)


def _http2_van(client: httpx.Client) -> bool:
    return client._transport._pool._http2


def test_de_racende_standaard_is_uitgezet():
    """postgrest/gotrue bouwen hun client met http2=True. Na import van
    backend.database levert diezelfde aanroep tóch een HTTP/1.1-verbinding —
    dat is precies wat de race wegneemt. AsyncClient blijft ongemoeid."""
    assert _http2_van(httpx.Client(http2=True)) is False
    assert _http2_van(httpx.Client()) is False


def test_create_client_geeft_http1_voor_data_en_auth():
    """Een echte Supabase-client (zoals get_db er een maakt) heeft zowel voor
    data (postgrest) als voor auth (gotrue) een HTTP/1.1-verbinding."""
    cl = D.create_client("https://xyzcompany.supabase.co", "ey.fake.key")
    assert _http2_van(cl.postgrest.session) is False
    assert _http2_van(cl.auth._http_client) is False


def test_patch_is_idempotent():
    """Twee keer draaien mag niets stukmaken (de wrapper mag zichzelf niet
    om zichzelf heen wikkelen)."""
    D._forceer_http1()
    D._forceer_http1()
    assert _http2_van(httpx.Client(http2=True)) is False


def test_geen_kapotte_clientoptions_meer():
    """De regressie die de site plat legde: _zonder_http2 bouwde een
    ClientOptions met een veld dat supabase==2.7.4 niet kent."""
    assert not hasattr(D, "_zonder_http2")
    with patch.object(D, "create_client", wraps=D.create_client) as fake:
        D._client = None
        D.get_db()
        D._client = None
    args, kwargs = fake.call_args
    assert len(args) == 2 and not kwargs, f"onverwachte aanroep: {args} {kwargs}"
