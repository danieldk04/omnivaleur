"""Gedeelde afspraken voor de hele testmap.

DE CHROME WEB STORE HOORT NIET IN EEN TEST.

Sinds 07-09-2026 kijkt de uitgifte of een extensiekopie nog meebeweegt met de
versie die in de Chrome Web Store staat (`ACHTERSTAND_GRENS` in
backend/api/jobs.py). Die versie wordt live opgehaald. In een test is dat twee
keer verkeerd: er gaat verkeer naar Google bij iets wat daar niets mee te maken
heeft, en de uitslag verandert vanzelf zodra er een nieuwe versie uitgaat — dan
zakt een test die niets met versies doet, op een dag dat niemand iets heeft
aangeraakt. Precies dat gebeurde: tien tests met een vaste versie in de hand
(1.0.286, 1.0.294) vielen om zodra de winkel op 1.0.311 stond.

Daarom vullen we het geheugenplekje waar dat antwoord in wordt bewaard vooraf
met "niets, en dat is nog lang geldig". Geen antwoord betekent in de code "we
weten het niet", en dan houdt de uitgifte niets tegen — net als in productie
wanneer Google niet antwoordt.

Bewust het geheugenplekje en niet de functie zelf: de tests die juist die functie
beproeven (tests/test_grote_catalogus.py) zetten dat plekje zelf terug en blijven
zo gewoon werken.
"""
import pytest


# GEEN ECHT STRIPE IN EEN TEST.
#
# backend/api/billing.py zet bij het laden `stripe.api_key` uit de lokale .env,
# dus de echte sleutel. De afreken-tests geven een verzonnen klantnummer mee
# ("cus_1"); `_levende_klant` vroeg daar bij Stripe zelf naar, kreeg "No such
# customer" en maakte dan een nieuwe klant aan met het testadres. Elke
# testronde zette zo klant@example.nl, vriend@example.nl en los@example.nl in
# het echte Stripe-dashboard (gemeten 10-10-2026: 28 klanten, 22 nep).
# Zonder sleutel weigert de Stripe-bibliotheek vóór er iets over het netwerk
# gaat. Tests die Stripe nodig hebben zetten hun eigen nep-klasse neer.
@pytest.fixture(autouse=True)
def _geen_echt_stripe_in_tests(monkeypatch):
    try:
        import stripe
    except Exception:  # noqa: BLE001 — een test die Stripe niet nodig heeft
        yield
        return
    try:
        # billing zet de sleutel bij het LADEN; laad hem dus eerst, anders zet de
        # eerste test die hem importeert de echte sleutel er na onze blokkade in.
        import backend.api.billing  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    monkeypatch.setattr(stripe, "api_key", None, raising=False)

    class _GeenNetwerk:
        name = "geen-netwerk-in-tests"

        def request(self, *a, **k):
            raise RuntimeError("Een test mag Stripe niet echt aanroepen: zet een nep-klasse neer")

        request_with_retries = request

        def close(self):
            pass

    monkeypatch.setattr(stripe, "default_http_client", _GeenNetwerk(), raising=False)
    yield


@pytest.fixture(autouse=True)
def _geen_webstore_vraag_in_tests():
    try:
        from backend.api import jobs
    except Exception:  # noqa: BLE001 — een test die de server niet nodig heeft
        yield
        return
    vorig = dict(jobs._WEBSTORE_CACHE)
    # ts ver in de toekomst: de geldigheidsduur is dan nooit verlopen, dus er
    # gaat geen enkel verzoek naar Google uit.
    jobs._WEBSTORE_CACHE.update(versie=None, ts=9e9, ok=False)
    try:
        yield
    finally:
        jobs._WEBSTORE_CACHE.clear()
        jobs._WEBSTORE_CACHE.update(vorig)


@pytest.fixture(autouse=True)
def _geen_echte_taalmodellen_in_tests(monkeypatch):
    """Sinds 23-09-2026 gaat elke taalvraag eerst naar Gemini (backend/services/
    taalmodel.py). Staat de echte Google-sleutel in .env, dan zou elke test die
    Claude nabootst stilletjes echt bij Google aankloppen. Standaard dus geen
    Google-sleutel; een test die Gemini zelf beproeft zet er een neer. En een
    nep-Anthropic-sleutel, zodat de tests die Claude nabootsen die route blijven
    nemen, ook op een machine zonder .env."""
    try:
        from backend.config import settings
    except Exception:  # noqa: BLE001
        return
    monkeypatch.setattr(settings, "google_api_key", "")
    if not settings.anthropic_api_key:
        monkeypatch.setattr(settings, "anthropic_api_key", "test-sleutel")
