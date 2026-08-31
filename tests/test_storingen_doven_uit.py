"""Meldingen die niet meer spelen moeten vanzelf van de lijst — zonder klantmail.

WAAROM DIT ER IS (31-08-2026, Daniel)
Daniel, over het statusbeeld dat de developer hem gaf: "er is namelijk niks meer
mbt zilverwebsite wat openstaat op dit moment." Op de lijst stonden op dat
moment zeventien meldingen van info@zilverwebsite.nl als "open", de oudste van
17 augustus.

De oorzaak was een gat in het ontwerp. De lijst ging maar één kant op: klantmail
zette storingen erop, en alleen de developer kon ze eraf halen met `opgelost` of
`afgewezen`. Handelde Daniel iets zelf af, of loste het vanzelf op, dan bleef het
eeuwig staan. Gevolg: de automatische starter ging op spoken af, en het
statusbeeld was structureel te somber.

DE GRENS DIE HIER BEWAAKT WORDT. Uitdoven is geen reparatie. Wie een oude
melding met `opgelost` afsluit, stuurt de klant post over een probleem dat hij
allang vergeten is — precies het soort mail dat op 31-08 misging en waarvoor de
hele mailflow die middag is stilgelegd. Daarom een aparte status `verlopen`, die
nooit tot een bericht leidt.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mail_analyse as M  # noqa: E402

NU = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
ZW = "info@zilverwebsite.nl"
EG = "info@papas-plectrums.nl"


def _melding(laatst_dagen_geleden, melders=(ZW,), status="open"):
    return {
        "eerst": (NU - timedelta(days=laatst_dagen_geleden + 2)).isoformat(),
        "laatst": (NU - timedelta(days=laatst_dagen_geleden)).isoformat(),
        "status": status,
        "uitleg": "",
        "melders": list(melders),
        "omschrijving": "Advertenties missen tekst en foto's.",
        "bericht_verstuurd": [],
    }


def _contact_op(dagen_geleden):
    return (NU - timedelta(days=dagen_geleden)).timestamp()


def test_stilgevallen_melding_dooft_uit():
    """DE KERN. De klant heeft ná zijn klacht nog contact gehad en is er niet op
    teruggekomen."""
    signalen = {"publiceren-onvolledig": _melding(20)}
    staat = {ZW: {"laatste_inkomend": _contact_op(3)}}

    uit = M._verloop_kandidaten(signalen, staat, nu=NU)

    assert [s for s, _ in uit] == ["publiceren-onvolledig"]


def test_zonder_contact_daarna_blijft_hij_staan():
    """Niets weten is geen reden om iets weg te halen. Iemand die drie weken op
    vakantie is heeft zijn storing niet ingetrokken."""
    signalen = {"publiceren-onvolledig": _melding(40)}
    staat = {ZW: {"laatste_inkomend": _contact_op(45)}}

    assert M._verloop_kandidaten(signalen, staat, nu=NU) == []


def test_een_zware_melding_krijgt_veel_langer_de_tijd():
    """Bij een klant die boos was of dreigde te stoppen, of bij een storing die
    meerdere mensen melden, is stilte veel minder overtuigend. Die houden we
    drie weken vast in plaats van één."""
    zwaar = _melding(10)
    zwaar["moet_zeker"] = True
    zwaar["waarom_zeker"] = ["een klant dreigt hierom te stoppen"]
    signalen = {"automatisch-verversen-mislukt-popup": zwaar}
    staat = {ZW: {"laatste_inkomend": _contact_op(1)}}

    assert M._verloop_kandidaten(signalen, staat, nu=NU) == [], (
        "een zware melding van 10 dagen oud mag nog niet uitdoven")

    zwaar["laatst"] = (NU - timedelta(days=25)).isoformat()
    assert len(M._verloop_kandidaten(signalen, staat, nu=NU)) == 1, (
        "na drie weken stilte mag ook een zware melding uitdoven")


def test_een_gewone_melding_dooft_na_een_week():
    """Zonder deze kortere grens bleef alles staan: gemeten op 31-08-2026 zaten
    de meeste meldingen van Zilverwebsite op 12 of 13 dagen, net binnen de oude
    grens van 14, terwijl er niets meer speelde."""
    signalen = {"maar-een-foto-geimporteerd": _melding(9)}
    staat = {ZW: {"laatste_inkomend": _contact_op(1)}}

    assert len(M._verloop_kandidaten(signalen, staat, nu=NU)) == 1


def test_een_verse_melding_dooft_nooit_uit():
    signalen = {"inloggen-mislukt": _melding(1)}
    staat = {ZW: {"laatste_inkomend": _contact_op(0)}}

    assert M._verloop_kandidaten(signalen, staat, nu=NU) == []


def test_bij_twee_melders_moet_iedereen_erover_heen_zijn():
    """Eén stille melder is geen bewijs dat het over is — de ander kan er nog
    middenin zitten. Dat was het geval bij Dennis en Egbert, die wekenlang
    dezelfde Marktplaats-storing meldden."""
    signalen = {"marktplaats-niet-ingelogd": _melding(20, melders=(ZW, EG))}
    staat = {ZW: {"laatste_inkomend": _contact_op(2)}}  # Egbert ontbreekt

    assert M._verloop_kandidaten(signalen, staat, nu=NU) == []

    staat[EG] = {"daniel_antwoordde": _contact_op(1)}
    assert [s for s, _ in M._verloop_kandidaten(signalen, staat, nu=NU)] == [
        "marktplaats-niet-ingelogd"]


def test_antwoord_van_daniel_telt_ook_als_contact():
    """Daniel handelt dingen zelf af. Dat is precies het geval dat de lijst
    nooit meekreeg."""
    signalen = {"publiceren-onvolledig": _melding(20)}
    staat = {ZW: {"daniel_antwoordde": _contact_op(4)}}

    assert [s for s, _ in M._verloop_kandidaten(signalen, staat, nu=NU)] == [
        "publiceren-onvolledig"]


def test_al_afgehandelde_meldingen_worden_niet_opnieuw_aangeraakt():
    signalen = {"a": _melding(30, status="opgelost"),
                "b": _melding(30, status="afgewezen"),
                "c": _melding(30, status="verlopen")}
    staat = {ZW: {"laatste_inkomend": _contact_op(1)}}

    assert M._verloop_kandidaten(signalen, staat, nu=NU) == []


def test_uitdoven_stuurt_nooit_bericht_naar_de_klant(monkeypatch):
    """DE BELANGRIJKSTE PROEF. `opgelost` zet melders in de rij voor een mail;
    `verlopen` mag dat nooit doen. Zou uitdoven mail veroorzaken, dan kreeg
    Zilverwebsite in één klap zeventien berichten over vergeten problemen."""
    bewaard = {}
    signalen = {"publiceren-onvolledig": _melding(20)}
    monkeypatch.setattr(M, "bugs", lambda: signalen)
    monkeypatch.setattr(M, "_lees", lambda naam, standaard=None: (
        {ZW: {"laatste_inkomend": _contact_op(2)}} if naam == "mail_state" else standaard))
    monkeypatch.setattr(M, "_schrijf", lambda naam, inhoud: bewaard.update({naam: inhoud}) or True)

    aantal = M.laat_verlopen_uitdoven()

    assert aantal == 1
    s = bewaard["bug_signalen"]["publiceren-onvolledig"]
    assert s["status"] == "verlopen"
    assert s.get("bericht_verstuurd") == [], "er staat een klant in de rij voor post"
    assert not s.get("uitleg"), (
        "een uitleg zou dit als reparatie laten tellen, en dan gaat er wél mail uit")
    assert not s.get("gerepareerd_op")


def test_uitgedoofde_melding_telt_niet_meer_als_werk(monkeypatch):
    """De automatische starter kijkt naar status 'open'. Zonder dit blijft hij
    sessies openen voor storingen die niet meer bestaan."""
    signalen = {"oud": _melding(30), "vers": _melding(1)}
    monkeypatch.setattr(M, "bugs", lambda: signalen)
    monkeypatch.setattr(M, "_lees", lambda naam, standaard=None: (
        {ZW: {"laatste_inkomend": _contact_op(0)}} if naam == "mail_state" else standaard))
    monkeypatch.setattr(M, "_schrijf", lambda naam, inhoud: True)

    M.laat_verlopen_uitdoven()

    nog_open = [k for k, s in signalen.items() if s.get("status") == "open"]
    assert nog_open == ["vers"]
