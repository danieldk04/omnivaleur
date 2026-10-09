"""Twee stukken met dezelfde titel krijgen elk hun eigen Vinted-advertentie.

WAAROM DIT ER IS (09-10-2026, Janneke 31d28378). Ze heeft twee jassen die
allebei "Tussenjas Name it maat 128" heten, een rode en een bruine. De rode
stond op Vinted (10303777676). Toen de bruine werd geplaatst, keek de extensie
eerst of hij "al online stond": een advertentie in de kast met precies dezelfde
titel. Die vond ze, van de rode jas, en koppelde die in plaats van te plaatsen.
In het dashboard hingen daarna twee jassen aan één advertentie, en de bruine
stond niet op Vinted.

Drie lagen:
  1. de server geeft bij uitgifte de advertenties van titelgenoten mee
     (`_vinted_bezet`, en voor oudere extensies de nieuwste in
     `platform_listing_id`, die ze al oversloegen);
  2. de extensie (1.0.376) slaat alles in `_vinted_bezet` over;
  3. meldt een extensie tóch een advertentie die bij een ander artikel hoort,
     dan koppelt de server hem niet maar meldt een eerlijke fout.

De extensieproeven draaien de echte functie uit vinted.js in Node, de oude uit
commit 991ff841 (de versie die Janneke vandaag draait, 1.0.374, heeft dezelfde
functie) en de nieuwe uit de werkmap.
"""
import asyncio
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402

VOOR_DE_REPARATIE = "991ff841"
NODE = shutil.which("node")
TITEL = "Tussenjas Name it maat 128"
ROOD, BRUIN, ANDERE_KLANT = "rood", "bruin", "vreemd"


