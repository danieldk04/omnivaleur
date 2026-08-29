"""Zodra er een concept klaarligt, krijgt Daniel een seintje.

Hij wil niet meer in de post zitten, alleen nog op verzenden drukken — dan moet
hij wel weten wanneer er iets te versturen is.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

WORTEL = pathlib.Path(__file__).resolve().parents[1]


def _laad(naam):
    sys.path.insert(0, str(WORTEL / "scripts"))
    spec = importlib.util.spec_from_file_location(naam, WORTEL / "scripts" / f"{naam}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[naam] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def L(monkeypatch):
    mod = _laad("leadgen_mail")
    monkeypatch.setenv("MAIL_HOST", "smtp.test")
    monkeypatch.setenv("MAIL_USER", "info@omnivaleur.nl")
    return mod


def _vang_post(L, monkeypatch):
    verstuurd = []

    class Postbode:
        def __enter__(self):
            return verstuurd.append

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(L, "_postbode", lambda *a, **kw: Postbode())
    return verstuurd


def test_seintje_bevat_ontvanger_en_tekst(L, monkeypatch):
    post = _vang_post(L, monkeypatch)
    monkeypatch.setitem(sys.modules, "mail_analyse", types.SimpleNamespace(bugs=lambda: {}))
    L._meld_concept_klaar({"email": "Klant@example.nl"}, "Re: vraag",
                          "Hi, de teksten komen nu vanzelf binnen.")
    assert len(post) == 1
    inhoud = post[0].get_content()
    assert "klant@example.nl" in inhoud
    assert "de teksten komen nu vanzelf binnen" in inhoud
    assert "Geschreven: klantenservice" in inhoud


def test_reparatie_van_de_developer_staat_erbij(L, monkeypatch):
    """Is er een storing voor gerepareerd, dan is het antwoord nagekeken in de
    code — dat scheelt Daniel het narekenen."""
    post = _vang_post(L, monkeypatch)
    nep = types.SimpleNamespace(bugs=lambda: {
        "advertentietekst-niet-geimporteerd": {
            "melders": ["klant@example.nl"], "status": "opgelost"}})
    monkeypatch.setitem(sys.modules, "mail_analyse", nep)
    L._meld_concept_klaar({"email": "klant@example.nl"}, "Re: vraag", "tekst")
    assert "Geschreven: klantenservice + developer" in post[0].get_content()


def test_zonder_mailinstellingen_gebeurt_er_niets(L, monkeypatch):
    post = _vang_post(L, monkeypatch)
    monkeypatch.delenv("MAIL_HOST", raising=False)
    L._meld_concept_klaar({"email": "klant@example.nl"}, "Re: vraag", "tekst")
    assert post == []


def test_mislukt_seintje_blokkeert_niets(L, monkeypatch):
    def stuk(*a, **kw):
        raise RuntimeError("mailserver plat")

    monkeypatch.setattr(L, "_postbode", stuk)
    monkeypatch.setitem(sys.modules, "mail_analyse", types.SimpleNamespace(bugs=lambda: {}))
    L._meld_concept_klaar({"email": "klant@example.nl"}, "Re: vraag", "tekst")  # geen fout


def test_elk_concept_komt_langs_het_seintje():
    """Eén plek waar alle concepten langskomen — dus ook één seintje."""
    bron = (WORTEL / "scripts" / "leadgen_mail.py").read_text()
    kop = bron.index("def _zet_concept_klaar")
    staart = bron.index("def _meld_concept_klaar")
    assert "_meld_concept_klaar(lead" in bron[kop:staart]


def test_terugkoppeling_meldt_de_developer():
    bron = (WORTEL / "scripts" / "mail_analyse.py").read_text()
    assert 'bron="klantenservice + developer"' in bron
