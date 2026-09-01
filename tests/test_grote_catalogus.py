"""Wat er misging bij een verkoper met 5.533 advertenties.

AANLEIDING (01-09-2026, telefoongesprek met Egbert Brouwer, Papa's Plectrums).
Drie klachten, en ze bleken alle drie hetzelfde te delen: iets dat bij honderd
artikelen niet opvalt, wordt bij vijfduizend een muur.

1. Het overzicht laden duurde eindeloos, bleef op een leeg scherm hangen of
   eindigde in een tijdverloop (502). Nagemeten op zijn echte gegevens:
   /api/listings/ deed er 17,9 seconden over, omdat het eerst alle item-id's
   ophaalde, die in brokken van 200 hakte en pér brok een vraag stelde — en dat
   daarna nog eens overdeed om bij elke advertentie de titel te zoeken. Ruim
   zeventig vragen achter elkaar binnen één verzoek. Met één gekoppelde vraag:
   1,5 seconde. De catalogus zelf was 13,4 MB ongecomprimeerd; ingepakt 1,53 MB.

2. De import meldde "alles opgehaald" terwijl bij honderd tot tweehonderd
   artikelen de prijs of de omschrijving ontbrak. Marktplaats levert die bij een
   zakelijke (Admarkt) import niet mee. De automatische aanvulronde op de server
   keek alleen naar lege omschrijvingen, dus wie alleen prijzen miste kwam nooit
   aan de beurt — gemeten: één account met 185 zulke artikelen.

3. Hij draaide 1.0.258 terwijl de Chrome Web Store op 1.0.279 stond, en het
   dashboard zei al die tijd groen "Extension active". De harde ondergrens
   (1.0.244) blokkeert alleen wat aantoonbaar niet kán werken; alles daarboven
   gold als in orde, hoeveel versies achter ook.
"""
import re
import sys
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL))

from backend.api import jobs as jobs_api  # noqa: E402
from backend.api import listings as listings_api  # noqa: E402

APP = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")


# ── Een minimale nabootsing van de Supabase-bouwer ───────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.kolommen, self.filters, self.in_filter = "", {}, None
        self.vanaf = self.tot = None

    def select(self, kolommen="*", **_kw):
        self.kolommen = kolommen
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def in_(self, k, waarden):
        self.in_filter = (k, list(waarden))
        return self

    def or_(self, tekst):
        self.db.or_filters.append(tekst)
        return self

    def order(self, *_a, **_k):
        return self

    def range(self, vanaf, tot):
        self.vanaf, self.tot = vanaf, tot
        return self

    def execute(self):
        self.db.verzoeken.append(self)
        rijen = self.db.rijen.get(self.tabel, [])
        if self.tabel == "listings" and "items!inner" in self.kolommen:
            gewenst = self.filters.get("items.user_id")
            rijen = [r for r in rijen
                     if self.db.items_op_id[r["item_id"]]["user_id"] == gewenst]
            rijen = [{**r, "items": {
                k: self.db.items_op_id[r["item_id"]][k] for k in ("title", "sku", "user_id")}}
                for r in rijen]
        else:
            rijen = [r for r in rijen
                     if all(r.get(k) == v for k, v in self.filters.items())]
            if self.in_filter:
                kolom, waarden = self.in_filter
                rijen = [r for r in rijen if r.get(kolom) in waarden]
        rijen = sorted(rijen, key=lambda r: r["id"])
        if self.vanaf is not None:
            rijen = rijen[self.vanaf:self.tot + 1]
        return type("R", (), {"data": rijen, "count": len(rijen)})()


class _DB:
    def __init__(self, items, listings):
        self.rijen = {"items": items, "listings": listings}
        self.items_op_id = {i["id"]: i for i in items}
        self.verzoeken, self.or_filters = [], []

    def table(self, naam):
        return _Q(self, naam)


def _voorraad(aantal=450, user="u1"):
    items = [{"id": f"it{n:04d}", "user_id": user, "title": f"artikel {n}",
              "sku": f"SKU{n}"} for n in range(aantal)]
    listings = [{"id": f"ls{n:04d}", "item_id": f"it{n:04d}",
                 "platform": "marktplaats", "status": "active"} for n in range(aantal)]
    return _DB(items, listings)


# ── 1. Het lege scherm en de tijdverloop ─────────────────────────────────────

def test_advertentielijst_kost_een_handvol_vragen_in_plaats_van_tientallen():
    """Dit is de aanroep die de gateway opgaf. De oude weg schaalde met het
    aantal ARTIKELEN (één vraag per 200 id's, plus dezelfde ronde nog eens voor
    de titels); de nieuwe met het aantal ADVERTENTIES, in pagina's van 1.000."""
    db = _voorraad(450)
    uit = listings_api._listings_via_items(db, "u1", None, None)
    assert len(uit) == 450
    # 450 advertenties = één volle pagina en dan een lege: twee vragen. De oude
    # weg deed er hier al negen, en bij Egbert ruim zeventig.
    assert len(db.verzoeken) <= 2, [q.tabel for q in db.verzoeken]


