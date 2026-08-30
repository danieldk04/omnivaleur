"""Een weggevallen verbinding mag nooit een advertentie kosten.

WAT ER GEBEURDE (28-08-2026, Jaap van zilverwebsite.nl)
Hij verving één advertentie en kreeg op zijn scherm:

    Refresh failed unexpectedly: EOF occurred in violation of protocol (_ssl.c:2417)

Dat is geen storing in zijn gegevens maar een weggevallen verbinding met de
database. Twee dingen klopten daar niet:

1. Zo'n hik werd niet opnieuw geprobeerd. execute_with_retry deed dat wel, maar
   het hele herplaats-, plaats- en verwijderpad loopt via naast_de_lus, en die
   probeerde niets opnieuw. Bovendien stond de kale ssl-fout niet in de lijst
   met herstelbare fouten, dus zelfs execute_with_retry liet hem door.

2. De verwijderopdracht werd als eerste weggeschreven en de herplaatsing pas
   daarna — met een vertaling en een paar databaseaanroepen ertussen. Viel de
   verbinding daar weg, dan stond de verwijdering er wél en de herplaatsing
   niet: de advertentie werd weggehaald en kwam nooit terug.
"""
import asyncio
import re
from pathlib import Path

import pytest

from backend.database import _is_herstelbaar

ROOT = Path(__file__).resolve().parents[1]
RELIST = (ROOT / "backend/services/relist.py").read_text(encoding="utf-8")
DB = (ROOT / "backend/database.py").read_text(encoding="utf-8")
LISTINGS = (ROOT / "backend/api/listings.py").read_text(encoding="utf-8")


# ── 1. De hik wordt herkend ──────────────────────────────────────────────────

def test_kale_ssl_eof_telt_als_herstelbaar():
    """Precies de fout die Jaap op zijn scherm kreeg."""
    import ssl
    assert _is_herstelbaar(ssl.SSLEOFError("EOF occurred in violation of protocol (_ssl.c:2417)"))


def test_ook_als_de_fout_alleen_als_tekst_doorkomt():
    assert _is_herstelbaar(RuntimeError("EOF occurred in violation of protocol (_ssl.c:2417)"))
    assert _is_herstelbaar(RuntimeError("Server disconnected without sending a response"))


def test_een_echte_gegevensfout_wordt_niet_herhaald():
    assert not _is_herstelbaar(ValueError("duplicate key value violates unique constraint"))


# ── 2. De hik wordt opgevangen ───────────────────────────────────────────────

def test_naast_de_lus_probeert_opnieuw():
    import ssl
    from backend.database import naast_de_lus

    pogingen = {"n": 0}

    def hik():
        pogingen["n"] += 1
        if pogingen["n"] < 3:
            raise ssl.SSLEOFError("EOF occurred in violation of protocol (_ssl.c:2417)")
        return "gelukt"

    assert asyncio.run(naast_de_lus(hik, herkans=True)) == "gelukt"
    assert pogingen["n"] == 3


def test_herkansen_staat_standaard_uit():
    """Blind herhalen van een insert maakt een tweede opdracht — en dus een
    tweede advertentie — als het antwoord onderweg wegviel."""
    import ssl
    from backend.database import naast_de_lus

    pogingen = {"n": 0}

    def hik():
        pogingen["n"] += 1
        raise ssl.SSLEOFError("EOF occurred in violation of protocol (_ssl.c:2417)")

    with pytest.raises(ssl.SSLEOFError):
        asyncio.run(naast_de_lus(hik))
    assert pogingen["n"] == 1


def test_de_opdrachten_krijgen_een_zelfbedacht_id():
    """Alleen dan is een herhaalde poging herkenbaar als 'stond er al'."""
    tak = _relist_tak()
    assert 'verwijder_id = str(uuid.uuid4())' in tak
    assert tak.count("dubbel_is_ok=True") == 2
    assert '"id": verwijder_id' in tak


def test_naast_de_lus_herhaalt_een_echte_fout_niet():
    from backend.database import naast_de_lus

    pogingen = {"n": 0}

    def stuk():
        pogingen["n"] += 1
        raise ValueError("kolom bestaat niet")

    with pytest.raises(ValueError):
        asyncio.run(naast_de_lus(stuk, herkans=True))
    assert pogingen["n"] == 1, "een echte fout drie keer proberen is alleen maar traag"


# ── 3. Niets kan meer misgaan tússen weghalen en terugzetten ─────────────────

def _relist_tak() -> str:
    return RELIST.split('# strategy == "relist": delete now')[1].split("\n    return {")[0]


def test_de_vertaling_gebeurt_voor_de_verwijderopdracht():
    """Vertalen praat met een dienst buiten de deur en kan dus wegvallen.

    Gebeurde dat ná het wegschrijven van de verwijdering, dan was de advertentie
    weg zonder dat er ooit een herplaatsing was vastgelegd.
    """
    tak = _relist_tak()
    assert tak.index("localize_item_for_platform(item, platform)") < tak.index('"action": "delete"')


def test_de_prijs_en_de_instellingen_ook():
    tak = _relist_tak()
    verwijder = tak.index('"action": "delete"')
    assert tak.index("relist_price =") < verwijder
    assert tak.index("verzendkeuzes(user_id") < verwijder
    assert tak.index("create_payload = {") < verwijder


def test_verwijdering_staat_nog_steeds_als_eerste_in_de_database():
    """Andersom mag ook niet: jobs.py zoekt de verwijdering op created_at <= die
    van de herplaatsing. Staat de herplaatsing eerder, dan vindt hij hem niet en
    plaatst hij een tweede advertentie naast de nog levende oude."""
    tak = _relist_tak()
    assert tak.index('"action": "delete"') < tak.index('"action": "create"')


