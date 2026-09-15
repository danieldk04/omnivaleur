"""De hele eBay-lus: plaatsen, een verkoop op eBay zien, en weghalen na een
verkoop elders.

WAAROM DIT ER IS (15-09-2026, gemeten op de echte eBay-koppeling van dealbeter)

1. Een verkoop op eBay werd nooit gezien. De controle wachtte op offer-status
   "ENDED" of "SOLD", maar eBay's specificatie kent voor dat veld alleen
   PUBLISHED en UNPUBLISHED. De verkoop staat in listing.soldQuantity.
2. Elke advertentie stond op "Alleen ophalen": zonder verkopersbeleid stuurt de
   Inventory API geen verzending mee.
3. Een tweede poging voor hetzelfde artikel liep altijd vast op "Offer entity
   already exists", want een offer blijft bestaan na een mislukte publicatie of
   na weghalen.
4. Na een verkoop elders werd een eBay-rij zonder offer-nummer met het openbare
   nummer weggehaald, en daar antwoordt eBay altijd 404 op.

De nep-eBay hieronder geeft de antwoorden die op 15-09-2026 echt zijn gemeten
(vormen van GET /offer, foutcode 25002 bij een dubbele offer, 20403 bij een
verkoper zonder verkopersbeleid). Deze tests draaien alleen de echte code.
"""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.platforms import ebay as E  # noqa: E402
from backend.services import polling as P  # noqa: E402
from backend.services import crosslist as C  # noqa: E402

TOEKOMST = "2099-01-01T00:00:00+00:00"
BELEID = {"fulfillment": "F1", "payment": "B1", "return": "R1"}


def _levende_offer(offer_id="264930679011", sku="IMP-F7B16F13", listing_id="168685598778"):
    """Letterlijk de vorm van GET /offer/264930679011 op 15-09-2026."""
    return {
        "offerId": offer_id, "sku": sku, "marketplaceId": "EBAY_NL",
        "format": "FIXED_PRICE", "quantityLimitPerBuyer": 1,
        "pricingSummary": {"price": {"value": "275.0", "currency": "EUR"}},
        "listingPolicies": {"eBayPlusIfEligible": False},
        "categoryId": "42146", "merchantLocationKey": "OMNIVALEUR_MAIN",
        "tax": {"applyTax": False},
        "listing": {"listingId": listing_id, "listingStatus": "ACTIVE", "soldQuantity": 0},
        "status": "PUBLISHED", "listingDuration": "GTC",
        "includeCatalogProductDetails": True, "hideBuyerDetails": False,
    }


