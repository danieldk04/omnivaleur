"""Gedeelde afspraken voor de hele testmap.

DE CHROME WEB STORE HOORT NIET IN EEN TEST.

Sinds 07-09-2026 kijkt de uitgifte of een extensiekopie nog meebeweegt met de
versie die in de Chrome Web Store staat (`ACHTERSTAND_GRENS` in
backend/api/jobs.py). Die versie wordt live opgehaald. In een test is dat twee
keer verkeerd: er gaat verkeer naar Google bij iets wat daar niets mee te maken
heeft, en de uitslag verandert vanzelf zodra er een nieuwe versie uitgaat — dan
zakt een test die niets met versies doet, op een dag dat niemand iets heeft
aangeraakt.

Hier zetten we die vraag daarom uit: geen antwoord betekent "we weten het niet",
en dan houdt de uitgifte niets tegen. Precies zoals in productie wanneer Google
niet antwoordt. Een test die deze grens juist wél wil beproeven zet zelf een
versie terug (zie tests/test_kopie_werkt_zichzelf_niet_bij.py).
"""
import pytest


@pytest.fixture(autouse=True)
def _geen_webstore_vraag_in_tests(monkeypatch):
    try:
        from backend.api import jobs
    except Exception:  # noqa: BLE001 — een test die de server niet nodig heeft
        return
    monkeypatch.setattr(jobs, "_gepubliceerde_extensieversie", lambda: None,
                        raising=False)
