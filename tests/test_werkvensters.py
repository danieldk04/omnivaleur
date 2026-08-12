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
