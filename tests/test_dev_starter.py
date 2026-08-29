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
        from datetime import datetime, timezone
        lijst.append(sleutel)
        staat[sleutel] = {"status": "gestart", "pid": 1, "log": "/dev/null",
                          "gestart": datetime.now(timezone.utc).isoformat()}
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


# ── stilvallen mag niet onzichtbaar zijn ──────────────────────────────────
def test_de_starter_meldt_zich_bij_elke_ronde(kast, gestart):
    kast["bug_signalen"] = {}
    S.ronde()
    assert kast["dev_starter_hartslag"]["wanneer"], "geen hartslag weggeschreven"


def test_het_dashboard_waarschuwt_als_hij_stil_is_terwijl_er_werk_wacht(monkeypatch):
    from backend.api import beheer
    monkeypatch.setattr(beheer, "_leadgen_lezen", lambda naam: None)
    stand = beheer._starter_stand({"iets": {"status": "open", "moet_zeker": True}})
    assert stand["waarschuwing"], "een starter die nooit draaide moet opvallen"
    assert stand["wacht_op_sessie"] == 1


def test_het_dashboard_zwijgt_als_er_niets_te_doen_is(monkeypatch):
    from backend.api import beheer
    monkeypatch.setattr(beheer, "_leadgen_lezen", lambda naam: None)
    assert beheer._starter_stand({})["waarschuwing"] == ""


def test_een_verse_hartslag_geeft_geen_waarschuwing(monkeypatch):
    from datetime import datetime, timezone
    from backend.api import beheer
    nu = {"wanneer": datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(beheer, "_leadgen_lezen", lambda naam: nu)
    stand = beheer._starter_stand({"iets": {"status": "open", "moet_zeker": True}})
    assert stand["waarschuwing"] == ""


# ── een sessie die niets opleverde ────────────────────────────────────────
# Aanleiding 29-08-2026: drie sessies stopten binnen twee seconden op de
# maandlimiet. Ze telden alle drie als "gedaan", vraten het dagmaximum op, en de
# drie storingen stonden daarna als opgepakt te verstoffen. De reden stond
# alleen in een logboek dat niemand opent.
def _log(tmp_path, tekst):
    pad = tmp_path / "sessie.log"
    pad.write_text(tekst)
    return str(pad)


def test_de_maandlimiet_wordt_herkend(tmp_path):
    reden = S._waarom_niets_geworden(_log(tmp_path,
        "# sessie\n\nYou've hit your monthly spend limit · raise it at claude.ai\n"))
    assert "maandlimiet" in reden


def test_een_sessie_die_niets_deed_valt_ook_op(tmp_path):
    """Ook zonder bekende foutzin: drie regels is geen gedane reparatie."""
    assert S._waarom_niets_geworden(_log(tmp_path, "# sessie\n\nklaar\n"))


def test_een_sessie_die_echt_werk_deed_is_geen_mislukking(tmp_path):
    assert S._waarom_niets_geworden(_log(tmp_path, "\n".join(
        [f"regel {i}: aan het werk" for i in range(40)]))) == ""


def test_een_hookmelding_over_node_is_geen_mislukking(tmp_path):
    """"node: not found" staat óók in het logboek van een geslaagde sessie."""
    tekst = "\n".join([f"regel {i}" for i in range(40)]
                      + ["SessionEnd hook failed: sh: node: command not found"])
    assert S._waarom_niets_geworden(_log(tmp_path, tekst)) == ""


def test_een_mislukte_sessie_geeft_de_storing_weer_vrij(kast, gestart, monkeypatch, tmp_path):
    kast["bug_signalen"] = {"eentje": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_waarom_niets_geworden", lambda log: "De maandlimiet is bereikt.")
    S.ronde()
    assert gestart == ["eentje"]
    S.ronde()          # pas nu is het proces weg en wordt het logboek gelezen
    # De storing is nooit aangeraakt, dus hij hoort gewoon weer in de wachtrij.
    staat = S._staat()
    assert staat["eentje"]["mislukt"]
    assert [k for k, _ in S._te_doen(kast["bug_signalen"], staat)] == ["eentje"]


def test_een_mislukte_sessie_kost_geen_plek_van_de_dag(kast, monkeypatch):
    from datetime import datetime, timezone
    nu = datetime.now(timezone.utc).isoformat()
    staat = {f"nr{i}": {"gestart": nu, "mislukt": "limiet"} for i in range(5)}
    assert S._vandaag_gestart(staat) == 0
    staat["echt"] = {"gestart": nu}
    assert S._vandaag_gestart(staat) == 1


def test_na_een_mislukking_wordt_er_niet_blindelings_doorgestart(kast, gestart, monkeypatch):
    """De oorzaak ligt buiten dit script; blijven proberen levert alleen ruis op."""
    kast["bug_signalen"] = {"een": _signaal(), "twee": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_waarom_niets_geworden", lambda log: "De maandlimiet is bereikt.")
    S.ronde()
    S.ronde()
    assert len(gestart) == 1, "hij is na een mislukking gewoon doorgegaan"


def test_het_dashboard_toont_waarom_er_niets_gebeurt(monkeypatch):
    from backend.api import beheer
    monkeypatch.setattr(beheer, "_eigenaar", lambda u: None)
    monkeypatch.setattr(beheer, "_leadgen_lezen", lambda naam: {
        "bug_signalen": {"eentje": {"status": "open", "moet_zeker": True,
                                    "melders": ["a@x.nl"], "omschrijving": "kapot"}},
        "dev_sessies": {"eentje": {"status": "mislukt", "gestart": "2026-08-29T12:20:00+00:00",
                                   "mislukt": "De maandlimiet is bereikt."}},
    }.get(naam))
    w = beheer.werkplaats(user=None)
    assert w["sessie_probleem"] == "De maandlimiet is bereikt."
    assert w["bezig"] is None
    assert w["wachtrij"][0]["sleutel"] == "eentje"
    assert w["wachtrij"][0]["melders"] == ["a@x.nl"]


def test_na_een_limiet_wordt_het_later_gewoon_weer_geprobeerd(kast, gestart, monkeypatch):
    """Een gebruikslimiet loopt vanzelf weer open — op 29-08-2026 binnen het uur.

    Zou de starter na één mislukking voorgoed stoppen, dan lag de hele machine
    stil tot iemand hem met de hand aanschopte. Precies wat hij moest voorkomen.
    """
    kast["bug_signalen"] = {"eentje": _signaal()}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_waarom_niets_geworden", lambda log: "De maandlimiet is bereikt.")
    S.ronde()
    S.ronde()                                    # stelt de mislukking vast, wacht
    assert len(gestart) == 1
    monkeypatch.setattr(S, "_minuten_bezig", lambda s: S.HERSTELPAUZE_MINUTEN + 1)
    S.ronde()
    assert len(gestart) == 2, "hij bleef na de wachttijd alsnog stilstaan"
