"""Verkopen buiten Vinted: vragen in plaats van gokken.

WAAROM DIT ER IS (30-08-2026)
Daniel zag alleen Vinted-verkopen in zijn overzicht. Klopt: van zijn 26 verkopen
stond er geen enkele op Marktplaats, terwijl hij daar 110 advertenties had staan.
De oorzaak zit niet in onze code maar in Marktplaats zelf — verkoop je met de
hand, dan komt er nooit een "verkocht" op je advertentie; jij haalt hem weg. Het
enige wat wij zien is dat de advertentie er niet meer is, en dat betekent daar
óók "verlopen na 30 dagen".

Automatisch boeken op afwezigheid is daarom uitgesloten: dat haalt een nog levend
artikel van Vinted, eBay en de webshop af, en dat is onherstelbaar werk. In
plaats daarvan wordt het als "mogelijk verkocht" gemeld en beantwoordt de
verkoper de vraag zelf.

Deze test bewaakt de drempels die die vraag betrouwbaar maken. Elke regel die
hier staat is er één die, als hij wegvalt, de verkoper onterechte vragen
oplevert — of erger, zijn voorraad overal weghaalt.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BG = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")

from backend.api import listings as api  # noqa: E402


# ── 1. De extensie trekt geen conclusie uit een mislukte blik ────────────────

def test_een_leeg_overzicht_levert_geen_enkele_verdenking_op():
    """Gaf de overzichtspagina niets terug, dan weten we niet of er advertenties
    ontbreken of dat de pagina simpelweg niet geladen is. Dan lijkt ALLES
    verdwenen en zou de verkoper honderden vragen krijgen."""
    assert "if (!ads.length) {" in BG
    aanhef = BG.split("if (!ads.length) {", 1)[1][:400]
    assert "deze ronde wordt niets als verdwenen geteld" in aanhef


def test_vier_uitkomsten_blijven_uit_elkaar():
    """"Weg" en "verkocht" leiden tot verschillende conclusies, en "onbekend"
    (401 bij een zakelijk account, serverfout) mag nooit als bewijs tellen."""
    functie = BG.split("async function bekijkEigenPagina(", 1)[1].split("\n}", 1)[0]
    for oordeel in ('"verkocht"', '"weg"', '"leeft"', '"onbekend"'):
        assert oordeel in functie, f"{oordeel} wordt niet meer teruggegeven"
    # 401/403/5xx is niets bewezen, geen verdwenen advertentie.
    assert 'if (!r.ok) return "onbekend";' in functie
    # 404 is dat wél.
    assert 'if (r.status === 404 || r.status === 410) return "weg";' in functie


def test_een_label_telt_meteen_en_afwezigheid_pas_na_twee_rondes():
    """Het label op de advertentiepagina is bewijs; afwezigheid is een aanwijzing
    en moet twee aparte rondes standhouden."""
    assert 'teBevestigen.push({ ...regel, reden: "label" });' in BG
    assert "VERDENKING_MIN_MINUTEN" in BG
    assert "const VERDENKING_MIN_MINUTEN = 30;" in BG
    blok = BG.split('} else if (oordeel === "weg") {', 1)[1][:500]
    assert "nu - eerder.eerst >= VERDENKING_MIN_MINUTEN * 60000" in blok


def test_een_teruggevonden_advertentie_wist_de_verdenking():
    """Staat hij er weer, dan is er niets aan de hand — de telling moet vervallen,
    anders stapelt een oude hik alsnog op tot een verkoopvraag."""
    assert "if (gezien.has(l.platform_listing_id)) delete staat[`${platform}:${l.platform_listing_id}`];" in BG


def test_elke_ronde_kijkt_een_stuk_verderop():
    """Zonder rotatie werden bij een groot account eeuwig dezelfde veertig
    advertenties nagekeken en kwam de rest nooit aan de beurt."""
    assert "mogelijk_verkocht_start_" in BG
    assert "gemist.slice(start, start + HAP)" in BG


def test_er_wordt_niets_verwijderd_op_dit_signaal():
    """De hele reden dat dit een vraag is: alleen melden, nooit afmelden."""
    blok = BG.split("const teBevestigen = [];", 1)[1].split("await verdenkingenOpslaan(staat);", 1)[0]
    assert "meldMogelijkeVerkopen" not in blok      # pas ná de lus, met de verzamelde regels
    assert "/api/listings/sold?" not in blok        # geen enkele directe verkoopboeking


# ── 2. De server markeert alleen, en raakt een echte verkoop nooit aan ───────

class _Q:
    """Een minimale nabootsing van de Supabase-bouwer, genoeg voor deze test."""

    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.op, self.velden = db, tabel, {}, None, None

    def select(self, *_a, **_k):
        self.op = "select"; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def in_(self, k, v):
        self.filters[f"in:{k}"] = list(v); return self

    def limit(self, _n):
        return self

    def execute(self):
        if self.tabel == "items":
            rijen = [i for i in self.db.items
                     if all(i.get(k) == v for k, v in self.filters.items() if not k.startswith("in:"))]
            return type("R", (), {"data": rijen})()
        rijen = [l for l in self.db.listings
                 if all(l.get(k) == v for k, v in self.filters.items() if not k.startswith("in:"))
                 and all(l.get(k[3:]) in v for k, v in self.filters.items() if k.startswith("in:"))]
        if self.op == "update":
            for l in rijen:
                l.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings

    def table(self, naam):
        return _Q(self, naam)


def _db(monkeypatch, listings):
    db = _DB([{"id": "it1", "user_id": "u1"}], listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    return db


def test_een_al_bevestigde_verkoop_wordt_nooit_teruggezet(monkeypatch):
    """Een 'sold' rij mag niet terugvallen naar een vraag: dan zou een bevestigde
    verkoop opnieuw als onzeker in beeld komen en uit Analytics verdwijnen."""
    db = _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "sold"}])
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats", "reden": "weg"}]},
                      user_id="u1")
    assert db.listings[0]["status"] == "sold"


def test_een_actieve_advertentie_wordt_gemarkeerd_met_de_reden(monkeypatch):
    db = _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "active"}])
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats", "reden": "label"}]},
                      user_id="u1")
    rij = db.listings[0]
    assert rij["status"] == "sold_unconfirmed"
    assert "toont zelf" in rij["error_message"]


def test_het_item_van_iemand_anders_blijft_ongemoeid(monkeypatch):
    db = _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "active"}])
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats"}]}, user_id="iemand-anders")
    assert db.listings[0]["status"] == "active"


def test_de_reden_mag_niet_op_een_mislukte_herplaatsing_lijken():
    """Het herplaats-overzicht herkent een mislukte herplaatsing aan deze woorden
    in hetzelfde veld. Staan ze in onze tekst, dan toont het dashboard een
    verkoopvraag als kapotte herplaatsing."""
    for tekst in api.VERDENKING_REDENEN.values():
        laag = tekst.lower()
        for verboden in ("relist", "delist", "still live"):
            assert verboden not in laag, f"{verboden!r} staat in de reden: {tekst}"
    # En het scherm zet er hoe dan ook een slot op.
    assert "l.status !== 'sold_unconfirmed' && l.error_message && /relist|delist|still live/i" in APP


# ── 3. Het antwoord van de verkoper ──────────────────────────────────────────

def test_ja_verkocht_boekt_de_verkoop_en_ruimt_elders_op(monkeypatch):
    from fastapi import BackgroundTasks
    db = _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "sold_unconfirmed", "id": "l1"}])
    taken = BackgroundTasks()
    uit = api.answer_possibly_sold({"item_id": "it1", "platform": "marktplaats",
                                    "verkocht": True, "sold_price": "22,50"},
                                   taken, user_id="u1")
    assert uit["status"] == "sold"
    assert len(taken.tasks) == 1                      # de normale verkoopafhandeling
    assert taken.tasks[0].args[:2] == ("it1", "marktplaats")
    assert taken.tasks[0].args[2] == 22.50            # komma-notatie wordt gelezen
    assert db.listings[0]["status"] == "sold_unconfirmed"  # de taak doet het werk


def test_nee_zet_hem_in_het_archief_en_niet_terug_op_live(monkeypatch):
    """Terug op 'active' zou betekenen dat de verkoopcontrole hem volgende ronde
    opnieuw ziet verdwijnen en de vraag eindeloos terugkomt."""
    from fastapi import BackgroundTasks
    db = _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "sold_unconfirmed", "id": "l1"}])
    uit = api.answer_possibly_sold({"item_id": "it1", "platform": "marktplaats", "verkocht": False},
                                   BackgroundTasks(), user_id="u1")
    assert uit["status"] == "delisted"
    assert db.listings[0]["status"] == "delisted"
    assert db.listings[0]["error_message"] is None


def test_zonder_openstaande_vraag_gebeurt_er_niets(monkeypatch):
    from fastapi import BackgroundTasks
    from fastapi import HTTPException
    _db(monkeypatch, [{"item_id": "it1", "platform": "marktplaats", "status": "active", "id": "l1"}])
    with pytest.raises(HTTPException) as e:
        api.answer_possibly_sold({"item_id": "it1", "platform": "marktplaats", "verkocht": True},
                                 BackgroundTasks(), user_id="u1")
    assert e.value.status_code == 404


# ── 4. Het scherm stelt de vraag ook echt ────────────────────────────────────

def test_de_vraag_staat_boven_de_itemlijst_met_beide_knoppen():
    assert 'id="sold-confirm-bar"' in APP
    assert "function renderSoldConfirmBar()" in APP
    assert "renderSoldConfirmBar();" in APP.split("function renderItemsTable(items) {", 1)[1][:200]
    assert "answerPossiblySold('${item.id}','${p}',true" in APP
    assert "answerPossiblySold('${item.id}','${p}',false" in APP
    # En hij zegt erbij dat er nog niets is weggehaald.
    assert "Nothing has been removed anywhere yet" in APP


def test_de_vraag_staat_ook_bij_analytics():
    """Daniel zocht ze in Analytics, want daar kijk je naar verkopen — en daar
    stonden ze niet. Een onbeantwoorde vraag is precies het verschil tussen wat
    je verkocht hebt en wat de omzet laat zien, dus hij hoort op beide plekken."""
    assert 'id="an-sold-confirm-bar"' in APP
    assert "const SOLD_CONFIRM_BARS = ['sold-confirm-bar', 'an-sold-confirm-bar'];" in APP
    # En Analytics tekent hem ook echt, anders blijft het vak leeg.
    kop = APP.split("function renderAnalytics(force) {", 1)[1][:900]
    assert "renderSoldConfirmBar();" in kop
    # Wel zichtbaar, niet meegeteld: de omzet hierboven blijft bevestigde verkopen.
    assert "none of this counts towards your revenue until you answer" in APP
    tabel = APP.split("// ── Sales breakdown table", 1)[1][:1200]
    assert "sold_unconfirmed" not in tabel


# ── 5. Het oordeel over één advertentiepagina, echt uitgevoerd ──────────────
# Een tekstcontrole zegt niets over wat de code bij een 403 of een doorstuur
# doet, en juist dáár zit het verschil tussen "verkocht" en "de sessie is weg".
# Daarom draait de functie hier echt, met nagebootste antwoorden van Marktplaats.

_GEVALLEN = [
    ("404 bestaat niet meer", {"status": 404}, "weg"),
    ("410 weggehaald", {"status": 410}, "weg"),
    ("401 zakelijk account zonder sessie", {"status": 401}, "onbekend"),
    ("403 geblokkeerd", {"status": 403}, "onbekend"),
    ("500 serverfout", {"status": 500}, "onbekend"),
    ("doorgestuurd naar de homepage",
     {"redirected": True, "url": "https://www.marktplaats.nl/", "html": "<h1>Marktplaats</h1>"}, "weg"),
    ("doorgestuurd binnen dezelfde advertentie",
     {"redirected": True, "url": "https://www.marktplaats.nl/v/kleding/m123-blazer", "html": "m123 blazer"}, "leeft"),
    ("label verkocht", {"html": "<div>m123</div><span>Verkocht</span>"}, "verkocht"),
    ("label gereserveerd", {"html": "m123 Gereserveerd"}, "verkocht"),
    ("het menu-item 'Verkochte artikelen' is geen verkoop",
     {"html": "m123 <a>Verkochte artikelen</a> blazer 39,50"}, "leeft"),
    ("tekst 'niet meer beschikbaar'", {"html": "Deze advertentie is niet meer beschikbaar"}, "weg"),
    ("gewone levende advertentie", {"html": "<h1>Blazer</h1> m123 39,50 Bieden"}, "leeft"),
    ("een pagina die ons advertentienummer niet noemt", {"html": "<h1>Zoekresultaten</h1>"}, "onbekend"),
]

_HARNAS = """
import fs from 'fs';
const src = fs.readFileSync(process.argv[2], 'utf8');
const code = src.slice(src.indexOf('const NIET_MEER_BESCHIKBAAR'),
                      src.indexOf('// \u2500\u2500 Verdenkingen die twee rondes'));
