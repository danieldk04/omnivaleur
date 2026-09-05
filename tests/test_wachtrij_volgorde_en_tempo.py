"""Wie is er als eerste aan de beurt, en hoe snel gaat het echt?

WAAROM DEZE TEST BESTAAT (03-09-2026, Toon van De Juiste Toon)

Toon stuurde twee klachten op één dag:

  12:44 "Ben al ff aan het laden 50 jobs, maar er gebeurd eigenlijk niets?"
  16:18 "Diverse item zijn geplaatst echter nog niets zichtbaar"

Gemeten aan zijn eigen account bleken zijn advertenties er gewoon te staan (9
van de 9 die dag stonden live op Marktplaats). Er waren twee echte oorzaken:

1. Om 02:33 zette de nachtelijke verversing 50 opdrachten klaar. De uitgifte
   pakte simpelweg de oudste twintig, dus zijn eigen klik van 13:28 stond
   achter drieëntwintig andere. Met Calm mode aan is dat uren.
2. Bij hem zat er 345 seconden tussen twee publicaties (Calm mode), terwijl het
   dashboard "within ~15 seconds" beloofde. Dat verschil is precies wat "er
   gebeurt eigenlijk niets" voelt.

Elke proef hieronder draait de ECHTE functies uit backend/api/jobs.py, en de
eerste laat eerst de oude aanpak falen op dezelfde gegevens.
"""
from datetime import datetime, timedelta, timezone

import backend.api.jobs as J


NU = datetime(2026, 9, 3, 14, 0, tzinfo=timezone.utc)


def _job(minuten_geleden, actie, gepland=False, item="it", platform="marktplaats", jid=None):
    gemaakt = NU - timedelta(minutes=minuten_geleden)
    return {
        "id": jid or f"{actie}-{item}-{minuten_geleden}",
        "action": actie, "platform": platform, "item_id": item,
        "created_at": gemaakt.isoformat(),
        "scheduled_for": (NU - timedelta(hours=9)).isoformat() if gepland else None,
    }


def _nachtronde(paren=24):
    """Zoals bij Toon: om 02:33 een verwijdering + een geplande herplaatsing."""
    rij = []
    for n in range(paren):
        rij.append(_job(687 - n, "delete", item=f"nacht{n}"))
        rij.append(_job(687 - n, "create", gepland=True, item=f"nacht{n}"))
    return rij


# ── 1. De klik van de verkoper zelf ──────────────────────────────────────────

def test_de_eigen_klik_stond_buiten_beeld_en_staat_nu_vooraan():
    eigen = _job(32, "create", item="eigen-klik")
    wachtrij = _nachtronde() + [eigen]

    # ZOALS HET WAS: op volgorde van binnenkomst, en dan de eerste twintig.
    oud = sorted(wachtrij, key=lambda j: j["created_at"])[:20]
    assert eigen not in oud, (
        "voorwaarde van de proef: in de oude aanpak viel zijn eigen klik "
        "buiten het venster van twintig")

    # ZOALS HET NU IS.
    nieuw = J._wachtrij_volgorde(wachtrij, NU)[:J.WACHTRIJ_KOP]
    assert eigen in nieuw, "zijn eigen klik hoort mee te gaan"
    plek = nieuw.index(eigen)
    assert plek <= 1, f"en niet ergens achteraan, maar vooraan (stond op {plek})"


def test_een_advertentie_die_nu_nergens_staat_gaat_altijd_eerst():
    # De verwijdering is al gelopen (staat niet meer in de wachtrij), dus deze
    # advertentie staat op dit moment op geen enkel kanaal.
    offline = _job(600, "create", gepland=True, item="offline")
    wachtrij = [_job(5, "create", item="eigen"), offline] + _nachtronde(2)
    volgorde = J._wachtrij_volgorde(wachtrij, NU)
    assert volgorde[0] is offline, (
        "een artikel dat nu nergens te koop staat gaat voor alles")


def test_de_nachtronde_wordt_niet_vergeten():
    # Alleen nachtronde: die moet gewoon lopen, er is niets anders.
    alleen_nacht = _nachtronde(3)
    assert J._wachtrij_volgorde(alleen_nacht, NU), "er moet werk uitkomen"

    # Een verwijdering die langer dan het geduld wacht, gaat boven een verse.
    oud = _job(700, "delete", item="oud")
    oud_paar = _job(700, "create", gepland=True, item="oud")
    vers = _job(5, "delete", item="vers")
    vers_paar = _job(5, "create", gepland=True, item="vers")
    volgorde = J._wachtrij_volgorde([vers, vers_paar, oud, oud_paar], NU)
    assert volgorde.index(oud) < volgorde.index(vers), (
        "wie het langst wacht komt als eerste van de nachtronde aan de beurt")


