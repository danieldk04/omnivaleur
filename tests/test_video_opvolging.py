"""De opvolging na Daniels video, en de strenge poort voor de koude reeks.

WAAROM DIT ER IS (14-09-2026)
Daniel stuurt de video zelf naar wie erom vraagt. Wie daarna stil bleef kreeg
sinds 06-09-2026 niets meer: de oude opvolging legde alleen een concept klaar, en
dat onderdeel ging uit met de AI. Voortaan verstuurt de machine V1 na 3 en V2 na 7
dagen zelf, in hetzelfde mailgesprek.

Dat is een mail in een gesprek dat Daniel zelf voert, dus de poort moet smal zijn.
Deze tests draaien de echte _video_opvolging met een nagebouwde postbus en laten
per regel zien wie er wel en wie er juist niet een mail krijgt. Daarnaast: kan de
machine de teksten of de stopvinkjes niet lezen, dan gaat er geen koude mail uit.
"""
import contextlib
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import leadgen_mail as lm  # noqa: E402
import leadgen_sheets as ls  # noqa: E402
import leadgen_sheets_opzetten as op  # noqa: E402

DAG = 86400
ADRES = "anna@vintagezolder.nl"
VIDEOMAIL = ("Hi Anna,\n\nHier is het filmpje: https://omnivaleur.com/mp\n\n"
             "Laat maar weten wat je ervan vindt.\n\nGroetjes,\nDaniel")


class NepBoek:
    def __init__(self, gestopt=()):
        self._gestopt, self.gebeurd = set(gestopt), []

    def gestopt(self):
        return self._gestopt

    def video_opvolging(self, lead, beurt, video_op):
        self.gebeurd.append((lead["email"], beurt))


class NepImap:
    def __init__(self, *a):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, *a):
        pass


@pytest.fixture
def postbus(monkeypatch):
    """Een postbus waarin Daniel Anna vier dagen geleden de video stuurde."""
    stand = SimpleNamespace(verzonden_op=time.time() - 4 * DAG, ontvangen_op=None,
                            tekst=VIDEOMAIL, klant=False, bezwaar=None, verstuurd=[], opgeslagen=0)
    monkeypatch.setenv("IMAP_HOST", "imap.test")
    monkeypatch.setenv("MAIL_PASS", "geheim")
    monkeypatch.setattr(lm, "VIDEO_VENSTER", ("00:00", "23:59"))
    monkeypatch.setattr(lm.imaplib, "IMAP4_SSL", NepImap)
    monkeypatch.setattr(lm, "_laatste_per_adres", lambda imap, mappen, veld:
                        ({ADRES: stand.verzonden_op} if mappen == ["Verzonden"]
                         else ({ADRES: stand.ontvangen_op} if stand.ontvangen_op else {})))
    monkeypatch.setattr(lm, "_laatste_verzonden_bericht", lambda imap, adres: {
        "Subject": "Re: Vraagje over je Marktplaats-aanbod", "Message-ID": "<video@omnivaleur.nl>",
        "References": "<mail1@omnivaleur.nl>", "From": "daniel@omnivaleur.nl", "Date": "",
        "tekst": stand.tekst})
    monkeypatch.setattr(lm, "_waarom_geen_concept", lambda adres, draad: stand.bezwaar)
    monkeypatch.setattr(lm, "is_klant", lambda adres: stand.klant)
    monkeypatch.setattr(lm, "_leads", lambda: [{"email": ADRES, "je_jullie": "Je", "platform": "MP"}])
    monkeypatch.setattr(lm, "_teksten", lambda: ls.controleer_teksten(op.mailteksten()))

    @contextlib.contextmanager
    def postbode(gebruiker, host):
        yield stand.verstuurd.append
    monkeypatch.setattr(lm, "_postbode", postbode)

    def opslaan(state):
        stand.opgeslagen += 1
    monkeypatch.setattr(lm, "_save_state", opslaan)
    return stand


def _draai(state, boek=None, droog=False):
    return lm._video_opvolging(state, boek or NepBoek(), "daniel@omnivaleur.nl", "smtp.test", droog=droog)


