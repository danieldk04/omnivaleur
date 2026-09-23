"""Krijgt 2dehands een beurt terwijl er een Marktplaats-rij staat?

WAAROM DIT ER IS (05-09-2026, Lynn van De Juiste Toon)

"Marktplaats ging vandaag helemaal super, niks op aan te merken. Naar
tweedehands pakt ie nog niet." Gemeten in haar eigen opdrachten: op 04-09 stond
er om 14:08:09 één 2dehands-publicatie klaar. Die is nooit opgepakt en is om
18:23 met de hand geannuleerd, terwijl er in diezelfde vier uur negen
Marktplaats-publicaties wél doorheen gingen (14:09:55, 14:14:30, 14:17:51,
14:25:01, 14:31:32, 14:35:02, 14:42:33, 14:46:02, 14:54:03). Op haar twee
drukste dagen ging er van de 75 en de 98 publicaties telkens precies één naar
2dehands.

De extensie vraagt de kanalen in een vaste volgorde met marktplaats voorop,
terwijl er maar één publicatie tegelijk mag lopen. Wie vooraan staat pakt dus
elke vrijgekomen plek. De extensie deelt de beurt sinds 1.0.306 zelf rond, maar
een nieuwe versie is er pas na de Web Store — daarom doet de server het ook.

Deze proef draait de ECHTE uitgifte (`get_pending_jobs`) tegen een nagemaakte
database met twintig Marktplaats-opdrachten en één voor 2dehands.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402

NU = datetime.now(timezone.utc)


def _job(jid, platform, minuten_geleden, actie="create"):
    return {
        "id": jid,
        "user_id": "u1",
        "item_id": "item-" + jid,
        "platform": platform,
        "action": actie,
        "status": "pending",
        "payload": {"price": 20},
        "created_at": (NU - timedelta(minutes=minuten_geleden)).isoformat(),
        "claimed_at": None,
        "done_at": None,
        "scheduled_for": None,
    }


def _bouw_db(wachtrij, laatst_bediend, laatst_geleden_sec=30, bezig=()):
    """Nagemaakte Supabase-client: alleen wat de uitgifte echt vraagt.

    `bezig` = de kanalen waar op dit moment echt een formulier openstaat (een
    verse claim). Dat is wat bepaalt of er nog een tabblad bij mag."""
    op_id = {j["id"]: j for j in wachtrij}

    class _B:
        def __init__(self, tabel):
            self.tabel, self.soort, self.filters = tabel, "select", {}
            self.niet_leeg = None
            self.ongelijk = {}

        def select(self, *a, **kw): self.soort = "select"; return self
        def update(self, v): self.soort = "update"; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def neq(self, k, v): self.ongelijk[k] = v; return self
        def in_(self, k, v): self.filters[k] = list(v); return self
        def lte(self, *a, **kw): return self
        def gte(self, *a, **kw): return self
        def or_(self, *a, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a, **kw): return self

        @property
        def not_(self):
            buiten = self

            class _Niet:
                def is_(self, kolom, waarde):
                    buiten.niet_leeg = kolom
                    return buiten
            return _Niet()

        def execute(self):
            data = []
            if self.tabel == "jobs" and self.soort == "select":
                if self.filters.get("status") == "claimed":
                    data = [{"platform": k, "action": "create",
                             "claimed_at": (NU - timedelta(seconds=20)).isoformat(),
                             "result": None} for k in bezig]
                elif self.niet_leeg == "claimed_at":
                    # "wie deed de vorige publicatie?"
                    data = [{"platform": laatst_bediend, "action": "create",
                             "claimed_at": (NU - timedelta(seconds=laatst_geleden_sec)).isoformat()}] \
                        if laatst_bediend else []
                elif "id" in self.filters:
                    data = [op_id[i] for i in self.filters["id"] if i in op_id]
                elif self.filters.get("action") == "delete":
                    data = []
                elif self.filters.get("status") == "pending":
                    rijen = [j for j in wachtrij if j["status"] == "pending"]
                    if "platform" in self.filters:
                        rijen = [j for j in rijen if j["platform"] == self.filters["platform"]]
                    if "platform" in self.ongelijk:
                        rijen = [j for j in rijen if j["platform"] != self.ongelijk["platform"]]
                    if "action" in self.filters:
                        rijen = [j for j in rijen if j["action"] in self.filters["action"]]
                    data = sorted(rijen, key=lambda j: j["created_at"])
            elif self.tabel == "items":
                data = [{"id": self.filters.get("id", "x"), "user_id": "u1",
                         "title": "t", "sku": None, "brand": None, "price": 20}]
            elif self.tabel == "listings":
                data = []
            return type("R", (), {"data": data})()

    class _Db:
        def table(self, naam): return _B(naam)

    return _Db()


def _uitgifte(monkeypatch, db, platform):
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)
    return J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.305"}})(),
        platform=platform, user_id="u1")


def _lynn_wachtrij():
    rij = [_job(f"mp{i}", "marktplaats", 60 - i) for i in range(20)]
    rij.append(_job("td0", "2dehands", 30))
    return rij


def test_2dehands_komt_aan_de_beurt_na_een_marktplaats_publicatie(monkeypatch):
    """Dit is Lynns geval: twintig Marktplaats-opdrachten, één voor 2dehands."""
    wachtrij = _lynn_wachtrij()
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit, "er moet werk uitgedeeld worden"
    assert uit[0]["platform"] == "2dehands", (
        "Marktplaats deed de vorige publicatie, dus 2dehands is nu aan de beurt; "
        f"gekregen: {uit[0]['platform']} ({uit[0]['id']})")


def test_daarna_is_marktplaats_weer_aan_de_beurt(monkeypatch):
    """Om de beurt is twee kanten op: 2dehands legt Marktplaats niet stil."""
    wachtrij = _lynn_wachtrij()
    db = _bouw_db(wachtrij, laatst_bediend="2dehands")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "marktplaats", (
        f"na een 2dehands-publicatie is Marktplaats aan de beurt; gekregen: {uit}")


def test_zonder_werk_op_een_ander_kanaal_gaat_alles_gewoon_door(monkeypatch):
    """Nooit een beurt doorgeven aan een leeg kanaal — dat legt de rij stil."""
    wachtrij = [_job(f"mp{i}", "marktplaats", 60 - i) for i in range(5)]
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "marktplaats", (
        "er is geen ander kanaal dat wacht, dus Marktplaats gaat gewoon door")


def test_een_scan_geeft_geen_beurt_door(monkeypatch):
    """Lezen is geen publiceren: een scan hoort de beurt niet te verschuiven."""
    wachtrij = [_job("sc0", "marktplaats", 10, actie="scan")]
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats")
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["id"] == "sc0", f"de scan hoort gewoon uitgedeeld te worden: {uit}"


# ── 19-09-2026: kanalen mogen naast elkaar publiceren ────────────────────────
#
# Daniel: "hij doet heel lang over 2dehands openen." Gemeten over tien dagen in
# zijn account: een opdracht die op een andere moest wachten stond 289 seconden
# (mediaan) stil, terwijl het invullen zelf 108 seconden kost op Marktplaats,
# 147 op 2dehands en 354 op Vinted. Drie kanalen achter elkaar is dus zes tot
# tien minuten voor werk dat niets met elkaar te maken heeft.
#
# De reden dat er maar één tegelijk mocht — twee tabbladen deelden één
# opslagplek, en publiceerden dan met elkaars foto's en prijzen — bestaat niet
# meer: elke opdracht hangt aan zijn eigen tabblad. Wat blijft is: nooit twee
# formulieren van dezelfde site.
VOOR_PARALLEL = "b3c31f1b"


def _oude_uitgifte():
    """backend/api/jobs.py zoals het was toen alles nog één voor één ging."""
    import importlib.util
    import subprocess
    import tempfile
    bron = subprocess.run(["git", "show", f"{VOOR_PARALLEL}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "MAX_PARALLELLE_PUBLICATIES" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_parallel.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_parallel", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _uitgifte_op(module, monkeypatch, db, platform):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(module, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(module, "_zet_kleur_goed", lambda rijen: None)
    return module.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.305"}})(),
        platform=platform, user_id="u1")


def test_2dehands_mag_beginnen_terwijl_marktplaats_nog_bezig_is(monkeypatch):
    """Precies Daniels geval van 19-09: Marktplaats vult in, 2dehands staat klaar."""
    wachtrij = [_job("mp0", "marktplaats", 20), _job("td0", "2dehands", 20)]
    db = _bouw_db(wachtrij, laatst_bediend=None, bezig=["marktplaats"])
    uit = _uitgifte(monkeypatch, db, "2dehands")
    assert uit and uit[0]["id"] == "td0", (
        f"2dehands heeft eigen werk en een eigen tabblad nodig; gekregen: {uit}")

    # En zoals het was: niets, tot Marktplaats klaar was.
    oud = _oude_uitgifte()
    oud_db = _bouw_db(wachtrij, laatst_bediend=None, bezig=["marktplaats"])
    assert _uitgifte_op(oud, monkeypatch, oud_db, "2dehands") == [], (
        "de oude uitgifte hield 2dehands juist tegen")


def test_nooit_twee_formulieren_van_hetzelfde_kanaal(monkeypatch):
    """De harde regel die blijft: één tabblad per kanaal."""
    wachtrij = [_job("mp0", "marktplaats", 20), _job("mp1", "marktplaats", 19)]
    db = _bouw_db(wachtrij, laatst_bediend=None, bezig=["marktplaats"])
    assert _uitgifte(monkeypatch, db, "marktplaats") == [], (
        "op Marktplaats staat al een formulier open; er mag er geen tweede bij")


def test_boven_drie_tegelijk_gaat_er_niets_meer_uit(monkeypatch):
    """Elk tabblad is een echt browservenster dat foto's uploadt; drie is genoeg."""
    wachtrij = [_job("fb0", "facebook", 20)]
    db = _bouw_db(wachtrij, laatst_bediend=None,
                  bezig=["marktplaats", "2dehands", "vinted"])
    assert _uitgifte(monkeypatch, db, "facebook") == [], (
        "drie kanalen zijn al bezig, het vierde wacht op een vrije plek")
    # Eén minder en het vierde kanaal mag wel.
    db2 = _bouw_db(wachtrij, laatst_bediend=None, bezig=["marktplaats", "2dehands"])
    uit = _uitgifte(monkeypatch, db2, "facebook")
    assert uit and uit[0]["id"] == "fb0", f"er is nog een plek vrij: {uit}"


