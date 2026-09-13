"""Een zoekertje op 2dehands gaat in de rubriek die de verkoper op Marktplaats koos.

WAT ER GEBEURDE (12-09-2026, Egbert Brouwer / Papa's Plectrums). "Ik heb vandaag
geprobeerd er 35 online te zetten, daar zijn er 34 niet van gelukt." Gemeten in
zijn opdrachten: 34 miniatuurgitaartjes, 4 mislukt en 30 teruggenomen, allemaal
op "2dehands charges for adverts in Muziek snaarinstrumenten gitaren ...".

Op Marktplaats staan precies die artikelen in Verzamelen | Muziek, Artiesten en
Beroemdheden (895/926), door hemzelf zo geplaatst. Onze import had "gitaren
elektrisch" uit de titel geraden, en 2dehands vraagt in gitaarrubrieken geld na
twee gratis zoekertjes. Van zijn 5.533 artikelen had er maar 947 bij ons dezelfde
rubriek als op Marktplaats.

Deze proef gebruikt zijn ECHTE opdracht d7e1fc68 en het ECHTE antwoord van de
Marktplaats-zoekfunctie (13-09-2026), en draait de uitgifte twee keer: zoals hij
nu is en zoals hij was op commit 09583430.
"""
import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402
import backend.services.mp_enrich as M  # noqa: E402

VOOR_DE_REPARATIE = "09583430"   # vast nummer: HEAD vergelijkt zichzelf na de commit
USER = "bcdf9aa4-314d-49a2-9573-8818ad61073d"
GITAREN = "muziek snaarinstrumenten gitaren elektrisch"
TITEL = "Miniatuur replica Gibson SG gitaar - Angus Young - AC/DC"
NUMMER = "1524927672"            # zijn Marktplaats-advertentie van dit artikel

# Letterlijk (ingekort tot de gebruikte velden) van
# /lrp/api/search?query=<TITEL>&sellerIds[]=6999351, 13-09-2026.
ECHT_ANTWOORD = {
    "listings": [
        {"itemId": "a1524927672", "title": TITEL, "categoryId": 926},
        {"itemId": "a1524781692", "title": "Baby miniatuur replica Gibson SG gitaar -Angus Young - AC/DC",
         "categoryId": 926},
    ],
    "facets": [{"key": "RelevantCategories", "categories": [
        {"id": 895, "label": "Verzamelen", "parentId": None},
        {"id": 926, "label": "Muziek, Artiesten en Beroemdheden", "parentId": 895},
    ]}],
}


class _Antwoord:
    def __init__(self, data, fout=False):
        self._data, self._fout = data, fout

    def raise_for_status(self):
        if self._fout:
            raise RuntimeError("503")

    def json(self):
        return self._data


