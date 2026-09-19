"""De vraag "is dit verkocht?" moet uit kunnen.

19-09-2026, Egbert van papas-plectrums.nl. Hij kreeg een mail over een artikel
dat verkocht leek en kreeg de vraag op zijn dashboard. Zijn antwoord: "Voor mij
is dit totaal niet van toepassing omdat ik altijd nieuwe voorraad koop, zodra
dit niet meer het geval is verwijder ik het product van de platformen."

Hij heeft gelijk. De vraag bestaat omdat afmelden bij de andere kanalen
onherstelbaar is, en dat geldt voor wie tweedehands unica verkoopt. Wie nieuwe
voorraad verkoopt heeft er tien van en haalt zijn advertentie zelf weg als de
voorraad op is; voor hem is een verdwenen advertentie nooit een verkoopsignaal.

Staat de schakelaar uit, dan gaat een verdwenen advertentie meteen het archief
in: precies wat er gebeurt als hij zelf "nee" antwoordt. Er gaat niets van een
ander kanaal af, er komt geen vraag en geen mail.
"""
import re
import sys
from pathlib import Path

import pytest
from fastapi import BackgroundTasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import listings as api  # noqa: E402
from backend.services import instellingen  # noqa: E402
from backend.services import verkoop_herinnering as vh  # noqa: E402


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

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in vals for k, vals in self.in_filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings

    def table(self, naam):
        return _Q(self, naam)


def _zet(monkeypatch, vraag_aan: bool, listings):
    monkeypatch.setattr(instellingen, "lees",
                        lambda _uid: {**instellingen.STANDAARD,
                                      instellingen.VERKOOPVRAAG: vraag_aan})
    db = _DB([{"id": "it1", "user_id": "u1", "title": "(1308) Plectrum"}], listings)
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "fetch_all", lambda maker: maker().execute().data)
    return db


def _actief():
    return [{"id": "l1", "item_id": "it1", "platform": "marktplaats", "status": "active"}]


# ── 1. De instelling zelf ───────────────────────────────────────────────────

def test_de_vraag_staat_standaard_aan():
    """Niemand mag hem ongemerkt kwijtraken: zonder keuze blijft het zoals het was."""
    assert instellingen.STANDAARD[instellingen.VERKOOPVRAAG] is True
    assert instellingen._schoon({})[instellingen.VERKOOPVRAAG] is True


@pytest.mark.parametrize("waarde", [True, False])
def test_de_keuze_wordt_bewaard(waarde):
    assert instellingen._schoon(
        {instellingen.VERKOOPVRAAG: waarde})[instellingen.VERKOOPVRAAG] is waarde


def test_bij_een_storing_blijft_de_vraag_aan(monkeypatch):
    """Anders gooit één hik in de database een echte verkoop stilzwijgend weg."""
    def stuk(_uid):
        raise RuntimeError("supabase hikt")
    monkeypatch.setattr(instellingen, "lees", stuk)
    assert instellingen.verkoopvraag_aan("u1") is True


# ── 2. Een verdwenen advertentie ────────────────────────────────────────────

def test_met_de_vraag_aan_wordt_er_gevraagd(monkeypatch):
    db = _zet(monkeypatch, True, _actief())
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats",
                                     "reden": "weg"}]}, user_id="u1")
    assert db.listings[0]["status"] == "sold_unconfirmed"
    assert "Mogelijk verkocht" in db.listings[0]["error_message"]


def test_met_de_vraag_uit_gaat_hij_meteen_naar_het_archief(monkeypatch):
    db = _zet(monkeypatch, False, _actief())
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats",
                                     "reden": "weg"}]}, user_id="u1")
    assert db.listings[0]["status"] == "delisted", "hij wil geen vraag, dus ook geen vraag"
    assert db.listings[0]["error_message"] is None


