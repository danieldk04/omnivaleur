"""Een storing hoort een storing te blijven, niet een spoorloze 500.

WAT ER GEBEURDE (30-08-2026, Amanda)
Zij drukte op Publish en kreeg op haar scherm:

    Publishing failed (HTTP 500): Internal Server Error

Daar stopte het spoor. Een onverwachte fout in de server ging als kale tekst
terug naar de browser en verder alleen naar de logregels van de container — bij
de volgende deploy weg. Er was dus letterlijk geen enkele plek waar iemand kon
zien wélke fout het was, bij welk artikel, of hoe vaak het gebeurde. Haar foto
van de melding was het enige bewijs dat het ooit was gebeurd.

Twee dingen worden hier bewaakt:

  1. Eén struikelend kanaal mag de hele publicatie niet meeslepen. De
     extensiekant had die afscherming al; de API-kant (eBay, Shopify) niet.
  2. Gaat er tóch iets onverwachts stuk, dan krijgt de fout een korte code die
     de klant op zijn scherm ziet én die wordt vastgelegd, zodat de developer
     hem kan terugvinden met `mail_analyse.py fouten`.
"""
import asyncio
from pathlib import Path

import pytest

from backend.services import crosslist as C

ROOT = Path(__file__).resolve().parents[1]
CROSSLIST = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")


# ── 1. Eén kanaal dat struikelt, sleept de rest niet mee ─────────────────────

class _Query:
    """Genoeg van de Supabase-bouwer om _publish_one te laten lopen."""

    def __init__(self, uitkomst, stuk=False):
        self._uitkomst, self._stuk = uitkomst, stuk

    def __getattr__(self, _naam):
        def bouw(*_a, **_kw):
            if self._stuk:
                raise RuntimeError("Server disconnected without sending a response")
            return self
        return bouw

    def execute(self):
        return self._uitkomst


class _Antwoord:
    def __init__(self, data):
        self.data = data


def _db(uitkomst, stuk=False):
    class DB:
        def table(self, _naam):
            return _Query(uitkomst, stuk)
    return DB()


def test_een_lege_insert_wordt_een_nette_fout(monkeypatch):
    """`insert.data[0]` op een lege lijst was een IndexError — en dus een 500."""
    monkeypatch.setattr(C, "get_db", lambda: _db(_Antwoord([])))
    uit = asyncio.run(C._publish_one({"id": "x"}, "shopify", {}, "u"))
    assert uit["status"] == "error"
    assert "shopify" == uit["platform"]
    assert "try again" in uit["error"].lower()


def test_een_weggevallen_verbinding_wordt_een_nette_fout(monkeypatch):
    monkeypatch.setattr(C, "get_db", lambda: _db(_Antwoord([]), stuk=True))
    uit = asyncio.run(C._publish_one({"id": "x"}, "ebay", {}, "u"))
    assert uit["status"] == "error"
    assert uit["platform"] == "ebay"


def test_de_api_kanalen_lopen_apart_van_elkaar():
    """Met return_exceptions=False trok één mislukt kanaal de hele publicatie
    om — inclusief de kanalen die al netjes in de wachtrij stonden."""
    code = [r for r in CROSSLIST.splitlines() if not r.lstrip().startswith("#")]
    assert any("return_exceptions=True" in r for r in code)
    assert not any("return_exceptions=False" in r for r in code)


# ── 2. Een onverwachte fout laat altijd een spoor na ─────────────────────────

def test_de_klant_krijgt_een_code_te_zien():
    import backend.main as M

    class _Verzoek:
        method = "POST"

        class url:
            path = "/api/items/abc/crosslist"
        headers = {}

    bewaard = {}
    orig = M._bewaar_serverfout
    M._bewaar_serverfout = lambda code, methode, pad, exc: bewaard.update(
        code=code, pad=pad, soort=type(exc).__name__)
    try:
        antwoord = asyncio.run(M.onverwachte_fout(_Verzoek(), IndexError("list index out of range")))
    finally:
        M._bewaar_serverfout = orig

    inhoud = antwoord.body.decode()
    assert antwoord.status_code == 500
    assert bewaard["code"] in inhoud, "de code moet ook op het scherm van de klant staan"
    assert bewaard["pad"] == "/api/items/abc/crosslist"
    assert bewaard["soort"] == "IndexError"
    # Kale "Internal Server Error" zegt de klant niets en de developer nog minder.
    assert "Internal Server Error" not in inhoud


def test_de_fout_wordt_vastgelegd_met_spoor(monkeypatch):
    import backend.database as D
    import backend.main as M

    kast = {}

    class _Tabel:
        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            return _Antwoord(list(kast.get("server_fouten", ())) and
                             [{"inhoud": kast["server_fouten"]}] or [])

        def upsert(self, rij, **_kw):
            kast[rij["naam"]] = rij["inhoud"]
            return self

    monkeypatch.setattr(D, "get_db", lambda: type("DB", (), {"table": lambda _s, _n: _Tabel()})())

    try:
        raise ValueError("iets ging stuk")
    except ValueError as e:
        M._bewaar_serverfout("AB12CD", "POST", "/api/items/x/crosslist", e)

    fout = kast["server_fouten"][0]
    assert fout["code"] == "AB12CD"
    assert fout["soort"] == "ValueError"
    assert "iets ging stuk" in fout["bericht"]
    assert "test_publiceren_zonder_serverfout" in fout["spoor"], \
        "zonder het spoor is de code niet meer dan een nummer"