def test_lezen_gaat_nooit_voor_publiceren():
    scan = _job(700, "scan", item=None)
    klik = _job(1, "create", item="eigen")
    volgorde = J._wachtrij_volgorde([scan, klik], NU)
    assert volgorde[0] is klik, "een scan leest alleen; publiceren gaat voor"


# ── 2. Dubbele scans ─────────────────────────────────────────────────────────

class _NepDb:
    def __init__(self):
        self.updates = []

    def table(self, naam):
        db = self

        class B:
            def __init__(self):
                self.velden = None
                self.filters = {}

            def update(self, velden):
                self.velden = velden
                return self

            def eq(self, k, v):
                self.filters[k] = v
                return self

            def execute(self):
                db.updates.append((naam, dict(self.filters), self.velden))
                return type("R", (), {"data": []})()

        return B()


def test_vier_keer_dezelfde_scan_wordt_er_een():
    # Zo stond het bij Toon echt: vier Marktplaats-scans van dezelfde seconde.
    scans = [_job(30, "scan", platform="marktplaats", jid=f"scan{n}") for n in range(4)]
    for n, s in enumerate(scans):
        # scan0 het oudst, scan3 het jongst — vier klikken vlak na elkaar.
        s["created_at"] = (NU - timedelta(minutes=30) + timedelta(seconds=n)).isoformat()
    anders = _job(10, "scan", platform="2dehands", jid="scan-2dh")
    db = _NepDb()

    over = J._ruim_dubbele_scans_op(db, scans + [anders], NU.isoformat())

    ids = [j["id"] for j in over]
    assert len([i for i in ids if i.startswith("scan") and i != "scan-2dh"]) == 1, (
        "één scan per kanaal blijft staan, de rest gaat weg")
    # De jongste, want die draagt de meest bijgewerkte lijst van "dit hebben we
    # al" mee; op die lijst bespaart de extensie haar verzoeken.
    assert "scan3" in ids, "de nieuwste scan is degene die blijft staan"
    assert "scan-2dh" in ids, "een scan op een ander kanaal is geen dubbele"
    geannuleerd = [u for u in db.updates if u[2] and u[2].get("status") == "cancelled"]
    assert len(geannuleerd) == 3, "de drie overtollige scans worden netjes afgesloten"


# ── 3. Het gemeten tempo ─────────────────────────────────────────────────────

class _TempoDb:
    """Levert precies de rijen die _gemeten_tempo opvraagt."""

    def __init__(self, rijen):
        self.rijen = rijen

    def table(self, _naam):
        rijen = self.rijen

        class B:
            def select(self, *a, **kw): return self
            def eq(self, *a, **kw): return self
            def in_(self, *a, **kw): return self
            def gte(self, *a, **kw): return self
            def order(self, *a, **kw): return self
            def limit(self, *a, **kw): return self

            @property
            def not_(self): return self

            def is_(self, *a, **kw): return self

            def execute(self): return type("R", (), {"data": rijen})()

        return B()


def _reeks(gaten_seconden, duur=25):
    """Opdrachten die elkaar met vaste tussenpozen opvolgen."""
    t = NU - timedelta(hours=2)
    rijen = []
    for gat in [0] + list(gaten_seconden):
        t = t + timedelta(seconds=gat)
        rijen.append({"action": "create", "claimed_at": t.isoformat(),
                      "done_at": (t + timedelta(seconds=duur)).isoformat()})
        t = t + timedelta(seconds=duur)
    return rijen


def _tempo(rijen, wie):
    # Het tempo wordt een minuut per gebruiker onthouden (zie TEMPO_GELDIG_SECONDEN);
    # in een test wil je die herinnering niet erven van de vorige proef.
    J._tempo_cache.pop(wie, None)
    return J._gemeten_tempo(_TempoDb(rijen), wie)


def test_calm_mode_is_te_meten_zonder_het_te_vragen():
    # Zo liep het bij Toon: 5 tot 6 minuten tussen twee publicaties.
    kalm = _tempo(_reeks([345, 300, 420, 360, 290]), "toon")
    assert kalm["calm"] is True
    assert 250 <= kalm["seconds_between"] <= 450

    # Zo liep het diezelfde dag bij drie andere verkopers: ruim tien seconden.
    snel = _tempo(_reeks([12, 10, 11, 13, 12]), "iemand-anders")
    assert snel["calm"] is False
    assert snel["seconds_between"] < J.TEMPO_KALM_DREMPEL