def test_archiveren_haalt_niets_van_een_ander_kanaal_af(monkeypatch):
    """Dit is het gevaar van deze knop: uitzetten mag nooit gaan betekenen dat we
    zelf maar aannemen dat het verkocht is."""
    db = _zet(monkeypatch, False, _actief() + [
        {"id": "l2", "item_id": "it1", "platform": "vinted", "status": "active"}])
    api.possibly_sold({"listings": [{"item_id": "it1", "platform": "marktplaats",
                                     "reden": "weg"}]}, user_id="u1")
    vinted = [r for r in db.listings if r["platform"] == "vinted"][0]
    assert vinted["status"] == "active"


# ── 3. De verkocht-badge uit de berichtenlijst ──────────────────────────────

def test_met_de_vraag_uit_doet_de_verkocht_badge_niets(monkeypatch):
    """De advertentie staat er nog gewoon; er valt hier niets te archiveren."""
    db = _zet(monkeypatch, False, _actief())
    uit = api.sold_from_messages({"platform": "marktplaats",
                                  "sold": [{"sku": "1308", "title": "Plectrum"}]},
                                 BackgroundTasks(), user_id="u1")
    assert uit == {"asked": 0, "skipped": 1}
    assert db.listings[0]["status"] == "active"


def test_met_de_vraag_aan_vraagt_de_badge_nog_steeds(monkeypatch):
    db = _zet(monkeypatch, True, _actief())
    uit = api.sold_from_messages({"platform": "marktplaats",
                                  "sold": [{"sku": "1308", "title": "Plectrum"}]},
                                 BackgroundTasks(), user_id="u1")
    assert uit["asked"] == 1
    assert db.listings[0]["status"] == "sold_unconfirmed"


# ── 4. De herinneringsmail ──────────────────────────────────────────────────

def test_de_herinneringsmail_slaat_hem_over(monkeypatch):
    """Vangnet voor vragen die er al stonden voordat hij de knop omzette."""
    monkeypatch.setattr(instellingen, "lees",
                        lambda _uid: {**instellingen.STANDAARD,
                                      instellingen.VERKOOPVRAAG: False})
    bron = Path(vh.__file__).read_text(encoding="utf-8")
    assert "if not verkoopvraag_aan(uid):" in bron, (
        "de herinnering vraagt de instelling niet na")
    assert instellingen.verkoopvraag_aan("u1") is False


# ── 5. Geen enkele plek mag de vraag buiten de schakelaar om stellen ────────

def test_elke_plek_die_de_vraag_stelt_kijkt_naar_de_schakelaar():
    """Deze test is het echte vangnet. De vraag wordt op vijf plekken gesteld —
    de extensiemelding, de berichtenbadge, de teruggenomen herplaatsing, de
    Vinted-reconciliatie, de fotocontrole en de verkoop zonder bewijs — en een
    zevende plek erbij zonder deze
    schakelaar zou de knop stilletjes half kapot maken."""
    gemist = []
    for pad in sorted((ROOT / "backend").rglob("*.py")):
        tekst = pad.read_text(encoding="utf-8")
        if not re.search(r'"status":\s*"sold_unconfirmed"', tekst):
            continue
        if "verkoopvraag_aan" not in tekst:
            gemist.append(str(pad.relative_to(ROOT)))
    assert not gemist, f"deze bestanden zetten sold_unconfirmed zonder de schakelaar: {gemist}"


def test_het_scherm_heeft_de_knop_ook_echt():
    app = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
    assert 'id="verkoopvraag-aan"' in app
    assert "saveVerkoopvraag()" in app
    assert "verkoopvraag: schakel.checked" in app


def test_uitzetten_ruimt_de_vragen_op_die_er_al_stonden():
    """Anders blijven er zeven onbeantwoordbare vragen op het dashboard staan."""
    bron = (ROOT / "backend/api/items.py").read_text(encoding="utf-8")
    assert "_sluit_openstaande_verkoopvragen(user_id)" in bron
    assert '"status": "delisted"' in bron
