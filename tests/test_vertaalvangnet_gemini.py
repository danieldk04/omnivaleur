"""Het vangnet: Gemini vertaalt als Claude niet kan, en nooit slordiger.

WAAROM DIT ER IS (19-09-2026, Daniel)

Zodra het Anthropic-tegoed op is staat publiceren volledig stil. Gemeten op
19-09-2026 met de echte sleutel: `client.messages.create` geeft dan
`BadRequestError: Your credit balance is too low to access the Anthropic API`.
`_vertaal` maakt daar terecht `VertalingOnbeschikbaar` van, want een Engelse
tekst op Marktplaats is erger dan een advertentie die wacht. Maar de verkoper
ziet dan alleen "Publishing is on hold" en er gebeurt niets meer.

Wat hieronder vastligt:
  1. Werkt Claude gewoon, dan wordt Gemini NIET aangeroepen. Het vangnet mag
     niets veranderen aan de dagelijkse gang van zaken.
  2. Ligt Claude plat en vertaalt Gemini netjes, dan gaat de advertentie door.
  3. Ligt Claude plat en is er geen Google-sleutel, dan gebeurt er precies wat
     er hiervoor gebeurde: de advertentie wacht.
  4. Ligt Claude plat en levert Gemini iets onbetrouwbaars (verkeerde taal, een
     praatje in plaats van een vertaling, een afgekapte tekst), dan wacht de
     advertentie ook. Een vangnet mag nooit een fout doorlaten die Claude zelf
     niet mocht doorlaten.
  5. De alinea-indeling (§BR§) overleeft het vangnet net zo goed.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402
import backend.services.gemini_vertaling as gv  # noqa: E402
from backend.services.crosslist import VertalingOnbeschikbaar, _vertaal  # noqa: E402

ENGELS = ("Authentic designer shorts from MyProtein in size XL, measurements "
          "available in the photos. Condition: new with tags.")
NEDERLANDS = ("Authentieke designer short van MyProtein in maat XL, de maten "
              "staan op de foto's. Staat: nieuw met kaartjes.")


class LegeRekening(Exception):
    """Zoals de echte fout eruitziet: 400, credit balance too low."""


# ── hulpstukken ──────────────────────────────────────────────────────────────

def claude_die_werkt(antwoord: str):
    def maak(**kw):
        return SimpleNamespace(content=[SimpleNamespace(text=antwoord)])
    return SimpleNamespace(messages=SimpleNamespace(create=maak))


def claude_die_plat_ligt(teller: list):
    def maak(**kw):
        teller.append(1)
        raise LegeRekening("Your credit balance is too low to access the Anthropic API")
    return SimpleNamespace(messages=SimpleNamespace(create=maak))


@pytest.fixture
def vangnet(monkeypatch):
    """Geeft een lijstje terug waarin elke aanroep van het vangnet belandt."""
    aanroepen = []

    def zet(antwoord):
        def nep(opdracht: str):
            aanroepen.append(opdracht)
            return antwoord
        monkeypatch.setattr(gv, "vertaal", nep)
        return aanroepen

    return zet


# ── 1. gewone dag: het vangnet blijft onaangeroerd ───────────────────────────

def test_werkt_claude_dan_wordt_gemini_niet_aangeroepen(monkeypatch, vangnet):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_werkt(NEDERLANDS))
    aanroepen = vangnet("DIT MAG NOOIT GEBRUIKT WORDEN")

    assert _vertaal(ENGELS, "nl") == NEDERLANDS
    assert aanroepen == [], "Gemini werd aangeroepen terwijl Claude gewoon antwoordde"


# ── 2. lege rekening: het vangnet neemt het over ─────────────────────────────

def test_lege_rekening_gemini_vertaalt_en_publiceren_gaat_door(monkeypatch, vangnet):
    pogingen = []
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt(pogingen))
    aanroepen = vangnet(NEDERLANDS)

    assert _vertaal(ENGELS, "nl") == NEDERLANDS
    assert len(aanroepen) == 1, "het vangnet kreeg de opdracht niet precies één keer"
    assert "<text>" in aanroepen[0], "het vangnet kreeg niet dezelfde opdracht als Claude"
    assert len(pogingen) == 1, "Claude werd nog een keer geprobeerd terwijl hij plat lag"


def test_alineas_overleven_het_vangnet(monkeypatch, vangnet):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt([]))
    bron = "Wol en zijde\nPasvorm valt ruim\nVerzenden kan"
    engels = "Wool and silk\nFits loose\nShipping possible"
    vangnet("Wol en zijde §BR§ Pasvorm valt ruim §BR§ Verzenden kan")

    uit = _vertaal(engels, "nl")
    assert uit == bron, f"alinea-indeling ging verloren: {uit!r}"


# ── 3. geen sleutel: alles blijft zoals het was ──────────────────────────────

def test_zonder_google_sleutel_wacht_de_advertentie(monkeypatch):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt([]))
    monkeypatch.setattr(gv.settings, "google_api_key", "")

    with pytest.raises(VertalingOnbeschikbaar):
        _vertaal(ENGELS, "nl")


# ── 4. het vangnet mag geen fout doorlaten ───────────────────────────────────

def test_vangnet_dat_de_verkeerde_taal_teruggeeft_wordt_geweigerd(monkeypatch, vangnet):
    """Dit is de fout van 08-09-2026: Engelse tekst op een Nederlands kanaal."""
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt([]))
    vangnet(ENGELS)  # Gemini geeft de Engelse brontekst terug

    with pytest.raises(VertalingOnbeschikbaar):
        _vertaal(ENGELS, "nl")


def test_vangnet_dat_een_praatje_teruggeeft_wordt_geweigerd(monkeypatch, vangnet):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt([]))
    vangnet("Ik zie dat je geen tekst hebt meegestuurd. " * 12)

    with pytest.raises(VertalingOnbeschikbaar):
        _vertaal(ENGELS, "nl")


def test_vangnet_dat_niets_levert_laat_de_advertentie_wachten(monkeypatch, vangnet):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt([]))
    vangnet(None)

    with pytest.raises(VertalingOnbeschikbaar):
        _vertaal(ENGELS, "nl")


# ── 5. het vangnet zelf: welk model, en wat weigert het ──────────────────────

class NepAntwoord:
    def __init__(self, status=200, lading=None, tekst=""):
        self.status_code = status
        self._lading = lading or {}
        self.text = tekst

    def json(self):
        return self._lading

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


MODELLENLIJST = {"models": [
    {"name": "models/gemini-2.5-flash-image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-lite-preview-09-2025", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
]}


def _antwoord(tekst: str, reden: str = "STOP"):
    return {"candidates": [{"finishReason": reden,
                            "content": {"parts": [{"text": tekst}]}}]}


@pytest.fixture
def gemini(monkeypatch):
    """Nepnetwerk voor het vangnet. Geeft de gebruikte adressen terug."""
    monkeypatch.setattr(gv.settings, "google_api_key", "test-sleutel")
    monkeypatch.setattr(gv, "_GEKOZEN", None)
    gebruikt = []

    def zet(post_antwoord):
        def nep_get(url, **kw):
            gebruikt.append(("get", url))
            return NepAntwoord(200, MODELLENLIJST)

        def nep_post(url, **kw):
            gebruikt.append(("post", url))
            return post_antwoord

        monkeypatch.setattr(gv.httpx, "get", nep_get)
        monkeypatch.setattr(gv.httpx, "post", nep_post)
        return gebruikt

    return zet


def test_vangnet_kiest_het_goedkoopste_stabiele_model(gemini):
    gebruikt = gemini(NepAntwoord(200, _antwoord(NEDERLANDS)))

    assert gv.vertaal("vertaal dit") == NEDERLANDS
    adres = [u for soort, u in gebruikt if soort == "post"][0]
    assert adres.endswith("/models/gemini-2.5-flash-lite:generateContent"), adres


def test_vangnet_vraagt_maar_een_keer_welke_modellen_er_zijn(gemini):
    gebruikt = gemini(NepAntwoord(200, _antwoord(NEDERLANDS)))
    gv.vertaal("een")
    gv.vertaal("twee")
    assert sum(1 for soort, _ in gebruikt if soort == "get") == 1


def test_afgekapt_antwoord_wordt_geweigerd(gemini):
    """Een halve omschrijving ziet er gaaf uit en is dat niet."""
    gemini(NepAntwoord(200, _antwoord("Authentieke designer short van MyPro", "MAX_TOKENS")))
    assert gv.vertaal("vertaal dit") is None


def test_verdwenen_model_laat_de_keuze_los(gemini):
    gemini(NepAntwoord(404, {}, "not found"))
    assert gv.vertaal("vertaal dit") is None
    assert gv._GEKOZEN is None, "de volgende poging blijft tegen een verdwenen naam praten"


def test_zonder_sleutel_gaat_er_geen_enkel_gesprek_uit(monkeypatch):
    monkeypatch.setattr(gv.settings, "google_api_key", "")

    def nooit(*a, **kw):
        raise AssertionError("er ging tóch een verzoek naar Google")

    monkeypatch.setattr(gv.httpx, "get", nooit)
    monkeypatch.setattr(gv.httpx, "post", nooit)
    assert gv.vertaal("vertaal dit") is None
