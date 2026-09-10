"""Het vangnet tegen dubbelverkoop mag niet eeuwig blijven proberen (10-09-2026).

WAAROM DEZE TEST BESTAAT — GEMETEN, NIET BEDACHT.

De Juiste Toon: artikel "Lederhosen maat 54" was op Vinted verkocht. De
Marktplaats-advertentie is voor de extensie niet te vinden (zakelijk account,
"Mijn advertenties" is leeg), dus kwam de verwijderopdracht op 'error' en bleef
de advertentierij op 'active'. `reconcileer_verkochte_artikelen` leest dat als
"nog niet afgemeld" en zette de afmelding elke twintig minuten opnieuw in gang:
van 09-09 19:52 tot 10-09 17:26, elke keer twee opdrachten, elke keer dezelfde
fout. Systeembreed: 462 van de 1.790 verwijderopdrachten sinds 25-08 waren een
herhaling van een eerdere.

Elke herhaling opent een tabblad bij de verkoper en schuift zijn echte werk naar
achteren, want schrijvende opdrachten gaan één voor één.

DE VOOR-EN-NA-PROEF staat in test_de_oude_code_bleef_elke_ronde_opnieuw_proberen:
die haalt de versie van vóór de reparatie uit commit 15506b9f (dus niet uit HEAD,
want daar zit de reparatie in) en laat hem onder exact dezelfde omstandigheden
tien rondes lang tien keer opnieuw beginnen.

Draaien:  python3 -m pytest tests/test_verkoop_reconciliatie_pogingen.py -q
"""
import asyncio
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl                    # noqa: E402
from backend.services import verkoop_reconciliatie as vr        # noqa: E402

OUDE_COMMIT = "15506b9f"   # de laatste commit vóór de reparatie


