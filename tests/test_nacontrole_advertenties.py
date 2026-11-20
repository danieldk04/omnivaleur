"""Nacontrole van live advertenties: geen valse verschillen (20-11-2026).

De eerste versie meldde 859 'prijs'-verschillen bij een klant die zelf bieden
toestaan koos (MIN_BID), 'bieden' bij artikelen zonder vraagprijs, en
'omschrijving begint anders' door <br/> in onze tekst en door een stuk tekst
uit het midden (categorySpecificDescription). Echte verschillen blijven staan.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import nacontrole_advertenties as n  # noqa: E402

GEPLAATST = {"title": "Zilveren horloge", "price": "39.00", "category": "x",
             "description": "Zilveren horloge van het merk Splendid.<br/><br/>Gekeurd met 925."}


def _rij(soort="FIXED", cents=3900, desc="Zilveren horloge van het merk splendid. Gekeurd met 925.",
         csd="werking. Gewicht: 27,5 gram."):
    return {"title": "Zilveren horloge", "priceInfo": {"priceType": soort, "priceCents": cents},
            "description": desc, "categorySpecificDescription": csd}


def _soorten(item, rij, **kw):
    return [s for s, _ in n.vergelijk_een(item, rij, "marktplaats", {}, set(), GEPLAATST, **kw)]


def test_identiek_geeft_niets_ondanks_br_en_csd_uit_het_midden():
    assert _soorten({"price": 39}, _rij()) == []


def test_min_bid_met_eigen_minimumbod_is_geen_fout():
    assert _soorten({"price": 39, "bid_percentage": 80}, _rij("MIN_BID")) == []


def test_min_bid_met_instelling_bieden_aan_is_geen_fout():
    assert _soorten({"price": 39}, _rij("MIN_BID"), bieden_aan=True) == []


def test_min_bid_zonder_keuze_blijft_een_fout():
    assert _soorten({"price": 39}, _rij("MIN_BID")) == ["prijs"]


def test_min_bid_met_ander_bedrag_blijft_een_fout():
    assert _soorten({"price": 39, "bid_percentage": 80}, _rij("MIN_BID", cents=2495)) == ["prijs"]


def test_bieden_bij_artikel_zonder_vraagprijs_is_geen_fout():
    assert _soorten({"price": 0}, _rij("FAST_BID", cents=0)) == []


def test_echte_andere_omschrijving_blijft_een_fout():
    assert _soorten({"price": 39}, _rij(desc="Iets heel anders over een lamp")) == ["omschrijving"]


def test_html_tekens_geven_geen_verschil():
    geplaatst = dict(GEPLAATST, description="19e&nbsp;eeuwse lepel, Lutz &amp; Weiss uit Pforzheim, zeer fraai.")
    rij = _rij(desc="19e eeuwse lepel, lutz weiss uit pforzheim, zeer fraai.")
    assert n.vergelijk_een({"price": 39}, rij, "marktplaats", {}, set(), geplaatst) == []
