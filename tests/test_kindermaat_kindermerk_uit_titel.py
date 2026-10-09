"""Kindermaat en kindermerk uit de titel (09-10-2026, Janneke 31d28378).

Van haar 2.748 artikelen hadden er ~2.070 geen maat en 2.746 geen merk, dus
stonden Marktplaats en 2dehands dicht met "Voeg merk, maat toe". Haar titels
zeggen het wel ("Tussenjas Name it maat 128"). Alleen bij een kinderartikel,
alleen het kinderraster, alleen precies één maat; volwassen kleding blijft leeg.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api.imports import maat_uit_titel, merk_uit_titel, _infer_attributes  # noqa: E402

K = "kinderen"


def test_kindermaten_uit_haar_titels():
    assert maat_uit_titel("Tussenjas Name it maat 128", K) == "128"
    assert maat_uit_titel("Tussenjas Name It maat 92", K) == "92"
    assert maat_uit_titel("Winterjas Noppies maat 98", K) == "98"
    assert maat_uit_titel("Trui Your Wishes maat 122-128", K) == "122"
    assert maat_uit_titel("Longsleeve Noppies maat 44/50", None, "babykleding") == "44"
    assert maat_uit_titel("Tussenjas Name it maat 56", None, "jongens kleding") == "56"


def test_schoenmaat_blijft_zoals_hij_was():
    assert maat_uit_titel("Schoenen Hip Shoestyle schoenmaat 31", K, "kinderen schoenen") == "31"


def test_niets_bij_twijfel():
    # Volwassen of onbekend: kleding uit de titel blijft bewust leeg.
    assert maat_uit_titel("Herenjas maat 98", "heren") is None
    assert maat_uit_titel("Jas maat 128") is None
    # Twee maten, geen rastermaat of een lengte in cm: liever leeg.
    assert maat_uit_titel("Jas maat 128 en maat 134", K) is None
    assert maat_uit_titel("Broek maat 125", K) is None
    assert maat_uit_titel("Deken maat 100 cm", K) is None
    assert maat_uit_titel("Trui maat 122-140", K) is None
    assert maat_uit_titel("Trui zonder maat", K) is None


def test_kindermerk_alleen_bij_kinderartikel():
    assert merk_uit_titel("Tussenjas Name it maat 128", {}, K) == "Name It"
    assert merk_uit_titel("Winterjas Noppies maat 98", {}, None, "peuterkleding") == "Noppies"
    assert merk_uit_titel("Regenlaarzen Bergstein schoenmaat 24", {}, K) == "Bergstein"
    # Bij volwassenen is "name it" gewone taal.
    assert merk_uit_titel("Name it what you want", {}, "dames") is None
    # Twee merken in één titel: niet kiezen.
    assert merk_uit_titel("Set Noppies en Jopper maat 92", {}, K) is None


def test_eigen_merken_werken_zoals_voorheen():
    assert merk_uit_titel("Trui Your Wishes maat 122-128", {"your wishes": "Your Wishes"}, K) == "Your Wishes"
    assert merk_uit_titel("Overhemd Profuomo", {"profuomo": "Profuomo"}) == "Profuomo"


def test_haar_titels_worden_als_kinderartikel_herkend():
    # Bij importeren komt het geslacht uit de titel; zonder dat geen kindermaat.
    for titel in ("Tussenjas Name it maat 128", "Winterjas Noppies maat 98", "Trui Your Wishes maat 122-128"):
        afl = _infer_attributes(titel)
        assert maat_uit_titel(titel, afl.get("gender"), afl.get("category")), titel
