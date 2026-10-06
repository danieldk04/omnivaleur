"""Een tapijt dat geld gaat kosten gaat naar Woonaccessoires | Overige, niet uit de rij.

WAT ER SPEELDE (06-10-2026, Toon / De Juiste Toon, 2dehands.be). "Stoffering |
Tapijten en Vloerkleden" (504/533) is bij hem vol en kost geld. Zelf zette hij
ze eerder in "Woonaccessoires | Overige" (504/536), en daar kwamen ze gratis
online. Omnivaleur bleef tegen de betaalknop van 533 lopen: 5 tapijten
liepen vast en de rest van de rij werd teruggenomen.

Zelfde mechanisme als de smartwatches (_GRATIS_UITWIJK). Voor-en-na: de vorige
versie (zonder tapijten in de lijst) neemt de rest van de rij terug.
"""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as jobs_api  # noqa: E402

# Vast commitnummer, geen HEAD (zie de smartwatch-proef): de code zonder tapijten.
VOOR_DE_REPARATIE = "1c6a4841"
USER = "toon"
TAPIJT = "wonen tapijten en kleden"
OVERIG = "wonen vachten"  # 504/536 in de extensie

FOUT_FORMULIER = (
    'Error: 2dehands (2dehands.be) charges for an advert in this category '
    '(Tapijten en Vloerkleden): there is no free option left and the publish button now reads '
    '"Naar betalen". Nothing was published and nothing was ordered — we never click a '
    'payment button for you. Either place this one yourself on 2dehands '
    '(2dehands.be) and pay for it, or move the item to a category that is free there.'
)
FOUT_BETAALPAGINA = ("Error: Not published | Still on "
                     "https://www.2dehands.be/payments/orderOverview?id=1")


# ── Een nagebootste database: filtert, werkt bij en kent payload->veld ──────
class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.kolommen, self.filters, self.wijziging = "*", [], None

    def select(self, kolommen="*", *_a, **_kw):
        self.kolommen = kolommen
        return self

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def eq(self, veld, waarde):
        self.filters.append(("eq", veld, waarde))
        return self

    def in_(self, veld, waarden):
        self.filters.append(("in", veld, list(waarden)))
        return self

    @property
    def not_(self):
        return self

    def __getattr__(self, _naam):
        return lambda *_a, **_kw: self

    @staticmethod
    def _waarde(rij, veld):
        if veld.startswith("payload->"):
            return (rij.get("payload") or {}).get(veld.split("->", 1)[1])
        return rij.get(veld)

    def execute(self):
        rijen = self.db.tabellen.setdefault(self.tabel, [])
        raak = [r for r in rijen if all(
            (self._waarde(r, v) == w) if soort == "eq" else (self._waarde(r, v) in w)
            for soort, v, w in self.filters)]
        if self.wijziging is not None:
            for r in raak:
                r.update(copy.deepcopy(self.wijziging))
            return _Antwoord(copy.deepcopy(raak))
        uit = []
        for r in raak:
            d = copy.deepcopy(r)
            for kol in str(self.kolommen).split(","):
                kol = kol.strip()
                if kol.startswith("payload->"):
                    d[kol.split("->", 1)[1]] = copy.deepcopy((r.get("payload") or {}).get(
                        kol.split("->", 1)[1]))
            uit.append(d)
        return _Antwoord(uit)


class _DB:
    def __init__(self, jobs):
        self.tabellen = {"jobs": jobs, "listings": []}

    def table(self, naam):
        return _Vraag(self, naam)

    def job(self, jid):
        return next(j for j in self.tabellen["jobs"] if j["id"] == jid)


def _job(jid, status, categorie, platform="2dehands", **extra):
    return {"id": jid, "user_id": USER, "item_id": f"item-{jid}", "platform": platform,
            "action": "create", "status": status, "payload": {"category": categorie},
            "created_at": "2026-10-06T12:00:00+00:00", "done_at": None, "result": None,
            "claimed_at": None, **extra}


def _zijn_rij():
    return _DB([
        _job("t1", "done", TAPIJT, done_at="2026-10-06T12:01:00+00:00"),
        _job("t2", "claimed", TAPIJT),
        _job("t3", "pending", TAPIJT),
        _job("t4", "pending", TAPIJT),
        _job("k1", "pending", "wonen kussens"),
        _job("m1", "pending", TAPIJT, platform="marktplaats"),
        _job("v1", "pending", TAPIJT, platform="vinted"),
    ])


def _ontwapen(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "execute_with_retry", lambda b, *_a, **_kw: b.execute())
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "_kanaal_kansloos", lambda *_a, **_kw: False)
    monkeypatch.setattr(module, "_is_zakelijk", lambda *_a, **_kw: False)
    if hasattr(module, "fetch_all"):
        monkeypatch.setattr(module, "fetch_all", lambda *_a, **_kw: [])


def _oude_module():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert '"wonen tapijten en kleden": "' not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_tapijt.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_tapijt", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def test_het_vastgelopen_tapijt_gaat_terug_in_de_rij_in_overige(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("t2", {"error": FOUT_FORMULIER}, user_id=USER)

    assert uit.get("requeued") is True
    t2 = db.job("t2")
    assert t2["status"] == "pending"
    assert t2["payload"]["category"] == OVERIG
    assert t2["payload"]["_uitgeweken_van"] == TAPIJT
    assert t2["result"] is None and t2["claimed_at"] is None