def test_vier_dagen_stil_na_de_video_geeft_opvolging_1_in_hetzelfde_gesprek(postbus):
    """DE KERN."""
    state, boek = {ADRES: {"soort": "warm", "beantwoord": True}}, NepBoek()
    assert _draai(state, boek) == 1
    msg = postbus.verstuurd[0]
    assert msg["To"] == ADRES
    assert msg["Subject"] == "Re: Vraagje over je Marktplaats-aanbod"
    assert msg["In-Reply-To"] == "<video@omnivaleur.nl>"
    assert msg["References"] == "<mail1@omnivaleur.nl> <video@omnivaleur.nl>"
    tekst = msg.get_body(preferencelist=("plain",)).get_content()
    assert "heb je nog naar de video kunnen kijken?" in tekst
    assert tekst.rstrip().endswith("Groetjes,\nDaniel")
    assert state[ADRES]["video_opvolg"] == 1 and state[ADRES]["video_op"] == postbus.verzonden_op
    assert postbus.opgeslagen >= 1 and boek.gebeurd == [(ADRES, 0)]


def test_de_machine_draait_twee_keer_maar_mailt_maar_een_keer(postbus):
    state = {ADRES: {"soort": "warm"}}
    _draai(state)
    _draai(state)
    assert len(postbus.verstuurd) == 1


def test_zeven_dagen_na_de_video_komt_opvolging_2(postbus):
    postbus.verzonden_op = time.time() - 8 * DAG
    state = {ADRES: {"video_opvolg": 1, "video_op": postbus.verzonden_op}}
    assert _draai(state) == 1
    assert "Laatste berichtje van mij" in postbus.verstuurd[0].get_body(("plain",)).get_content()
    assert state[ADRES]["video_opvolg"] == 2
    assert _draai(state) == 0                                 # daarna is het klaar


def test_opvolging_2_wacht_tot_dag_7(postbus):
    postbus.verzonden_op = time.time() - 5 * DAG
    assert _draai({ADRES: {"video_opvolg": 1, "video_op": postbus.verzonden_op}}) == 0


@pytest.mark.parametrize("waarom, instellen", [
    ("ze antwoordden na de video", lambda p, st: setattr(p, "ontvangen_op", p.verzonden_op + 3600)),
    ("jouw laatste mail had geen videolink", lambda p, st: setattr(p, "tekst", "Hoi, ik bel je morgen.")),
    ("pas twee dagen stil", lambda p, st: setattr(p, "verzonden_op", time.time() - 2 * DAG)),
    ("video van twaalf dagen oud", lambda p, st: setattr(p, "verzonden_op", time.time() - 12 * DAG)),
    ("het is een klant", lambda p, st: setattr(p, "klant", True)),
    ("de postbus ziet een bezwaar", lambda p, st: setattr(p, "bezwaar", "er ligt al een concept")),
    ("afgemeld", lambda p, st: st.update(afgemeld=True)),
    ("zei nee", lambda p, st: st.update(afgewezen=True)),
    ("gebruikt een concurrent", lambda p, st: st.update(concurrent=True)),
    ("bounce", lambda p, st: st.update(bounce=True)),
    ("jouw mail sloot het gesprek af", lambda p, st: setattr(
        p, "tekst", VIDEOMAIL.replace("Laat maar weten", "Mocht het anders liggen, dan hoor ik het wel."))),
])
def test_wie_er_geen_opvolging_krijgt(postbus, waarom, instellen):
    state = {ADRES: {"soort": "warm"}}
    instellen(postbus, state[ADRES])
    assert _draai(state) == 0, waarom
    assert postbus.verstuurd == [], waarom


def test_jij_schreef_na_de_video_zelf_nog_iets(postbus):
    video_op = time.time() - 9 * DAG
    postbus.verzonden_op = time.time() - 8 * DAG          # jouw nieuwere mail, een dag na de video
    assert _draai({ADRES: {"video_opvolg": 1, "video_op": video_op}}) == 0


def test_niet_meer_mailen_aangevinkt(postbus):
    assert _draai({ADRES: {"soort": "warm"}}, NepBoek(gestopt={ADRES})) == 0


def test_iemand_buiten_de_leadlijst_krijgt_nooit_iets(postbus, monkeypatch):
    """Groothandels en partners krijgen ook de video, maar staan niet in de lijst."""
    monkeypatch.setattr(lm, "_leads", lambda: [])
    assert _draai({ADRES: {"soort": "warm"}}) == 0


def test_s_nachts_gaat_er_niets_uit(postbus, monkeypatch):
    monkeypatch.setattr(lm, "VIDEO_VENSTER", ("25:00", "25:01"))
    assert _draai({ADRES: {"soort": "warm"}}) == 0


