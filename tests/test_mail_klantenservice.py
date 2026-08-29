"""De lijn klantenservice ↔ developer, en wat er bij Daniel terechtkomt.

De rolverdeling ligt vast (docs/team-notes.md, 29-08-2026): Daniel is CEO, de
mailagent is de klantenservicemedewerker, Claude Code is de developer. Daaruit
volgen drie afspraken die dit bestand bewaakt:

  1. Wat klanten melden komt bij de DEVELOPER terecht, niet bij Daniel — en met
     een duidelijk seintje wanneer iets met zekerheid gerepareerd moet worden.
  2. Wat de developer terugmeldt, stuurt wat de klantenservice schrijft. Anders
     zegt hij "ik kijk ernaar" terwijl het gisteren gerepareerd is.
  3. Daniel wordt alleen gestoord voor geld, een klant die dreigt te stoppen,
     een storing bij meerdere mensen, en iets wat niet te onderbouwen is — door
     hemzelf zo gekozen.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import mail_analyse as M  # noqa: E402


@pytest.fixture
def opslag(monkeypatch):
    """De sleutel-waardetabel vervangen door een gewone dict."""
    kast: dict = {}
    monkeypatch.setattr(M.L, "_db_lees", lambda naam, standaard: kast.get(naam, standaard))
    monkeypatch.setattr(M.L, "_db_schrijf", lambda naam, inhoud: kast.__setitem__(naam, inhoud) or True)
    monkeypatch.setattr(M.L, "is_klant", lambda adres: True)
    # Het slot op dubbele concepten kijkt in de echte postbus; die is er hier niet.
    # Standaard "er mag een concept", zodat elke test over de terugkoppeling gaat
    # en niet over de mailverbinding.
    monkeypatch.setattr(M.L, "_waarom_geen_concept", lambda adres, inkomend: None)
    return kast


def _bericht(mid="<a@b.nl>", adres="klant@voorbeeld.nl", richting="in"):
    return {"message_id": mid, "richting": richting, "adres": adres,
            "onderwerp": "Probleem", "wanneer": "2026-08-29T09:00:00+00:00",
            "tekst": "Het lukt niet"}


def _oordeel(mid="<a@b.nl>", **kw):
    basis = {"message_id": mid, "thema": "publiceren-mislukt", "stemming": "neutraal",
             "storing": True, "bug_sleutel": "publiceren-mislukt-vinted",
             "escalatie": "", "samenvatting": "Zijn advertenties komen niet op Vinted."}
    basis.update(kw)
    return basis


# ------------------------------------------------- 1. het postvak van de developer
def test_een_melding_komt_bij_de_developer_terecht(opslag):
    M._verwerk([_bericht()], [_oordeel()])
    signalen = opslag["bug_signalen"]
    assert "publiceren-mislukt-vinted" in signalen
    assert signalen["publiceren-mislukt-vinted"]["melders"] == ["klant@voorbeeld.nl"]


def test_twee_mensen_met_hetzelfde_probleem_is_een_patroon(opslag):
    M._verwerk([_bericht("<1@x>", "een@x.nl")], [_oordeel("<1@x>")])
    _, escalaties = M._verwerk([_bericht("<2@x>", "twee@x.nl")], [_oordeel("<2@x>")])
    assert any(e["escalatie"] == "storing_bij_meerderen" for e in escalaties)


def test_een_boze_klant_zet_het_seintje_moet_zeker(opslag):
    """Dit is het signaal aan de developer: niet 'als het uitkomt'."""
    M._verwerk([_bericht()], [_oordeel(stemming="boos")])
    s = opslag["bug_signalen"]["publiceren-mislukt-vinted"]
    assert s["moet_zeker"] is True
    assert any("boos" in r for r in s["waarom_zeker"])


def test_een_gewone_melding_is_nog_geen_voorrang(opslag):
    M._verwerk([_bericht()], [_oordeel()])
    assert not opslag["bug_signalen"]["publiceren-mislukt-vinted"].get("moet_zeker")


def test_onze_eigen_uitgaande_mail_telt_niet_als_melding(opslag):
    M._verwerk([_bericht(richting="uit")], [_oordeel()])
    assert opslag.get("bug_signalen") == {}


# ------------------------------------------------- 2. de developer stuurt het concept
def test_wat_de_developer_meldt_stuurt_het_concept(opslag):
    M._verwerk([_bericht()], [_oordeel()])
    M.opgelost(type("A", (), {"sleutel": "publiceren-mislukt-vinted",
                              "uitleg": "Vinted krijgt nu alle foto's mee."})())
    stand = M.stand_van_de_storingen("het publiceren mislukt bij vinted")
    assert "IS GEREPAREERD" in stand
    assert "alle foto's" in stand


def test_een_bekende_storing_belooft_nooit_een_datum(opslag):
    M._verwerk([_bericht()], [_oordeel(stemming="boos")])
    stand = M.stand_van_de_storingen("het publiceren mislukt bij vinted")
    assert "voorrang" in stand
    assert "GEEN datum" in stand


def test_zonder_bekende_storing_krijgt_het_concept_niets_opgelegd(opslag):
    M._verwerk([_bericht()], [_oordeel()])
    assert M.stand_van_de_storingen("wat kost het abonnement?") == ""


def test_de_klantenservice_vraagt_dit_ook_echt_op():
    """De kennis van de developer moet in de opdracht aan het model belanden,
    anders is de hele lijn een dode letter."""
    bron = (Path(__file__).parent.parent / "scripts" / "leadgen_mail.py").read_text()
    schrijver = bron.split("def _slim_concept")[1].split("\ndef ")[0]
    assert "stand_van_de_storingen" in schrijver
    assert "+ (stand" in schrijver


def test_een_gerepareerde_storing_die_terugkomt_gaat_weer_open(opslag):
    M._verwerk([_bericht()], [_oordeel()])
    M.opgelost(type("A", (), {"sleutel": "publiceren-mislukt-vinted",
                              "uitleg": "Gerepareerd."})())
    M._verwerk([_bericht("<later@x>", "ander@x.nl")], [_oordeel("<later@x>")])
    assert opslag["bug_signalen"]["publiceren-mislukt-vinted"]["status"] == "open"


# ------------------------------------------------- 3. wanneer Daniel gestoord wordt
@pytest.mark.parametrize("reden", ["geld", "vertrek", "kan_niet_onderbouwen"])
def test_alleen_de_vier_gekozen_redenen_bereiken_daniel(opslag, reden):
    _, escalaties = M._verwerk([_bericht()], [_oordeel(escalatie=reden, storing=False,
                                                        bug_sleutel="")])
    assert [e["escalatie"] for e in escalaties] == [reden]


def test_een_gewone_vraag_stoort_daniel_niet(opslag):
    _, escalaties = M._verwerk([_bericht()],
                               [_oordeel(storing=False, bug_sleutel="", escalatie="")])
    assert escalaties == []


def test_alleen_geld_en_vertrek_zijn_spoed():
    """De rest staat in het dashboard; daar wil hij geen mailtje voor."""
    assert set(M.SPOED) == {"geld", "vertrek"}
    assert set(M.ESCALATIE_REDENEN) == {"geld", "vertrek", "storing_bij_meerderen",
                                        "kan_niet_onderbouwen"}


# ------------------------------------------------- terugkoppeling naar de klant
def test_melders_krijgen_bericht_als_het_gerepareerd_is(opslag, monkeypatch):
    M._verwerk([_bericht()], [_oordeel()])
    M.opgelost(type("A", (), {"sleutel": "publiceren-mislukt-vinted",
                              "uitleg": "Vinted krijgt nu alle foto's mee."})())
    monkeypatch.setattr(M, "_herstelbericht",
                        lambda adres, signalen: "Hi, je meldde dat het publiceren niet "
                                                "lukte. Dat is nu gerepareerd, kijk je even mee?")
    gezet = []
    monkeypatch.setattr(M.L, "_zet_concept_klaar",
                        lambda lead, *a, **k: gezet.append(lead["email"]) or True)
    assert M.bericht_over_reparaties() == 1
    assert gezet == ["klant@voorbeeld.nl"]
    # en niet nog een keer bij de volgende ronde
    assert M.bericht_over_reparaties() == 0


def test_zonder_uitleg_van_de_developer_gaat_er_niets_uit(opslag, monkeypatch):
    """Een reparatie zonder uitleg levert een lege mail op; dan liever niets."""
    M._verwerk([_bericht()], [_oordeel()])
    signalen = opslag["bug_signalen"]
    signalen["publiceren-mislukt-vinted"]["status"] = "opgelost"
    monkeypatch.setattr(M.L, "_zet_concept_klaar",
                        lambda *a, **k: pytest.fail("er mag niets uitgaan"))
    assert M.bericht_over_reparaties() == 0


def test_de_developer_leest_dit_postvak_bij_elke_sessie():
    """Zonder deze afspraak in CLAUDE.md komt er nooit iemand kijken."""
    afspraken = (Path(__file__).parent.parent / "CLAUDE.md").read_text()
    assert "mail_analyse.py bugs" in afspraken
    assert "mail_analyse.py opgelost" in afspraken


def test_onze_eigen_seintjes_tellen_niet_als_binnengekomen_post(monkeypatch):
    """Het weekbericht, de trendmotor en de alarmen sturen we aan onszelf. Die
    als klantpost tellen vervuilt de thema's en de stemming meteen."""
    bron = (Path(__file__).parent.parent / "scripts" / "mail_analyse.py").read_text()
    ophalen = bron.split("def _nieuwe_post")[1].split("\ndef ")[0]
    assert 'adres == gebruiker.lower()' in ophalen


