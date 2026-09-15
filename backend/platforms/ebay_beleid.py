"""
eBay: verzending, retour en betaling via verkopersbeleid.

WAAROM DIT ER IS (15-09-2026, gemeten op ebay.nl)

Elke eBay-advertentie die Omnivaleur plaatste stond op "Alleen ophalen". Op de
openbare pagina van ebay.nl/itm/168685598778 stond letterlijk "Ophalen: Alleen
ophalen bij Drimmelen, Nederland", en GetItem gaf ShipToLocations 'None'. Een
koper buiten ophaalafstand kon dus niets bestellen.

De oorzaak: de Inventory API heeft geen velden voor verzendkosten. Verzending,
retour en betaling gaan uitsluitend via verkopersbeleid (business policies), en
dat werkt pas als de verkoper is aangemeld voor het programma
SELLING_POLICY_MANAGEMENT. Zonder die aanmelding antwoordt eBay op elke
beleidsvraag met 20403 "User is not eligible for Business Policy" (gemeten bij
dealbeter), en valt een plaatsing terug op alleen ophalen.

Wat hier gebeurt: de verkoper vult in het dashboard één keer zijn verzendkosten
in. Wij melden hem aan, maken drie beleidsregels onder de naam "Omnivaleur" en
hangen die aan elke advertentie. De aanmelding kan bij eBay tot 24 uur duren;
tot die tijd blijven de instellingen bewaard en wordt het bij de volgende
poging vanzelf opnieuw geprobeerd.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

ACCOUNT_API = ("https://api.sandbox.ebay.com/sell/account/v1" if settings.ebay_sandbox
               else "https://api.ebay.com/sell/account/v1")

PROGRAMMA = "SELLING_POLICY_MANAGEMENT"
BELEIDSNAAM = "Omnivaleur"
_CATEGORIE = [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}]

# Binnenlandse standaardverzending per marktplaats. Gemeten met GeteBayDetails
# op site 146 (ebay.nl): NL_StandardDelivery heet daar "Standaardverzending".
_VERZENDDIENST = {"EBAY_NL": "NL_StandardDelivery"}

# eBay kent voor verzendtijd alleen deze waarden.
TOEGESTANE_VERZENDDAGEN = (1, 2, 3, 4, 5, 10, 15, 20, 30)
TOEGESTANE_RETOURDAGEN = (14, 30, 60)

# Verkoopfouten die betekenen dat onze bewaarde beleidsnummers niet meer kloppen
# (de verkoper heeft ze bij eBay weggehaald of veranderd).
BELEID_ONGELDIG = {25007, 25008, 25009, 25035, 25036}


class EbayVerzendingNietKlaar(RuntimeError):
    """Plaatsen kan nog niet: verzending is niet ingesteld of eBay is nog bezig."""


def controleer_instellingen(body: dict) -> dict:
    """Wat de verkoper invult, gecontroleerd voordat het naar eBay gaat."""
    try:
        kosten = round(float(str(body.get("kosten", "")).replace(",", ".")), 2)
    except (TypeError, ValueError):
        raise ValueError("Enter your shipping cost in euros (0 for free shipping).")
    if kosten < 0 or kosten > 500:
        raise ValueError("Shipping cost must be between €0 and €500.")
    try:
        dagen = int(body.get("verzenddagen") or 3)
        retour = int(body.get("retourdagen") or 30)
    except (TypeError, ValueError):
        raise ValueError("Dispatch time and return period must be whole days.")
    if dagen not in TOEGESTANE_VERZENDDAGEN:
        raise ValueError(f"eBay only allows a dispatch time of {', '.join(map(str, TOEGESTANE_VERZENDDAGEN))} days.")
    if retour not in TOEGESTANE_RETOURDAGEN:
        raise ValueError("Return period must be 14, 30 or 60 days.")
    return {
        "kosten": kosten,
        "verzenddagen": dagen,
        "retourdagen": retour,
        "ophalen": bool(body.get("ophalen")),
    }


def _verzend_beleid(inst: dict, marktplaats: str) -> dict:
    kosten = float(inst["kosten"])
    return {
        "name": BELEIDSNAAM,
        "marketplaceId": marktplaats,
        "categoryTypes": _CATEGORIE,
        "handlingTime": {"unit": "DAY", "value": int(inst["verzenddagen"])},
        "localPickup": bool(inst.get("ophalen")),
        "shippingOptions": [{
            "optionType": "DOMESTIC",
            "costType": "FLAT_RATE",
            "shippingServices": [{
                "sortOrder": 1,
                "shippingServiceCode": _VERZENDDIENST.get(marktplaats, "NL_StandardDelivery"),
                "shippingCost": {"value": f"{kosten:.2f}", "currency": "EUR"},
                "freeShipping": kosten == 0,
            }],
        }],
    }


def _betaal_beleid(marktplaats: str) -> dict:
    return {"name": BELEIDSNAAM, "marketplaceId": marktplaats,
            "categoryTypes": _CATEGORIE, "immediatePay": True}


def _retour_beleid(inst: dict, marktplaats: str) -> dict:
    return {
        "name": BELEIDSNAAM,
        "marketplaceId": marktplaats,
        "categoryTypes": _CATEGORIE,
        "returnsAccepted": True,
        "returnPeriod": {"unit": "DAY", "value": int(inst["retourdagen"])},
        "returnShippingCostPayer": "BUYER",
    }


# soort → (pad om aan te maken, pad om bij te werken, naam van het nummer)
_SOORTEN = {
    "fulfillment": ("/fulfillment_policy/", "/fulfillment_policy/{id}", "fulfillmentPolicyId"),
    "payment": ("/payment_policy", "/payment_policy/{id}", "paymentPolicyId"),
    "return": ("/return_policy", "/return_policy/{id}", "returnPolicyId"),
}


def _fout_ids(resp: httpx.Response) -> set[int]:
    try:
        return {int(e.get("errorId")) for e in (resp.json().get("errors") or []) if e.get("errorId")}
    except Exception:  # noqa: BLE001
        return set()


def _fouttekst(resp: httpx.Response) -> str:
    try:
        fouten = resp.json().get("errors") or []
        if fouten:
            return "; ".join(e.get("longMessage") or e.get("message") or "" for e in fouten)
    except Exception:  # noqa: BLE001
        pass
    return resp.text[:300]


async def aangemeld(client: httpx.AsyncClient, headers: dict) -> bool:
    resp = await client.get(f"{ACCOUNT_API}/program/get_opted_in_programs", headers=headers)
    if not resp.is_success:
        return False
    return any(p.get("programType") == PROGRAMMA for p in (resp.json().get("programs") or []))


async def meld_aan(client: httpx.AsyncClient, headers: dict) -> None:
    resp = await client.post(f"{ACCOUNT_API}/program/opt_in",
                             json={"programType": PROGRAMMA}, headers=headers)
    # 25803 = "already exists": al aangemeld, of de aanmelding loopt al.
    if resp.is_success or 25803 in _fout_ids(resp):
        return
    raise RuntimeError(f"eBay did not accept the sign-up for seller policies: {_fouttekst(resp)}")


async def _zet_beleid(client: httpx.AsyncClient, headers: dict, soort: str,
                      lading: dict, marktplaats: str) -> str | None:
    """Maak het beleid aan, of werk het bij als het er al is. Geeft het nummer
    terug, of None als eBay de verkoper (nog) niet toelaat tot verkopersbeleid."""
    maak, werk_bij, veld = _SOORTEN[soort]
    zoek = await client.get(f"{ACCOUNT_API}/{soort}_policy/get_by_policy_name",
                            params={"marketplace_id": marktplaats, "name": BELEIDSNAAM},
                            headers=headers)
    if 20403 in _fout_ids(zoek):
        return None
    if zoek.is_success and zoek.json().get(veld):
        nummer = zoek.json()[veld]
        resp = await client.put(f"{ACCOUNT_API}{werk_bij.format(id=nummer)}",
                                json=lading, headers=headers)
    else:
        resp = await client.post(f"{ACCOUNT_API}{maak}", json=lading, headers=headers)
    if 20403 in _fout_ids(resp):
        return None
    if not resp.is_success:
        raise RuntimeError(f"eBay rejected the {soort} policy: {_fouttekst(resp)}")
    return str(resp.json().get(veld) or "") or None


async def richt_in(headers: dict, inst: dict,
                   marktplaats: str | None = None) -> dict:
    """Meld aan en zet de drie beleidsregels klaar.

    Geeft {"status": "klaar", "beleid": {...}} of {"status": "wacht_op_ebay"}.
    """
    marktplaats = marktplaats or settings.ebay_marketplace_id
    async with httpx.AsyncClient(timeout=30.0) as client:
        if not await aangemeld(client, headers):
            await meld_aan(client, headers)
        nummers = {}
        for soort, lading in (("fulfillment", _verzend_beleid(inst, marktplaats)),
                              ("payment", _betaal_beleid(marktplaats)),
                              ("return", _retour_beleid(inst, marktplaats))):
            nummer = await _zet_beleid(client, headers, soort, lading, marktplaats)
            if not nummer:
                return {"status": "wacht_op_ebay"}
            nummers[soort] = nummer
    return {"status": "klaar", "beleid": nummers}


def als_listing_policies(beleid: dict) -> dict:
    return {
        "fulfillmentPolicyId": beleid["fulfillment"],
        "paymentPolicyId": beleid["payment"],
        "returnPolicyId": beleid["return"],
    }


def bewaar_extra(user_id: str, wijzigingen: dict) -> dict:
    """Voeg velden toe aan extra_data zonder de rest (zoals ship_from) te wissen.
    Een waarde None haalt het veld weg."""
    from backend.database import get_db
    db = get_db()
    rij = (db.table("platform_credentials").select("extra_data")
           .eq("user_id", user_id).eq("platform", "ebay").limit(1).execute()).data
    extra = dict(((rij or [{}])[0].get("extra_data")) or {})
    for sleutel, waarde in wijzigingen.items():
        if waarde is None:
            extra.pop(sleutel, None)
        else:
            extra[sleutel] = waarde
    (db.table("platform_credentials").update({"extra_data": extra})
     .eq("user_id", user_id).eq("platform", "ebay").execute())
    return extra


async def beleid_voor_plaatsing(headers: dict, credentials: dict) -> dict:
    """De beleidsnummers voor een nieuwe advertentie, of een duidelijke fout.

    Staat de aanmelding bij eBay nog in behandeling, dan wordt het hier opnieuw
    geprobeerd: zo gaat plaatsen vanzelf werken zodra eBay klaar is, zonder dat
    de verkoper het formulier nog eens hoeft op te slaan."""
    extra = credentials.get("extra_data") or {}
    beleid = extra.get("ebay_beleid") or {}
    if all(beleid.get(s) for s in _SOORTEN):
        return als_listing_policies(beleid)
    inst = extra.get("verzending")
    if not inst:
        raise EbayVerzendingNietKlaar(
            "Set your eBay shipping costs first: open Platforms, and fill in "
            "'Shipping & returns' under eBay. Without it eBay lists your item as "
            "pickup only, so nobody can order it with delivery.")
    uitkomst = await richt_in(headers, inst)
    if uitkomst["status"] != "klaar":
        raise EbayVerzendingNietKlaar(
            "eBay is still switching on your shipping settings. This can take up "
            "to 24 hours after you saved them; publishing to eBay works as soon "
            "as eBay is done. Try again later.")
    if credentials.get("user_id"):
        await asyncio.to_thread(bewaar_extra, credentials["user_id"],
                                {"ebay_beleid": uitkomst["beleid"]})
    return als_listing_policies(uitkomst["beleid"])


async def lees_account(headers: dict) -> dict:
    """Registratie en verkooplimiet, rechtstreeks van eBay. Nooit een fout."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{ACCOUNT_API}/privilege", headers=headers)
        if not resp.is_success:
            return {"registratie_klaar": None, "limiet": None}
        j = resp.json()
        limiet = j.get("sellingLimit") or {}
        return {
            "registratie_klaar": j.get("sellerRegistrationCompleted"),
            "limiet": {
                "aantal": limiet.get("quantity"),
                "bedrag": (limiet.get("amount") or {}).get("value"),
            } if limiet else None,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("eBay-account niet uit te lezen: %s", e)
        return {"registratie_klaar": None, "limiet": None}


# Velden die PUT /offer/{id} accepteert (EbayOfferDetailsWithId in eBay's spec).
_OFFER_VELDEN = (
    "availableQuantity", "categoryId", "charity", "extendedProducerResponsibility",
    "hideBuyerDetails", "includeCatalogProductDetails", "listingDescription",
    "listingDuration", "listingPolicies", "listingStartDate", "lotSize",
    "merchantLocationKey", "pricingSummary", "quantityLimitPerBuyer", "regulatory",
    "secondaryCategoryId", "storeCategoryNames", "tax",
)


def offer_voor_put(offer: dict) -> dict:
    return {k: v for k, v in offer.items() if k in _OFFER_VELDEN}


async def hang_beleid_aan_live_advertenties(platform, user_id: str) -> dict:
    """Advertenties die al op eBay staan (op alleen ophalen) krijgen alsnog
    verzending. PUT op een gepubliceerde offer past de live advertentie aan."""
    from backend.database import get_db
    db = get_db()
    creds = (db.table("platform_credentials").select("*")
             .eq("user_id", user_id).eq("platform", "ebay").limit(1).execute()).data
    if not creds:
        return {"bijgewerkt": 0, "mislukt": 0}
    credentials = await platform._ensure_fresh_token(creds[0])
    beleid = (credentials.get("extra_data") or {}).get("ebay_beleid") or {}
    if not all(beleid.get(s) for s in _SOORTEN):
        return {"bijgewerkt": 0, "mislukt": 0}
    gewenst = als_listing_policies(beleid)
    item_ids = [r["id"] for r in (db.table("items").select("id")
                .eq("user_id", user_id).limit(20000).execute()).data or []]
    offers: list[str] = []
    for i in range(0, len(item_ids), 100):
        for r in (db.table("listings").select("platform_offer_id")
                  .in_("item_id", item_ids[i:i + 100]).eq("platform", "ebay")
                  .in_("status", ["active", "sold_unconfirmed"]).execute()).data or []:
            if r.get("platform_offer_id"):
                offers.append(r["platform_offer_id"])
    bijgewerkt = mislukt = 0
    from backend.platforms.ebay import INVENTORY_API
    headers = platform._auth_headers(credentials, write=True)
    async with httpx.AsyncClient(timeout=30.0) as client:
        for offer_id in offers:
            try:
                resp = await client.get(f"{INVENTORY_API}/offer/{offer_id}", headers=headers)
                if not resp.is_success:
                    mislukt += 1
                    continue
                offer = resp.json()
                huidig = offer.get("listingPolicies") or {}
                if all(huidig.get(k) == v for k, v in gewenst.items()):
                    continue
                lading = offer_voor_put(offer)
                lading["listingPolicies"] = {**huidig, **gewenst}
                put = await client.put(f"{INVENTORY_API}/offer/{offer_id}",
                                       json=lading, headers=headers)
                if put.is_success:
                    bijgewerkt += 1
                else:
                    mislukt += 1
                    logger.warning("eBay-offer %s kreeg geen verzending: %s",
                                   offer_id, _fouttekst(put))
            except Exception as e:  # noqa: BLE001
                mislukt += 1
                logger.warning("eBay-offer %s bijwerken mislukt: %s", offer_id, e)
    logger.info("eBay-verzending aan live advertenties gehangen voor %s: %d bijgewerkt, %d mislukt",
                user_id, bijgewerkt, mislukt)
    return {"bijgewerkt": bijgewerkt, "mislukt": mislukt}