def test_titel_en_sku_staan_los_op_de_advertentie_net_als_eerst():
    """Het dashboard en de extensie lezen l.title en l.sku. Kwamen die in een
    apart blokje binnen, dan zou de extensie geen enkele verkochte advertentie
    meer herkennen — die matcht juist op de SKU."""
    db = _voorraad(3)
    uit = listings_api._listings_via_items(db, "u1", None, None)
    for l in uit:
        assert l["title"] and l["sku"]
        assert "items" not in l, "het gekoppelde blokje hoort platgeslagen te zijn"


def test_de_snelle_en_de_oude_weg_geven_hetzelfde_terug():
    db = _voorraad(120)
    snel = listings_api._listings_via_items(db, "u1", None, None)
    oud = listings_api._listings_per_brok(db, "u1", None, None)
    sleutel = lambda r: (r["id"], r["title"], r["sku"])  # noqa: E731
    assert sorted(map(sleutel, snel)) == sorted(map(sleutel, oud))


def test_alleen_de_eigen_advertenties(monkeypatch):
    db = _voorraad(5, user="u1")
    db.rijen["items"].append({"id": "vreemd", "user_id": "u2", "title": "x", "sku": "y"})
    db.items_op_id["vreemd"] = db.rijen["items"][-1]
    db.rijen["listings"].append({"id": "lsX", "item_id": "vreemd",
                                 "platform": "marktplaats", "status": "active"})
    uit = listings_api._listings_via_items(db, "u1", None, None)
    assert [l["id"] for l in uit] == [f"ls{n:04d}" for n in range(5)]


def test_valt_de_snelle_weg_weg_dan_komt_de_oude_erachteraan(monkeypatch):
    """De snelle weg leunt op de sleutel tussen listings en items. Verdwijnt die
    ooit, dan is traag oneindig veel beter dan een verkoper die denkt dat zijn
    advertenties weg zijn."""
    db = _voorraad(10)
    monkeypatch.setattr(listings_api, "get_db", lambda: db)
    monkeypatch.setattr(listings_api, "_listings_via_items",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("geen sleutel")))
    uit = listings_api.list_all_listings(user_id="u1")
    assert len(uit) == 10


def test_antwoorden_gaan_ingepakt_over_de_lijn():
    """13,4 MB tegen 1,53 MB. Zonder dit blijft een grote catalogus minuten
    onderweg, hoe snel de server hem ook opdiept."""
    from backend.main import app
    namen = [m.cls.__name__ for m in app.user_middleware]
    assert "GZipMiddleware" in namen


def test_het_scherm_haalt_de_catalogus_in_pagina_s_van_duizend():
    """29 vragen achter elkaar tegen 7. De server begrenst hem op dezelfde 1.000,
    zodat één aanroep nooit de hele voorraad kan opeisen."""
    blok = APP.split("async function fetchAllItems(")[1].split("return all;")[0]
    assert "const pageSize = 1000;" in blok
    from backend.api import items as items_api
    bron = (WORTEL / "backend" / "api" / "items.py").read_text(encoding="utf-8")
    assert "limit = max(1, min(limit, 1000))" in bron


def test_een_lege_eerste_lading_toont_voortgang_en_geen_leeg_scherm():
    """Bij 5.533 artikelen duurt de eerste lading seconden. Zonder een teken van
    leven leest dat als 'hij doet het niet' — precies wat Egbert meldde."""
    assert "function _toonLaadVoortgang(" in APP
    assert "fetchAllItems(_toonLaadVoortgang)" in APP


# ── 2. De halve import ───────────────────────────────────────────────────────

def test_de_automatische_aanvulronde_kijkt_ook_naar_de_prijs():
    """Keek alleen naar lege omschrijvingen. Een verkoper bij wie de tekst wél
    binnenkwam maar de prijs niet, kwam daardoor nooit aan de beurt — gemeten op
    de echte database: 185 artikelen die om die reden nooit zijn aangeraakt."""
    bron = (WORTEL / "backend" / "services" / "mp_enrich.py").read_text(encoding="utf-8")
    blok = bron.split("async def _verkopers_met_gaten")[1].split("\nasync def ")[0]
    m = re.search(r'\.or_\("([^"]+)"\)', blok)
    assert m, "geen or_-filter gevonden in _verkopers_met_gaten"
    filt = m.group(1)
    assert "description.is.null" in filt and "description.eq." in filt
    assert "price.is.null" in filt and "price.eq.0" in filt


