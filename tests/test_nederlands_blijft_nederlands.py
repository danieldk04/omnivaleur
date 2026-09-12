"""Een Nederlandse advertentie mag niet in het Engels op Marktplaats komen.

GEMETEN (12-09-2026, Toon van De Juiste Toon). Zijn tapijt stond in het Engels
op Marktplaats terwijl de database gewoon Nederlands bevatte. Oorzaak: bij het
herplaatsen ging de Nederlandse tekst opnieuw door "vertaal naar het
Nederlands", en het model draaide de richting om — 3 van de 6 pogingen kwamen
in het Engels terug, met `_taal: nl` erop, dus niemand zag er iets van.

Deze proef draait zonder echte vertaaldienst: elke aanroep van het model geeft
hier gegarandeerd Engels terug. Voor de reparatie zakte deze test; erna wordt
het model niet eens meer gebeld, want de tekst stond al goed.
"""
import backend.services.crosslist as cl


def test_nederlandse_tekst_gaat_niet_langs_het_model(monkeypatch):
    geroepen = []

    def _nooit(text, target_lang, brand=None):
        geroepen.append(text)
        return "Characterized by geometric patterns and vibrant colors"

    monkeypatch.setattr(cl, "_vertaal", _nooit)

    item = {
        "title": "Handgeknoopt Perzisch Shiraz wollen tapijt 135/80 cm",
        "description": (
            "TL07\n\nKenmerkt zich door geometrische patronen en levendige kleuren\n\n"
            "In vaal rode kleur met blauw ecru en oranje accenten\n\n"
            "Afmeting: 135/80 cm\n\nDejuistetoon Etten-Leur"
        ),
    }
    uit = cl.localiseer_sync(dict(item), "marktplaats")

    assert geroepen == [], "Nederlandse tekst hoort niet naar de vertaaldienst te gaan"
    assert uit["title"] == item["title"]
    assert uit["description"] == item["description"]
    assert uit[cl.TAAL_VELD] == "nl"


def test_een_omgedraaide_vertaling_wordt_geweigerd(monkeypatch):
    """Komt het antwoord tóch in de andere taal terug, dan wint de brontekst."""
    class _Antwoord:
        content = [type("T", (), {"text": (
            "The item has a great condition and will be shipped from the "
            "Netherlands with care for you and your family"
        )})()]

    class _Client:
        class messages:
            @staticmethod
            def create(**kw):
                return _Antwoord()

    monkeypatch.setattr(cl, "_claude_client", lambda: _Client())

    bron = ("Dit kleed is van wol en heeft een mooie kleur, het is niet "
            "beschadigd en wordt met zorg verstuurd naar u")
    assert cl._vertaal(bron, "nl") == bron


def test_laatste_zeef_vertrouwt_het_stempel_niet(monkeypatch):
    """Engelse tekst met `_taal: nl` erop mag de deur niet uit.

    Precies wat er op 11-09-2026 gebeurde: het model draaide de richting om, de
    opdracht kreeg toch het stempel "nl", en de zeef liet hem daarop door.
    """
    import backend.api.jobs as jobs

    engels = {
        "title": "Handgeknoopt Perzisch Shiraz wollen tapijt 135/80 cm",
        "description": (
            "TL07\n\nCharacterized by geometric patterns and vibrant colors\n\n"
            "In muted red color with blue ecru and orange accents\n\n"
            "Size: 135/80 cm\n\nThe item will be shipped with care for you"
        ),
        "_taal": "nl",
    }
    baan = {"id": "j1", "action": "create", "platform": "marktplaats", "payload": dict(engels)}

    # De vertaling doet het niet beter: ze geeft dezelfde Engelse tekst terug.
    monkeypatch.setattr(cl, "_vertaal", lambda text, taal, brand=None: text)

    gemeld = []
    monkeypatch.setattr(jobs, "_meld_vertaalstoring", lambda reden: gemeld.append(reden))

    class _Db:
        def table(self, *a, **kw):
            raise AssertionError("mag niets wegschrijven")

    door = jobs._zet_taal_goed(_Db(), [baan])

    assert door == [], "Engelse advertentie is toch naar Marktplaats gestuurd"
    assert gemeld, "niemand is gewaarschuwd"
