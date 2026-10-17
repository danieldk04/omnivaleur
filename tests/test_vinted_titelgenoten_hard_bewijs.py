"""Vinted-advertenties hingen aan het verkeerde artikel met dezelfde titel.

WAAROM DIT ER IS (16-10-2026, Janneke 31d28378, Als Nieuw kinderkleding)
Een groene "Tussenjas Name it maat 128" werd op Vinted verkocht, maar die
advertentie (10392587289) hing aan haar blauwe fleece met dezelfde titel.
Omnivaleur boekte de fleece als verkocht, haalde de FLEECE van Marktplaats en
liet de verkochte jas staan. 9 van haar 193 Vinted-rijen hingen verkeerd.

Gemeten in de serverlog van 15-10 (UTC):
  20:01:16  jas cace9e18 (groen, 30 euro) krijgt de Vinted-opdracht
  20:03:52  de bewaker van de extensie meldt hem "timed out"; tabblad blijft open
  20:04:15  jas f7abfe10 (25 euro) krijgt al de volgende Vinted-opdracht
  20:06:40  f7abfe10 "timed out";  20:06:47 jas 6eb3ae64 erbij
  20:07:15  cace9e18 meldt zich alsnog: advertentie gevonden op titel in de kast
  20:10:19  fleece 4b6dcf79: "staat al online" = 10392587289, de groene jas

Drie lagen, elk met de oude code (VOOR) naast de nieuwe:
  1. extensie: koppelen op titel vraagt bij titelgenoten hard bewijs
     (prijs, en "pas na onze klik verschenen"), anders niet koppelen;
  2. server: na een "timed out" blijft Vinted even bezet, en "staat al online"
     bij titelgenoten koppelt de server niet;
  3. import en scan: alleen de titel gelijk en de prijs niet = twijfel.
"""
import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.imports as I  # noqa: E402
import backend.api.jobs as J  # noqa: E402
from tests.test_vinted_titelgenoot_niet_koppelen import _DB as _TitelDB  # noqa: E402
from tests.test_shopify_nummer_gaat_voor_titel import _DB as _ScanDB  # noqa: E402

VOOR = "8a07b59d"
NODE = shutil.which("node")
TITEL = "Tussenjas Name it maat 128"


