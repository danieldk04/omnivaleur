"""Een kanaal op "staat online" zetten kan alleen als het er echt staat.

WAAROM DIT ER IS (14-09-2026, Johan Kist / Blackbird Guitars)

Johan klikte in een kwartier bij 23 gitaren elk grijs kanaalicoon aan en
bevestigde telkens "Mark this item as listed on X?". Hij dacht dat hij plaatste.
De server zette zonder vragen 83 advertenties op actief: 2dehands 23, Vinted 23,
Facebook 23, eBay 7, Shopify 7. Niets daarvan bestond. eBay en Shopify waren niet
eens gekoppeld. Het dashboard toonde alles als live, echt plaatsen naar die
kanalen gebeurde daardoor niet meer, elke nacht faalden de verwijderopdrachten
en elk half uur ging er een Vinted-scan de mist in.

De server weigert nu twee dingen:
  1. eBay of Shopify op actief zetten zonder koppeling;
  2. een kanaal op actief zetten zonder herkenbare advertentielink, als er ook
     nergens een spoor van een plaatsing is (geen mislukte of lopende poging,
     geen herplaatsing, geen advertentienummer).
De gewone routes blijven werken: een vastgelopen publicatie afsluiten, "het staat
er wél" bij een mislukte publicatie, een zelf herplaatste advertentie, en een
link plakken bij het verwijderen.

Draaien: python3 -m pytest tests/test_kanaalicoon_is_geen_publiceren.py
"""
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs  # noqa: E402
from backend.api import listings as api  # noqa: E402

# De stand vlak vóór deze reparatie. Niet HEAD: de auto-push-hook commit werk
# in uitvoering, dus HEAD bevat de reparatie al.
OUDE_COMMIT = "c7119a04"


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters = {}, {}
        self.op, self.velden = "select", None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def insert(self, velden): self.op, self.velden = "insert", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def limit(self, *_a, **_k): return self

    def execute(self):
        bron = self.db.tabellen.setdefault(self.tabel, [])
        if self.op == "insert":
            rij = {"id": f"{self.tabel}-{len(bron) + 1}", "platform_listing_id": None, **self.velden}
            bron.append(rij)
            return type("R", (), {"data": [rij]})()
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.in_filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, **tabellen):
        self.tabellen = {"items": [], "listings": [], "jobs": [], "platform_credentials": [],
                         **tabellen}

    def table(self, naam): return _Q(self, naam)


PLATFORMS_JOHAN = ["2dehands", "vinted", "facebook", "ebay", "shopify"]


def _johan(**extra):
    """Zijn account zoals het op 14-09 om 21:06 was: 23 gitaren, alleen live op
    Marktplaats, eBay en Shopify nooit gekoppeld."""
    return _DB(
        items=[{"id": f"g{i}", "user_id": "johan"} for i in range(23)],
        listings=[{"id": f"mp{i}", "item_id": f"g{i}", "platform": "marktplaats",
                   "status": "active", "platform_listing_id": f"m22{i:08d}"} for i in range(23)],
        platform_credentials=[{"id": "c1", "user_id": "johan", "platform": "marktplaats"}],
        **extra,
    )


@pytest.fixture
def scans(monkeypatch):
    geplande: list = []
    monkeypatch.setattr(jobs, "_queue_scan", lambda db, uid, p: geplande.append((uid, p)))
    return geplande


def _nieuw(monkeypatch, db, body, user_id="johan"):
    monkeypatch.setattr(api, "get_db", lambda: db)
    return api.mark_listing_active(body, user_id=user_id)


