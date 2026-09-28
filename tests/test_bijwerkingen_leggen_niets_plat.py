"""Verzendkost-bijwerkingen zijn onderhoud; ze mogen niets stilleggen (28-09-2026).

Egbert Brouwer (bcdf9aa4). Om 12:25 UTC zette zijn extensie 235 bijwerkingen van
gisteren door, een per 9 seconden. Twee dingen gingen daardoor mis:

1. Zijn 98 patches van 12:30 stonden achter die 235: tot de database om 13:05
   omviel ging er één nieuw zoekertje online ("doet helemaal geen nieuwe online
   zetten").
2. Elke klare bijwerking liet het dashboard (pollActivity) de hele voorraad en
   alle advertenties opnieuw ophalen: 5.533 artikelen, zo'n 5 MB per keer. Dat
   legde de database plat, voor iedereen. Zie ook
   tests/dashboard-laadrondes-test.js voor de kant van het dashboard.

Elke proef draait de echte functies en laat eerst de versie van vóór deze
reparatie falen op dezelfde gegevens.
"""
from datetime import datetime, timedelta, timezone

import backend.api.jobs as J
from tests.test_2dehands_verzendkosten_bijwerken import (
    USER, _bijwerking, _db, _plaatsing_in_de_rij, _tijd, _uitgifte)
from tests.test_2dehands_volgt_de_marktplaats_rubriek import _oude_module

VOOR_DE_REPARATIE = "d8011011"   # vast nummer: HEAD vergelijkt zichzelf na de commit


def _oude_jobs():
    return _oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_bijwerking_plat",
                        moet_bevatten=("_is_2dh_bijwerking",),
                        moet_missen=("OOK EEN LOPENDE BIJWERKING",))


# ── 1. Een lopende bijwerking laat het dashboard niet alles herladen ─────────
def test_een_lopende_bijwerking_telt_niet_als_werk_op_het_scherm(monkeypatch):
    bezig = {**_bijwerking("b-bezig"), "status": "claimed", "claimed_at": _tijd(0), "result": None}
    plaatsing = {**_plaatsing_in_de_rij("p-bezig"), "status": "claimed", "claimed_at": _tijd(0),
                 "result": None}

    def db_met(rijen):
        class _V:
            def __getattr__(self, _n):
                return lambda *a, **k: self

            @property
            def not_(self):
                return self

            def execute(self):
                return type("R", (), {"data": [dict(r) for r in rijen], "count": None})()
        return type("Db", (), {"table": lambda self, n: _V()})()

    for module, verwacht in ((J, []), (_oude_jobs(), ["b-bezig"])):
        monkeypatch.setattr(module, "get_db", lambda: db_met([bezig]))
        monkeypatch.setattr(module, "_gemeten_tempo", lambda *a: {})
        uit = module.active_jobs(user_id=USER)
        assert [j["id"] for j in uit["working"]] == verwacht, module.__name__

    # Een plaatsing die loopt blijft gewoon zichtbaar als werk.
    monkeypatch.setattr(J, "get_db", lambda: db_met([plaatsing]))
    assert [j["id"] for j in J.active_jobs(user_id=USER)["working"]] == ["p-bezig"]


# ── 2. De eigen klik gaat voor het onderhoud ─────────────────────────────────
NU = datetime(2026, 9, 28, 12, 31, tzinfo=timezone.utc)


def _licht(jid, actie, gemaakt):
    return {"id": jid, "action": actie, "platform": "2dehands", "item_id": jid,
            "created_at": gemaakt.isoformat(), "scheduled_for": None}


def _egbert_om_half_een():
    """235 bijwerkingen van gisteravond, 98 patches van vandaag 12:30."""
    gister = datetime(2026, 9, 27, 20, 45, tzinfo=timezone.utc)
    rij = [_licht(f"b{i:03}", "content_refresh", gister + timedelta(seconds=i)) for i in range(235)]
    vandaag = datetime(2026, 9, 28, 12, 30, 22, tzinfo=timezone.utc)
    return rij + [_licht(f"p{i:02}", "create", vandaag + timedelta(seconds=3 * i)) for i in range(98)]


