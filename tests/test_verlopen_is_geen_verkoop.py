"""Een verlopen advertentie is geen verkoop, dus ook geen verkoopvraag.

19-09-2026, Lynn van De Juiste Toon: "Bij Items staat bij 'did these items
sell?' de melding 'Not found on the platform anymore', maar als ik die dan na ga
dan staan ze er wel nog op. Voornamelijk bij 2dehands."

Allebei waar. Het zoekertje is van de zoekresultaten af, maar zijn eigen pagina
staat er nog, met foto's, tekst en VERLOPEN erop. Gemeten op haar account op
19-09-2026: van de 74 gemelde 2dehands-zoekertjes gaven er 55 HTTP 410 met "Dit
zoekertje is helaas verlopen"; van vijf bewezen levende advertenties gaf er nul
dat signaal.

Twee dingen zijn daarop gerepareerd:
1. de extensie meldt zo'n advertentie als "verlopen" en de server maakt er dan
   geen vraag van maar archiveert hem (hier getest);
2. een serverronde kijkt de vragen die er al stonden na op diezelfde pagina en
   trekt in wat aantoonbaar alleen verlopen is (hier getest).

De voor-en-na-proef op de echte pagina's staat in
tests/verlopen-is-geen-verkoop-test.mjs.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402
from backend.services import instellingen  # noqa: E402
from backend.services import verlopen_controle as vc  # noqa: E402


# ── Nagebootste database ────────────────────────────────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.op, self.velden = {}, {}, None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def limit(self, _n): return self
    def order(self, *_a, **_k): return self

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in vals for k, vals in self.in_filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": list(rijen)})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings

    def table(self, naam):
        return _Q(self, naam)


def _zet(monkeypatch, listings, vraag_aan=True):
    monkeypatch.setattr(instellingen, "lees",
                        lambda _uid: {**instellingen.STANDAARD,
                                      instellingen.VERKOOPVRAAG: vraag_aan})
    db = _DB([{"id": "it1", "user_id": "u1", "title": "(1308) Perzisch tapijtje"}], listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    return db


def _actief(platform="2dehands"):
    return [{"id": "l1", "item_id": "it1", "platform": platform, "status": "active"}]


# ── 1. De melding vanuit de extensie ────────────────────────────────────────

def test_verlopen_wordt_geen_verkoopvraag(monkeypatch):
    """Dit is de klacht van Lynn, letterlijk."""
    db = _zet(monkeypatch, _actief())
    uit = api.possibly_sold({"listings": [{"item_id": "it1", "platform": "2dehands",
                                           "reden": "verlopen"}]}, user_id="u1")
    assert db.listings[0]["status"] == "delisted", "verlopen is geen verkoop"
    assert "verlopen" in db.listings[0]["error_message"].lower()
    assert "Mogelijk verkocht" not in db.listings[0]["error_message"]
    assert uit["expired"] == 1


def test_een_verdwenen_advertentie_blijft_wel_een_vraag(monkeypatch):
    """De reparatie mag het echte geval niet meenemen: staat er geen uitleg op de
    pagina, dan weten we het niet en hoort de vraag er juist te zijn."""
    db = _zet(monkeypatch, _actief())
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "2dehands",
                                     "reden": "weg"}]}, user_id="u1")
    assert db.listings[0]["status"] == "sold_unconfirmed"
    assert "Mogelijk verkocht" in db.listings[0]["error_message"]


def test_een_verkocht_label_blijft_ook_een_vraag(monkeypatch):
    db = _zet(monkeypatch, _actief())
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "2dehands",
                                     "reden": "label"}]}, user_id="u1")
    assert db.listings[0]["status"] == "sold_unconfirmed"


def test_verlopen_archiveert_ook_als_de_verkoopvraag_uitstaat(monkeypatch):
    db = _zet(monkeypatch, _actief(), vraag_aan=False)
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "2dehands",
                                     "reden": "verlopen"}]}, user_id="u1")
    assert db.listings[0]["status"] == "delisted"


# ── 2. De serverronde die de openstaande vragen natrekt ─────────────────────

VERLOPEN_PAGINA = ('<div class="ExpiredListing-module-root" id="expired-listing-root">'
                   'Dit zoekertje is helaas verlopen</div>' + "x" * 6000)
LEVENDE_PAGINA = "<html><body>Perzisch tapijtje 127/68</body></html>" + "x" * 6000


class _Antwoord:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


class _Client:
    """Geeft per adres terug wat 2dehands teruggaf."""
    def __init__(self, per_url):
        self.per_url, self.gevraagd = per_url, []

    async def __aenter__(self): return self
    async def __aexit__(self, *_a): return False

    async def get(self, url, **_k):
        self.gevraagd.append(url)
        return self.per_url[url]


def _vraag(nummer, url, reden=None):
    return {"id": f"l-{nummer}", "item_id": "it1", "platform": "2dehands",
            "platform_listing_id": nummer, "platform_listing_url": url,
            "status": "sold_unconfirmed",
            "error_message": reden or api.VERDENKING_REDENEN["weg"]}


def _draai(monkeypatch, listings, per_url):
    import asyncio
    db = _DB([{"id": "it1", "user_id": "u1", "title": "t"}], listings)
    client = _Client(per_url)
    monkeypatch.setattr(vc, "get_db", lambda: db)
    monkeypatch.setattr(vc, "PAUZE_SECONDEN", 0)

    async def _direct(fn):
        return fn()
    monkeypatch.setattr(vc, "naast_de_lus", _direct)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: client)
    return db, asyncio.run(vc.controleer_verlopen_verkoopvragen()), client


def test_ronde_trekt_een_verlopen_vraag_in(monkeypatch):
    url = "https://www.2dehands.be/v/x/m222"
    db, uit, _ = _draai(monkeypatch, [_vraag("m222", url)],
                        {url: _Antwoord(410, VERLOPEN_PAGINA)})
    assert uit["verlopen"] == 1
    assert db.listings[0]["status"] == "delisted"
    assert "verlopen" in db.listings[0]["error_message"].lower()


def test_ronde_laat_een_levende_advertentie_met_rust(monkeypatch):
    url = "https://www.2dehands.be/v/x/m333"
    db, uit, _ = _draai(monkeypatch, [_vraag("m333", url)],
                        {url: _Antwoord(200, LEVENDE_PAGINA)})
    assert uit["verlopen"] == 0
    assert db.listings[0]["status"] == "sold_unconfirmed", "hier valt niets in te trekken"


def test_een_geblokkeerde_aanvraag_verandert_niets(monkeypatch):
    """403 is geen uitspraak. Gemeten: 2dehands kapt een snelle reeks zo af."""
    url = "https://www.2dehands.be/v/x/m444"
    db, uit, _ = _draai(monkeypatch, [_vraag("m444", url)],
                        {url: _Antwoord(403, "")})
    assert uit["verlopen"] == 0
    assert db.listings[0]["status"] == "sold_unconfirmed"


def test_een_hele_ronde_zonder_antwoord_stopt(monkeypatch):
    """Meet je niets, dan weet je niets: dan is de meting kapot, niet de voorraad."""
    urls = {f"https://www.2dehands.be/v/x/m{i}": _Antwoord(403, "") for i in range(10)}
    vragen = [_vraag(f"m{i}", u) for i, u in enumerate(urls)]
    db, uit, client = _draai(monkeypatch, vragen, urls)
    assert uit["verlopen"] == 0
    assert len(client.gevraagd) == 5, "na vijf keer niets stopt de ronde"
    assert all(r["status"] == "sold_unconfirmed" for r in db.listings)


def test_een_verkocht_label_wordt_niet_nagetrokken(monkeypatch):
    """Die vraag berust op bewijs op de pagina, niet op een verdwenen advertentie."""
    url = "https://www.2dehands.be/v/x/m555"
    db, uit, client = _draai(monkeypatch, [_vraag("m555", url, api.VERDENKING_REDENEN["label"])],
                             {url: _Antwoord(410, VERLOPEN_PAGINA)})
    assert client.gevraagd == [], "hier heeft deze ronde niets te zoeken"
    assert db.listings[0]["status"] == "sold_unconfirmed"


def test_zonder_adres_gebeurt_er_niets(monkeypatch):
    rij = _vraag("m666", "")
    db, uit, client = _draai(monkeypatch, [rij], {})
    assert client.gevraagd == []
    assert db.listings[0]["status"] == "sold_unconfirmed"