def test_droog_laat_zien_maar_verstuurt_en_noteert_niets(postbus):
    state = {ADRES: {"soort": "warm"}}
    assert _draai(state, droog=True) == 1
    assert postbus.verstuurd == [] and "video_opvolg" not in state[ADRES]


def test_kapotte_teksten_geen_video_opvolging(postbus, monkeypatch):
    def kapot():
        raise ls.TekstenFout("V1: [naam] kent de machine niet")
    monkeypatch.setattr(lm, "_teksten", kapot)
    assert _draai({ADRES: {"soort": "warm"}}) == 0 and postbus.verstuurd == []


# ── De koude reeks: niets uit als de spreadsheet niet bruikbaar is ─────────


@pytest.fixture
def beurt(monkeypatch):
    uit = SimpleNamespace(verstuurd=None, alarm=[], wachtrij_gestopt=None)
    monkeypatch.setattr(lm, "MAILFLOW_GEPAUZEERD", False)
    monkeypatch.setattr(lm, "_controleer_afzender", lambda: "smtp.test")
    monkeypatch.setattr(lm, "_need", lambda naam: "daniel@omnivaleur.nl")
    monkeypatch.setattr(lm, "_state", lambda: {})
    monkeypatch.setattr(lm, "_dagplan", lambda state, per_dag: {"tijden": ["00:00"], "gedaan": 0,
                                                                "gerapporteerd": True})
    monkeypatch.setattr(lm, "_eigen_mail_meenemen", lambda state, boek: 0)
    monkeypatch.setattr(lm, "resend_mag_versturen", lambda: True)
    monkeypatch.setattr(lm, "_save_plan", lambda plan: None)
    monkeypatch.setattr(lm, "_storingsalarm", lambda reden, **kw: uit.alarm.append((reden, kw)))

    def wachtrij(state, budget, gestopt=frozenset()):
        uit.wachtrij_gestopt = gestopt
        return [({"email": "nieuw@x.nl"}, 0, "nieuw")]
    monkeypatch.setattr(lm, "_wachtrij", wachtrij)

    def verstuur(rij, *a):
        uit.verstuurd = rij
        return len(rij)
    monkeypatch.setattr(lm, "_verstuur", verstuur)

    class Boek(NepBoek):
        fouten = []

        def wegschrijven(self):
            pass

        def afsluiten(self):
            pass
    uit.boek = Boek(gestopt={"stop@x.nl"})
    monkeypatch.setattr(lm, "Leadboek", lambda: uit.boek)
    return uit


def test_kapotte_mailtekst_er_gaat_niets_uit_en_daniel_hoort_het(beurt, monkeypatch):
    def kapot():
        raise ls.TekstenFout("A1: [naam] kent de machine niet")
    monkeypatch.setattr(lm, "_teksten", kapot)
    lm.tick(SimpleNamespace(per_dag=0, max_per_beurt=3))
    assert beurt.verstuurd is None
    assert "[naam]" in beurt.alarm[0][0]


def test_stoplijst_onleesbaar_er_gaat_niets_uit(beurt, monkeypatch):
    monkeypatch.setattr(lm, "_teksten", lambda: {})

    def onleesbaar():
        raise ls.SheetsFout("503")
    beurt.boek.gestopt = onleesbaar
    lm.tick(SimpleNamespace(per_dag=0, max_per_beurt=3))
    assert beurt.verstuurd is None and beurt.alarm


def test_alles_in_orde_de_stoplijst_gaat_mee_naar_de_wachtrij(beurt, monkeypatch):
    monkeypatch.setattr(lm, "_teksten", lambda: {})
    lm.tick(SimpleNamespace(per_dag=0, max_per_beurt=3))
    assert beurt.wachtrij_gestopt == {"stop@x.nl"}
    assert beurt.verstuurd and not beurt.alarm


def test_wachtrij_slaat_aangevinkte_leads_over(monkeypatch):
    leads = [{"email": "a@x.nl", "ads": 5}, {"email": "Stop@X.nl", "ads": 900}]
    monkeypatch.setattr(lm, "_leads", lambda: leads)
    monkeypatch.setattr(lm, "_beurt", lambda lead, st: (0, "nieuw"))
    assert [l["email"] for l, _, _ in lm._wachtrij({}, 10, {"stop@x.nl"})] == ["a@x.nl"]
