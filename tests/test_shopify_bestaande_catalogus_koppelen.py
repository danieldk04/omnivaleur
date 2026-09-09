"""Een artikel dat al op Shopify staat, wordt zonder handmatig werk als 'gelist' herkend.

WAAROM DIT ER IS (09-09-2026, Daniel)

"Op dit moment wordt dit product niet herkend als actief product op Shopify."
Marktplaats en 2dehands hebben een scan die een bestaande advertentie herkent
en aanbiedt om te koppelen; Shopify had dat niet. Wie zijn winkel koppelt
terwijl er al een catalogus staat — de normale situatie — zag elk artikel dat
óók op Shopify staat gewoon als "niet gelist", en zou dat per artikel
handmatig moeten aanvinken.

GEMETEN op Revaleur's eigen winkel (09-09-2026, 315 actieve Shopify-producten):
241 artikelen stonden al Active op Shopify zonder koppeling in Omnivaleur.
"(1274) Beige Suitsupply Shirt - Men S - Very Good" stond al sinds 31-05-2026
op Shopify — ruim vóór het op 03-07-2026 vanuit Marktplaats werd geïmporteerd.
Na de koppelronde: 241 gekoppeld, 3 terecht overgeslagen (merkverschil), geen
enkel Shopify-product aan twee artikelen gehangen.

Deze tests bewaken de twee vangnetten tegen een VERKEERDE koppeling — die is
erger dan geen koppeling, want zet straks een verkoop op het verkeerde
artikel af (zie match_shopify_sale in shopify_orders.py, dat eerst op
platform_listing_id zoekt).
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.shopify_reconcile as sr  # noqa: E402


# ── Nep-Shopify: geen echt netwerkverkeer, wel dezelfde vorm ─────────────────

def _product(pid, title, sku, vendor="Suitsupply", handle=None, extra_variant=None):
    variants = [{"sku": sku}]
    if extra_variant:
        variants.append(extra_variant)
    return {"id": pid, "title": title, "vendor": vendor,
            "handle": handle or title.lower().replace(" ", "-"),
            "variants": variants}


class _Antwoord:
    def __init__(self, status, data, headers=None):
        self.status_code = status
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


def _nep_shopify(monkeypatch, producten):
    import httpx

    async def get(self, url, params=None, headers=None, **kw):
        return _Antwoord(200, {"products": producten}, headers={})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)


# ── Nep-database: net genoeg om de reconciliatie te sturen ───────────────────

class _Tabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam
        self._filters = []
        self._select = None

    def select(self, *a, **kw):
        self._select = a
        return self

    def eq(self, veld, waarde):
        self._filters.append((veld, waarde))
        return self

    def in_(self, veld, waarden):
        self._filters.append(("in", veld, set(waarden)))
        return self

    def limit(self, n):
        return self

    def insert(self, rij):
        self.db.ingevoegd.append(rij)
        self._insert = rij
        return self

    def execute(self):
        if getattr(self, "_insert", None) is not None:
            return type("R", (), {"data": [self._insert]})()
        rijen = list(self.db.tabellen.get(self.naam, []))
        for f in self._filters:
            if f[0] == "in":
                _, veld, waarden = f
                rijen = [r for r in rijen if r.get(veld) in waarden]
            else:
                veld, waarde = f
                rijen = [r for r in rijen if r.get(veld) == waarde]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, tabellen):
        self.tabellen = tabellen
        self.ingevoegd = []

    def table(self, naam):
        return _Tabel(self, naam)


def _opzet(monkeypatch, items, producten, bestaande_listings=None):
    db = _DB({
        "platform_credentials": [{
            "user_id": "u1", "platform": "shopify", "access_token": "tok",
            "extra_data": {"shop_domain": "test-shop.myshopify.com"},
        }],
        "items": items,
        "listings": list(bestaande_listings or []),
    })
    monkeypatch.setattr(sr, "get_db", lambda: db)

    async def geen_verversing(cred):
        return cred["extra_data"]["shop_domain"], cred["access_token"]
    monkeypatch.setattr(sr, "_shop_creds", geen_verversing)
    _nep_shopify(monkeypatch, producten)
    return db


def _item(iid, title, brand=None, sku=None, user_id="u1"):
    return {"id": iid, "title": title, "brand": brand, "sku": sku, "user_id": user_id}


# ── 1. De kern: koppelen wat ondubbelzinnig hetzelfde is ────────────────────

def test_een_al_bestaand_shopify_product_wordt_gekoppeld(monkeypatch):
    """Precies het geval van (1274): al op Shopify, nog geen listings-rij."""
    items = [_item("i1", "(1274) Beige Suitsupply Shirt - Men S - Very Good", "Suitsupply")]
    producten = [_product(15685268799818, "Beige Suitsupply Shirt - Men S - Very Good", "1274")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))

    assert uit["gekoppeld"] == 1
    assert len(db.ingevoegd) == 1
    rij = db.ingevoegd[0]
    assert rij["item_id"] == "i1"
    assert rij["platform"] == "shopify"
    assert rij["status"] == "active"
    assert rij["platform_listing_id"] == "15685268799818"
    assert rij["platform_listing_url"].endswith("/products/beige-suitsupply-shirt-men-s-very-good")


def test_een_al_gekoppeld_artikel_blijft_met_rust(monkeypatch):
    """Veilig om vaker te draaien: geen tweede rij voor wat al gekoppeld is."""
    items = [_item("i1", "(1274) Beige Suitsupply Shirt", "Suitsupply")]
    producten = [_product(999, "Beige Suitsupply Shirt", "1274")]
    bestaand = [{"item_id": "i1", "platform": "shopify", "status": "active"}]
    db = _opzet(monkeypatch, items, producten, bestaande_listings=bestaand)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))

    assert uit["gekoppeld"] == 0
    assert db.ingevoegd == []


def test_geen_shopify_koppeling_geeft_meteen_op(monkeypatch):
    db = _DB({"platform_credentials": [], "items": [], "listings": []})
    monkeypatch.setattr(sr, "get_db", lambda: db)
    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit == {"gekoppeld": 0, "reden": "Shopify niet gekoppeld"}


# ── 2. De twee vangnetten tegen een verkeerde koppeling ──────────────────────

def test_ander_merk_bij_hetzelfde_nummer_wordt_niet_gekoppeld(monkeypatch):
    """(1277) is hier Ralph Lauren in Omnivaleur, maar Suitsupply op Shopify —
    zelfde situatie als het echte 'Red/White Suitsupply Shirt'-geval."""
    items = [_item("i1", "(1277) Red/White Sweater", "Ralph Lauren")]
    producten = [_product(1, "Red/White Suitsupply Shirt", "1277", vendor="Suitsupply")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))

    assert uit["gekoppeld"] == 0
    assert uit["overgeslagen_merkverschil"] == 1
    assert db.ingevoegd == []


def test_zonder_merk_op_een_van_beide_kanten_mag_het_nummer_beslissen(monkeypatch):
    """Ontbreekt het merk (bij het artikel of bij het Shopify-product), dan is
    er niets om tegenover elkaar te zetten — het nummer blijft dan het enige
    signaal, precies zoals tweelingen.familie_ids het ook doet."""
    items = [_item("i1", "(1274) Iets zonder merkveld", brand=None)]
    producten = [_product(1, "Beige Suitsupply Shirt", "1274", vendor="Suitsupply")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit["gekoppeld"] == 1


def test_dubbele_sku_op_shopify_zelf_wordt_niet_gegokt(monkeypatch):
    """Draagt hetzelfde nummer twee Shopify-producten (een fout in de winkel
    zelf), dan is niet te zeggen welke ervan bedoeld is."""
    items = [_item("i1", "(1274) Beige Shirt", "Suitsupply")]
    producten = [
        _product(1, "Beige Suitsupply Shirt A", "1274", vendor="Suitsupply"),
        _product(2, "Beige Suitsupply Shirt B", "1274", vendor="Suitsupply"),
    ]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit["gekoppeld"] == 0
    assert db.ingevoegd == []


def test_hetzelfde_nummer_op_twee_eigen_artikelen_is_dubbelzinnig(monkeypatch):
    """Twee Omnivaleur-artikelen met hetzelfde nummer (de verkoper hergebruikte
    het) — dan is niet te zeggen welke van de twee bij het Shopify-product
    hoort, dus geen van beide wordt gekoppeld."""
    items = [
        _item("i1", "(1274) Eerste artikel", "Suitsupply"),
        _item("i2", "(1274) Tweede artikel", "Suitsupply"),
    ]
    producten = [_product(1, "Beige Suitsupply Shirt", "1274", vendor="Suitsupply")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit["gekoppeld"] == 0
    assert uit["overgeslagen_dubbelzinnig"] == 2
    assert db.ingevoegd == []


def test_geen_nummer_geen_koppeling(monkeypatch):
    items = [_item("i1", "Kaal artikel zonder nummer of sku", "Suitsupply")]
    producten = [_product(1, "Iets anders", "1274", vendor="Suitsupply")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit["gekoppeld"] == 0


def test_sku_als_terugval_zonder_nummer_in_de_titel(monkeypatch):
    """Zelfde regel als tweelingen.nummer_van: geen nummer in de titel? Dan het
    SKU-veld van het item zelf, niet de Shopify-SKU."""
    items = [_item("i1", "Kaal artikel", "Suitsupply", sku="1274")]
    producten = [_product(1, "Beige Suitsupply Shirt", "1274", vendor="Suitsupply")]
    db = _opzet(monkeypatch, items, producten)

    uit = asyncio.run(sr.reconcile_shopify_catalog("u1"))
    assert uit["gekoppeld"] == 1
