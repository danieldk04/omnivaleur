"""Gebruikt elke Supabase-verbinding HTTP/1.1, niet de racende HTTP/2-standaard?

WAAROM DIT ER IS (06-09-2026, storing "publiceren-mislukt", site-breed plat)

Drie klanten (amandahaas1979@gmail.com, info@zilverwebsite.nl,
info@papas-plectrums.nl) meldden terugkerende "Publishing failed (HTTP 500)"
en "Relist failed", laatst op 04-09-2026. In `server_fouten` op 05/06-09 stond
een reeks kale protocolfouten tegen Supabase: `RuntimeError: deque mutated
during iteration` in hpack, `RemoteProtocolError: <ConnectionTerminated>`,
`LocalProtocolError: Received pseudo-header in trailer`. Allemaal HTTP/2.

postgrest 0.16.11 en gotrue 2.12.4 (de versies achter de pin supabase==2.7.4
op Railway) zetten in hun eigen broncode `http2=True` op de httpx-client die ze
aanmaken. Die ene client wordt over alle gelijktijdige verzoeken gedeeld
(FastAPI draait de synchrone routes in een threadpool), en de
HTTP/2-verbindingsstaat in httpcore is niet thread-safe. Een lezing wordt bij
zo'n fout automatisch herhaald, een schrijfactie nooit — dat zou dubbele rijen
geven — dus komt die als kale 500 bij de klant terecht.

supabase==2.7.4 kent geen `httpx_client`-optie (`ClientOptions` heeft het veld
niet, `_init_postgrest_client` geeft niets door). De vorige poging dat toch te
doen gooide `TypeError: unexpected keyword argument 'httpx_client'` op élke
verbinding en legde de hele site plat. `backend.database._forceer_http1` zet
daarom de vlag om op de constructor die de bibliotheek zelf gebruikt.
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


def test_de_racende_standaard_bestaat_echt():
    """Een httpx-client met http2=True staat ook echt op http2 — dat is precies
    wat postgrest/gotrue in hun broncode doen. Kale httpx.Client() staat al op
    http2=False; de expliciete keuze in de bibliotheken is het probleem."""
    assert _http2_van(httpx.Client(http2=True)) is True
    assert _http2_van(httpx.Client()) is False


def test_patch_zet_http2_uit_op_de_bibliotheekclients():
    """Na import van backend.database levert elke SyncClient die de
    Supabase-bibliotheek aanmaakt een HTTP/1.1-verbinding, ook al vraagt de
    bibliotheek zelf om http2=True."""
    geraakt = 0
    for modulepad in ("postgrest.utils", "gotrue.http_clients",
                      "supabase_auth.http_clients", "storage3.utils"):
        try:
            module = __import__(modulepad, fromlist=["SyncClient"])
        except Exception:
            continue
        klasse = getattr(module, "SyncClient", None)
        if not isinstance(klasse, type) or not issubclass(klasse, httpx.Client):
            continue
        geraakt += 1
        # exact zoals de bibliotheek hem bouwt: met http2=True erbij
        client = klasse(base_url="https://x.invalid", headers={}, timeout=5, http2=True)
        assert _http2_van(client) is False, f"{modulepad} kreeg toch HTTP/2"
        client.close()
    assert geraakt >= 1, "geen enkele Supabase-SyncClient gevonden om te controleren"


def test_create_client_geeft_http1_voor_data_en_auth():
    """Een echte Supabase-client (zoals get_db er een maakt) heeft zowel voor
    data (postgrest) als voor auth (gotrue) een HTTP/1.1-verbinding."""
    cl = D.create_client("https://xyzcompany.supabase.co", "ey.fake.key")
    assert _http2_van(cl.postgrest.session) is False
    assert _http2_van(cl.auth._http_client) is False


def test_geen_kapotte_clientoptions_meer():
    """De regressie die de site plat legde: _zonder_http2 bouwde een
    ClientOptions met een veld dat supabase==2.7.4 niet kent."""
    assert not hasattr(D, "_zonder_http2")
    with patch.object(D, "create_client", wraps=D.create_client) as fake:
        D._client = None
        D.get_db()
        D._client = None
    # get_db roept create_client aan met alleen url + key, geen opties-object
    args, kwargs = fake.call_args
    assert len(args) == 2 and not kwargs, f"onverwachte aanroep: {args} {kwargs}"
