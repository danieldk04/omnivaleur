"""Marktplaats en 2dehands krijgen hun advertentie in het Nederlands. Altijd.

AANLEIDING (04-09-2026, Daniel). Op marktplaats.nl stond zijn advertentie (1357)
"Lilac Profuomo Shirt - Men 45 - New With Tags" — de Engelse titel uit het
dashboard, woord voor woord, terwijl Omnivaleur juist belooft die te vertalen
("You enter listings in English — Omnivaleur automatically translates titles and
descriptions to Dutch before publishing on Marktplaats and 2dehands").

WAT ER MISGING. Het vertalen zat op elke plek waar een 'create'-opdracht wordt
klaargezet apart ingebouwd:

  * publish_to_platforms          → vertaalde (_build_dutch / _pick)
  * refresh_listing, beide takken → vertaalde (localize_item_for_platform)
  * herstel_vastgelopen_werk      → NIET

Die laatste is de reddingsronde: elke zes uur zoekt hij advertenties die tussen
weghalen en terugplaatsen zijn blijven hangen, en zet er alsnog een plaatsing
voor klaar. Die plaatsing werd gebouwd uit de kale databaserij, en dat is de
Engelse tekst. Er ging technisch niets mis, dus er kwam ook geen foutmelding —
de advertentie stond gewoon in het Engels online, zonder de vaste slottekst van
de verkoper.

WAT ER NU GEBEURT. De reddingsronde gaat langs dezelfde localisatie als de rest.
En omdat "elk pad moet er zelf aan denken" precies de vorm van deze fout is,
draagt elke gelocaliseerde payload voortaan een taalstempel (crosslist.TAAL_VELD)
en zeeft de uitgifte van werk aan de extensie op dat stempel: wat er zonder
langskomt, wordt daar alsnog vertaald (_zet_taal_goed in backend/api/jobs.py).
Dat repareert meteen de opdrachten die nu al in de wachtrij staan.

Draaien: python3 -m pytest tests/test_marktplaats_vertaling.py
"""
import asyncio
import importlib.util
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as database  # noqa: E402
from backend.api import jobs as api  # noqa: E402
from backend.services import crosslist  # noqa: E402
from backend.services import relist  # noqa: E402

# NIET HEAD. De auto-push-hook commit werk in uitvoering onder "auto: update
# ...", dus HEAD bevat de reparatie al voordat deze proef draait — en dan meet de
# voor-en-na-proef twee keer hetzelfde.
VOOR_DE_REPARATIE = "4687587"

# De echte titel van Daniels advertentie, zoals hij in het dashboard staat.
ENGELSE_TITEL = "(1357) Lilac Profuomo Shirt - Men 45 - New With Tags"
NEDERLANDSE_TITEL = "(1357) Lila Profuomo Overhemd - Heren 45 - Nieuw met kaartje"
ENGELSE_TEKST = "Beautiful lilac shirt, never worn, tags still on."
NEDERLANDSE_TEKST = "Prachtig lila overhemd, nooit gedragen, kaartjes zitten er nog aan."
SLOTTEKST = "Kijkt u ook eens bij onze andere advertenties."


# ── Een database die genoeg lijkt op de echte ────────────────────────────────
# Zelfde opzet als in tests/test_reddingsronde_geen_dubbele.py.
class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.ins = {}, {}
        self.lt_ = self.gte_ = None
        self.op, self.velden, self.is_single = None, None, False
        self.desc = False

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def insert(self, velden): self.op, self.velden = "insert", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def lt(self, k, v): self.lt_ = (k, v); return self
    def gte(self, k, v): self.gte_ = (k, v); return self
    def order(self, *_a, desc=False, **_k): self.desc = desc; return self
    def limit(self, _n): return self
    def single(self): self.is_single = True; return self

    def execute(self):
        bron = self.db.tabellen.setdefault(self.tabel, [])
        if self.op == "insert":
            rij = dict(self.velden, id=f"nieuw-{len(bron)}")
            bron.append(rij)
            self.db.ingevoegd.append(rij)
            return type("R", (), {"data": [rij]})()
        rijen = [r for r in bron if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.ins.items())]
        for grens, oper in ((self.lt_, lambda a, b: a < b), (self.gte_, lambda a, b: a >= b)):
            if grens:
                k, v = grens
                rijen = [r for r in rijen if oper(str(r.get(k) or ""), str(v))]
        rijen.sort(key=lambda r: str(r.get("created_at") or ""), reverse=self.desc)
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen[0] if self.is_single else rijen})()


class _DB:
    def __init__(self, listings, jobs, items):
        self.tabellen = {"listings": listings, "jobs": jobs, "items": items}
        self.ingevoegd = []

    def table(self, naam):
        return _Q(self, naam)


NU = datetime.now(timezone.utc)

