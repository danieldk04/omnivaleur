"""Toon (de Juiste Toon, 96e30080), 27-10-2026: zijn eerste eBay-advertentie, een tapijt,
stond op "mislukt" met

    eBay error while publishing offer: ... invalid item condition information.
    De opgegeven ID voor de staat is ongeldig voor de geselecteerde ID van de primaire rubriek.

Oorzaak: bij staat "fair" stuurden we altijd USED_GOOD (5000). Kleding kent die,
maar de rubriek Tapijten (45510) kent alleen Nieuw en Gebruikt (USED_EXCELLENT, 3000).
eBay accepteerde het inventarisitem en de offer en weigerde pas bij het publiceren.
Van alle 269 eBay-advertenties in de database is dit de enige met deze fout.

Deze tests spelen eBay na: een rubriek die alleen NEW en USED_EXCELLENT accepteert.

Draaien:  python3.13 -m pytest tests/test_ebay_staat_per_rubriek.py -q
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.platforms import ebay as ebay_mod  # noqa: E402
from backend.platforms.ebay import _kies_staat, _staat_alternatieven  # noqa: E402

TOEGESTAAN_TAPIJT = {"1000", "3000"}                     # Nieuw en Gebruikt
TOEGESTAAN_KLEDING = {"1000", "3000", "4000", "5000", "6000"}


class _Antwoord:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self.is_success = status < 400
        self._data = data if data is not None else {}
        self.text = str(self._data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.is_success:
            raise httpx.HTTPStatusError("fout", request=None, response=None)


class _FakeEbay:
    """Een eBay-rubriek met een vaste lijst toegestane conditie-ID's."""

    ID = {"NEW": "1000", "USED_EXCELLENT": "3000", "USED_VERY_GOOD": "4000",
          "USED_GOOD": "5000", "USED_ACCEPTABLE": "6000"}

    def __init__(self, toegestaan, metadata_werkt=True):
        self.toegestaan, self.metadata_werkt = toegestaan, metadata_werkt
        self.staten_gestuurd, self.publicaties = [], []
        self.huidige = None

    def client(self):
        eb = self

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def put(self, url, json=None, headers=None):
                if "inventory_item" in url:
                    eb.huidige = json["condition"]
                    eb.staten_gestuurd.append(json["condition"])
                return _Antwoord(204)

            async def post(self, url, json=None, headers=None):
                if url.endswith("/offer"):
                    return _Antwoord(201, {"offerId": "o1"})
                if url.endswith("/publish"):
                    eb.publicaties.append(eb.huidige)
                    if eb.ID[eb.huidige] in eb.toegestaan:
                        return _Antwoord(200, {"listingId": "L1"})
                    return _Antwoord(400, {"errors": [{
                        "errorId": 25021,
                        "message": "The eBay listing associated with the inventory item, or the "
                                   "unpublished offer has invalid item condition information. "
                                   "De opgegeven ID voor de staat is ongeldig voor de geselecteerde "
                                   "ID van de primaire rubriek.",
                    }]})
                return _Antwoord(200, {})

            async def get(self, url, **kw):
                if "get_item_condition_policies" in url:
                    if not eb.metadata_werkt:
                        return _Antwoord(500)
                    return _Antwoord(200, {"itemConditionPolicies": [{
                        "categoryId": "45510",
                        "itemConditions": [{"conditionId": i} for i in sorted(eb.toegestaan)],
                    }]})
                return _Antwoord(200, {})

        return Client()


