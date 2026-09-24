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
        monkeypatch.setattr(gv.settings, "google_api_key", "test-sleutel")
        return aanroepen

    return zet


# ── 1. gewone dag: Gemini vertaalt, Claude blijft onaangeroerd ─────────────
#
# Sinds 23-09-2026 (Daniel: "zet alles op Gemini") is Gemini de eerste keus en
# Claude de reserve. Tot die dag was het andersom.

def test_werkt_gemini_dan_wordt_claude_niet_aangeroepen(monkeypatch, vangnet):
    pogingen = []
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt(pogingen))
    aanroepen = vangnet(NEDERLANDS)

    assert _vertaal(ENGELS, "nl") == NEDERLANDS
    assert len(aanroepen) == 1
    assert pogingen == [], "Claude werd aangeroepen terwijl Gemini gewoon antwoordde"


def test_ligt_gemini_plat_dan_vertaalt_claude(monkeypatch, vangnet):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_werkt(NEDERLANDS))
    aanroepen = vangnet(None)

    assert _vertaal(ENGELS, "nl") == NEDERLANDS
    assert len(aanroepen) == 1, "Gemini werd na één mislukking nog eens geprobeerd"


def test_zonder_google_sleutel_vertaalt_claude_gewoon(monkeypatch):
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_werkt(NEDERLANDS))
    assert _vertaal(ENGELS, "nl") == NEDERLANDS


# ── 2. lege rekening: het vangnet neemt het over ─────────────────────────────

def test_lege_rekening_gemini_vertaalt_en_publiceren_gaat_door(monkeypatch, vangnet):
    pogingen = []
    monkeypatch.setattr(cl, "_claude_client", lambda: claude_die_plat_ligt(pogingen))
    aanroepen = vangnet(NEDERLANDS)

    assert _vertaal(ENGELS, "nl") == NEDERLANDS
    assert len(aanroepen) == 1, "het vangnet kreeg de opdracht niet precies één keer"
    assert "<text>" in aanroepen[0], "Gemini kreeg niet de volledige vertaalopdracht"
    assert pogingen == [], "Claude werd geprobeerd terwijl Gemini al vertaalde"


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
    {"name": "models/gemini-3.1-flash-image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-pro", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-flash-lite-latest", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
]}


def _antwoord(tekst: str, reden: str = "STOP"):
    return {"candidates": [{"finishReason": reden,
                            "content": {"parts": [{"text": tekst}]}}]}


def _klacht(code: int, boodschap: str = ""):
    return NepAntwoord(code, {"error": {"message": boodschap}}, boodschap)


@pytest.fixture
def gemini(monkeypatch):
    """Nepnetwerk voor het vangnet. Geeft de gebruikte modelnamen terug."""
    monkeypatch.setattr(gv.settings, "google_api_key", "test-sleutel")
    monkeypatch.setattr(gv, "_OPGEHEVEN", set())
    monkeypatch.setattr(gv, "_LIJST", None)
    monkeypatch.setattr(__import__("time"), "sleep", lambda s: None)
    gevraagd = []

    def zet(*antwoorden):
        """Elk volgend verzoek krijgt het volgende antwoord; het laatste blijft gelden."""
        reeks = list(antwoorden)

        def nep_get(url, **kw):
            return NepAntwoord(200, MODELLENLIJST)

        def nep_post(url, **kw):
            gevraagd.append(url.split("/models/")[1].split(":")[0])
            return reeks.pop(0) if len(reeks) > 1 else reeks[0]

        monkeypatch.setattr(gv.httpx, "get", nep_get)
        monkeypatch.setattr(gv.httpx, "post", nep_post)
        return gevraagd

    return zet


def test_flash_gaat_voor_flash_lite(gemini):
    """Gemeten 19-09-2026: Flash-Lite schreef "Grije" waar Flash "Grijze" schreef."""
    gevraagd = gemini(NepAntwoord(200, _antwoord(NEDERLANDS)))

    assert gv.vertaal("vertaal dit") == NEDERLANDS
    assert gevraagd == ["gemini-flash-latest"]


def test_een_overbelast_model_geeft_de_beurt_door(gemini):
    """Gemeten: Flash gaf 3 van de 6 keer 503. Dan mag de advertentie niet wachten."""
    gevraagd = gemini(_klacht(503, "high demand"), NepAntwoord(200, _antwoord(NEDERLANDS)))

    assert gv.vertaal("vertaal dit") == NEDERLANDS
    assert len(gevraagd) == 2 and gevraagd[0] == "gemini-flash-latest"