class NepEbay:
    def __init__(self):
        self.offers: dict[str, dict] = {}
        self.aanroepen: list[tuple[str, str, dict | None]] = []
        self.aangemeld = False
        self.beleid_toegestaan = True
        self.beleid: dict[str, dict] = {}
        self.volgnummer = 500

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        pad, q = url.path, parse_qs(url.query)
        body = json.loads(request.content) if request.content else None
        self.aanroepen.append((request.method, pad, body))
        inv = "/sell/inventory/v1"
        acc = "/sell/account/v1"
        m = request.method

        if pad == f"{inv}/location/OMNIVALEUR_MAIN" and m == "GET":
            return httpx.Response(200, json={"merchantLocationKey": "OMNIVALEUR_MAIN"})
        if pad.startswith(f"{inv}/inventory_item/") and m == "PUT":
            return httpx.Response(204)
        if pad == f"{inv}/offer" and m == "POST":
            if any(o["sku"] == body["sku"] for o in self.offers.values()):
                return httpx.Response(400, json={"errors": [{
                    "errorId": 25002, "domain": "API_INVENTORY", "category": "REQUEST",
                    "message": "A user error has occurred. Offer entity already exists."}]})
            self.volgnummer += 1
            oid = f"OFF{self.volgnummer}"
            self.offers[oid] = {**body, "offerId": oid, "status": "UNPUBLISHED"}
            return httpx.Response(201, json={"offerId": oid})
        if pad == f"{inv}/offer" and m == "GET":
            sku = q.get("sku", [""])[0]
            gevonden = [o for o in self.offers.values() if o["sku"] == sku]
            return httpx.Response(200, json={"total": len(gevonden), "offers": gevonden})
        if pad.startswith(f"{inv}/offer/"):
            deel = pad[len(f"{inv}/offer/"):].split("/")
            oid, actie = deel[0], (deel[1] if len(deel) > 1 else None)
            if oid not in self.offers:
                return httpx.Response(404, json={"errors": [{"errorId": 25713}]})
            offer = self.offers[oid]
            if actie is None and m == "GET":
                return httpx.Response(200, json=offer)
            if actie is None and m == "PUT":
                offer.update(body)
                return httpx.Response(204)
            if actie == "publish":
                self.volgnummer += 1
                lid = f"LIST{self.volgnummer}"
                offer["status"] = "PUBLISHED"
                offer["listing"] = {"listingId": lid, "listingStatus": "ACTIVE", "soldQuantity": 0}
                return httpx.Response(200, json={"listingId": lid})
            if actie == "withdraw":
                offer["status"] = "UNPUBLISHED"
                offer.pop("listing", None)
                return httpx.Response(200, json={"offerId": oid})
            if m == "DELETE":
                return httpx.Response(404)

        if pad == f"{acc}/program/get_opted_in_programs":
            progs = [{"programType": "SELLING_POLICY_MANAGEMENT"}] if self.aangemeld else []
            return httpx.Response(200, json={"programs": progs})
        if pad == f"{acc}/program/opt_in":
            return httpx.Response(200, json={})
        if pad.startswith(acc) and "_policy" in pad:
            if not self.beleid_toegestaan:
                return httpx.Response(400, json={"errors": [{
                    "errorId": 20403, "message": "Invalid .",
                    "longMessage": "User is not eligible for Business Policy."}]})
            soort = pad.split("/")[4].split("_")[0]
            veld = {"fulfillment": "fulfillmentPolicyId", "payment": "paymentPolicyId",
                    "return": "returnPolicyId"}[soort]
            if pad.endswith("get_by_policy_name"):
                if soort in self.beleid:
                    return httpx.Response(200, json=self.beleid[soort])
                return httpx.Response(404, json={"errors": [{"errorId": 20404}]})
            if m == "PUT":
                # Gemeten 15-09-2026: zonder het volledige beleid weigert eBay.
                if soort == "fulfillment" and "globalShipping" not in body:
                    return httpx.Response(400, json={"errors": [{"errorId": 20403,
                        "longMessage": "Global shipping field is null"}]})
                self.beleid[soort].update(body)
                return httpx.Response(200, json=self.beleid[soort])
            self.beleid[soort] = {**body, veld: f"{veld[:3]}-1", "globalShipping": False}
            return httpx.Response(201, json={veld: f"{veld[:3]}-1"})
        return httpx.Response(500, json={"onverwacht": f"{m} {pad}"})


@pytest.fixture
def ebay(monkeypatch):
    nep = NepEbay()
    echte_client = httpx.AsyncClient

    def client(*a, **k):
        k.pop("transport", None)
        return echte_client(*a, transport=httpx.MockTransport(nep.handler), **k)

    monkeypatch.setattr(httpx, "AsyncClient", client)

    async def geen_kenmerken(_categorie):
        return []
    monkeypatch.setattr(E, "_get_required_aspects", geen_kenmerken)
    return nep


def _item(**extra):
    item = {"id": "item-1", "sku": "IMP-1", "title": "Authentic olive green lederhosen",
            "price": 55.0, "condition": "good", "ebay_category_id": "15687",
            "photo_urls": ["https://img.omnivaleur.com/a.jpg"], "description": "Leather."}
    item.update(extra)
    return item


def _creds(**extra_data):
    return {"access_token": "t", "refresh_token": "r", "token_expires_at": TOEKOMST,
            "extra_data": extra_data}


# ── 1. Een verkoop op eBay wordt gezien en meldt elders af ──────────────────

def test_levende_advertentie_telt_als_actief(ebay):
    ebay.offers["264930679011"] = _levende_offer()
    status = asyncio.run(E.EbayPlatform().get_listing_status("264930679011", _creds()))
    assert status == "active"


@pytest.mark.parametrize("listing_status", ["ENDED", "OUT_OF_STOCK"])
def test_verkochte_advertentie_telt_als_verkocht(ebay, listing_status):
    """Offer-status blijft PUBLISHED; alleen soldQuantity verraadt de verkoop."""
    offer = _levende_offer()
    offer["listing"].update({"listingStatus": listing_status, "soldQuantity": 1})
    ebay.offers["264930679011"] = offer
    status = asyncio.run(E.EbayPlatform().get_listing_status("264930679011", _creds()))
    assert status == "sold", f"een eBay-verkoop werd gelezen als '{status}'"


