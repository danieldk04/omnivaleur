"""Een eBay-site per klant (20-10-2026): standaard ebay.nl, EBAY_BE op verzoek.

WAAROM: de eBay-site was één serverbrede instelling. Een klant uit het buitenland
kon niets anders dan ebay.nl krijgen. Nu kiest extra_data.ebay_marktplaats de site,
en wie niets koos blijft precies zoals het was (EBAY_NL, oude beleidssleutel).

De proef draait de echte code tegen de nep-eBay uit test_ebay_complete_lus. Wat
hier NIET bewezen is: of eBay "BE_StandardDelivery" en de rubrieken op ebay.be
accepteert. Dat kan alleen een echte proefadvertentie op de server."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_ebay_complete_lus import ebay, _item, _creds  # noqa: E402,F401
from backend.platforms import ebay as E  # noqa: E402
from backend.platforms import ebay_beleid as B  # noqa: E402

VERZENDING = {"kosten": 5.0, "verzenddagen": 3, "retourdagen": 30, "ophalen": True}


@pytest.fixture
def opname(ebay, monkeypatch):
    """Legt vast wat er echt naar eBay ging (inclusief koppen) en wat er bewaard werd."""
    verzoeken, bewaard, gekozen = [], [], []
    echt = ebay.handler

    def handler(request):
        verzoeken.append(request)
        return echt(request)
    ebay.handler = handler

    monkeypatch.setattr(B, "bewaar_extra", lambda uid, w: bewaard.append(w) or w)

    async def kies(titel, merk, categorie, geslacht, marktplaats=None):
        gekozen.append(marktplaats)
        return "99999"
    monkeypatch.setattr(E, "resolve_category_id", kies)
    return verzoeken, bewaard, gekozen, ebay


def _plaats(creds):
    item = _item()
    return asyncio.run(E.EbayPlatform().create_listing(item, creds))


def _offer(nep):
    return next(iter(nep.offers.values()))


def test_zonder_keuze_blijft_alles_ebay_nl(opname):
    verzoeken, bewaard, gekozen, nep = opname
    uit = _plaats({**_creds(verzending=VERZENDING), "user_id": "u1"})
    assert _offer(nep)["marketplaceId"] == "EBAY_NL"
    assert "ebay.nl/itm/" in uit["platform_listing_url"]
    assert bewaard == [{"ebay_beleid": nep_beleid(nep)}], "NL houdt de oude beleidssleutel"
    puts = [r for r in verzoeken if r.method == "PUT" and "inventory_item" in r.url.path]
    assert puts and all(r.headers["Content-Language"] == "nl-NL" for r in puts)
    assert nep.beleid["fulfillment"]["shippingOptions"][0]["shippingServices"][0]["shippingServiceCode"] == "NL_StandardDelivery"
    assert _offer(nep)["categoryId"] == "15687", "NL gebruikt de bewaarde rubriek zoals altijd"
    assert gekozen == []


def nep_beleid(nep):
    return {"fulfillment": "ful-1", "payment": "pay-1", "return": "ret-1"}


def test_belgie_gebruikt_ebay_be_overal(opname):
    verzoeken, bewaard, gekozen, nep = opname
    creds = {**_creds(verzending=VERZENDING, ebay_marktplaats="EBAY_BE"), "user_id": "u1"}
    uit = _plaats(creds)
    offer = _offer(nep)
    assert offer["marketplaceId"] == "EBAY_BE"
    assert "ebay.be/itm/" in uit["platform_listing_url"]
    assert bewaard == [{"ebay_beleid_EBAY_BE": nep_beleid(nep)}], "BE krijgt een eigen beleidssleutel"
    puts = [r for r in verzoeken if r.method == "PUT" and "inventory_item" in r.url.path]
    assert puts and all(r.headers["Content-Language"] == "nl-BE" for r in puts)
    beleidsvragen = [r for r in verzoeken if "_policy/get_by_policy_name" in r.url.path]
    assert beleidsvragen and all(r.url.params["marketplace_id"] == "EBAY_BE" for r in beleidsvragen)
    fulf = nep.beleid["fulfillment"]
    assert fulf["marketplaceId"] == "EBAY_BE"
    diensten = fulf["shippingOptions"][0]["shippingServices"]
    assert [d["shippingServiceCode"] for d in diensten] == ["BE_StandardDelivery"], "geen NL_PickUp op ebay.be"
    assert offer["categoryId"] == "99999" and gekozen == ["EBAY_BE"], \
        "de ebay.nl-rubriek van het artikel mag niet naar ebay.be"


def test_onbekende_keuze_valt_terug_op_standaard():
    assert B.marktplaats_van({"extra_data": {"ebay_marktplaats": "EBAY_XX"}}) == "EBAY_NL"
    assert B.marktplaats_van({"extra_data": {"ebay_marktplaats": "EBAY_BE"}}) == "EBAY_BE"
    assert B.marktplaats_van({}) == "EBAY_NL" and B.marktplaats_van(None) == "EBAY_NL"


def test_rubriekboom_wordt_per_site_opgevraagd(monkeypatch):
    gevraagd = []

    async def token():
        return "t"

    class Antwoord:
        def __init__(self, mp): self.mp = mp
        def raise_for_status(self): pass
        def json(self): return {"categoryTreeId": {"EBAY_NL": "146", "EBAY_BE": "23"}[self.mp]}

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, params=None, headers=None):
            gevraagd.append(params["marketplace_id"]); return Antwoord(params["marketplace_id"])

    monkeypatch.setattr(E, "_get_app_token", token)
    monkeypatch.setattr(E.httpx, "AsyncClient", Client)
    E._category_tree_cache.clear()
    assert asyncio.run(E._get_category_tree_id()) == "146"
    assert asyncio.run(E._get_category_tree_id("EBAY_BE")) == "23"
    assert asyncio.run(E._get_category_tree_id("EBAY_BE")) == "23"
    assert gevraagd == ["EBAY_NL", "EBAY_BE"], "elke site één keer opgevraagd en onthouden"