def _bron(pad: str, commit: str | None) -> str:
    if commit is None:
        return (ROOT / pad).read_text()
    return subprocess.run(["git", "show", f"{commit}:{pad}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


_OUD: dict = {}


def _oude_module(pad: str, commit: str = VOOR):
    """De module zoals hij vóór de reparatie was, naast de huidige geladen."""
    if (pad, commit) not in _OUD:
        map_ = Path(tempfile.mkdtemp())
        naam = f"oud_{commit}_" + Path(pad).stem
        (map_ / f"{naam}.py").write_text(_bron(pad, commit))
        spec = importlib.util.spec_from_file_location(naam, map_ / f"{naam}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _OUD[(pad, commit)] = mod
    return _OUD[(pad, commit)]


def _stuk(bron: str, kop: str, eind: str) -> str:
    start = bron.index(kop)
    return bron[start:bron.index(eind, start) + len(eind)]


def _node(js: str):
    if NODE is None:
        pytest.skip("node is niet geïnstalleerd")
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    uit = json.loads(r.stdout.strip())
    return uit["id"] if uit else None


def _kast(*advertenties):
    return [{"id": i, "title": TITEL, "price": {"amount": f"{p:.1f}", "currency_code": "EUR"},
             "is_closed": False, "is_draft": False} for i, p in advertenties]


# ── laag 1: de extensie (content/vinted.js) ──────────────────────────────────
def _zoek(commit, payload, kast, timeout, opts):
    """resolveCreatedVintedItem uit de echte vinted.js, met een nagemaakte kast."""
    bron = _bron("extension/content/vinted.js", commit)
    return _node(f"""
const sleep = async () => {{}};
const getVintedUserId = async () => "1";
const fetch = async () => ({{ ok: true, json: async () => ({{ items: {json.dumps(kast)} }}) }});
{_stuk(bron, "  async function resolveCreatedVintedItem(", "\n  }\n")}
const item = {json.dumps(payload)};
resolveCreatedVintedItem(item, item.platform_listing_id, {timeout}, {json.dumps(opts)})
  .then((r) => console.log(JSON.stringify(r)));
""")


# De kast om 20:10:16, toen de fleece aan de beurt was. 10392558329 hing toen
# (ten onrechte) aan de groene jas, de twee oudste aan ec8b24d7 en 7116aa69.
KAST_2010 = _kast((10392587289, 30.0), (10392558329, 25.0), (10392421333, 27.5),
                  (10392410083, 25.0))
FLEECE_OUDE_SERVER = {"title": TITEL, "price": 29.5,
                      "_vinted_bezet": ["10392558329", "10392421333", "10392410083"],
                      "platform_listing_id": "10392558329"}
FLEECE = {**FLEECE_OUDE_SERVER, "_vinted_titelgenoten": 6}
VOORAF = {"exact": True, "vooraf": True}


def test_oud_gaf_de_fleece_de_advertentie_van_de_groene_jas():
    assert _zoek(VOOR, FLEECE_OUDE_SERVER, KAST_2010, 2500, {"exact": True}) == "10392587289"


def test_nieuw_koppelt_vooraf_niet_bij_titelgenoten():
    assert _zoek(None, FLEECE, KAST_2010, 2500, VOORAF) is None


def test_nieuw_ziet_titelgenoten_ook_zonder_telling_van_de_server():
    """Twee advertenties met deze titel in de kast zelf zijn al titelgenoten."""
    payload = {"title": TITEL, "price": 30.0}
    kast = _kast((10392587289, 30.0), (10392410083, 30.0))
    assert _zoek(VOOR, payload, kast, 2500, {"exact": True}) == "10392587289"
    assert _zoek(None, payload, kast, 2500, VOORAF) is None


def test_nieuw_koppelt_vooraf_nog_wel_een_enig_stuk_met_dezelfde_prijs():
    """Waar de controle voor is: hing de plaatsing en zette de verkoper hem zelf
    online, dan koppelen in plaats van een tweede advertentie."""
    assert _zoek(None, {"title": TITEL, "price": 30.0}, _kast((10392587289, 30.0)),
                 2500, VOORAF) == "10392587289"


def test_nieuw_koppelt_vooraf_geen_enig_stuk_met_een_andere_prijs():
    kast = _kast((9801378562, 40.0))
    assert _zoek(VOOR, {"title": TITEL, "price": 45.0}, kast, 2500, {"exact": True}) == "9801378562"
    assert _zoek(None, {"title": TITEL, "price": 45.0}, kast, 2500, VOORAF) is None


# Na de klik van de groene jas (20:02): het hoogste nummer in de kast was toen
# 10392460030 (de Noppies-jas van 20:01). Om 20:07 stond de advertentie van
# f7abfe10 (25 euro) er nieuw bij.
GROEN = {"title": TITEL, "price": 30.0, "_vinted_bezet": ["10392421333", "10392410083"],
         "_vinted_titelgenoten": 6}
HOOGWATER = 10392460030
KAST_2007 = _kast((10392558329, 25.0), (10392460030, 29.5), (10392421333, 27.5),
                  (10392410083, 25.0))


def test_oud_gaf_de_groene_jas_na_de_klik_de_advertentie_van_een_ander():
    assert _zoek(VOOR, GROEN, KAST_2007, 5, {}) == "10392558329"


def test_nieuw_neemt_na_de_klik_geen_advertentie_met_een_andere_prijs():
    assert _zoek(None, GROEN, KAST_2007, 5, {"naId": HOOGWATER}) is None


def test_nieuw_vindt_na_de_klik_wel_de_eigen_advertentie():
    kast = _kast((10392587289, 30.0)) + KAST_2007
    assert _zoek(None, GROEN, kast, 5, {"naId": HOOGWATER}) == "10392587289"


def test_nieuw_kiest_niet_tussen_twee_nieuwe_met_dezelfde_prijs():
    payload = {**GROEN, "price": 25.0}
    kast = _kast((10392587289, 25.0)) + KAST_2007
    assert _zoek(VOOR, payload, kast, 5, {}) == "10392587289"
    assert _zoek(None, payload, kast, 5, {"naId": HOOGWATER}) is None


def test_nieuw_zonder_hoogwater_bij_titelgenoten_geen_koppeling():
    kast = _kast((10392587289, 30.0)) + KAST_2007
    assert _zoek(None, GROEN, kast, 5, {}) is None


def test_nieuw_zonder_titelgenoten_vindt_de_advertentie_zoals_altijd():
    kast = _kast((10392587289, 30.0))
    assert _zoek(None, {"title": TITEL, "price": 30.0}, kast, 5, {}) == "10392587289"


# ── laag 1b: de bewaker in background.js ─────────────────────────────────────
def _bewaker(commit, payload, kast):
    bron = _bron("extension/background.js", commit)
    hulp = (_stuk(bron, "function _vintedPrijsKlopt(", "\n}\n")
            if "function _vintedPrijsKlopt(" in bron else "")
    return _node(f"""
const VINTED_ORIGINS = ["https://www.vinted.nl"];
const fetch = async (url) => ({{ ok: true, json: async () =>
  (String(url).includes("/users/current") ? {{ user: {{ id: 1 }} }} : {{ items: {json.dumps(kast)} }}) }});
{_stuk(bron, "function _vintedTitelSleutel(", "\n}\n")}
{_stuk(bron, "function _vintedTitelZonderSku(", "\n}\n")}
{hulp}
{_stuk(bron, "async function bgVindVintedAdvertentie(", "\n}\n")}
bgVindVintedAdvertentie({json.dumps(payload)}).then((r) => console.log(JSON.stringify(r)));
""")


def test_oude_bewaker_gaf_de_fleece_de_groene_jas():
    assert _bewaker(VOOR, FLEECE_OUDE_SERVER, KAST_2010) == "10392587289"


def test_nieuwe_bewaker_koppelt_niet_bij_titelgenoten():
    assert _bewaker(None, FLEECE, KAST_2010) is None


def test_nieuwe_bewaker_koppelt_een_enig_stuk_nog_wel():
    assert _bewaker(None, {"title": TITEL, "price": 30.0},
                    _kast((10392587289, 30.0))) == "10392587289"


def test_nieuwe_bewaker_koppelt_geen_enig_stuk_met_een_andere_prijs():
    assert _bewaker(None, {"title": TITEL, "price": 45.0}, _kast((10392587289, 40.0))) is None


# ── laag 2a: de uitgifte houdt Vinted bezet na een "timed out" ──────────────
TIMEOUT = ("Extension timed out waiting for this vinted job to finish (no response after "
           "3 minutes). The page may have changed. [laatste stap: \"plaatsen: op de knop "
           "geklikt, wachten op de advertentie\", 94s geleden] [extensie 1.0.388]")


def _uitgifte(monkeypatch, mod, fouten_geleden_sec, fouttekst=TIMEOUT):
    nu = datetime.now(timezone.utc)
    wachtend = {"id": "56ded954", "user_id": "u1", "item_id": "f7abfe10", "platform": "vinted",
                "action": "create", "status": "pending", "payload": {"title": TITEL, "price": 25.0},
                "created_at": (nu - timedelta(minutes=5)).isoformat(), "claimed_at": None,
                "done_at": None, "scheduled_for": None}
    fout = {"result": {"error": fouttekst},
            "done_at": (nu - timedelta(seconds=fouten_geleden_sec)).isoformat()}

    class _B:
        def __init__(self, tabel):
            self.tabel, self.filters, self.ondergrens = tabel, {}, None

        def select(self, *a, **k): return self
        def update(self, *a, **k): return self
        def eq(self, k, v): self.filters[k] = v; return self
        def neq(self, *a, **k): return self
        def in_(self, k, v): self.filters[k] = list(v); return self
        def lte(self, *a, **k): return self
        def gte(self, k, v): self.ondergrens = (k, v); return self
        def or_(self, *a, **k): return self
        def ilike(self, *a, **k): return self
        def order(self, *a, **k): return self
        def limit(self, *a, **k): return self

        @property
        def not_(self):
            buiten = self

            class _Niet:
                def is_(self, *a): return buiten
            return _Niet()

        def execute(self):
            data = []
            f = self.filters
            if self.tabel == "jobs":
                if f.get("status") == "error" and f.get("platform") == "vinted":
                    # Zoals de echte database: alleen binnen het gevraagde venster.
                    if not self.ondergrens or fout["done_at"] >= self.ondergrens[1]:
                        data = [fout]
                elif f.get("status") == "pending" or "id" in f:
                    data = [wachtend]
            elif self.tabel == "items":
                data = [{"id": "f7abfe10", "user_id": "u1", "title": TITEL, "sku": None,
                         "brand": None, "price": 25.0}]
            return type("R", (), {"data": data})()

    class _Db:
        def table(self, naam): return _B(naam)

    monkeypatch.setattr(mod, "get_db", lambda: _Db())
    monkeypatch.setattr(mod, "_record_extension_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_recover_stale_claims", lambda *a, **k: None)
    monkeypatch.setattr(mod, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(mod, "_zet_kleur_goed", lambda rijen: None)
    monkeypatch.setattr(mod, "_vinted_titelgenoten_meegeven", lambda *a, **k: 0)
    uit = mod.get_pending_jobs(request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.388"}})(),
                               platform="vinted", user_id="u1")
    return [j["id"] for j in uit]


def test_oud_gaf_23_seconden_na_de_time_out_al_de_volgende_vinted_plaatsing(monkeypatch):
    assert _uitgifte(monkeypatch, _oude_module("backend/api/jobs.py"), 23) == ["56ded954"]


def test_nieuw_houdt_vinted_bezet_zolang_het_tabblad_kan_doorwerken(monkeypatch):
    assert _uitgifte(monkeypatch, J, 23) == []
    assert _uitgifte(monkeypatch, J, 7 * 60) == []


def test_nieuw_geeft_vinted_weer_vrij_na_de_naloop(monkeypatch):
    assert _uitgifte(monkeypatch, J, 9 * 60) == ["56ded954"]


# De opruiming door de server zelf, als de "timed out" van de extensie nooit
# aankwam (Janneke, 16-10 22:26-22:30: vijf keer 422 op /error).
ONDERBROKEN = ("Publishing was interrupted (Chrome likely closed mid-run) and couldn't be "
               "verified either way — check whether it actually listed before publishing again "
               "to avoid a duplicate.")
EERSTE_REPARATIE = "a5466632"


def test_eerste_reparatie_liet_na_de_opruiming_de_volgende_toch_uit(monkeypatch):
    mod = _oude_module("backend/api/jobs.py", EERSTE_REPARATIE)
    assert _uitgifte(monkeypatch, mod, 3, ONDERBROKEN) == ["56ded954"]


def test_nieuw_houdt_vinted_ook_bezet_na_de_opruiming_door_de_server(monkeypatch):
    assert _uitgifte(monkeypatch, J, 3, ONDERBROKEN) == []
    assert _uitgifte(monkeypatch, J, 9 * 60, ONDERBROKEN) == ["56ded954"]


def test_nieuw_een_andere_fout_houdt_niets_bezet(monkeypatch):
    """Tabblad dicht of een uitgelegde fout: daar loopt niets meer."""
    dicht = "The tab this vinted job was working in was closed before it finished."
    assert _uitgifte(monkeypatch, J, 23, dicht) == ["56ded954"]


# ── laag 2b: "staat al online" bij titelgenoten koppelt de server niet ──────
def _afmelden(monkeypatch, mod, items):
    db = _TitelDB(items=items, listings=[])
    db.tabellen["jobs"] = [{"id": "j1", "user_id": "u1", "item_id": "fleece", "platform": "vinted",
                            "action": "create", "status": "claimed",
                            "payload": {"title": TITEL, "price": 29.5}}]
    gemeld, gekoppeld = {}, []

    async def _koppel(db_, job, body):
        gekoppeld.append(body["platform_listing_id"])

    monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr(mod, "_record_extension_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(mod, "fail_job", lambda job_id, body, user_id: gemeld.update(body))
    monkeypatch.setattr(mod, "_rond_publicatie_af", _koppel)
    monkeypatch.setattr(mod, "_verzending_alsnog_bijwerken", lambda *a, **k: None)
    uit = asyncio.run(mod.complete_job("j1", {"platform_listing_id": "10392587289",
                                              "note": "already_published_manually"}, user_id="u1"))
    return uit.get("status"), gekoppeld, gemeld.get("error", "")


TWEE_JASSEN = [{"id": "fleece", "user_id": "u1", "title": TITEL},
               {"id": "groen", "user_id": "u1", "title": TITEL}]


def test_oude_server_koppelde_de_groene_advertentie_aan_de_fleece(monkeypatch):
    status, gekoppeld, _ = _afmelden(monkeypatch, _oude_module("backend/api/jobs.py"), TWEE_JASSEN)
    assert gekoppeld == ["10392587289"]


def test_nieuwe_server_koppelt_al_online_niet_bij_titelgenoten(monkeypatch):
    status, gekoppeld, fout = _afmelden(monkeypatch, J, TWEE_JASSEN)
    assert status == "title_twin_not_linked"
    assert gekoppeld == []
    assert "more items with this title" in fout


def test_nieuwe_server_koppelt_al_online_zonder_titelgenoot_gewoon(monkeypatch):
    status, gekoppeld, _ = _afmelden(monkeypatch, J, TWEE_JASSEN[:1])
    assert gekoppeld == ["10392587289"]


def test_titelgenoten_gaan_mee_in_de_opdracht():
    db = _TitelDB(items=TWEE_JASSEN + [{"id": "vreemd", "user_id": "u2", "title": TITEL}],
                  listings=[])
    job = {"id": "j1", "user_id": "u1", "item_id": "fleece", "platform": "vinted",
           "action": "create", "payload": {"title": TITEL, "price": 29.5}}
    J._vinted_titelgenoten_meegeven(db, "u1", [job])
    assert job["payload"]["_vinted_titelgenoten"] == 1


# ── laag 3: import en scan koppelen niet op titel alleen ────────────────────
# Janneke's 0e7753df: Shopify-artikel van 25 euro, eigen oude Vinted-advertentie
# van 15 euro met dezelfde titel en een andere tekst.
JAS56 = {"id": "0e7753df", "title": "Jas Name it maat 56", "price": 25.0, "brand": None,
         "sku": "imp-0e7753df"}
OUDE_ADV = {"platform": "vinted", "platform_listing_id": "10309904325",
            "title": "Jas Name it maat 56", "price": 15.0}


def test_oude_import_koppelde_15_euro_aan_25_euro_op_titel():
    oud = _oude_module("backend/api/imports.py")
    assert oud._match_candidate(OUDE_ADV, [JAS56], {}) == ("0e7753df", "same_title")


def test_nieuwe_import_maakt_er_twijfel_van():
    assert I._match_candidate(OUDE_ADV, [JAS56], {}) == ("0e7753df", "likely_same")
    assert I._twijfelreden(OUDE_ADV, "0e7753df", "likely_same", set(), {}, {}) == "likely_same"


def test_nieuwe_import_koppelt_dezelfde_prijs_nog_steeds():
    adv = {**OUDE_ADV, "price": 25.0}
    assert I._match_candidate(adv, [JAS56], {}) == ("0e7753df", "same_title")


@pytest.mark.parametrize("vinted, shopify", [(15.0, 27.5), (15.0, 30.0), (17.5, 27.5), (40.0, 45.0)])
def test_nieuwe_import_vangt_alle_vijf_gemeten_gevallen(vinted, shopify):
    """De vijf foute koppelingen bij Janneke hadden deze prijzen (en 15 tegen 25)."""
    adv = {**OUDE_ADV, "price": vinted}
    assert I._match_candidate(adv, [{**JAS56, "price": shopify}], {})[1] == "likely_same"


def _scan(mod, monkeypatch, prijs):
    monkeypatch.setattr(mod, "fetch_all", lambda q: q().execute().data or [])
    monkeypatch.setattr(mod, "fetch_all_in", lambda q, _k, _w: q().execute().data or [])
    db = _ScanDB(items=[{**JAS56, "user_id": "u1"}], listings=[])
    mod._store_scan_results(db, {"id": "s1", "user_id": "u1", "platform": "vinted", "action": "scan"},
                            [{**OUDE_ADV, "price": prijs}])
    return db.import_candidates[0]["suggested_item_id"], [l["item_id"] for l in db.listings]


def test_oude_scan_hing_de_advertentie_van_15_euro_aan_het_jasje_van_25(monkeypatch):
    assert _scan(_oude_module("backend/api/jobs.py"), monkeypatch, 15.0) == ("0e7753df", ["0e7753df"])


def test_nieuwe_scan_koppelt_hem_niet(monkeypatch):
    assert _scan(J, monkeypatch, 15.0) == (None, [])


def test_nieuwe_scan_koppelt_dezelfde_prijs_nog_steeds(monkeypatch):
    assert _scan(J, monkeypatch, 25.0) == ("0e7753df", ["0e7753df"])