# ── een kleine nep-database ──────────────────────────────────────────────────
class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.actie, self.data = db, tabel, [], "select", None

    def select(self, *_a, **_k):
        return self

    def update(self, data):
        self.actie, self.data = "update", data
        return self

    def insert(self, data):
        self.actie, self.data = "insert", data
        return self

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v)
        return self

    def neq(self, k, v):
        self.filters.append(lambda r: r.get(k) != v)
        return self

    def in_(self, k, vs):
        vs = list(vs)
        self.filters.append(lambda r: r.get(k) in vs)
        return self

    def limit(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def execute(self):
        rijen = self.db.tabellen.setdefault(self.tabel, [])
        if self.actie == "insert":
            rijen.append(dict(self.data))
            return type("R", (), {"data": [self.data]})()
        hits = [r for r in rijen if all(f(r) for f in self.filters)]
        if self.actie == "update":
            for r in hits:
                r.update(self.data)
        return type("R", (), {"data": [dict(r) for r in hits]})()


class _DB:
    def __init__(self, **tabellen):
        self.tabellen = tabellen

    def table(self, naam):
        return _Q(self, naam)


def _janneke(extra_twins: int = 0):
    items = [{"id": ROOD, "user_id": "u1", "title": TITEL},
             {"id": BRUIN, "user_id": "u1", "title": TITEL},
             {"id": ANDERE_KLANT, "user_id": "u2", "title": TITEL}]
    listings = [{"item_id": ROOD, "platform": "vinted", "platform_listing_id": "10303777676",
                 "status": "active", "created_at": "2026-10-09T12:54:01"},
                {"item_id": ANDERE_KLANT, "platform": "vinted", "platform_listing_id": "555",
                 "status": "active", "created_at": "2026-10-09T13:00:00"}]
    for n in range(extra_twins):
        items.append({"id": f"tw{n}", "user_id": "u1", "title": TITEL})
        listings.append({"item_id": f"tw{n}", "platform": "vinted",
                         "platform_listing_id": f"77{n}", "status": "active",
                         "created_at": f"2026-10-0{n + 1}T10:00:00"})
    return _DB(items=items, listings=listings)


def _bruine_opdracht():
    return {"id": "j1", "user_id": "u1", "item_id": BRUIN, "platform": "vinted",
            "action": "create", "status": "claimed",
            "payload": {"title": TITEL, "price": 29.5}}


# ── laag 1: de server geeft de titelgenoten mee ─────────────────────────────
def test_uitgifte_geeft_de_advertentie_van_de_rode_jas_mee():
    job = _bruine_opdracht()
    assert J._vinted_titelgenoten_meegeven(_janneke(), "u1", [job]) == 1
    assert job["payload"]["_vinted_bezet"] == ["10303777676"]
    # Voor de extensie die ze vandaag draait: die sloeg dit veld al over.
    assert job["payload"]["platform_listing_id"] == "10303777676"


def test_advertentie_van_een_andere_klant_telt_niet_mee():
    job = _bruine_opdracht()
    J._vinted_titelgenoten_meegeven(_janneke(), "u1", [job])
    assert "555" not in job["payload"]["_vinted_bezet"]


def test_herplaatsing_houdt_haar_eigen_oude_nummer():
    job = _bruine_opdracht()
    job["payload"]["platform_listing_id"] = "oud-nummer-van-de-bruine"
    J._vinted_titelgenoten_meegeven(_janneke(), "u1", [job])
    assert job["payload"]["platform_listing_id"] == "oud-nummer-van-de-bruine"
    assert job["payload"]["_vinted_bezet"] == ["10303777676"]


def test_zonder_titelgenoot_verandert_er_niets():
    db = _DB(items=[{"id": BRUIN, "user_id": "u1", "title": TITEL}], listings=[])
    job = _bruine_opdracht()
    assert J._vinted_titelgenoten_meegeven(db, "u1", [job]) == 0
    assert job["payload"] == {"title": TITEL, "price": 29.5}


def test_nieuwste_titelgenoot_eerst():
    job = _bruine_opdracht()
    J._vinted_titelgenoten_meegeven(_janneke(extra_twins=2), "u1", [job])
    assert job["payload"]["_vinted_bezet"][0] == "10303777676"
    assert set(job["payload"]["_vinted_bezet"]) == {"10303777676", "770", "771"}


# ── laag 2: de extensie, de echte functie in Node ───────────────────────────
def _functie(bron: str, naam: str) -> str:
    start = bron.index(f"  async function {naam}(")
    eind = bron.index("\n  }\n", start) + 4
    return bron[start:eind]


def _vinted_js(commit: str | None) -> str:
    if commit is None:
        return (ROOT / "extension/content/vinted.js").read_text()
    return subprocess.run(["git", "show", f"{commit}:extension/content/vinted.js"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def _al_online(commit: str | None, payload: dict, kast: list) -> str | None:
    """De controle vooraf, letterlijk zoals content/vinted.js hem aanroept."""
    if NODE is None:
        pytest.skip("node is niet geïnstalleerd")
    driver = f"""
const sleep = async () => {{}};
const getVintedUserId = async () => "1";
const fetch = async () => ({{ ok: true, json: async () => ({{ items: {json.dumps(kast)} }}) }});
{_functie(_vinted_js(commit), "resolveCreatedVintedItem")}
const item = {json.dumps(payload)};
resolveCreatedVintedItem(item, item.platform_listing_id, 2500, {{ exact: true }})
  .then((r) => console.log(JSON.stringify(r)));
"""
    r = subprocess.run([NODE, "-e", driver], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    uit = json.loads(r.stdout.strip())
    return uit["id"] if uit else None


KAST = [{"id": 10303777676, "title": TITEL, "is_closed": False, "is_draft": False}]


def test_oude_server_oude_extensie_koppelt_de_rode_jas():
    """Zo ging het vanmiddag: de bruine jas kreeg 10303777676."""
    assert _al_online(VOOR_DE_REPARATIE, {"title": TITEL}, KAST) == "10303777676"


def test_nieuwe_server_repareert_het_ook_met_haar_huidige_extensie():
    job = _bruine_opdracht()
    J._vinted_titelgenoten_meegeven(_janneke(), "u1", [job])
    assert _al_online(VOOR_DE_REPARATIE, job["payload"], KAST) is None


def test_nieuwe_extensie_slaat_alle_titelgenoten_over():
    job = _bruine_opdracht()
    J._vinted_titelgenoten_meegeven(_janneke(extra_twins=2), "u1", [job])
    kast = KAST + [{"id": 770, "title": TITEL, "is_closed": False, "is_draft": False},
                   {"id": 771, "title": TITEL, "is_closed": False, "is_draft": False}]
    # De oude extensie slaat er maar één over en pakt de volgende: daarvoor is laag 3.
    assert _al_online(VOOR_DE_REPARATIE, job["payload"], kast) in {"770", "771"}
    assert _al_online(None, job["payload"], kast) is None


def test_nieuwe_extensie_koppelt_nog_steeds_een_echt_zelf_geplaatste():
    """Waar de controle voor is: hing de plaatsing en zette ze hem zelf online,
    dan koppelen en niet nog een keer plaatsen."""
    job = _bruine_opdracht()
    J._vinted_titelgenoten_meegeven(_janneke(), "u1", [job])
    kast = [{"id": 10399999999, "title": TITEL, "is_closed": False, "is_draft": False}] + KAST
    assert _al_online(None, job["payload"], kast) == "10399999999"


def test_achtergrond_zoekt_ook_niet_bij_een_titelgenoot():
    bron = (ROOT / "extension/background.js").read_text()
    blok = bron[bron.index("async function bgVindVintedAdvertentie"):]
    blok = blok[:blok.index("\n}\n")]
    assert re.search(r"!bezet\.has\(String\(it\.id\)\)", blok)


# ── laag 3: de server koppelt nooit andermans advertentie ───────────────────
def test_afmelden_met_de_advertentie_van_de_rode_jas_wordt_geweigerd(monkeypatch):
    db = _janneke()
    db.tabellen["jobs"] = [_bruine_opdracht()]
    gemeld = {}
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(J, "fail_job", lambda job_id, body, user_id: gemeld.update(body))
    uit = asyncio.run(J.complete_job("j1", {"platform_listing_id": "10303777676",
                                            "note": "already_published_manually"}, user_id="u1"))
    assert uit["status"] == "advert_belongs_to_other_item"
    assert TITEL in gemeld["error"]
    # Geen tweede rij op dezelfde advertentie.
    assert [l["item_id"] for l in db.tabellen["listings"]
            if l["platform_listing_id"] == "10303777676"] == [ROOD]


def test_advertentie_van_een_andere_klant_houdt_niets_tegen():
    job = _bruine_opdracht()
    assert J._advertentie_van_ander_artikel(_janneke(), job, {"platform_listing_id": "555"}) is None


def test_eigen_advertentie_van_hetzelfde_artikel_houdt_niets_tegen():
    job = _bruine_opdracht()
    job["item_id"] = ROOD
    assert J._advertentie_van_ander_artikel(_janneke(), job,
                                            {"platform_listing_id": "10303777676"}) is None