ITEM = {
    "id": "item-1", "user_id": "daniel",
    "title": ENGELSE_TITEL, "description": ENGELSE_TEKST,
    "brand": "Profuomo", "condition": "new_with_tags",
    "photo_urls": ["a"], "price": 39.99,
}


def _nep_vertaling(item, platform):
    """Wat localize_item_for_platform doet, zonder het model erbij te halen."""
    if platform not in ("marktplaats", "2dehands"):
        return item
    return {**item, "title": NEDERLANDSE_TITEL, "description": NEDERLANDSE_TEKST,
            crosslist.TAAL_VELD: "nl"}


def _job(jid, actie, status, oud_uren=1, sched=False):
    return {"id": jid, "user_id": "daniel", "item_id": "item-1", "platform": "marktplaats",
            "action": actie, "status": status,
            "created_at": (NU - timedelta(hours=oud_uren)).isoformat(),
            "scheduled_for": (NU + timedelta(hours=2)).isoformat() if sched else None,
            "payload": {"title": ENGELSE_TITEL}, "result": None}


@pytest.fixture
def opzet(monkeypatch):
    """Een advertentie die tussen weghalen en terugplaatsen is blijven hangen."""
    def maak(module=relist):
        db = _DB([{"id": "rij-1", "item_id": "item-1", "platform": "marktplaats",
                   "status": "relisting", "platform_listing_id": "m1",
                   "listed_at": "2026-08-01T00:00:00+00:00",
                   "last_refreshed_at": NU.isoformat(), "refresh_count": 1,
                   "error_message": None}],
                 [_job("d1", "delete", "done"), _job("c1", "create", "error", sched=True)],
                 [dict(ITEM)])
        monkeypatch.setattr(module, "get_db", lambda: db)
        monkeypatch.setattr(database, "get_db", lambda: db)
        monkeypatch.setattr(module, "_met_fabrikant", lambda item, platform, uid: dict(item))
        monkeypatch.setattr(crosslist, "localize_item_for_platform",
                            lambda item, platform: _klaar(_nep_vertaling(item, platform)))
        monkeypatch.setattr(crosslist, "slottekst_van", lambda uid: SLOTTEKST)
        return db
    return maak


def _klaar(waarde):
    """Een al-af resultaat dat toch ge-await mag worden."""
    lus = asyncio.get_event_loop_policy().get_event_loop()
    fut = lus.create_future()
    fut.set_result(waarde)
    return fut


def _plaatsing(db):
    return next(j for j in db.ingevoegd if j.get("action") == "create")


# ── 1. De reddingsronde ──────────────────────────────────────────────────────

def test_de_reddingsronde_plaatst_in_het_nederlands(opzet):
    db = opzet()
    asyncio.run(relist.herstel_vastgelopen_werk())
    payload = _plaatsing(db)["payload"]
    assert payload["title"] == NEDERLANDSE_TITEL, (
        "de reddingsronde zet de Engelse dashboardtitel op Marktplaats")
    assert payload["description"].startswith(NEDERLANDSE_TEKST)


def test_de_reddingsronde_zet_de_vaste_slottekst_er_weer_onder(opzet):
    """Die zat óók alleen in publish_to_platforms ingebouwd."""
    db = opzet()
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert _plaatsing(db)["payload"]["description"].endswith(SLOTTEKST)


def test_de_reddingsronde_stempelt_de_taal(opzet):
    """Zonder stempel vertaalt de uitgifte hem straks nóg een keer."""
    db = opzet()
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert _plaatsing(db)["payload"][crosslist.TAAL_VELD] == "nl"


