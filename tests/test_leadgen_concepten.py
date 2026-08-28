"""Bewaakt de afspraken rond conceptantwoorden op koude-mailreacties.

Aanleiding, 27-08-2026. Rob Kruizinga van Borstelbeer antwoordde op de koude
mail met één inhoudelijke zin: productvarianten uit zijn webshop zijn niet op
Marktplaats te zetten. Hij kreeg als concept de standaard verkoopmail terug —
demovideo, platformlijst en maandbedrag — en niets over zijn vraag.

Daar zaten twee losse fouten onder, en dit bestand legt van allebei vast dat ze
niet mogen terugkomen:

  1. Het vangnet-sjabloon trad stil in zodra het echte antwoord niet lukte.
     Dat is erger dan geen antwoord: een verkeerd antwoord kost de lead.
  2. Het sjabloon bepaalde waar iemand "naar vroeg" door de HELE mail te lezen,
     inclusief het citaat van onze eigen koude mail eronder. Die noemt zelf de
     platformen en de prijs, dus vroeg iedereen die antwoordde daar automatisch
     naar.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import leadgen_mail as L  # noqa: E402


# ------------------------------------------------------- het citaat is niet van hem
def test_eigen_tekst_laat_ons_eigen_citaat_buiten_beschouwing():
    """Wat onder ">" staat is onze eigen tekst, niet zijn vraag."""
    body = (
        "Klinkt leuk, ben benieuwd! Probleem is nu dat alle productvariabelen\n"
        "binnen de site niet in bijv. marktplaats te zetten zijn.\n"
        "\n"
        "Op 27-08-2026 schreef Daniel:\n"
        "> Qua platformen: Marktplaats, 2dehands, Vinted, eBay en Shopify.\n"
        "> De kosten zijn EUR 19,99 per maand, eerste 7 dagen gratis.\n"
    )
    eigen = L._eigen_tekst(body)
    assert "productvariabelen" in eigen
    # Precies de twee onderwerpen die hij NIET aansneed:
    assert "19,99" not in eigen
    assert "Vinted" not in eigen


# ------------------------------------------------------- geen sjabloon meer
def test_geen_sjabloon_als_het_echte_antwoord_niet_lukt(monkeypatch):
    """Mislukt het schrijven, dan komt er niets — geen verkoopmail."""
    monkeypatch.setattr(L, "_slim_concept", lambda *a, **k: None)
    monkeypatch.setattr(L, "is_klant", lambda adres: False)
    monkeypatch.setattr(L, "_verzonden_tekst_uit_kas", lambda *a, **k: "")

    lead = {"email": "info@borstelbeer.nl", "bedrijf": "Borstelbeer", "ads": 1200}
    tekst = L._concept_tekst(lead, "Probleem is nu dat alle productvariabelen "
                                    "binnen de site niet in marktplaats te zetten zijn.")
    assert tekst == ""


def test_afwijzing_houdt_wel_zijn_eigen_korte_tekst(monkeypatch):
    """Een nette afsluiter bij een 'nee' is geen verkooppraat en blijft bestaan."""
    monkeypatch.setattr(L, "is_klant", lambda adres: False)
    tekst = L._concept_tekst({"email": "x@y.nl"}, "geen interesse", soort="afwijzing")
    assert tekst.strip()
    assert L.VIDEO not in tekst
    assert "19,99" not in tekst


# ------------------------------------------------------- oude SDK mag niet stil breken
class _NepAntwoord:
    stop_reason = "end_turn"
    content: list = []


class _OudeSDK:
    """Bootst een anthropic-SDK na die `output_config` nog niet kent.

    Precies wat er op de server draaide: anthropic 0.34.2 uit september 2024.
    De aanroep gooide een TypeError, die netjes werd opgevangen, en vanaf dat
    moment kreeg iedere lead in stilte het sjabloon.
    """

    def __init__(self):
        self.aanroepen = []

    class _Messages:
        def __init__(self, ouder):
            self.ouder = ouder

        def create(self, **kw):
            self.ouder.aanroepen.append(kw)
            if "output_config" in kw:
                raise TypeError(
                    "Messages.create() got an unexpected keyword argument 'output_config'")
            return _NepAntwoord()

    @property
    def messages(self):
        return self._Messages(self)


def test_te_oude_sdk_probeert_opnieuw_zonder_de_onbekende_parameter():
    client = _OudeSDK()
    antwoord = L._claude(client, model="claude-opus-5", max_tokens=100,
                         output_config={"effort": "low"},
                         messages=[{"role": "user", "content": "hoi"}])
    assert antwoord is not None
    assert len(client.aanroepen) == 2, "hij hoort het één keer opnieuw te proberen"
    assert "output_config" not in client.aanroepen[1]
    # De rest van de aanvraag blijft ongemoeid.
    assert client.aanroepen[1]["model"] == "claude-opus-5"


def test_een_echte_fout_wordt_niet_stilgehouden():
    """Alleen een onbekende parameter mag een tweede poging krijgen."""
    class _Stuk:
        class _M:
            def create(self, **kw):
                raise TypeError("create() missing 1 required positional argument: 'model'")

        @property
        def messages(self):
            return self._M()

    with pytest.raises(TypeError):
        L._claude(_Stuk(), max_tokens=100, messages=[])


# ------------------------------------------------------------------ de aanhef
#
# Aanleiding, 28-08-2026. Albert Kok kreeg als koude mail "Hi kok
# modelauto&#x27;s," — zijn winkelnaam als voornaam, én ongeschonden HTML zoals
# Marktplaats die teruggeeft. Twee fouten in één regel, en het is de eerste
# regel die iemand leest.
def test_html_codes_komen_nooit_in_een_naam():
    lead = {"email": "albertkok63@gmail.com", "name": "kok modelauto&#x27;s"}
    assert "&#" not in L._bedrijfsnaam(lead)
    assert L._bedrijfsnaam(lead) == "kok modelauto's"
    assert "&#" not in L._tekst(lead, L.MAIL1)


def test_een_verkopersnaam_wordt_nooit_als_voornaam_gebruikt():
    """Ook niet als hij toevallig als een naam van een mens leest.

    De namen hieronder komen uit de echte lijst. Elke poging om er met een regel
    een voornaam uit te halen liep hierop stuk: "Hi Boutique," is niet beter dan
    "Hi kok modelauto's,"."""
    for naam in ("kok modelauto's", "Vintage Kleding Store B.V.", "Boutique MoDo",
                 "Trimsalon Sanndjees", "Houtkamp Lederwaren", "Albert Kok",
                 "de Kledingkast", "Emtrade", "2ehands Import"):
        lead = {"email": "info@ergens.nl", "name": naam}
        assert L._persoonsnaam(lead) == "", naam
        assert L._aanhef(lead) == "Hi", naam
        assert L._tekst(lead, L.MAIL1).startswith("Hi,\n"), naam


def test_een_voornaam_die_er_echt_staat_mag_wel_in_de_aanhef():
    assert L._aanhef({"email": "a@b.nl", "voornaam": "Albert"}) == "Hi Albert"
    assert L._aanhef({"email": "a@b.nl", "contactpersoon": "Albert Kok"}) == "Hi Albert"


def test_het_emailadres_wordt_nooit_een_aanhef():
    """"Hi Zilverwebsite," leest als een rondzendbrief, en dat is het ook."""
    assert L._aanhef({"email": "info@zilverwebsite.nl"}) == "Hi"
