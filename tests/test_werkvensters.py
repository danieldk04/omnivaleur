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


def test_koppelen_alleen_waar_het_nodig_is():
    fn = _koppel_vroeg()
    assert "koppelingNodig" in fn, \
        "zonder toets op het adres koppelt de extensie aan élk werk-tabblad"
    # en dat gebeurt vóór het koppelen zelf
    assert fn.index("koppelingNodig") < fn.index("chrome.debugger.attach")


def test_koppelingnodig_kent_beide_redenen():
    fn = BG.split("function koppelingNodig(")[1].split("\n}\n")[0]
    assert "HEEFT_TOETSEN_NODIG" in fn and "VINTED_FORMULIER_KLOK" in fn, \
        "beide redenen om te koppelen horen hier langs te komen"


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


# ── Het Vinted-formulier loopt stil zonder koppeling ──────────────────────────
#
# GEMETEN 15-09-2026. In een tabblad dat niet in beeld staat knijpt Chrome de
# setTimeout van de PAGINA af tot één per seconde, en na vijf minuten verborgen
# nog verder. Onze eigen pauzes lopen via een Web Worker en merken dat niet, maar
# Vinted's formulier draait op de klok van de pagina: keuzelijsten, suggesties en
# controles wachten op een timer die bijna stilstaat. Daniel zag precies dat:
# "er gebeurt niks totdat ik er zelf naartoe klik". Een debugger-koppeling zet
# die rem uit, zoals een open DevTools dat doet — dat is waarom Marktplaats er
# nooit last van had.

def test_het_vinted_formulier_koppelt_wel():
    import re
    regel = re.search(r"^const VINTED_FORMULIER_KLOK = (/.+/i);$", BG, flags=re.M)
    assert regel, "VINTED_FORMULIER_KLOK staat er niet als losse regel"
    py = re.compile(regel.group(1)[1:-2], re.I)
    mag = [
        "https://www.vinted.nl/items/new",
        "https://www.vinted.be/items/new",
        "https://www.vinted.com/items/new",
        "https://www.vinted.co.uk/items/new",
        "https://www.vinted.nl/items/6543210/edit",
    ]
    mag_niet = [
        # scannen en verwijderen gaan via Vinted's eigen API en hebben de klok
        # van het formulier niet nodig: daar zou de gele balk puur schade zijn.
        "https://www.vinted.nl/items/6543210",
        "https://www.vinted.nl/member/12345",
        "https://www.marktplaats.nl/v/kleding/m123-jas",
        "about:blank",
    ]
    for u in mag:
        assert py.match(u), f"{u} hoort wél te koppelen"
    for u in mag_niet:
        assert not py.match(u), f"{u} hoort NIET te koppelen"


def test_tabblad_dat_van_de_verkoper_wordt_gaat_los():
    # Blijft het tabblad open zodat hij het zelf afmaakt, dan hoort Chrome's gele
    # foutopsporingsbalk weg te zijn voor hij ernaar kijkt.
    blok = BG.split("awaitingManualFinish: true, manueleControles: 0")[1][:400]
    assert "ontkoppelVroeg(" in blok, \
        "een opengelaten tabblad houdt anders de gele balk vast"