const gevallen = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const uit = [];
for (const g of gevallen) {
  globalThis.fetch = async () => ({
    status: g.status ?? 200, ok: (g.status ?? 200) < 400, redirected: !!g.redirected,
    url: g.url ?? 'https://www.marktplaats.nl/seller/view/m123',
    text: async () => g.html ?? '',
  });
  uit.push(await eval(code + '; bekijkEigenPagina')('marktplaats', 'm123'));
}
globalThis.fetch = async () => { throw new Error('offline'); };
uit.push(await eval(code + '; bekijkEigenPagina')('marktplaats', 'm123'));
console.log(JSON.stringify(uit));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node niet beschikbaar")
def test_het_oordeel_per_advertentiepagina(tmp_path):
    harnas = tmp_path / "verdict.mjs"
    harnas.write_text(_HARNAS, encoding="utf-8")
    invoer = tmp_path / "gevallen.json"
    invoer.write_text(json.dumps([g[1] for g in _GEVALLEN]), encoding="utf-8")

    r = subprocess.run(["node", str(harnas), str(ROOT / "extension" / "background.js"), str(invoer)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    uitkomsten = json.loads(r.stdout.strip().splitlines()[-1])

    verwacht = [g[2] for g in _GEVALLEN] + ["onbekend"]   # laatste: geen verbinding
    namen = [g[0] for g in _GEVALLEN] + ["geen verbinding"]
    fouten = [f"{n}: {u} in plaats van {v}"
              for n, u, v in zip(namen, uitkomsten, verwacht) if u != v]
    assert not fouten, "\n".join(fouten)