# ── Een minimale Supabase-bouwer ────────────────────────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.eqs, self.ins, self.gtes = {}, {}, {}
        self.op, self.velden, self.rijen_in = "select", None, None
        self._n = None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def insert(self, rows):
        self.op = "insert"
        self.rijen_in = rows if isinstance(rows, list) else [rows]
        return self
    def eq(self, k, v): self.eqs[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def gte(self, k, v): self.gtes[k] = v; return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self._n = n; return self

    def _match(self, r):
        return (all(r.get(k) == v for k, v in self.eqs.items())
                and all(r.get(k) in v for k, v in self.ins.items())
                and all(str(r.get(k) or "") >= str(v) for k, v in self.gtes.items()))

    def execute(self):
        bron = getattr(self.db, self.tabel)
        if self.op == "insert":
            for r in self.rijen_in:
                r.setdefault("id", f"{self.tabel}-{len(bron) + 1}")
                bron.append(dict(r))
            return types.SimpleNamespace(data=list(self.rijen_in))
        rijen = [r for r in bron if self._match(r)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
            return types.SimpleNamespace(data=rijen)
        return types.SimpleNamespace(data=rijen[: self._n] if self._n else rijen)


class _DB:
    def __init__(self, listings=None, jobs=None, items=None):
        self.listings, self.jobs, self.items = listings or [], jobs or [], items or []
    def table(self, naam): return _Q(self, naam)


def _t(uren_terug: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=uren_terug)).isoformat()


def _situatie_toon():
    """Verkocht op Vinted, Marktplaats-rij blijft 'active' zonder nummer."""
    return _DB(
        listings=[
            {"id": "L_v", "item_id": "it1", "platform": "vinted", "status": "sold",
             "sold_at": _t(120), "platform_listing_id": "9760553726"},
            {"id": "L_mp", "item_id": "it1", "platform": "marktplaats",
             "status": "active", "platform_listing_id": None},
        ],
        items=[{"id": "it1", "user_id": "u1"}],
    )


def _draai(module, db, rondes: int) -> list[dict]:
    """Laat de ronde N keer lopen en geef terug wat er is afgemeld.

    De nep-`delist_all_platforms` doet wat de echte doet en waar het hier om
    gaat: hij zet een verwijderopdracht in de tabel. Zo ziet de volgende ronde
    dezelfde geschiedenis als in productie.
    """
    aanroepen: list[dict] = []

    async def nep_delist(item_id, user_id, alleen_platforms=None):
        aanroepen.append({"item_id": item_id, "alleen_platforms": alleen_platforms})
        kanalen = alleen_platforms if alleen_platforms is not None else {"marktplaats"}
        for p in sorted(kanalen):
            db.jobs.append({"id": f"j{len(db.jobs) + 1}", "user_id": user_id,
                            "item_id": item_id, "platform": p, "action": "delete",
                            "status": "error", "created_at": _t(0)})
        return [{"platform": p, "status": "queued"} for p in sorted(kanalen)]

    async def direct(fn, *_a, **_k):
        return fn()

    oud_get, oud_lus, oud_delist = cl.get_db, module.naast_de_lus, cl.delist_all_platforms
    module.get_db = lambda: db
    module.naast_de_lus = direct
    cl.delist_all_platforms = nep_delist
    try:
        for _ in range(rondes):
            asyncio.run(module.reconcileer_verkochte_artikelen())
    finally:
        module.get_db = oud_get
        module.naast_de_lus = oud_lus
        cl.delist_all_platforms = oud_delist
    return aanroepen


def _oude_module() -> types.ModuleType:
    tekst = subprocess.run(
        ["git", "show", f"{OUDE_COMMIT}:backend/services/verkoop_reconciliatie.py"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "MAX_POGINGEN" not in tekst, (
        f"commit {OUDE_COMMIT} bevat de reparatie al — dan vergelijkt de "
        f"voor-proef de reparatie met zichzelf")
    mod = types.ModuleType("vr_oud")
    mod.__dict__["__file__"] = "vr_oud.py"
    exec(compile(tekst, "vr_oud.py", "exec"), mod.__dict__)
    return mod


# ── 1. De voor-proef: de oude code bleef elke ronde opnieuw beginnen ────────

def test_de_oude_code_bleef_elke_ronde_opnieuw_proberen():
    db = _situatie_toon()
    aanroepen = _draai(_oude_module(), db, rondes=10)
    assert len(aanroepen) == 10, (
        "de oude code hoort in tien rondes tien keer opnieuw af te melden — "
        f"dat is de lus die we repareren, gemeten: {len(aanroepen)}")
    assert len(db.jobs) == 10


# ── 2. Na de reparatie: één poging, daarna wachten ─────────────────────────

def test_na_de_reparatie_maar_een_poging_per_wachttijd():
    db = _situatie_toon()
    aanroepen = _draai(vr, db, rondes=10)
    assert len(aanroepen) == 1, (
        f"na één poging hoort de ronde een uur te wachten, gemeten: {len(aanroepen)}")
    assert len(db.jobs) == 1
    assert db.listings[1]["status"] == "active", "de rij blijft staan zoals hij was"


# ── 3. De wachttijd loopt op en stopt na vier pogingen ─────────────────────

@pytest.mark.parametrize("pogingen_uren, verwacht", [
    ([1.5],                 True),   # 1 poging, ruim een uur geleden → mag
    ([0.5],                 False),  # 1 poging, een half uur geleden → wachten
    ([20, 5],               True),   # 2 pogingen, laatste 5 uur geleden → mag
    ([20, 2],               False),  # 2 pogingen, laatste 2 uur geleden → wachten
    ([40, 30, 10],          False),  # 3 pogingen, laatste 10 uur geleden → wachten
    ([90, 80, 30],          True),   # 3 pogingen, laatste 30 uur geleden → mag
    ([90, 80, 40, 30],      False),  # vier pogingen: klaar, nooit meer
])
def test_wachttijd_en_bovengrens(pogingen_uren, verwacht):
    db = _situatie_toon()
    for n, uren in enumerate(pogingen_uren):
        db.jobs.append({"id": f"oud{n}", "user_id": "u1", "item_id": "it1",
                        "platform": "marktplaats", "action": "delete",
                        "status": "error", "created_at": _t(uren)})
    aanroepen = _draai(vr, db, rondes=1)
    assert bool(aanroepen) is verwacht


# ── 4. Alleen de kanalen die nog een poging mogen ──────────────────────────

def test_een_kanaal_dat_op_is_sleept_de_andere_niet_mee():
    db = _situatie_toon()
    db.listings.append({"id": "L_2dh", "item_id": "it1", "platform": "2dehands",
                        "status": "delisted", "platform_listing_id": "m2440770728"})
    # 2dehands heeft zijn vier pogingen erop zitten, Marktplaats nog geen enkele
    for n in range(4):
        db.jobs.append({"id": f"z{n}", "user_id": "u1", "item_id": "it1",
                        "platform": "2dehands", "action": "delete",
                        "status": "done", "created_at": _t(20 + n)})
    aanroepen = _draai(vr, db, rondes=1)
    assert len(aanroepen) == 1
    assert aanroepen[0]["alleen_platforms"] == {"marktplaats"}, (
        "2dehands is op; alleen Marktplaats mag nog een poging")
    assert not any(j["platform"] == "2dehands" and j["created_at"] > _t(1)
                   for j in db.jobs), "geen nieuwe 2dehands-opdracht"


# ── 5. Een verwijdering van vóór de verkoop telt niet mee ──────────────────

def test_pogingen_van_voor_de_verkoop_gebruiken_het_budget_niet_op():
    db = _situatie_toon()          # verkoop was 120 uur terug
    for n in range(4):
        db.jobs.append({"id": f"v{n}", "user_id": "u1", "item_id": "it1",
                        "platform": "marktplaats", "action": "delete",
                        "status": "done", "created_at": _t(130 + n)})
    aanroepen = _draai(vr, db, rondes=1)
    assert len(aanroepen) == 1, ("een herplaatsing of handmatige afmelding van vóór "
                                 "de verkoop mag dit vangnet niet vooraf opgebruiken")


# ── 6. Een verse verkoop krijgt zijn poging gewoon meteen ──────────────────

def test_verse_verkoop_wordt_meteen_afgemeld():
    db = _DB(
        listings=[
            {"id": "L_v", "item_id": "it2", "platform": "vinted", "status": "sold",
             "sold_at": _t(1), "platform_listing_id": "1"},
            {"id": "L_mp", "item_id": "it2", "platform": "marktplaats",
             "status": "active", "platform_listing_id": "m1"},
        ],
        items=[{"id": "it2", "user_id": "u1"}],
    )
    aanroepen = _draai(vr, db, rondes=1)
    assert len(aanroepen) == 1
    assert aanroepen[0]["alleen_platforms"] == {"marktplaats"}
