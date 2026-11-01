"""Azure Translator vertaalt vóór de taalmodellen, per regel en met geheugen.

WAAROM DIT ER IS (01-11-2026, Daniel)
Op 31-10 kostte vertalen via Gemini EUR 5,49 op één dag (Goudlief, 2.588 artikelen
tegelijk). Azure F0 is gratis tot 2 miljoen tekens per maand. Wat hier vastligt:
  1. Zonder sleutel verandert er niets: geen verzoek aan Azure.
  2. Met sleutel gaat de tekst naar Azure en NIET naar het taalmodel.
  3. Elke regel gaat één keer: een tweede artikel met dezelfde regels kost niets.
  4. Een regel die Azure al als doeltaal herkent blijft letterlijk staan.
  5. Het merk gaat beschermd mee; de regelindeling blijft gelijk.
  6. Azure weigert (tegoed op) -> het taalmodel neemt over, zoals hiervoor.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.azure_vertaling as av  # noqa: E402
import backend.services.crosslist as cl  # noqa: E402
import backend.services.gemini_vertaling as gv  # noqa: E402

BRON = ("Basic Information\n\nSPU ID:\n63124\n\nMaterial:\nroestvrij staal\n\n"
        "Seizoen:\nFour Seasons\n\nThis lovely necklace by Pandora is new with tags.")
VASTE_VERTALING = {"Basic Information": "Basisinformatie", "SPU ID:": "SPU-ID:",
                   "Material:": "Materiaal:", "Four Seasons": "Vier seizoenen"}


@pytest.fixture
def azure(monkeypatch):
    verzoeken = []

    def nep_post(url, params=None, headers=None, json=None, timeout=None):
        verzoeken.append(json)
        uit = []
        for stuk in json:
            t = stuk["Text"]
            if t in ("roestvrij staal", "Seizoen:"):
                uit.append({"detectedLanguage": {"language": "nl"},
                            "translations": [{"text": t + " (niet aanraken)"}]})
            elif t in VASTE_VERTALING:
                uit.append({"detectedLanguage": {"language": "en"},
                            "translations": [{"text": VASTE_VERTALING[t]}]})
            else:
                assert "mstrans:dictionary" in t, "merk niet beschermd"
                uit.append({"detectedLanguage": {"language": "en"}, "translations": [
                    {"text": "Deze mooie ketting van Pandora is nieuw met labels."}]})
        return SimpleNamespace(status_code=200, json=lambda: uit, text="")

    monkeypatch.setattr(av.settings, "azure_translator_key", "test")
    monkeypatch.setattr(av.httpx, "post", nep_post)
    av._GEHEUGEN.clear()
    return verzoeken


def test_zonder_sleutel_geen_azure(monkeypatch):
    monkeypatch.setattr(av.settings, "azure_translator_key", "")
    monkeypatch.setattr(av.httpx, "post", lambda *a, **k: pytest.fail("Azure aangeroepen"))
    assert av.vertaal(BRON, "nl") is None


def test_per_regel_met_geheugen_en_merk(azure):
    uit = av.vertaal(BRON, "nl", "Pandora")
    assert uit.split("\n")[0] == "Basisinformatie"
    assert "Materiaal:\nroestvrij staal" in uit           # al Nederlands: letterlijk
    assert "Seizoen:\nVier seizoenen" in uit
    assert "63124" in uit
    assert uit.count("\n") == BRON.count("\n")              # regelindeling gelijk
    assert len(azure) == 1
    # Tweede artikel met dezelfde specificaties: alleen de nieuwe regel gaat.
    av.vertaal(BRON.replace("63124", "99999"), "nl", "Pandora")
    assert len(azure) == 1


def test_crosslist_gebruikt_azure_en_niet_het_taalmodel(azure, monkeypatch):
    monkeypatch.setattr(gv, "vertaal", lambda o: pytest.fail("Gemini aangeroepen"))
    monkeypatch.setattr(cl, "_claude_client", lambda: pytest.fail("Claude aangeroepen"))
    uit = cl._vertaal(BRON, "nl", "Pandora")
    assert "Deze mooie ketting van Pandora" in uit


def test_azure_weigert_dan_neemt_het_taalmodel_over(monkeypatch):
    monkeypatch.setattr(av.settings, "azure_translator_key", "test")
    monkeypatch.setattr(av.httpx, "post", lambda *a, **k: SimpleNamespace(
        status_code=403, text="quota exceeded", json=lambda: {}))
    av._GEHEUGEN.clear()
    gevraagd = []
    monkeypatch.setattr(gv, "beschikbaar", lambda: True)
    monkeypatch.setattr(gv, "vertaal", lambda o: (gevraagd.append(o),
                        "Deze mooie ketting is nieuw met labels en kaartjes erbij.")[1])
    uit = cl._vertaal("This lovely necklace is new with tags and all labels attached.", "nl")
    assert gevraagd and uit.startswith("Deze mooie ketting")
