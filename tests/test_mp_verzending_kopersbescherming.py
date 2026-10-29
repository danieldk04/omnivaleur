"""Marktplaats: zelf verzenden voor een vast bedrag en kopersbescherming uit.

WAAROM (29-10-2026, Mieneke van Voordeelsieraden). Haar prijzen zijn inclusief
verzekerde verzending; ze kiest op Marktplaats altijd "Zelf verzenden" met EUR
0,01, en wil kopersbescherming uit. Het plaatsformulier zet PostNL, DHL en Budbee
klaar met de kosten van Marktplaats en laat kopersbescherming aan. Dit is nu een
instelling van de verkoper. Zonder instelling verandert er niets (de standaard).
"""
from backend.services import instellingen as I


def _lees_als(monkeypatch, inst):
    monkeypatch.setattr(I, "lees", lambda user_id: I._schoon(inst))


def test_standaard_stuurt_niets_mee(monkeypatch):
    _lees_als(monkeypatch, {})
    uit = I.verzendkeuzes("u", 100)
    assert I.MP_ZELF_VERZENDEN not in uit
    assert I.MP_KOPERSBESCHERMING not in uit


def test_bedrag_en_uitzetten_gaan_mee(monkeypatch):
    _lees_als(monkeypatch, {I.MP_ZELF_VERZENDEN: 1, I.MP_KOPERSBESCHERMING: "uit"})
    uit = I.verzendkeuzes("u", 100)
    assert uit[I.MP_ZELF_VERZENDEN] == 1
    assert uit[I.MP_KOPERSBESCHERMING] == "uit"


def test_volg_stuurt_niets_mee(monkeypatch):
    _lees_als(monkeypatch, {I.MP_KOPERSBESCHERMING: "volg"})
    assert I.MP_KOPERSBESCHERMING not in I.verzendkeuzes("u", 100)


def test_schoon_stelt_bij_en_vangt_rommel_op():
    assert I._schoon({I.MP_ZELF_VERZENDEN: None})[I.MP_ZELF_VERZENDEN] is None
    assert I._schoon({I.MP_ZELF_VERZENDEN: ""})[I.MP_ZELF_VERZENDEN] is None
    assert I._schoon({I.MP_ZELF_VERZENDEN: "abc"})[I.MP_ZELF_VERZENDEN] is None
    assert I._schoon({I.MP_ZELF_VERZENDEN: 0})[I.MP_ZELF_VERZENDEN] == I.MP_ZELF_VERZENDEN_MIN
    assert I._schoon({I.MP_ZELF_VERZENDEN: 99999999})[I.MP_ZELF_VERZENDEN] == I.MP_ZELF_VERZENDEN_MAX
    assert I._schoon({I.MP_ZELF_VERZENDEN: 295})[I.MP_ZELF_VERZENDEN] == 295
    assert I._schoon({I.MP_KOPERSBESCHERMING: "iets"})[I.MP_KOPERSBESCHERMING] == "volg"
    assert I._schoon({})[I.MP_ZELF_VERZENDEN] is None
    assert I._schoon({})[I.MP_KOPERSBESCHERMING] == "volg"


def test_andere_instellingen_blijven_ongemoeid(monkeypatch):
    _lees_als(monkeypatch, {"levering": "verzenden", "pakket_grens": 50,
                            I.MP_ZELF_VERZENDEN: 1})
    uit = I.verzendkeuzes("u", 10)
    assert uit["levering"] == "verzenden" and uit["pakket"] == I.PAKKET_KLEIN
