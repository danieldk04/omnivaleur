"""Delist zet geen verwijdering klaar op een kanaal waar het artikel nooit stond.

WAAROM (22-10-2026, klant c184e384). Hij klikte Delist op tientallen opladers
waarvan de plaatsing op Marktplaats en Vinted nog in de wachtrij stond. De server
annuleerde die plaatsingen en zette er in dezelfde klik tóch een verwijdering voor
klaar (de rij stond op 'pending'). Die vonden niets en kwamen terug als 136 keer
"verwijderen mislukt, kijk het zelf na". Een plaatsing die wél was opgepakt kan
halverwege iets online hebben gezet: daar blijft de verwijdering staan.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402
from tests.test_vinted_titelgenoot_niet_koppelen import _DB  # noqa: E402

VOOR_DE_REPARATIE = "af78811b"
LADER = "189fd486"


def _db(mp_opgepakt=None, vinted_status="pending"):
    return _DB(
        items=[{"id": LADER, "user_id": "u1", "title": "Dell 180W laptop oplader DA180PM111",
                "created_at": "2026-10-22T10:28:24+00:00"}],
        listings=[
            {"id": "l-mp", "item_id": LADER, "platform": "marktplaats", "status": "pending",
             "platform_listing_id": None, "platform_listing_url": None, "created_at": "2026-10-22T10:33:42+00:00"},
            {"id": "l-vi", "item_id": LADER, "platform": "vinted", "status": "pending",
             "platform_listing_id": None, "platform_listing_url": None, "created_at": "2026-10-22T10:33:43+00:00"},
            {"id": "l-2d", "item_id": LADER, "platform": "2dehands", "status": "active",
             "platform_listing_id": "m2456546121", "platform_listing_url": None, "created_at": "2026-10-22T10:46:07+00:00"},
        ],
        jobs=[
            {"id": "c-mp", "user_id": "u1", "item_id": LADER, "platform": "marktplaats", "action": "create",
             "status": "claimed" if mp_opgepakt else "pending", "claimed_at": mp_opgepakt, "result": None,
             "created_at": "2026-10-22T10:33:42+00:00", "payload": {"title": "Dell 180W laptop oplader"}},
            {"id": "c-vi", "user_id": "u1", "item_id": LADER, "platform": "vinted", "action": "create",
             "status": vinted_status, "claimed_at": None, "result": None,
             "created_at": "2026-10-22T10:33:43+00:00", "payload": {"title": "Dell 180W laptop oplader"}},
            {"id": "c-2d", "user_id": "u1", "item_id": LADER, "platform": "2dehands", "action": "create",
             "status": "done", "claimed_at": "2026-10-22T10:53:33+00:00", "result": {},
             "created_at": "2026-10-22T10:46:07+00:00", "payload": {"title": "Dell 180W laptop oplader"}},
        ],
        platform_credentials=[])


def _draai(functie, db):
    oud = cl.get_db
    cl.get_db = lambda: db
    try:
        uit = asyncio.run(functie(LADER, "u1"))
    finally:
        cl.get_db = oud
    verwijderingen = sorted(j["platform"] for j in db.tabellen["jobs"] if j["action"] == "delete")
    return verwijderingen, uit


def _oude_functie():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/services/crosslist.py"],
                                   cwd=ROOT, text=True)
    begin = bron.index("async def delist_all_platforms(")
    eind = min(bron.index("\nasync def ", begin + 10), bron.index("\ndef ", begin + 10))
    lokaal = {}
    exec(compile(bron[begin:eind], "oud_crosslist", "exec"), vars(cl), lokaal)  # noqa: S102
    return lokaal["delist_all_platforms"]


def test_oud_zette_verwijderingen_klaar_voor_wat_nooit_geplaatst_was():
    verwijderingen, _ = _draai(_oude_functie(), _db())
    assert verwijderingen == ["2dehands", "marktplaats", "vinted"]


def test_nieuw_alleen_waar_het_echt_staat():
    db = _db()
    verwijderingen, uit = _draai(cl.delist_all_platforms, db)
    assert verwijderingen == ["2dehands"]
    assert {r["platform"] for r in uit if r.get("status") == "not_published"} == {"marktplaats", "vinted"}
    # de wachtende plaatsingen gaan nog steeds niet door
    assert {j["platform"]: j["status"] for j in db.tabellen["jobs"] if j["action"] == "create"} == {
        "marktplaats": "cancelled", "vinted": "cancelled", "2dehands": "done"}


def test_tweede_klik_na_annuleren_ook_niet():
    verwijderingen, _ = _draai(cl.delist_all_platforms, _db(vinted_status="cancelled"))
    assert "vinted" not in verwijderingen


def test_opgepakte_plaatsing_kan_iets_online_gezet_hebben():
    verwijderingen, _ = _draai(cl.delist_all_platforms, _db(mp_opgepakt="2026-10-22T10:50:00+00:00"))
    assert "marktplaats" in verwijderingen
