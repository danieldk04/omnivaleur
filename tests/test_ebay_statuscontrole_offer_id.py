"""Een levende eBay-advertentie mag niet stil in het archief belanden.

WAAROM DIT ER IS (14-09-2026, gemeten op de echte database en op ebay.nl)

eBay's Inventory API kent twee nummers voor dezelfde advertentie: het openbare
advertentienummer (`platform_listing_id`, staat in de link naar de advertentie)
en het interne offer-nummer (`platform_offer_id`). Alleen het tweede werkt op
`GET /offer/{id}`; met het eerste antwoordt eBay altijd 404.

De verkoopcontrole gaf het openbare nummer door. Elke echte eBay-advertentie
kreeg daardoor twee rondes achter elkaar "niet gevonden" en ging binnen het uur
op 'delisted'. Gemeten: alle 8 echt gepubliceerde eBay-advertenties in de
database stonden op 'delisted', terwijl
https://www.ebay.nl/itm/168685598778 op dat moment gewoon te koop stond.

Gevolg voor de klant: de advertentie verdwijnt uit zijn Live-overzicht naar
Archief, en een echte eBay-verkoop wordt nooit opgemerkt, dus blijft het artikel
op Marktplaats en Vinted gewoon te koop staan.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import polling as P  # noqa: E402


class _NepEbay:
    """Doet wat eBay echt doet: alleen het offer-nummer levert een antwoord op."""

    ECHT_OFFER = "264930679011"

    def __init__(self):
        self.gevraagd = []

    async def get_listing_status(self, gegeven_id, credentials):
        self.gevraagd.append(gegeven_id)
        if gegeven_id == self.ECHT_OFFER:
            return "active"
        return "not_found"          # 404 op elk ander nummer


class _NepTabel:
    def __init__(self, opslag):
        self.opslag = opslag

    def update(self, velden):
        self.opslag.update(velden)
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": []})()


class _NepDb:
    def __init__(self, opslag):
        self.opslag = opslag

    def table(self, naam):
        return _NepTabel(self.opslag)


def _draai(listing):
    """Draait één controleronde en geeft terug wat er naar de database ging."""
    opslag = {}
    ebay = _NepEbay()
    oude_db, oude_platform = P.get_db, P.get_platform
    P.get_db = lambda: _NepDb(opslag)
    P.get_platform = lambda naam: ebay
    try:
        asyncio.run(P._check_one(listing, {"access_token": "x"}))
    finally:
        P.get_db, P.get_platform = oude_db, oude_platform
    return opslag, ebay


def _rij(**extra):
    rij = {
        "id": "rij-1",
        "item_id": "item-1",
        "platform": "ebay",
        "platform_listing_id": "168685598778",   # openbaar nummer
        "platform_offer_id": "264930679011",     # intern offer-nummer
        "status": "active",
        "not_found_count": 1,                    # was al één keer misgegaan
    }
    rij.update(extra)
    return rij


def test_levende_ebay_advertentie_blijft_staan():
    """DE KERN: met het juiste nummer ziet de controle dat hij nog te koop staat."""
    opslag, ebay = _draai(_rij())

    assert ebay.gevraagd == ["264930679011"], (
        f"eBay werd bevraagd met het verkeerde nummer: {ebay.gevraagd}")
    assert opslag.get("status") != "delisted", (
        f"levende advertentie werd toch gearchiveerd: {opslag}")
    assert opslag.get("not_found_count") == 0, (
        "de teller 'niet gevonden' had teruggezet moeten worden")


def test_zonder_offer_nummer_geen_gok():
    """Geen offer-nummer bekend: dan niets concluderen, niet gokken op 404.

    Zonder deze regel zou de terugval op het openbare nummer dezelfde valse
    'niet gevonden' opleveren als vóór de reparatie.
    """
    opslag, ebay = _draai(_rij(platform_offer_id=None))

    assert ebay.gevraagd == [], f"toch bevraagd zonder offer-nummer: {ebay.gevraagd}"
    assert opslag.get("status") != "delisted", f"toch gearchiveerd: {opslag}"
    assert "last_checked" in opslag, "de rij moet wel afgestempeld worden"


def test_andere_kanalen_gebruiken_gewoon_het_advertentienummer():
    """Marktplaats en Vinted kennen geen offer-nummer; die keten blijft gelijk."""
    rij = _rij(platform="marktplaats", platform_listing_id="264930679011",
               platform_offer_id=None)
    opslag, ebay = _draai(rij)

    assert ebay.gevraagd == ["264930679011"], (
        f"marktplaats kreeg het verkeerde nummer: {ebay.gevraagd}")