def test_de_patches_van_vandaag_gaan_voor_de_bijwerkingen_van_gisteren():
    rij = _egbert_om_half_een()
    kop = J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert all(j["action"] == "create" for j in kop), [j["id"] for j in kop]
    oud = _oude_jobs()._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert all(j["action"] == "content_refresh" for j in oud), "zo stond het live om 12:30"


def test_zonder_eigen_werk_komen_de_bijwerkingen_gewoon_aan_de_beurt():
    rij = [r for r in _egbert_om_half_een() if r["action"] == "content_refresh"]
    kop = J._wachtrij_volgorde(rij, NU)[:J.WACHTRIJ_KOP]
    assert [j["id"] for j in kop] == [f"b{i:03}" for i in range(J.WACHTRIJ_KOP)]


def test_de_uitgifte_geeft_de_plaatsing_ook_na_een_lange_rij_bijwerkingen(monkeypatch):
    """Door de echte get_pending_jobs, met een extensie die bijwerkingen kan."""
    rij = [{**_bijwerking(f"b{i}"), "created_at": _tijd(900 - i)} for i in range(40)]
    rij.append(_plaatsing_in_de_rij("p1"))
    nu = _uitgifte(monkeypatch, _db(rij), "1.0.357")
    assert [j["id"] for j in nu] == ["p1"]
    oud = _uitgifte(monkeypatch, _db(rij), "1.0.357", module=_oude_jobs())
    assert [j["id"] for j in oud] == ["b0"], "vroeger: eerst de oudste bijwerking"


# ── 3. Meer dan WACHTRIJ_MAX bijwerkingen: de klik valt niet buiten beeld ────
def _db_met_grens(wachtend):
    """Een nep-database die limit, order en het filter op bijwerkingen echt toepast."""
    class _V:
        def __init__(self, t):
            self.t, self.f, self.grens, self.niet_bijwerking, self.kol = t, {}, None, False, ""

        def select(self, *a, **k):
            self.kol = a[0] if a else ""
            return self

        def eq(self, k, v):
            self.f[k] = v
            return self

        def in_(self, k, v):
            self.f[k] = list(v)
            return self

        def or_(self, s):
            if s == J._NIET_2DH_BIJWERKING:
                self.niet_bijwerking = True
            return self

        def limit(self, n):
            self.grens = n
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        @property
        def not_(self):
            return self

        def execute(self):
            data = []
            if self.t == "jobs" and self.f.get("status") == "pending":
                data = sorted((j for j in wachtend
                               if j["platform"] == self.f.get("platform", j["platform"])),
                              key=lambda j: j["created_at"])
                if self.niet_bijwerking:
                    data = [j for j in data if not J._is_2dh_bijwerking(j)]
                if "id" in self.f:
                    data = [j for j in data if j["id"] in self.f["id"]]
                if self.grens:
                    data = data[:self.grens]
            elif self.t == "items":
                data = [{"id": "it1", "user_id": USER, "title": "t", "sku": None, "brand": None}]
            return type("R", (), {"data": [dict(j) for j in data], "count": None})()

    return type("Db", (), {"table": lambda self, n: _V(n)})()


def test_een_volle_rij_bijwerkingen_duwt_de_klik_niet_buiten_de_lezing(monkeypatch):
    rij = [{**_bijwerking(f"b{i}"), "created_at": _tijd(9000 - i)} for i in range(J.WACHTRIJ_MAX + 20)]
    rij.append(_plaatsing_in_de_rij("p1"))
    assert [j["id"] for j in _uitgifte(monkeypatch, _db_met_grens(rij), "1.0.357")] == ["p1"]
    # Zonder de aparte lezing viel hij buiten de eerste WACHTRIJ_MAX.
    oud = _uitgifte(monkeypatch, _db_met_grens(rij), "1.0.357", module=_oude_jobs())
    assert [j["id"] for j in oud] == ["b0"]
    # En een gewone rij onder de grens kost geen extra lezing (zelfde uitkomst).
    klein = rij[:10] + [rij[-1]]
    assert [j["id"] for j in _uitgifte(monkeypatch, _db_met_grens(klein), "1.0.357")] == ["p1"]
