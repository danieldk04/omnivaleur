"""Een tweede scan mag niet wissen wat de eerste al gevonden had.

Toon (dejuistetoon), 02-09-2026. Vinted knijpt af tijdens een scan, dus komt een
scan geregeld terug met een lege omschrijving voor een advertentie waar de vorige
scan er wél een vond. Die leegte werd over de goede tekst heen geschreven.
Gemeten in zijn gegevens: 271 kandidaten zonder tekst, terwijl het artikel dat
eruit geïmporteerd was er wél een had.

Er staat hieronder bewust ook een test die de OUDE regel naspeelt. Anders weet je
alleen dat de nieuwe code werkt, niet dat ze iets repareert.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.jobs import _rijke_velden

EERSTE_SCAN = {
    "description": "KEL11 Traditioneel geweven Kelim kleed, 224 tekens aan tekst.",
    "brand": "Handgemaakt",
    "size": "",
    "condition": "Goed",
    "color": "bruin",
    "material": "wol",
    "category": None,
    "gender": None,
}
AFGEKNEPEN_SCAN = {          # exact wat Vinted teruggaf toen hij afkneep: niets
    "description": "",
    "brand": "",
    "size": "",
    "condition": "",
    "color": "",
    "material": "",
}


def _oude_regel(row, photo_urls):
    """De regel zoals hij tot 02-09-2026 in jobs.py stond."""
    return {
        "photo_urls": photo_urls or None,
        "description": (row.get("description") or None),
        "brand": (row.get("brand") or None),
        "size": (row.get("size") or None),
        "condition": (row.get("condition") or None),
        "category": (row.get("category") or None),
        "gender": (row.get("gender") or None),
        "color": (row.get("color") or None),
        "material": (row.get("material") or None),
    }


def test_de_oude_regel_wiste_de_tekst():
    """De voor-proef. Zakt deze test ooit, dan test hij het verkeerde."""
    vorige = _rijke_velden(EERSTE_SCAN, ["a.jpg"], None)
    assert vorige["description"], "de eerste scan hoort tekst te vinden"
    daarna = _oude_regel(AFGEKNEPEN_SCAN, [])
    assert daarna["description"] is None, "dit was precies het mankement"


def test_afgeknepen_scan_laat_de_tekst_staan():
    """De na-proef, zelfde omstandigheden."""
    vorige = _rijke_velden(EERSTE_SCAN, ["a.jpg"], None)
    daarna = _rijke_velden(AFGEKNEPEN_SCAN, [], vorige)
    assert daarna["description"] == EERSTE_SCAN["description"]
    assert daarna["brand"] == "Handgemaakt"
    assert daarna["condition"] == "Goed"
    assert daarna["photo_urls"] == ["a.jpg"], "ook foto's mogen niet verdampen"


def test_een_echte_wijziging_wint_wel():
    """Aanvullen mag nooit betekenen dat een verkoper zijn tekst niet meer
    kan wijzigen: past hij hem op Vinted aan, dan hoort die aanpassing hier te
    landen. Alleen leegte wordt genegeerd, geen inhoud."""
    vorige = _rijke_velden(EERSTE_SCAN, ["a.jpg"], None)
    nieuw = _rijke_velden({**EERSTE_SCAN, "description": "Herschreven tekst"},
                          ["b.jpg"], vorige)
    assert nieuw["description"] == "Herschreven tekst"
    assert nieuw["photo_urls"] == ["b.jpg"]


def test_zonder_voorganger_verandert_er_niets():
    """Een advertentie die we nog nooit zagen: gewoon wat de scan vond."""
    uit = _rijke_velden(AFGEKNEPEN_SCAN, [], None)
    assert uit["description"] is None
    assert uit["brand"] is None


def test_lege_lijst_bij_de_vorige_telt_als_leeg():
    """Een vorige rij die zelf niets droeg, mag niet als 'bewaren' gelden."""
    vorige = {"description": None, "brand": "", "photo_urls": [], "size": None,
              "condition": None, "category": None, "gender": None,
              "color": None, "material": None}
    uit = _rijke_velden(AFGEKNEPEN_SCAN, [], vorige)
    assert uit["description"] is None
    assert uit["photo_urls"] is None


def test_de_ronde_leest_de_vorige_waarden_ook_echt_op():
    """De pure regel hierboven kan kloppen terwijl de ronde hem nooit voedt.
    Dus: staat de aanroep er, mét de vorige rij erbij?"""
    src = (Path(__file__).resolve().parent.parent / "backend/api/jobs.py").read_text(encoding="utf-8")
    ronde = src.split("def _store_scan_results(")[1]
    assert "prior_rich" in ronde, "de vorige waarden worden niet gelezen"
    assert "_rijke_velden(row, photo_urls," in ronde, "de ronde gebruikt de regel niet"
    assert "prior_rich.get(str(platform_listing_id))" in ronde, \
        "de vorige rij wordt niet meegegeven, dan beschermt de regel niets"