def _plaats(monkeypatch, eb, conditie="fair"):
    async def klaar(*a, **kw):
        return None

    async def vers(creds):
        return creds

    async def geen_beleid(*a, **kw):
        return {}

    async def geen_aspecten(*a, **kw):
        return []

    async def token():
        return "app-token"

    import backend.platforms.ebay_beleid as beleid
    platform = ebay_mod.EbayPlatform()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: eb.client())
    monkeypatch.setattr(platform, "_ensure_fresh_token", vers)
    monkeypatch.setattr(platform, "_ensure_location", klaar)
    monkeypatch.setattr(beleid, "beleid_voor_plaatsing", geen_beleid)
    monkeypatch.setattr(ebay_mod, "_get_required_aspects", geen_aspecten)
    monkeypatch.setattr(ebay_mod, "_get_app_token", token)
    monkeypatch.setattr(ebay_mod, "_toegestane_staten_cache", {})
    item = {"id": "i1", "sku": "tll07", "title": "Groen oosters tapijt 62/30",
            "description": "Uniek groen oosters tapijtje", "price": 20.0,
            "photo_urls": ["https://x/1.jpg"], "condition": conditie,
            "category": "wonen tapijten en kleden"}
    return asyncio.run(platform.create_listing(
        item, {"access_token": "t", "user_id": "u1", "token_expires_at": None}))


def test_tapijt_fair_wordt_gebruikt_en_publiceert_in_een_keer(monkeypatch):
    eb = _FakeEbay(TOEGESTAAN_TAPIJT)
    uit = _plaats(monkeypatch, eb, "fair")
    assert uit["platform_listing_id"] == "L1"
    assert eb.staten_gestuurd == ["USED_EXCELLENT"], eb.staten_gestuurd
    assert eb.publicaties == ["USED_EXCELLENT"], "één publicatiepoging, geen omweg"


def test_zonder_opzoeking_herstelt_het_publiceren_zichzelf(monkeypatch):
    """Metadata-API valt weg: de eerste poging (USED_GOOD) wordt geweigerd, daarna
    proberen we de naastgelegen gebruikte staten tot eBay het goedvindt."""
    eb = _FakeEbay(TOEGESTAAN_TAPIJT, metadata_werkt=False)
    uit = _plaats(monkeypatch, eb, "fair")
    assert uit["platform_listing_id"] == "L1"
    assert eb.publicaties[0] == "USED_GOOD" and eb.publicaties[-1] == "USED_EXCELLENT"
    assert "NEW" not in eb.publicaties, "een gebruikt stuk mag nooit als nieuw eindigen"


def test_kleding_houdt_zijn_eigen_staat(monkeypatch):
    eb = _FakeEbay(TOEGESTAAN_KLEDING)
    _plaats(monkeypatch, eb, "fair")
    assert eb.staten_gestuurd == ["USED_GOOD"]
    eb = _FakeEbay(TOEGESTAAN_KLEDING)
    _plaats(monkeypatch, eb, "good")
    assert eb.staten_gestuurd == ["USED_EXCELLENT"]


def test_rubriek_alleen_nieuw_weigert_gebruikt_stuk_met_heldere_tekst(monkeypatch):
    eb = _FakeEbay({"1000"})
    with pytest.raises(RuntimeError) as fout:
        _plaats(monkeypatch, eb, "fair")
    assert "only allows new items" in str(fout.value)
    assert "NEW" not in eb.staten_gestuurd, "nooit als nieuw aanbieden"


def test_nieuw_blijft_nieuw(monkeypatch):
    eb = _FakeEbay(TOEGESTAAN_TAPIJT)
    _plaats(monkeypatch, eb, "new_with_tags")
    assert eb.staten_gestuurd == ["NEW"]


def test_kies_staat_kiest_dichtstbijzijnde_gebruikte():
    assert _kies_staat("USED_GOOD", {"NEW", "USED_EXCELLENT"}) == "USED_EXCELLENT"
    assert _kies_staat("USED_ACCEPTABLE", {"NEW", "USED_GOOD", "USED_EXCELLENT"}) == "USED_GOOD"
    assert _kies_staat("USED_GOOD", None) == "USED_GOOD"
    assert _kies_staat("USED_GOOD", set()) == "USED_GOOD"
    assert _kies_staat("USED_GOOD", {"USED_GOOD"}) == "USED_GOOD"
    assert _kies_staat("NEW", {"NEW_OTHER", "USED_EXCELLENT"}) == "NEW_OTHER"
    assert "NEW" not in _staat_alternatieven("USED_GOOD")
    assert _staat_alternatieven("NEW") == []
