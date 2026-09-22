"""Een smartwatch die geld gaat kosten gaat naar Sporthorloges, niet uit de rij.

WAT ER SPEELDE (22-09-2026, call met Martijn Bax / Watchero, tweedehands Apple
Watches). Marktplaats laat per account maar twee advertenties gratis in
"Smartwatches" staan; de derde kost geld. "Sporthorloges" heeft die grens niet,
en daar zet hij de rest zelf in. Hij vroeg of Omnivaleur dat ook kan.

Zoals het was: de extensie ziet bij de derde smartwatch de betaalknop, klikt er
terecht niet op en meldt een betalende rubriek. De server nam daarop de rest
van zijn rij in Smartwatches terug. Vanaf de derde ging er dus niets meer online.

Deze proef draait zijn rij in het klein twee keer: door de code zoals hij nu is,
en door de code van vóór de reparatie.
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

# Vast commitnummer, geen HEAD: zodra dit gecommit is vergelijkt HEAD de
# reparatie met zichzelf en bewijst de voor-en-na niets meer.
VOOR_DE_REPARATIE = "f2219d4d"
USER = "martijn"
SMARTWATCH = "sieraden smartwatch"
SPORT = "sieraden sporthorloge"

# Wat de extensie meldt als het formulier de betaalknop toont. Letterlijk de
# opbouw van betaalrubriekBezwaar() in extension/content/shared.js.
FOUT_FORMULIER = (
    'Error: Marktplaats (marktplaats.nl) charges for an advert in this category '
    '(Smartwatches): there is no free option left and the publish button now reads '
    '"Naar betalen". Nothing was published and nothing was ordered — we never click a '
    'payment button for you. Either place this one yourself on Marktplaats '
    '(marktplaats.nl) and pay for it, or move the item to a category that is free there.'
)
# En als het tabblad toch op de betaalpagina uitkwam.
FOUT_BETAALPAGINA = ("Error: Not published | Still on "
                     "https://www.marktplaats.nl/payments/orderOverview?id=1")


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


def _job(jid, status, categorie, platform="marktplaats", **extra):
    return {"id": jid, "user_id": USER, "item_id": f"item-{jid}", "platform": platform,
            "action": "create", "status": status, "payload": {"category": categorie},
            "created_at": "2026-09-22T12:00:00+00:00", "done_at": None, "result": None,
            "claimed_at": None, **extra}


def _zijn_rij():
    """Twee smartwatches al gratis geplaatst, de derde loopt nu vast, drie wachten nog."""
    return _DB([
        _job("s1", "done", SMARTWATCH, done_at="2026-09-22T12:01:00+00:00"),
        _job("s2", "done", SMARTWATCH, done_at="2026-09-22T12:03:00+00:00"),
        _job("s3", "claimed", SMARTWATCH),
        _job("s4", "pending", SMARTWATCH),
        _job("s5", "pending", SMARTWATCH),
        _job("s6", "pending", SMARTWATCH),
        _job("h1", "pending", "sieraden horloges heren"),
        _job("v1", "pending", SMARTWATCH, platform="vinted"),
    ])


def _ontwapen(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "execute_with_retry", lambda b, *_a, **_kw: b.execute())
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "_kanaal_kansloos", lambda *_a, **_kw: False)
    # Martijn heeft een zakelijk Marktplaats-account.
    monkeypatch.setattr(module, "_is_zakelijk", lambda *_a, **_kw: True)
    if hasattr(module, "fetch_all"):
        monkeypatch.setattr(module, "fetch_all", lambda *_a, **_kw: [])


def _oude_module():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_GRATIS_UITWIJK" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


# ── De reparatie ─────────────────────────────────────────────────────────────
def test_de_derde_smartwatch_gaat_terug_in_de_rij_in_sporthorloges(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("s3", {"error": FOUT_FORMULIER}, user_id=USER)

    assert uit.get("requeued") is True
    s3 = db.job("s3")
    assert s3["status"] == "pending"
    assert s3["payload"]["category"] == SPORT
    assert s3["payload"]["_uitgeweken_van"] == SMARTWATCH
    assert s3["result"] is None and s3["claimed_at"] is None
    assert s3["created_at"] > "2026-09-22T12:00:00+00:00", "verse plek in de rij"


def test_de_wachtende_smartwatches_gaan_mee_en_niets_wordt_teruggenomen(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job("s3", {"error": FOUT_FORMULIER}, user_id=USER)

    for jid in ("s4", "s5", "s6"):
        assert db.job(jid)["status"] == "pending"
        assert db.job(jid)["payload"]["category"] == SPORT
    assert not [j for j in db.tabellen["jobs"] if j["status"] in ("cancelled", "error")]


def test_andere_rubrieken_en_kanalen_blijven_onaangeroerd(monkeypatch):
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job("s3", {"error": FOUT_FORMULIER}, user_id=USER)

    assert db.job("h1")["payload"] == {"category": "sieraden horloges heren"}
    assert db.job("v1")["payload"] == {"category": SMARTWATCH}, "Vinted kent geen gratis grens"


def test_ook_als_het_tabblad_op_de_betaalpagina_uitkwam(monkeypatch):
    # Zonder dit zou de betaalmuur bij een eerste plaatsing zelfs het hele
    # kanaal dichtzetten: Smartwatches vol zegt niets over Marktplaats.
    db = _zijn_rij()
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("s3", {"error": FOUT_BETAALPAGINA}, user_id=USER)

    assert uit.get("requeued") is True
    assert db.job("s3")["payload"]["category"] == SPORT


def test_kost_sporthorloges_ook_geld_dan_de_gewone_rem_en_geen_lus(monkeypatch):
    db = _DB([_job("x1", "claimed", SPORT)])
    db.job("x1")["payload"] = {"category": SPORT, "_uitgeweken_van": SMARTWATCH}
    db.tabellen["jobs"].append(_job("x2", "pending", SPORT))
    db.job("x2")["payload"] = {"category": SPORT, "_uitgeweken_van": SMARTWATCH}
    _ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("x1", {"error": FOUT_FORMULIER.replace("Smartwatches", "Sporthorloges")},
                            user_id=USER)

    assert not uit.get("requeued")
    assert db.job("x1")["status"] == "error"
    assert db.job("x2")["status"] == "cancelled"


def test_uitgifte_wijkt_uit_zodra_smartwatches_geld_kost():
    db = _DB([
        _job("s1", "done", SMARTWATCH, done_at="2026-09-22T12:01:00+00:00"),
        _job("s3", "done", SPORT, done_at="2026-09-22T12:09:00+00:00"),
        _job("s7", "pending", SMARTWATCH),
    ])
    db.job("s3")["payload"]["_uitgeweken_van"] = SMARTWATCH
    kandidaat = copy.deepcopy(db.job("s7"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)

    assert kandidaat["payload"]["category"] == SPORT
    assert db.job("s7")["payload"]["category"] == SPORT, "ook in de database, als bewijs"


def test_uitgifte_herkent_ook_de_oude_betaalmelding_zelf():
    db = _DB([
        _job("s1", "done", SMARTWATCH, done_at="2026-09-22T12:01:00+00:00"),
        _job("s2", "error", SMARTWATCH, done_at="2026-09-22T12:05:00+00:00",
             result={"error": FOUT_FORMULIER}),
        _job("s7", "pending", SMARTWATCH),
    ])
    kandidaat = copy.deepcopy(db.job("s7"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"]["category"] == SPORT


def test_zolang_er_een_gratis_plek_is_blijft_hij_in_smartwatches():
    db = _DB([
        _job("s1", "done", SMARTWATCH, done_at="2026-09-22T12:01:00+00:00"),
        _job("s7", "pending", SMARTWATCH),
    ])
    kandidaat = copy.deepcopy(db.job("s7"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"] == {"category": SMARTWATCH}


def test_een_verkochte_smartwatch_maakt_weer_plek():
    # Na het uitwijken ging er toch weer een smartwatch gratis in Smartwatches:
    # dan is dat het laatste wat we weten en blijft de volgende daar ook.
    db = _DB([
        _job("s3", "done", SPORT, done_at="2026-09-22T12:09:00+00:00"),
        _job("s8", "done", SMARTWATCH, done_at="2026-09-23T09:00:00+00:00"),
        _job("s9", "pending", SMARTWATCH),
    ])
    db.job("s3")["payload"]["_uitgeweken_van"] = SMARTWATCH
    kandidaat = copy.deepcopy(db.job("s9"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"] == {"category": SMARTWATCH}


def test_de_rubriek_van_marktplaats_zelf_wijkt_ook_uit():
    pl = {"category": SMARTWATCH,
          "mp_category": {"l1": 1826, "l2": 3041, "l1_naam": "Sieraden, Tassen en Uiterlijk",
                          "l2_naam": "Smartwatches"}}
    nieuw = jobs_api._uitwijk_payload(pl)
    assert nieuw["mp_category"]["l2"] == 3045
    assert nieuw["mp_category"]["l2_naam"] == "Sporthorloges"
    assert nieuw["category"] == SPORT
    assert nieuw["_uitgeweken_van"] == "mp:1826/3041"
    assert pl["mp_category"]["l2"] == 3041, "het origineel blijft ongemoeid"


def test_geen_uitwijk_bij_andere_rubrieken_of_een_herplaatsing():
    assert jobs_api._uitwijk_payload({"category": "sieraden horloges heren"}) is None
    assert jobs_api._uitwijk_payload({"category": SMARTWATCH, "_refresh_rollback": {}}) is None
    assert jobs_api._uitwijk_payload({"category": SPORT, "_uitgeweken_van": SMARTWATCH}) is None


def test_de_uitgifte_wijkt_uit_voor_de_betaalrem_kijkt():
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text()
    a = bron.index("if not _zet_rubriek_van_marktplaats(db, user_id, kandidaat):")
    b = bron.index("_wijk_uit_naar_gratis_rubriek(db, user_id, kandidaat)", a)
    c = bron.index("if _weiger_bekende_betaalde_rubriek(db, user_id, kandidaat):", a)
    assert a < b < c


def test_de_extensie_plaatst_de_uitgeweken_opdracht_echt_in_sporthorloges():
    """Draait getMpSyiUrl uit extension/background.js zelf, niet een beschrijving ervan."""
    script = r"""
    const fs = require("fs");
    const bron = fs.readFileSync(process.argv[1], "utf8");
    const stuk = (begin) => {
      const s = bron.indexOf(begin);
      if (s < 0) throw new Error(begin + " niet gevonden");
      return bron.slice(s, bron.indexOf("\n}", s) + 2) + (begin.startsWith("const") ? ";" : "");
    };
    // Alles boven de klasse zijn de vaste rubriektabellen waar getMpSyiUrl op leunt.
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
        ["marktplaats", {"category": SPORT, "_uitgeweken_van": SMARTWATCH}],
        ["marktplaats", jobs_api._uitwijk_payload(
            {"category": SMARTWATCH, "mp_category": {"l1": 1826, "l2": 3041}})],
        ["2dehands", {"category": SPORT, "_uitgeweken_van": SMARTWATCH}],
        ["marktplaats", {"category": SMARTWATCH}],
    ]
    uit = json.loads(subprocess.run(
        ["node", "-e", script, str(ROOT / "extension" / "background.js"), json.dumps(payloads)],
        capture_output=True, text=True, check=True).stdout)
    assert uit == [
        "https://www.marktplaats.nl/plaats/1826/3045?bucketId=199&title=",
        "https://www.marktplaats.nl/plaats/1826/3045?bucketId=199&title=",
        "https://www.2dehands.be/plaats/1826/3045?bucketId=199&title=",
        "https://www.marktplaats.nl/plaats/1826/3041?bucketId=199&title=",
    ]


# ── De voor-proef: zo ging het vóór deze reparatie ───────────────────────────
def test_de_vorige_versie_nam_de_rest_van_zijn_smartwatches_terug(monkeypatch):
    oud = _oude_module()
    db = _zijn_rij()
    _ontwapen(oud, monkeypatch, db)
    uit = oud.fail_job("s3", {"error": FOUT_FORMULIER}, user_id=USER)

    assert not uit.get("requeued")
    assert db.job("s3")["status"] == "error"
    assert [db.job(j)["status"] for j in ("s4", "s5", "s6")] == ["cancelled"] * 3
