"""Automatisch herplaatsen op 2dehands, als proef alleen voor Voordeelsieraden (20-11-2026).

Mieneke wil op 2dehands.be bovenaan blijven. Een verlenging houdt de advertentie op
zijn plek, een herplaatsing zet hem bovenaan. Alleen wie in RELIST_2DEHANDS_PROEF
staat krijgt dat; Marktplaats blijft ongewijzigd voor iedereen.
"""
import asyncio
from datetime import datetime, timezone

from backend.services import crosslist, instellingen, relist
from tests.test_herplaatsronde_ziet_alles import _DB, _advertentie

MIENEKE = "mieneke"
ANDER = "andere-verkoper"


def _draai(monkeypatch, *, vast_moment=False, moment=None, dagen_oud=30, aantal=4):
    nu = datetime.now(timezone.utc)
    paren = []
    for i in range(aantal):
        for eigenaar, basis in ((MIENEKE, 100), (ANDER, 200)):
            lst, it = _advertentie(basis + i, eigenaar, dagen_oud, nu)
            lst["platform"] = "2dehands"
            paren.append((lst, it))
    # Dezelfde artikelen staan ook op Marktplaats: die ronde mag niet veranderen.
    for i in range(3):
        lst, it = _advertentie(900 + i, ANDER, dagen_oud, nu)
        paren.append((lst, it))
    db = _DB({"listings": [p[0] for p in paren], "items": [p[1] for p in paren], "jobs": []})

    async def niets(*_a, **_k): return None
    monkeypatch.setattr(crosslist, "get_db", lambda: db)
    monkeypatch.setattr(crosslist, "_echte_datums_ophalen", niets)
    monkeypatch.setattr(crosslist, "_mag_nog_werken", lambda _u: True)
    monkeypatch.setattr(crosslist, "_dagelijkse_relist_grens", lambda _db, _u, _p="marktplaats": 25)
    monkeypatch.setattr(crosslist, "RELIST_2DEHANDS_PROEF", {MIENEKE})
    monkeypatch.setattr(instellingen, "alle_relist_dagen", lambda: {MIENEKE: 25, ANDER: 27})
    monkeypatch.setattr(instellingen, "alle_relist_momenten",
                        lambda: {MIENEKE: moment} if moment else {})
    monkeypatch.setattr(instellingen, "moment_staat_open", lambda m, _nu: True)
    monkeypatch.setattr(instellingen, "dagen_per_moment", lambda _m, _w: 1)
    monkeypatch.setattr(instellingen, "lees", lambda u: {"auto_relist": True})
    klaargezet = []

    async def opnemer(item_id, platform, user_id, strategy, **_k):
        klaargezet.append((platform, user_id))
        return {"status": "queued"}
    monkeypatch.setattr(relist, "refresh_listing", opnemer)
    fn = crosslist.relist_op_vast_moment if vast_moment else crosslist.relist_expiring_marktplaats
    asyncio.run(fn())
    return klaargezet


def test_alleen_de_proefverkoper_krijgt_herplaatsing_op_2dehands(monkeypatch):
    klaar = _draai(monkeypatch)
    assert klaar.count(("2dehands", MIENEKE)) == 4
    assert not [k for k in klaar if k[0] == "2dehands" and k[1] != MIENEKE]


def test_marktplaats_blijft_zoals_het_was(monkeypatch):
    klaar = _draai(monkeypatch)
    assert klaar.count(("marktplaats", ANDER)) == 3
    assert not [k for k in klaar if k[0] == "marktplaats" and k[1] == MIENEKE]


def test_te_jonge_advertentie_wordt_niet_herplaatst(monkeypatch):
    # Haar termijn is 25 dagen: 20 dagen oud is nog niet aan de beurt.
    assert [k for k in _draai(monkeypatch, dagen_oud=20) if k[0] == "2dehands"] == []


def test_vast_moment_geldt_ook_voor_2dehands(monkeypatch):
    moment = {"dagen": [0, 1, 2, 3, 4, 5, 6], "uur": 16}
    gewoon = _draai(monkeypatch, moment=moment)
    assert [k for k in gewoon if k[0] == "2dehands"] == []     # gewone ronde laat haar met rust
    vast = _draai(monkeypatch, vast_moment=True, moment=moment)
    assert vast == [("2dehands", MIENEKE)] * 4


def test_verlengen_laat_proefverkoper_met_rust_tot_vangnet(monkeypatch):
    import inspect
    bron = inspect.getsource(crosslist.extend_expiring_2dehands)
    assert "RELIST_2DEHANDS_PROEF" in bron and "_RELIST_2DEHANDS_VANGNET_DAGEN" in bron