def test_de_import_zwijgt_niet_meer_over_wat_er_leeg_binnenkwam():
    """"✅ Import successful" terwijl er tweehonderd artikelen zonder prijs of
    tekst in staan, is geen geslaagde import maar een halve."""
    assert "function mistKernGegevens(" in APP
    blok = APP.split("async function bulkImportAllCandidates(")[1].split("\nasync function ")[0]
    assert "mistKernGegevens" in blok, "de import telt niet wat er leeg is"
    assert "vulUitMarktplaats(" in blok, "de import haalt het ontbrekende niet op"
    assert "${aanvulNote}" in blok, "de slotmelding vertelt het niet"


def test_de_import_blijft_niet_eindeloos_ophalen():
    """Vier rondes, geen zestig: anders zit hij na een import van duizenden
    advertenties nog tien minuten voor een wachtscherm. De rest haalt de server
    zelf op, elk kwartier een ronde."""
    blok = APP.split("async function bulkImportAllCandidates(")[1].split("\nasync function ")[0]
    assert re.search(r"vulUitMarktplaats\([^;]*?\),\s*4\)", blok, re.S), blok[-1500:]


def test_de_knop_en_de_import_gebruiken_dezelfde_ronde():
    """Eén ronde, twee aanroepers. Anders loopt het gedrag van de knop en dat van
    de import na de eerste reparatie uit elkaar."""
    assert APP.count("async function vulUitMarktplaats(") == 1
    blok = APP.split("async function fillFromMarktplaats(")[1].split("\nasync function ")[0]
    assert "await vulUitMarktplaats(" in blok


# ── 3. De extensie die stil achterliep ───────────────────────────────────────

def test_de_versie_wordt_uit_de_web_store_gelezen_en_niet_geraden():
    """De bestandsnaam in de doorverwijzing van Google draagt de versie:
    ..._1_0_279_0.crx. We halen die crx niet op — alleen de kopregel."""
    m = jobs_api._CRX_VERSIE.search("GFAOGAPBHAACFBPDPPDCMNKJNDLPHLEH_1_0_279_0.crx")
    assert m and f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}" == "1.0.279"


def test_geen_antwoord_van_google_betekent_geen_melding(monkeypatch):
    """Liever geen bijwerkmelding dan een verkeerde. Valt Google weg, dan blijft
    published leeg en verandert er niets aan wat het scherm laat zien."""
    jobs_api._WEBSTORE_CACHE.update(versie=None, ts=0.0, ok=False)
    import httpx
    monkeypatch.setattr(httpx, "get",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("weg")))
    assert jobs_api._gepubliceerde_extensieversie() is None
    jobs_api._WEBSTORE_CACHE.update(versie=None, ts=0.0, ok=False)


def test_google_wordt_hoogstens_een_keer_per_uur_bevraagd(monkeypatch):
    jobs_api._WEBSTORE_CACHE.update(versie=None, ts=0.0, ok=False)
    aanroepen = []

    class _R:
        headers = {"location": "https://x/ABC_1_0_300_0.crx"}

    def _nep(*a, **k):
        aanroepen.append(1)
        return _R()

    import httpx
    monkeypatch.setattr(httpx, "get", _nep)
    assert jobs_api._gepubliceerde_extensieversie() == "1.0.300"
    assert jobs_api._gepubliceerde_extensieversie() == "1.0.300"
    assert len(aanroepen) == 1
    jobs_api._WEBSTORE_CACHE.update(versie=None, ts=0.0, ok=False)


def test_het_endpoint_geeft_beide_grenzen():
    jobs_api._WEBSTORE_CACHE.update(versie="1.0.279", ts=9e9, ok=True)
    uit = jobs_api.extension_version(user_id="u1")
    assert uit["published"] == "1.0.279"
    assert uit["minimum"] == ".".join(str(x) for x in jobs_api.MINIMALE_SCANVERSIE)
    jobs_api._WEBSTORE_CACHE.update(versie=None, ts=0.0, ok=False)


def test_boven_de_ondergrens_maar_achter_is_melden_en_niet_blokkeren():
    """1.0.258 kán publiceren, dus blokkeren zou onterecht zijn. Maar groen
    'Extension active' terwijl er eenentwintig versies nieuwer klaarstaan is
    precies hoe Egbert wekenlang op een oude kopie bleef zitten."""
    assert "function extVersionAchter(" in APP
    blok = APP.split("function extVersionAchter(")[1].split("\n}")[0]
    # de harde ondergrens houdt voorrang: daar hoort het blokkerende venster
    assert "extVersionIsOld()" in blok
    assert "_gepubliceerdeVersie" in blok
    assert 'id="ext-update-banner"' in APP
    assert "function dismissExtUpdateBanner(" in APP


def test_de_zijbalk_zegt_niet_langer_groen_in_orde_bij_een_achterstand():
    blok = APP.split("function renderExtStatus(")[1].split("\n}")[0]
    assert "extVersionAchter()" in blok
    # rindex: de tekst "Extension active" staat ook in de toelichting bovenaan.
    # Het gaat om de laatste — de regel die het groene label echt zet.
    assert blok.index("extVersionAchter()") < blok.rindex("Extension active")