def test_door_ebay_beeindigd_met_blokkade_telt_niet_als_actief(ebay):
    """Echte vorm van 15-09-2026 (offer 215295556011): eBay beëindigde de
    advertentie en zette listingOnHold erbij. Die is weg, niet actief."""
    ebay.offers["264930679011"] = {
        "offerId": "264930679011", "status": "UNPUBLISHED",
        "listing": {"listingId": "178340224235", "listingStatus": "ENDED",
                    "soldQuantity": 0, "listingOnHold": True},
    }
    status = asyncio.run(E.EbayPlatform().get_listing_status("264930679011", _creds()))
    assert status == "not_found", f"een beëindigde eBay-advertentie bleef '{status}'"


def test_zelf_beeindigd_zonder_verkoop_is_niet_verkocht(ebay):
    offer = _levende_offer()
    offer["status"] = "UNPUBLISHED"
    offer.pop("listing")
    ebay.offers["264930679011"] = offer
    status = asyncio.run(E.EbayPlatform().get_listing_status("264930679011", _creds()))
    assert status == "not_found"


class _NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam, self.velden = db, naam, None

    def select(self, *_a, **_k): return self
    def update(self, velden): self.velden = velden; return self
    def eq(self, *_a, **_k): return self
    def in_(self, *_a, **_k): return self
    def limit(self, *_a): return self

    def execute(self):
        if self.velden is not None:
            self.db.updates.append((self.naam, self.velden))
            return type("R", (), {"data": []})()
        return type("R", (), {"data": self.db.rijen.get(self.naam, [])})()


class _NepDb:
    def __init__(self, rijen=None):
        self.rijen = rijen or {}
        self.updates = []

    def table(self, naam):
        return _NepTabel(self, naam)


def test_controleronde_meldt_ebay_verkoop_overal_af(ebay, monkeypatch):
    """Van begin tot eind door de echte verkoopcontrole."""
    offer = _levende_offer()
    offer["listing"].update({"listingStatus": "ENDED", "soldQuantity": 1})
    ebay.offers["264930679011"] = offer
    afgemeld = []

    async def handle_item_sold(item_id, platform, **_k):
        afgemeld.append((item_id, platform))

    db = _NepDb()
    monkeypatch.setattr(P, "get_db", lambda: db)
    monkeypatch.setattr(P, "handle_item_sold", handle_item_sold)
    rij = {"id": "rij-1", "item_id": "item-1", "platform": "ebay",
           "platform_listing_id": "168685598778", "platform_offer_id": "264930679011",
           "status": "active", "not_found_count": 0}
    asyncio.run(P._check_one(rij, _creds()))
    assert afgemeld == [("item-1", "ebay")], "de eBay-verkoop is niet elders afgemeld"


# ── 2. Geen advertentie op "alleen ophalen" ──────────────────────────────────

def test_zonder_verzendinstellingen_wordt_er_niets_geplaatst(ebay):
    from backend.platforms.ebay_beleid import EbayVerzendingNietKlaar
    with pytest.raises(EbayVerzendingNietKlaar):
        asyncio.run(E.EbayPlatform().create_listing(_item(), _creds()))
    geplaatst = [a for a in ebay.aanroepen if a[0] in ("PUT", "POST") and "/inventory/" in a[1]]
    assert geplaatst == [], f"toch naar eBay gestuurd zonder verzending: {geplaatst}"


def test_advertentie_krijgt_verzendbeleid_mee(ebay):
    uit = asyncio.run(E.EbayPlatform().create_listing(_item(), _creds(ebay_beleid=BELEID)))
    offer = ebay.offers[uit["platform_offer_id"]]
    assert offer["listingPolicies"] == {"fulfillmentPolicyId": "F1", "paymentPolicyId": "B1",
                                        "returnPolicyId": "R1"}
    assert offer["status"] == "PUBLISHED"


# ── 3. Een tweede poging loopt niet meer vast ────────────────────────────────

