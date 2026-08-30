"""
Dezelfde trui mag niet twee keer in de voorraad staan — en als dat toch zo is,
mag het dashboard niet doen alsof hij nergens op staat.

Aanleiding (30-08-2026): op de eigen voorraad stonden 46 items die in
werkelijkheid 13 artikelen waren. Bij elk van die rijen zei het dashboard "staat
niet op Vinted", terwijl de Vinted-advertentie gewoon aan de zusterrij hing. Eén
druk op Publish had daar een tweede advertentie van gemaakt.
"""
import re
from pathlib import Path

import pytest

from backend.services.tweelingen import (
    advertentiecode, plausibel, zelfde_artikel, groepeer, zusters,
    bekende_merken_van, nummer_van,
)

WORTEL = Path(__file__).resolve().parents[1]


# ── Het advertentienummer ────────────────────────────────────────────────
def test_nummer_uit_de_titel_overleeft_de_vertaling():
    nl = "(1032) Grijs Ralph Lauren Zip Vest - Heren L - Goed"
    en = "(1032) Grey Ralph Lauren Zip Vest - Men L - Good"
    assert advertentiecode(nl) == advertentiecode(en) == "1032"


def test_eigen_sku_tussen_haakjes_telt_ook():
    assert advertentiecode("(REV-36689077) Trui") == "REV-36689077"
    assert advertentiecode("[IMP-B73A940F] Trui") == "IMP-B73A940F"


def test_een_maat_of_woord_is_geen_nummer():
    # Zou dit wel een nummer zijn, dan werd élk XL-artikel familie van elkaar —
    # en bij een verkoop kregen ze allemaal een verwijderopdracht.
    for titel in ["(XL) trui", "(new) shirt", "(2x) blikjes", "Gewoon een titel",
                  "(1237, 1238) Twee truien"]:
        assert advertentiecode(titel) is None, titel
    assert nummer_van({"title": "(XL) trui"}) == ""


def test_sku_valt_alleen_terug_op_een_kaal_nummer():
    assert advertentiecode("Geen code", "1327") == "1327"
    assert advertentiecode("Geen code", "IMP-AB12CD34") is None


# ── De harde controle eromheen ───────────────────────────────────────────
def test_zelfde_nummer_maar_andere_kleur_maat_merk_of_prijs_telt_niet():
    basis = {"title": "(99) Blauwe Nike trui - Heren M", "price": 20, "brand": "Nike"}
    gevallen = {
        "colour": {"title": "(99) Rode Nike trui - Heren M", "price": 20, "brand": "Nike"},
        "size":   {"title": "(99) Blauwe Nike trui - Heren XL", "price": 20, "brand": "Nike"},
        "brand":  {"title": "(99) Blauwe Adidas trui - Heren M", "price": 20, "brand": "Adidas"},
        "price":  {"title": "(99) Blauwe Nike trui - Heren M", "price": 200, "brand": "Nike"},
    }
    merken = {"nike", "adidas"}
    for reden, ander in gevallen.items():
        assert plausibel(basis, ander, merken) == reden
        assert zelfde_artikel(basis, ander, merken) is False


def test_vertaalde_tweeling_wordt_wel_herkend():
    nl = {"id": "a", "title": "(1314) Donkergroen Suitable Half Zip - Heren XL", "price": 14.99}
    en = {"id": "b", "title": "(1314) Dark Green Suitable Half Zip - Men XL", "price": 14.99}
    assert zelfde_artikel(nl, en, {"suitable"}) is True


def test_zonder_nummer_nooit_samenvoegen():
    # Twee truien die alleen op de maat na identiek heten scoren bijna 1,0 op
    # tekstgelijkenis. Zonder nummer blijft het antwoord nee.
    a = {"id": "a", "title": "Navy Denham Half Zip - Men M", "price": 15}
    b = {"id": "b", "title": "Navy Denham Half Zip - Men M", "price": 15}
    assert zelfde_artikel(a, b, set()) is False


