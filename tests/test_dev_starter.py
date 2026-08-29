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
        S._tel_een_start_mee()          # net als de echte _start
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
        S._tel_een_start_mee(), S._bewaar(st), True)[-1])
    for _ in range(S.MAX_PER_DAG + 2):
        S.ronde()
    assert len(gestart) == S.MAX_PER_DAG


def test_een_opgeloste_storing_geeft_zijn_plek_van_de_dag_niet_terug(kast, gestart, monkeypatch):
    """Hier zat de fout: het maximum werd uit dev_sessies afgeleid, en een
    opgeloste storing verdwijnt daaruit. Juist een geslaagde sessie — de duurste —
    raakte je dus kwijt uit de telling, en dan konden er veel meer dan drie draaien."""
    from datetime import datetime, timezone
    vandaag = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_start", lambda k, s, st: (
        gestart.append(k),
        st.__setitem__(k, {"status": "gestart", "pid": 1, "gestart": vandaag}),
        S._tel_een_start_mee(), S._bewaar(st), True)[-1])
    for i in range(S.MAX_PER_DAG):
        kast["bug_signalen"] = {f"klaar{i}": _signaal()}
        S.ronde()
        # de storing wordt gerepareerd en verdwijnt uit de administratie
        kast["bug_signalen"][f"klaar{i}"]["status"] = "opgelost"
        S.ronde()
    assert len(gestart) == S.MAX_PER_DAG
    kast["bug_signalen"] = {"nog een": _signaal()}
    S.ronde()
    assert len(gestart) == S.MAX_PER_DAG, "het dagmaximum lekt bij elke geslaagde reparatie"


def test_een_mislukte_sessie_geeft_zijn_plek_wel_terug(kast, gestart, monkeypatch):
    """Die heeft geen gebruikslimiet gekost, dus mag hij geen plek kosten."""
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_waarom_niets_geworden", lambda log: "De limiet was even vol.")
    kast["bug_signalen"] = {"eentje": _signaal()}
    S.ronde()
    assert S._vandaag_gestart() == 1
    S.ronde()                     # stelt de mislukking vast
    assert S._vandaag_gestart() == 0


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


def test_de_limiet_wordt_herkend_zonder_verkeerd_advies(tmp_path):
    """De melding mag niet naar een betaalpagina wijzen.

    Nagemeten op 29-08-2026: precies deze limiet was een uur later vanzelf weer
    weg, zonder dat er iets is betaald of gewijzigd. "Verhoog je maandlimiet"
    stuurt Daniel dan de verkeerde kant op voor iets wat zichzelf oplost.
    """
    reden = S._waarom_niets_geworden(_log(tmp_path,
        "# sessie\n\nYou've hit your monthly spend limit · raise it at claude.ai\n"))
    assert reden, "de limiet werd niet herkend"
    assert "verhoog" not in reden.lower() and "settings/usage" not in reden
    assert "opnieuw" in reden.lower()


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


# ── het scherm: wat er gebeurd is en wat er van Daniel wordt gevraagd ──────
def _beheer(monkeypatch, signalen, sessies=None, escalaties=None):
    from backend.api import beheer
    monkeypatch.setattr(beheer, "_eigenaar", lambda u: None)
    monkeypatch.setattr(beheer, "_leadgen_lezen", lambda naam: {
        "bug_signalen": signalen, "dev_sessies": sessies or {},
        "mail_escalaties": escalaties or [],
        "dev_starter_hartslag": None}.get(naam))
    return beheer


def test_de_tijdlijn_toont_de_hele_lijn_op_volgorde(monkeypatch):
    """Melding → doorgegeven → opgepakt → teruggemeld → concept naar de klant."""
    beheer = _beheer(monkeypatch,
        {"kapot": {"status": "opgelost", "moet_zeker": True, "melders": ["a@x.nl"],
                   "omschrijving": "het lukt niet", "waarom_zeker": ["boos"],
                   "laatst": "2026-08-29T09:00:00+00:00",
                   "gemeld_als_patroon": "2026-08-29T09:10:00+00:00",
                   "gerepareerd_op": "2026-08-29T11:00:00+00:00", "uitleg": "gemaakt",
                   "bericht_verstuurd": ["a@x.nl"]}},
        {"kapot": {"status": "afgerond", "gestart": "2026-08-29T10:00:00+00:00"}})
    rijen = beheer.werkplaats(user=None)["tijdlijn"]
    stappen = [(r["van"], r["naar"]) for r in rijen]
    assert ("klant", "klantenservice") in stappen
    assert ("klantenservice", "developer") in stappen
    assert ("developer", "klantenservice") in stappen
    assert ("klantenservice", "klant") in stappen
    # nieuwste bovenaan
    assert rijen == sorted(rijen, key=lambda r: r["wanneer"], reverse=True)


