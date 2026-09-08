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
        self.filters, self.in_filters, self.tekstfilter = {}, {}, None
        self.op, self.velden, self.omgekeerd, self.grens = None, None, False, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def filter(self, kolom, _op, patroon):
        # Alleen wat we echt gebruiken: result->>error ilike '%[extensie %'
        self.tekstfilter = (kolom, patroon.strip("%"))
        return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, _k, desc=False): self.omgekeerd = desc; return self
    def limit(self, n): self.grens = n; return self

    def execute(self):
        bron = ({"listings": self.db.listings,
                 "extension_heartbeat": self.db.heartbeat}.get(self.tabel, self.db.jobs))
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.in_filters.items())]
        if self.tekstfilter:
            kolom, naald = self.tekstfilter
            if kolom == "result->>error":
                rijen = [r for r in rijen if naald in str((r.get("result") or {}).get("error") or "")]
        if self.omgekeerd:
            rijen = list(reversed(rijen))
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        elif self.grens:
            rijen = rijen[:self.grens]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, jobs=None, listings=None, heartbeat=None):
        self.jobs, self.listings = jobs or [], listings or []
        self.heartbeat = heartbeat or []

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


# ── De bredere rem: veel wisselende mislukkingen, nooit één succes ───────────
#
# GEMETEN (07-09-2026, Egbert Brouwer). 671 plaatsopdrachten voor 2dehands, nul
# geslaagd. De laatste tientallen wisselen tussen "timed out", "not signed in" en
# "queue stopped" — de oude rem keek naar drie identieke op rij en zag dit niet.

_NIET_INGELOGD = ("You are not signed in to 2dehands (2dehands.be) in this browser, "
                  "so nothing was published.")
_WACHTRIJ_GESTOPT = "queue stopped"


def _wisselend(n, platform="2dehands"):
    """n mislukkingen die van vorm wisselen, allemaal ondoorgrond, nooit een succes."""
    vormen = [TIMEOUT, _NIET_INGELOGD, {"cancelled": _WACHTRIJ_GESTOPT, "error": _WACHTRIJ_GESTOPT}]
    rijen = []
    for i in range(n):
        v = vormen[i % 3]
        if isinstance(v, dict):
            rijen.append({"id": f"w{i}", "user_id": "u", "platform": platform, "action": "create",
                          "status": "cancelled", "item_id": f"i{i}", "result": v})
        else:
            rijen.append({"id": f"w{i}", "user_id": "u", "platform": platform, "action": "create",
                          "status": "error", "item_id": f"i{i}", "result": {"error": v}})
    return rijen


def test_kanaal_kansloos_bij_veel_wisselende_mislukkingen():
    db = _DB(jobs=_wisselend(12))
    assert api._kanaal_kansloos(db, "u", "2dehands") is True


def test_kanaal_kansloos_onder_de_drempel_is_nog_geen_patroon():
    """Vijf keer 'niet ingelogd' is vervelend, maar nog geen bewijs dat het
    kanaal kansloos is — en het zijn geen drie identieke tijdsoverschrijdingen."""
    jobs = [{"id": f"n{i}", "user_id": "u", "platform": "2dehands", "action": "create",
             "status": "error", "item_id": f"i{i}", "result": {"error": _NIET_INGELOGD}}
            for i in range(5)]
    db = _DB(jobs=jobs)
    assert api._kanaal_kansloos(db, "u", "2dehands") is False


def test_kanaal_kansloos_zwijgt_zodra_er_ooit_iets_lukte():
    jobs = _wisselend(12)
    jobs.append({"id": "ok", "user_id": "u", "platform": "2dehands", "action": "create",
                 "status": "done", "item_id": "i99", "result": {}})
    db = _DB(jobs=jobs)
    assert api._kanaal_kansloos(db, "u", "2dehands") is False


def test_kanaal_kansloos_negeert_uitgelegde_fouten():
    """Twaalf keer 'vul de foto's in' met nul successen: dat zegt wél iets over
    de artikelen (foto's ontbreken), dus geen kanaalbrede rem."""
    db = _DB(jobs=_mislukt(12, fout="Photos could not be uploaded"))
    assert api._kanaal_kansloos(db, "u", "2dehands") is False


def test_de_bredere_rem_herschrijft_ook_bij_een_inlogverwijt():
    """VOOR: alleen 'timed out' werd rechtgezet naar 'formulier ging niet open'.
    NA: een inlogverwijt op een kansloos kanaal ook."""
    job = {"action": "create", "platform": "2dehands"}
    uit = api._rechtgezette_foutmelding(job, {"error": _NIET_INGELOGD}, None, kansloos=True)
    assert "never opened" in uit["error"]
    assert "2dehands.be" in uit["error"]
    assert uit["error_oorspronkelijk"] == _NIET_INGELOGD


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


# ── De rem mag geen muur zijn ──────────────────────────────────────────────

def _muur_mislukt(n, versie=None, status="cancelled"):
    stempel = f" [extensie {versie}]" if versie else ""
    return [{"user_id": "u", "platform": "2dehands", "action": "create",
             "status": status, "result": {"error": TIMEOUT + stempel}} for _ in range(n)]


def test_een_bijgewerkte_kopie_krijgt_het_kanaal_terug():
    """WAAROM DIT ER IS (08-09-2026, Egbert Brouwer).

    De rem sloeg aan zolang er nog nooit één plaatsing was geslaagd, en hield
    precies de poging tegen waarmee dat had kunnen veranderen. Gemeten in het
    opdrachtenlogboek: na 06-09 21:14 is er voor zijn 2dehands geen enkele
    opdracht meer aangemaakt, ook niet nadat Chrome zijn kopie had bijgewerkt
    van 1.0.306 naar 1.0.311 — de versie waarin de gemeten oorzaken juist waren
    verholpen. Elke klik op publiceren gaf de foutmelding van dagen eerder
    terug. Een rem die zichzelf nooit meer kan opheffen is geen rem.
    """
    db = _DB(jobs=_muur_mislukt(40) + _muur_mislukt(20, "1.0.306", status="error"),
             heartbeat=[{"user_id": "u", "ext_version": "1.0.311"}])
    assert api._kanaal_kansloos(db, "u", "2dehands") is False


def test_dezelfde_kopie_blijft_wel_geremd():
    """De uitweg is "er draait iets anders", niet "probeer het gewoon nog eens"."""
    db = _DB(jobs=_muur_mislukt(40) + _muur_mislukt(20, "1.0.311", status="error"),
             heartbeat=[{"user_id": "u", "ext_version": "1.0.311"}])
    assert api._kanaal_kansloos(db, "u", "2dehands") is True


def test_zonder_bekende_versie_verandert_er_niets():
    """Weten we niet welke kopie draait, dan houden we de rem zoals hij was."""
    db = _DB(jobs=_muur_mislukt(40) + _muur_mislukt(20, "1.0.306", status="error"))
    assert api._kanaal_kansloos(db, "u", "2dehands") is True