def test_er_worden_er_niet_eindeloos_bewaard(monkeypatch):
    import backend.database as D
    import backend.main as M

    kast = {"server_fouten": [{"code": f"OUD{i}"} for i in range(M.FOUTEN_BEWAREN + 20)]}

    class _Tabel:
        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            return _Antwoord([{"inhoud": kast["server_fouten"]}])

        def upsert(self, rij, **_kw):
            kast[rij["naam"]] = rij["inhoud"]
            return self

    monkeypatch.setattr(D, "get_db", lambda: type("DB", (), {"table": lambda _s, _n: _Tabel()})())
    M._bewaar_serverfout("NIEUW1", "GET", "/api/items", RuntimeError("x"))

    assert len(kast["server_fouten"]) == M.FOUTEN_BEWAREN
    assert kast["server_fouten"][0]["code"] == "NIEUW1", "de nieuwste hoort bovenaan"


def test_de_developer_kan_de_fouten_opvragen():
    """De opdrachtregel is de plek waar de developer zijn post leest."""
    tekst = (ROOT / "scripts/mail_analyse.py").read_text(encoding="utf-8")
    assert 'sub.add_parser("fouten"' in tekst
    assert '_lees("server_fouten"' in tekst


# ─────────────────────────────────────────────────────────────────────────────
# 04-09-2026 — het logboek wiste zichzelf
#
# Egbert klikte op "Clear all" en kreeg code F1F7E7 op zijn scherm. Tegen de
# tijd dat wij die opzochten was hij weg: een verversing die elke vijftien
# seconden faalde had in ruim een uur alle zestig plekken gevuld met exact
# dezelfde fout. Het logboek dat er is om te kunnen BEWIJZEN wat er stukging,
# duwde het bewijs er zelf uit.

def _logboek_opzet(monkeypatch, beginstand):
    import backend.database as D

    kast = {"server_fouten": beginstand}

    class _Tabel:
        def select(self, *_a): return self
        def eq(self, *_a): return self
        def execute(self): return _Antwoord([{"inhoud": kast["server_fouten"]}])

        def upsert(self, rij, **_kw):
            kast[rij["naam"]] = rij["inhoud"]
            return self

    monkeypatch.setattr(D, "get_db",
                        lambda: type("DB", (), {"table": lambda _s, _n: _Tabel()})())
    return kast


def _oude_bewaarder():
    """De echte oude versie uit git, niet een nagemaakte."""
    import re
    import subprocess
    import backend.main as M
    bron = subprocess.run(["git", "show", "4687587:backend/main.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    stuk = re.search(r"\ndef _bewaar_serverfout\(.*?(?=\n@app)", bron, re.S)
    assert stuk, "de oude bewaarder staat niet in die commit"
    ruimte = {"datetime": M.datetime, "timezone": M.timezone,
              "traceback": M.traceback, "FOUTEN_BEWAREN": M.FOUTEN_BEWAREN,
              "logger": M.logger}
    exec(compile(stuk.group(0), "<oud>", "exec"), ruimte)
    return ruimte["_bewaar_serverfout"]


def test_een_storing_die_zich_herhaalt_wist_de_rest_niet(monkeypatch):
    import backend.main as M

    egbert = {"code": "F1F7E7", "wanneer": "2026-09-04T11:00:00+00:00",
              "methode": "POST", "pad": "/api/listings/clear-error",
              "soort": "RemoteProtocolError", "bericht": "Server disconnected",
              "spoor": "", "aantal": 1, "codes": ["F1F7E7"]}
    kast = _logboek_opzet(monkeypatch, [egbert])

    # De verversing faalt honderd keer achter elkaar met exact dezelfde fout.
    for n in range(100):
        M._bewaar_serverfout(f"S{n:05d}", "GET", "/api/items/sync",
                             TypeError("select() got an unexpected keyword argument 'head'"))

    lijst = kast["server_fouten"]
    codes = [f.get("code") for f in lijst]
    assert "F1F7E7" in codes, "de melding van Egbert is er weer uit gedrukt"
    herhaling = [f for f in lijst if f["pad"] == "/api/items/sync"]
    assert len(herhaling) == 1, "dezelfde storing hoort één regel te zijn"
    assert herhaling[0]["aantal"] == 100
    assert herhaling[0]["codes"][0] == "S00099", "de laatste code moet terug te vinden zijn"
    assert len(herhaling[0]["codes"]) == 10

    # VOOR: dezelfde honderd meldingen op de oude bewaarder, en F1F7E7 is weg.
    kast2 = _logboek_opzet(monkeypatch, [dict(egbert)])
    oud = _oude_bewaarder()
    for n in range(100):
        oud(f"S{n:05d}", "GET", "/api/items/sync",
            TypeError("select() got an unexpected keyword argument 'head'"))
    assert "F1F7E7" not in [f.get("code") for f in kast2["server_fouten"]]
    assert len(kast2["server_fouten"]) == M.FOUTEN_BEWAREN


def test_de_developer_ziet_hoe_vaak_en_met_welke_codes():
    tekst = (ROOT / "scripts/mail_analyse.py").read_text(encoding="utf-8")
    assert "codes:" in tekst, "de codes van een herhaalde storing horen zichtbaar te zijn"
