"""Elke melding die de gebruiker in het dashboard ziet, is Engels.

Het dashboard is volledig Engels. Een half-Nederlandse foutmelding leest daar als
een storing in het programma in plaats van als uitleg, en is voor een niet-
Nederlandse gebruiker onbruikbaar. De extensie stuurt haar foutteksten één op één
door naar het dashboard, dus daar begint het.

Interne logregels (clog/console) mogen wél Nederlands blijven: die leest alleen
de ontwikkelaar.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRONNEN = [
    "extension/content/shared.js",
    "extension/content/vinted.js",
    "extension/content/marktplaats.js",
    "extension/content/tweedehands.js",
    "extension/content/facebook.js",
    "extension/background.js",
]

# Woorden die alleen in Nederlandse zinnen voorkomen (geen valse treffers op
# Engelse tekst of op veldnamen zoals "size" of "brand").
NEDERLANDS = re.compile(
    r"\b(niet|geen|kon|bleef|leeg|gevonden|advertentie|zoekertje|plaatsen|"
    r"beschrijving|verplicht|vul|klik|typ|opnieuw|mislukt|verlopen|tabblad|"
    r"knop|veld|uitgelogd|bieden|melding|gebruiker|omdat|werd|foto's)\b",
    re.I,
)
# Een throw of een `error:`-veld gaat rechtstreeks naar het dashboard.
NAAR_DE_GEBRUIKER = re.compile(r"(throw new Error\(|error:\s*)((?:[^;]|\n){0,400}?);")
TEKSTEN = re.compile(r'"([^"\n]{12,})"|`([^`]{12,})`')


def _nederlandse_meldingen(bestand: str):
    src = (ROOT / bestand).read_text(encoding="utf-8")
    uit = []
    for m in NAAR_DE_GEBRUIKER.finditer(src):
        for dubbel, backtick in TEKSTEN.findall(m.group(2)):
            tekst = dubbel or backtick
            if NEDERLANDS.search(tekst):
                uit.append((src[: m.start()].count("\n") + 1, tekst[:90]))
    return uit


@pytest.mark.parametrize("bestand", BRONNEN)
def test_geen_nederlandse_foutmeldingen(bestand):
    gevonden = _nederlandse_meldingen(bestand)
    assert not gevonden, f"Nederlandse tekst in een gebruikersmelding ({bestand}): {gevonden}"
