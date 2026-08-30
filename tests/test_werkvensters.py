"""Eén werkvenster, niet zeven.

De extensie doet haar werk in een apart Chrome-venster. Het nummer van dat
venster stond alleen in het werkgeheugen van de extensie, en dat wordt bij elke
update gewist. Het oude venster bleef dan gewoon staan terwijl de extensie dacht
dat ze er geen had — en maakte er een nieuwe bij. Na een dag bijwerken stonden er
zeven, acht lege vensters onderin de balk.

De oplossing: het venster draagt een herkenbaar anker-tabblad (een eigen pagina
van de extensie), zodat het altijd terug te vinden is.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BG = (ROOT / "extension/background.js").read_text(encoding="utf-8")


def test_anker_is_een_eigen_pagina():
    assert (ROOT / "extension/keeper.html").exists(), "het anker-tabblad mist"
    assert 'const KEEPER_URL = chrome.runtime.getURL("keeper.html")' in BG, \
        "een lege pagina is niet te herkennen als ons venster"


def test_venster_wordt_teruggezocht_voor_er_een_nieuwe_komt():
    inner = BG.split("async function openWorkerTabInner(")[1].split("\n}")[0]
    assert "vindEnOpruimenWerkvensters()" in inner
    # en dat gebeurt vóór het aanmaken van een nieuw venster
    assert inner.index("vindEnOpruimenWerkvensters()") < inner.index("chrome.windows.create")


def test_lege_restanten_worden_opgeruimd():
    fn = BG.split("async function vindEnOpruimenWerkvensters()")[1].split("\n}\n")[0]
    assert "chrome.windows.remove" in fn
    # nooit een venster sluiten waar nog iets van de gebruiker in staat
    assert "alleenAnker" in fn
    assert 'tabs.every(t => t.url === "about:blank" || !t.url)' in fn, \
        "oude, lege vensters mogen alleen dicht als ALLES erin leeg is"


def test_opruimen_gebeurt_ook_bij_starten_en_bijwerken():
    assert "chrome.runtime.onInstalled.addListener(() => { opruimenBijStart(); });" in BG
    assert "chrome.runtime.onStartup.addListener(() => { opruimenBijStart(); });" in BG


# ── De gele foutopsporingsbalk van Chrome ─────────────────────────────────────
#
# Chrome zet boven élk venster waaraan een extensie zich koppelt de balk
# "'Omnivaleur' is begonnen met foutopsporing voor deze browser", mét een knop
# "Annuleren". Die koppeling stond bij ieder werk-tabblad aan, ook bij scannen,
# Vinted, eBay en verwijderen — waar hij niets doet. Amanda stuurde er op
# 30-08-2026 een foto van als "een foutmelding wat betreft de browser".
#
# Nodig is hij op precies één plek: het plaatsformulier van Marktplaats en
# 2dehands, waar het verborgen omschrijvingsveld een échte toetsaanslag eist
# (zie typEchteToets).

def _koppel_vroeg() -> str:
    return BG.split("async function koppelVroeg(")[1].split("\n}\n")[0]


def test_koppelen_alleen_op_het_plaatsformulier():
    fn = _koppel_vroeg()
    assert "HEEFT_TOETSEN_NODIG" in fn, \
        "zonder toets op het adres koppelt de extensie aan élk werk-tabblad"
    # en dat gebeurt vóór het koppelen zelf
    assert fn.index("HEEFT_TOETSEN_NODIG") < fn.index("chrome.debugger.attach")


def test_de_toets_herkent_alleen_de_plaatspaginas():
    import re
    regel = re.search(r"^const HEEFT_TOETSEN_NODIG = (/.+/i);$", BG, flags=re.M)
    assert regel, "HEEFT_TOETSEN_NODIG staat er niet als losse regel"
    patroon = regel.group(1)
    # De JS-regex omzetten naar Python: alleen \b en de vorm zijn hier gelijk.
    py = re.compile(patroon[1:-2].replace("(?:", "(?:"), re.I)
    mag = [
        "https://www.marktplaats.nl/plaats/621/636?bucketId=162&title=",
        "https://marktplaats.nl/plaats/1784/1789?title=",
        "https://www.2dehands.be/plaats/621/636?title=",
    ]
    mag_niet = [
        "https://www.vinted.nl/items/new",
        "https://www.marktplaats.nl/my-account/sell/index.html",
        "https://www.marktplaats.nl/v/antiek-en-kunst/antiek-lampen/m123-vintage-lamp",
        "https://www.ebay.nl/sh/lst/active",
        "about:blank",
    ]
    for u in mag:
        assert py.match(u), f"{u} hoort wél te koppelen"
    for u in mag_niet:
        assert not py.match(u), f"{u} hoort NIET te koppelen — dat is de gele balk voor niets"


def test_elk_werk_tabblad_geeft_zijn_adres_mee():
    # Een aanroep zonder adres zou de toets hierboven overslaan en dus
    # stilzwijgend terugvallen op "altijd koppelen".
    import re
    aanroepen = re.findall(r"await koppelVroeg\(([^)]*)\)", BG)
    assert aanroepen, "koppelVroeg wordt nergens aangeroepen"
    for a in aanroepen:
        assert "," in a, f"koppelVroeg({a}) krijgt geen adres mee"