def test_wachtende_tapijten_gaan_mee_en_andere_kanalen_en_rubrieken_niet(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job("t2", {"error": FOUT_FORMULIER}, user_id=USER)

    for jid in ("t3", "t4"):
        assert db.job(jid)["payload"]["category"] == OVERIG, jid
        assert db.job(jid)["status"] == "pending"
    assert db.job("k1")["payload"] == {"category": "wonen kussens"}
    assert db.job("v1")["payload"] == {"category": TAPIJT}, "Vinted kent geen gratis grens"
    assert db.job("m1")["payload"] == {"category": TAPIJT}, "Marktplaats heeft een eigen telling"
    assert not [j for j in db.tabellen["jobs"] if j["status"] in ("cancelled", "error")]


def test_ook_als_het_tabblad_op_de_betaalpagina_uitkwam(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("t2", {"error": FOUT_BETAALPAGINA}, user_id=USER)
    assert uit.get("requeued") is True
    assert db.job("t2")["payload"]["category"] == OVERIG


def test_kost_overige_ook_geld_dan_de_gewone_rem_en_geen_lus(monkeypatch):
    db = _DB([_job("x1", "claimed", OVERIG), _job("x2", "pending", OVERIG)])
    for j in ("x1", "x2"):
        db.job(j)["payload"] = {"category": OVERIG, "_uitgeweken_van": TAPIJT}
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("x1", {"error": FOUT_FORMULIER.replace("Tapijten en Vloerkleden", "Overige")},
                            user_id=USER)
    assert not uit.get("requeued")
    assert db.job("x1")["status"] == "error"
    assert db.job("x2")["status"] == "cancelled"


def test_uitgifte_wijkt_uit_zodra_tapijten_geld_kosten():
    db = _DB([
        _job("t1", "done", TAPIJT, done_at="2026-10-06T12:01:00+00:00"),
        _job("t2", "error", TAPIJT, done_at="2026-10-06T12:05:00+00:00",
             result={"error": FOUT_FORMULIER}),
        _job("t7", "pending", TAPIJT),
    ])
    kandidaat = copy.deepcopy(db.job("t7"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"]["category"] == OVERIG


def test_zolang_er_een_gratis_plek_is_blijft_het_tapijt_in_tapijten():
    db = _DB([_job("t1", "done", TAPIJT, done_at="2026-10-06T12:01:00+00:00"),
              _job("t7", "pending", TAPIJT)])
    kandidaat = copy.deepcopy(db.job("t7"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"] == {"category": TAPIJT}


def test_de_rubriek_van_marktplaats_zelf_wijkt_ook_uit():
    pl = {"category": TAPIJT,
          "mp_category": {"l1": 504, "l2": 533, "l1_naam": "Huis en Inrichting",
                          "l2_naam": "Tapijten en Vloerkleden"}}
    nieuw = jobs_api._uitwijk_payload(pl)
    assert (nieuw["mp_category"]["l1"], nieuw["mp_category"]["l2"]) == (504, 536)
    assert nieuw["category"] == OVERIG
    assert nieuw["_uitgeweken_van"] == "mp:504/533"
    assert pl["mp_category"]["l2"] == 533, "het origineel blijft ongemoeid"


def test_geen_uitwijk_bij_herplaatsing_of_al_uitgeweken():
    assert jobs_api._uitwijk_payload({"category": TAPIJT, "_refresh_rollback": {}}) is None
    assert jobs_api._uitwijk_payload({"category": OVERIG, "_uitgeweken_van": TAPIJT}) is None
    assert jobs_api._uitwijk_payload({"category": "wonen kussens"}) is None


def test_de_extensie_opent_voor_de_uitgeweken_opdracht_echt_rubriek_536():
    """Draait getMpSyiUrl uit extension/background.js zelf, niet een beschrijving ervan."""
    script = r"""
    const fs = require("fs");
    const bron = fs.readFileSync(process.argv[1], "utf8");
    const stuk = (begin) => {
      const s = bron.indexOf(begin);
      if (s < 0) throw new Error(begin + " niet gevonden");
      return bron.slice(s, bron.indexOf("\n}", s) + 2);
    };
    const code = [
      "const importScripts = () => {};",
      bron.slice(0, bron.indexOf("class CategoryUnresolvedError")),
      stuk("class CategoryUnresolvedError"), "let _mpOpNummer = null;",
      stuk("function mpCategorieOpNummer("), stuk("function mpKidsSizeCat3("),
      stuk("function getMpSyiUrl("),
    ].join("\n");
    const f = new Function(code + "\nreturn getMpSyiUrl;")();
    const payloads = JSON.parse(process.argv[2]);
    console.log(JSON.stringify(payloads.map(([p, pl]) => f(p, pl))));
    """
    payloads = [
        ["2dehands", jobs_api._uitwijk_payload({"category": TAPIJT})],
        ["2dehands", jobs_api._uitwijk_payload(
            {"category": TAPIJT, "mp_category": {"l1": 504, "l2": 533}})],
        ["2dehands", {"category": TAPIJT}],
    ]
    uit = json.loads(subprocess.run(
        ["node", "-e", script, str(ROOT / "extension" / "background.js"), json.dumps(payloads)],
        capture_output=True, text=True, check=True).stdout)
    assert uit == [
        "https://www.2dehands.be/plaats/504/536?title=",
        "https://www.2dehands.be/plaats/504/536?title=",
        "https://www.2dehands.be/plaats/504/533?title=",
    ]


def test_de_vorige_versie_nam_de_rest_van_zijn_tapijten_terug(monkeypatch):
    oud = _oude_module()
    db = _zijn_rij()
    _ontwapen(oud, monkeypatch, db)
    uit = oud.fail_job("t2", {"error": FOUT_FORMULIER}, user_id=USER)

    assert not uit.get("requeued")
    assert db.job("t2")["status"] == "error"
    assert [db.job(j)["status"] for j in ("t3", "t4")] == ["cancelled"] * 2
