"""De verkocht-badge in de berichtenlijst als bevestigingsvraag.

WAAROM DIT ER IS (01-09-2026, Daniel; herzien 07-09-2026)
Op de advertentie zelf komt nooit een "verkocht" te staan als je met de hand
verkoopt — jij haalt de advertentie weg en meer ziet Marktplaats niet. Op het
GESPREK met de koper zet Marktplaats wél een groene "Verkocht!"-badge. Dat is de
enige plek waar het platform een handmatige verkoop hardop bevestigt.

Sinds 07-09-2026 (Daniel) wordt daarop niet meer meteen geboekt en afgemeld,
maar GEVRAAGD: de advertentierij gaat op 'sold_unconfirmed' en verschijnt in het
dashboard als ja/nee-vraag. Afmelden bij andere kanalen is onherstelbaar, dus de
verkoper beslist. De grenzen hieronder houden de aanwijzing zuiver.

Het lezen van de badge zelf staat in tests/berichten-verkocht-badge-test.js —
dat draait de echte extensiecode tegen een namaakscherm.
"""
import sys
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402
from backend.services import crosslist as cl  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.op, self.velden = {}, {}, None, None

    def select(self, *_a, **_k):
        self.op = "select"; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def insert(self, velden):
        self.op, self.velden = "insert", velden; return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def in_(self, k, vals):
        self.in_filters[k] = list(vals); return self

    def order(self, *_a, **_k):
        return self

    def range(self, *_a, **_k):
        return self

    def limit(self, _n):
        return self

    def _match(self, r):
        if not all(r.get(k) == v for k, v in self.filters.items()):
            return False
        return all(r.get(k) in vals for k, vals in self.in_filters.items())

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        if self.op == "insert":
            bron.append(dict(self.velden))
            return type("R", (), {"data": [self.velden]})()
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


def _db(monkeypatch, items, listings):
    db = _DB(items, listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "fetch_all", lambda bouw: bouw().execute().data)
    return db


ITEMS = [
    {"id": "it-641", "user_id": "u1", "title": "(641) Blauw Ralph Lauren Half Zip - Men M"},
    {"id": "it-1308", "user_id": "u1", "title": "(1308) Marine Profuomo Half Zip - Men S"},
    {"id": "it-1314", "user_id": "u1", "title": "(1314) Donkergroen Suitable Half Zip"},
    {"id": "it-999", "user_id": "iemand-anders", "title": "(999) Niet van deze verkoper"},
]


def _post(regels, monkeypatch, items=None, listings=None):
    db = _db(monkeypatch, list(items if items is not None else ITEMS), listings or [])
    taken = BackgroundTasks()
    uit = api.sold_from_messages({"platform": "marktplaats", "sold": regels}, taken, user_id="u1")
    return db, taken, uit


# ── 1. Er wordt gevraagd, niet geboekt ─────────────────────────────────────

def test_een_badge_op_een_levend_artikel_vraagt_om_bevestiging(monkeypatch):
    listings = [{"item_id": "it-641", "platform": "marktplaats", "status": "active"}]
    db, taken, uit = _post([{"sku": "641", "title": "(641) Blauw Ralph Lauren"}], monkeypatch,
                           listings=listings)
    assert uit == {"asked": 1, "skipped": 0}
    assert not taken.tasks, "niets wordt meteen afgemeld"
    assert listings[0]["status"] == "sold_unconfirmed"
    assert "Verkocht!" in listings[0]["error_message"]


def test_een_artikel_dat_al_verkocht_is_wordt_niet_opnieuw_gevraagd(monkeypatch):
    listings = [{"item_id": "it-641", "platform": "marktplaats", "status": "sold"}]
    _db_, taken, uit = _post([{"sku": "641"}], monkeypatch, listings=listings)
    assert uit == {"asked": 0, "skipped": 1}
    assert not taken.tasks


def test_een_openstaande_vraag_wordt_niet_verdubbeld(monkeypatch):
    listings = [{"item_id": "it-1314", "platform": "marktplaats", "status": "sold_unconfirmed"}]
    _db_, taken, uit = _post([{"sku": "1314"}], monkeypatch, listings=listings)
    assert uit == {"asked": 0, "skipped": 1}