def test_een_opgeheven_model_wijst_zelf_zijn_opvolger_aan(gemini):
    """De echte 404 zegt: "Please update your code to use models/gemini-3.5-flash-lite"."""
    gevraagd = gemini(
        _klacht(404, "This model is no longer available to new users. Please update "
                     "your code to use models/gemini-9.9-flash for the latest features."),
        NepAntwoord(200, _antwoord(NEDERLANDS)))

    assert gv.vertaal("vertaal dit") == NEDERLANDS
    assert gevraagd[1] == "gemini-9.9-flash", gevraagd


def test_de_lijst_van_google_bepaalt_niet_in_zijn_eentje(gemini):
    """`gemini-2.5-flash-lite` staat in de lijst en geeft 404. Dat mag niet fataal zijn."""
    kandidaten = gv._kandidaten()
    assert kandidaten[0] == "gemini-flash-latest"
    assert "gemini-3.5-pro" not in kandidaten
    assert not any("image" in n for n in kandidaten)
    assert "gemini-flash-lite-latest" in kandidaten


def test_een_uitwijk_wordt_niet_onthouden(gemini):
    """Gemeten: Flash gaf één keer 503 en daarna bleef alles op het mindere model.

    Eén drukke minuut mag het betere model niet voor de rest van de dag afschrijven.
    """
    gevraagd = gemini(_klacht(503, "high demand"), NepAntwoord(200, _antwoord(NEDERLANDS)))
    gv.vertaal("een")
    eerste_ronde = len(gevraagd)
    gv.vertaal("twee")

    assert gevraagd[eerste_ronde] == "gemini-flash-latest", gevraagd


def test_een_opgeheven_model_wordt_niet_nog_eens_geprobeerd(gemini):
    """Een 404 is blijvend: die naam bestaat niet meer."""
    gevraagd = gemini(_klacht(404, "no longer available"), NepAntwoord(200, _antwoord(NEDERLANDS)))
    gv.vertaal("een")
    gevraagd.clear()
    gv.vertaal("twee")

    assert "gemini-flash-latest" not in gevraagd, gevraagd


def test_afgekapt_antwoord_wordt_geweigerd(gemini):
    """Een halve omschrijving ziet er gaaf uit en is dat niet."""
    gemini(NepAntwoord(200, _antwoord("Authentieke designer short van MyPro", "MAX_TOKENS")))
    assert gv.vertaal("vertaal dit") is None


def test_valt_alles_uit_dan_wacht_de_advertentie(gemini):
    gevraagd = gemini(_klacht(404, "not found"))
    assert gv.vertaal("vertaal dit") is None
    assert len(gevraagd) >= 2, "het vangnet probeerde maar één model"


def test_zonder_sleutel_gaat_er_geen_enkel_gesprek_uit(monkeypatch):
    monkeypatch.setattr(gv.settings, "google_api_key", "")

    def nooit(*a, **kw):
        raise AssertionError("er ging tóch een verzoek naar Google")

    monkeypatch.setattr(gv.httpx, "get", nooit)
    monkeypatch.setattr(gv.httpx, "post", nooit)
    assert gv.vertaal("vertaal dit") is None


def test_zijn_alle_modellen_te_druk_dan_nog_een_ronde(gemini):
    """24-09-2026, gratis sleutel: 7 van 8 verzoeken 503, en elke vraag ging naar
    het dure Claude. Na een korte pauze antwoordt Google vaak wel."""
    druk = _klacht(503, "high demand")
    gevraagd = gemini(druk, druk, druk, druk, NepAntwoord(200, _antwoord(NEDERLANDS)))

    assert gv.vertaal("vertaal dit") == NEDERLANDS
    assert len(gevraagd) == 5


def test_blijft_het_te_druk_dan_hooguit_twee_rondes(gemini):
    gevraagd = gemini(_klacht(503, "high demand"))

    assert gv.vertaal("vertaal dit") is None
    assert len(gevraagd) == 2 * len(gv._kandidaten())


def test_een_leeg_tegoed_krijgt_geen_tweede_ronde(gemini):
    """402 is een nee, geen drukte: meteen door naar de reserve."""
    gevraagd = gemini(_klacht(402, "Your prepayment credits are depleted."))

    assert gv.vertaal("vertaal dit") is None
    assert len(gevraagd) == 1