def _oud(db, body, user_id="johan"):
    """De echte oude functie uit git, niet een nagemaakte."""
    bron = subprocess.run(["git", "show", f"{OUDE_COMMIT}:backend/api/listings.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    stuk = re.search(r"\ndef mark_listing_active\(.*?(?=\n@router)", bron, re.S)
    assert stuk, "de oude functie staat niet in die commit"
    ruimte: dict = {"HTTPException": api.HTTPException, "Depends": lambda _f: None,
                    "get_current_user": None, "get_db": lambda: db,
                    "datetime": datetime, "timezone": timezone,
                    "_parse_listing_id": api._parse_listing_id, "logger": api.logger}
    exec(compile(stuk.group(0), "<oud>", "exec"), ruimte)
    return ruimte["mark_listing_active"](body, user_id=user_id)


def _johans_kwartier(doe):
    """Wat hij deed: bij alle 23 gitaren 2dehands, Vinted en Facebook aanklikken,
    en bij 7 daarvan ook eBay en Shopify. Geen link, geen enkele plaatsing."""
    geweigerd = 0
    for i in range(23):
        for p in PLATFORMS_JOHAN:
            if p in ("ebay", "shopify") and i >= 7:
                continue
            try:
                doe({"item_id": f"g{i}", "platform": p})
            except api.HTTPException as e:
                assert e.status_code == 422
                geweigerd += 1
    return geweigerd


def _nep_rijen(db):
    return [r for r in db.tabellen["listings"]
            if r["platform"] != "marktplaats" and r["status"] == "active"]


# ── Voor en na: precies zijn kwartier ─────────────────────────────────────
def test_voor_zijn_kwartier_gaf_83_nep_advertenties(scans):
    db = _johan()
    geweigerd = _johans_kwartier(lambda body: _oud(db, body))
    assert geweigerd == 0
    nep = _nep_rijen(db)
    assert len(nep) == 83
    per_kanaal = {p: sum(1 for r in nep if r["platform"] == p) for p in PLATFORMS_JOHAN}
    assert per_kanaal == {"2dehands": 23, "vinted": 23, "facebook": 23, "ebay": 7, "shopify": 7}
    assert all(not r["platform_listing_id"] for r in nep)
    # En daar kwamen de scans vandaan die elk half uur faalden.
    assert ("johan", "vinted") in scans


def test_na_zijn_kwartier_staat_er_niets_op_actief(monkeypatch, scans):
    db = _johan()
    geweigerd = _johans_kwartier(lambda body: _nieuw(monkeypatch, db, body))
    assert geweigerd == 83
    assert _nep_rijen(db) == []
    assert scans == []


# ── eBay en Shopify: zonder koppeling nooit ───────────────────────────────
@pytest.mark.parametrize("platform,link", [
    ("ebay", "https://www.ebay.nl/itm/405512345678"),
    ("shopify", "https://blackbird-guitars.myshopify.com/products/gibson-les-paul"),
])
def test_niet_gekoppeld_kanaal_weigert_ook_met_link(monkeypatch, scans, platform, link):
    db = _johan()
    with pytest.raises(api.HTTPException) as e:
        _nieuw(monkeypatch, db, {"item_id": "g0", "platform": platform, "platform_listing_url": link})
    assert e.value.status_code == 422
    assert "connect" in str(e.value.detail).lower()
    assert _nep_rijen(db) == []


def test_gekoppeld_ebay_met_link_mag(monkeypatch, scans):
    db = _johan()
    db.tabellen["platform_credentials"].append({"id": "c2", "user_id": "johan", "platform": "ebay"})
    uit = _nieuw(monkeypatch, db, {"item_id": "g0", "platform": "ebay",
                                   "platform_listing_url": "https://www.ebay.nl/itm/405512345678"})
    assert uit["ok"] and uit["linked"]
    assert uit["listing"]["platform_listing_id"] == "405512345678"


def test_koppeling_van_een_ander_telt_niet(monkeypatch, scans):
    db = _johan()
    db.tabellen["platform_credentials"].append({"id": "c9", "user_id": "iemand", "platform": "shopify"})
    with pytest.raises(api.HTTPException):
        _nieuw(monkeypatch, db, {"item_id": "g0", "platform": "shopify",
                                 "platform_listing_url": "https://x.myshopify.com/products/123"})


# ── Extensiekanalen: zonder spoor alleen met een echte link ───────────────
@pytest.mark.parametrize("platform,link,nummer", [
    ("vinted", "https://www.vinted.nl/items/5123456789-gibson-les-paul", "5123456789"),
    ("2dehands", "https://www.2dehands.be/v/muziek-en-instrumenten/gitaren/m2212345678-gibson", "m2212345678"),
    ("facebook", "https://www.facebook.com/marketplace/item/1234567890123456/", "1234567890123456"),
])
def test_met_echte_link_wordt_hij_gekoppeld(monkeypatch, scans, platform, link, nummer):
    db = _johan()
    uit = _nieuw(monkeypatch, db, {"item_id": "g3", "platform": platform, "platform_listing_url": link})
    assert uit["linked"] and uit["listing"]["platform_listing_id"] == nummer
    assert scans == []   # gekoppeld: niets meer op te zoeken


@pytest.mark.parametrize("link", ["https://www.blackbirdguitars.nl/gibson-les-paul", "ja", "   "])
def test_een_link_die_geen_advertentie_is_telt_niet(monkeypatch, scans, link):
    db = _johan()
    with pytest.raises(api.HTTPException) as e:
        _nieuw(monkeypatch, db, {"item_id": "g3", "platform": "vinted", "platform_listing_url": link})
    assert e.value.status_code == 422
    assert _nep_rijen(db) == []


# ── De gewone routes blijven werken zonder link ───────────────────────────
def test_vastgelopen_publicatie_afsluiten_mag(monkeypatch, scans):
    """De oranje stip: de extensie plaatste, maar kon het niet bevestigen."""
    db = _johan(jobs=[{"id": "j1", "user_id": "johan", "item_id": "g1", "platform": "2dehands",
                       "action": "create", "status": "claimed"}])
    uit = _nieuw(monkeypatch, db, {"item_id": "g1", "platform": "2dehands"})
    assert uit["ok"]
    assert db.tabellen["jobs"][0]["status"] == "done"
    assert ("johan", "2dehands") in scans


@pytest.mark.parametrize("status", ["error", "relisting", "pending"])
def test_een_eerdere_plaatsing_is_genoeg_spoor(monkeypatch, scans, status):
    """Mislukt-venster ("It is online"), zelf herplaatst, of nog in de rij."""
    db = _johan()
    db.tabellen["listings"].append({"id": "x", "item_id": "g2", "platform": "vinted",
                                    "status": status, "platform_listing_id": None})
    uit = _nieuw(monkeypatch, db, {"item_id": "g2", "platform": "vinted"})
    assert uit["ok"] and db.tabellen["listings"][-1]["status"] == "active"


def test_verwijderde_advertentie_met_nummer_mag_terug(monkeypatch, scans):
    db = _johan()
    db.tabellen["listings"].append({"id": "x", "item_id": "g2", "platform": "2dehands",
                                    "status": "delisted", "platform_listing_id": "m2299999999"})
    uit = _nieuw(monkeypatch, db, {"item_id": "g2", "platform": "2dehands"})
    assert uit["linked"]


def test_andermans_artikel_blijft_verboden(monkeypatch, scans):
    db = _johan()
    with pytest.raises(api.HTTPException) as e:
        _nieuw(monkeypatch, db, {"item_id": "g0", "platform": "vinted",
                                 "platform_listing_url": "https://www.vinted.nl/items/1"},
               user_id="iemand-anders")
    assert e.value.status_code == 404
