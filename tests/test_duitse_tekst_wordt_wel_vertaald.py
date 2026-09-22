"""Een Duitse advertentie mag niet onvertaald op Marktplaats komen.

GEMETEN (22-09-2026, Toon van De Juiste Toon). Zijn lederhose stond in het Duits
op marktplaats.nl: "Herren Original Trachten Lederhosen / Größe 50 / Farbe Khaki
/ Material Leder/Wildleder". Daniel zag het en meldde het: "Hij heeft tekst in
het Duits vanuit Vinted geplaatst naar mp."

DE OORZAAK, WOORD VOOR WOORD NAGETELD OP ZIJN ECHTE TEKST. `lijkt_al_in_taal`
kende twee talen: Nederlands en Engels. Toon neemt de Duitse tekst van zijn
leverancier over in zijn Vinted-advertentie en zet er zijn eigen Nederlandse
winkelblok onder ("Kijk op onze webshop ... Locatie: Mon Plaisir 19,
Etten-Leur"). Die twee samen leverden 8 Nederlandse stopwoorden op — allemaal uit
dat winkelblok — en 0 Engelse. Van het Duits zag de functie NIETS, want die taal
bestond er niet. De regel "nl >= 3 en nl >= en * 2" kwam dus uit op "staat al in
het Nederlands", de vertaling werd overgeslagen, en de Duitse tekst ging
ongewijzigd de deur uit. Dezelfde fout als op 08-09 en 12-09, alleen met een
taal die we niet kenden.

Deze proef gebruikt zijn echte advertentietekst, en draait `localiseer_sync` met
een nagebootste vertaaldienst: zo is te zien OF er vertaald wordt, zonder dat er
een model aan te pas komt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402

# Zijn echte advertentie, overgenomen van de schermafdruk van 22-09-2026 19:16.
DUITS = """Herren Original Trachten Lederhosen
Größe 50
Farbe Khaki
Material Leder/Wildleder
Flach gemessen 53 Zentimeter siehe letztes Foto
Mehrere Modelle auf Lager Damen/Herren
Info Dejuistetoon

#dejuistetoon
#leer
#suede
#lederhosen
#trachten"""

# Zijn eigen winkelblok, in het Nederlands, dat hij onder elke advertentie zet.
WINKELBLOK = """Kijk op onze webshop Dejuistetoon voor het volledige en actuele aanbod.

Wil je onze collectie in het echt bekijken , maak een afspraak.

Alle dagen op afspraak | Do & Za 10.00 uur tot 17.00 uur

Locatie: Mon Plaisir 19, Etten-Leur.
telefoon: +31 6 5396 0664"""

TOONS_ADVERTENTIE = DUITS + "\n\n" + WINKELBLOK

# De Nederlandse tekst uit de proef van 12-09: die mag juist NIET alsnog langs
# het model, anders komt die fout terug (het model draaide de richting om).
NEDERLANDS = (
    "Kenmerkt zich door geometrische patronen en levendige kleuren\n\n"
    "In vaal rode kleur met blauw ecru en oranje accenten\n\n"
    "Afmeting: 135/80 cm\n\nDejuistetoon Etten-Leur"
)
ENGELS = (
    "Black MyProtein shorts for men, size XL. This item is new with tags and "
    "comes from a smoke free home. Please check the measurements in the photos."
)


# ── De herkenning zelf ──────────────────────────────────────────────────────
def test_duits_met_nederlands_winkelblok_telt_niet_als_nederlands():
    assert cl.lijkt_al_in_taal(TOONS_ADVERTENTIE, "nl") is False


def test_duits_telt_ook_niet_als_engels():
    assert cl.lijkt_al_in_taal(TOONS_ADVERTENTIE, "en") is False


def test_zijn_winkelblok_op_zichzelf_is_gewoon_nederlands():
    assert cl.lijkt_al_in_taal(WINKELBLOK, "nl") is True


def test_nederlands_blijft_nederlands():
    assert cl.lijkt_al_in_taal(NEDERLANDS, "nl") is True


def test_engels_blijft_engels():
    assert cl.lijkt_al_in_taal(ENGELS, "en") is True
    assert cl.lijkt_al_in_taal(ENGELS, "nl") is False


def test_grosse_telt_mee_als_duits_woord():
    """ss-scherp hoorde in de tekenklasse: "groesse" viel anders uiteen.

    Deze tekst heeft evenveel Duitse als Nederlandse woorden. Telt het Duitse
    woord niet mee, dan wint het Nederlands met 3 tegen 0 en zou de tekst
    onvertaald doorgaan.
    """
    tekst = "Gr\u00f6\u00dfe 50 Gr\u00f6\u00dfe 52 Gr\u00f6\u00dfe 54 het een voor"
    assert cl.lijkt_al_in_taal(tekst, "nl") is False


def test_duitse_markers_die_ook_nederlands_zijn_staan_er_niet_in():
    """Een marker die in beide talen bestaat zet juist de vertaling stil."""
    for woord in ("die", "den", "leder", "material", "artikel", "lager",
                  "gewicht", "kinder"):
        assert woord not in cl._STOPWOORDEN_DE, woord


# ── Het hele pad: wordt er ook echt vertaald? ───────────────────────────────
def _met_nepvertaler(monkeypatch):
    geroepen = []

    def _nep(text, target_lang, brand=None):
        geroepen.append((text, target_lang))
        return "VERTAALD: " + text

    monkeypatch.setattr(cl, "_vertaal", _nep)
    return geroepen


def test_zijn_lederhose_gaat_wel_langs_de_vertaling(monkeypatch):
    geroepen = _met_nepvertaler(monkeypatch)
    item = {"title": "Heren originele trachten Lederhosen",
            "description": TOONS_ADVERTENTIE}
    uit = cl.localiseer_sync(dict(item), "marktplaats")

    assert geroepen, "de Duitse tekst hoort naar de vertaaldienst te gaan"
    assert all(taal == "nl" for _, taal in geroepen), geroepen
    assert uit["description"].startswith("VERTAALD: ")
    assert uit[cl.TAAL_VELD] == "nl"


def test_hetzelfde_geldt_voor_2dehands(monkeypatch):
    geroepen = _met_nepvertaler(monkeypatch)
    cl.localiseer_sync({"title": "Lederhosen", "description": TOONS_ADVERTENTIE}, "2dehands")
    assert geroepen, "ook op 2dehands hoort dit vertaald te worden"


def test_een_nederlandse_advertentie_gaat_nog_steeds_niet_langs_het_model(monkeypatch):
    """De reparatie van 12-09 mag hier niet onder lijden."""
    geroepen = _met_nepvertaler(monkeypatch)
    item = {"title": "Handgeknoopt Perzisch Shiraz wollen tapijt 135/80 cm",
            "description": NEDERLANDS}
    uit = cl.localiseer_sync(dict(item), "marktplaats")

    assert geroepen == [], "Nederlandse tekst hoort niet naar de vertaaldienst te gaan"
    assert uit["description"] == NEDERLANDS
    assert uit[cl.TAAL_VELD] == "nl"
