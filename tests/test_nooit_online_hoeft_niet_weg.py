"""Een advertentie die nooit online kwam, krijgt bij een verkoop geen verwijderopdracht.

WAAROM DIT ER IS (23-09-2026, Toon, schapenvachten). Verkocht op Vinted, daarna
drie keer een mislukte 2dehands-verwijdering ("check it by hand") voor een
advertentie die nooit had bestaan: de plaatsing was op 20-09 teruggenomen omdat
de rubriek geld kostte. Daniel: zo'n rij mag stil vervallen.

Maar alleen als elke plaatsingspoging zelf zei dat er niets online ging. Een
ontbrekend advertentienummer alleen is geen bewijs.
"""
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402
from tests.test_verkoopkanaal_moet_bewezen_zijn import _DB  # noqa: E402

VOOR = "1bcf8092"
BETAALMUUR = ('2dehands (2dehands.be) charges for adverts in "Wonen tapijten en kleden": '
              "the site says this is a paid category. Nothing was published.")
TWIJFEL = ("The tab this 2dehands job was working in was closed before it finished. "
           "Nothing was published (or it wasn't confirmed) — check the platform.")


def _situatie(fout):
    items = [{"id": "i1", "user_id": "u1", "title": "2stuks schapenvachten"}]
    listings = [
        {"id": "v1", "item_id": "i1", "platform": "vinted", "status": "active",
         "platform_listing_id": "10051662805"},
        {"id": "t1", "item_id": "i1", "platform": "2dehands", "status": "error",
         "platform_listing_id": None, "listed_at": None},
    ]
    db = _DB(items, listings)
    db.rest.append({"item_id": "i1", "platform": "2dehands", "action": "create",
                    "status": "cancelled", "result": {"error": fout}})
    return db, listings


def _verkoop(module, monkeypatch, db):
    verwijderd = []
    monkeypatch.setattr(module, "get_db", lambda: db)

    async def _naast(fn, *_a, **_k):
        return fn()

    monkeypatch.setattr(module, "naast_de_lus", _naast)
    monkeypatch.setattr(module, "_enqueue_extension_delete",
                        lambda _db, _u, item_id, listing, _row: verwijderd.append(listing["platform"]))
    try:
        asyncio.run(module.handle_item_sold("i1", "vinted", bewijs=module.BEWIJS_BESTELLING))
    except AttributeError as e:          # de nagebootste bouwer stopt bij het opruimen
        assert any(w in str(e) for w in ("in_", "order", "single")), f"onverwachte fout: {e}"
    return verwijderd


def test_teruggenomen_plaatsing_vervalt_stil(monkeypatch):
    db, listings = _situatie(BETAALMUUR)
    assert _verkoop(cl, monkeypatch, db) == [], "er stond nooit iets online, dus niets te verwijderen"
    assert listings[1]["status"] == "delisted"

    oud = _oude_crosslist()
    db2, _ = _situatie(BETAALMUUR)
    assert _verkoop(oud, monkeypatch, db2) == ["2dehands"], (
        "de oude versie stuurde er toch een verwijderopdracht op af")


def test_twijfel_wordt_nog_steeds_verwijderd(monkeypatch):
    db, listings = _situatie(TWIJFEL)
    assert _verkoop(cl, monkeypatch, db) == ["2dehands"], (
        "'or it wasn't confirmed' kan live staan, dus die gaat gewoon weg")


def test_met_advertentienummer_altijd_verwijderen(monkeypatch):
    db, listings = _situatie(BETAALMUUR)
    listings[1]["platform_listing_id"] = "m2443963620"
    assert _verkoop(cl, monkeypatch, db) == ["2dehands"]


def _oude_crosslist():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/services/crosslist.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_nooit_online" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_crosslist_nooit_online.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("backend.services.oude_crosslist_nooit_online", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud
