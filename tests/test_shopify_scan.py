"""Shopify-producten inlezen (backend/services/shopify_scan.py), 23-09-2026."""
from backend.services import shopify_scan as s


def _product(**over):
    p = {"id": 123, "title": "Gouden ring - One size", "handle": "gouden-ring",
         "vendor": "Goudlief", "body_html": "Mooie ring.<br>Material: 14k goud<br>Fit: normaal",
         "images": [{"src": "https://cdn.shopify.com/a.jpg"}],
         "variants": [{"price": "149.00", "sku": "R1", "inventory_management": "shopify",
                       "inventory_quantity": 1}],
         "options": [], "tags": "", "created_at": "2026-09-01T10:00:00+02:00"}
    p.update(over)
    return p


def test_volgende_pagina_uit_link_kop():
    kop = ('<https://x.myshopify.com/admin/api/2024-01/products.json?limit=250&page_info=abc>; rel="previous", '
           '<https://x.myshopify.com/admin/api/2024-01/products.json?limit=250&page_info=def123>; rel="next"')
    assert s.volgende_pagina(kop) == "def123"
    assert s.volgende_pagina('<https://x/p?page_info=abc>; rel="previous"') is None
    assert s.volgende_pagina(None) is None


def test_uitverkocht_alleen_als_alle_bijgehouden_varianten_op_nul_staan():
    assert s.uitverkocht(_product(variants=[{"inventory_management": "shopify", "inventory_quantity": 0}]))
    assert not s.uitverkocht(_product())
    # Geen voorraadbeheer: we weten het niet, dus tonen.
    assert not s.uitverkocht(_product(variants=[{"inventory_management": None, "inventory_quantity": 0}]))


def test_winkelnaam_is_geen_merk():
    alles_winkel = [_product(vendor="Goudlief") for _ in range(12)]
    assert s.winkelnaam_als_merk(alles_winkel) == "Goudlief"
    regel = s.naar_scanregel(alles_winkel[0], "goudlief.myshopify.com", "Goudlief")
    assert regel["brand"] is None
    gemengd = [_product(vendor=f"Merk{i}") for i in range(12)]
    assert s.winkelnaam_als_merk(gemengd) is None
    assert s.naar_scanregel(gemengd[0], "x.myshopify.com")["brand"] == "Merk0"


def test_scanregel_heeft_wat_de_opslag_en_de_verkoopkoppeling_nodig_hebben():
    r = s.naar_scanregel(_product(), "goudlief.myshopify.com")
    # platform_listing_id = product-id: daarop koppelt een verkoop in de winkel.
    assert r["platform_listing_id"] == "123"
    assert r["platform_listing_url"] == "https://goudlief.myshopify.com/products/gouden-ring"
    assert r["price"] == 149.0 and r["photo_urls"] == ["https://cdn.shopify.com/a.jpg"]
    assert r["is_closed"] is False


def test_materiaal_neemt_de_rest_van_de_omschrijving_niet_mee():
    # Gemeten op een echte winkel: zonder de reparatie werd dit
    # "14k goud Fit: normaal".
    assert s.naar_scanregel(_product(), "x.myshopify.com")["material"] == "14k goud"


def test_vastgelopen_shopify_scan_gaat_niet_terug_naar_de_extensie():
    from datetime import datetime, timezone
    from backend.api import jobs

    updates = []

    class Q:
        def __init__(self): self._upd = None
        def select(self, *_): return self
        def eq(self, *_): return self
        def update(self, velden): self._upd = velden; return self
        def execute(self):
            if self._upd is not None:
                updates.append(self._upd); return type("R", (), {"data": []})()
            return type("R", (), {"data": [{"id": "j1", "action": "scan", "platform": "shopify",
                                            "item_id": None, "scheduled_for": None,
                                            "claimed_at": "2026-01-01T00:00:00+00:00", "result": {}}]})()

    class DB:
        def table(self, _): return Q()

    jobs._recover_stale_claims(DB(), "u1", None, datetime.now(timezone.utc))
    assert updates and updates[0]["status"] == "error"