# ── Groeperen ────────────────────────────────────────────────────────────
def _voorraad():
    return [
        {"id": "1", "title": "(1032) Grey Ralph Lauren Zip Vest - Men L - Good",
         "price": 24.99, "brand": "Ralph Lauren", "created_at": "2026-07-03T09:26:00"},
        {"id": "2", "title": "(1032) Grijs Ralph Lauren Zip Vest - Heren L - Goed",
         "price": 24.99, "brand": "Ralph Lauren", "created_at": "2026-08-25T10:33:00"},
        {"id": "3", "title": "(1032) Grijs Ralph Lauren Zip Vest - Heren L - Goed",
         "price": 24.99, "brand": "Ralph Lauren", "created_at": "2026-08-25T10:34:00"},
        {"id": "4", "title": "(1317) Navy Denham Half Zip - Men M",
         "price": 14.99, "brand": "Denham", "created_at": "2026-07-03T09:26:00"},
    ]


def test_groep_bevat_alle_kopieen_en_begint_bij_de_oudste():
    groepen = groepeer(_voorraad())
    assert len(groepen) == 1
    assert [i["id"] for i in groepen[0]] == ["1", "2", "3"]


def test_een_item_zonder_kopie_vormt_geen_groep():
    groepen = groepeer(_voorraad())
    assert all("4" not in [i["id"] for i in g] for g in groepen)


def test_zusters_geeft_de_andere_rijen():
    v = _voorraad()
    assert sorted(i["id"] for i in zusters(v[0], v)) == ["2", "3"]
    assert zusters(v[3], v) == []


def test_hergebruikt_nummer_splitst_de_groep():
    # Dezelfde verkoper, hetzelfde nummer, maar aantoonbaar twee artikelen.
    v = [
        {"id": "a", "title": "(150) Blauwe Nike trui - Heren M", "price": 20,
         "brand": "Nike", "created_at": "2026-01-01"},
        {"id": "b", "title": "(150) Blauwe Nike trui - Heren M", "price": 20,
         "brand": "Nike", "created_at": "2026-01-02"},
        {"id": "c", "title": "(150) Rode Adidas broek - Heren XL", "price": 20,
         "brand": "Adidas", "created_at": "2026-01-03"},
    ]
    groepen = groepeer(v)
    assert len(groepen) == 1
    assert sorted(i["id"] for i in groepen[0]) == ["a", "b"]


def test_bekende_merken_van_negeert_leegte():
    assert bekende_merken_van([{"brand": "Nike"}, {"brand": ""}, {}]) == {"nike"}


# ── De import maakt geen kopieën meer ────────────────────────────────────
def test_import_matcht_op_het_advertentienummer():
    from backend.api import imports as imp
    items = [{"id": "bestaand", "title": "(1032) Grey Ralph Lauren Zip Vest - Men L",
              "price": 24.99, "brand": "Ralph Lauren", "created_at": "2026-07-03"}]
    cand = {"platform": "2dehands", "platform_listing_id": "m999",
            "title": "(1032) Grijs Ralph Lauren Zip Vest - Heren L", "price": 24.99}
    item_id, reden = imp._match_candidate(cand, items, {}, {"ralph lauren"})
    assert (item_id, reden) == ("bestaand", "same_code")


def test_import_pakt_de_oudste_rij_als_er_al_kopieen_zijn():
    from backend.api import imports as imp
    items = [
        {"id": "nieuw", "title": "(1032) Grijs vest - Heren L", "price": 24.99,
         "created_at": "2026-08-25"},
        {"id": "oudste", "title": "(1032) Grey vest - Men L", "price": 24.99,
         "created_at": "2026-07-03"},
    ]
    cand = {"platform": "marktplaats", "platform_listing_id": "m1",
            "title": "(1032) Grijs vest - Heren L", "price": 24.99}
    assert imp._match_candidate(cand, items, {}, set())[0] == "oudste"


