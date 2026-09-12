"""Vier verschillende lederhosen zijn geen vier keer dezelfde lederhose.

WAAROM DIT ER IS (12-09-2026, De Juiste Toon)
"Ben dit hele weekend al de Lederhosen aan het plaatsen, belangrijk voor
oktober, zie alleen ze nog niet snel op mp komen." Bij elke poging kwam:
"Already listed here under a duplicate copy of this item. Merge them first,
otherwise you get two adverts for one article."

Ze waren geen dubbelen. Vier artikelen die allemaal "Lederhosen Dames" heten
zijn vier verschillende broeken: 40 cm, 35 cm, 47 cm en een groene suède, elk
met eigen prijs, eigen tekst en negen tot elf eigen foto's. Ze delen één
plaatje: zijn eigen info-/maatfoto, die in 17 van zijn artikelen zit. Op de oude
regel ("dezelfde titel én minstens één gedeelde foto") gold dat als bewijs, en
de melding stuurde hem naar samenvoegen — wat twee echte broeken tot één zou
hebben geplakt.

GEMETEN op zijn 1.318 artikelen, alle 43 paren met dezelfde titel én een
gedeelde foto. De scheiding is scherp, zonder twijfelgevallen ertussen: 26 echte
dubbelen delen de hele kleinere fotoset (4 van 4, 5 van 5, 9 van 9, 10 van 10,
11 van 11, en twee paren van 1 van 1), 17 valse delen precies één foto van zeven
tot elf. Over alle verkopers samen geeft de nieuwe regel 32 artikelen vrij en
blokkeert er geen enkele bij.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.crosslist import _zelfde_artikel_al_online, _zelfde_fotos  # noqa: E402

INFO = "https://img.omnivaleur.com/toon/a13db2d0d574470e35573e5f.jpg"


def broek(n: int, aantal: int = 9) -> set:
    """Een lederhose met eigen foto's plus zijn vaste info-plaatje."""
    return {f"https://img.omnivaleur.com/toon/broek{n}-{i}.jpg" for i in range(aantal)} | {INFO}


def test_alleen_het_infoplaatje_gedeeld_is_geen_dubbele():
    assert not _zelfde_fotos(broek(1), broek(2))
    assert not _zelfde_fotos(broek(1, 10), broek(3, 6))


def test_twee_imports_van_dezelfde_advertentie_blijven_een_dubbele():
    zelfde = broek(1)
    assert _zelfde_fotos(zelfde, set(zelfde))


def test_import_die_een_foto_meer_ophaalde_telt_nog_steeds_als_dubbele():
    groot = broek(1, 10)
    klein = set(list(groot)[:9])
    assert _zelfde_fotos(groot, klein)


def test_twee_artikelen_met_dezelfde_enige_foto_zijn_een_dubbele():
    # Zijn twee grand foulards: allebei één foto, en dat is dezelfde.
    een = {"https://img.omnivaleur.com/toon/94c2faf1c9.jpg"}
    assert _zelfde_fotos(een, set(een))


def test_lege_fotoset_blokkeert_nooit():
    assert not _zelfde_fotos(set(), broek(1))
    assert not _zelfde_fotos(broek(1), set())