def test_een_computer_die_uit_stond_telt_niet_als_traagheid():
    # Vier vlotte opdrachten, dan een nacht niets, dan weer vlot. Dat mag nooit
    # als "Calm mode" gelezen worden.
    tempo = _tempo(_reeks([10, 12, 9, 8 * 3600, 11, 10]), "computer-uit")
    assert tempo["calm"] is False, "een nacht stilstand is geen tempo"


def test_een_wachtrij_duurt_langer_dan_de_gaten_ertussen():
    """05-09-2026, Toon opnieuw.

    Het gat tussen twee opdrachten zegt hoe snel de extensie eráán begint. Het
    zegt niet hoe lang een wachtrij duurt, want het werk zelf zit er niet in.
    Gemeten op zijn eigen account, 39 monsters uit twaalf uur: gat 16 seconden,
    werk 29 seconden, van start tot start 46. Wie de looptijd van 38 opdrachten
    met het gat uitrekent belooft bijna drie keer te snel.
    """
    tempo = _tempo(_reeks([30, 30, 30, 30, 30], duur=30), "toon-tempo")
    assert tempo["seconds_between"] == 30, "het gat blijft het gat"
    assert tempo["seconds_per_job"] == 60, (
        "een opdracht van 30 seconden met 30 seconden ertussen kost een minuut")


def test_zonder_genoeg_metingen_beweren_we_niets_over_de_looptijd():
    tempo = _tempo(_reeks([300]), "te-weinig-looptijd")
    assert tempo["seconds_per_job"] is None


def test_te_weinig_metingen_levert_geen_bewering_op():
    tempo = _tempo(_reeks([300]), "te-weinig")
    assert tempo["seconds_between"] is None and tempo["calm"] is False, (
        "met twee opdrachten weten we het niet, en dan zeggen we niets")


# ── 4. En dan de echte uitgifte, niet alleen de losse volgorde ───────────────

def test_de_echte_uitgifte_geeft_zijn_eigen_klik_en_niet_de_nachtronde(monkeypatch):
    """De hele /pending-route draaien met Toons wachtrij van die dag.

    Los getoetst is niet getoetst: het venster van twintig zat in de uitgifte
    zelf, dus alleen hier is te zien dat zijn klik er ook echt uit komt.
    """
    nacht = _nachtronde(24)
    eigen = _job(32, "create", item="eigen-klik", jid="eigen-klik")
    wachtrij = nacht + [eigen]
    op_id = {j["id"]: j for j in wachtrij}
    for j in wachtrij:
        j.setdefault("user_id", "u1")
        j.setdefault("status", "pending")
        j.setdefault("payload", {"price": 20})

    class _B:
        def __init__(self, tabel):
            self.tabel, self.soort, self.velden, self.filters = tabel, "select", None, {}

        def select(self, *a, **kw): self.soort = "select"; return self
        def update(self, v): self.soort, self.velden = "update", v; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def in_(self, k, v): self.filters[k] = list(v); return self
        def lte(self, *a, **kw): return self
        def gte(self, *a, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a, **kw): return self

        def execute(self):
            data = []
            if self.tabel == "jobs" and self.soort == "select":
                if self.filters.get("status") == "claimed":
                    data = []
                elif "id" in self.filters:
                    data = [op_id[i] for i in self.filters["id"] if i in op_id]
                elif self.filters.get("action") == "delete":
                    # De gepaarde verwijdering van een nachtronde-herplaatsing
                    # staat nog te wachten.
                    data = [{"status": "pending", "payload": {}}]
                elif self.filters.get("status") == "pending":
                    data = [j for j in wachtrij
                            if j["platform"] == self.filters.get("platform", j["platform"])]
            elif self.tabel == "items":
                data = [{"id": "x", "user_id": "u1", "title": "t", "sku": None,
                         "brand": None, "price": 20}]
            return type("R", (), {"data": data})()

    class _Db:
        def table(self, naam): return _B(naam)

    db = _Db()
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)

    uit = J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.287"}})(),
        platform="marktplaats", user_id="u1")

    assert len(uit) == 1, "de extensie krijgt er altijd precies één"
    assert uit[0]["id"] == "eigen-klik", (
        "zijn eigen klik gaat voor de nachtronde; vóór deze reparatie kwam die "
        "niet eens in het venster van twintig voor")