def test_verschillend_artikel_met_hetzelfde_nummer_wordt_geen_koppeling():
    from backend.api import imports as imp
    items = [{"id": "x", "title": "(1032) Blauwe trui - Heren M", "price": 20,
              "brand": "Nike", "created_at": "2026-07-03"}]
    cand = {"platform": "vinted", "platform_listing_id": "9",
            "title": "(1032) Rode broek - Heren XL", "price": 20, "brand": "Adidas"}
    assert imp._match_candidate(cand, items, {}, {"nike", "adidas"}) == (None, None)


def test_tweede_advertentie_krijgt_een_eigen_regel_onder_hetzelfde_item():
    bron = (WORTEL / "backend/api/imports.py").read_text()
    start = bron.index("match_id, reden = _match_candidate(\n")
    blok = bron[start:bron.index("_backfill_item_from_candidate(db, match_id", start)]
    # Geen nieuw item meer: de advertentie krijgt een eigen listing-regel.
    assert 'db.table("listings").insert({' in blok
    assert '"item_id": match_id' in blok
    # En het advertentienummer van een ANDERE advertentie mag nooit overschreven
    # worden — dat was hoe advertenties uit beeld verdwenen.
    assert 'str(r.get("platform_listing_id")) == str(pid)' in blok


def test_titelmatch_houdt_zijn_rem():
    # Tien identieke blikjes plectrums zijn tien voorwerpen, geen één.
    bron = (WORTEL / "backend/api/imports.py").read_text()
    assert 'reden == "same_title" and _tweede_advertentie(' in bron


# ── Publiceren zet er geen tweede advertentie bij ────────────────────────
def test_publiceren_slaat_een_kanaal_over_waar_de_zuster_al_staat():
    bron = (WORTEL / "backend/services/crosslist.py").read_text()
    blok = bron[bron.index("STAAT DIT ARTIKEL ER AL OP"):bron.index("api_platforms = [p for p in platforms if p in API_PLATFORMS]")]
    assert "familie_ids" in blok
    assert '"status": "duplicate"' in blok
    # Alleen levende advertenties tellen: een verwijderde advertentie mag
    # publiceren niet blokkeren.
    assert '["active", "hidden", "pending", "relisting"]' in blok
    # En het kanaal valt uit de lijst, dus er wordt niets in de wachtrij gezet.
    assert "platforms = [p for p in platforms if p not in bezet]" in blok


def test_publiceren_kijkt_naar_de_levende_regel_niet_de_eerste():
    bron = (WORTEL / "backend/services/crosslist.py").read_text()
    assert 'row = next((r for r in rijen' in bron


# ── Samenvoegen ──────────────────────────────────────────────────────────
class _Antwoord:
    def __init__(self, data): self.data = data


class _Vraag:
    def __init__(self, db, tabel, soort):
        self.db, self.tabel, self.soort, self.filters = db, tabel, soort, {}
        self.payload = None

    def select(self, *a, **k): return self
    def insert(self, p): self.payload = p; return self
    def update(self, p): self.payload = p; return self
    def delete(self): return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.filters[k] = list(v); return self

    def execute(self):
        self.db.log.append((self.tabel, self.soort, dict(self.filters), self.payload))
        if self.tabel == "items" and self.soort == "select":
            gevraagd = self.filters.get("id")
            gevraagd = gevraagd if isinstance(gevraagd, list) else [gevraagd]
            return _Antwoord([r for r in self.db.items
                              if r["id"] in gevraagd
                              and r["user_id"] == self.filters.get("user_id", r["user_id"])])
        return _Antwoord([])


class _DB:
    def __init__(self, items):
        self.items, self.log = items, []

    def table(self, naam):
        class _T:
            def __init__(s, db, naam): s.db, s.naam = db, naam
            def select(s, *a, **k): return _Vraag(s.db, s.naam, "select")
            def insert(s, p): return _Vraag(s.db, s.naam, "insert").insert(p)
            def update(s, p): return _Vraag(s.db, s.naam, "update").update(p)
            def delete(s): return _Vraag(s.db, s.naam, "delete")
        return _T(self, naam)