def test_mislukt_opslaan_wordt_hard_gemeld(capsys, monkeypatch):
    """Anders meldt hij '25 beoordeeld' terwijl er niets is opgeslagen."""
    monkeypatch.setattr(M.L, "_db_schrijf", lambda naam, inhoud: False)
    assert M._schrijf("mail_analyse", {}) is False
    assert "NIET opgeslagen" in capsys.readouterr().out


def test_vier_reparaties_voor_dezelfde_persoon_worden_een_mail(opslag, monkeypatch):
    """HIER GING HET MIS (29-08-2026). Er ligt nooit meer dan één concept tegelijk
    voor dezelfde persoon. Ging de terugkoppeling per storing, dan kreeg iemand met
    vier gerepareerde meldingen er één en bleven de andere drie hangen tot Daniel
    die eerste mail had verstuurd. Egbert had er vier klaarstaan en hoorde niets —
    juist de klant die dreigde te stoppen."""
    signalen = {}
    for i in range(4):
        signalen[f"storing{i}"] = {
            "melders": ["egbert@x.nl"], "status": "opgelost", "uitleg": f"reparatie {i}",
            "omschrijving": f"probleem {i}", "bericht_verstuurd": []}
    opslag["bug_signalen"] = signalen
    meegegeven = []
    monkeypatch.setattr(M, "_herstelbericht",
                        lambda adres, sn: meegegeven.append(len(sn)) or "Hi, alles is gemaakt.")
    gezet = []
    monkeypatch.setattr(M.L, "_zet_concept_klaar",
                        lambda lead, *a, **k: gezet.append(lead["email"]) or True)
    assert M.bericht_over_reparaties() == 1, "er hoort één mail te komen, geen vier"
    assert meegegeven == [4], "alle vier de reparaties horen in die ene mail te staan"
    assert gezet == ["egbert@x.nl"]
    # en alle vier staan als afgehandeld genoteerd, dus geen herhaling
    assert all(s["bericht_verstuurd"] == ["egbert@x.nl"] for s in signalen.values())
    assert M.bericht_over_reparaties() == 0


def test_er_wordt_geen_tekst_geschreven_die_toch_wordt_weggegooid(opslag, monkeypatch):
    """Het slot werd pas NA het schrijven geraadpleegd. Dat kostte elke ronde vier
    modelaanroepen waarvan de tekst meteen de prullenbak in ging, elke tien minuten."""
    opslag["bug_signalen"] = {"kapot": {"melders": ["a@x.nl"], "status": "opgelost",
                                        "uitleg": "gemaakt", "omschrijving": "x",
                                        "bericht_verstuurd": []}}
    monkeypatch.setattr(M.L, "_waarom_geen_concept",
                        lambda adres, inkomend: "er ligt al een concept voor deze persoon")
    monkeypatch.setattr(M, "_herstelbericht",
                        lambda *a: pytest.fail("er is een mail geschreven die toch niet mag"))
    assert M.bericht_over_reparaties() == 0
