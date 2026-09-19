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
VOOR_14_SEPTEMBER = "c232f2ee"   # de versie die zijn vijftig zoekertjes annuleerde
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


def _zet_marktplaats_nep(monkeypatch, client, mod=None):
    mod = mod or M

    async def verkoper(*_a, **_kw):
        return 6999351
    monkeypatch.setattr(mod, "_verkopersnummer", verkoper)
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **kw: client)


def _verkoper_onvindbaar(monkeypatch, client, mod=None):
    """Precies wat er op 14-09-2026 om 17:07 gebeurde: wie de verkoper is was
    even niet vast te stellen. Vijftig opdrachten binnen één minuut kregen
    daardoor het stempel "staat niet op Marktplaats"."""
    mod = mod or M

    async def geen(*_a, **_kw):
        return None
    monkeypatch.setattr(mod, "_verkopersnummer", geen)
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **kw: client)


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

    def is_(self, k, v):
        self.f[f"is:{k}"] = v
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
    def __init__(self, jobs, op_marktplaats=None, geschiedenis=None, eerder=None,
                 items_titel=None):
        self.jobs = jobs
        self.items_titel = items_titel or TITEL     # de brontitel uit de voorraad
        self.op_marktplaats = op_marktplaats or {}      # item_id -> advertentienummer
        self.geschiedenis = geschiedenis or []
        self.eerder = eerder or {}                      # item_id -> eerder gevonden rubriek
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
                     "items": {"title": self.items_titel}} for i in ids if i in self.op_marktplaats]
        if v.tabel == "jobs" and v.f.get("is:payload->mp_category") == "null":
            mc = self.eerder.get(v.f.get("item_id"))
            return [{"mp_category": mc}] if mc else []
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