def test_tweede_poging_hergebruikt_de_bestaande_offer(ebay):
    """Gemeten bij dealbeter: RYOBI-set, offer 264926465011 UNPUBLISHED sinds 13-09."""
    ebay.offers["264926465011"] = {"offerId": "264926465011", "sku": "IMP-1",
                                   "marketplaceId": "EBAY_NL", "status": "UNPUBLISHED",
                                   "pricingSummary": {"price": {"value": "229.0", "currency": "EUR"}}}
    uit = asyncio.run(E.EbayPlatform().create_listing(_item(price=60.0), _creds(ebay_beleid=BELEID)))
    assert uit["platform_offer_id"] == "264926465011"
    offer = ebay.offers["264926465011"]
    assert offer["status"] == "PUBLISHED"
    assert offer["pricingSummary"]["price"]["value"] == "60.0", "nieuwe prijs niet doorgezet"
    assert "sku" not in (next(b for m, p, b in ebay.aanroepen
                              if m == "PUT" and p.endswith("/offer/264926465011")) or {})


def test_al_live_na_afgebroken_verzoek_wordt_niet_dubbel_geplaatst(ebay):
    ebay.offers["264930679011"] = _levende_offer(sku="IMP-1")
    uit = asyncio.run(E.EbayPlatform().create_listing(_item(), _creds(ebay_beleid=BELEID)))
    assert uit["platform_listing_id"] == "168685598778"
    assert not [a for a in ebay.aanroepen if a[1].endswith("/publish")], "dubbel gepubliceerd"


# ── 4. Verkocht elders: eBay-advertentie gaat echt weg ───────────────────────

def test_verkocht_elders_haalt_ebay_rij_zonder_offer_nummer_weg(ebay, monkeypatch):
    ebay.offers["264930679011"] = _levende_offer(sku="IMP-1")
    db = _NepDb({
        "items": [{"id": "item-1", "user_id": "u1", "sku": "IMP-1"}],
        "platform_credentials": [_creds()],
    })
    monkeypatch.setattr(C, "get_db", lambda: db)
    monkeypatch.setattr(C, "_log_event", lambda *a, **k: None)
    rij = {"id": "l1", "item_id": "item-1", "platform": "ebay",
           "platform_listing_id": "168685598778", "platform_offer_id": None}
    asyncio.run(C._delist_one(rij))
    assert ("POST", "/sell/inventory/v1/offer/264930679011/withdraw", None) in ebay.aanroepen
    assert ("listings", {"status": "delisted"}) in db.updates
    assert ebay.offers["264930679011"]["status"] == "UNPUBLISHED"


# ── 5. Verzendinstellingen bij eBay klaarzetten ──────────────────────────────

def test_verkoper_zonder_verkopersbeleid_wordt_aangemeld_en_wacht(ebay):
    from backend.platforms import ebay_beleid as B
    ebay.beleid_toegestaan = False
    inst = B.controleer_instellingen({"kosten": "6,95", "verzenddagen": 3, "retourdagen": 30})
    uit = asyncio.run(B.richt_in({"Authorization": "Bearer t"}, inst, "EBAY_NL"))
    assert uit == {"status": "wacht_op_ebay"}
    assert ("POST", "/sell/account/v1/program/opt_in",
            {"programType": "SELLING_POLICY_MANAGEMENT"}) in ebay.aanroepen


def test_aangemelde_verkoper_krijgt_drie_beleidsregels(ebay):
    from backend.platforms import ebay_beleid as B
    ebay.aangemeld = True
    inst = B.controleer_instellingen({"kosten": 6.95, "verzenddagen": 2, "retourdagen": 14,
                                      "ophalen": True})
    uit = asyncio.run(B.richt_in({"Authorization": "Bearer t"}, inst, "EBAY_NL"))
    assert uit["status"] == "klaar"
    assert set(uit["beleid"]) == {"fulfillment", "payment", "return"}
    verzend = next(b for m, p, b in ebay.aanroepen if m == "POST" and "fulfillment_policy" in p)
    dienst, ophalen = verzend["shippingOptions"][0]["shippingServices"]
    assert dienst["shippingCost"] == {"value": "6.95", "currency": "EUR"}
    assert dienst["shippingServiceCode"] == "NL_StandardDelivery"
    assert verzend["handlingTime"] == {"unit": "DAY", "value": 2}
    # localPickup true weigert ebay.nl; ophalen is daar een eigen dienst.
    assert verzend["localPickup"] is False
    assert ophalen["shippingServiceCode"] == "NL_PickUp"
    assert not [a for a in ebay.aanroepen if a[1].endswith("/opt_in")], "onnodig opnieuw aangemeld"


