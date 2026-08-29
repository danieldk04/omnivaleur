"""De automatische starter: wanneer hij wél en wanneer hij níet een sessie begint.

WAAROM DIT ER IS (29-08-2026)
De lijn klantenservice → developer bestond al, maar werd alleen gelezen wanneer
Daniel toevallig een sessie opende. De starter dicht dat gat. Juist omdat hij
zelf een Claude Code-sessie opstart die mag committen en pushen, staan de remmen
hier in een test: één sessie tegelijk, nooit twee voor dezelfde storing, en niet
beginnen in een werkmap waar het werk van iemand anders klaarstaat.
"""
import sys
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL / "scripts"))
import dev_starter as S  # noqa: E402


@pytest.fixture
def kast(monkeypatch):
    """De sleutel-waardetabel vervangen door een gewone dict."""
    inhoud: dict = {}
    monkeypatch.setattr(S.A.L, "_db_lees", lambda naam, standaard: inhoud.get(naam, standaard))
    monkeypatch.setattr(S.A.L, "_db_schrijf",
                        lambda naam, waarde: inhoud.__setitem__(naam, waarde) or True)
    monkeypatch.setattr(S, "_werkmap_schoon", lambda: (True, ""))
    return inhoud


def _signaal(melders=("een@x.nl",), **kw):
    s = {"melders": list(melders), "status": "open", "moet_zeker": True,
         "omschrijving": "Het lukt niet", "eerst": "2026-08-20T10:00:00+00:00",
         "laatst": "2026-08-24T10:00:00+00:00", "waarom_zeker": ["een klant is hier boos over"]}
    s.update(kw)
    return s


@pytest.fixture
def gestart(monkeypatch):
    """Onthoudt welke sleutels er gestart zouden zijn, zonder iets te starten."""
    lijst: list[str] = []

    def nep(sleutel, signaal, staat):
        lijst.append(sleutel)
        staat[sleutel] = {"status": "gestart", "pid": 1, "gestart": "2026-08-29T10:00:00+00:00"}
        S._bewaar(staat)
        return True

    monkeypatch.setattr(S, "_start", nep)
    return lijst


# ── wat hij oppakt ─────────────────────────────────────────────────────────
def test_alleen_wat_met_zekerheid_gerepareerd_moet_worden(kast, gestart):
    kast["bug_signalen"] = {
        "moet-wel": _signaal(),
        "moet-niet": _signaal(moet_zeker=False),
    }
    S.ronde()
    assert gestart == ["moet-wel"]


def test_wat_de_meeste_mensen_raakt_gaat_voor(kast, gestart):
    kast["bug_signalen"] = {
        "een-melder": _signaal(("a@x.nl",)),
        "twee-melders": _signaal(("a@x.nl", "b@x.nl")),
    }
    S.ronde()
    assert gestart == ["twee-melders"]


def test_een_gerepareerde_storing_wordt_niet_opgepakt(kast, gestart):
    kast["bug_signalen"] = {"klaar": _signaal(status="opgelost")}
    S.ronde()
    assert gestart == []


# ── de remmen ──────────────────────────────────────────────────────────────
def test_nooit_twee_sessies_voor_dezelfde_storing(kast, gestart, monkeypatch):
    kast["bug_signalen"] = {"eentje": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)   # de vorige sessie is klaar
    S.ronde()
    S.ronde()
    assert gestart == ["eentje"], "dezelfde storing is een tweede keer gestart"


def test_een_sleutel_komt_pas_terug_als_hij_opgelost_of_afgewezen_is(kast, gestart, monkeypatch):
    kast["bug_signalen"] = {"eentje": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    S.ronde()
    # Afgewezen: het slot mag eraf, zodat dezelfde storing later opnieuw kan.
    kast["bug_signalen"]["eentje"]["status"] = "afgewezen"
    S.ronde()                                    # ruimt het slot op
    kast["bug_signalen"]["eentje"]["status"] = "open"
    S.ronde()
    assert gestart == ["eentje", "eentje"]


def test_er_draait_er_maar_een_tegelijk(kast, gestart, monkeypatch):
    kast["bug_signalen"] = {"een": _signaal(("a@x.nl", "b@x.nl")), "twee": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: True)    # de eerste is nog bezig
    S.ronde()
    S.ronde()
    assert gestart == ["een"]


def test_niet_meer_dan_het_dagmaximum(kast, gestart, monkeypatch):
    kast["bug_signalen"] = {f"nr{i}": _signaal() for i in range(S.MAX_PER_DAG + 2)}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    from datetime import datetime, timezone
    vandaag = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(S, "_start", lambda k, s, st: (
        gestart.append(k),
        st.__setitem__(k, {"status": "gestart", "pid": 1, "gestart": vandaag}),
        S._bewaar(st), True)[-1])
    for _ in range(S.MAX_PER_DAG + 2):
        S.ronde()
    assert len(gestart) == S.MAX_PER_DAG


def test_niet_beginnen_in_de_werkmap_van_iemand_anders(kast, gestart, monkeypatch):
    kast["bug_signalen"] = {"eentje": _signaal()}
    monkeypatch.setattr(S, "_werkmap_schoon", lambda: (False, "scripts/iets.py"))
    S.ronde()
    assert gestart == []


def test_de_eigen_boekhouding_telt_niet_als_werk_van_iemand_anders(monkeypatch):
    """.claude-flow schrijft bij elke sessie iets weg; anders start hij nooit."""
    class Uit:
        stdout = " M .claude-flow/data/graph-state.json\n?? .claude-flow/sessions/x.json\n"
    monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: Uit())
    assert S._werkmap_schoon() == (True, "")


# ── de opdracht die de sessie meekrijgt ────────────────────────────────────
def test_de_opdracht_vraagt_om_terugmelden_aan_de_klant():
    tekst = S.opdracht("iets-kapot", _signaal(("boos@klant.nl",)))
    assert "mail_analyse.py opgelost iets-kapot" in tekst
    assert "boos@klant.nl" in tekst
    # en om eerst te kijken, want er is eerder iets 'gerepareerd' dat al klaar was
    assert "voordat je iets wijzigt" in tekst
    # en om niets te pushen als de tests rood zijn
    assert "push dan NIETS" in tekst


def test_de_launchagent_wijst_naar_de_wrapper_die_bestaat():
    import plistlib
    plist = plistlib.loads((WORTEL / "config" / "com.omnivaleur.devstarter.plist").read_bytes())
    assert plist["Label"] == "com.omnivaleur.devstarter"
    # Laden mag niet meteen een sessie starten.
    assert plist["RunAtLoad"] is False
    assert (WORTEL / "scripts" / "dev_starter.sh").is_file()