def test_een_gearchiveerd_artikel_blijft_gearchiveerd(monkeypatch):
    listings = [{"item_id": "it-641", "platform": "marktplaats", "status": "delisted"}]
    _db_, taken, uit = _post([{"sku": "641"}], monkeypatch, listings=listings)
    assert uit == {"asked": 0, "skipped": 1}


def test_het_artikel_van_iemand_anders_blijft_ongemoeid(monkeypatch):
    listings = [{"item_id": "it-999", "platform": "marktplaats", "status": "active"}]
    _db_, taken, uit = _post([{"sku": "999"}], monkeypatch, listings=listings)
    assert uit == {"asked": 0, "skipped": 1}
    assert listings[0]["status"] == "active"


def test_een_nummer_dat_bij_twee_artikelen_hoort_wordt_overgeslagen(monkeypatch):
    """Bij twijfel over WELK artikel het is, is niets doen de enige veilige
    uitkomst."""
    items = ITEMS + [{"id": "it-641b", "user_id": "u1", "title": "(641) Zelfde nummer, ander artikel"}]
    listings = [{"item_id": "it-641", "platform": "marktplaats", "status": "active"},
                {"item_id": "it-641b", "platform": "marktplaats", "status": "active"}]
    _db_, taken, uit = _post([{"sku": "641"}], monkeypatch, items=items, listings=listings)
    assert uit == {"asked": 0, "skipped": 1}
    assert all(l["status"] == "active" for l in listings)


def test_alleen_marktplaats_en_2dehands(monkeypatch):
    _db(monkeypatch, list(ITEMS), [])
    with pytest.raises(HTTPException) as e:
        api.sold_from_messages({"platform": "vinted", "sold": [{"sku": "641"}]},
                               BackgroundTasks(), user_id="u1")
    assert e.value.status_code == 400


# ── 2. Eén verkoop is één verkoop, ook bij zes advertentierijen ─────────────

def test_een_verkoop_telt_maar_een_keer_bij_meerdere_advertentierijen(monkeypatch):
    """Elke herplaatsing zet er een advertentierij bij — één artikel van Daniel
    had er zes op Marktplaats. Alle rijen op 'verkocht' zetten betekent zes
    verkopen in Analytics voor één trui."""
    listings = [
        {"id": "l1", "item_id": "it1", "platform": "marktplaats", "status": "delisted",
         "listed_at": "2026-07-15T12:00:00+00:00"},
        {"id": "l2", "item_id": "it1", "platform": "marktplaats", "status": "delisted",
         "listed_at": "2026-08-29T12:00:00+00:00"},
        {"id": "l3", "item_id": "it1", "platform": "marktplaats", "status": "active",
         "listed_at": "2026-09-01T08:34:00+00:00"},
        {"id": "l4", "item_id": "it1", "platform": "vinted", "status": "active",
         "listed_at": "2026-06-01T00:00:00+00:00"},
    ]
    db = _DB([{"id": "it1", "user_id": "u1"}], listings)
    monkeypatch.setattr(cl, "get_db", lambda: db)

    import asyncio
    # Alleen het boeken zelf beproeven. Wat daarna komt — het opruimen van de
    # andere kanalen — heeft een veel rijkere database nodig en heeft zijn eigen
    # proeven; hier stopt het op de nagebootste bouwer (in_, order of single).
    try:
        asyncio.run(cl.handle_item_sold("it1", "marktplaats"))
    except AttributeError as e:
        assert any(w in str(e) for w in ("in_", "order", "single")), f"onverwachte fout: {e}"

    verkocht = [l for l in listings if l["status"] == "sold"]
    assert len(verkocht) == 1, f"{len(verkocht)} rijen op 'verkocht' — dat is {len(verkocht)}x omzet"
    assert verkocht[0]["id"] == "l3", "de verkoop hoort bij de advertentie die op dat moment leefde"
    assert listings[0]["status"] == "delisted" and listings[1]["status"] == "delisted"
    assert listings[3]["platform"] == "vinted" and listings[3]["status"] != "sold"
