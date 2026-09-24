"""Het Nederlandse dashboard is compleet: geen enkele zin blijft Engels.

WAAROM (Daniel, 24-09-2026). Klanten (Toon, Johan) vroegen om een Nederlands
dashboard. Het dashboard blijft in het Engels geschreven; frontend/i18n.js
vertaalt op het scherm met frontend/i18n/nl.json. Dat werkt alleen zolang elke
Engelse zin ook in dat woordenboek staat. Half vertaald is slechter dan Engels
(een half-Nederlandse melding leest als een storing, team-notes 03-09-2026),
dus deze proef faalt zodra er een zin bijkomt zonder vertaling.

Nieuwe tekst gebouwd en deze proef faalt? Dan:
  1. python3 scripts/i18n_extract.py   (toont wat ontbreekt, met bestand:regel)
  2. zet de vertaling in frontend/i18n/nl.json, of, als het geen tekst voor de
     gebruiker is (klassenaam, API-veld), de regel in frontend/i18n/negeer.txt
  3. python3 scripts/i18n_extract.py --versie   (anders krijgen browsers het
     oude woordenboek uit hun cache)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import i18n_extract as x  # noqa: E402

WB = json.loads(x.WOORDENBOEK.read_text(encoding="utf-8"))
PLEK = re.compile(r"\{(\d+)(?:\|[^|}]*\|[^}]*)?\}")


def test_elke_zin_heeft_een_vertaling():
    mist = x.ontbrekend()
    regels = [f"  {v['plekken'][0]}: {t}" for t, v in list(mist.items())[:40]]
    assert not mist, (
        f"{len(mist)} Engelse zin(nen) zonder Nederlandse vertaling. Voeg ze toe aan "
        "frontend/i18n/nl.json (of negeer.txt als het geen tekst voor de gebruiker is):\n"
        + "\n".join(regels)
    )


def test_woordenboek_is_schoon():
    for en, nl in WB.items():
        assert isinstance(nl, str) and nl.strip(), f"lege vertaling voor {en!r}"
        assert en == en.strip() and "  " not in en, f"sleutel met losse witruimte: {en!r}"
        # Een lijst of opmaak die de browser niet toont hoort er niet in.
        assert "<" not in en or ">" not in en, f"HTML in sleutel: {en!r}"


def test_plekken_kloppen():
    """Elke {n} in de vertaling bestaat in het Engels. Een {n} uit het Engels
    mag alleen wegvallen als het een meervouds-s is ({1|dag|dagen})."""
    for en, nl in WB.items():
        in_en = set(re.findall(r"\{(\d+)\}", en))
        in_nl = set(PLEK.findall(nl))
        assert in_nl <= in_en, f"{en!r}: vertaling gebruikt {in_nl - in_en} die niet bestaat"
        # Wat wegvalt moet een meervoudsplek zijn: in het Engels direct na een woord.
        for n in in_en - in_nl:
            assert re.search(r"[a-z]\{" + n + r"\}", en), (
                f"{en!r}: {{{n}}} valt weg in de vertaling {nl!r} (een getal of naam kwijt?)"
            )


def test_patronen_zijn_niet_te_ruim():
    """Een patroon met {0} geldt voor ELKE tekst die erop past, ook voor een titel
    van een klant. "{0} day{1}" zou "Sale day was" vertalen, en "{0} {1}" alles.
    Elk patroon heeft daarom vaste tekst om op te passen."""
    for en in WB:
        if not re.search(r"\{\d+\}", en):
            continue
        vast = re.sub(r"\{\d+\}", "", en)
        letters = re.findall(r"[A-Za-z]", vast)
        # Een tijdsduur als "~{0}m {1}s" is door de ~ al specifiek genoeg.
        genoeg = (len(letters) >= 3 and re.search(r"[A-Za-z]{2}", vast)) or ("~" in vast and letters)
        assert genoeg, f"patroon met te weinig vaste tekst: {en!r}"


def test_woordenboekversie_staat_in_elke_pagina():
    versie = x.versie()
    for naam in x.PAGINAS:
        src = (x.FRONTEND / naam).read_text(encoding="utf-8")
        m = re.search(r'<script src="/i18n\.js\?v=([0-9a-f]+)"></script>', src)
        assert m, f"{naam} laadt de vertaallaag niet"
        assert m.group(1) == versie, (
            f"{naam} vraagt woordenboekversie {m.group(1)}, maar nl.json is nu {versie}. "
            "Draai: python3 scripts/i18n_extract.py --versie"
        )
        # Als eerste script in de kop, anders flitst het Engels even voorbij.
        assert src.index("/i18n.js") < src.index("</head>"), f"{naam}: i18n.js hoort in de kop"
        eerste = re.search(r"<script\b", src)
        assert eerste and "/i18n.js" in src[eerste.start():eerste.start() + 60], (
            f"{naam}: i18n.js moet het eerste script zijn"
        )


def test_extensiemenu_blijft_engels_in_de_uitleg():
    """De extensie zelf (popup) is Engels en gaat via de Chrome Web Store. Een
    vertaalde verwijzing naar een knop die daar anders heet, stuurt de klant de
    verkeerde kant op."""
    popup = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
    for label in ("Calm mode", "Business account (Admarkt)", "Let Omnivaleur type like a keyboard"):
        assert label in popup, f"{label!r} staat niet meer in de popup; pas nl.json aan"
        for en, nl in WB.items():
            if label in en:
                assert label in nl, f"{en!r}: popupknop {label!r} is vertaald naar {nl!r}"


def test_negeerlijst_bevat_geen_zinnen():
    """Wie een echte zin op de negeerlijst zet in plaats van hem te vertalen,
    laat hem stil Engels. Zinnen horen in nl.json."""
    for regel in x.negeerlijst():
        woorden = re.findall(r"[A-Za-z]{2,}", regel)
        engels = len(x._EN.findall(regel))
        assert not (len(woorden) >= 5 and engels >= 3), f"zin op de negeerlijst: {regel!r}"


def test_vertaler_volgt_dezelfde_regels_als_de_browser():
    """Proef op de Python-kopie van de regels in i18n.js (letterlijk, patroon,
    zin voor zin, voorvoegsel, technische staart)."""
    vt = x.Vertaler(WB)
    assert vt.vertaal("Save") == "Opslaan"
    assert vt.vertaal("12 items total") == "{0} items totaal"
    assert vt.vertaal("Vinted: Could not save") is not None
    assert vt.vertaal("Saved. Could not save") == "Opgeslagen. Kon niet opslaan"
    assert vt.vertaal("Het staat er al") is None