def test_de_beurt_wordt_nooit_doorgegeven_aan_een_kanaal_dat_al_bezig_is(monkeypatch):
    """De beurtverdeling mag geen tweede tabblad op een bezet kanaal openen.

    Marktplaats deed de vorige publicatie én 2dehands is op dit moment aan het
    invullen. De beurtverdeling zou 2dehands aanwijzen; dat zou nu een tweede
    2dehands-formulier opleveren."""
    wachtrij = [_job("mp0", "marktplaats", 20), _job("td0", "2dehands", 20)]
    db = _bouw_db(wachtrij, laatst_bediend="marktplaats", bezig=["2dehands"])
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["platform"] == "marktplaats", (
        f"2dehands is bezig, dus Marktplaats doet gewoon zijn eigen werk: {uit}")


def test_een_scan_houdt_geen_enkel_kanaal_tegen(monkeypatch):
    """Lezen blokkeert niets, ook niet met de nieuwe telling."""
    wachtrij = [_job("mp0", "marktplaats", 20)]
    db = _bouw_db(wachtrij, laatst_bediend=None, bezig=[])
    uit = _uitgifte(monkeypatch, db, "marktplaats")
    assert uit and uit[0]["id"] == "mp0"


# ── 23-09-2026: geen beurt aan werk dat op zijn rubriek wacht ────────────────
#
# Gemeten bij f8c0cce9 (muziekwinkel): 14 zoekertjes voor 2dehands wachtten op
# hun Marktplaats-rubriek (de opzoeking gaf geen antwoord), 13 Vinted-plaatsingen
# erachter. Vinted deed de vorige publicatie, dus gaf de server de beurt aan
# 2dehands; die werden verderop allemaal teruggehouden en er ging niets uit. Een
# uur lang bewoog er alleen iets als er toevallig een ander soort opdracht tussen
# kwam. Chrome stond de hele tijd aan.
VOOR_RUBRIEKWACHT = "2ea80204"


