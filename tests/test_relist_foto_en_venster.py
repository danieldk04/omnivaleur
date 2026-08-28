"""Vier klachten over herplaatsen op Marktplaats, en de vier fixes erachter.

1. "Bij het herplaatsen neemt hij elke keer maar één foto mee."
   Een geïmporteerde advertentie kwam met één foto binnen (de zoeklijst van
   Marktplaats geeft alleen het omslagplaatje). De volledige reeks staat op de
   advertentiepagina, en die zien we vlak vóór het verwijderen.

2. "Ik moet elke keer zelf op Verlaten drukken, dan publiceert hij meteen."
   Een tabblad sluiten van een half ingevuld Marktplaats-formulier laat Chrome
   "Site verlaten?" vragen. Tot er geklikt wordt staat álles stil, ook het
   tabblad dat op dat moment een advertentie invult.

3. "Het scherm komt elke keer in beeld waar hij aan het listen is."
   Het werkvenster werd bij elke publicatie uitgeklapt.

4. "<br/> staat letterlijk in de advertentietekst."
   Items uit Shopify dragen HTML mee; het tekstveld van Marktplaats is plat.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BG = (ROOT / "extension/background.js").read_text(encoding="utf-8")
SHARED = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "extension/manifest.json").read_text(encoding="utf-8")
JOBS = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
SHOPIFY = (ROOT / "backend/platforms/shopify_importer.py").read_text(encoding="utf-8")


# ── 1. Alle foto's mee bij herplaatsen ───────────────────────────────────────

def test_advertentie_wordt_vastgelegd_voor_verwijderen():
    fn = BG.split("async function bgDeleteMp2dh(")[1]
    assert "snapshot = await mpAdvertentieSnapshot(tabId)" in fn, \
        "zonder snapshot komt een geïmporteerde advertentie met één foto terug"
    assert "captured_listing: snapshot" in fn


def test_snapshot_leest_de_hele_galerij_en_de_grootste_versie():
    fn = BG.split("async function mpAdvertentieSnapshot(")[1].split("\nasync function")[0]
    assert "Thumbnails-module-item" in fn, "de miniatuurrij is de bron van de volgorde"
    assert "MP_FOTO_REGEL" in fn
    assert 'const MP_FOTO_REGEL = "ecg_mp_eps$_86"' in BG


def test_server_vult_ook_het_item_zelf_aan():
    blok = JOBS.split("# HET ITEM ZELF OOK BIJWERKEN.")[1].split("elif job[\"action\"]")[0]
    assert 'patch["photo_urls"] = cap_photos' in blok
    assert "<= 1" in blok, "een verkoper die zijn foto's zelf koos wordt nooit overruled"
    for veld in ("brand", "size", "color", "condition"):
        assert veld in blok, f"{veld} hoort ook uit de live advertentie te komen"


# ── 2. Nooit meer "Site verlaten?" ───────────────────────────────────────────

def test_afsluitvraag_wordt_ontwapend_voor_sluiten():
    assert (ROOT / "extension/content/unload_guard.js").exists()
    assert "async function ontwapenAfsluitvraag(tabId)" in BG
    assert "function sluitWerkTabblad(" in BG
    # geen enkel werk-tabblad wordt nog rauw gesloten
    ruw = [l for l in BG.splitlines()
           if "chrome.tabs.remove(" in l and "ontwapenAfsluitvraag" not in l]
    assert not ruw, f"deze sluiten nog zonder ontwapening: {ruw}"


def test_ook_wegnavigeren_ontwapent():
    assert "async function stuurWerkTabbladNaar(tabId, url)" in BG
    assert "await ontwapenAfsluitvraag(tabId)" in \
        BG.split("async function stuurWerkTabbladNaar(tabId, url) {")[1].split("\n}")[0]


def test_wacht_draait_vroeg_en_in_de_hoofdwereld():
    assert '"content/unload_guard.js"' in MANIFEST
    blok = MANIFEST.split('"content/unload_guard.js"')[1].split("}")[0]
    assert '"document_start"' in blok, "later is te laat: de pagina heeft zich dan al aangemeld"
    assert '"MAIN"' in blok, "in onze eigen wereld zien we de meldingen van de pagina niet"


def test_wacht_doet_uit_zichzelf_niets():
    guard = (ROOT / "extension/content/unload_guard.js").read_text(encoding="utf-8")
    assert "window.__ovDisarmUnload" in guard
    # de melding gaat pas weg als wíj erom vragen — niet zomaar bij elk bezoek
    assert "let ontwapend = false;" in guard


# ── 3. Het werkvenster blijft uit beeld ──────────────────────────────────────

def test_werkvenster_klapt_nooit_meer_open():
    inner = BG.split("async function openWorkerTabInner(")[1].split("\n}")[0]
    assert 'const wantState = "minimized";' in inner
    assert 'wantState = opts.silent ? "minimized" : "normal"' not in BG
    assert 'chrome.windows.create({ url: leeg, focused: false, ...WORKER_WIN_SIZE })' \
        not in inner.split("catch")[0], "een gewoon venster komt in beeld"


# ── 4. Geen HTML in een plat tekstveld ───────────────────────────────────────

def test_beschrijving_wordt_platgeslagen_voor_elk_formulier():
    assert "function platteTekst(" in SHARED
    assert "const value = platteTekst(text)" in SHARED, "fillDescription slaat het over"
    assert "const tekst = platteTekst(ruweTekst)" in SHARED, \
        "de echte toetsaanslag zou de HTML er weer overheen typen"
    assert "platteTekst," in SHARED.split("window.CL = ")[1], "niet gedeeld met de platforms"


def test_import_haalt_fotos_en_kenmerken_van_de_advertentiepagina():
    """De zoeklijst van Marktplaats geeft alleen titel, prijs en omslagplaatje.

    Merk, maat, kleur en de rest van de foto's staan op de advertentiepagina —
    dezelfde pagina die deze ronde toch al ophaalt voor de omschrijving.
    """
    enrich = (ROOT / "backend/services/mp_enrich.py").read_text(encoding="utf-8")
    assert "def _kenmerken_uit_html(" in enrich
    assert "def _fotos_uit_html(" in enrich
    assert 'FOTO_REGEL = "ecg_mp_eps$_86"' in enrich
    fn = enrich.split("async def een(paar):")[1].split("verwerkt, _ =")[0]
    assert "volledige_advertentie(client" in fn
    assert 'patch["photo_urls"] = fotos' in fn
    assert 'for veld in ("brand", "size", "color", "condition")' in fn


def test_maat_emmertjes_van_marktplaats_komen_niet_in_het_item():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mp_enrich_test", ROOT / "backend/services/mp_enrich.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._onze_maat("Maat 46/48 (XL) of groter") == "XL"
    assert mod._onze_maat("Overige maten") == ""
    assert mod._onze_maat("46") == "46"
    assert mod._onze_conditie("Zo goed als nieuw") == "good"
    assert mod._onze_conditie("Gedragen") == "fair"
    assert mod._onze_conditie("Nieuw met prijskaartje") == "new_with_tags"


def test_kenmerken_worden_uit_de_echte_paginavorm_gelezen():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mp_enrich_test2", ROOT / "backend/services/mp_enrich.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Letterlijk de vorm zoals hij op 28-08-2026 op een echte advertentie stond.
    stuk = ('<div class="Attributes-module-item"><div class="Attributes-module-label">'
            'Conditie</div><div class="Attributes-module-value">Gedragen</div></div>'
            '<div class="Attributes-module-item"><div class="Attributes-module-label">'
            'Maat</div><div class="Attributes-module-value">M</div></div>')
    k = mod._kenmerken_uit_html(stuk)
    assert k["conditie"] == "Gedragen" and k["maat"] == "M"
    foto = ('src="//images.marktplaats.com/api/v1/hz-mp-pro-listing/images/'
            '09b1bd24-9c8a-441b-a890-e7e8905cbbc0?rule=ecg_mp_eps$_82"')
    assert mod._fotos_uit_html(foto) == [
        "https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/"
        "09b1bd24-9c8a-441b-a890-e7e8905cbbc0?rule=ecg_mp_eps$_86"]


def test_shopify_import_bewaart_platte_tekst():
    assert "def _platte_tekst(" in SHOPIFY
    assert '"description": _platte_tekst(desc_raw),' in SHOPIFY, \
        "body_html rechtstreeks opslaan zet <br/> in elke advertentie"
