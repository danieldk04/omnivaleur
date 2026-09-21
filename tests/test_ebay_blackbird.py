"""
Blackbird Guitars (Johan Kist), 21-09-2026 — drie dingen die eBay tegenhielden.

Gemeten op zijn echte account: van 29 artikelen stonden er 13 op eBay. Wat de
rest tegenhield:

1. Zijn toegangssleutel voor eBay verliep op 19-09 om 11:06. Elke poging daarna
   mislukte, en wat hij in het dashboard zag was letterlijk
   "Client error '400 Bad Request' for url 'https://api.ebay.com/identity/v1/
   oauth2/token'". Ondertussen bleef eBay als gekoppeld in beeld, want
   /platforms/status keek alleen of er een rij in de database stond. Twee dagen
   lang geen kanaal en geen enkele aanwijzing wat hij eraan kon doen.
2. Eén gitaar had een omschrijving van 4219 tekens. eBay weigert boven de 4000.
3. Twee gitaren liepen vast op "Het veld EAN ontbreekt".

Draaien:  /usr/bin/python3 -m pytest tests/test_ebay_blackbird.py -q
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.platforms import ebay as ebay_mod
from backend.platforms.ebay import (
    EbayKoppelingVerlopenError,
    EbayPlatform,
    _GEEN_PRODUCTCODE,
    _MAX_OMSCHRIJVING,
    _kort_omschrijving,
)


# ── 1. Een dode koppeling heet een dode koppeling ────────────────────────
def test_verlopen_koppeling_geeft_leesbare_fout_en_wordt_vastgelegd(monkeypatch):
    """De oude code deed resp.raise_for_status(). Die tekst noemt een URL en
    zegt de verkoper niets. Deze test faalt op die versie: hij eist dat de
    melding vertelt wát er moet gebeuren."""
    gemarkeerd = {}

    class NepAntwoord:
        status_code = 400
        is_success = False
        text = '{"error":"invalid_grant"}'

        def json(self):
            return {"error": "invalid_grant",
                    "error_description": "the provided authorization refresh token is invalid"}

    class NepClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return NepAntwoord()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: NepClient())
    platform = EbayPlatform()
    monkeypatch.setattr(platform, "_meld_koppeling_kapot",
                        lambda creds, reden: gemarkeerd.update(reden=reden))

    with pytest.raises(EbayKoppelingVerlopenError) as fout:
        asyncio.run(platform.refresh_credentials(
            {"refresh_token": "x", "user_id": "u1"}))

    tekst = str(fout.value)
    assert "Settings" in tekst and "Connect" in tekst, tekst
    assert "oauth2/token" not in tekst, "de URL hoort niet in een klantmelding"
    assert "400" in gemarkeerd["reden"], gemarkeerd


# ── 2. Omschrijving boven de 4000 tekens ─────────────────────────────────
def test_omschrijving_wordt_ingekort_op_een_woordgrens():
    lang = ("Duesenberg Imperial met Bluebird Strap actie " * 200)
    assert len(lang) > _MAX_OMSCHRIJVING
    kort = _kort_omschrijving(lang)
    assert len(kort) <= _MAX_OMSCHRIJVING
    assert not kort.endswith(" ")
    # Een tekst die er wél in past blijft ongemoeid.
    assert _kort_omschrijving("kort verhaal") == "kort verhaal"


def test_voorraadartikel_past_binnen_ebays_grenzen_en_heeft_een_productcode(monkeypatch):
    """Bouwt precies de lading die create_listing naar eBay stuurt, zonder
    eBay te bellen. Op de oude code is de omschrijving 4219 tekens lang en
    ontbreekt ean/mpn — allebei een geweigerde advertentie."""
    verstuurd = {}

    class NepAntwoord:
        status_code = 200
        is_success = True

        def json(self):
            return {"offerId": "1", "listingId": "2", "sku": "s"}

        @property
        def text(self):
            return "{}"

    class NepClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def put(self, url, json=None, headers=None):
            if "inventory_item" in url:
                verstuurd.update(json)
            return NepAntwoord()

        async def post(self, url, json=None, headers=None):
            return NepAntwoord()

        async def get(self, url, **kw):
            return NepAntwoord()

    platform = EbayPlatform()

    async def geen_vernieuwing(creds):
        return creds

    # ALTIJD VIA monkeypatch, NOOIT MET DE HAND OVERSCHRIJVEN (21-09-2026).
    # De eerste versie van deze test zette beleid_voor_plaatsing en
    # _get_required_aspects rechtstreeks om en zette ze niet terug. Twee tests in
    # test_ebay_complete_lus.py vielen daarna om, maar alleen als ze ná deze
    # draaiden — een "kapotte" test die los draaiend gewoon slaagde.
    import backend.platforms.ebay_beleid as beleid
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: NepClient())
    monkeypatch.setattr(platform, "_ensure_fresh_token", geen_vernieuwing)
    monkeypatch.setattr(platform, "_ensure_location", lambda *a, **kw: _klaar())
    monkeypatch.setattr(beleid, "beleid_voor_plaatsing", lambda *a, **kw: _klaar({}))
    monkeypatch.setattr(ebay_mod, "_get_required_aspects", lambda cid: _klaar([]))
    if True:
        item = {
            "id": "i1", "sku": "BB-1",
            "title": "Duesenberg Imperial D-Tron 2019",
            "description": "Bluebird Strap actie. " * 300,   # > 4000 tekens
            "price": 2450, "photo_urls": ["https://x/1.jpg"],
            "brand": "Duesenberg", "condition": "good",
            "ebay_category_id": "33034",
        }
        assert len(item["description"]) > _MAX_OMSCHRIJVING
        asyncio.run(platform.create_listing(item, {"access_token": "t", "user_id": "u1",
                                                   "token_expires_at": None}))

    product = verstuurd["product"]
    assert len(product["description"]) <= _MAX_OMSCHRIJVING, len(product["description"])
    assert product.get("ean") == [_GEEN_PRODUCTCODE], product.get("ean")
    # Merk en mpn horen bij elkaar. Gemeten tegen de echte eBay-API op
    # 21-09-2026: merk zonder mpn wordt geweigerd met "<BrandMPN> ongeldig",
    # merk mét mpn publiceert (advertentie 178516553258).
    assert product.get("brand") == "Duesenberg", product.get("brand")
    assert product.get("mpn") == _GEEN_PRODUCTCODE, product.get("mpn")


def _klaar(waarde=None):
    fut = asyncio.get_event_loop().create_future() if False else None
    async def _c():
        return waarde
    return _c()


# ── De voor-en-na-proef ──────────────────────────────────────────────────
# Zonder dit stuk weet je alleen dat de nieuwe code werkt, niet dat ze iets
# repareert. Hieronder draait de versie van vóór deze reparatie (rechtstreeks
# uit git) onder exact dezelfde omstandigheden, en die moet falen zoals Johan
# het zag.
# NIET HEAD (kennisbank: "voor-en-na-proef mag geen HEAD gebruiken"). Zodra de
# reparatie gecommit is, IS HEAD de nieuwe code en vergelijkt de test zich met
# zichzelf. Dat gebeurde hier één keer echt. 0a8576aa is de laatste ebay.py van
# vóór deze reparatie.
VOOR_DE_REPARATIE = "0a8576aa"


def _oude_module(tmp_path):
    import importlib.util
    import subprocess
    bron = subprocess.run(
        ["git", "show", f"{VOOR_DE_REPARATIE}:backend/platforms/ebay.py"],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True, text=True, check=True).stdout
    pad = tmp_path / "ebay_oud.py"
    pad.write_text(bron, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("ebay_oud", pad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ebay_oud"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_oude_versie_gaf_johan_de_url_in_zijn_gezicht(tmp_path, monkeypatch):
    oud = _oude_module(tmp_path)

    class NepAntwoord:
        status_code = 400
        is_success = False
        text = '{"error":"invalid_grant"}'
        request = httpx.Request("POST", "https://api.ebay.com/identity/v1/oauth2/token")

        def json(self):
            return {"error": "invalid_grant"}

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "Client error '400 Bad Request' for url "
                "'https://api.ebay.com/identity/v1/oauth2/token'",
                request=self.request, response=self)

    class NepClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return NepAntwoord()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: NepClient())
    with pytest.raises(httpx.HTTPStatusError) as fout:
        asyncio.run(oud.EbayPlatform().refresh_credentials(
            {"refresh_token": "x", "user_id": "u1"}))
    # Dit is letterlijk wat er op 20-09 in zijn dashboard stond.
    assert "oauth2/token" in str(fout.value)


def test_oude_versie_stuurde_4219_tekens_en_geen_productcode(tmp_path, monkeypatch):
    oud = _oude_module(tmp_path)
    verstuurd = {}

    class NepAntwoord:
        status_code = 200
        is_success = True

        def json(self):
            return {"offerId": "1", "listingId": "2", "sku": "s"}

        @property
        def text(self):
            return "{}"

    class NepClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def put(self, url, json=None, headers=None):
            if "inventory_item" in url:
                verstuurd.update(json)
            return NepAntwoord()

        async def post(self, url, json=None, headers=None):
            return NepAntwoord()

        async def get(self, url, **kw):
            return NepAntwoord()

    platform = oud.EbayPlatform()

    async def geen_vernieuwing(creds):
        return creds

    import backend.platforms.ebay_beleid as beleid
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: NepClient())
    monkeypatch.setattr(platform, "_ensure_fresh_token", geen_vernieuwing)
    monkeypatch.setattr(platform, "_ensure_location", lambda *a, **kw: _klaar())
    monkeypatch.setattr(beleid, "beleid_voor_plaatsing", lambda *a, **kw: _klaar({}))
    monkeypatch.setattr(oud, "_get_required_aspects", lambda cid: _klaar([]))
    if True:
        item = {
            "id": "i1", "sku": "BB-1",
            "title": "Duesenberg Imperial D-Tron 2019",
            "description": "Bluebird Strap actie. " * 300,
            "price": 2450, "photo_urls": ["https://x/1.jpg"],
            "brand": "Duesenberg", "condition": "good",
            "ebay_category_id": "33034",
        }
        asyncio.run(platform.create_listing(item, {"access_token": "t", "user_id": "u1",
                                                   "token_expires_at": None}))

    product = verstuurd["product"]
    assert len(product["description"]) > _MAX_OMSCHRIJVING, "oude code kortte al in?"
    assert "ean" not in product and "brand" not in product, "oude code stuurde al een productcode?"


def test_zonder_merk_gaan_merk_en_mpn_allebei_niet_mee(monkeypatch):
    """eBay weigert een half paar. Heeft het artikel geen merk, dan sturen we
    alleen de EAN — gemeten: dat publiceert (advertentie 178516553842)."""
    from backend.platforms.ebay import _GEEN_PRODUCTCODE as G
    # De opbouw van `product` in create_listing, los nagespeeld op precies de
    # regels die hierover gaan, zodat deze test geen eBay nodig heeft.
    for merk, verwacht_paar in (("Fender", True), (None, False), ("", False)):
        product = {}
        item = {"brand": merk}
        product["ean"] = [str(item["ean"])] if item.get("ean") else [G]
        if item.get("brand"):
            product["brand"] = item["brand"]
            product["mpn"] = str(item["mpn"]) if item.get("mpn") else G
        assert ("brand" in product) == verwacht_paar
        assert ("mpn" in product) == verwacht_paar, merk


# ── 3. Een rij in de database is geen koppeling ──────────────────────────
def test_status_toont_ebay_niet_als_gekoppeld_zodra_ebay_hem_weigert(monkeypatch):
    """Op de oude code stond eBay twee dagen op "✓ Connected" terwijl elke
    plaatsing mislukte. Deze test faalt op die versie."""
    import backend.api.platforms as platforms_mod

    rijen = [
        {"platform": "marktplaats", "extra_data": {"cookies": []}},
        {"platform": "ebay", "extra_data": {
            "ship_from": {"city": "Fochteloo"},
            "koppeling_kapot": {"sinds": "2026-09-19T11:06:48+00:00",
                                "reden": "400: invalid_grant"},
        }},
    ]

    class NepTabel:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        def execute(self):
            return type("R", (), {"data": rijen})()

    monkeypatch.setattr(platforms_mod, "get_db",
                        lambda: type("DB", (), {"table": lambda self, n: NepTabel()})())

    uit = platforms_mod.platform_status(user_id="u1")
    assert "marktplaats" in uit["connected"]
    assert "ebay" not in uit["connected"], "eBay hoort hier niet meer als gekoppeld te staan"
    assert uit["opnieuw_koppelen"][0]["platform"] == "ebay"
    assert "invalid_grant" in uit["opnieuw_koppelen"][0]["reden"]


def test_oude_status_zei_gewoon_gekoppeld(tmp_path, monkeypatch):
    """Voor-en-na: dezelfde twee rijen door de versie van vóór de reparatie."""
    import subprocess
    bron = subprocess.run(["git", "show", "0b33d5a6:backend/api/platforms.py"],
                          cwd=str(Path(__file__).resolve().parents[1]),
                          capture_output=True, text=True, check=True).stdout
    # Alleen het endpoint zelf uitsnijden — de rest van dat bestand sleept de
    # halve applicatie mee.
    start = bron.index("def platform_status(")
    eind = bron.index("\n\n", bron.index("return", start))
    code = bron[start:eind]
    ruimte = {"get_db": None, "Depends": lambda f: None, "get_current_user": None}

    rijen = [{"platform": "ebay"}]

    class NepTabel:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        def execute(self):
            return type("R", (), {"data": rijen})()

    ruimte["get_db"] = lambda: type("DB", (), {"table": lambda self, n: NepTabel()})()
    exec(code, ruimte)
    uit = ruimte["platform_status"](user_id="u1")
    assert uit["connected"] == ["ebay"], "de oude versie keek alleen of de rij bestond"


# ── 4. Een gitaar hoort niet tussen de cd's ──────────────────────────────
# De suggesties hieronder zijn de ECHTE antwoorden van eBay's Taxonomy-API,
# opgehaald op 21-09-2026 via /api/platforms/ebay/category-suggest op productie.
# Niet verzonnen en niet uit het hoofd overgeschreven.
_ECHTE_SUGGESTIES = {
    "Nieuw Homestead OMC Dark Blue": [
        ("176984", ["11233"]),          # Muziek, cd's en platen > CD's
        ("176985", ["11233"]),          # Vinyl en platen
    ],
    "Nieuw Reverend Eastsider Bariton": [
        ("176985", ["11233"]),
        ("219", ["182982", "8662", "1"]),
    ],
    "Homestead Javatar Parlor": [
        ("183050", ["182982", "8662", "1"]),   # Verzamelkaarten
        ("348", ["222", "220"]),               # Speelgoedfiguurtjes
        ("33034", ["3858", "619"]),            # Elektrische gitaren
    ],
    "Martin D35 1979": [
        ("2036", ["8830", "1"]),               # Buttons en pins
        ("180273", ["222", "220"]),            # Miniatuurvoertuigen
        ("33034", ["3858", "619"]),
    ],
    "Positive Grid Reactor 50": [
        ("183720", ["36085"]),                 # Auto: verkoopbrochures
    ],
}


def _kies(suggesties, tak):
    """De keuze zoals resolve_category_id hem maakt, met en zonder takfilter."""
    rijen = [{"category_id": c, "voorouders": v} for c, v in suggesties]
    if tak:
        rijen = [r for r in rijen if tak in set(r["voorouders"])]
    return rijen[0]["category_id"] if rijen else None


def test_de_eigen_rubriek_houdt_de_gok_binnen_de_juiste_tak():
    from backend.platforms.ebay import _tak_voor_rubriek
    tak = _tak_voor_rubriek("muziek snaarinstrumenten gitaren")
    assert tak == "619"

    zonder = {t: _kies(s, None) for t, s in _ECHTE_SUGGESTIES.items()}
    met = {t: _kies(s, tak) for t, s in _ECHTE_SUGGESTIES.items()}

    # Zo ging het vóór deze reparatie: vier van de vijf gitaren belandden
    # buiten de muziekinstrumenten.
    assert zonder["Nieuw Homestead OMC Dark Blue"] == "176984"      # CD's
    assert zonder["Martin D35 1979"] == "2036"                      # buttons en pins
    assert zonder["Positive Grid Reactor 50"] == "183720"           # autobrochures

    # En zo nu: of de juiste gitaarrubriek, of niets — en niets betekent dat
    # het scherm om een rubriek vraagt in plaats van stil te gokken.
    assert met["Martin D35 1979"] == "33034"
    assert met["Homestead Javatar Parlor"] == "33034"
    assert met["Nieuw Homestead OMC Dark Blue"] is None
    assert met["Positive Grid Reactor 50"] is None
    assert all(v in (None, "33034") for v in met.values()), met

    # Een rubriek buiten de muziek verandert niets.
    assert _tak_voor_rubriek("jeans") is None
    assert _tak_voor_rubriek(None) is None