def _merge(items, keep, merge):
    from backend.api import items as items_api
    db = _DB(items)
    items_api.get_db = lambda: db
    uit = items_api.merge_items({"keep": keep, "merge": merge}, user_id="u1")
    return uit, db.log


def test_samenvoegen_verhuist_advertenties_en_verwijdert_de_kopie():
    items = [
        {"id": "a", "user_id": "u1", "title": "(1032) Grey vest - Men L", "price": 24.99, "brand": "RL"},
        {"id": "b", "user_id": "u1", "title": "(1032) Grijs vest - Heren L", "price": 24.99, "brand": "RL"},
    ]
    uit, log = _merge(items, "a", ["b"])
    assert uit["merged"] == ["b"] and uit["refused"] == []
    assert ("listings", "update", {"item_id": "b"}, {"item_id": "a"}) in log
    assert ("jobs", "update", {"item_id": "b"}, {"item_id": "a"}) in log
    assert any(t == "items" and s == "delete" and f.get("id") == "b" for t, s, f, _ in log)


def test_samenvoegen_weigert_twee_verschillende_artikelen():
    items = [
        {"id": "a", "user_id": "u1", "title": "(1032) Blauwe Nike trui - Heren M", "price": 20, "brand": "Nike"},
        {"id": "b", "user_id": "u1", "title": "(1032) Rode Adidas broek - Heren XL", "price": 20, "brand": "Adidas"},
    ]
    uit, log = _merge(items, "a", ["b"])
    assert uit["merged"] == []
    assert uit["refused"] == [{"id": "b", "reason": "not_the_same_article"}]
    # En er is niets aangeraakt.
    assert not any(s in ("update", "delete") for _, s, _, _ in log)


def test_samenvoegen_raakt_andermans_item_niet_aan():
    items = [
        {"id": "a", "user_id": "u1", "title": "(1032) Grey vest", "price": 20},
        {"id": "b", "user_id": "u2", "title": "(1032) Grijs vest", "price": 20},
    ]
    uit, log = _merge(items, "a", ["b"])
    assert uit["refused"] == [{"id": "b", "reason": "not_found"}]
    assert not any(s in ("update", "delete") for _, s, _, _ in log)


def test_samenvoegen_eist_beide_velden():
    from fastapi import HTTPException
    from backend.api import items as items_api
    for body in ({}, {"keep": "a"}, {"merge": ["b"]}, {"keep": "a", "merge": ["a"]}):
        with pytest.raises(HTTPException) as e:
            items_api.merge_items(body, user_id="u1")
        assert e.value.status_code == 400


# ── Het scherm zegt niet langer "staat er niet op" ───────────────────────
def test_dashboard_telt_de_advertenties_van_de_zusterrij_mee():
    app = (WORTEL / "frontend/app.html").read_text()
    blok = app[app.index("function renderPlatformMatrix"):app.index("function renderPlatformCheckboxes")] \
        if "function renderPlatformCheckboxes" in app else app[app.index("function renderPlatformMatrix"):]
    assert "state.dupSisters[itemId]" in blok
    assert "s-twin" in blok
    # De stip mag niet klikbaar zijn: "markeer als geplaatst" zou hier juist een
    # tweede advertentie uitlokken.
    assert "&& !bySister[p]" in blok


def test_dashboard_heeft_een_samenvoegknop():
    app = (WORTEL / "frontend/app.html").read_text()
    assert 'id="duplicate-bar"' in app
    assert "function renderDuplicateBar" in app
    assert "renderDuplicateBar();" in app
    assert "mergeAllDuplicates" in app and "/api/items/merge" in app


def test_dubbelen_worden_niet_elke_ronde_opnieuw_opgehaald():
    # Een volledige voorraaduitlezing elke 15 seconden legde de server plat bij
    # de grote accounts; de groepen veranderen alleen bij import of samenvoegen.
    app = (WORTEL / "frontend/app.html").read_text()
    blok = app[app.index("async function loadDuplicates"):app.index("async function loadAll")]
    assert "Date.now() - _dupTs < 600000" in blok
    assert "loadDuplicates(true)" in app
