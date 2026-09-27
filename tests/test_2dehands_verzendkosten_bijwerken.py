"""Verzendkosten van een zoekertje dat al op 2dehands staat: wie krijgt dit werk?

Zie tests/2dehands-verzendkosten-bijwerken-test.js voor wat de extensie doet en
wat er live is nagemeten. Hier: de uitgifte. Een kopie onder 1.0.354 zou het
hele plaatsformulier opnieuw invullen (1.0.353) of de opdracht als mislukt melden
(ouder), dus die krijgt dit werk nooit. En mislukt de laatste, dan wacht de rest:
bij Egbert stonden er 116 klaar.
"""
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import backend.api.jobs as J

ROOT = Path(__file__).resolve().parents[1]
USER = "bcdf9aa4-314d-49a2-9573-8818ad61073d"


@pytest.fixture(autouse=True)
def _geen_echte_mail(monkeypatch):
    gemeld = []
    monkeypatch.setattr(J, "_stuur_naar_eigenaar", lambda onderwerp, tekst: gemeld.append((onderwerp, tekst)))
    monkeypatch.setattr(J, "_bijwerking_stil_gemeld", {})
    return gemeld


def _tijd(minuten_geleden: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten_geleden)).isoformat()


def _bijwerking(jid="j1"):
    return {"id": jid, "user_id": USER, "item_id": "it1", "platform": "2dehands",
            "action": "content_refresh", "status": "pending", "created_at": _tijd(5),
            "claimed_at": None, "done_at": None, "scheduled_for": None,
            "payload": {"platform_listing_id": "m2446754373", "_verzending_bijwerken": True,
                        "verzending": {"soort": "zelf", "cents": 495}}}


def _db(wachtend, afgerond=(), laatst_geplaatst_op=None):
    class _Vraag:
        def __init__(self, t):
            self.t, self.soort, self.f, self.kolommen = t, "select", {}, ""

        def select(self, *a, **k):
            self.kolommen = a[0] if a else ""
            return self

        def update(self, v):
            self.soort = "update"
            return self

        def eq(self, k, v):
            self.f[k] = v
            return self

        def neq(self, k, v):
            self.f["!" + k] = v
            return self

        def in_(self, k, v):
            self.f[k] = list(v)
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        @property
        def not_(self):
            return self

        def execute(self):
            data = []
            if self.t == "jobs" and self.soort == "select":
                status = self.f.get("status")
                if status == "pending" or (isinstance(status, list) and "pending" in status):
                    data = [j for j in wachtend
                            if j["platform"] == self.f.get("platform", j["platform"])
                            and j["platform"] != self.f.get("!platform")
                            and (not isinstance(self.f.get("action"), list)
                                 or j["action"] in self.f["action"])]
                    if "id" in self.f:
                        data = [j for j in data if j["id"] in self.f["id"]]
                elif isinstance(status, list) and "error" in status:
                    data = list(afgerond)
                elif self.kolommen == "platform,claimed_at,action" and laatst_geplaatst_op:
                    data = [{"platform": laatst_geplaatst_op, "claimed_at": _tijd(1), "action": "create"}]
                elif "id" in self.f:
                    ids = self.f["id"] if isinstance(self.f["id"], list) else [self.f["id"]]
                    data = [j for j in wachtend if j["id"] in ids]
            elif self.t == "items":
                data = [{"id": "it1", "user_id": USER, "title": "t", "sku": None, "brand": None}]
            return type("R", (), {"data": data, "count": None})()

    return type("Db", (), {"table": lambda self, n: _Vraag(n)})()


def _plaatsing_in_de_rij(jid="p1", platform="2dehands", minuten=1):
    return {**_bijwerking(jid), "action": "create", "platform": platform, "created_at": _tijd(minuten),
            "payload": {"title": "Metallica - Skulls - Rugpatch", "price": 11.95,
                        "verzending": {"soort": "standaard"}}}


