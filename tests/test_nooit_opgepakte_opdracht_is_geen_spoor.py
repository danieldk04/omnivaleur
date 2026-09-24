"""Een plaatsopdracht die de extensie nooit oppakte, bewijst niet dat iets online staat.

WAAROM DIT ER IS (23-09-2026, Johan Kist / Blackbird Guitars, klant f8c0cce9)

Zijn 2dehands-opdrachten wachtten op de rubriek (die wachttijd is 24-09 om 14:14
gerepareerd). Het icoon stond oranje. Hij klikte erop bij een Gibson Les Paul
Junior Pro (19:16) en een Magrabo-gitaarband (21:10) en bevestigde "Mark it as
listed anyway?". De server vond de open opdracht een spoor van een plaatsing en
zette beide op actief, terwijl de extensie ze nooit had opgepakt (claimed_at
leeg). Op zijn 2dehands-account (28 advertenties) staat geen van beide.

Gevolg op 24-09: zijn verversing van de Les Paul verwijderde eerst op 2dehands,
vond niets ("cannot be found in your 2dehands listings overview, and we could not
verify whether it is still online") en het opnieuw plaatsen werd overgeslagen.

Draaien: python3 -m pytest tests/test_nooit_opgepakte_opdracht_is_geen_spoor.py
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_kanaalicoon_is_geen_publiceren import _DB, _nieuw, api, scans  # noqa: E402,F401

# De stand vlak vóór deze reparatie, als vast nummer (niet HEAD: de
# auto-push-hook commit werk in uitvoering).
OUDE_COMMIT = "efabbbbd"

LES_PAUL = "b182ad4a"


def _johan_23_09(opdracht_status="pending", claimed_at=None, result=None):
    """Zijn Les Paul om 19:16: live op Marktplaats, 2dehands-rij 'pending', de
    plaatsopdracht wacht op de rubriek en is nooit opgepakt."""
    return _DB(
        items=[{"id": LES_PAUL, "user_id": "johan"}],
        listings=[
            {"id": "mp", "item_id": LES_PAUL, "platform": "marktplaats",
             "status": "active", "platform_listing_id": "1531411541"},
            {"id": "b2e66897", "item_id": LES_PAUL, "platform": "2dehands",
             "status": "pending", "platform_listing_id": None},
        ],
        jobs=[{"id": "642da9c5", "user_id": "johan", "item_id": LES_PAUL, "platform": "2dehands",
               "action": "create", "status": opdracht_status, "claimed_at": claimed_at,
               "result": result}],
    )


def _oud(db, body):
    """De echte oude functie uit git, in de echte module-omgeving van nu."""
    bron = subprocess.run(["git", "show", f"{OUDE_COMMIT}:backend/api/listings.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    stuk = re.search(r"\ndef mark_listing_active\(.*?(?=\n@router)", bron, re.S)
    assert stuk, "de oude functie staat niet in die commit"
    ruimte = {**vars(api), "get_db": lambda: db, "Depends": lambda _f: None}
    exec(compile(stuk.group(0), "<oud>", "exec"), ruimte)
    return ruimte["mark_listing_active"](body, user_id="johan")


def _tweedehands(db):
    return next(r for r in db.tabellen["listings"] if r["platform"] == "2dehands")


def test_voor_zette_de_oude_code_hem_op_actief_zonder_advertentie(scans):
    db = _johan_23_09()
    uit = _oud(db, {"item_id": LES_PAUL, "platform": "2dehands"})
    assert uit["ok"]
    rij = _tweedehands(db)
    assert rij["status"] == "active" and not rij["platform_listing_id"]
    assert db.tabellen["jobs"][0]["result"] == {"manual": "marked active by user"}


def test_na_weigert_de_server_en_blijft_de_opdracht_staan(monkeypatch, scans):
    db = _johan_23_09()
    with pytest.raises(api.HTTPException) as e:
        _nieuw(monkeypatch, db, {"item_id": LES_PAUL, "platform": "2dehands"})
    assert e.value.status_code == 422
    assert "hasn't started" in e.value.detail and "2dehands" in e.value.detail
    assert _tweedehands(db)["status"] == "pending"
    assert db.tabellen["jobs"][0]["status"] == "pending"   # gaat gewoon nog uit
    assert scans == []


@pytest.mark.parametrize("status,claimed_at,result", [
    ("claimed", "2026-09-23T19:05:00+00:00", None),                  # loopt nu
    ("pending", "2026-09-23T19:05:00+00:00", None),                  # liep al eens
    ("pending", None, {"_progress": {"stap": "formulier ingevuld"}}),  # meldde voortgang
])
def test_een_opdracht_die_echt_liep_mag_nog_steeds_afgesloten(monkeypatch, scans,
                                                               status, claimed_at, result):
    """De oranje stip blijft werken waar hij voor is: de extensie plaatste, maar
    kon het niet bevestigen."""
    db = _johan_23_09(status, claimed_at, result)
    uit = _nieuw(monkeypatch, db, {"item_id": LES_PAUL, "platform": "2dehands"})
    assert uit["ok"] and _tweedehands(db)["status"] == "active"
    assert db.tabellen["jobs"][0]["status"] == "done"


def test_met_link_mag_het_altijd(monkeypatch, scans):
    """Zelf op 2dehands gezet? Dan is de link het bewijs."""
    db = _johan_23_09()
    uit = _nieuw(monkeypatch, db, {"item_id": LES_PAUL, "platform": "2dehands",
                                   "platform_listing_url": "https://www.2dehands.be/v/x/m2446999999-gibson"})
    assert uit["linked"] and _tweedehands(db)["platform_listing_id"] == "m2446999999"
