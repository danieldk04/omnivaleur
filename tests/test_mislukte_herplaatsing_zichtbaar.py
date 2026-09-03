"""Een mislukte herplaatsing mag niet stil zijn.

WAAROM DIT ER IS (03-09-2026, Amanda Haas). Zij mailde: "Als ik dan een melding
krijg dat er een nieuwe advertentie wordt geplaatst, dan zie ik vervolgens niks
in het overzicht bij mp, terwijl hij wel aangeeft een nieuwe advertentie te
hebben geplaatst."

Herplaatsen is twee stappen: eerst weg bij Marktplaats, dan opnieuw plaatsen.
Struikelde die tweede stap, dan schreef de server dat NERGENS op. De regel die
een mislukte publicatie vastlegt raakt namelijk alleen een advertentierij die op
'pending' staat, en dat is een eerste publicatie; bij een herplaatsing staat de
oude rij op 'delisted'. Gevolg: het artikel had geen advertentie meer, geen
foutmelding, geen rood bolletje. Gemeten in haar gegevens op 03-09-2026: elf
artikelen in precies die stille toestand.

Elke proef hieronder laat de oude regel er ook op vallen.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.tot, self.vanaf = {}, None, None
        self.op, self.velden = None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def lte(self, k, v): self.tot = (k, v); return self
    def gte(self, k, v): self.vanaf = (k, v); return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self

    def execute(self):
        bron = self.db.listings if self.tabel == "listings" else self.db.jobs
        rijen = [r for r in bron if all(r.get(k) == v for k, v in self.filters.items())]
        if self.tot:
            k, v = self.tot
            rijen = [r for r in rijen if str(r.get(k) or "") <= str(v)]
        if self.vanaf:
            k, v = self.vanaf
            rijen = [r for r in rijen if str(r.get(k) or "") >= str(v)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
                self.db.bijgewerkt.append(r["id"])
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, listings, jobs=None):
        self.listings, self.jobs, self.bijgewerkt = listings, jobs or [], []

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture(autouse=True)
def _geen_echte_database(monkeypatch):
    monkeypatch.setattr(api, "execute_with_retry", lambda q, *a, **k: q.execute())
    # Het terugdraaien van de verversbeurt praat met de ECHTE database. Hier
    # alleen tellen dat het gebeurt.
    from backend.services import relist as relist_mod
    teruggedraaid = []
    monkeypatch.setattr(relist_mod, "rollback_refresh",
                        lambda rb, uid: teruggedraaid.append((rb, uid)))
    return teruggedraaid


def _tijd(minuten_geleden):
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten_geleden)).isoformat()


def _plaatsopdracht():
    return {"id": "create-1", "user_id": "u1", "item_id": "it1",
            "platform": "marktplaats", "action": "create", "created_at": _tijd(10)}


def _verwijderopdracht(status="done", rij_id="nieuw"):
    return {"id": "delete-1", "user_id": "u1", "item_id": "it1",
            "platform": "marktplaats", "action": "delete", "status": status,
            "created_at": _tijd(20),
            "payload": {"_refresh_rollback": {"listing_id": rij_id}}}


FOUT = ("Error: Not published — complete the fields marked in red and click publish "
        "yourself. € | Geen prijs ingevuld.")


def _oude_regel(db):
    """Wat de server tot 03-09-2026 deed bij een mislukte publicatie."""
    return api.execute_with_retry(
        db.table("listings").update({"status": "error", "error_message": FOUT})
        .eq("item_id", "it1").eq("platform", "marktplaats").eq("status", "pending"))


def test_de_oude_regel_liet_een_herplaatsing_stil():
    db = _DB([{"id": "nieuw", "item_id": "it1", "platform": "marktplaats",
               "status": "delisted", "error_message": None}],
             [_verwijderopdracht()])
    _oude_regel(db)
    assert db.listings[0]["status"] == "delisted"
    assert db.listings[0]["error_message"] is None, "precies het gat: geen advertentie én geen uitleg"


def test_nu_staat_er_wel_iets():
    db = _DB([{"id": "nieuw", "item_id": "it1", "platform": "marktplaats",
               "status": "delisted", "error_message": None}],
             [_verwijderopdracht()])
    geraakt = api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT)
    assert geraakt == 1
    rij = db.listings[0]
    assert rij["status"] == "error", "alleen 'error' laat het scherm een rode melding tekenen"
    assert "Geen prijs ingevuld" in rij["error_message"]
    assert "already removed" in rij["error_message"], "de verkoper moet weten dat de oude weg is"


def test_alleen_de_advertentie_van_deze_herplaatsing():
    """Een artikel heeft na een paar rondes meerdere rijen; de oude zijn archief."""
    db = _DB([
        {"id": "oud", "item_id": "it1", "platform": "marktplaats", "status": "delisted"},
        {"id": "nieuw", "item_id": "it1", "platform": "marktplaats", "status": "delisted"},
    ], [_verwijderopdracht(rij_id="nieuw")])
    api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT)
    assert db.listings[0]["status"] == "delisted", "de archiefrij blijft met rust"
    assert db.listings[1]["status"] == "error"


def test_een_verkocht_artikel_blijft_verkocht():
    db = _DB([{"id": "nieuw", "item_id": "it1", "platform": "marktplaats", "status": "sold"}],
             [_verwijderopdracht()])
    assert api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT) == 0
    assert db.listings[0]["status"] == "sold"


def test_een_advertentie_die_nog_live_staat_blijft_live():
    """Mislukte verwijdering: de advertentie staat er nog, dus dit is geen gat."""
    db = _DB([{"id": "nieuw", "item_id": "it1", "platform": "marktplaats", "status": "active"}],
             [_verwijderopdracht()])
    assert api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT) == 0
    assert db.listings[0]["status"] == "active"


def test_geen_herplaatsing_dan_verandert_er_niets():
    """Een eerste publicatie heeft geen verwijderopdracht; die weg blijft zoals hij was."""
    db = _DB([{"id": "rij", "item_id": "it1", "platform": "marktplaats", "status": "delisted"}], [])
    assert api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT) == 0
    assert db.listings[0]["status"] == "delisted"


def test_een_mislukte_verwijdering_telt_niet_als_herplaatsing():
    db = _DB([{"id": "rij", "item_id": "it1", "platform": "marktplaats", "status": "delisted"}],
             [_verwijderopdracht(status="error")])
    assert api._meld_mislukte_herplaatsing(db, "u1", _plaatsopdracht(), FOUT) == 0


def test_de_mislukte_publicatie_roept_dit_ook_echt_aan():
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    kop = bron.index('if job and job["action"] == "create":', bron.index("def fail_job"))
    staart = bron.index('elif job and job["action"] == "delete":', kop)
    assert "_meld_mislukte_herplaatsing" in bron[kop:staart]


# ── En liever nog: een verwijdering die niet terug kan komen, gaat niet door ──
#
# De reparatie voor "geen vraagprijs, maar bieden" zit in de extensie, en die
# bereikt een verkoper pas nadat de Chrome Web Store hem heeft goedgekeurd — bij
# een eerdere klant duurde dat drie weken. Tot die tijd zou elke nacht opnieuw
# een advertentie verdwijnen. Daarom staat de rem ook op de server.

def _plaatsing_in_de_wachtrij(prijs, platform="marktplaats"):
    return {"id": "create-1", "user_id": "u1", "item_id": "it1", "platform": platform,
            "action": "create", "status": "pending", "created_at": _tijd(19),
            "payload": {"price": prijs}}


def _verwijdering(platform="marktplaats"):
    j = _verwijderopdracht()
    j["platform"] = platform
    return j


def test_zonder_vraagprijs_en_een_oude_kopie_gaat_de_verwijdering_niet_door():
    db = _DB([], [_plaatsing_in_de_wachtrij(0)])
    reden = api._herplaatsing_kansloos(db, "u1", _verwijdering(), (1, 0, 281))
    assert reden and "Bieden" in reden and "still live" in reden


def test_met_de_bijgewerkte_kopie_loopt_alles_gewoon_door():
    db = _DB([], [_plaatsing_in_de_wachtrij(0)])
    assert api._herplaatsing_kansloos(db, "u1", _verwijdering(), api.KAN_BIEDEN_VANAF) is None


def test_een_onbekende_versie_telt_als_oud():
    """Kopieën van vóór 1.0.250 sturen hun versie niet mee — die kunnen dit zeker niet."""
    db = _DB([], [_plaatsing_in_de_wachtrij(None)])
    assert api._herplaatsing_kansloos(db, "u1", _verwijdering(), None) is not None


def test_een_artikel_met_prijs_wordt_nooit_geremd():
    db = _DB([], [_plaatsing_in_de_wachtrij(12.5)])
    assert api._herplaatsing_kansloos(db, "u1", _verwijdering(), (1, 0, 281)) is None


def test_vinted_valt_hier_buiten():
    db = _DB([], [_plaatsing_in_de_wachtrij(0, platform="vinted")])
    assert api._herplaatsing_kansloos(db, "u1", _verwijdering("vinted"), (1, 0, 281)) is None


def test_een_losse_verwijdering_is_geen_herplaatsing():
    db = _DB([], [])
    assert api._herplaatsing_kansloos(db, "u1", _verwijdering(), (1, 0, 281)) is None


def test_terugnemen_laat_de_advertentie_staan_en_zegt_waarom(_geen_echte_database):
    plaatsing = _plaatsing_in_de_wachtrij(0)
    verwijdering = _verwijdering()
    db = _DB([{"id": "nieuw", "item_id": "it1", "platform": "marktplaats",
               "status": "relisting", "error_message": None}],
             [plaatsing, verwijdering])
    reden = api._herplaatsing_kansloos(db, "u1", verwijdering, (1, 0, 281))
    api._neem_herplaatsing_terug(db, verwijdering, _tijd(0), reden)
    assert plaatsing["status"] == "cancelled", "de plaatsing die toch zou mislukken gaat weg"
    assert verwijdering["status"] == "cancelled", "en de verwijdering dus ook"
    rij = db.listings[0]
    assert rij["status"] == "active", "de advertentie staat er nog: hij is nooit weggehaald"
    assert "no asking price" in rij["error_message"]
    # Het scherm tekent hier een "Relist failed — still live"-melding mét een
    # opnieuw-knop; die herkent hij aan deze woorden.
    assert "still live" in rij["error_message"]
    assert _geen_echte_database, "de verversbeurt en het dagquotum gaan terug: er is niets ververst"


def test_de_uitdeellus_roept_de_rem_ook_echt_aan():
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    lus = bron[bron.index("    ready = []"):bron.index("    # A relist's \"create\" job can sit queued")]
    assert "_herplaatsing_kansloos" in lus and "_neem_herplaatsing_terug" in lus


def test_de_rem_geldt_alleen_bij_een_echte_poll_van_de_extensie():
    """Het dashboard telt hier alleen opdrachten en stuurt geen platform mee; dan
    weten we niet welke kopie er draait. Op dat niet-weten mag geen herplaatsing
    sneuvelen — anders zou het openstaande scherm van de verkoper zijn eigen
    verversingen afbreken."""
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    lus = bron[bron.index("    ready = []"):bron.index("    # A relist's \"create\" job can sit queued")]
    regels = lus.splitlines()
    i = next(n for n, r in enumerate(regels) if "_herplaatsing_kansloos" in r)
    assert "platform is not None" in regels[i - 1], regels[i - 1]
