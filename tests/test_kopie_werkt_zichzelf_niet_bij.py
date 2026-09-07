"""Een extensiekopie die zichzelf niet meer bijwerkt krijgt geen werk meer.

AANLEIDING (07-09-2026, De Juiste Toon). Zijn Chromebook draaide 1.0.260 van
28 augustus terwijl er 1.0.311 in de Chrome Web Store stond: 51 versies en tien
dagen achterstand. De harde ondergrens (1.0.244) liet die kopie gewoon door, dus
kreeg hij elke dag werk dat ze half afleverde — de drie rubrieken waar hij op
vastliep waren precies de drie die ná 1.0.260 zijn toegevoegd. Hij zag alleen dat
het "wederom" niet werkte.

De andere computers die die week werk deden stonden op 1.0.308, 1.0.309 en twee
op 1.0.311. Chrome werkt een kopie uit de Web Store dus wel degelijk bij; een
kopie die tien dagen stilstaat is met de hand geladen en zal nooit bijwerken.

Deze test bewaakt drie dingen: dat zo'n kopie herkend wordt, dat de kopieën die
gewoon een paar versies achterlopen er NIET onder vallen, en dat het dashboard
dezelfde grens gebruikt als de server.
"""
import re
from pathlib import Path

from backend.api.jobs import (ACHTERSTAND_GRENS, MINIMALE_SCANVERSIE,
                              _achterstand, _kopie_staat_stil)

WORTEL = Path(__file__).resolve().parents[1]

# De echte meting van 07-09-2026, uit extension_heartbeat.ext_version.
TOON = (1, 0, 260)
WEBSTORE = (1, 0, 311)
ANDERE_KLANTEN = [(1, 0, 308), (1, 0, 309), (1, 0, 311), (1, 0, 311)]


def test_de_oude_regel_liet_toons_kopie_gewoon_door():
    # Dit is de voor-meting: met alleen de harde ondergrens was er niets aan de
    # hand. Precies daarom liep hij er tien dagen mee door.
    assert not (TOON < MINIMALE_SCANVERSIE)


def test_toons_kopie_wordt_nu_herkend_als_stilstaand():
    assert _achterstand(TOON, WEBSTORE) == 51
    assert _achterstand(TOON, WEBSTORE) >= ACHTERSTAND_GRENS


def test_wie_gewoon_een_paar_versies_achterloopt_blijft_werken():
    # Deze drie stonden op dezelfde dag online en moesten door kunnen werken.
    for versie in ANDERE_KLANTEN:
        achter = _achterstand(versie, WEBSTORE)
        assert achter < ACHTERSTAND_GRENS, versie


def test_bij_twijfel_houden_we_niets_tegen():
    # Geen versie gemeld, of de Web Store gaf niets terug: dan weten we het niet,
    # en dan blokkeren we niet. Een kopie ten onrechte stilzetten is erger.
    assert _achterstand(None, WEBSTORE) is None
    assert _achterstand(TOON, None) is None
    assert _kopie_staat_stil(None) is None


def test_een_nieuwere_kopie_dan_de_winkel_telt_niet_als_achterstand():
    # Daniels eigen kopie is met de hand geladen en loopt juist vóór.
    assert _achterstand((1, 0, 312), WEBSTORE) == 0


def test_een_andere_hoofdreeks_telt_altijd_als_ver_weg():
    assert _achterstand((1, 0, 311), (1, 1, 0)) >= ACHTERSTAND_GRENS


def test_de_grens_is_ruimer_dan_een_paar_dagen_uitgaven():
    # Er gaan ongeveer vijf versies per dag uit. Onder de tien zou een gewone
    # drukke dag al iemand blokkeren die morgen vanzelf bijwerkt.
    assert ACHTERSTAND_GRENS >= 10


def test_het_dashboard_gebruikt_dezelfde_grens_als_de_server():
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    # De grens komt van de server mee; het scherm mag hem niet zelf verzinnen.
    assert "blokkeer_achterstand" in app
    assert "extVersionStaatStil()" in app
    # En de standaardwaarde in het scherm (voor het antwoord binnen is) moet
    # gelijk zijn aan die van de server, anders zegt het scherm iets anders dan
    # de uitgifte doet.
    m = re.search(r"let _blokkeerAchterstand = (\d+);", app)
    assert m, "_blokkeerAchterstand niet gevonden in app.html"
    assert int(m.group(1)) == ACHTERSTAND_GRENS


def test_het_venster_biedt_geen_toch_doorgaan_bij_een_stilstaande_kopie():
    # "Continue anyway" zou een lege belofte zijn: de server geeft deze kopie
    # toch geen werk. Precies daarmee is Toon tien dagen doorgelopen.
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    blok = app.split("function renderExtSetup()")[1][:2600]
    assert "ext-outdated-skip" in blok
    assert "staatStil ? 'none' : 'block'" in blok


def test_de_uitgifte_blokkeert_een_stilstaande_kopie():
    bron = (WORTEL / "backend" / "api" / "jobs.py").read_text(encoding="utf-8")
    blok = bron.split("def get_pending_jobs(")[1][:4000]
    assert "_kopie_staat_stil(gemeld)" in blok
    # ... en geeft niets terug, net als bij de harde ondergrens.
    assert blok.count("return []") >= 2
