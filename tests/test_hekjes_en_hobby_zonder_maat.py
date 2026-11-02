"""Gollem Joukes, 02-11-2026: hekjes uit Vinted-teksten en strijkemblemen/stropdassen
zonder maat, merk en kleur op Marktplaats."""
from backend.services.crosslist import _zonder_hekjes, _missing_fields_per_platform


def test_hekjes_weg_woord_blijft():
    assert _zonder_hekjes("Leuk #carnaval #festival") == "Leuk carnaval festival"
    assert _zonder_hekjes("kruis#stropdas") == "kruis stropdas"
    assert _zonder_hekjes("nr #12") == "nr 12"
    assert _zonder_hekjes("kruis # bloem ##tijger") == "kruis bloem tijger"


def test_tekst_zonder_hekje_ongewijzigd():
    t = "Regel een  \n\nregel twee "
    assert _zonder_hekjes(t) == t and _zonder_hekjes("") == ""


def _item(cat, gender):
    return {"price": 2, "description": "x", "photo_urls": ["a"], "category": cat, "gender": gender}


def test_strijkembleem_en_stropdas_hoeven_geen_maat_merk_kleur():
    for cat, g in (("hobby kledingapplicaties en strijkemblemen", "hobby"),
                   ("heren accessoires", "heren")):
        assert _missing_fields_per_platform(_item(cat, g), ["marktplaats", "2dehands"]) == {}


def test_kleding_blijft_maat_eisen():
    m = _missing_fields_per_platform(_item("jassen", "heren"), ["marktplaats"])
    assert set(m["marktplaats"]) == {"brand", "size", "color"}
