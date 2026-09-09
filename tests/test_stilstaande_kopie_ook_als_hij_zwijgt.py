"""Een stilstaande extensiekopie moet ook zichtbaar zijn als ze zich niet meldt.

AANLEIDING (09-09-2026, De Juiste Toon). Hij laadde 8 september 's avonds een
stapel artikelen klaar en vroeg de volgende middag waarom er niets op
Marktplaats stond. Gemeten in zijn account:

- extension_heartbeat: laatste melding 08-09 13:31 UTC, versie 1.0.260;
  in de Chrome Web Store stond 1.0.313. 53 versies achter.
- Alle vier de andere actieve verkopers stonden diezelfde ochtend op 1.0.311 of
  1.0.313: Chrome werkt een kopie uit de winkel dus gewoon bij. Deze niet, want
  ze is met de hand geladen.
- 61 opdrachten stonden te wachten; de laatste die nog draaide was van 08-09.
- De uitgifte gaf die kopie sinds 07-09 terecht geen werk meer
  (ACHTERSTAND_GRENS), maar het scherm zei alleen: "your extension has not
  checked in — open Chrome, the queue picks up by itself after that."

Dat laatste kon niet kloppen en stuurde hem een dag lang naar een schakelaar
die al goed stond. De server wist de versie de hele tijd: die staat in de
aanwezigheidsstempel, ook als de kopie al uren zwijgt.
"""
import re
from pathlib import Path

import pytest

from backend.api import jobs

WORTEL = Path(__file__).resolve().parents[1]

# De echte meting uit Toons account op 09-09-2026.
TOON = "1.0.260"
WINKEL = "1.0.313"


class _Vraag:
    """Een ketting die net zoveel kan als de echte: alles behalve antwoorden."""

    def __init__(self, data):
        self._data = data

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self

    def execute(self):
        class R:  # noqa: D401
            data = self._data
        return R()


class _Db:
    def __init__(self, hartslag_versie, fouten=()):
        self._hb = [{"ext_version": hartslag_versie}] if hartslag_versie else []
        self._fouten = list(fouten)

    def table(self, naam):
        return _Vraag(self._hb if naam == "extension_heartbeat" else self._fouten)


@pytest.fixture
def winkel_staat_op_1_0_313():
    """De winkelversie vastzetten, zonder verkeer naar Google (zie conftest)."""
    vorig = dict(jobs._WEBSTORE_CACHE)
    jobs._WEBSTORE_CACHE.update(versie=WINKEL, ts=9e9, ok=True)
    yield
    jobs._WEBSTORE_CACHE.clear()
    jobs._WEBSTORE_CACHE.update(vorig)


def test_de_oude_regel_zag_toons_kopie_niet(winkel_staat_op_1_0_313):
    """Het gat: hij zat boven de harde ondergrens, dus er kwam geen melding.

    Dit is de voormeting. 1.0.260 is nieuwer dan 1.0.244, en de melding keek
    alleen naar foutmeldingen mét een versiestempel eronder — die had hij niet.
    """
    assert jobs._kopstuk_versie(TOON) > jobs.MINIMALE_SCANVERSIE
    # Geen enkele foutmelding met een stempel onder de ondergrens: dat was de
    # enige bron die de oude regel gebruikte.
    zonder_stempels = _Db(TOON, fouten=[{"result": {"error": "Geen postcode ingevuld."}}])
    assert not any(
        jobs._extensie_versie((r["result"] or {}).get("error")) for r in [
            {"result": {"error": "Geen postcode ingevuld."}}]
    )
    # En tóch moet er nu een waarschuwing komen — puur op de hartslag.
    assert jobs._verouderde_extensie(zonder_stempels, "u")["outdated_extension"] == TOON


def test_de_stilstaande_kopie_wordt_gemeld_ook_zonder_hartslag_van_vandaag(
        winkel_staat_op_1_0_313):
    uit = jobs._verouderde_extensie(_Db(TOON), "u")
    assert uit["outdated_extension"] == TOON
    assert uit["published_extension"] == WINKEL
    assert uit["outdated_versies_achter"] == 53
    # Het scherm moet hieraan kunnen zien dat aanzetten niet helpt.
    assert uit["outdated_krijgt_geen_werk"] is True


def test_wie_gewoon_een_paar_versies_achterloopt_krijgt_geen_paniekmelding(
        winkel_staat_op_1_0_313):
    # De andere vier verkopers van die ochtend. Die werken gewoon door.
    for versie in ("1.0.311", "1.0.313", "1.0.294"):
        assert jobs._verouderde_extensie(_Db(versie), "u") == {}, versie


def test_bij_twijfel_zeggen_we_niets():
    # Geen winkelversie binnen (conftest zet hem op None): dan weten we het niet
    # en blijft het scherm zoals het was.
    assert jobs._verouderde_extensie(_Db(TOON), "u") == {}
    # En zonder hartslagversie ook niet.
    assert jobs._verouderde_extensie(_Db(None), "u") == {}


def test_het_scherm_stuurt_hem_niet_meer_naar_de_schakelaar():
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    balk = app.split("function renderActivityBar()")[1].split("function ")[0]
    assert "ext.outdated_krijgt_geen_werk" in balk, \
        "de wachtrijbalk kijkt niet of deze kopie überhaupt werk krijgt"
    # De oude belofte mag alleen nog gelden voor een kopie die wél mag werken.
    voor, na = balk.split("ext.outdated_krijgt_geen_werk", 1)
    assert "the queue picks up by itself after that" not in voor
    assert "too old to run them" in na


def test_de_melding_noemt_de_versie_uit_de_winkel_en_geen_vast_nummer():
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    blok = app.split("function extraOudeExtensieMelding(")[1].split("\nfunction ")[0]
    assert "published_extension" in blok
    # Een hard nummer in de tekst veroudert: precies daarom vond Toon niets fout
    # aan zijn 1.0.260 toen er "not version 1.0.249 or newer" stond.
    assert not re.search(r"not version 1\.0\.\d+ or newer", blok)