def _oude_module(pad_in_repo: str, commit: str, naam: str, moet_bevatten=(), moet_missen=()):
    bron = subprocess.run(["git", "show", f"{commit}:{pad_in_repo}"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    for tekst in moet_bevatten:
        assert tekst in bron, f"verkeerd commitnummer gepind: {tekst} ontbreekt"
    for tekst in moet_missen:
        assert tekst not in bron, f"verkeerd commitnummer gepind: {tekst} zit er al in"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / f"{naam}.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location(naam, pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _oude_jobs():
    return _oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_rubriek",
                        moet_missen=("_zet_rubriek_van_marktplaats",))


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


def test_een_storing_bij_marktplaats_houdt_de_opdracht_vast_maar_niet_voor_altijd(monkeypatch):
    J._RUBRIEK_STORING.clear()
    _zet_marktplaats_nep(monkeypatch, _Client(fout=True))
    job = _echte_opdracht()
    db = _DB([job], op_marktplaats={job["item_id"]: NUMMER})
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is False
    assert job["payload"].get("_rubriek_zoeken_sinds")
    assert not job["payload"].get("_rubriek_niet_op_marktplaats"), (
        "een storing is geen bewijs dat het artikel niet op Marktplaats staat")

    # Binnen de storingsrust wordt er niet opnieuw gebeld: dat salvo is juist
    # waar Marktplaats op dichtklapt.
    stil = _Client(fout=True)
    _zet_marktplaats_nep(monkeypatch, stil)
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is False
    assert stil.vragen == []

    J._RUBRIEK_STORING.clear()
    job["payload"]["_rubriek_zoeken_sinds"] = (
        datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is False, (
        "elf minuten is geen reden om alsnog met de geraden, betalende rubriek te gaan")

    J._RUBRIEK_STORING.clear()
    job["payload"]["_rubriek_zoeken_sinds"] = (
        datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is True, (
        "na zes uur moet hij alsnog de deur uit, anders staat de rij stil")


def test_de_vijftig_van_14_september_blijven_staan_in_plaats_van_geannuleerd(monkeypatch):
    """Zijn echte ronde van 14-09-2026, voor en na.

    Om 17:04 zette hij er vijftig klaar. Binnen één minuut waren ze alle vijftig
    geannuleerd met "2dehands charges for adverts in Muziek snaarinstrumenten
    gitaren", terwijl diezelfde opzoeking de dag ervoor 127 keer achter elkaar
    wél lukte. Nagemeten op 14-09-2026: alle vijftig staan gewoon in Verzamelen |
    Muziek, Artiesten en Beroemdheden op Marktplaats.
    """
    betaald = {"status": "error", "category": GITAREN, "mp_category": None,
               "result": {"error": J._melding_rubriek_vraagt_geld("2dehands", "Gitaren")}}
    op_mp = {"f47f50da-a1ee-498a-b531-b93a290e0e22": NUMMER}

    # ZOALS HET WAS: wie de verkoper is was even niet vast te stellen, en dat
    # gold als antwoord. De opdracht ging met de geraden gitaarrubriek de rij in
    # en werd door de rem meteen teruggenomen.
    oud_mp = _oude_module("backend/services/mp_enrich.py", VOOR_14_SEPTEMBER, "oud_mp_enrich",
                          moet_bevatten=("rubriek_van_eigen_advertentie",))
    oud = _oude_module("backend/api/jobs.py", VOOR_14_SEPTEMBER, "oud_jobs_14sep",
                       moet_bevatten=("_zet_rubriek_van_marktplaats",))
    _verkoper_onvindbaar(monkeypatch, _Client(), oud_mp)
    monkeypatch.setitem(sys.modules, "backend.services.mp_enrich", oud_mp)
    oud_job = _echte_opdracht()
    oud_db = _DB([oud_job], op_marktplaats=op_mp, geschiedenis=[betaald])
    assert _uitgifte(oud, monkeypatch, oud_db) == []
    assert oud_job["payload"].get("_rubriek_niet_op_marktplaats") is True
    assert any(t == "jobs" and w.get("status") == "cancelled" for t, _f, w in oud_db.updates), (
        "dit is wat Egbert vijftig keer las"
    )
    monkeypatch.setitem(sys.modules, "backend.services.mp_enrich", M)

    # ZOALS HET NU IS: geen antwoord is geen stempel. De opdracht blijft staan
    # en wordt opnieuw geprobeerd zodra de opzoeking het weer doet.
    J._RUBRIEK_STORING.clear()
    _verkoper_onvindbaar(monkeypatch, _Client())
    job = _echte_opdracht()
    db = _DB([job], op_marktplaats=op_mp, geschiedenis=[betaald])
    assert _uitgifte(J, monkeypatch, db) == []
    assert not job["payload"].get("_rubriek_niet_op_marktplaats")
    assert not any(t == "jobs" and w.get("status") == "cancelled" for t, _f, w in db.updates), (
        "een storing mag geen zoekertje annuleren"
    )
    assert job["status"] == "pending"

    # En zodra Marktplaats weer antwoordt gaat hij alsnog naar Verzamelen.
    J._RUBRIEK_STORING.clear()
    _zet_marktplaats_nep(monkeypatch, _Client())
    uit = _uitgifte(J, monkeypatch, _DB([job], op_marktplaats=op_mp, geschiedenis=[betaald]))
    assert len(uit) == 1 and uit[0]["payload"]["mp_category"]["l2"] == 926


def test_een_lege_lijst_is_geen_antwoord():
    """Marktplaats antwoordt onder druk met een keurige 200 en niets erin."""
    leeg = _Client({"listings": [], "facets": []})
    assert asyncio.run(M.rubriek_op_advertentienummer(leeg, 6999351, TITEL, NUMMER)) is None
    oud_mp = _oude_module("backend/services/mp_enrich.py", VOOR_14_SEPTEMBER, "oud_mp_leeg",
                          moet_bevatten=("rubriek_van_eigen_advertentie",))
    assert asyncio.run(oud_mp.rubriek_op_advertentienummer(
        _Client({"listings": [], "facets": []}), 6999351, TITEL, NUMMER)) == {}, (
        "vroeger gold een leeg antwoord als 'staat niet op Marktplaats'")


def test_een_rubriek_die_we_al_kennen_wordt_niet_opnieuw_opgezocht(monkeypatch):
    """Vijftig zoekertjes waren vijftig vragen aan Marktplaats binnen een minuut."""
    J._RUBRIEK_STORING.clear()
    client = _Client(fout=True)
    _zet_marktplaats_nep(monkeypatch, client)
    job = _echte_opdracht()
    db = _DB([job], op_marktplaats={job["item_id"]: NUMMER},
             eerder={job["item_id"]: {"l1": 895, "l1_naam": "Verzamelen",
                                      "l2": 926, "l2_naam": "Muziek, Artiesten en Beroemdheden"}})
    assert J._zet_rubriek_van_marktplaats(db, USER, job) is True
    assert job["payload"]["mp_category"]["l2"] == 926
    assert client.vragen == [], "hier hoort geen enkel verzoek naar buiten te gaan"


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


# ── 19-09-2026: de advertentie heet op Marktplaats anders dan bij ons ────────
#
# Daniel: "hij doet heel lang over 2dehands openen, ik denk dat ie vastgelopen
# is." Gemeten in zijn eigen opdrachten: Marktplaats ging om 09:50:14 open en
# was om 09:53:34 klaar; het zoekertje op 2dehands van 09:50:08 stond om 10:02
# nog steeds te wachten, terwijl het dashboard "binnen ~15 seconden" beloofde.
#
# De oorzaak: wij plaatsen op Marktplaats met een VERTAALDE titel en bewaren in
# de voorraad de brontitel, en die is Engels bij alles wat uit Vinted of de
# webshop komt. Er werd gezocht op "(1367) White Columbia Fleece Jacket" terwijl
# de advertentie "(1367) Witte Columbia fleecejas" heet: nul resultaten, en nul
# is hier niet "bestaat niet" maar "kon niet zoeken" — dus wachten, tot zes uur.
VOOR_DE_TITELREPARATIE = "69c8ad7d"
NL_TITEL = "(1367) Witte Columbia fleecejas - Heren XL - Zeer goed"
EN_TITEL = "(1367) White Columbia Fleece Jacket - Men XL - Very Good"
JAS_NUMMER = "m2444265405"
JAS_ITEM = "88f41d7a-56a6-48c6-b742-2bcbcf7c0eaf"
JAS_RUBRIEK = {"l1": 1776, "l1_naam": "Kleding | Heren",
               "l2": 2788, "l2_naam": "Jassen | Winter"}

# Letterlijk (ingekort) van /lrp/api/search met sellerIds[]=25837606, 19-09-2026.
EIGEN_LIJST = {
    "listings": [
        {"itemId": "m2444265405", "title": NL_TITEL, "categoryId": 2788},
        {"itemId": "m2444076253", "title": "(1370) Marineblauw Quechua Broek - Heren XL",
         "categoryId": 2788},
    ],
    "facets": [{"key": "RelevantCategories", "categories": [
        {"id": 1776, "label": "Kleding | Heren", "parentId": None},
        {"id": 2788, "label": "Jassen | Winter", "parentId": 1776},
    ]}],
}


class _ClientPerVraag:
    """Antwoordt zoals Marktplaats het vandaag deed: de Engelse titel levert
    niets op, de eigen advertentielijst (zonder zoekterm) levert alles."""

    def __init__(self):
        self.vragen = []

    async def get(self, url, params=None, headers=None):
        self.vragen.append(params)
        vraag = (params or {}).get("query")
        if not vraag:
            return _Antwoord(EIGEN_LIJST)                 # de eigen advertenties
        if vraag.split()[:2] == NL_TITEL.split()[:2]:
            return _Antwoord(EIGEN_LIJST)                 # de titel zoals geplaatst
        return _Antwoord({"listings": [], "facets": []})  # de Engelse brontitel

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def test_de_engelse_brontitel_vindt_de_advertentie_niet_maar_de_eigen_lijst_wel():
    """Voor-en-na op precies de vraag die vanochtend bleef hangen."""
    oud_mp = _oude_module("backend/services/mp_enrich.py", VOOR_DE_TITELREPARATIE,
                          "oud_mp_titel", moet_missen=("_rubriek_uit_zoekantwoord",))
    assert asyncio.run(oud_mp.rubriek_op_advertentienummer(
        _ClientPerVraag(), 25837606, EN_TITEL, JAS_NUMMER)) is None, \
        "de oude versie hoort hier juist te blijven wachten"

    client = _ClientPerVraag()
    assert asyncio.run(M.rubriek_op_advertentienummer(
        client, 25837606, EN_TITEL, JAS_NUMMER)) == JAS_RUBRIEK
    assert client.vragen[-1].get("query") is None, \
        "de laatste ronde vraagt de eigen advertenties op, zonder zoekterm"
    # En met beide titels is de eerste vraag meteen raak: geen extra ronde nodig.
    kort = _ClientPerVraag()
    assert asyncio.run(M.rubriek_op_advertentienummer(
        kort, 25837606, [NL_TITEL, EN_TITEL], JAS_NUMMER)) == JAS_RUBRIEK
    assert len(kort.vragen) == 1


def test_een_nummer_dat_niet_van_deze_verkoper_is_blijft_leeg():
    """De eigen lijst mag nooit een rubriek van een ANDERE advertentie opleveren."""
    assert asyncio.run(M.rubriek_op_advertentienummer(
        _ClientPerVraag(), 25837606, NL_TITEL, "m1111111111")) == {}


def test_de_jas_gaat_nu_meteen_de_deur_uit_in_plaats_van_zes_uur_te_wachten(monkeypatch):
    """De echte uitgifte, met de Engelse titel in de voorraad en de Nederlandse
    in de opdracht — precies zoals het vanochtend in de database stond."""
    opdracht = {"id": "48e41d01-ecc0-4be4-884f-83e92d549099", "user_id": USER,
                "item_id": JAS_ITEM, "platform": "2dehands", "action": "create",
                "status": "pending", "scheduled_for": None, "claimed_at": None,
                "created_at": (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat(),
                "payload": {"title": NL_TITEL, "category": "heren jassen", "price": 14.99,
                            "_taal": "nl", "description": "Authentiek fleecejack van Columbia."}}

    def opzetten(module, monkeypatch):
        _zet_marktplaats_nep(monkeypatch, _ClientPerVraag(), mod=M)

        async def verkoper(*_a, **_kw):
            return 25837606
        monkeypatch.setattr(M, "_verkopersnummer", verkoper)
        return _DB([dict(opdracht)], op_marktplaats={JAS_ITEM: JAS_NUMMER},
                   items_titel=EN_TITEL)

    db = opzetten(J, monkeypatch)
    uit = _uitgifte(J, monkeypatch, db)
    assert len(uit) == 1, "de opdracht hoort nu gewoon uitgedeeld te worden"
    assert uit[0]["payload"]["mp_category"] == JAS_RUBRIEK
    assert "_rubriek_zoeken_sinds" not in uit[0]["payload"]

    # En zoals het was: wachten, met een stempel en zonder rubriek.
    oud_j = _oude_module("backend/api/jobs.py", VOOR_DE_TITELREPARATIE, "oude_jobs_titel",
                         moet_bevatten=("_zet_rubriek_van_marktplaats",))
    oud_m = _oude_module("backend/services/mp_enrich.py", VOOR_DE_TITELREPARATIE,
                         "oud_mp_titel2", moet_missen=("_rubriek_uit_zoekantwoord",))
    monkeypatch.setitem(sys.modules, "backend.services.mp_enrich", oud_m)
    _zet_marktplaats_nep(monkeypatch, _ClientPerVraag(), mod=oud_m)

    async def verkoper(*_a, **_kw):
        return 25837606
    monkeypatch.setattr(oud_m, "_verkopersnummer", verkoper)
    oud_db = _DB([dict(opdracht)], op_marktplaats={JAS_ITEM: JAS_NUMMER}, items_titel=EN_TITEL)
    assert _uitgifte(oud_j, monkeypatch, oud_db) == [], \
        "de oude versie hield deze opdracht juist vast"