def test_ongeldige_instellingen_worden_geweigerd():
    from backend.platforms import ebay_beleid as B
    for fout in ({"kosten": ""}, {"kosten": -1}, {"kosten": 5, "verzenddagen": 7},
                 {"kosten": 5, "retourdagen": 21}):
        with pytest.raises(ValueError):
            B.controleer_instellingen(fout)


def test_slottekst_gaat_niet_mee_naar_ebay():
    slot = "#DeJuisteToon\n\nKijk op onze webshop Dejuistetoon.\ntelefoon: +31 6 5396 0664."
    tekst = "Mooie lederhose, maat 52.\n\n" + slot
    uit = C._zonder_links(C._zonder_slot(tekst, slot))
    assert "0664" not in uit and "webshop" not in uit
    assert uit == "Mooie lederhose, maat 52."


# ── 6. Geen verzonnen kenmerken ──────────────────────────────────────────────

def test_ontbrekende_kenmerken_worden_niet_verzonnen():
    """Gemeten 15-09-2026: bodywarmer kreeg Type Blazer, Stijl 3-in-1, Acetaat."""
    item = {"title": "Grey Suitsupply bodywarmer men size M", "brand": "Suitsupply",
            "size": "M", "gender": "heren"}
    aspects = {"Brand": ["Suitsupply"], "Size": ["M"]}
    E._fill_required_aspects(aspects, item, [
        {"name": "Type", "values": ["Blazer", "Bodywarmers", "Jas"], "vrij": True},
        {"name": "Stijl", "values": ["3-in-1", "Bomber"], "vrij": True},
        {"name": "Buitenmateriaal", "values": ["Acetaat", "Katoen"], "vrij": True},
        {"name": "Patroon", "values": ["Effen", "Overige"], "vrij": False},
        {"name": "Pasvorm", "values": ["Normaal", "Slim"], "vrij": False},
    ])
    assert aspects["Type"] == ["Bodywarmers"], "het woord uit de titel hoort te winnen"
    assert aspects["Stijl"] == ["Onbekend"]
    assert aspects["Buitenmateriaal"] == ["Onbekend"]
    assert aspects["Patroon"] == ["Overige"], "neutrale waarde uit eBay's eigen lijst"
    assert aspects["Pasvorm"] == ["Normaal"], "alleen vaste waarden: dan toch de eerste"


# ── 7. eBay's echte reden komt bij de verkoper ───────────────────────────────

def test_verstopte_uitleg_van_ebay_komt_in_de_foutmelding():
    """Letterlijk het antwoord op de publicatie van 15-09-2026 (eigenaarsaccount)."""
    tekst = ("Het lijkt erop dat je niet de vereiste informatie hebt verstrekt om je "
             "identiteit of financi&euml;le gegevens te bevestigen.")
    resp = httpx.Response(400, json={"errors": [{
        "errorId": 25019, "message": "Cannot revise listing. Object kan niet worden aangeboden "
        "of gewijzigd. De titel en/of beschrijving bevat wellicht ongepaste taal.",
        "parameters": [
            {"name": "0", "value": tekst + "<font color=#757575 size=1>{e299627-1212400x}</font>"},
            {"name": "2", "value": "TRISK_pmts2_Issue_617_Block_BuyingandSellingandm2m"},
        ]}]})
    with pytest.raises(RuntimeError) as fout:
        E._raise_with_ebay_error(resp, "publishing offer")
    assert "identiteit of financiële gegevens te bevestigen" in str(fout.value)
    assert "e299627" not in str(fout.value) and "TRISK" not in str(fout.value)


