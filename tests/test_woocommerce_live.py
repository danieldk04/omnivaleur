"""WooCommerce-koppeling tegen een ECHTE WooCommerce-winkel.

Draait alleen met WOO_TEST_URL, WOO_TEST_CK en WOO_TEST_CS. Bedoeld voor een
lokale testwinkel (WordPress Playground: npx @wp-playground/cli server met
WooCommerce), NOOIT voor de winkel van een klant: deze proef maakt producten
en bestellingen aan en zet voorraad op nul.

Optioneel WOO_TEST_MODUS=basic|query|oauth1 (standaard wat bij het adres hoort).
"""
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.platforms import woocommerce as w  # noqa: E402

URL, CK, CS = (os.environ.get(k) for k in ("WOO_TEST_URL", "WOO_TEST_CK", "WOO_TEST_CS"))
pytestmark = pytest.mark.skipif(not (URL and CK and CS), reason="geen testwinkel opgegeven")


def _run(c):
    return asyncio.run(c)


@pytest.fixture(scope="module")
def winkel():
    api_root = _run(w.ontdek_api(w.normaliseer_adres(URL) if URL.startswith("https") else URL.rstrip("/")))
    modus = os.environ.get("WOO_TEST_MODUS") or w.modi_voor(api_root)[0]
    return w.WooClient(api_root, CK, CS, modus)


def _nieuw_product(winkel, **velden):
    body = {"name": f"Proef {time.time_ns()}", "type": "simple", "regular_price": "20",
            "manage_stock": True, "stock_quantity": 1, **velden}
    _, p, _ = _run(winkel.verzoek("POST", "wc/v3/products", body=body))
    return p


def _creds(winkel):
    return {"access_token": CK, "refresh_token": CS,
            "extra_data": {"api_root": winkel.api_root, "modus": winkel.modus}}


def test_inlezen_geeft_scanregels(winkel):
    from backend.services.woocommerce_scan import naar_scanregel
    p = _nieuw_product(winkel, sku=f"LIVE-{time.time_ns()}", stock_quantity=3,
                       attributes=[{"name": "Merk", "options": ["Jottum"], "visible": True},
                                   {"name": "Maat", "options": ["104"], "visible": True},
                                   {"name": "Staat", "options": ["Zo goed als nieuw"], "visible": True}])
    concept = _nieuw_product(winkel, status="draft")
    producten = _run(winkel.producten())
    ids = {str(x["id"]) for x in producten}
    assert str(p["id"]) in ids and str(concept["id"]) not in ids, "alleen gepubliceerde producten"
    r = naar_scanregel(next(x for x in producten if x["id"] == p["id"]))
    assert (r["brand"], r["size"], r["condition"], r["price"]) == ("Jottum", "104", "Zo goed als nieuw", 20.0)
    assert r["platform_listing_url"] and r["platform_listing_url"].startswith(w.site_van_api(winkel.api_root))


def test_alleen_gewijzigde_producten_sinds(winkel):
    sinds = (datetime.now(timezone.utc) - timedelta(seconds=5)).replace(tzinfo=None).isoformat(timespec="seconds")
    p = _nieuw_product(winkel)
    recent = {x["id"] for x in _run(winkel.producten(sinds))}
    assert p["id"] in recent
    toekomst = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None).isoformat(timespec="seconds")
    assert _run(winkel.producten(toekomst)) == []


def test_plaatsen_is_een_stuk_met_foto_en_niet_dubbel(winkel):
    plat = w.WooCommercePlatform()
    sku = f"OMNI-{time.time_ns()}"
    item = {"title": "Proef plaatsen", "price": 12.5, "description": "Regel 1\nRegel 2", "sku": sku,
            "photo_urls": ["https://omnivaleur.com/logo.png", "/lokaal/pad.jpg"]}
    vastgelegd = []

    async def _leg_vast(x): vastgelegd.append(x)

    uit = _run(plat.create_listing(item, _creds(winkel), on_created=_leg_vast))
    assert vastgelegd == [uit] and uit["platform_listing_url"]
    p = _run(winkel.product(uit["platform_listing_id"]))
    assert p["stock_quantity"] == 1 and p["manage_stock"] is True and p["regular_price"] == "12.50"
    assert len(p["images"]) == 1, "alleen het openbare adres; de winkel haalt het zelf op"
    tweede = _run(plat.create_listing(item, _creds(winkel)))
    assert tweede["platform_listing_id"] == uit["platform_listing_id"], "zelfde SKU = zelfde product"


