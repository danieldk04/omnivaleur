"""De bevestigingspoort: zachte verkoopsignalen vragen, harde blijven automatisch.

WAAROM DIT ER IS (07-09-2026, Daniel)
Delist moet over alle kanalen kloppen: verkoopt iets ergens, dan hoort het overal
anders weg — maar pas als de verkoper dat bevestigt, zodat er nooit iets
verdwijnt dat niet echt verkocht is.

  * Zacht signaal (advertentie verdwenen, 'verkocht'-label op MP/2dehands, de
    berichtenbadge, de 5-minuten statuscheck van MP/2dehands): de rij gaat op
    'sold_unconfirmed' en de verkoper krijgt een ja/nee-vraag in het dashboard.
  * Hard signaal (betaalde bestelling op Shopify/eBay, Vinted-bestellingenpagina):
    daar staat een koper met een bon, dus dat wordt meteen afgehandeld.
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import BackgroundTasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402
from backend.services import polling as pol  # noqa: E402


# ── Nagebootste database ────────────────────────────────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.op, self.velden = {}, {}, None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def neq(self, k, v): self.filters[f"neq:{k}"] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self

    def _match(self, r):
        for k, v in self.filters.items():
            if k.startswith("neq:"):
                if r.get(k[4:]) == v: return False
            elif r.get(k) != v:
                return False
        return all(r.get(k) in vals for k, vals in self.in_filters.items())

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        rijen = [r for r in bron if self._match(r)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings

    def table(self, naam):
        return _Q(self, naam)


class _Req:
    def __init__(self, headers=None):
        self._h = {k.lower(): v for k, v in (headers or {}).items()}

    @property
    def headers(self):
        return type("H", (), {"get": lambda _s, k, d=None: self._h.get(k.lower(), d)})()


def _mark_sold(monkeypatch, listings, headers=None):
    db = _DB([{"id": "it1", "user_id": "u1"}], listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    taken = BackgroundTasks()
    uit = api.mark_sold("it1", "marktplaats", taken, _Req(headers),
                        sold_price=None, dry_run=False, user_id="u1")
    return db, taken, uit


# ── 1. mark_sold: extensie vraagt, dashboard beslist ────────────────────────

def test_een_extensiemelding_op_marktplaats_vraagt_om_bevestiging(monkeypatch):
    db, taken, uit = _mark_sold(
        monkeypatch,
        [{"id": "l1", "item_id": "it1", "platform": "marktplaats", "status": "active"}],
        headers={"X-Omnivaleur-Ext": "1.0.310"})
    assert uit["status"] == "awaiting_confirmation"
    assert not taken.tasks, "niets wordt automatisch afgemeld"
    assert db.listings[0]["status"] == "sold_unconfirmed"
    assert "toont zelf" in db.listings[0]["error_message"]


def test_de_handmatige_sold_knop_meldt_wel_meteen_af(monkeypatch):
    """De knop in het dashboard draagt geen versiekopstuk: dat is de verkoper zelf
    die op Sold klikt, met de dry-run-waarschuwing al gezien."""
    _db, taken, uit = _mark_sold(
        monkeypatch,
        [{"id": "l1", "item_id": "it1", "platform": "marktplaats", "status": "active"}],
        headers=None)
    assert uit["status"] == "delist_triggered"
    assert len(taken.tasks) == 1
    assert taken.tasks[0].args[:2] == ("it1", "marktplaats")


def test_een_extensiemelding_op_ebay_blijft_automatisch(monkeypatch):
    db = _DB([{"id": "it1", "user_id": "u1"}], [
        {"id": "l1", "item_id": "it1", "platform": "ebay", "status": "active"}])
    monkeypatch.setattr(api, "get_db", lambda: db)
    taken = BackgroundTasks()
    uit = api.mark_sold("it1", "ebay", taken, _Req({"X-Omnivaleur-Ext": "1.0.310"}),
                        sold_price=None, dry_run=False, user_id="u1")
    assert uit["status"] == "delist_triggered"
    assert len(taken.tasks) == 1


# ── 2. De 5-minuten statuscheck ────────────────────────────────────────────

def _check(monkeypatch, platform, status, listing_status="active"):
    geboekt = []

    class _P:
        async def get_listing_status(self, *_a, **_k):
            return status

    monkeypatch.setattr(pol, "get_platform", lambda _n: _P())

    async def _fake_handle(item_id, plat, *a, **k):
        geboekt.append((item_id, plat))

    monkeypatch.setattr(pol, "handle_item_sold", _fake_handle)

    listing = {"id": "l1", "item_id": "it1", "platform": platform, "status": listing_status,
               "platform_listing_id": "x1"}
    updates = {}

    class _Q2:
        def __init__(self): self.f = {}
        def update(self, v): updates.update(v); return self
        def eq(self, *_a): return self
        def execute(self): return type("R", (), {"data": [listing]})()

    class _DB2:
        def table(self, _n): return _Q2()

    monkeypatch.setattr(pol, "get_db", lambda: _DB2())
    monkeypatch.setattr(pol, "_exec", lambda q: asyncio.sleep(0, result=q.execute()))
    asyncio.run(pol._check_one(listing, {}))
    return updates, geboekt


def test_marktplaats_verkocht_wordt_een_vraag_niet_een_afmelding(monkeypatch):
    updates, geboekt = _check(monkeypatch, "marktplaats", "sold")
    assert updates.get("status") == "sold_unconfirmed"
    assert not geboekt, "geen automatische cross-platform afmelding op dit signaal"
    # zelfde reden-tekst als de rest van de bevestigingsstroom
    assert updates.get("error_message") == api.VERDENKING_REDENEN["label"]


def test_ebay_verkocht_wordt_wel_meteen_afgehandeld(monkeypatch):
    updates, geboekt = _check(monkeypatch, "ebay", "sold")
    assert geboekt == [("it1", "ebay")]
    assert updates.get("status") != "sold_unconfirmed"


def test_2dehands_niet_gevonden_blijft_zoals_het_was(monkeypatch):
    """not_found is een aparte tak (twee rondes) en die verandert niet."""
    updates, geboekt = _check(monkeypatch, "2dehands", "not_found")
    assert updates.get("status") != "sold_unconfirmed"
    assert not geboekt


# ── 3. Shopify: matchen op product-id, niet alleen SKU ─────────────────────

def test_match_shopify_op_productid_met_eigendomscontrole(monkeypatch):
    from backend.services import shopify_orders as so
    db = _DB(
        [{"id": "itA", "user_id": "u1", "sku": ""}, {"id": "itB", "user_id": "u2", "sku": ""}],
        [{"id": "l1", "item_id": "itA", "platform": "shopify", "platform_listing_id": "999"}])
    # product 999 hoort bij itA (van u1)
    got = asyncio.run(so.match_shopify_sale(db, "u1", {"product_id": "999"}))
    assert got == "itA"
    # dezelfde bestelregel bij een andere winkelier levert niets op
    assert asyncio.run(so.match_shopify_sale(db, "u2", {"product_id": "999"})) is None


def test_match_shopify_valt_terug_op_sku_binnen_de_winkelier(monkeypatch):
    from backend.services import shopify_orders as so
    db = _DB(
        [{"id": "itA", "user_id": "u1", "sku": "REV-XYZ"}, {"id": "itB", "user_id": "u2", "sku": "REV-XYZ"}],
        [])
    assert asyncio.run(so.match_shopify_sale(db, "u1", {"sku": "REV-XYZ"})) == "itA"
    assert asyncio.run(so.match_shopify_sale(db, "u2", {"sku": "REV-XYZ"})) == "itB"


# ── 4. De planner draait de vangnetten ─────────────────────────────────────

def test_reconciliatie_en_herinnering_staan_in_de_planner():
    sched = (ROOT / "backend/scheduler.py").read_text(encoding="utf-8")
    assert 'id="verkoop_reconciliatie"' in sched
    assert 'id="verkoop_herinnering"' in sched
    assert "reconcileer_verkochte_artikelen" in sched
    assert "herinner_onbevestigde_verkopen" in sched


# ── 5. Afmelden telt per advertentie, niet per platform ────────────────────

def test_delist_dedupt_per_advertentie_niet_per_platform():
    """Dubbele import of meerdere herplaatsingen = twee verschillende
    advertenties op één platform. Beide moeten weg; de oude 'één per platform'
    liet de tweede staan en het verkochte artikel bleef te koop."""
    cl = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    blok = cl.split("async def delist_all_platforms(", 1)[1].split("\nasync def ", 1)[0]
    assert "seen_ads" in blok and "(l[\"platform\"], pid or \"\")" in blok
    # 'delisted' alleen nog als vangnet: geen tabblad per archiefrij
    assert "als VANGNET" in blok


def test_extensie_verwijderopdracht_dedupt_op_advertentienummer():
    cl = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    fn = cl.split("def _enqueue_extension_delete(", 1)[1].split("\ndef ", 1)[0]
    assert "ad_id" in fn and "j_pid == ad_id" in fn


def test_al_verkocht_elders_zet_onbevestigde_rij_in_het_archief():
    recon = (ROOT / "backend/services/verkoop_reconciliatie.py").read_text(encoding="utf-8")
    assert 'r.get("status") == "sold_unconfirmed"' in recon
    assert '"status": "delisted"' in recon
