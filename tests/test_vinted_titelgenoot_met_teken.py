"""Titelgenoten die alleen in een leesteken verschillen tellen ook mee.

WAAROM (14-10-2026, Janneke 31d28378). "Vest Dirkje maat 86" stond op Vinted;
"Vest Dirkje maat 86*" (een tweede vest) werd twee keer geweigerd met "the
advert we found there belongs to another item". De extensie vergelijkt titels
op alleen letters en cijfers, dus voor haar zijn die twee gelijk. De server
zocht titelgenoten met precies dezelfde tekst, vond de ander niet, en gaf geen
_vinted_bezet mee. De proef draait de oude functie (van vóór de reparatie)
en de nieuwe tegen dezelfde nep-database.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402
from tests.test_vinted_titelgenoot_niet_koppelen import _DB  # noqa: E402

VOOR_DE_REPARATIE = "c8b2071"


def _db():
    return _DB(
        items=[{"id": "vest1", "user_id": "u1", "title": "Vest Dirkje maat 86"},
               {"id": "vest2", "user_id": "u1", "title": "Vest Dirkje maat 86*"},
               {"id": "vreemd", "user_id": "u2", "title": "Vest Dirkje maat 86"},
               {"id": "anders", "user_id": "u1", "title": "Vest Dirkje maat 92"}],
        listings=[{"item_id": "vest1", "platform": "vinted", "platform_listing_id": "10366429698",
                   "status": "active", "created_at": "2026-10-13T18:50:57"},
                  {"item_id": "vreemd", "platform": "vinted", "platform_listing_id": "555",
                   "status": "active", "created_at": "2026-10-13T10:00:00"},
                  {"item_id": "anders", "platform": "vinted", "platform_listing_id": "777",
                   "status": "active", "created_at": "2026-10-13T11:00:00"}])


def _opdracht():
    return {"id": "j", "user_id": "u1", "item_id": "vest2", "platform": "vinted", "action": "create",
            "payload": {"title": "Vest Dirkje maat 86*"}}


def _oude_functie():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                                   cwd=ROOT, text=True)
    begin = bron.index("def _vinted_titelgenoten_meegeven(")
    eind = bron.index("\ndef ", begin + 10)
    ns = dict(vars(J))
    exec(bron[begin:eind], ns)  # noqa: S102 — eigen code uit git, alleen in de proef
    return ns["_vinted_titelgenoten_meegeven"]


def test_oud_vindt_het_vest_met_sterretje_niet():
    job = _opdracht()
    assert _oude_functie()(_db(), "u1", [job]) == 0
    assert "_vinted_bezet" not in job["payload"]


def test_nieuw_geeft_de_advertentie_van_het_andere_vest_mee():
    job = _opdracht()
    assert J._vinted_titelgenoten_meegeven(_db(), "u1", [job]) == 1
    assert job["payload"]["_vinted_bezet"] == ["10366429698"]


def test_andere_maat_en_andere_klant_tellen_niet_mee():
    job = _opdracht()
    J._vinted_titelgenoten_meegeven(_db(), "u1", [job])
    assert "777" not in job["payload"]["_vinted_bezet"]
    assert "555" not in job["payload"]["_vinted_bezet"]


def test_voornummer_telt_niet_mee():
    db = _db()
    db.tabellen["items"].append({"id": "vest3", "user_id": "u1", "title": "(1327) Vest Dirkje maat 86"})
    job = {**_opdracht(), "item_id": "vest3", "payload": {"title": "(1327) Vest Dirkje maat 86"}}
    J._vinted_titelgenoten_meegeven(db, "u1", [job])
    assert "10366429698" in job["payload"]["_vinted_bezet"]
