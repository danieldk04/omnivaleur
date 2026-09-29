"""Toons tweelingen: zelfde eigen code in de omschrijving én zelfde afmeting.

29-09-2026, De Juiste Toon: kleed A07 stond twee keer op Marktplaats, een keer
met de Vinted-foto's en een keer met de oude 2dehands-foto's. De rijen zijn echte
kopieën uit zijn database (ingekort). De oude regel (titel plus gedeelde foto)
vond ze niet; de nieuwe wel. En een hergebruikte code met een andere afmeting
(TXL30) blijft twee voorwerpen.
"""
import importlib.util
from pathlib import Path

_pad = Path(__file__).parent.parent / "scripts" / "ruim_dubbele_advertenties_uit_import.py"
_spec = importlib.util.spec_from_file_location("ruim_dubbel", _pad)
ruim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ruim)

A07_VINTED = {
    "id": "b5ac8df1", "title": "Foulard plaid woondeken Azteken bruin groen 155/120 cm",
    "price": 30.0, "sku": "IMP-B5AC8DF1", "created_at": "2026-08-28T12:03:56",
    "description": "A07\n\nFoulard plaid woondeken Azteken\nBruintinten groen\n"
                   "Afmetingen: 155/120 cm\n\nDJT DeJuisteToon",
    "photo_urls": ["https://img.omnivaleur.com/x/imported/3350e275.jpg"],
}
A07_2DEHANDS = {
    "id": "aaebe360", "title": "Foulard plaid woondeken Azteken bruin groen 155/120",
    "price": 30.0, "sku": "IMP-AAEBE360", "created_at": "2026-09-05T14:15:35",
    "description": "A07 Foulard plaid woondeken Azteken Bruintinten groen Afmetingen 155/120"
                   "  OVER DE JUISTE TOON: Ontdek onze betoverende vintage collectie",
    "photo_urls": ["https://img.omnivaleur.com/x/imported/6cf415c7.avif"],
}
TXL30_A = {
    "id": "t1", "title": "Perzisch tapijt klassiek patroon versleten sleets 183/124 cm",
    "price": 75.0, "sku": "IMP-T1", "created_at": "2026-08-28",
    "description": "TXL30\nPerzisch tapijt\nAfmetingen 183/124 cm", "photo_urls": ["a.jpg"],
}
TXL30_B = {
    "id": "t2", "title": "TXL30 Perzisch tapijt taupe rood zwart 150/96",
    "price": 65.0, "sku": "IMP-T2", "created_at": "2026-09-05",
    "description": "TXL30 Perzisch tapijt taupe rood zwart 150/96", "photo_urls": ["b.jpg"],
}


def test_oude_regel_mist_a07():
    assert ruim._families([A07_VINTED, A07_2DEHANDS]) == []


def test_eigen_code_en_afmeting_vindt_a07():
    fam = ruim.families_op_code([A07_VINTED, A07_2DEHANDS, TXL30_A])
    assert [sorted(i["id"] for i in g) for g in fam] == [["aaebe360", "b5ac8df1"]]


def test_zelfde_code_andere_afmeting_blijft_twee_voorwerpen():
    assert ruim.families_op_code([TXL30_A, TXL30_B]) == []


def test_zonder_afmeting_geen_tweeling():
    zonder = [{**A07_VINTED, "title": "Foulard", "description": "A07 Foulard"},
              {**A07_2DEHANDS, "title": "Foulard", "description": "A07 Foulard"}]
    assert ruim.families_op_code(zonder) == []


def test_bron_is_het_kanaal_van_de_oudste_advertentierij():
    assert ruim.bron([{"platform": "marktplaats", "created_at": "2026-09-15"},
                      {"platform": "vinted", "created_at": "2026-08-28"}]) == "vinted"
    assert ruim.bron([]) == "?"


# TK199 (29-09-2026): vier rijen, vier Marktplaats-advertenties, op Marktplaats
# verkocht terwijl de andere drie bleven staan. De 2dehands-rij had geen
# omschrijving en dus geen code; de titel is letterlijk gelijk.
TK199_VINTED = {
    "id": "11c5b701", "title": "Vintage tafelkleed met een Japans tafereel ovaal 160/140 cm",
    "price": 30.0, "sku": "IMP-11C5B701", "created_at": "2026-08-28T10:55",
    "description": "TK199\nVintage tafelkleed met een Japans tafereel\nAfmetingen 160/140 cm",
    "photo_urls": ["v.jpg"],
}
TK199_2DEHANDS = {
    "id": "b1350c16", "title": "Vintage tafelkleed met een Japans tafereel ovaal 160/140 cm",
    "price": 30.0, "sku": "IMP-B1350C16", "created_at": "2026-09-05T14:08",
    "description": "", "photo_urls": ["d.jpg"],
}


def test_rij_zonder_code_met_dezelfde_titel_hoort_erbij():
    fam = ruim.families_op_code([TK199_VINTED, TK199_2DEHANDS])
    assert [sorted(i["id"] for i in g) for g in fam] == [["11c5b701", "b1350c16"]]


def test_zelfde_titel_met_andere_code_blijft_los():
    ander = {**TK199_2DEHANDS, "description": "TK200 Vintage tafelkleed 160/140 cm"}
    assert ruim.families_op_code([TK199_VINTED, ander]) == []


def test_zelfde_titel_zonder_afmeting_blijft_los():
    a = {**TK199_VINTED, "title": "Lederhosen dames", "description": ""}
    b = {**TK199_2DEHANDS, "title": "Lederhosen dames"}
    assert ruim.families_op_code([a, b]) == []
