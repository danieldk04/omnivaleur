"""
Tijdelijk meetpunt. De serverlogs zijn niet van buitenaf te lezen, dus zonder
dit is een storing op de server onzichtbaar: het enige dat de browser te zien
kreeg was een vervangen foutpagina van Cloudflare.
"""
from collections import deque

# Laatste verzoeken: methode, route zonder id's, status, duur. Geen inhoud.
RECENT: deque = deque(maxlen=100)

# Laatste echte foutmeldingen van de database, zodat de oorzaak zichtbaar is
# ook wanneer Cloudflare het antwoord onderweg vervangt.
ERRORS: deque = deque(maxlen=20)


def record_error(waar: str, exc: BaseException) -> None:
    ERRORS.append({"waar": waar, "fout": f"{type(exc).__name__}: {exc}"[:300]})
