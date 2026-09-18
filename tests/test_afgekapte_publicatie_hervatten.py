"""Een publicatie die halverwege werd afgekapt blijft niet eeuwig "Publishing…".

WAAROM DIT ER IS (18-09-2026, Daniels eigen account).

Railway geeft een oude deployment standaard nul seconden om af te ronden: bij
elke nieuwe versie krijgt het proces meteen een SIGKILL. Drukte iemand net op
publiceren, dan is het verzoek weg. Marktplaats, 2dehands en Vinted overleven
dat (hun opdracht staat in de wachtrij), Shopify en eBay niet: die worden
rechtstreeks vanuit het verzoek gepubliceerd.

GEMETEN: (1370) Navy Quechua Trousers, 16:15:32 UTC. Drie extensie-opdrachten
klaargezet, Shopify-rij aangemaakt om 16:15:34.9, en daarna niets meer — in de
winkel bestond geen product met SKU 1370, en de rij stond een half uur later nog
steeds op 'pending' zonder advertentienummer.

Deze tests bewaken de drie afslagen van de herstelronde: koppelen wat er al
staat, alsnog publiceren wat er niet staat, en een leesbare fout achterlaten als
geen van beide kan.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402
import backend.services.publicatie_herstel as ph  # noqa: E402
import backend.services.shopify_reconcile as sr  # noqa: E402


def _tijd(minuten_geleden: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten_geleden)).isoformat()


class _Tabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam
        self._filters = []
        self._update = None
        self._delete = False

    def select(self, *a, **kw):
        return self

    def eq(self, veld, waarde):
        self._filters.append(("eq", veld, waarde))
        return self

    def in_(self, veld, waarden):
        self._filters.append(("in", veld, set(waarden)))
        return self

    def is_(self, veld, waarde):
        self._filters.append(("eq", veld, None if waarde == "null" else waarde))
        return self

    def lt(self, veld, waarde):
        self._filters.append(("lt", veld, waarde))
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    def update(self, patch):
        self._update = patch
        return self

    def delete(self):
        self._delete = True
        return self

    def _treffers(self):
        rijen = list(self.db.tabellen.get(self.naam, []))
        for soort, veld, waarde in self._filters:
            if soort == "in":
                rijen = [r for r in rijen if r.get(veld) in waarde]
            elif soort == "lt":
                rijen = [r for r in rijen if (r.get(veld) or "") < waarde]
            else:
                rijen = [r for r in rijen if r.get(veld) == waarde]
        return rijen

    def execute(self):
        treffers = self._treffers()
        if self._delete:
            for r in treffers:
                self.db.tabellen[self.naam].remove(r)
                self.db.verwijderd.append((self.naam, r))
            return type("R", (), {"data": treffers})()
        if self._update is not None:
            for r in treffers:
                r.update(self._update)
                self.db.bijgewerkt.append((self.naam, dict(r)))
            return type("R", (), {"data": treffers})()
        return type("R", (), {"data": treffers})()


class _DB:
    def __init__(self, tabellen):
        self.tabellen = tabellen
        self.bijgewerkt = []
        self.verwijderd = []

    def table(self, naam):
        return _Tabel(self, naam)


def _opzet(monkeypatch, listings, items, gekoppeld=True):
    db = _DB({
        "listings": listings,
        "items": items,
        "platform_credentials": ([{"user_id": "u1", "platform": "shopify"}]
                                 if gekoppeld else []),
    })
    monkeypatch.setattr(ph, "get_db", lambda: db)
    gepubliceerd = []

    async def nep_publish(item_id, platforms, user_id):
        gepubliceerd.append((item_id, tuple(platforms), user_id))
        for r in db.tabellen["listings"]:
            if r["item_id"] == item_id and r["platform"] in platforms:
                r.update({"status": "active", "platform_listing_id": "999"})
        return [{"platform": p, "status": "active"} for p in platforms]

    monkeypatch.setattr(cl, "publish_to_platforms", nep_publish)

    async def geen_catalogus(user_id):
        return {"gekoppeld": 0}
    monkeypatch.setattr(sr, "reconcile_shopify_catalog", geen_catalogus)
    return db, gepubliceerd


def _rij(minuten=30, platform="shopify", **kw):
    r = {"id": "L1", "item_id": "i1", "platform": platform, "status": "pending",
         "platform_listing_id": None, "created_at": _tijd(minuten)}
    r.update(kw)
    return r


def _item(**kw):
    r = {"id": "i1", "user_id": "u1", "sku": "1370",
         "title": "(1370) Navy Quechua Trousers - Men XL - Very Good"}
    r.update(kw)
    return r


# ── 1. Het product staat er niet: alsnog publiceren ─────────────────────────

def test_afgekapte_shopify_publicatie_wordt_alsnog_gedaan(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij()], [_item()])

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == [("i1", ("shopify",), "u1")]
    assert uit["hervat"] == 1
    assert db.tabellen["listings"][0]["status"] == "active"


# ── 2. Het product staat er wél: koppelen, niet nog een keer aanmaken ───────

def test_bestaand_product_wordt_gekoppeld_en_niet_opnieuw_aangemaakt(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij()], [_item()])

    async def catalogusronde(user_id):
        # Zo werkt reconcile_shopify_catalog: hij vindt het product op SKU en
        # legt het vast op de vastgelopen rij.
        db.tabellen["listings"][0].update(
            {"status": "active", "platform_listing_id": "16048596812106"})
        return {"gekoppeld": 1, "hersteld": 1}
    monkeypatch.setattr(sr, "reconcile_shopify_catalog", catalogusronde)

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == []          # géén tweede product in de winkel
    assert uit["gekoppeld"] == 1
    assert db.tabellen["listings"][0]["platform_listing_id"] == "16048596812106"


# ── 3. Een publicatie die net loopt, blijft met rust ────────────────────────

def test_een_verse_rij_wordt_niet_aangeraakt(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij(minuten=2)], [_item()])

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == []
    assert uit == {"gekoppeld": 0, "hervat": 0, "gemeld": 0, "gevonden": 0}
    assert db.tabellen["listings"][0]["status"] == "pending"


# ── 4. Het artikel bestaat niet meer ────────────────────────────────────────

def test_rij_zonder_artikel_wordt_opgeruimd(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij()], [])

    asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == []
    assert db.tabellen["listings"] == []


# ── 5. Kanaal niet meer gekoppeld: zichtbare fout, geen eeuwige Publishing ──

def test_zonder_koppeling_komt_er_een_leesbare_fout(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij()], [_item()], gekoppeld=False)

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == []
    assert uit["gemeld"] == 1
    rij = db.tabellen["listings"][0]
    assert rij["status"] == "error"
    assert "Publish" in rij["error_message"]


# ── 6. Ontbrekende velden worden benoemd ───────────────────────────────────

def test_ontbrekende_velden_komen_op_de_rij_te_staan(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij()], [_item()])

    async def weigert(item_id, platforms, user_id):
        raise cl.CrosslistValidationError({"shopify": ["price"]})
    monkeypatch.setattr(cl, "publish_to_platforms", weigert)

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert uit["gemeld"] == 1
    rij = db.tabellen["listings"][0]
    assert rij["status"] == "error"
    assert "price" in rij["error_message"]


# ── 7. eBay loopt langs dezelfde weg ───────────────────────────────────────

def test_ebay_wordt_ook_hervat(monkeypatch):
    db, gepubliceerd = _opzet(monkeypatch, [_rij(platform="ebay")], [_item()])
    db.tabellen["platform_credentials"] = [{"user_id": "u1", "platform": "ebay"}]

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert gepubliceerd == [("i1", ("ebay",), "u1")]
    assert uit["hervat"] == 1


# ── 8. Een weigering mag geen eeuwige herhaling worden ─────────────────────

def test_geweigerd_kanaal_laat_geen_eeuwige_pending_achter(monkeypatch):
    """publish_to_platforms kan het kanaal weigeren (hetzelfde voorwerp staat er
    al onder een dubbele rij, of het kanaal staat op pauze). Die weigering raakt
    onze rij niet aan — dan moet de herstelronde hem zelf sluiten, anders
    probeert hij het elke tien minuten opnieuw."""
    db, _ = _opzet(monkeypatch, [_rij()], [_item()])

    async def weigert(item_id, platforms, user_id):
        return [{"platform": "shopify", "status": "duplicate",
                 "error": "Already listed here under a duplicate copy of this item."}]
    monkeypatch.setattr(cl, "publish_to_platforms", weigert)

    uit = asyncio.run(ph.hervat_afgekapte_api_publicaties())

    assert uit["gemeld"] == 1
    rij = db.tabellen["listings"][0]
    assert rij["status"] == "error"
    assert "duplicate copy" in rij["error_message"]
