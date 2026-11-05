"""De driedagenveger blijft van een grote reeks af zolang die loopt (05-11-2026, Goudlief).

Op 31-10 zette zij duizenden plaatsingen klaar. De veger blies er na drie dagen 500 per
ronde af, terwijl haar extensie dagelijks honderden plaatste. Draait de echte
`herstel_vastgelopen_werk` tegen een nep-tabel, met de oude code als voor-en-na-proef.
"""
import asyncio
import importlib.util
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORTEL = Path(__file__).resolve().parent.parent
NU = datetime.now(timezone.utc)
dag = lambda d: (NU - timedelta(days=d)).isoformat()  # noqa: E731


class Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.velden = db, tabel, [], None

    def select(self, *_a): return self
    def eq(self, k, v): self.f.append(lambda r: r.get(k) == v); return self
    def in_(self, k, v): v = list(v); self.f.append(lambda r: r.get(k) in v); return self
    def lt(self, k, v): self.f.append(lambda r: (r.get(k) or "") < v); return self
    def gt(self, k, v): self.f.append(lambda r: (r.get(k) or "") > v); return self
    def gte(self, k, v): self.f.append(lambda r: (r.get(k) or "") >= v); return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self.n = n; return self
    def update(self, v): self.velden = v; return self

    def execute(self):
        rijen = [r for r in self.db.get(self.tabel, []) if all(f(r) for f in self.f)]
        if self.velden is not None:
            for r in rijen:
                r.update(self.velden)
            return type("R", (), {"data": rijen})()
        return type("R", (), {"data": rijen[:getattr(self, "n", None)]})()


def _baan(i, user, platform="marktplaats", action="create", status="pending", **rest):
    return {"id": i, "user_id": user, "item_id": "i" + i, "platform": platform, "action": action,
            "status": status, "created_at": rest.pop("created_at", dag(5)), "payload": {}, **rest}


def _laad(code=None):
    pad = WORTEL / "backend/services/relist.py"
    if code:
        pad = Path(__file__).parent / f".relist_{code}.py"
        pad.write_text(subprocess.check_output(["git", "show", f"{code}:backend/services/relist.py"],
                                               cwd=WORTEL, text=True))
    spec = importlib.util.spec_from_file_location("relist_proef_" + (code or "nu"), pad)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        if code:
            pad.unlink()
    return mod


def _draai(mod, jobs, monkeypatch):
    tabellen = {"jobs": jobs}
    db = type("Db", (), {"table": lambda self, n: Vraag(tabellen, n)})()
    monkeypatch.setattr(mod, "get_db", lambda: db)

    async def direct(fn, *_a, **_k):
        return fn()
    monkeypatch.setattr(mod, "naast_de_lus", direct)
    monkeypatch.setattr(mod, "_waarom_bleef_het_staan", lambda *_a: "reden")
    asyncio.run(mod.herstel_vastgelopen_werk())
    return {j["id"]: j["status"] for j in jobs}


def _rij():
    return [
        _baan("loopt", "goudlief"),
        _baan("klaar", "goudlief", status="done", done_at=dag(1)),
        _baan("stil", "amanda"),
        _baan("stil_klaar", "amanda", status="done", done_at=dag(4)),
        _baan("te_oud", "goudlief", created_at=dag(15)),
        _baan("ander_kanaal", "goudlief", platform="2dehands"),
        _baan("prijs", "x", action="content_refresh", payload={"_prijs_bijwerken": True}),
    ]


def test_lopende_reeks_blijft_staan(monkeypatch):
    s = _draai(_laad(), _rij(), monkeypatch)
    assert s["loopt"] == "pending", "er lukte gisteren nog iets op dit kanaal"
    assert s["stil"] == "error", "drie dagen niets gelukt blijft een storing"
    assert s["te_oud"] == "error", "ook een lopende reeks heeft een bovengrens"
    assert s["ander_kanaal"] == "error", "werk op een ander kanaal lift niet mee"
    assert s["prijs"] == "pending", "wacht op de extensie-update, advertentie staat online"


def test_oude_code_blies_de_lopende_reeks_af(monkeypatch):
    s = _draai(_laad("0320d27d"), _rij(), monkeypatch)
    assert s["loopt"] == "error" and s["prijs"] == "error"


def test_lopende_reeks_duwt_andere_klanten_niet_uit_de_ronde(monkeypatch):
    jobs = [_baan(f"g{i}", "goudlief") for i in range(600)]
    jobs += [_baan("klaar", "goudlief", status="done", done_at=dag(1)), _baan("ander", "amanda")]
    s = _draai(_laad(), jobs, monkeypatch)
    assert s["ander"] == "error" and s["g0"] == "pending"
