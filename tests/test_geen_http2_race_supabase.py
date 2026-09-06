"""Gebruikt elke Supabase-verbinding HTTP/1.1, niet de racende HTTP/2-standaard?

WAAROM DIT ER IS (06-09-2026, storing "publiceren-mislukt")

Drie klanten (amandahaas1979@gmail.com, info@zilverwebsite.nl,
info@papas-plectrums.nl) meldden terugkerende "Publishing failed (HTTP 500)"
en "Relist failed", laatst op 04-09-2026. De vier oorspronkelijke oorzaken van
30-08 (bedrijfsgegevens meegestuurd, Vinted-kinderkleding, dubbele foto's, de
oude 500) waren al gerepareerd en kwamen in geen van hun 300+ opdrachten sinds
01-09 terug. Wel gevonden in `server_fouten`: op 05-09-2026 08:50 UTC een kale
`KeyError` middenin httpcore, op /api/jobs/relist-status, precies dezelfde
route als de oude 500.

postgrest-py zet standaard `http2=True` op zijn httpx-client, en die ene client
wordt over alle gelijktijdige verzoeken heen gedeeld (FastAPI draait de
synchrone routes in een threadpool). httpx/httpcore houdt de openstaande
HTTP/2-streams van zo'n gedeelde verbinding bij in één woordenboek dat niet
thread-safe is; twee threads die tegelijk een stream afsluiten laten het
struikelen. Nagebouwd tegen de echte Supabase-URL met 40 threads en 1000
gelijktijdige verzoeken op een gedeelde client: 103 kapotte lezingen met
`http2=True`, nul met `http2=False`. Een lezing wordt bij zo'n fout automatisch
herhaald (`_lezen_met_herkansing`), maar een schrijfactie (een job aanmaken,
een status bijwerken) nooit — dat zou dubbele advertenties geven — dus komt
die als kale 500 bij de klant terecht.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as D  # noqa: E402


def _http2_van(client: httpx.Client) -> bool:
    return client._transport._pool._http2


def test_postgrest_standaard_is_de_racende_http2():
    """Vastleggen wat er zou gebeuren zonder deze reparatie: de kale
    postgrest/httpx-standaard is http2=True — precies de instelling die de
    race veroorzaakte."""
    assert _http2_van(httpx.Client()) is True


def test_zonder_http2_bouwt_een_http1_client():
    opties = D._zonder_http2()
    assert opties.httpx_client is not None
    assert _http2_van(opties.httpx_client) is False


def test_elke_supabase_verbinding_krijgt_http1():
    """Alle vier de plekken die een Supabase-client opzetten (get_db,
    get_admin_db, get_auth_db, verse_auth_client) moeten de http2=False
    client doorgeven, anders blijft de race op één van de vier bestaan."""
    D._client = None
    D._admin_client = None
    D._auth_client = None

    with patch.object(D, "create_client") as fake:
        D.get_db()
        D.get_admin_db()
        D.get_auth_db()
        D.verse_auth_client()

    assert fake.call_count == 4
    for _, kwargs_of_args in enumerate(fake.call_args_list):
        args, kwargs = kwargs_of_args
        opties = kwargs.get("options") if "options" in kwargs else args[2]
        assert _http2_van(opties.httpx_client) is False

    D._client = None
    D._admin_client = None
    D._auth_client = None