class _Client:
    def __init__(self, data=ECHT_ANTWOORD, fout=False):
        self.data, self.fout, self.vragen = data, fout, []

    async def get(self, url, params=None, headers=None):
        self.vragen.append(params)
        return _Antwoord(self.data, self.fout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def _zet_marktplaats_nep(monkeypatch, client):
    async def verkoper(*_a, **_kw):
        return 6999351
    monkeypatch.setattr(M, "_verkopersnummer", verkoper)
    monkeypatch.setattr(M.httpx, "AsyncClient", lambda *a, **kw: client)


# ── een database met net genoeg om de uitgifte te laten draaien ──────────────
class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.wijziging = db, tabel, {}, None

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def in_(self, k, v):
        self.f[k] = list(v)
        return self

    @property
    def not_(self):
        return self

    def __getattr__(self, _n):
        return lambda *_a, **_kw: self

    def execute(self):
        return type("R", (), {"data": self.db.antwoord(self)})()


class _DB:
    def __init__(self, jobs, op_marktplaats=None, geschiedenis=None):
        self.jobs = jobs
        self.op_marktplaats = op_marktplaats or {}      # item_id -> advertentienummer
        self.geschiedenis = geschiedenis or []
        self.updates = []

    def table(self, naam):
        return _Vraag(self, naam)

    def antwoord(self, v):
        if v.wijziging is not None:
            self.updates.append((v.tabel, dict(v.f), v.wijziging))
            return []
        if v.tabel == "listings" and v.f.get("platform") == "marktplaats":
            ids = v.f.get("item_id")
            ids = ids if isinstance(ids, list) else [ids]
            return [{"item_id": i, "platform_listing_id": self.op_marktplaats[i],
                     "items": {"title": TITEL}} for i in ids if i in self.op_marktplaats]
        if v.tabel == "jobs" and v.f.get("status") == "pending":
            return [j for j in self.jobs if j["status"] == "pending"
                    and j["platform"] == v.f.get("platform", j["platform"])]
        if v.tabel == "jobs" and isinstance(v.f.get("status"), list) and "done" in v.f["status"]:
            return self.geschiedenis
        return []


def _echte_opdracht(jid="d7e1fc68-6d09-4887-8616-336d3611640b", item="f47f50da-a1ee-498a-b531-b93a290e0e22"):
    """Opdracht d7e1fc68 van 12-09-2026, zoals hij in de wachtrij stond."""
    return {"id": jid, "user_id": USER, "item_id": item, "platform": "2dehands",
            "action": "create", "status": "pending", "scheduled_for": None, "claimed_at": None,
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "payload": {"title": TITEL, "category": GITAREN, "price": 17.95, "_taal": "nl",
                        "description": "Miniatuur replica van de Gibson SG van Angus Young."}}


def _oude_jobs():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_zet_rubriek_van_marktplaats" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_rubriek", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _extensie_opent(item: dict) -> str:
    """Welk formulier de extensie opent: getMpSyiUrl, letterlijk uit background.js."""
    spec = importlib.util.spec_from_file_location("mpv", ROOT / "tests" / "test_marktplaats_verversen.py")
    mpv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mpv)
    if mpv.NODE is None:
        pytest.skip("node is niet geïnstalleerd")
    driver = f"{mpv._mp_url_js()}\nconsole.log(getMpSyiUrl('2dehands', {json.dumps(item)}));"
    r = subprocess.run([mpv.NODE, "-e", driver], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _uitgifte(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    for naam in ("_record_extension_heartbeat", "_recover_stale_claims"):
        if hasattr(module, naam):
            monkeypatch.setattr(module, naam, lambda *a, **kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(module, "_zet_taal_goed", lambda _db, rijen: rijen)
    return module.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.320"}})(),
        platform="2dehands", user_id=USER)


# ── de proeven ───────────────────────────────────────────────────────────────
def test_de_rubriek_komt_van_het_advertentienummer_niet_van_een_gelijkende_titel():
    client = _Client()
    uit = asyncio.run(M.rubriek_op_advertentienummer(client, 6999351, TITEL, NUMMER))
    assert uit == {"l1": 895, "l1_naam": "Verzamelen",
                   "l2": 926, "l2_naam": "Muziek, Artiesten en Beroemdheden"}
    assert client.vragen[0]["sellerIds[]"] == 6999351
    # Een nummer dat er niet tussen staat: gezocht, niets zeker, dus leeg.
    assert asyncio.run(M.rubriek_op_advertentienummer(_Client(), 6999351, TITEL, "111")) == {}
    # Marktplaats onbereikbaar: geen antwoord, en dat is iets anders dan leeg.
    assert asyncio.run(M.rubriek_op_advertentienummer(_Client(fout=True), 6999351, TITEL, NUMMER)) is None


def test_egberts_gitaartje_gaat_nu_naar_verzamelen_en_vroeger_naar_de_betaalde_gitaren(monkeypatch):
    """Voor-en-na op de echte uitgifte, tot en met het adres dat de extensie opent."""
    _zet_marktplaats_nep(monkeypatch, _Client())
    nu_db = _DB([_echte_opdracht()], op_marktplaats={"f47f50da-a1ee-498a-b531-b93a290e0e22": NUMMER})
    nu = _uitgifte(J, monkeypatch, nu_db)
    assert len(nu) == 1
    assert nu[0]["payload"]["mp_category"]["l2"] == 926
    assert _extensie_opent(nu[0]["payload"]) == "https://www.2dehands.be/plaats/895/926?title="
    assert any(t == "jobs" and "mp_category" in (w.get("payload") or {})
               for t, _f, w in nu_db.updates), "de rubriek moet ook in de opdracht zelf komen te staan"

    oud = _oude_jobs()
    oud_db = _DB([_echte_opdracht()], op_marktplaats={"f47f50da-a1ee-498a-b531-b93a290e0e22": NUMMER})
    vroeger = _uitgifte(oud, monkeypatch, oud_db)
    assert len(vroeger) == 1 and "mp_category" not in vroeger[0]["payload"]
    # /plaats/728/748 is letterlijk het adres uit zijn foutmelding ("Naar betalen").
    assert _extensie_opent(vroeger[0]["payload"]) == "https://www.2dehands.be/plaats/728/748?title="


def test_een_storing_bij_marktplaats_houdt_de_opdracht_even_vast_maar_niet_voor_altijd(monkeypatch):
    _zet_marktplaats_nep(monkeypatch, _Client(fout=True))
    job = _echte_opdracht()
    db = _DB([job], op_marktplaats={job["item_id"]: NUMMER})
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is False
    assert job["payload"].get("_rubriek_zoeken_sinds")
    job["payload"]["_rubriek_zoeken_sinds"] = (
        datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat()
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is True, (
        "na twintig minuten moet hij alsnog de deur uit, anders staat de rij stil")


def test_niet_op_marktplaats_of_een_marktplaats_opdracht_blijft_zoals_hij_was(monkeypatch):
    _zet_marktplaats_nep(monkeypatch, _Client())
    los = _echte_opdracht()
    assert J._zet_rubriek_van_marktplaats(_DB([los]), USER, los) is True
    assert "mp_category" not in los["payload"]
    mp = {**_echte_opdracht(), "platform": "marktplaats"}
    assert J._zet_rubriek_van_marktplaats(_DB([mp], {mp["item_id"]: NUMMER}), USER, mp) is True
    assert "mp_category" not in mp["payload"]


def test_de_rem_op_gitaren_neemt_de_miniaturen_die_op_marktplaats_staan_niet_meer_mee(monkeypatch):
    rij = [dict(_echte_opdracht(f"g{i}", f"i{i}")) for i in range(5)]
    op_mp = {"i0": "1", "i1": "2", "i2": "3"}          # drie staan op Marktplaats

    db = _DB(rij, op_marktplaats=op_mp)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    assert J._stop_wachtrij(db, USER, "2dehands", "reden", rubriek=GITAREN) == 2

    oud = _oude_jobs()
    oud_db = _DB([dict(_echte_opdracht(f"g{i}", f"i{i}")) for i in range(5)], op_marktplaats=op_mp)
    monkeypatch.setattr(oud, "execute_with_retry", lambda q, *a, **k: q.execute())
    assert oud._stop_wachtrij(oud_db, USER, "2dehands", "reden", rubriek=GITAREN) == 5, (
        "de oude rem nam ook de miniaturen terug die in Verzamelen gratis kunnen")


def test_een_rubriek_die_al_geld_kostte_gaat_niet_opnieuw_de_deur_uit(monkeypatch):
    """Zijn 12-09: 8 van de 34 werden ná de rem aangemaakt en liepen er opnieuw op."""
    betaald = {"status": "error", "category": GITAREN, "mp_category": None,
               "result": {"error": J._melding_rubriek_vraagt_geld("2dehands", "Gitaren")}}
    gelukt = {"status": "done", "category": GITAREN, "mp_category": None, "result": {}}
    rubriek = GITAREN

    assert J._betaalde_rubriek_bekend(_DB([], geschiedenis=[betaald, gelukt, gelukt]), USER, "2dehands", rubriek)
    assert not J._betaalde_rubriek_bekend(_DB([], geschiedenis=[gelukt, betaald]), USER, "2dehands", rubriek), (
        "een geslaagde plaatsing daarna betekent dat er weer een gratis plek is")
    assert not J._betaalde_rubriek_bekend(_DB([], geschiedenis=[betaald]), USER, "2dehands", "mp:895/926"), (
        "een betalende gitaarrubriek zegt niets over Verzamelen")

    job = _echte_opdracht()
    db = _DB([job], geschiedenis=[betaald])
    assert J._weiger_bekende_betaalde_rubriek(db, USER, job) is True
    assert any(t == "jobs" and w.get("status") == "cancelled" for t, _f, w in db.updates)
    herplaatsing = {**_echte_opdracht(), "payload": {**_echte_opdracht()["payload"], "_refresh_rollback": {"x": 1}}}
    assert J._weiger_bekende_betaalde_rubriek(_DB([], geschiedenis=[betaald]), USER, herplaatsing) is False