def test_mislukte_herplaatsing_haalt_de_verwijdering_weer_weg():
    """Anders blijft er een kale verwijderopdracht staan en is de advertentie weg."""
    tak = _relist_tak()
    staart = tak[tak.index('"action": "create"'):]
    assert "except Exception" in staart
    assert 'db.table("jobs").delete().eq("id", verwijder_id)' in staart
    assert '"status": "cancelled"' in staart, "vangnet als zelfs weghalen niet lukt"


def test_de_melding_zegt_dat_de_advertentie_nog_leeft():
    staart = _relist_tak()
    staart = staart[staart.index('"action": "create"'):]
    boodschap = re.search(r'raise RefreshError\(\s*"(.*?)"\s*(?:"(.*?)"\s*)*\)', staart, re.S)
    assert boodschap, "er moet een leesbare melding volgen"
    assert "still live" in staart


# ── 4. En de verkoper leest geen Python meer ─────────────────────────────────

def test_verbindingsfout_wordt_geen_ruwe_python_op_het_scherm():
    fn = LISTINGS.split("async def refresh_one_listing(")[1].split("\n@router.")[0]
    herstelbaar = fn.index("if _is_herstelbaar(e):")
    ruw = fn.index('detail=f"Refresh failed unexpectedly')
    assert herstelbaar < ruw, "de hik moet eerder worden afgevangen dan de ruwe 500"
    assert "status_code=503" in fn
    assert "still live" in fn


# ── 4. Elke leesactie overleeft de hik, ook zonder wrapper ───────────────────
#
# WAAROM (30-08-2026). `execute_with_retry` bestond, maar zo'n tweehonderd
# plekken roepen gewoon `.execute()` aan. Viel de verbinding daar weg, dan werd
# het een kale "HTTP 500: Internal Server Error" — het scherm waar Amanda een
# foto van stuurde. Binnen een kwartier na het inschakelen van de foutcodes
# stonden er twee zulke fouten in de lijst, allebei op /api/jobs/relist-status.

def _nep_select():
    """Een echte Supabase-selectbouwer, zonder verbinding te maken."""
    from postgrest import SyncSelectRequestBuilder
    return SyncSelectRequestBuilder.__new__(SyncSelectRequestBuilder)


def test_een_kale_leesactie_wordt_opnieuw_geprobeerd(monkeypatch):
    import httpx

    from backend import database as D

    pogingen = {"n": 0}

    def hik(_self, *a, **kw):
        pogingen["n"] += 1
        if pogingen["n"] < 3:
            raise httpx.RemoteProtocolError("<ConnectionTerminated error_code:1>")
        return "gelukt"

    monkeypatch.setattr(D, "_ORIGINEEL_SELECT_EXECUTE", hik)
    assert _nep_select().execute() == "gelukt"
    assert pogingen["n"] == 3


def test_een_kapotte_query_wordt_niet_herhaald(monkeypatch):
    from backend import database as D

    pogingen = {"n": 0}

    def kapot(_self, *a, **kw):
        pogingen["n"] += 1
        raise ValueError("column does not exist")

    monkeypatch.setattr(D, "_ORIGINEEL_SELECT_EXECUTE", kapot)
    with pytest.raises(ValueError):
        _nep_select().execute()
    assert pogingen["n"] == 1, "een fout in de query herhalen heeft geen zin"


def test_schrijfacties_blijven_met_rust():
    """Een insert blind herhalen na een weggevallen antwoord maakt een tweede
    rij — en dus een tweede advertentie. Alleen lezen wordt herhaald."""
    import postgrest

    for bouwer in (postgrest.SyncQueryRequestBuilder, postgrest.SyncFilterRequestBuilder):
        assert not issubclass(bouwer, postgrest.SyncSelectRequestBuilder)
    assert "execute" in postgrest.SyncSelectRequestBuilder.__dict__, \
        "de herhaling hoort alleen op de selectbouwer te staan"


def test_de_wrapper_telt_niet_dubbel(monkeypatch):
    """execute_with_retry mag er geen negen pogingen van maken."""
    import httpx

    from backend import database as D

    pogingen = {"n": 0}

    def hik(_self, *a, **kw):
        pogingen["n"] += 1
        if pogingen["n"] < 3:
            raise httpx.RemoteProtocolError("<ConnectionTerminated error_code:1>")
        return "gelukt"

    monkeypatch.setattr(D, "_ORIGINEEL_SELECT_EXECUTE", hik)
    assert D.execute_with_retry(_nep_select()) == "gelukt"
    assert pogingen["n"] == 3


def test_een_html_pagina_van_de_gateway_telt_als_hik():
    """Supabase staat achter Cloudflare. Hapert die, dan komt er een HTML-pagina
    terug die de client "JSON could not be generated (400)" noemt — dat lijkt een
    kapotte query maar het verzoek is de database nooit binnengekomen."""
    boodschap = ("{'message': 'JSON could not be generated', 'code': 400, "
                 "'details': \"b'<html><head><title>400 Bad Request</title></head>"
                 "<body><center><h1>400 Bad Request</h1></center>"
                 "<hr><center>cloudflare</center></body></html>'\"}")
    assert _is_herstelbaar(RuntimeError(boodschap))


def test_een_echte_400_van_de_database_wordt_niet_herhaald():
    assert not _is_herstelbaar(RuntimeError(
        "{'message': 'column listings.zzz does not exist', 'code': '42703'}"))
