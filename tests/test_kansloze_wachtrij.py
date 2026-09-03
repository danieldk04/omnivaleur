"""Een kanaal dat nog nooit heeft gewerkt, mag niet zestien uur doorgaan.

WAAROM DIT ER IS (03-09-2026, Egbert Brouwer / papas-plectrums)
"Ik loop compleet vast hier, kan niet doen wat ik wil doen."

Nagemeten in het opdrachtenlogboek: van zijn 305 opdrachten voor 2dehands is er
nooit één geslaagd. 26 werden er afgebroken door de bewaker van de extensie na
exact drie minuten, telkens zonder één teken van leven uit het tabblad, en 279
stonden er nog achter. Zijn Marktplaats-opdrachten uit dezelfde ronde liepen wel
door (15 geplaatst), en bij andere verkopers slaagde 2dehands in dezelfde
periode 97 keer. Het verschil zit dus niet in onze code en niet in de categorie
(de nummers 728/748 zijn op 2dehands dezelfde als op Marktplaats, nagemeten via
hun eigen zoek-API) maar in de site: www.2dehands.be antwoordt op het
plaatsadres met HTTP 401 zolang je daar niet bent ingelogd — twaalf bytes platte
tekst, geen formulier. Daar draait ons invulscript niet, dus meldt niemand iets
terug en loopt de bewaker af.

De extensie doet met opzet één opdracht tegelijk. 279 keer drie en een halve
minuut is zestien uur waarin hij verder niets kan publiceren.

Dit staat op de SERVER en niet alleen in de extensie, want een reparatie in de
extensie bereikt hem pas nadat Google hem heeft goedgekeurd; bij hem duurde dat
eerder drie weken. Zie ook _rechtgezette_foutmelding, dat om precies dezelfde
reden bestaat en om precies dezelfde klant.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402

TIMEOUT = ("Extension timed out waiting for this 2dehands job to finish (no response after "
           "3 minutes). The page may have changed, needs a manual step, or the extension lost "
           "track of the tab.")


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters = {}, {}
        self.op, self.velden, self.omgekeerd, self.grens = None, None, False, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, _k, desc=False): self.omgekeerd = desc; return self
    def limit(self, n): self.grens = n; return self

    def execute(self):
        bron = self.db.listings if self.tabel == "listings" else self.db.jobs
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.in_filters.items())]
        if self.omgekeerd:
            rijen = list(reversed(rijen))
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        elif self.grens:
            rijen = rijen[:self.grens]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, jobs=None, listings=None):
        self.jobs, self.listings = jobs or [], listings or []

    def table(self, naam): return _Q(self, naam)


@pytest.fixture(autouse=True)
def _geen_echte_database(monkeypatch):
    monkeypatch.setattr(api, "execute_with_retry", lambda q, *a, **k: q.execute())


def _mislukt(n, platform="2dehands", fout=TIMEOUT):
    return [{"id": f"e{i}", "user_id": "u", "platform": platform, "action": "create",
             "status": "error", "item_id": f"i{i}", "result": {"error": fout}} for i in range(n)]


# ── Wanneer is een reeks kansloos ────────────────────────────────────────────

def test_een_of_twee_keer_is_pech_en_stopt_de_rij_niet():
    """VOOR-EN-NA-rem: één mislukking mag nooit een wachtrij wissen."""
    for aantal in (1, 2):
        db = _DB(jobs=_mislukt(aantal))
        assert api._kansloze_reeks(db, "u", "2dehands") is False, aantal


def test_drie_keer_op_rij_op_een_kanaal_dat_nooit_werkte_is_een_patroon():
    db = _DB(jobs=_mislukt(3))
    assert api._kansloze_reeks(db, "u", "2dehands") is True


def test_werkte_het_kanaal_ooit_wel_dan_blijft_de_rij_staan():
    """Egberts Marktplaats liep wél. Die rij mag niet meegesleept worden."""
    jobs = _mislukt(3, platform="marktplaats")
    jobs.append({"id": "ok", "user_id": "u", "platform": "marktplaats", "action": "create",
                 "status": "done", "item_id": "i9", "result": {}})
    db = _DB(jobs=jobs)
    assert api._kansloze_reeks(db, "u", "marktplaats") is False


def test_een_andere_fout_telt_niet_mee():
    """Een echte, uitgelegde fout is geen stilte en zegt niets over de rest."""
    db = _DB(jobs=_mislukt(3, fout="Photos could not be uploaded"))
    assert api._kansloze_reeks(db, "u", "2dehands") is False


# ── Wat de verkoper te lezen krijgt ─────────────────────────────────────────

def test_de_melding_wijst_hem_naar_de_juiste_site():
    job = {"action": "create", "platform": "2dehands"}
    uit = api._rechtgezette_foutmelding(job, {"error": TIMEOUT}, None, kansloos=True)
    tekst = uit["error"]
    # VOOR: de oude tekst noemde inloggen niet en wees naar "de pagina".
    assert "page may have changed" in TIMEOUT
    assert "sign in" not in TIMEOUT
    # NA: hij weet nu wat hij moet doen, en waar.
    assert "never opened" in tekst
    assert "2dehands.be" in tekst
    assert "sign in" in tekst
    # Hij IS op Marktplaats ingelogd, dus "log in" zonder uitleg klopt niet.
    assert "separate logins" in tekst
    assert uit["error_oorspronkelijk"] == TIMEOUT


def test_de_melding_beweert_niet_langer_dat_hij_uitgelogd_is():
    """DE OORZAAK STOND ER ALS FEIT, EN HET WAS EEN GOK (03-09-2026).

    De eerste versie zei "That is what it looks like when you are not signed
    in". Het bewijs daarvoor was HTTP 401 op het plaatsadres van 2dehands.
    Nagemeten: www.marktplaats.nl geeft op precies datzelfde adres precies
    dezelfde 401, twaalf bytes "Unauthorized" — en daar publiceert Egbert wel.
    Het bewijs bewees dus niets, en hij mailde terecht terug dat hij ingelogd
    was. Wat we mogen opschrijven is de waarneming, plus de controle die hij
    zelf kan doen.
    """
    tekst = api._melding_formulier_ging_niet_open("2dehands")
    # VOOR: één oorzaak, als feit gebracht.
    assert "That is what it looks like when you are not signed in" not in tekst
    # NA: de waarneming.
    assert "never reported back" in tekst
    # NA: de controle die het in één klik beslist, met het adres erbij.
    assert "https://www.2dehands.be/my-account/sell/index.html" in tekst
    # NA: allebei de mogelijkheden, en die van ons staat vooraan.
    assert "the fault is on our side" in tekst
    assert tekst.index("on our side") < tekst.index("not signed in")
    assert "Unauthorized" in tekst


def test_marktplaats_krijgt_zijn_eigen_controlepagina():
    tekst = api._melding_formulier_ging_niet_open("marktplaats")
    assert "https://www.marktplaats.nl/my-account/sell/index.html" in tekst
    assert "2dehands.be/my-account" not in tekst


def test_de_eerste_zeventig_tekens_zeggen_al_iets():
    """De rode balk in het dashboard kapt af op 70 tekens. Wat daar staat is
    voor de meeste verkopers de hele boodschap, dus dat mag geen aanloop zijn."""
    kop = api._melding_formulier_ging_niet_open("2dehands")[:70]
    assert "never opened" in kop


def test_zonder_patroon_blijft_de_oorspronkelijke_melding_staan():
    job = {"action": "create", "platform": "2dehands"}
    uit = api._rechtgezette_foutmelding(job, {"error": TIMEOUT}, None, kansloos=False)
    assert uit["error"] == TIMEOUT


# ── De rij terugnemen ───────────────────────────────────────────────────────

def test_de_hele_rij_wordt_teruggenomen_met_de_reden_erbij():
    """279 wachtende opdrachten, zestien uur werk dat toch niets oplevert."""
    wachtend = [{"id": f"w{i}", "user_id": "u", "platform": "2dehands", "action": "create",
                 "status": "pending", "item_id": f"i{i}", "payload": {}} for i in range(279)]
    ander = {"id": "mp1", "user_id": "u", "platform": "marktplaats", "action": "create",
             "status": "pending", "item_id": "i0", "payload": {}}
    listings = [{"id": f"l{i}", "item_id": f"i{i}", "platform": "2dehands", "status": "pending"}
                for i in range(279)]
    listings.append({"id": "lmp", "item_id": "i0", "platform": "marktplaats", "status": "pending"})
    db = _DB(jobs=wachtend + [ander], listings=listings)

    aantal = api._stop_wachtrij(db, "u", "2dehands", "Sign in to 2dehands first.")

    assert aantal == 279
    assert all(j["status"] == "cancelled" for j in wachtend)
    assert wachtend[0]["result"]["error"] == "Sign in to 2dehands first."
    # Het andere kanaal blijft met rust: daar werkt het wél.
    assert ander["status"] == "pending"
    assert listings[-1]["status"] == "pending"
    # De advertentierijen blijven niet op "bezig" hangen, met de reden erbij.
    tweedehands = [l for l in listings if l["platform"] == "2dehands"]
    assert all(l["status"] == "error" for l in tweedehands)
    assert all(l["error_message"] == "Sign in to 2dehands first." for l in tweedehands)


def test_lege_rij_is_geen_fout():
    db = _DB(jobs=[], listings=[])
    assert api._stop_wachtrij(db, "u", "2dehands", "reden") == 0
