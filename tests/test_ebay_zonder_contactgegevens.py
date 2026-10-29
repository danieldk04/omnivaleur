"""Toon (de Juiste Toon, 96e30080), 28-10-2026: zijn Perzische tapijt (IMP-CDE9C79E) stond op
eBay onder "Schending van het beleid: Aanbieden om buiten eBay om te kopen of verkopen".

De omschrijving kwam uit zijn Marktplaats-advertentie en bevatte een telefoonnummer, zijn
webshop, Instagram en "kom langs in onze winkel". Marktplaats en 2dehands halen adressen er
al uit (_zonder_links), eBay kreeg de tekst ongewijzigd. De teksten hieronder zijn de echte
omschrijvingen uit zijn database.

Draaien:  python3.13 -m pytest tests/test_ebay_zonder_contactgegevens.py -q
"""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.platforms import ebay as ebay_mod  # noqa: E402
from tests.test_ebay_staat_per_rubriek import _FakeEbay, TOEGESTAAN_TAPIJT  # noqa: E402

PERZISCH = (
    "TL72\nPerzisch tapijt\nZijdeachtig\nRood oranje beige groen\nTweezijdig franjes\n"
    "Met metalen keurmerk\nAfmetingen\n126/94\n\nOVER DE JUISTE TOON:\nOntdek onze betoverende "
    "vintage collectie vol kleurrijke en tijdloze schatten die een tweede leven verdienen.\n\n"
    "BELANGRIJKE INFORMATIE\n• Prijzen zijn exclusief verzendkosten (binnen Nederland €7,50, "
    "Belgie 11,00 euro).\n• Artikelen kunnen in overleg geruild worden; geen geld retour.\n"
    "• De foto's in de advertentie zijn onderdeel van de productbeschrijving.\n"
    "Volg ons op Instagram, bekijk de webshop of kom langs in onze winkel in Etten-Leur, "
    "Mon Plaisir 19, Nederland\n\nWinkelbezoek elke dag mogelijk, op afspraak, neem contact op "
    "via 0031 6 53 96 06 64"
)

WANDKLEED = (
    "Tk16\nVintage Turks kleed\nIn velvet stof , hip als wandkleed of picknick kleed\n"
    "3 zijde franje\nAfmeting\n240/220\n\nDJT DeJuisteToon\nPrachtige vintage woonaccessoires.\n\n"
    "Kijk op onze webshop Dejuistetoon voor het volledige en actuele aanbod.\n\n"
    "Wil je onze collectie in het echt bekijken , maak een afspraak.\n"
    "Zie openingstijden op de website\nDeJuisteToon\n\n"
    "Alle dagen op afspraak | Do & Za 10.00 uur tot 17.00 uur\n\n"
    "Locatie: Mon Plaisir 19, Etten-Leur.\ntelefoon: +31 6 5396 0664."
)

# Schone teksten van dezelfde klant: die moeten letterlijk blijven.
SCHOON_TL72 = "Oosters floraal tapijt\n\nAfmetingen: 126/95cm\n\nTL72\n\n#Dejuistetoon 🇳🇱"
SCHOON_TL104 = ("Oosters handgeknoopt tapijt Diverse kleuren oranje, roestbruin Tweezijdig "
                "franje Afmetingen: 125/70 cm\n TL104*\n Dejuistetoon Etten-Leur 🇳🇱")


def test_perzisch_tapijt_verliest_alle_buiten_ebay_regels():
    uit = ebay_mod._zonder_contactgegevens(PERZISCH)
    for weg in ("0031", "06 64", "Instagram", "webshop", "winkel", "afspraak", "contact"):
        assert weg.lower() not in uit.lower(), (weg, uit)
    # het stuk zelf blijft
    for blijft in ("Perzisch tapijt", "Zijdeachtig", "Afmetingen\n126/94", "keurmerk",
                   "exclusief verzendkosten", "onderdeel van de productbeschrijving"):
        assert blijft in uit, (blijft, uit)


def test_wandkleed_verliest_telefoon_locatie_en_afspraak():
    uit = ebay_mod._zonder_contactgegevens(WANDKLEED)
    for weg in ("5396", "Locatie", "afspraak", "webshop", "openingstijden"):
        assert weg.lower() not in uit.lower(), (weg, uit)
    assert "240/220" in uit and "Vintage Turks kleed" in uit


def test_afmetingen_zijn_geen_telefoonnummer():
    tekst = "Perzisch tapijt 182/123 cm\nAfmetingen: 240/220 en 126/94 en 1,40 x 0,70\nArtikelnummer 0612345"
    assert ebay_mod._zonder_contactgegevens(tekst) == tekst


def test_schone_tekst_blijft_letterlijk_gelijk():
    assert ebay_mod._zonder_contactgegevens(SCHOON_TL72) == SCHOON_TL72
    assert ebay_mod._zonder_contactgegevens(SCHOON_TL104) == SCHOON_TL104
    assert ebay_mod._zonder_contactgegevens("") == ""


def test_webadres_en_mail_gaan_ook_weg():
    uit = ebay_mod._zonder_contactgegevens("Mooi dekbed in goede staat, ruim genoeg.\nMail naar info@dejuistetoon.eu of kijk op https://dejuistetoon.eu")
    assert "@" not in uit and "dejuistetoon.eu" not in uit and "Mooi dekbed" in uit


def test_bijna_niets_over_dan_blijft_de_tekst():
    tekst = "Bel 06 12345678"
    assert ebay_mod._zonder_contactgegevens(tekst) == tekst


# ---- het echte pad: wat gaat er naar eBay -------------------------------------------------

class _Opnemer(_FakeEbay):
    def __init__(self):
        super().__init__(TOEGESTAAN_TAPIJT)
        self.omschrijvingen = []

    def client(self):
        eb = self
        basis = super().client()

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def put(self, url, json=None, headers=None):
                if "inventory_item" in url:
                    eb.omschrijvingen.append(("product", json["product"]["description"]))
                return await basis.put(url, json=json, headers=headers)

            async def post(self, url, json=None, headers=None):
                if url.endswith("/offer"):
                    eb.omschrijvingen.append(("aanbieding", json["listingDescription"]))
                return await basis.post(url, json=json, headers=headers)

            async def get(self, url, **kw):
                return await basis.get(url, **kw)

        return Client()


def _plaats(monkeypatch, eb, omschrijving):
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
    monkeypatch.setattr(ebay_mod, "_toegestane_staten_cache", {}, raising=False)
    item = {"id": "i1", "sku": "IMP-CDE9C79E", "title": "Perzisch tapijt zijdeachtig rood oranje beige groen",
            "description": omschrijving, "price": 65.0, "photo_urls": ["https://x/1.jpg"],
            "condition": "good", "category": "wonen tapijten en kleden"}
    return asyncio.run(platform.create_listing(
        item, {"access_token": "t", "user_id": "u1", "token_expires_at": None}))


def test_beide_plekken_waar_eBay_de_tekst_leest_zijn_schoon(monkeypatch):
    """eBay leest de omschrijving op twee plekken: het voorraadartikel en de aanbieding.
    De aanbieding (listingDescription) is wat de koper ziet."""
    eb = _Opnemer()
    uit = _plaats(monkeypatch, eb, PERZISCH)
    assert uit["platform_listing_id"] == "L1"
    assert {plek for plek, _ in eb.omschrijvingen} == {"product", "aanbieding"}
    for plek, tekst in eb.omschrijvingen:
        assert "0031" not in tekst and "Instagram" not in tekst and "webshop" not in tekst, (plek, tekst)
        assert "Perzisch tapijt" in tekst, plek
