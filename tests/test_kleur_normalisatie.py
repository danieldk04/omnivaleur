"""De kleur die de server meestuurt is de kleur die Marktplaats aanbiedt.

WAAROM DIT ER IS (Toon, dejuistetoon, 03-09-2026). Marktplaats biedt in het
Kleur-veld alleen de kale grondvorm aan; verkopers schrijven "bruine", "rode",
"crème", "lichtblauw", "Beige bruin". Zo'n woord matcht op geen enkele optie, het
verplichte veld blijft leeg, en dan doet de plaatsknop van Marktplaats stil niets
(gemeten 21-08-2026). Bij Toon raakte dat 175 van zijn 1.024 artikelen.

De extensie kan dit sinds 1.0.282 zelf, maar die bereikt de verkoper pas nadat de
Chrome Web Store hem heeft goedgekeurd. De server bereikt hem meteen. Twee plekken
dus, en die moeten hetzelfde zeggen — daar gaat de laatste test over: die leest de
tabellen uit shared.js en legt ze naast die in Python.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from backend.services.kleur import (  # noqa: E402
    COLOUR_NL, KLEUR_BASIS, KLEUR_SYNONIEM, normaliseer_kleur,
)

# De 59 kleurwaarden die Toon echt in zijn kast heeft, met hun aantallen.
TOON_KLEUREN = [
    ("rood", 81), ("bruin", 78), ("beige", 52), ("ecru", 52), ("bruine", 41),
    ("groen", 41), ("zwart", 30), ("roze", 28), ("blauw", 27), ("zwarte", 20),
    ("oranje", 19), ("grijs", 18), ("rode", 16), ("taupe", 16), ("groene", 15),
    ("geel", 15), ("crème", 13), ("paars", 11), ("witte", 10), ("goud", 9),
    ("wit", 9), ("lichtblauw", 7), ("bordeaux", 7), ("blauwe", 7), ("Bruin", 5),
    ("khaki", 5), ("olijfgroene", 4), ("zalm", 4), ("donkerblauw", 4),
    ("olijfgroen", 4), ("Meerkleurig", 4), ("Wit", 3), ("paarse", 3),
    ("grijze", 3), ("camel", 2), ("gouden", 2), ("gele", 2), ("donkergroene", 2),
    ("Rood", 2), ("donkergroen", 2), ("Blauw", 1), ("mint", 1),
    ("Beige bruin", 1), ("donkergrijs", 1), ("kaki", 1), ("Zwart, Rood", 1),
    ("lichtblauwe", 1), ("lila", 1), ("red", 1), ("bruin olijfgroen", 1),
    ("Zwart", 1), ("Donkergroen zwart", 1), ("Kleurrijk", 1), ("Taupe", 1),
    ("Bruin taupe", 1), ("divers", 1), ("Ecru", 1), ("Grijs", 1), ("marine", 1),
]

# Wat Marktplaats aanbiedt.
MP_KLEUREN = set(KLEUR_BASIS.values())


def test_elke_kleur_van_toon_wordt_een_naam_die_marktplaats_kent():
    """Alle 59, zonder uitzondering. Eén die overblijft is een artikel dat vastloopt."""
    blijft_liggen = []
    artikelen = 0
    for waarde, aantal in TOON_KLEUREN:
        net = normaliseer_kleur(waarde)
        if net not in MP_KLEUREN:
            blijft_liggen.append(f"{waarde} ({aantal}x) -> {net!r}")
            artikelen += aantal
    assert not blijft_liggen, (
        f"{artikelen} artikelen lopen hierop vast: {', '.join(blijft_liggen)}"
    )


@pytest.mark.parametrize("waarde,verwacht", [
    ("bruine", "Bruin"), ("zwarte", "Zwart"), ("rode", "Rood"), ("witte", "Wit"),
    ("gele", "Geel"), ("grijze", "Grijs"), ("gouden", "Goud"), ("paarse", "Paars"),
    ("lichtblauw", "Blauw"), ("donkerblauw", "Blauw"), ("olijfgroene", "Groen"),
    ("donkergroen", "Groen"), ("crème", "Wit"), ("ecru", "Wit"), ("taupe", "Beige"),
    ("camel", "Beige"), ("marine", "Blauw"), ("zalm", "Roze"), ("lila", "Paars"),
    ("kaki", "Groen"), ("Meerkleurig", "Meerkleurig"), ("divers", "Meerkleurig"),
    ("Beige bruin", "Beige"), ("Bruin taupe", "Bruin"), ("Zwart, Rood", "Zwart"),
    ("bruin olijfgroen", "Bruin"), ("Donkergroen zwart", "Groen"), ("red", "Rood"),
])
def test_de_verwachte_grondvorm(waarde, verwacht):
    assert normaliseer_kleur(waarde) == verwacht


@pytest.mark.parametrize("waarde", ["katoen", "wol", "handgemaakt", "", None, "   ", "42"])
def test_wat_geen_kleur_is_blijft_met_rust(waarde):
    """Liever niets dan een verzonnen kleur: de eigen tekst van de verkoper wint."""
    assert normaliseer_kleur(waarde) == ""


def test_server_en_extensie_kennen_dezelfde_kleuren():
    """Twee plekken die hetzelfde moeten zeggen, dus hier vergeleken.

    Loopt dit uit elkaar, dan krijgt de ene verkoper wél zijn advertentie en de
    andere niet, afhankelijk van welke extensieversie toevallig op zijn computer
    staat. Dat is precies het soort verschil dat niemand terugvindt.
    """
    js = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")

    def tabel(naam):
        blok = re.search(rf"const {naam} = \{{(.*?)\n  \}};", js, re.S)
        assert blok, f"{naam} niet gevonden in shared.js"
        # Commentaarregels eruit: die noemen soms een veldnaam met een waarde
        # ("plaidsKleur: \"Meerkleurig\"") en dat is geen tabelregel.
        inhoud = "\n".join(
            r for r in blok.group(1).splitlines() if not r.lstrip().startswith("//")
        )
        uit = {}
        for sleutel, waarde in re.findall(
            r'([A-Za-z_"][\w" ]*?)\s*:\s*"([^"]*)"', inhoud
        ):
            uit[sleutel.strip().strip('"').lower()] = waarde
        return uit

    assert tabel("KLEUR_BASIS") == {k: v for k, v in KLEUR_BASIS.items()}
    assert tabel("KLEUR_SYNONIEM") == {k: v for k, v in KLEUR_SYNONIEM.items()}
    assert tabel("COLOUR_NL") == {k: v for k, v in COLOUR_NL.items()}


# ── De opdracht die de deur uit gaat ────────────────────────────────────────
def _jobs():
    return [
        {"id": "a", "platform": "marktplaats", "payload": {"color": "bruine"}},
        {"id": "b", "platform": "2dehands", "payload": {"color": "crème"}},
        {"id": "c", "platform": "vinted", "payload": {"color": "bruine"}},
        {"id": "d", "platform": "marktplaats", "payload": {"color": "katoen"}},
        {"id": "e", "platform": "marktplaats", "payload": {"color": "Bruin"}},
        {"id": "f", "platform": "marktplaats", "payload": {}},
        {"id": "g", "platform": "marktplaats", "payload": None},
    ]


def test_de_kleur_wordt_goedgezet_vlak_voor_uitgifte():
    """Zo werkt de reparatie ook op de extensie die de verkoper vandaag draait.

    Een nieuwe extensie staat pas in de Chrome Web Store nadat Google hem heeft
    goedgekeurd, en Chrome haalt hem daarna op zijn eigen moment op. Egbert
    draaide daardoor drie weken een versie eenentwintig stappen achter. Wat hier
    op de server gebeurt, geldt bij de eerstvolgende opdracht.
    """
    from backend.api.jobs import _zet_kleur_goed

    jobs = _jobs()
    aangepast = _zet_kleur_goed(jobs)
    op_id = {j["id"]: j for j in jobs}
    assert op_id["a"]["payload"]["color"] == "Bruin"
    assert op_id["b"]["payload"]["color"] == "Wit"
    assert aangepast == 2
    # Vinted heeft een eigen kleurenlijst en blijft ongemoeid.
    assert op_id["c"]["payload"]["color"] == "bruine"
    # Wat geen kleur is blijft staan zoals de verkoper het schreef.
    assert op_id["d"]["payload"]["color"] == "katoen"
    # Al goed is al goed: niets te melden, niets te veranderen.
    assert op_id["e"]["payload"]["color"] == "Bruin"


def test_een_lege_of_ontbrekende_opdracht_laat_niets_omvallen():
    """Een opdracht zonder kleur, zonder payload of helemaal leeg mag nooit de
    uitgifte van álle andere opdrachten meeslepen — dan ligt publiceren stil."""
    from backend.api.jobs import _zet_kleur_goed

    assert _zet_kleur_goed([]) == 0
    assert _zet_kleur_goed(None) == 0
    assert _zet_kleur_goed(_jobs()[5:]) == 0


def test_de_uitgifte_roept_hem_ook_echt_aan():
    """Een helper die nergens wordt aangeroepen repareert niets."""
    bron = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    uitgifte = bron[bron.index("def get_pending_jobs("):]
    assert "_zet_kleur_goed(ready)" in uitgifte[: uitgifte.index("\n@router")]
