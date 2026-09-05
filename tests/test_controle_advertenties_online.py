"""De Juiste Toon, 05-09-2026: 20 advertenties groen in het dashboard, weg op Marktplaats.

Zijn overzicht zei van 274 artikelen dat ze op Marktplaats stonden. Zijn eigen
openbare verkoperspagina toonde er 317, en twintig van onze 274 zaten daar niet
bij; hun advertentiepagina gaf 404. Hij denkt dus dat die twintig te koop staan
en dat is niet zo — en als er een verkocht is, blijft dat artikel ondertussen wél
op Vinted en 2dehands staan.

De twee bestaande controles konden dit niet zien. De servercontrole vraagt een
pagina op met de cookies van de verkoper en Toon heeft geen Marktplaats-koppeling,
dus zijn advertenties kregen wel een stempel maar werden nooit nagekeken. De
controle in de extensie leest zijn eigen "Mijn advertenties", en dat overzicht is
bij een zakelijk account leeg. De openbare zoek-API heeft geen van beide bezwaren.

Hier wordt de vergelijking zelf beproefd, zonder Marktplaats en zonder database.

Draaien: python -m pytest tests/test_controle_advertenties_online.py
"""
import importlib.util
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "controle_ads", WORTEL / "scripts" / "controleer_advertenties_online.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def _actief(*paren):
    return [{"item_id": i, "platform_listing_id": n} for i, n in paren]


def test_een_advertentie_die_er_niet_meer_is_wordt_gemeld():
    verdwenen, hernummerd, los = C.vergelijk(
        _actief(("i1", "m111"), ("i2", "m222")),
        {"m111": "Kelim loper 74/42 cm"},
        {"i1": "Kelim loper 74/42 cm", "i2": "Miniatuur tapijtje 27/24 cm"},
        {"m111", "m222"},
    )
    assert [t for t, _, _ in verdwenen] == ["Miniatuur tapijtje 27/24 cm"]
    assert hernummerd == [] and los == []


def test_een_advertentie_onder_een_nieuw_nummer_is_geen_verdwenen_advertentie():
    """Marktplaats geeft bij opnieuw plaatsen een nieuw nummer. Dat is
    administratie, geen verkoopprobleem, en mag nooit als 'weg' gelden."""
    verdwenen, hernummerd, _ = C.vergelijk(
        _actief(("i1", "m111")),
        {"m999": "Kelim loper 74/42 cm"},
        {"i1": "Kelim loper 74/42 cm"},
        {"m111"},
    )
    assert verdwenen == []
    assert hernummerd == [("Kelim loper 74/42 cm", "m111", ["m999"])]


def test_titels_matchen_ongeacht_hoofdletters_en_leestekens():
    _, hernummerd, _ = C.vergelijk(
        _actief(("i1", "m111")),
        {"m999": "MINIATUUR  tapijt   31/25 cm"},
        {"i1": "Miniatuur tapijt 31/25 cm"},
        {"m111"},
    )
    assert hernummerd, "een dubbele spatie mag geen andere advertentie maken"


def test_advertenties_op_zijn_lijst_zonder_koppeling_worden_apart_geteld():
    """Bij Toon zijn dat er 63: eigen plaatsingen en Admarkt die wij nooit aan
    een artikel hebben gekoppeld. Geen storing, wel het vermelden waard."""
    _, _, los = C.vergelijk(
        _actief(("i1", "m111")),
        {"m111": "Kelim loper", "m222": "Iets wat hij zelf plaatste"},
        {"i1": "Kelim loper"},
        {"m111"},
    )
    assert los == [("m222", "Iets wat hij zelf plaatste")]


def test_alles_klopt_levert_niets_op():
    verdwenen, hernummerd, los = C.vergelijk(
        _actief(("i1", "m111")), {"m111": "Kelim loper"},
        {"i1": "Kelim loper"}, {"m111"})
    assert (verdwenen, hernummerd, los) == ([], [], [])


def test_het_script_schrijft_niets():
    """De afweging 'is deze advertentie echt weg' hoort niet in een losse
    controle. Eén ronde die niets vindt is geen bewijs — zie not_found_count in
    backend/services/polling.py en de scanbeveiliging in api/jobs.py."""
    bron = (WORTEL / "scripts" / "controleer_advertenties_online.py").read_text()
    # sys.path.insert is geen databaseschrijfactie; die laten we met rust.
    regels = [r for r in bron.splitlines() if "sys.path.insert" not in r]
    for verboden in (".update(", ".insert(", ".delete(", ".upsert("):
        treffers = [r.strip() for r in regels if verboden in r]
        assert not treffers, f"dit script hoort alleen te kijken, maar doet {verboden}: {treffers}"