def _oude_jobs():
    """backend/api/jobs.py zoals hij om 09:40 op 26-09 live stond (vóór deze reparatie)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rubriekproef", ROOT / "tests" / "test_2dehands_volgt_de_marktplaats_rubriek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._oude_module("backend/api/jobs.py", VOOR_HET_VASTLOPEN, "oude_jobs_vastlopen",
                            moet_bevatten=("MINIMALE_2DH_BIJWERK_VERSIE",),
                            moet_missen=("_is_2dh_bijwerking",))


VOOR_HET_VASTLOPEN = "faefb348"   # vast nummer: HEAD vergelijkt zichzelf na de commit


def _uitgifte(monkeypatch, db, versie, platform="2dehands", module=J):
    J_ = module
    monkeypatch.setattr(J_, "get_db", lambda: db)
    for naam in ("_record_extension_heartbeat", "_recover_stale_claims"):
        monkeypatch.setattr(J_, naam, lambda *a, **k: None)
    monkeypatch.setattr(J_, "_gepubliceerde_extensieversie", lambda: None)
    monkeypatch.setattr(J_, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J_, "_zet_kleur_goed", lambda r: None)
    monkeypatch.setattr(J_, "_zet_taal_goed", lambda db, js: list(js))
    monkeypatch.setattr(J_, "_haal_links_eruit", lambda db, js: 0)
    return J_.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": versie}})(),
        platform=platform, user_id=USER)



@pytest.mark.parametrize("versie,uitgedeeld", [
    ("1.0.352", False),   # kent geen wijzigadres voor 2dehands
    ("1.0.353", False),   # zou het plaatsformulier opnieuw invullen
    ("1.0.354", True),
])
def test_alleen_naar_een_kopie_die_het_kan(monkeypatch, versie, uitgedeeld):
    uit = _uitgifte(monkeypatch, _db([_bijwerking()]), versie)
    assert bool(uit) == uitgedeeld, f"{versie}: {uit}"
    if uitgedeeld:
        assert uit[0]["payload"]["verzending"] == {"soort": "zelf", "cents": 495}


def test_na_een_mislukking_wacht_de_rest(monkeypatch):
    afgerond = [
        {"status": "done", "created_at": _tijd(60), "claimed_at": _tijd(30), "done_at": _tijd(29)},
        {"status": "error", "created_at": _tijd(60), "claimed_at": _tijd(20), "done_at": _tijd(19)},
    ]
    assert _uitgifte(monkeypatch, _db([_bijwerking()], afgerond), "1.0.354") == []


def test_telt_wat_het_laatst_afliep_niet_wat_het_laatst_klaarstond(monkeypatch):
    """Een reeks wordt in één seconde aangemaakt en loopt daarna een voor een af."""
    zelfde = _tijd(60)
    afgerond = [
        {"status": "error", "created_at": zelfde, "claimed_at": _tijd(40), "done_at": _tijd(39)},
        {"status": "done", "created_at": zelfde, "claimed_at": _tijd(10), "done_at": _tijd(9)},
    ]
    assert len(_uitgifte(monkeypatch, _db([_bijwerking()], afgerond), "1.0.354")) == 1


def test_de_noodrem_raakt_geen_plaatsingen(monkeypatch):
    plaatsing = {**_bijwerking("p1"), "action": "create",
                 "payload": {"title": "Patch", "price": 11.95, "verzending": {"soort": "onbekend"}}}
    afgerond = [{"status": "error", "created_at": _tijd(9), "claimed_at": _tijd(9), "done_at": _tijd(8)}]
    uit = _uitgifte(monkeypatch, _db([plaatsing], afgerond), "1.0.354")
    assert [j["id"] for j in uit] == ["p1"]


# ── wachtende bijwerkingen mogen niets stilleggen (Egbert, 26-09-2026) ────────
def _dertig_wachtend_en_daarna_een_plaatsing(platform_van_de_plaatsing="2dehands"):
    rij = [{**_bijwerking(f"b{i}"), "created_at": _tijd(90 - i)} for i in range(30)]
    return rij + [_plaatsing_in_de_rij(platform=platform_van_de_plaatsing)]


@pytest.mark.parametrize("versie", ["1.0.352", "1.0.354-na-een-mislukking"])
def test_een_nieuwe_plaatsing_gaat_langs_de_wachtende_bijwerkingen(monkeypatch, versie):
    """Bij hem stonden er 178 vooraan; de kop van de rij is er 25."""
    afgerond = ([{"status": "error", "created_at": _tijd(99), "claimed_at": _tijd(95), "done_at": _tijd(94)}]
                if "mislukking" in versie else [])
    nu = _uitgifte(monkeypatch, _db(_dertig_wachtend_en_daarna_een_plaatsing(), afgerond), versie[:7])
    assert [j["id"] for j in nu] == ["p1"]
    oud = _uitgifte(monkeypatch, _db(_dertig_wachtend_en_daarna_een_plaatsing(), afgerond), versie[:7],
                    module=_oude_jobs())
    assert oud == [], "zo stond het vanochtend live: de plaatsing kwam nooit aan de beurt"
    # En niet omdat de oude uitgifte in deze proef niets kan: zonder de rij ervoor gaat hij wel.
    alleen = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij()], afgerond), versie[:7], module=_oude_jobs())
    assert [j["id"] for j in alleen] == ["p1"]


def test_de_beurt_gaat_niet_naar_een_kanaal_dat_alleen_wachtend_werk_heeft(monkeypatch):
    """Marktplaats plaatste als laatste, dus 2dehands zou de beurt krijgen."""
    rij = _dertig_wachtend_en_daarna_een_plaatsing(platform_van_de_plaatsing="marktplaats")
    nu = _uitgifte(monkeypatch, _db(rij, laatst_geplaatst_op="marktplaats"), "1.0.352",
                   platform="marktplaats")
    assert [j["id"] for j in nu] == ["p1"]
    oud = _uitgifte(monkeypatch, _db(rij, laatst_geplaatst_op="marktplaats"), "1.0.352",
                    platform="marktplaats", module=_oude_jobs())
    assert oud == [], "vroeger: beurt naar 25 bijwerkingen die daarna allemaal werden overgeslagen"
    alleen = _uitgifte(monkeypatch, _db(rij[-1:], laatst_geplaatst_op="marktplaats"), "1.0.352",
                       platform="marktplaats", module=_oude_jobs())
    assert [j["id"] for j in alleen] == ["p1"]


def test_het_dashboard_toont_ze_niet_als_wachtrij(monkeypatch):
    rij = [_bijwerking(f"b{i}") for i in range(3)] + [_plaatsing_in_de_rij()]
    for module, verwacht in ((J, ["p1"]), (_oude_jobs(), ["b0", "b1", "b2", "p1"])):
        monkeypatch.setattr(module, "get_db", lambda: _db(rij))
        monkeypatch.setattr(module, "_gemeten_tempo", lambda *a: {})
        uit = module.active_jobs(user_id=USER)
        assert sorted(j["id"] for j in uit["queued"]) == verwacht, module.__name__
        assert uit["queued_total"] == len(verwacht)


def test_de_rij_legen_laat_ze_staan(monkeypatch):
    rij = [_bijwerking("b0"), _plaatsing_in_de_rij()]
    geannuleerd = []

    class _V:
        def update(self, _v):
            return self

        def in_(self, k, v):
            geannuleerd.extend(v)
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        def execute(self):
            return type("R", (), {"data": []})()

    monkeypatch.setattr(J, "get_db", lambda: type("Db", (), {"table": lambda self, n: _V()})())
    monkeypatch.setattr(J, "fetch_all", lambda *a, **k: [dict(j) for j in rij])
    J.cancel_queued_jobs(user_id=USER)
    assert "b0" not in geannuleerd and "p1" in geannuleerd


def test_de_extensie_zelf():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is niet geïnstalleerd")
    r = subprocess.run([node, str(ROOT / "tests" / "2dehands-verzendkosten-bijwerken-test.js")],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


# ── na een plaatsing zonder eigen bedrag: alsnog bijwerken ───────────────────
class _Opname:
    """Onthoudt wat er in de jobs-tabel gezet wordt; 'al' = er wacht er al een."""

    def __init__(self, al=False):
        self.al, self.ingevoegd = al, []

    def table(self, _naam):
        opname = self

        class _V:
            def insert(self, rij):
                opname.ingevoegd.append(rij)
                return self

            def __getattr__(self, _n):
                return lambda *a, **k: self

            def execute(self):
                return type("R", (), {"data": [{"id": "x"}] if opname.al else []})()
        return _V()


def _plaatsing(verzending):
    return {"id": "p1", "user_id": USER, "item_id": "it1", "platform": "2dehands", "action": "create",
            "payload": {"title": "Metallica - Skulls - Rugpatch", "verzending": verzending}}


ANTWOORD = {"platform_listing_id": "m2446754373",
            "platform_listing_url": "https://www.2dehands.be/seller/view/m2446754373"}


def test_oude_kopie_plaatste_met_bpost_dan_komt_er_een_bijwerking():
    db = _Opname()
    J._verzending_alsnog_bijwerken(db, _plaatsing({"soort": "zelf", "cents": 495}), ANTWOORD)
    assert len(db.ingevoegd) == 1
    rij = db.ingevoegd[0]
    assert (rij["action"], rij["platform"], rij["status"]) == ("content_refresh", "2dehands", "pending")
    assert rij["payload"]["_verzending_bijwerken"] is True
    assert rij["payload"]["verzending"] == {"soort": "zelf", "cents": 495}
    assert rij["payload"]["platform_listing_id"] == "m2446754373"


def test_geen_bijwerking_als_het_bedrag_er_al_stond_of_niet_hoorde():
    for verzending, antwoord in (
        ({"soort": "zelf", "cents": 495}, {**ANTWOORD, "verzending_gezet": True}),
        ({"soort": "platform"}, ANTWOORD),
        ({"soort": "onbekend"}, ANTWOORD),
        ({"soort": "zelf", "cents": 495}, {}),              # geen zoekertje, niets bij te werken
    ):
        db = _Opname()
        J._verzending_alsnog_bijwerken(db, _plaatsing(verzending), antwoord)
        assert db.ingevoegd == [], (verzending, antwoord)
    db = _Opname(al=True)
    J._verzending_alsnog_bijwerken(db, _plaatsing({"soort": "zelf", "cents": 495}), ANTWOORD)
    assert db.ingevoegd == [], "er wacht er al een: geen tweede"


# ── de driedagenveger laat deze opdrachten wachten ───────────────────────────
def test_de_driedagenveger_laat_een_wachtende_bijwerking_staan(monkeypatch):
    """Een Web Store-goedkeuring kan dagen duren; het zoekertje staat ondertussen online."""
    import asyncio
    import backend.services.relist as rl

    def _dagen(n):
        return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()

    banen = [
        {**_bijwerking("wacht"), "created_at": _dagen(5)},
        {**_bijwerking("te_oud"), "created_at": _dagen(22)},
        {"id": "gewoon", "user_id": USER, "item_id": "it2", "platform": "2dehands",
         "action": "create", "status": "pending", "created_at": _dagen(5), "payload": {}},
    ]
    gewijzigd = {}

    class _V:
        def __init__(self, t):
            self.t, self.velden, self.id = t, None, None

        def update(self, v):
            self.velden = v
            return self

        def eq(self, k, v):
            if k == "id":
                self.id = v
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        def execute(self):
            if self.velden is not None:
                gewijzigd[self.id] = self.velden
                return type("R", (), {"data": []})()
            return type("R", (), {"data": list(banen) if self.t == "jobs" else []})()

    db = type("Db", (), {"table": lambda self, n: _V(n)})()
    monkeypatch.setattr(rl, "get_db", lambda: db)

    async def direct(fn, *_a, **_k):
        return fn()
    monkeypatch.setattr(rl, "naast_de_lus", direct)
    monkeypatch.setattr(rl, "_waarom_bleef_het_staan", lambda *_a: "reden")
    asyncio.run(rl.herstel_vastgelopen_werk())

    assert "wacht" not in gewijzigd, "vijf dagen wachten op de extensie is geen fout"
    assert gewijzigd["te_oud"]["status"] == "cancelled", "na drie weken stil ingetrokken, niet rood"
    assert gewijzigd["gewoon"]["status"] == "error", "de gewone opdrachten blijven zoals ze waren"


# ── een stilstaande reeks meldt zichzelf (de klant ziet hem niet meer) ────────
def test_stilstand_komt_een_keer_per_dag_in_de_mail(_geen_echte_mail):
    fout = [{"id": "job-fout", "status": "error", "created_at": _tijd(9), "claimed_at": _tijd(9), "done_at": _tijd(8)}]
    assert J._bijwerken_2dh_staat_stil(_db([], fout), USER) is True
    assert J._bijwerken_2dh_staat_stil(_db([], fout), USER) is True
    assert len(_geen_echte_mail) == 1, "niet elke poll een mail"
    onderwerp, tekst = _geen_echte_mail[0]
    assert "job-fout" in tekst and USER in tekst


def test_geen_mail_als_het_goed_ging_of_niet_te_lezen_was(_geen_echte_mail):
    goed = [{"id": "j", "status": "done", "created_at": _tijd(9), "claimed_at": _tijd(9), "done_at": _tijd(8)}]
    assert J._bijwerken_2dh_staat_stil(_db([], goed), USER) is False

    class _Kapot:
        def table(self, _n):
            raise RuntimeError("database weg")
    assert J._bijwerken_2dh_staat_stil(_Kapot(), USER) is True, "bij twijfel niets uitdelen"
    assert _geen_echte_mail == [], "een leesfout is geen mislukte bijwerking"


# ── een valse mislukking zet de reeks niet meer stil (27-09-2026) ─────────────
# Egbert: van 59 bijwerkingen meldde er één een tijdsoverschrijding (klik op
# Opslaan gedaan, tabblad weg), terwijl 2dehands het nieuwe bedrag wel toonde.
# De noodrem ging dicht en 93 bijwerkingen wachtten ruim vier uur.
VOOR_HET_VANGNET = "28c6560b"   # vast nummer: HEAD vergelijkt zichzelf na de commit
TIJDSOVERSCHRIJDING = ("Extension timed out waiting for this 2dehands job to finish (no response after "
                       "3 minutes). [het tabblad was al weg voordat we konden kijken] [extensie 1.0.354]")


def _pagina(prijs):
    return ('<html>"shippingInformation":{"mappedShippingOptions":{},"augmentedLabels":[{"shouldShowMoreInfo":false,'
            '"carrierId":null,"labels":[{"label":"Verzenden voor","price":"€\xa0' + prijs + '",'
            '"deliveryMethod":"UNKNOWN_BECAUSE_DIY","carrierName":"Zelf Verzenden"}]}]}</html>')


def _vangnet_oud():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rubriekproef", ROOT / "tests" / "test_2dehands_volgt_de_marktplaats_rubriek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._oude_module("backend/api/jobs.py", VOOR_HET_VANGNET, "oude_jobs_vangnet",
                            moet_bevatten=("_bijwerken_2dh_staat_stil",),
                            moet_missen=("_bijwerking_staat_al_online",))


def _meld_fout(monkeypatch, pagina, module=J, status_code=200):
    """fail_job op een bijwerking van EUR 2,95; geeft terug wat er in jobs werd gezet."""
    import httpx
    job = {**_bijwerking("d10256ad"), "status": "claimed",
           "payload": {"platform_listing_id": "m2446742224", "_verzending_bijwerken": True,
                       "verzending": {"soort": "zelf", "cents": 295}}}
    geschreven, bezocht = [], []

    class _V:
        def __init__(self, t):
            self.t, self.w = t, None

        def update(self, v):
            self.w = v
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        def execute(self):
            if self.w is not None:
                geschreven.append((self.t, self.w))
                return type("R", (), {"data": [], "count": None})()
            data = [job] if self.t == "jobs" else []
            return type("R", (), {"data": data, "count": None})()

    db = type("Db", (), {"table": lambda self, n: _V(n)})()
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(httpx, "get", lambda url, **k: bezocht.append(url) or type(
        "R", (), {"status_code": status_code, "text": pagina})())
    module.fail_job("d10256ad", {"error": TIJDSOVERSCHRIJDING}, user_id=USER)
    status = [w["status"] for t, w in geschreven if t == "jobs" and "status" in w]
    return status, bezocht


def test_toont_de_pagina_het_bedrag_dan_is_de_bijwerking_gelukt(monkeypatch):
    nu, bezocht = _meld_fout(monkeypatch, _pagina("2,95"))
    assert nu == ["done"], "het zoekertje toont het nieuwe bedrag: gelukt, geen fout"
    assert bezocht == ["https://www.2dehands.be/m2446742224"]
    # en dus blijft de noodrem open voor de volgende
    afgerond = [{"id": "d10256ad", "status": nu[0], "created_at": _tijd(9), "claimed_at": _tijd(9),
                 "done_at": _tijd(1)}]
    assert J._bijwerken_2dh_staat_stil(_db([], afgerond), USER) is False

    oud, _ = _meld_fout(monkeypatch, _pagina("2,95"), module=_vangnet_oud())
    assert oud == ["error"], "de oude code telde dit als mislukt (en zette de reeks stil)"


@pytest.mark.parametrize("pagina,code", [
    (_pagina("7,10"), 200),       # ander bedrag: echt niet gelukt
    (_pagina("2,95"), 410),       # verlopen zoekertje
    ("<html>geen blok</html>", 200),  # toestemmingsscherm, onderhoud
    (_pagina("2,95"), 403),       # afgeremd
])
def test_zonder_bewijs_blijft_het_een_mislukking(monkeypatch, pagina, code):
    nu, _ = _meld_fout(monkeypatch, pagina, status_code=code)
    assert nu == ["error"]
