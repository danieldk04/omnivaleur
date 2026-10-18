"""Een eigen vaste tekst op Vinted.

Lynn van De Juiste Toon, 18-10-2026: "om van omnivaleur door te plaatsen naar
vinted is een stuk van onze standaard toegevoegde tekst niet toegestaan (we
verwijzen naar de site en hebben ons nummer). Deze tekst willen we nog wel bij .be
en marktplaats erbij, maar een andere tekst (of geen extra tekst) bij vinted."

Gemeten op hun account: de vaste slottekst (instelling "slottekst") noemt de
webshop, het adres en +31 6 5396 0664, en hun laatste Vinted-plaatsing van 17-10
droeg hem letterlijk. Er was één tekst voor alle kanalen behalve eBay.

Deze proef draait de echte publicatieroute, de echte herplaatsing en de echte
laatste zeef vlak voor de uitgifte, met hun echte slottekst, en leest de
instellingen via instellingen.lees: zo faalt hij ook op de code van vóór deze
reparatie, die de nieuwe keuze niet kende.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402
from backend.services import crosslist as cl  # noqa: E402
from backend.services import instellingen as I  # noqa: E402
from backend.services import relist as R  # noqa: E402

TOON = ("#DeJuisteToon\n\nKijk op onze webshop Dejuistetoon voor het volledige en actuele aanbod.\n\n"
        "Wil je onze collectie in het echt bekijken , maak een afspraak.\n\n"
        "Alle dagen op afspraak | Do & Za 10.00 uur tot 17.00 uur\n\n"
        "Locatie: Mon Plaisir 19, Etten-Leur.\ntelefoon: +31 6 5396 0664.")
VINTED_EIGEN = "#DeJuisteToon\n\nVragen? Stuur ons gerust een bericht via Vinted."
KANGA = ("Traditionele oost Afrikaanse kanga.\n\nAfmetingen: 135/105cm\n\nGS4")
NUMMER = "5396 0664"


def _instellingen(monkeypatch, **rauw):
    monkeypatch.setattr(I, "lees", lambda _u: I._schoon({"slottekst": TOON, **rauw}))


# ── De echte publicatieroute ─────────────────────────────────────────────────
class _Antwoord:
    def __init__(self, data): self.data = data


class _Klaar:
    def __init__(self, antwoord): self.antwoord = antwoord
    def eq(self, *a, **k): return self
    def execute(self): return self.antwoord


class _Vraag:
    def __init__(self, db, tabel): self.db, self.tabel = db, tabel
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def neq(self, *a, **k): return self
    def in_(self, *a, **k): return self
    def is_(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def lt(self, *a, **k): return self

    @property
    def not_(self): return self

    def insert(self, rij, *a, **k):
        for r in (rij if isinstance(rij, list) else [rij]):
            self.db.geschreven.setdefault(self.tabel, []).append(r)
        return _Klaar(_Antwoord(rij if isinstance(rij, list) else [rij]))

    def upsert(self, rij, *a, **k): return self.insert(rij)
    def update(self, patch, *a, **k): return _Klaar(_Antwoord([patch]))
    def delete(self, *a, **k): return _Klaar(_Antwoord([]))
    def execute(self): return _Antwoord(self.db.rijen.get(self.tabel, []))


class _NepDb:
    def __init__(self, rijen): self.rijen, self.geschreven = rijen, {}
    def table(self, naam): return _Vraag(self, naam)


def _publiceer(monkeypatch, beschrijving, kanalen):
    artikel = {"id": "i1", "user_id": "96e30080", "title": "Kanga blauw geel",
               "description": beschrijving, "photo_urls": ["https://x/1.jpg"],
               "category": "wonen vachten", "price": 25, "condition": "good"}
    db = _NepDb({"items": [artikel], "listings": [], "jobs": []})
    monkeypatch.setattr(cl, "get_db", lambda: db)
    import backend.database as bd
    import backend.services.photo_mirror as pm
    monkeypatch.setattr(bd, "get_db", lambda: db)
    monkeypatch.setattr(cl, "publicatie_geblokkeerd", lambda *a, **k: None)
    monkeypatch.setattr(pm, "is_mirrored", lambda _u: True)

    async def _exec(vraag, *a, **k):
        return vraag.execute()

    async def _lok(item, platform):
        return dict(item)
    monkeypatch.setattr(cl, "_exec", _exec)
    monkeypatch.setattr(cl, "localize_item_for_platform", _lok)
    monkeypatch.setattr(I, "fabrikant", lambda uid: {})
    monkeypatch.setattr(I, "fabrikant_verplicht", lambda uid: False)
    monkeypatch.setattr(I, "verzendkeuzes", lambda uid, prijs=None: {})
    monkeypatch.setattr(I, "locatie", lambda uid: {})
    asyncio.run(cl.publish_to_platforms("i1", kanalen, "96e30080"))
    return {j["platform"]: j["payload"]["description"]
            for j in db.geschreven.get("jobs", []) if j.get("action") == "create"}


@pytest.mark.parametrize("keuze", ["geen", "eigen"])
def test_publiceren_vinted_krijgt_niet_de_webshoptekst(monkeypatch, keuze):
    _instellingen(monkeypatch, vinted_slot=keuze, slottekst_vinted=VINTED_EIGEN)
    uit = _publiceer(monkeypatch, KANGA, ["marktplaats", "2dehands", "vinted"])
    assert set(uit) == {"marktplaats", "2dehands", "vinted"}, uit
    assert NUMMER not in uit["vinted"] and "webshop" not in uit["vinted"], uit["vinted"]
    assert uit["vinted"].startswith(KANGA)
    if keuze == "eigen":
        assert uit["vinted"].endswith(VINTED_EIGEN)
    else:
        assert uit["vinted"] == KANGA
    for kanaal in ("marktplaats", "2dehands"):
        assert uit[kanaal].endswith(TOON), (kanaal, uit[kanaal])
        assert NUMMER in uit[kanaal]


def test_publiceren_zonder_keuze_blijft_precies_zoals_het_was(monkeypatch):
    _instellingen(monkeypatch)
    uit = _publiceer(monkeypatch, KANGA, ["marktplaats", "vinted"])
    assert uit["vinted"] == KANGA + "\n\n" + TOON
    assert uit["marktplaats"] == KANGA + "\n\n" + TOON


def test_ingelezen_tekst_met_de_slottekst_erin_gaat_op_vinted_eraf(monkeypatch):
    """Een artikel dat van Marktplaats werd ingelezen draagt de tekst al."""
    _instellingen(monkeypatch, vinted_slot="eigen", slottekst_vinted=VINTED_EIGEN)
    uit = _publiceer(monkeypatch, KANGA + "\n\n" + TOON, ["marktplaats", "vinted"])
    assert NUMMER not in uit["vinted"], uit["vinted"]
    assert uit["vinted"] == KANGA + "\n\n" + VINTED_EIGEN
    assert uit["marktplaats"].count(NUMMER) == 1


def test_ingelezen_met_opmaak_en_witruimte_gaat_er_ook_af():
    html = ("<p>Traditionele kanga.</p><p>#DeJuisteToon</p><p>Kijk op onze webshop Dejuistetoon voor "
            "het volledige en actuele aanbod.</p><p>Wil je onze collectie in het echt bekijken , maak "
            "een afspraak.</p><p>Alle dagen op afspraak | Do &amp; Za 10.00 uur tot 17.00 uur</p>"
            "<p>Locatie: Mon Plaisir 19, Etten-Leur.<br>telefoon: +31 6 5396 0664.</p>")
    uit = cl.omschrijving_met_slot(html, "vinted", TOON, "")
    assert NUMMER not in uit and "Mon Plaisir" not in uit and "webshop" not in uit, uit
    assert "Traditionele kanga." in uit


def test_eigen_vinted_tekst_komt_nooit_op_marktplaats():
    """Andersom: een Vinted-advertentie die werd ingelezen, gaat naar Marktplaats."""
    uit = cl.omschrijving_met_slot(KANGA + "\n\n" + VINTED_EIGEN, "marktplaats", TOON, VINTED_EIGEN)
    assert "via Vinted" not in uit
    assert uit.endswith(TOON)


# ── De herplaatsing (zelfde regels als publiceren) ──────────────────────────
def test_herplaatsen_op_vinted_volgt_de_keuze(monkeypatch):
    _instellingen(monkeypatch, vinted_slot="geen")
    uit = R._met_slottekst({"title": "Kanga", "description": KANGA}, "vinted", "96e30080")
    assert uit["description"] == KANGA
    mp = R._met_slottekst({"title": "Kanga", "description": KANGA}, "marktplaats", "96e30080")
    assert NUMMER in mp["description"]


# ── De laatste zeef vlak voor de uitgifte ───────────────────────────────────
class _ZeefDb:
    def __init__(self): self.updates = []

    def table(self, _naam):
        db = self

        class Q:
            def update(self, velden): self.velden = velden; return self
            def eq(self, _k, v): db.updates.append(v); return self
            def execute(self): return _Antwoord([])
        return Q()


def test_opdracht_die_al_klaarstond_krijgt_bij_uitgifte_de_vinted_tekst(monkeypatch):
    """Toon had al Vinted-plaatsingen klaarstaan met de oude tekst eronder."""
    _instellingen(monkeypatch, vinted_slot="eigen", slottekst_vinted=VINTED_EIGEN)
    oud = KANGA + "\n\n" + TOON
    jobs = [{"id": "v", "platform": "vinted", "action": "create", "user_id": "96e30080",
             "payload": {"description": oud}},
            {"id": "m", "platform": "marktplaats", "action": "create", "user_id": "96e30080",
             "payload": {"description": oud}}]
    db = _ZeefDb()
    J._vinted_tekst_binnen_grens(db, jobs)
    assert jobs[0]["payload"]["description"] == KANGA + "\n\n" + VINTED_EIGEN
    assert jobs[1]["payload"]["description"] == oud
    assert db.updates == ["v"]


def test_zeef_zonder_keuze_raakt_niets_aan(monkeypatch):
    _instellingen(monkeypatch)
    jobs = [{"id": "v", "platform": "vinted", "action": "create", "user_id": "96e30080",
             "payload": {"description": KANGA}}]
    db = _ZeefDb()
    J._vinted_tekst_binnen_grens(db, jobs)
    assert jobs[0]["payload"]["description"] == KANGA
    assert db.updates == []


# ── De instelling ───────────────────────────────────────────────────────────
def test_instelling_standaard_en_opgeschoond():
    assert I._schoon({})["vinted_slot"] == "zelfde"
    assert I._schoon({"vinted_slot": "onzin"})["vinted_slot"] == "zelfde"
    assert I._schoon({"vinted_slot": "geen"})["vinted_slot"] == "geen"
    assert I._schoon({"slottekst_vinted": "  x  "})["slottekst_vinted"] == "x"
    assert len(I._schoon({"slottekst_vinted": "x" * 9000})["slottekst_vinted"]) == I.SLOTTEKST_MAX
    assert I.vinted_slot_uit(I._schoon({"slottekst": "a", "vinted_slot": "eigen",
                                        "slottekst_vinted": "b"})) == "b"
    assert I.vinted_slot_uit(I._schoon({"slottekst": "a"})) == "a"
    assert I.vinted_slot_uit(I._schoon({"slottekst": "a", "vinted_slot": "geen"})) == ""


def test_het_scherm_stuurt_de_keuze_mee():
    app = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
    assert 'id="slottekst-vinted-keuze"' in app and 'id="slottekst-vinted"' in app
    assert "vinted_slot: document.getElementById('slottekst-vinted-keuze').value" in app
    assert "slottekst_vinted: document.getElementById('slottekst-vinted').value" in app
