"""Een geslaagde Facebook-publicatie werd altijd rood, een mislukte zag er hetzelfde uit.

GEMETEN 17-09-2026, Johan Kist. Acht Facebook-opdrachten op "done", alle acht met
"Extension completed job but returned no platform_listing_id" op de rij. Facebook
geeft na publiceren nooit een nummer (de advertentie staat eerst in beoordeling),
dus dat rood kwam er bij élke publicatie. En de extensie meldde tot 1.0.338 ook
"klaar" als Facebook op het formulier bleef staan, dus de server kon het verschil
niet zien. Zie tests/facebook-bevestiging-test.js voor de extensiekant.

Hier: met `bevestigd` (extensie 1.0.338 en later) wordt de rij groen, zonder
bevestiging blijft hij rood maar met een melding waar de verkoper iets mee kan.
De oude versie van de server (VOOR_DE_REPARATIE) draait mee als tegenbewijs.
"""
import asyncio
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as nieuw  # noqa: E402

VOOR_DE_REPARATIE = "48a9c4b9"


def _oude_module():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"], cwd=ROOT)
    mod = types.ModuleType("jobs_voor_de_reparatie")
    exec(compile(bron, "jobs_voor.py", "exec"), mod.__dict__)
    return mod


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.op, self.velden, self.filters = db, tabel, None, None, {}

    def select(self, *_a):
        self.op = "select"; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def is_(self, k, v):
        self.filters[k] = None; return self

    def execute(self):
        rijen = [r for r in self.db.rijen if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return types.SimpleNamespace(data=[dict(r) for r in rijen])


class _DB:
    def __init__(self, rijen):
        self.rijen = rijen

    def table(self, naam):
        return _Q(self, naam)


def _afronden(module, platform, body):
    db = _DB([{"id": "rij1", "item_id": "i1", "platform": platform, "platform_listing_id": None,
               "status": "pending", "error_message": None}])
    job = {"id": "j1", "item_id": "i1", "platform": platform, "action": "create"}
    asyncio.run(module._rond_publicatie_af(db, job, body))
    return db.rijen[0]


def test_bevestigde_facebook_publicatie_wordt_groen_en_was_rood():
    body = {"platform_listing_id": None, "platform_listing_url": nieuw.FB_EIGEN_ADVERTENTIES,
            "bevestigd": "jouw-advertenties"}
    oud = _afronden(_oude_module(), "facebook", body)
    assert oud["status"] == "error"                       # tegenbewijs: zo zag Johan het
    rij = _afronden(nieuw, "facebook", body)
    assert rij["status"] == "active"
    assert rij["error_message"] is None
    assert rij["platform_listing_url"] == nieuw.FB_EIGEN_ADVERTENTIES


def test_onbevestigde_facebook_publicatie_blijft_rood_met_bruikbare_melding():
    rij = _afronden(nieuw, "facebook", {"platform_listing_id": None, "platform_listing_url": None})
    assert rij["status"] == "error"
    assert "Your listings" in rij["error_message"] and "It is online" in rij["error_message"]


def test_andere_kanalen_blijven_zoals_ze_waren():
    # `bevestigd` zonder nummer telt alleen op Facebook; op Vinted is geen nummer echt fout.
    rij = _afronden(nieuw, "vinted", {"platform_listing_id": None, "bevestigd": "jouw-advertenties"})
    assert rij["status"] == "error"
    assert rij["error_message"] == "Extension completed job but returned no platform_listing_id"
