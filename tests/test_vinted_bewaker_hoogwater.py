"""De bewaker koppelt bij titelgenoten alleen een advertentie van ná de klik.

WAAROM DIT ER IS (17/18-10-2026, Janneke 31d28378)
Vanaf 1.0.394 kreeg vrijwel elke Vinted-plaatsing van Janneke "timed out" met
als laatste stap "plaatsen: op de knop geklikt, wachten op de advertentie".
Op haar Vinted-profiel stonden alle 17 gewoon online. Gemeten in de opdrachten
van drie klanten (Janneke, Toon 96e30080, 8f91a370): het invulscript ziet de
advertentie na de klik nooit zelf, elke geslaagde plaatsing werd ~181 s na de
laatste stap afgemeld door de bewaker in background.js (bgVindVintedAdvertentie).
Sinds 1.0.394 koppelt die bewaker niets bij titelgenoten, en Janneke heeft
bij 2.316 van haar 3.219 artikelen een titelgenoot.

Nu geeft het invulscript het hoogwater (hoogste advertentienummer vlak vóór de
klik) aan de achtergrond, en mag de bewaker bij titelgenoten de ENE advertentie
koppelen met deze titel en prijs die pas na de klik verscheen.

Echte gegevens van 17/18-10: "Winterjas Noppies maat 140", drie stukken
(48,50 jongens, 50,00 meisjes, 48,50 meisjes).
"""
import json

from tests.test_vinted_titelgenoten_hard_bewijs import _bron, _node, _stuk

VOOR = "cf894c1d"   # extensie 1.0.395
TITEL = "Winterjas Noppies maat 140"


def _kast(*advertenties):
    return [{"id": i, "title": t, "price": {"amount": f"{p:.2f}", "currency_code": "EUR"},
             "is_closed": False, "is_draft": False} for i, t, p in advertenties]


def _bewaker(commit, payload, kast, na_id=None):
    bron = _bron("extension/background.js", commit)
    return _node(f"""
const VINTED_ORIGINS = ["https://www.vinted.nl"];
const fetch = async (url) => ({{ ok: true, json: async () =>
  (String(url).includes("/users/current") ? {{ user: {{ id: 1 }} }} : {{ items: {json.dumps(kast)} }}) }});
{_stuk(bron, "function _vintedTitelSleutel(", "\n}\n")}
{_stuk(bron, "function _vintedTitelZonderSku(", "\n}\n")}
{_stuk(bron, "function _vintedPrijsKlopt(", "\n}\n")}
{_stuk(bron, "async function bgVindVintedAdvertentie(", "\n}\n")}
bgVindVintedAdvertentie({json.dumps(payload)}, {json.dumps(na_id)}).then((r) => console.log(JSON.stringify(r)));
""")


# d219ed5b (meisjes, 50 euro), om 21:18 geplaatst. Vlak voor de klik was
# 10419036363 (Tussenjas Noppies maat 74) de nieuwste in haar kast.
KAST_2122 = _kast((10419166038, TITEL, 50.0), (10419036363, "Tussenjas Noppies maat 74", 23.5),
                  (10418907120, "Winterjas Noppies maat 92", 48.5))
MEISJE_50 = {"title": TITEL, "price": 50.0, "_vinted_titelgenoten": 2}

# b33585d7 (meisjes, 48,50), 18-10 09:10. De advertentie van d219ed5b staat er al.
KAST_0914 = _kast((10422879568, TITEL, 48.5), (10419166038, TITEL, 50.0),
                  (10419036363, "Tussenjas Noppies maat 74", 23.5))
MEISJE_485 = {"title": TITEL, "price": 48.5, "_vinted_titelgenoten": 2,
              "_vinted_bezet": ["10419166038"]}


def test_oude_bewaker_liet_de_online_jas_als_mislukt_staan():
    assert _bewaker(VOOR, MEISJE_50, KAST_2122, 10419036363) is None
    assert _bewaker(VOOR, MEISJE_485, KAST_0914, 10419166038) is None


def test_nieuwe_bewaker_koppelt_de_advertentie_van_na_de_klik():
    assert _bewaker(None, MEISJE_50, KAST_2122, 10419036363) == "10419166038"
    assert _bewaker(None, MEISJE_485, KAST_0914, 10419166038) == "10422879568"


def test_nieuw_zonder_hoogwater_bij_titelgenoten_nog_steeds_niets():
    # Een invulscript van vóór deze versie stuurt geen hoogwater mee.
    assert _bewaker(None, MEISJE_50, KAST_2122) is None


def test_nieuw_een_oudere_advertentie_van_een_titelgenoot_telt_niet():
    # De klik leverde niets op; alleen de advertentie van het andere stuk staat er.
    kast = _kast((10419166038, TITEL, 48.5), (10419036363, "Tussenjas Noppies maat 74", 23.5))
    assert _bewaker(None, MEISJE_485, kast, 10419166038) is None


def test_nieuw_kiest_niet_tussen_twee_nieuwe_met_dezelfde_prijs():
    kast = _kast((10422879999, TITEL, 48.5), (10422879568, TITEL, 48.5),
                 (10419166038, TITEL, 50.0))
    assert _bewaker(None, MEISJE_485, kast, 10419166038) is None


def test_nieuw_een_nieuwe_met_een_andere_prijs_is_een_ander_stuk():
    kast = _kast((10422879568, TITEL, 50.0), (10419036363, "Tussenjas Noppies maat 74", 23.5))
    assert _bewaker(None, MEISJE_485, kast, 10419036363) is None


def test_nieuw_enig_stuk_wordt_nog_steeds_gevonden_met_en_zonder_hoogwater():
    stuk = {"title": "Tussenjas Kids Only maat 134", "price": 17.5}
    kast = _kast((10423075109, "Tussenjas Kids Only maat 134", 17.5),
                 (10422879568, TITEL, 48.5))
    assert _bewaker(None, stuk, kast) == "10423075109"
    assert _bewaker(None, stuk, kast, 10422879568) == "10423075109"


def test_invulscript_geeft_het_hoogwater_door_voor_de_klik():
    bron = _bron("extension/content/vinted.js", None)
    hoog = bron.index("const hoogwater = await vintedHoogwater()")
    bericht = bron.index('type: "VINTED_HOOGWATER"', hoog)
    assert bericht < bron.index("submitListing(", hoog)
    achter = _bron("extension/background.js", None)
    assert 'msg.type === "VINTED_HOOGWATER"' in achter
    assert achter.count("bgVindVintedAdvertentie(meta.payload || meta, meta.vintedNaId)") == 4