def _wacht_wachtrij():
    rij = []
    for i in range(5):
        j = _job(f"td{i}", "2dehands", 60 - i)
        j["payload"]["_rubriek_zoeken_sinds"] = (NU - timedelta(minutes=20)).isoformat()
        rij.append(j)
    rij.append(_job("vi0", "vinted", 50))
    return rij


def _rubriek_onbekend(module, monkeypatch):
    # De Marktplaats-opzoeking die geen antwoord geeft: wat staat te wachten,
    # blijft staan (zoals _zet_rubriek_van_marktplaats dan doet).
    monkeypatch.setattr(module, "_zet_rubriek_van_marktplaats",
                        lambda db, u, j: not (j.get("payload") or {}).get("_rubriek_zoeken_sinds"))


def test_wachtende_2dehands_rij_legt_vinted_niet_stil(monkeypatch):
    _rubriek_onbekend(J, monkeypatch)
    db = _bouw_db(_wacht_wachtrij(), laatst_bediend="vinted")
    uit = _uitgifte(monkeypatch, db, "vinted")
    assert uit and uit[0]["id"] == "vi0", (
        f"2dehands wacht op zijn rubriek, dus Vinted doet zijn eigen werk: {uit}")

    oud = _oude_uitgifte_op(VOOR_RUBRIEKWACHT)
    _rubriek_onbekend(oud, monkeypatch)
    oud_db = _bouw_db(_wacht_wachtrij(), laatst_bediend="vinted")
    assert _uitgifte_op(oud, monkeypatch, oud_db, "vinted") == [], (
        "de oude uitgifte gaf de beurt aan de wachtende 2dehands-rij en deelde niets uit")


def test_wachten_voorbij_het_geduld_krijgt_wel_de_beurt(monkeypatch):
    """Na het geduld gaat 2dehands alsnog; dan hoort het ook weer aan de beurt."""
    rij = _wacht_wachtrij()
    for j in rij[:5]:
        j["payload"]["_rubriek_zoeken_sinds"] = (
            NU - J._RUBRIEK_ZOEK_GEDULD - timedelta(minutes=1)).isoformat()
    monkeypatch.setattr(J, "_zet_rubriek_van_marktplaats", lambda db, u, j: True)
    db = _bouw_db(rij, laatst_bediend="vinted")
    uit = _uitgifte(monkeypatch, db, "vinted")
    assert uit and uit[0]["platform"] == "2dehands", f"geduld is op, 2dehands mag: {uit}"


def _oude_uitgifte_op(commit):
    import importlib.util
    import subprocess
    import tempfile
    bron = subprocess.run(["git", "show", f"{commit}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_wacht_op_rubriek" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / f"oude_jobs_{commit}.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location(f"oude_jobs_{commit}", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud
