"""Koppelen met een sleutel die de winkelier zelf aanmaakt.

WAAROM DEZE WEG BESTAAT (28-08-2026)
Shopify zette de app-aanvraag op "paused": ze accepteren geen apps meer die
koppelen met een marktplaats buiten Shopify, en dat geldt voor álle zulke apps.
Er is dus geen versie van Omnivaleur die daar doorheen komt zolang ze naar
Marktplaats, Vinted en eBay publiceert. Een app die de winkelier zelf in zijn
eigen beheerscherm maakt heeft geen enkele beoordeling nodig en gebruikt dezelfde
Admin API — alleen het verkrijgen van de sleutel verschilt.

Twee dingen moeten hier waterdicht zijn:

1. Een sleutel wordt NOOIT opgeslagen zonder dat we hem bij Shopify hebben
   nagekeken. Niemand anders controleert hem nog, en een sleutel die te weinig
   mag levert anders pas weken later een onverklaarbare fout op midden in een
   publicatie.

2. De verkoopmelding moet blijven werken. Die liep over de webhook orders/paid,
   en die hoort bij ÓNZE app — bij een zelfgemaakte app komt hij nooit binnen.
   Zonder vangnet zou een winkelier stil de belangrijkste functie kwijtraken:
   iets dat in de eigen winkel verkocht is, blijft dan overal elders te koop.
"""
import asyncio
from pathlib import Path

import pytest

from backend.platforms.shopify import (AANBEVOLEN_SCOPES, VERPLICHTE_SCOPES,
                                       controleer_admin_token,
                                       is_valid_admin_token, is_valid_shop_domain)

ROOT = Path(__file__).resolve().parents[1]
ORDERS = (ROOT / "backend/services/shopify_orders.py").read_text(encoding="utf-8")
PLATFORMS = (ROOT / "backend/api/platforms.py").read_text(encoding="utf-8")
APP = (ROOT / "frontend/app.html").read_text(encoding="utf-8")


# ── 1. De vorm van winkel en sleutel ─────────────────────────────────────────

@pytest.mark.parametrize("tok,ok", [
    ("shpat_" + "a" * 32, True),
    ("shpat_" + "0123456789abcdef" * 2, True),
    ("shpss_" + "a" * 32, False),       # storefront-sleutel, werkt hier niet
    ("shpca_" + "a" * 32, False),
    ("shpat_kort", False),
    ("", False),
    (None, False),
])
def test_sleutelvorm(tok, ok):
    assert is_valid_admin_token(tok) is ok


def test_alleen_echte_shopify_winkels():
    """Een vrij in te vullen adres is een open deur naar onze eigen server."""
    assert is_valid_shop_domain("mijn-winkel.myshopify.com")
    assert not is_valid_shop_domain("evil.com")
    assert not is_valid_shop_domain("mijn-winkel.myshopify.com.evil.com")
    assert not is_valid_shop_domain("localhost")
    assert not is_valid_shop_domain("169.254.169.254")


@pytest.mark.parametrize("shop,tok", [
    ("evil.com", "shpat_" + "a" * 32),
    ("x.myshopify.com", "shpss_" + "a" * 32),
    ("x.myshopify.com", ""),
    ("", "shpat_" + "a" * 32),
])
def test_onbruikbare_invoer_bereikt_shopify_niet(shop, tok, monkeypatch):
    """Fout ingevulde gegevens moeten worden afgevangen vóór er een verzoek uitgaat."""
    import httpx

    def nooit(*a, **k):
        raise AssertionError("er ging tóch een verzoek naar buiten")

    monkeypatch.setattr(httpx.AsyncClient, "get", nooit)
    with pytest.raises(ValueError):
        asyncio.run(controleer_admin_token(shop, tok))


# ── 2. Wat Shopify terugstuurt ───────────────────────────────────────────────

class _Antwoord:
    def __init__(self, code, data=None):
        self.status_code = code
        self._data = data or {}
        self.text = str(self._data)

    def json(self):
        return self._data


def _nep_shopify(monkeypatch, scopes, shop_code=200):
    import httpx

    async def get(self, url, **kw):
        if "access_scopes" in url:
            return _Antwoord(200, {"access_scopes": [{"handle": s} for s in scopes]})
        return _Antwoord(shop_code, {"shop": {"name": "Testwinkel"}})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)


ALLES = list(VERPLICHTE_SCOPES) + list(AANBEVOLEN_SCOPES)


def test_volledige_sleutel_wordt_geaccepteerd(monkeypatch):
    _nep_shopify(monkeypatch, ALLES)
    r = asyncio.run(controleer_admin_token("x.myshopify.com", "shpat_" + "a" * 32))
    assert r["shop"] == "x.myshopify.com"
    assert r["shop_name"] == "Testwinkel"
    assert r["aanbevolen_ontbreekt"] == []


def test_te_weinig_rechten_wordt_geweigerd_met_uitleg(monkeypatch):
    _nep_shopify(monkeypatch, ["read_products"])   # write_products mist
    with pytest.raises(ValueError) as e:
        asyncio.run(controleer_admin_token("x.myshopify.com", "shpat_" + "a" * 32))
    assert "write_products" in str(e.value), "de winkelier moet weten wát er mist"


def test_ontbrekende_extras_blokkeren_niet_maar_worden_gemeld(monkeypatch):
    """Precies de stand van de winkel die vandaag gekoppeld is: alleen producten."""
    _nep_shopify(monkeypatch, ["read_products", "write_products"])
    r = asyncio.run(controleer_admin_token("x.myshopify.com", "shpat_" + "a" * 32))
    assert "read_orders" in r["aanbevolen_ontbreekt"]


@pytest.mark.parametrize("code,fragment", [
    (401, "rejected"),
    (403, "rejected"),
    (404, "different store"),
    (500, "unexpected"),
])
def test_shopify_fouten_worden_leesbare_taal(monkeypatch, code, fragment):
    import httpx

    async def get(self, url, **kw):
        return _Antwoord(code, {})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    with pytest.raises(ValueError) as e:
        asyncio.run(controleer_admin_token("x.myshopify.com", "shpat_" + "a" * 32))
    assert fragment in str(e.value)
    assert "_ssl" not in str(e.value) and "Traceback" not in str(e.value)


# ── 3. Opslaan gebeurt pas ná de controle ────────────────────────────────────

def test_endpoint_slaat_niets_op_zonder_controle():
    fn = PLATFORMS.split("async def shopify_connect_token(")[1].split("\n@router.")[0]
    assert fn.index("controleer_admin_token(") < fn.index("_save_credentials("), \
        "een ongecontroleerde sleutel mag nooit in de database belanden"
    assert 'raise HTTPException(status_code=400' in fn
    assert '"koppeling": "eigen_sleutel"' in fn, "we moeten weten hoe er gekoppeld is"


# ── 4. De verkoopmelding blijft werken zonder webhook ────────────────────────

def test_verkoopcontrole_staat_in_de_planner():
    sched = (ROOT / "backend/scheduler.py").read_text(encoding="utf-8")
    assert "controleer_shopify_verkopen" in sched
    assert 'id="shopify_verkopen"' in sched


def test_verkoop_wordt_altijd_op_de_juiste_verkoper_gezocht():
    """Twee winkeliers kunnen dezelfde SKU gebruiken. Zonder user_id zou een
    verkoop bij de een de advertenties van de ander overal weghalen."""
    blok = ORDERS.split('db.table("items")')[1][:300]
    assert '.eq("user_id"' in blok
    assert '.eq("sku", sku)' in blok


def test_merkteken_schuift_pas_op_na_een_geslaagde_ronde():
    """Anders slaat een mislukte ronde stilletjes een verkoop over."""
    i = ORDERS.index("orders_gezien_tot")
    j = ORDERS.rindex("orders_gezien_tot")
    assert i != j, "er moet zowel gelezen als geschreven worden"
    assert "OVERLAP_MINUTEN" in ORDERS, "een grens zonder speling laat een order ertussenuit vallen"


def test_een_winkel_zonder_opgeslagen_domein_wordt_overgeslagen():
    """Gokken op de verkeerde winkel is erger dan niets doen."""
    assert "if not shop or not token" in ORDERS


def test_geen_toegang_stopt_niet_de_hele_ronde():
    assert "PermissionError" in ORDERS
    assert ORDERS.count("continue") >= 3


# ── 5. Wat de winkelier op zijn scherm ziet ──────────────────────────────────

def test_het_scherm_noemt_elke_benodigde_toestemming():
    venster = APP.split('id="shopify-connect-overlay"')[1].split("</div>\n\n<div id=")[0]
    for scope in list(VERPLICHTE_SCOPES) + list(AANBEVOLEN_SCOPES):
        assert scope in venster, f"{scope} staat niet in de uitleg"


def test_het_geheim_blijft_niet_in_een_gesloten_venster_staan():
    fn = APP.split("function closeShopifyConnect()")[1][:300]
    assert "shopify-secret-input').value = ''" in fn


def test_het_geheimveld_is_afgeschermd():
    venster = APP.split('id="shopify-connect-overlay"')[1].split("</div>\n\n<div id=")[0]
    assert 'id="shopify-secret-input" type="password"' in venster


def test_rechten_worden_gelezen_met_komma_of_spatie():
    """Shopify levert ze soms met komma's, soms met spaties. Alleen op komma
    splitsen maakte er één sliert van, en meldde dan onterecht dat read_products
    ontbrak terwijl het recht gewoon aan stond (Revaleur, 28-08-2026)."""
    import re as _re
    src = (ROOT / "backend/platforms/shopify.py").read_text(encoding="utf-8")
    fn = src.split("async def vraag_token(")[1].split("\n\n# ")[0]
    patroon = _re.search(r'_re?\.?split\(r"\[([^"]+)\]\+"', fn) or _re.search(r'split\(r"(\[[^"]+\]\+)"', fn)
    assert "re.split" in fn and "\\s" in fn, "moet ook op spaties splitsen"


def test_leeg_rechtenantwoord_leidt_niet_tot_een_onterechte_afwijzing():
    src = (ROOT / "backend/platforms/shopify.py").read_text(encoding="utf-8")
    fn = src.split("async def controleer_app_gegevens(")[1].split("\nasync def ")[0]
    assert "if not toegekend:" in fn
    assert "access_scopes.json" in fn, "bij een leeg antwoord alsnog bij de bron navragen"


# ── 6. De weg die voor iedere klant werkt ────────────────────────────────────

def test_er_wordt_een_echte_sleutel_opgehaald_voor_we_iets_opslaan():
    """Alleen door het écht te doen weten we dat het werkt. Precies dat ging mis
    toen het venster stappen beschreef die Shopify allang had geschrapt."""
    fn = PLATFORMS.split("async def shopify_connect_app(")[1].split("\n@router.")[0]
    assert fn.index("controleer_app_gegevens(") < fn.index("_save_credentials(")
    assert '"koppeling": "eigen_app"' in fn
    assert '"client_secret"' in fn, "zonder het geheim kan de sleutel morgen niet ververst worden"


def test_de_sleutel_wordt_ververst_voor_hij_verloopt():
    """De sleutel van een eigen app leeft 24 uur. Zonder verversen valt alles
    elke dag stil op een 401 die niemand ziet."""
    src = (ROOT / "backend/platforms/shopify.py").read_text(encoding="utf-8")
    fn = src.split("async def _shop_creds(")[1].split("\nasync def ")[0]
    assert "vraag_token(" in fn
    assert "TOKEN_MARGE_MINUTEN" in fn, "op het laatste moment verversen breekt midden in een publicatie"
    assert "token_expires_at" in fn


def test_een_koppeling_zonder_geheim_blijft_gewoon_werken():
    """OAuth-koppelingen en oude custom apps hebben geen client_id/secret en
    hun sleutel verloopt niet — die mogen niet ineens stukgaan."""
    src = (ROOT / "backend/platforms/shopify.py").read_text(encoding="utf-8")
    fn = src.split("async def _shop_creds(")[1].split("\nasync def ")[0]
    assert "if not (shop and client_id and client_secret):" in fn
    assert 'return shop, credentials.get("access_token")' in fn


def test_de_verkoopronde_gebruikt_dezelfde_verversing():
    assert "_shop_creds" in ORDERS, "anders loopt die ronde elke dag vast op een verlopen sleutel"


def test_de_verkoopronde_overschrijft_geen_verse_sleutel():
    """Het merkteken wegschrijven met de OUDE gegevens zou de zojuist opgehaalde
    vervaldatum weer wissen."""
    staart = ORDERS.split("orders_gezien_tot\": nieuw")[0][-700:]
    assert 'select("extra_data")' in staart
    assert "basis" in staart


def test_ontbrekende_verkooprechten_worden_op_het_scherm_gemeld():
    fn = APP.split("async function submitShopifyToken()")[1].split("\nasync function ")[0]
    assert "missing_optional_scopes" in fn
    assert "read_orders" in fn