def _oude_relist(tmp_path):
    """De reddingsronde zoals hij was vóór de reparatie, als draaiende module."""
    bron = subprocess.run(
        ["git", "show", f"{VOOR_DE_REPARATIE}:backend/services/relist.py"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    pad = tmp_path / "relist_voor_de_reparatie.py"
    pad.write_text(bron, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("relist_voor_de_reparatie", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_de_oude_reddingsronde_plaatste_aantoonbaar_in_het_engels(opzet, tmp_path):
    """Zonder deze proef weet je alleen dat het nu werkt, niet dat er iets stuk was."""
    oud = _oude_relist(tmp_path)
    db = opzet(module=oud)
    asyncio.run(oud.herstel_vastgelopen_werk())
    assert _plaatsing(db)["payload"]["title"] == ENGELSE_TITEL
    assert SLOTTEKST not in _plaatsing(db)["payload"]["description"]


# ── 2. Het vangnet bij de uitgifte ───────────────────────────────────────────

def _zeef(monkeypatch, jobs):
    db = _DB([], list(jobs), [])
    db.tabellen["jobs"] = list(jobs)
    gebeld = []

    def nep(payload, platform):
        gebeld.append(platform)
        return _nep_vertaling(payload, platform)

    monkeypatch.setattr(crosslist, "localiseer_sync", nep)
    api._zet_taal_goed(db, jobs)
    return gebeld


def test_een_onvertaalde_opdracht_wordt_alsnog_vertaald(monkeypatch):
    job = _job("c9", "create", "pending")
    job["payload"] = {"title": ENGELSE_TITEL, "description": ENGELSE_TEKST}
    gebeld = _zeef(monkeypatch, [job])
    assert gebeld == ["marktplaats"]
    assert job["payload"]["title"] == NEDERLANDSE_TITEL


def test_dat_wordt_ook_teruggeschreven_in_de_opdracht(monkeypatch):
    """Anders vertaalt élke poll dezelfde opdracht opnieuw."""
    job = _job("c9", "create", "pending")
    job["payload"] = {"title": ENGELSE_TITEL, "description": ENGELSE_TEKST}
    db = _DB([], [dict(job)], [])
    monkeypatch.setattr(crosslist, "localiseer_sync", _nep_vertaling)
    api._zet_taal_goed(db, [job])
    assert db.tabellen["jobs"][0]["payload"]["title"] == NEDERLANDSE_TITEL


def test_een_al_gestempelde_opdracht_blijft_met_rust(monkeypatch):
    job = _job("c9", "create", "pending")
    job["payload"] = {"title": NEDERLANDSE_TITEL, "description": NEDERLANDSE_TEKST,
                      crosslist.TAAL_VELD: "nl"}
    assert _zeef(monkeypatch, [job]) == []


def test_vinted_en_shopify_gaan_hier_niet_doorheen(monkeypatch):
    """Daar gaat de tekst uit zoals de verkoper hem zelf schreef."""
    jobs = []
    for platform in ("vinted", "shopify", "ebay"):
        job = _job("c9", "create", "pending")
        job["platform"] = platform
        job["payload"] = {"title": ENGELSE_TITEL}
        jobs.append(job)
    assert _zeef(monkeypatch, jobs) == []


def test_verwijderen_en_scannen_gaan_hier_niet_doorheen(monkeypatch):
    jobs = [_job("d9", "delete", "pending"), _job("s9", "scan", "pending")]
    assert _zeef(monkeypatch, jobs) == []


def test_een_kapotte_vertaling_houdt_het_uitdelen_niet_tegen(monkeypatch):
    """Liever de oude tekst dan een verkoper die niets kan publiceren."""
    def stuk(payload, platform):
        raise RuntimeError("het model is even weg")
    monkeypatch.setattr(crosslist, "localiseer_sync", stuk)
    job = _job("c9", "create", "pending")
    db = _DB([], [dict(job)], [])
    api._zet_taal_goed(db, [job])          # mag niet gooien
    assert job["payload"]["title"] == ENGELSE_TITEL


# ── 3. Het stempel wordt overal gezet ────────────────────────────────────────

def test_elke_localisatie_stempelt_de_taal(monkeypatch):
    monkeypatch.setattr(crosslist, "_vertaal",
                        lambda tekst, taal, merk=None: f"[{taal}] {tekst}")
    nl = crosslist.localiseer_sync(dict(ITEM), "marktplaats")
    assert nl[crosslist.TAAL_VELD] == "nl"
    assert nl["title"] == f"[nl] {ENGELSE_TITEL}"

    en = crosslist.localiseer_sync(dict(ITEM), "vinted")
    assert en[crosslist.TAAL_VELD] == "en"

    onbekend = crosslist.localiseer_sync(dict(ITEM), "facebook")
    assert crosslist.TAAL_VELD not in onbekend


def test_de_async_en_de_synchrone_kant_doen_hetzelfde(monkeypatch):
    """Twee ingangen naar dezelfde vertaling; ze mogen niet uit elkaar lopen."""
    monkeypatch.setattr(crosslist, "_vertaal",
                        lambda tekst, taal, merk=None: f"[{taal}] {tekst}")
    for platform in ("marktplaats", "2dehands", "vinted", "ebay", "facebook"):
        synchroon = crosslist.localiseer_sync(dict(ITEM), platform)
        via_lus = asyncio.run(crosslist.localize_item_for_platform(dict(ITEM), platform))
        assert synchroon == via_lus, platform


def test_publiceren_stempelt_zijn_payload_ook():
    """_pick() bouwt zijn eigen vertaling en moet hetzelfde stempel zetten."""
    bron = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    tak = bron.split("async def _build_english():")[1].split("translations = await")[0]
    assert tak.count(f"{crosslist.TAAL_VELD}") == 0, "gebruik de constante, niet de tekst"
    assert tak.count("TAAL_VELD: \"en\"") == 1
    assert tak.count("TAAL_VELD: \"nl\"") == 1