def test_voor_jou_bevat_alleen_wat_van_daniel_is(monkeypatch):
    beheer = _beheer(monkeypatch,
        {"kapot": {"status": "open", "moet_zeker": True, "melders": ["a@x.nl"],
                   "omschrijving": "x", "laatst": "2026-08-29T09:00:00+00:00"}},
        {}, [{"escalatie": "geld", "adres": "a@x.nl", "samenvatting": "dubbel afgeschreven",
              "afgehandeld": False},
             {"escalatie": "geld", "adres": "oud@x.nl", "samenvatting": "al gedaan",
              "afgehandeld": True}])
    voor_jou = beheer.werkplaats(user=None)["voor_jou"]
    wie = [a["wie"] for a in voor_jou]
    assert "a@x.nl" in wie
    assert "oud@x.nl" not in wie, "een afgehandelde escalatie hoort hier niet meer"
    # Een openstaande storing is werk voor MIJ, niet voor Daniel. Wat hier wél
    # bij mag staan is de machine zelf: een starter die stilligt kan alleen hij
    # oplossen, en die staat hier omdat er geen hartslag is in deze test.
    assert all(a["soort"] != "storing" for a in voor_jou)
    assert all(a["soort"] in ("geld", "vertrek", "kan_niet_onderbouwen", "concept", "machine")
               for a in voor_jou)


def test_wie_nog_geen_bericht_kon_krijgen_staat_bij_daniel(monkeypatch):
    """Er gaat nooit twee post tegelijk naar dezelfde persoon; die wacht dus op hem."""
    beheer = _beheer(monkeypatch,
        {"kapot": {"status": "opgelost", "melders": ["a@x.nl", "b@x.nl"],
                   "bericht_verstuurd": ["a@x.nl"], "uitleg": "gemaakt",
                   "laatst": "2026-08-29T09:00:00+00:00",
                   "gerepareerd_op": "2026-08-29T11:00:00+00:00"}})
    voor_jou = beheer.werkplaats(user=None)["voor_jou"]
    assert any(a["soort"] == "concept" and a["wie"] == "b@x.nl" for a in voor_jou)


# ── het scherm mag niets beweren wat niet waar is ─────────────────────────
def test_een_teruggemelde_storing_staat_niet_meer_als_bezig(monkeypatch):
    """De starter zet een sessie pas tien minuten later op afgerond. Tot die tijd
    stond er "aan het werk" boven een kaart die de reparatie al beschreef."""
    from datetime import datetime, timezone
    nu = datetime.now(timezone.utc).isoformat()
    beheer = _beheer(monkeypatch,
        {"kapot": {"status": "opgelost", "melders": ["a@x.nl"], "uitleg": "gemaakt",
                   "laatst": "2026-08-29T09:00:00+00:00", "gerepareerd_op": nu}},
        {"kapot": {"status": "gestart", "gestart": nu}})
    assert beheer.werkplaats(user=None)["bezig"] is None


def test_een_escalatie_over_een_gerepareerde_storing_valt_van_de_lijst(monkeypatch):
    """Nagemeten op 29-08-2026: vier van de twaalf punten op Daniels lijst gingen
    over storingen die al opgelost waren. Zo verliest zo'n lijst zijn waarde."""
    beheer = _beheer(monkeypatch,
        {"klaar": {"status": "opgelost", "melders": ["a@x.nl"], "uitleg": "gemaakt",
                   "laatst": "2026-08-29T09:00:00+00:00",
                   "gerepareerd_op": "2026-08-29T11:00:00+00:00",
                   "bericht_verstuurd": ["a@x.nl"]},
         "nog niet": {"status": "open", "melders": ["b@x.nl"], "omschrijving": "x",
                      "laatst": "2026-08-29T09:00:00+00:00"}},
        {},
        [{"escalatie": "vertrek", "adres": "a@x.nl", "bug_sleutel": "klaar",
          "samenvatting": "dreigt te stoppen", "afgehandeld": False},
         {"escalatie": "vertrek", "adres": "b@x.nl", "bug_sleutel": "nog niet",
          "samenvatting": "dreigt ook", "afgehandeld": False}])
    wie = [a["wie"] for a in beheer.werkplaats(user=None)["voor_jou"]]
    assert "b@x.nl" in wie
    assert "a@x.nl" not in wie, "een escalatie over een gerepareerde storing bleef staan"


def test_een_escalatie_zonder_storing_blijft_gewoon_staan(monkeypatch):
    """Geld en 'hier heb ik geen antwoord op' hangen niet aan een storing."""
    beheer = _beheer(monkeypatch, {},
        {}, [{"escalatie": "geld", "adres": "a@x.nl", "samenvatting": "dubbel afgeschreven",
              "afgehandeld": False}])
    assert any(a["wie"] == "a@x.nl" for a in beheer.werkplaats(user=None)["voor_jou"])
