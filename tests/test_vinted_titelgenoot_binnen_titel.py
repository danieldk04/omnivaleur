"""Een kortere titel die binnen de onze valt is ook een titelgenoot.

WAAROM (14-10-2026, Janneke 31d28378). "Trui Lyle & Scott maat 110-116
(donkerblauw)" werd geweigerd met "the advert we found there belongs to "Trui
Lyle & Scott maat 110-116"". Na een trage plaatsing zoekt de extensie in de
kast naar een advertentie waarvan de titel de onze bevat of erin valt
(resolveCreatedVintedItem in content/vinted.js), en pakte zo de advertentie van
een andere trui. De server gaf alleen advertenties van precies gelijke titels
als bezet mee. De proef draait de oude functie (van vóór de reparatie) en de
nieuwe tegen dezelfde nep-database, met haar echte titels en nummers.
"""
import subprocess
from pathlib import Path

from backend.api import jobs as J
from tests.test_vinted_titelgenoot_niet_koppelen import _DB

ROOT = Path(__file__).resolve().parents[1]
VOOR_DE_REPARATIE = "60d0cc9a"


def _oude_functie():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                                   cwd=ROOT, text=True)
    begin = bron.index("def _vinted_titelgenoten_meegeven(")
    eind = bron.index("\ndef ", begin + 10)
    ns = dict(vars(J))
    exec(bron[begin:eind], ns)  # noqa: S102 — eigen code uit git, alleen in de proef
    return ns["_vinted_titelgenoten_meegeven"]

DONKER = "Trui Lyle & Scott maat 110-116 (donkerblauw)"


def _db():
    return _DB(
        items=[{"id": "trui1", "user_id": "u1", "title": "Trui Lyle & Scott maat 110-116"},
               {"id": "trui2", "user_id": "u1", "title": "Trui Lyle & Scott maat 110-116"},
               {"id": "donker", "user_id": "u1", "title": DONKER},
               {"id": "set", "user_id": "u1", "title": "Set Lyle & Scott maat 110-116"},
               {"id": "groter", "user_id": "u1", "title": "Trui Lyle & Scott maat 122-128"},
               {"id": "vreemd", "user_id": "u2", "title": "Trui Lyle & Scott maat 110-116"}],
        listings=[{"item_id": "trui1", "platform": "vinted", "platform_listing_id": "10380266841",
                   "status": "active", "created_at": "2026-10-14T19:48:03"},
                  {"item_id": "trui2", "platform": "vinted", "platform_listing_id": "10380316482",
                   "status": "active", "created_at": "2026-10-14T20:00:50"},
                  {"item_id": "set", "platform": "vinted", "platform_listing_id": "111",
                   "status": "active", "created_at": "2026-10-14T10:00:00"},
                  {"item_id": "groter", "platform": "vinted", "platform_listing_id": "222",
                   "status": "active", "created_at": "2026-10-14T11:00:00"},
                  {"item_id": "vreemd", "platform": "vinted", "platform_listing_id": "555",
                   "status": "active", "created_at": "2026-10-14T12:00:00"}])


def _opdracht(item="donker", titel=DONKER):
    return {"id": "j", "user_id": "u1", "item_id": item, "platform": "vinted", "action": "create",
            "payload": {"title": titel}}


def test_oud_geeft_de_kortere_titelgenoten_niet_mee():
    job = _opdracht()
    _oude_functie()(_db(), "u1", [job])
    assert "10380316482" not in (job["payload"].get("_vinted_bezet") or [])


def test_nieuw_geeft_beide_truien_mee_nieuwste_eerst():
    job = _opdracht()
    assert J._vinted_titelgenoten_meegeven(_db(), "u1", [job]) == 1
    assert job["payload"]["_vinted_bezet"] == ["10380316482", "10380266841"]


def test_andere_maat_ander_soort_en_andere_klant_tellen_niet_mee():
    job = _opdracht()
    J._vinted_titelgenoten_meegeven(_db(), "u1", [job])
    for vreemd in ("111", "222", "555"):
        assert vreemd not in job["payload"]["_vinted_bezet"]


def test_omgekeerd_de_kortere_titel_ziet_de_langere():
    db = _db()
    db.tabellen["listings"].append({"item_id": "donker", "platform": "vinted",
                                    "platform_listing_id": "999", "status": "active",
                                    "created_at": "2026-10-14T21:00:00"})
    job = _opdracht("trui1", "Trui Lyle & Scott maat 110-116")
    J._vinted_titelgenoten_meegeven(db, "u1", [job])
    assert "999" in job["payload"]["_vinted_bezet"]