def test_afmelden_zet_op_uitverkocht_en_wist_niets(winkel):
    p = _nieuw_product(winkel)
    assert _run(w.WooCommercePlatform().delete_listing(str(p["id"]), _creds(winkel)))
    na = _run(winkel.product(str(p["id"])))
    assert na["status"] == "publish" and na["stock_status"] == "outofstock" and na["stock_quantity"] == 0


def test_afmelden_zonder_voorraadbeheer(winkel):
    p = _nieuw_product(winkel, manage_stock=False)
    _run(w.WooCommercePlatform().delete_listing(str(p["id"]), _creds(winkel)))
    assert _run(winkel.product(str(p["id"])))["stock_status"] == "outofstock"


def test_prijs_wijzigen_haalt_actieprijs_weg(winkel):
    p = _nieuw_product(winkel, sale_price="15")
    _run(w.WooCommercePlatform().update_listing_price(str(p["id"]), 17.0, _creds(winkel)))
    na = _run(winkel.product(str(p["id"])))
    assert na["price"] == "17.00" or float(na["price"]) == 17.0
    assert na["sale_price"] == ""


def test_echte_bestelling_wordt_gezien_en_verlaagt_de_voorraad(winkel):
    from backend.services.woocommerce_orders import regels_uit_bestelling
    p = _nieuw_product(winkel, stock_quantity=5, sku=f"ORD-{time.time_ns()}")
    sinds = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(tzinfo=None).isoformat(timespec="seconds")
    _run(winkel.verzoek("POST", "wc/v3/orders", body={
        "status": "processing", "set_paid": True,
        "line_items": [{"product_id": p["id"], "quantity": 1}]}))
    orders = _run(winkel.bestellingen(sinds))
    regels = [r for o in orders for r in regels_uit_bestelling(o)]
    assert any(r["product_id"] == str(p["id"]) and r["sku"] == p["sku"] for r in regels)
    assert _run(winkel.product(str(p["id"])))["stock_quantity"] == 4, "WooCommerce telde zelf af"


def test_bestelling_in_afwachting_van_betaling_telt_niet(winkel):
    p = _nieuw_product(winkel)
    sinds = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(tzinfo=None).isoformat(timespec="seconds")
    _run(winkel.verzoek("POST", "wc/v3/orders", body={
        "status": "pending", "line_items": [{"product_id": p["id"], "quantity": 1}]}))
    orders = _run(winkel.bestellingen(sinds))
    assert not any(li.get("product_id") == p["id"] for o in orders for li in o.get("line_items") or [])


def test_voorraadregel_tegen_de_echte_winkel(winkel, monkeypatch):
    from backend.services import shopify_voorraad as sv
    from backend.services import woocommerce_voorraad as wv
    from tests.test_woocommerce import _DB

    p = _nieuw_product(winkel, stock_quantity=5)
    db = _DB(items=[{"id": "i1", "user_id": "u1"}],
             listings=[{"id": "w1", "item_id": "i1", "platform": "woocommerce", "status": "active",
                        "platform_listing_id": str(p["id"])},
                       {"id": "m1", "item_id": "i1", "platform": "marktplaats", "status": "active"}],
             platform_credentials=[{"user_id": "u1", "platform": "woocommerce", **_creds(winkel)}])

    async def _naast(fn, *_a, **_k): return fn()
    monkeypatch.setattr(wv, "naast_de_lus", _naast)
    import backend.database as bd
    monkeypatch.setattr(bd, "naast_de_lus", _naast)
    assert _run(wv.na_verkoop(db, "i1", "marktplaats")) == sv.BLIJFT
    assert _run(winkel.product(str(p["id"])))["stock_quantity"] == 4
    assert db.t["platform_credentials"][0]["extra_data"].get(sv.VLAG) is True