def test_verificatie_van_ebay_staat_in_de_accountcontrole(monkeypatch):
    from backend.platforms import ebay_beleid as B

    def handler(request):
        if request.url.path.endswith("/privilege"):
            return httpx.Response(200, json={"sellingLimit": {"quantity": 75000},
                                             "sellerRegistrationCompleted": True})
        if request.url.path.endswith("/kyc"):
            return httpx.Response(200, json={"kycChecks": [{
                "remedyUrl": "https://www.ebay.nl/sellerhub", "alert": "Accountgegevens bijwerken",
                "detailMessage": "We konden sommige van de verstrekte gegevens niet verifiëren."}]})
        return httpx.Response(500)

    echte_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda *a, **k: echte_client(*a, transport=httpx.MockTransport(handler),
                                                     **{x: y for x, y in k.items() if x != "transport"}))
    uit = asyncio.run(B.lees_account({"Authorization": "Bearer t"}))
    assert uit["registratie_klaar"] is True
    assert uit["verificatie"][0]["melding"] == "Accountgegevens bijwerken"


def test_verzendkosten_wijzigen_blijft_werken(ebay):
    """Tweede keer opslaan: bijwerken met het volledige beleid, niet 'wacht op eBay'."""
    from backend.platforms import ebay_beleid as B
    ebay.aangemeld = True
    h = {"Authorization": "Bearer t"}
    eerst = asyncio.run(B.richt_in(h, B.controleer_instellingen({"kosten": 6.95}), "EBAY_NL"))
    daarna = asyncio.run(B.richt_in(h, B.controleer_instellingen({"kosten": 7.50}), "EBAY_NL"))
    assert daarna == eerst and daarna["status"] == "klaar"
    dienst = ebay.beleid["fulfillment"]["shippingOptions"][0]["shippingServices"][0]
    assert dienst["shippingCost"]["value"] == "7.50"
    ongewijzigd = [a for a in ebay.aanroepen if a[0] == "PUT" and "payment_policy" in a[1]]
    assert ongewijzigd == [], "ongewijzigd beleid hoort niet opnieuw verstuurd te worden"


# ── 6. ebay.nl: Nederlandse tekst en een vaste rubriek ──────────────────────

def test_ebay_krijgt_de_nederlandse_tekst_zonder_vertaling(monkeypatch):
    """ebay.nl, verzending alleen binnen Nederland: de koper is Nederlands."""
    async def nooit(*a, **k):
        raise AssertionError("een al-Nederlandse tekst ging toch naar de vertaler")
    monkeypatch.setattr(C, "_translate_with_claude", nooit)
    item = {"title": "Handgeknoopt Perzisch Shiraz wollen tapijt 135/80 cm",
            "description": "Mooi handgeknoopt wollen tapijt uit Iran, in goede staat. "
                           "Afmeting 135 bij 80 centimeter, ophalen in Etten-Leur kan ook."}
    uit = asyncio.run(C.localize_item_for_platform(item, "ebay"))
    assert C.taal_van_platform("ebay") == "nl"
    assert uit["title"] == item["title"] and uit["description"] == item["description"]


def test_vaste_rubriek_wint_van_een_verkeerde_gok(ebay):
    """Gemeten 15-09-2026: eBay's zoeker gaf voor Toons schapenvacht 'Laarzen'
    (53557) en bewaarde dat op het artikel. De vaste rubriek gaat voor."""
    item = _item(category="wonen vachten", gender="wonen", ebay_category_id="53557")
    uit = asyncio.run(E.EbayPlatform().create_listing(item, _creds(ebay_beleid=BELEID)))
    assert ebay.offers[uit["platform_offer_id"]]["categoryId"] == "91421"


def test_gok_buiten_de_eigen_tak_wordt_niet_gebruikt(monkeypatch):
    """Echte volgorde voor 'Leuke net kinder lederhose': boeken en wandkleden
    eerst. Zonder kinderkleding in het lijstje liever geen rubriek dan een foute."""
    monkeypatch.setattr(E.settings, "ebay_app_id", "x")
    lijst = [{"category_id": "171228", "name": "Boeken", "voorouders": ["267", "171228"]},
             {"category_id": "38237", "name": "Wandtapijten", "voorouders": ["11700", "10033"]}]

    async def zoeker(_tekst):
        return lijst
    monkeypatch.setattr(E, "_raw_category_suggestions", zoeker)
    assert asyncio.run(E.resolve_category_id("Leuke net kinder lederhose", None,
                                             "jongens kleding", "kinderen")) is None
    lijst.append({"category_id": "15615", "name": "Shorts", "voorouders": ["11450", "171146", "147317"]})
    assert asyncio.run(E.resolve_category_id("Leuke net kinder lederhose", None,
                                             "jongens kleding", "kinderen")) == "15615"
