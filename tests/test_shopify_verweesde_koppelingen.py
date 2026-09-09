"""Een Shopify-listingrij rechtzetten die 'actief' zegt terwijl het product weg is.

WAAROM DIT ER IS (09-09-2026, Daniel)

GEMETEN op Revaleur's eigen winkel, ná de koppelronde uit
tests/test_shopify_bestaande_catalogus_koppelen.py: van de 264 actieve
Shopify-rijen wezen er 4 naar een product dat er niet meer is. Drie soorten,
die allemaal een andere, veilige uitkomst verdienen — zie de docstring van
reconcile_verweesde_shopify_listings voor de volledige uitleg:

  1. "(1327) Navy Suitsupply Suit Pants" had TWEE actieve rijen: de oudste
     (24-07) wees naar een verdwenen product, de nieuwste (02-08) bestond nog
     gewoon. Een oude herplaatsing had een tweede product naast het eerste
     gezet in plaats van het te vervangen. Rechtstreeks opgeruimd, geen vraag.
  2. "(1323) Grey Suitsupply Cardigan" en "(1288) Beige Profuomo Fleece
     Jacket" hadden geen levende Shopify-rij meer en ook geen bevestigde
     verkoop op een ander kanaal. Naar 'sold_unconfirmed' — de bestaande
     "Is dit verkocht?"-vraag op het dashboard.
  3. "B'TWIN Cycling Set" had nooit een platform_listing_id gekregen (een
     mislukte publicatie van 11-08-2026 die op 'active' bleef staan). Zonder
     ID is er niets te controleren, en dat telt hier ook als "weg".

Een verkeerde gok is hier erger dan geen actie: die haalt een levend artikel
van al je andere kanalen af (via de sold-confirm-flow) of verbergt juist een
storing. Vandaar de harde regel: een transiënte fout (429, 5xx, een
netwerkhik) mag een listing NOOIT laten kelderen.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.shopify_reconcile as sr  # noqa: E402


# ── Nep-database, met update-ondersteuning ───────────────────────────────────

class _Tabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam
        self._filters = []
        self._update = None

    def select(self, *a, **kw):
        return self

    def eq(self, veld, waarde):
        self._filters.append((veld, waarde))
        return self

    def in_(self, veld, waarden):
        self._filters.append(("in", veld, set(waarden)))
        return self

    def limit(self, n):
        return self

    def update(self, velden):
        self._update = velden
        return self

    def _match(self, rijen):
        for f in self._filters:
            if f[0] == "in":
                _, veld, waarden = f
                rijen = [r for r in rijen if r.get(veld) in waarden]
            else:
                veld, waarde = f
                rijen = [r for r in rijen if r.get(veld) == waarde]
        return rijen

    def execute(self):
        alle = self.db.tabellen.setdefault(self.naam, [])
        if self._update is not None:
            getroffen = self._match(list(alle))
            for r in getroffen:
                r.update(self._update)
            self.db.bijgewerkt.append(
                (self.naam, dict(self._update), [r.get("id") for r in getroffen]))
            return type("R", (), {"data": getroffen})()
        return type("R", (), {"data": self._match(list(alle))})()


class _DB:
    def __init__(self, tabellen):
        self.tabellen = tabellen
        self.bijgewerkt = []

    def table(self, naam):
        return _Tabel(self, naam)


# ── Nep-Shopify: elk product-id krijgt een vaste of oplopende reeks statussen ─

class _Antwoord:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return {}


def _nep_bestaat(monkeypatch, status_per_id: dict):
    """status_per_id: pid -> 200 (levend), 404 (weg), of een lijst zoals
    [429, 200] voor 'eerst afgewezen, dan alsnog gevonden'."""
    import httpx
    volgende = {k: (list(v) if isinstance(v, list) else [v]) for k, v in status_per_id.items()}

    async def get(self, url, headers=None, **kw):
        pid = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".json")
        reeks = volgende.get(pid, [500])
        code = reeks.pop(0) if len(reeks) > 1 else reeks[0]
        return _Antwoord(code, headers={"Retry-After": "0"})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)


def _opzet(monkeypatch, listings, status_per_id, items=None):
    db = _DB({
        "platform_credentials": [{
            "user_id": "u1", "platform": "shopify", "access_token": "tok",
            "extra_data": {"shop_domain": "test-shop.myshopify.com"},
        }],
        "items": items or [{"id": "i1", "user_id": "u1"}],
        "listings": listings,
    })
    monkeypatch.setattr(sr, "get_db", lambda: db)

    async def geen_verversing(cred):
        return cred["extra_data"]["shop_domain"], cred["access_token"]
    monkeypatch.setattr(sr, "_shop_creds", geen_verversing)
    monkeypatch.setattr(sr, "_PAUZE_TUSSEN_PAGINAS", 0)  # tests mogen niet wachten
    _nep_bestaat(monkeypatch, status_per_id)
    return db


def _rij(rid, item_id, pid, status="active"):
    return {"id": rid, "item_id": item_id, "platform": "shopify",
            "status": status, "platform_listing_id": pid}


# ── 1. Overbodig: er is al een levende opvolger ──────────────────────────────

def test_verweesde_rij_met_levende_opvolger_gaat_rechtstreeks_naar_delisted(monkeypatch):
    """Precies "(1327) Navy Suitsupply Suit Pants": een oude relist zette een
    tweede product naast het eerste."""
    oud = _rij("oud", "i1", "111")
    nieuw = _rij("nieuw", "i1", "222")
    db = _opzet(monkeypatch, [oud, nieuw], {"111": 404, "222": 200})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit["opgeruimd"] == 1
    assert uit["gevraagd"] == 0
    assert oud["status"] == "delisted"
    assert nieuw["status"] == "active"  # de levende rij blijft met rust


# ── 2. Niets meer levend, geen bevestigde verkoop elders: vraag het ──────────

def test_geen_levende_rij_en_geen_verkoop_elders_wordt_gevraagd(monkeypatch):
    """"(1323) Grey Suitsupply Cardigan": weg op Shopify, nergens 'sold'."""
    rij = _rij("r1", "i1", "111")
    listings = [
        rij,
        {"id": "vinted1", "item_id": "i1", "platform": "vinted", "status": "active"},
    ]
    db = _opzet(monkeypatch, listings, {"111": 404})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit["gevraagd"] == 1
    assert uit["opgeruimd"] == 0
    assert rij["status"] == "sold_unconfirmed"
    assert "Shopify" in rij["error_message"]


# ── 3. Niets meer levend, MAAR al bevestigd verkocht elders: geen vraag ──────

def test_al_bevestigd_verkocht_op_ander_kanaal_wordt_direct_afgesloten(monkeypatch):
    rij = _rij("r1", "i1", "111")
    listings = [
        rij,
        {"id": "vinted1", "item_id": "i1", "platform": "vinted", "status": "sold"},
    ]
    db = _opzet(monkeypatch, listings, {"111": 404})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit["opgeruimd"] == 1
    assert uit["gevraagd"] == 0
    assert rij["status"] == "delisted"


# ── 4. Geen platform_listing_id: telt ook als 'weg', niet als 'onbekend' ────

def test_zonder_platform_listing_id_telt_als_weg(monkeypatch):
    """"B'TWIN Cycling Set": een mislukte publicatie die nooit een ID kreeg."""
    rij = _rij("r1", "i1", None)
    db = _opzet(monkeypatch, [rij], {})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit["gevraagd"] == 1
    assert rij["status"] == "sold_unconfirmed"


# ── 5. Het hardste vangnet: een transiënte fout mag NOOIT laten kelderen ────

def test_een_tijdelijke_shopify_storing_verandert_niets(monkeypatch):
    """500 (of blijvend 429) is geen bewijs dat het product weg is."""
    rij = _rij("r1", "i1", "111")
    db = _opzet(monkeypatch, [rij], {"111": 500})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit["opgeruimd"] == 0
    assert uit["gevraagd"] == 0
    assert uit["overgeslagen"] == 1
    assert rij["status"] == "active"


def test_429_wordt_afgewacht_en_daarna_gewoon_als_levend_gezien(monkeypatch):
    """Eerst afgewezen (rate limit), daarna een normaal antwoord — geen storing."""
    rij = _rij("r1", "i1", "111")
    db = _opzet(monkeypatch, [rij], {"111": [429, 200]})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit == {"opgeruimd": 0, "gevraagd": 0, "overgeslagen": 0}
    assert rij["status"] == "active"


def test_onzekerheid_over_een_rij_raakt_de_andere_rij_van_hetzelfde_artikel_niet_aan(monkeypatch):
    """Twijfel over rij A mag rij B van hetzelfde artikel niet meesleuren —
    anders zou een halve controle een verkeerde 'overbodig'-conclusie trekken."""
    a = _rij("a", "i1", "111")
    b = _rij("b", "i1", "222")
    db = _opzet(monkeypatch, [a, b], {"111": 500, "222": 404})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert a["status"] == "active"
    assert b["status"] == "active"
    assert uit["opgeruimd"] == 0 and uit["gevraagd"] == 0


# ── 6. Wat gewoon leeft, blijft onaangeroerd ─────────────────────────────────

def test_een_levend_artikel_wordt_niet_aangeraakt(monkeypatch):
    rij = _rij("r1", "i1", "111")
    db = _opzet(monkeypatch, [rij], {"111": 200})

    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))

    assert uit == {"opgeruimd": 0, "gevraagd": 0, "overgeslagen": 0}
    assert rij["status"] == "active"


def test_geen_shopify_koppeling_geeft_meteen_op(monkeypatch):
    db = _DB({"platform_credentials": [], "items": [], "listings": []})
    monkeypatch.setattr(sr, "get_db", lambda: db)
    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))
    assert uit["opgeruimd"] == 0 and uit["gevraagd"] == 0
    assert uit["reden"] == "Shopify niet gekoppeld"


def test_geen_actieve_shopify_rijen_is_geen_probleem(monkeypatch):
    db = _opzet(monkeypatch, [], {})
    uit = asyncio.run(sr.reconcile_verweesde_shopify_listings("u1"))
    assert uit == {"opgeruimd": 0, "gevraagd": 0}
