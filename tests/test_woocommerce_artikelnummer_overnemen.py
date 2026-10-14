"""Toon (dejuistetoon), 14-10-2026: zijn WooCommerce-producten heten "kh15" of
"wk011*", maar in Omnivaleur kregen ze IMP-C3626C97 en zoeken op zijn eigen
nummer vond niets. Na de scan draagt een gekoppeld artikel nu het nummer uit de
winkel, behalve waar dat iets kapotmaakt."""
from backend.services import woocommerce_scan as ws

U = "96e30080-toon"


class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.kolommen, self.patch = db, tabel, [], None, None
        self.van, self.tot = 0, None

    def select(self, kolommen):
        self.kolommen = [k.strip() for k in kolommen.split(",")]
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v)
        return self

    def in_(self, k, vs):
        vs = set(vs)
        self.filters.append(lambda r: r.get(k) in vs)
        return self

    def order(self, _):
        return self

    def range(self, van, tot):
        self.van, self.tot = van, tot
        return self

    def execute(self):
        rijen = [r for r in self.db.tabellen[self.tabel] if all(f(r) for f in self.filters)]
        if self.patch is not None:
            for r in rijen:
                r.update(self.patch)
            return _Antwoord(rijen)
        rijen = rijen[self.van:None if self.tot is None else self.tot + 1]
        # Alleen de gevraagde kolommen, zoals de echte database.
        return _Antwoord([{k: r.get(k) for k in self.kolommen} for r in rijen])


class _Db:
    def __init__(self, items, listings):
        self.tabellen = {"items": items, "listings": listings}

    def table(self, naam):
        return _Vraag(self, naam)


def _opzet():
    items = [
        {"id": "a", "user_id": U, "sku": "IMP-C3626C97"},   # koeienhuid, gewoon
        {"id": "b", "user_id": U, "sku": "IMP-CB4D462E"},   # staat ook op eBay
        {"id": "c", "user_id": U, "sku": "eigen-1"},         # verkoper koos zelf een nummer
        {"id": "d", "user_id": U, "sku": "IMP-D7CB5985"},   # nummer al bij ander artikel
        {"id": "e", "user_id": U, "sku": "IMP-EEEEEEEE"},   # nummer dubbel in de winkel
        {"id": "f", "user_id": U, "sku": "IMP-FFFFFFFF"},   # tweede met dat dubbele nummer
        {"id": "g", "user_id": U, "sku": "kh99"},
        {"id": "x", "user_id": "iemand-anders", "sku": "IMP-XXXXXXXX"},
    ]
    listings = [
        {"id": 1, "item_id": "a", "platform": "woocommerce", "platform_listing_id": "48991"},
        {"id": 2, "item_id": "b", "platform": "woocommerce", "platform_listing_id": "48999"},
        {"id": 3, "item_id": "b", "platform": "ebay", "platform_listing_id": "ebay-1"},
        {"id": 4, "item_id": "c", "platform": "woocommerce", "platform_listing_id": "49007"},
        {"id": 5, "item_id": "d", "platform": "woocommerce", "platform_listing_id": "49018"},
        {"id": 6, "item_id": "e", "platform": "woocommerce", "platform_listing_id": "49030"},
        {"id": 7, "item_id": "f", "platform": "woocommerce", "platform_listing_id": "49032"},
        {"id": 8, "item_id": "x", "platform": "woocommerce", "platform_listing_id": "49239"},
    ]
    regels = [
        {"platform_listing_id": "48991", "sku": "kh15"},
        {"platform_listing_id": "48999", "sku": "kh16"},
        {"platform_listing_id": "49007", "sku": "kh17"},
        {"platform_listing_id": "49018", "sku": "KH99"},
        {"platform_listing_id": "49030", "sku": "gr11"},
        {"platform_listing_id": "49032", "sku": "gr11"},
        {"platform_listing_id": "49239", "sku": "wk011*"},
        {"platform_listing_id": "50000", "sku": None},
    ]
    return _Db(items, listings), regels


def test_gekoppeld_artikel_krijgt_het_nummer_uit_de_winkel():
    db, regels = _opzet()
    assert ws.winkelnummers_overnemen(db, U, regels) == 1
    sku = {i["id"]: i["sku"] for i in db.tabellen["items"]}
    assert sku["a"] == "kh15"


def test_niets_kapotmaken():
    db, regels = _opzet()
    ws.winkelnummers_overnemen(db, U, regels)
    sku = {i["id"]: i["sku"] for i in db.tabellen["items"]}
    assert sku["b"] == "IMP-CB4D462E"        # eBay vindt zijn aanbod op dit nummer
    assert sku["c"] == "eigen-1"             # een eigen nummer blijft staan
    assert sku["d"] == "IMP-D7CB5985"        # kh99 hoort al bij artikel g
    assert (sku["e"], sku["f"]) == ("IMP-EEEEEEEE", "IMP-FFFFFFFF")  # gr11 dubbel in de winkel
    assert sku["x"] == "IMP-XXXXXXXX"        # andermans artikel


def test_tweede_keer_doet_niets():
    db, regels = _opzet()
    ws.winkelnummers_overnemen(db, U, regels)
    assert ws.winkelnummers_overnemen(db, U, regels) == 0


def test_scanregel_draagt_het_nummer():
    regel = ws.naar_scanregel({"id": 48991, "name": "Grote Koeienhuid", "sku": " kh15 ",
                               "regular_price": "100", "images": []})
    assert regel["sku"] == "kh15"
