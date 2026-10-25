"""Een bewuste kopie of een eigen stuk uit de webshop is geen dubbele (Janneke, 25-10-2026).

Zij verkoopt van veel producten meer stuks, elk met eigen Shopify-product maar
dezelfde titel en foto. Na een verkoop klikt ze op Herplaatsen (nieuwe rij REV-…)
en kreeg ze "Staat hier al onder een dubbele kopie van dit item", omdat een ander
stuk al op Vinted stond. Twee imports van dezelfde advertentie blijven wel
geblokkeerd.
"""
from backend.services.crosslist import _zelfde_artikel_al_online
from tests.test_dubbele_advertentie_zelfde_foto import NepDb, GEBRUIKER

FOTO = ["https://img/trui-1.jpg"]


def _item(i, sku, titel="Trui Lyle & Scott maat 110-116"):
    return {"id": i, "user_id": GEBRUIKER, "sku": sku, "title": titel, "photo_urls": FOTO}


def _db(items, listings):
    return NepDb(items=items, listings=listings)


def _vinted_actief(item_id):
    return {"item_id": item_id, "platform": "vinted", "status": "active",
            "platform_listing_id": "10516716449", "platform_listing_url": "u"}


def _shop(item_id, nummer):
    return {"item_id": item_id, "platform": "shopify", "status": "active",
            "platform_listing_id": nummer, "platform_listing_url": None}


def test_herplaatste_kopie_wordt_niet_geblokkeerd_door_een_ander_stuk():
    oud = _item("a", "IMP-A")
    kopie = _item("b", "REV-B")
    db = _db([oud, kopie], [_vinted_actief("a"), _shop("a", "111")])
    assert _zelfde_artikel_al_online(db, kopie, ["vinted"]) == {}


def test_stuk_met_eigen_webshopnummer_wordt_niet_geblokkeerd():
    a, b = _item("a", "IMP-A"), _item("b", "IMP-B")
    db = _db([a, b], [_vinted_actief("a"), _shop("a", "111"), _shop("b", "222")])
    assert _zelfde_artikel_al_online(db, b, ["vinted"]) == {}


def test_tweede_import_van_dezelfde_advertentie_blijft_geblokkeerd():
    a, b = _item("a", "IMP-A"), _item("b", "IMP-B")
    db = _db([a, b], [_vinted_actief("a"), _shop("a", "111"), _shop("b", "111")])
    assert set(_zelfde_artikel_al_online(db, b, ["vinted"])) == {"vinted"}


def test_zonder_webshopnummers_blijft_de_oude_controle_gelden():
    a, b = _item("a", "IMP-A"), _item("b", "IMP-B")
    db = _db([a, b], [_vinted_actief("a")])
    assert set(_zelfde_artikel_al_online(db, b, ["vinted"])) == {"vinted"}
