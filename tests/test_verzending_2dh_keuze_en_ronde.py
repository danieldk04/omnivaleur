"""Verzendkosten op 2dehands: drie keuzes, een eigen keuze per artikel, en de ronde
over wat al online staat (27-09-2026).

WAT ER GEBEURDE. Egbert Brouwer (Papa's Plectrums) mailde drie keer over dure
verzendkosten op 2dehands. Elke keer moest iemand bij ons iets met de hand doen:
een titelwoord zetten, een briefgrens zetten, en daarna een script draaien om de
zoekertjes die al online stonden om te zetten (197 omgezet, 198 bleven liggen
omdat Marktplaats 403 gaf en niemand de tweede ronde draaide). Daniel: "ervoor
zorgen dat ik niet constant iedereen individueel zit te berichten".

Voor-en-na tegen a602e666 (Preferences: verzendkosten op 2dehands stelt de
verkoper zelf in), de laatste versie zonder deze wijziging.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

import backend.api.jobs as J  # noqa: E402
import backend.services.instellingen as I  # noqa: E402
import backend.services.mp_enrich as M  # noqa: E402
import backend.services.verzending_2dh as V  # noqa: E402
import backend.services.verzending_2dh_ronde as RO  # noqa: E402

VOOR = "a602e666"   # vast nummer: HEAD vergelijkt zichzelf na de commit
EGBERT = {"modus": "regel", "woorden": ["patch"], "brief_onder": 495}


def _laad(pad, naam):
    spec = importlib.util.spec_from_file_location(naam, ROOT / pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _laad("tests/test_2dehands_volgt_de_marktplaats_rubriek.py", "rubriekproef_v")
NUMMER = "1475716652"


def _oud(pad, naam, bevat, mist):
    return R._oude_module(pad, VOOR, naam, moet_bevatten=bevat, moet_missen=mist)


# ── de keuze per verkoper ─────────────────────────────────────────────────────
def test_de_keuze_wordt_bewaard_en_de_oude_code_gooide_hem_weg():
    K = I.VERZENDING_2DH_MODUS
    assert I._schoon({K: "alles"})[K] == "alles"
    assert I._schoon({K: " Standaard "})[K] == "standaard"
    assert I._schoon({K: "verzonnen"})[K] == "standaard"
    assert I._schoon({**I._schoon({K: "alles"}), "relist_dagen": 30})[K] == "alles", \
        "een andere instelling opslaan gooit de keuze niet weg"
    oud = _oud("backend/services/instellingen.py", "oude_instellingen_modus",
               ("verzending_2dh_brief_onder",), ("verzending_2dh_modus",))
    assert K not in oud._schoon({K: "alles"}), "vroeger bestond deze keuze niet"


def test_wie_nog_niet_koos_houdt_wat_hij_had():
    """Egberts rij van vandaag heeft geen keuze, wel een grens en een woord."""
    K = I.VERZENDING_2DH_MODUS
    egbert = {I.VERZENDING_2DH_WOORDEN: ["patch"], I.VERZENDING_2DH_BRIEF_ONDER: 495}
    assert I._schoon(egbert)[K] == "regel"
    assert I._schoon({I.VERZENDING_2DH_WOORDEN: ["patch"]})[K] == "regel"
    assert I._schoon(None)[K] == "standaard"
    assert I.modus_van({"woorden": ["patch"], "brief_onder": 0}) == "regel", \
        "een regel zonder keuze (de oude vorm) blijft werken"


@pytest.mark.parametrize("modus,titel,cents,verwacht", [
    ("standaard", "Rugpatch", 225, False),     # grens en woord blijven bewaard, maar gelden niet
    ("regel", "Rugpatch", 495, True),
    ("regel", "Koelkast magneet", 225, True),
    ("regel", "Mok", 695, False),
    ("alles", "Mok", 695, True),
    ("alles", "Slipmat groot", 1395, True),     # ook boven Bpost
    ("alles", "Mok", 0, False),                 # geen bedrag is geen bedrag
    ("alles", "Mok", None, False),
])
def test_welk_bedrag_mee_gaat(modus, titel, cents, verwacht):
    regel = {**EGBERT, "modus": modus}
    assert I.neemt_bedrag_over(regel, titel, cents) is verwacht


# ── de beslissing ─────────────────────────────────────────────────────────────
ZELF = {"soort": "zelf"}


@pytest.mark.parametrize("regel,eigen,titel,mp,verwacht", [
    (EGBERT, None, "Rugpatch", {"soort": "zelf", "cents": 495}, {**ZELF, "cents": 495}),
    (EGBERT, None, "Mok", {"soort": "zelf", "cents": 695}, V.STANDAARD),
    (EGBERT, None, "Mok", None, None),                          # storing: weten we niet
    (EGBERT, None, "Mok", {"soort": "platform"}, V.STANDAARD),
    (EGBERT, V.BPOST, "Rugpatch", {"soort": "zelf", "cents": 495}, V.STANDAARD),
    (EGBERT, 300, "Bandana", None, {**ZELF, "cents": 300}),      # eigen keuze: Marktplaats niet nodig
    (EGBERT, 0, "Bandana", None, {**ZELF, "cents": 0}),
    ({**EGBERT, "modus": "standaard"}, None, "Rugpatch", None, V.STANDAARD),
    ({**EGBERT, "modus": "alles"}, None, "Mok", {"soort": "zelf", "cents": 1395}, {**ZELF, "cents": 1395}),
])
def test_doel(regel, eigen, titel, mp, verwacht):
    assert V.doel(regel, eigen, titel, mp) == verwacht


def test_keuze_van_buiten_wordt_begrensd():
    assert V.keuze_uit_invoer("volg") is None
    assert V.keuze_uit_invoer("bpost") == "bpost"
    assert V.keuze_uit_invoer(295) == 295
    assert V.keuze_uit_invoer("295") == 295
    for fout in (-1, 10000, "abc", None, True, 2.5e9):
        with pytest.raises(ValueError):
            V.keuze_uit_invoer(fout)


# ── de uitgifte van een nieuw zoekertje ──────────────────────────────────────
class _DBMetEigen(R._DB):
    def __init__(self, *a, eigen=None, eigen_fout=False, **k):
        super().__init__(*a, **k)
        self.eigen, self.eigen_fout = eigen or {}, eigen_fout

    def antwoord(self, v):
        if v.tabel == "platform_credentials" and v.f.get("platform") == V.RIJ_EIGEN:
            if self.eigen_fout:
                raise RuntimeError("database weg")
            return [{"extra_data": {"artikelen": self.eigen}}]
        return super().antwoord(v)


def _uitgifte(monkeypatch, titel, mp, regel, eigen=None, module=J, op_mp=True, **kw):
    J._VERZENDING_STORING.clear()
    vragen = []

    async def verzending(nummer, verkoper=None):
        vragen.append(nummer)
        return mp
    monkeypatch.setattr(M, "verzending_van_advertentie", verzending)
    monkeypatch.setattr(I, "verzending_2dh_regel", lambda user_id, db=None: regel)
    job = R._echte_opdracht()
    job["payload"] = {**job["payload"], "title": titel}
    db = _DBMetEigen([job], op_marktplaats={job["item_id"]: NUMMER} if op_mp else {},
                     eigen={job["item_id"]: eigen} if eigen is not None else {}, **kw)
    module._zet_verzending_van_marktplaats(db, R.USER, job)
    return job["payload"].get("verzending"), vragen


def _oude_jobs():
    return _oud("backend/api/jobs.py", "oude_jobs_keuze",
                ("verzending_2dh_regel",), ("eigen_keuzes",))


def test_alles_neemt_ook_een_pakketbedrag_mee_en_vroeger_niet(monkeypatch):
    regel = {"modus": "alles", "woorden": [], "brief_onder": 0}
    nu, vragen = _uitgifte(monkeypatch, "Slipmat groot", {"soort": "zelf", "cents": 1395}, regel)
    assert nu == {"soort": "zelf", "cents": 1395} and vragen == [NUMMER]
    # De oude code met de oude instellingen: de keuze bestond niet, de rij had
    # dus geen grens en geen woord, en dat was Bpost.
    oud_I = _oud("backend/services/instellingen.py", "oude_instellingen_alles",
                 ("verzending_2dh_brief_onder",), ("verzending_2dh_modus",))
    s = oud_I._schoon({"verzending_2dh_modus": "alles"})
    oude_regel = {"woorden": s["verzending_2dh_woorden"], "brief_onder": s["verzending_2dh_brief_onder"]}
    monkeypatch.setitem(sys.modules, "backend.services.instellingen", oud_I)
    oud, _ = _uitgifte(monkeypatch, "Slipmat groot", {"soort": "zelf", "cents": 1395},
                       oude_regel, module=_oude_jobs())
    assert oud == {"soort": "standaard"}


def test_eigen_bedrag_voor_een_artikel_zonder_marktplaats(monkeypatch):
    """Een bandana die hij als brief verstuurt, of iets uit een Vinted-import."""
    nu, vragen = _uitgifte(monkeypatch, "Bandana", None, EGBERT, eigen=225, op_mp=False)
    assert nu == {"soort": "zelf", "cents": 225}
    assert vragen == [], "een eigen keuze heeft Marktplaats niet nodig"
    oud, _ = _uitgifte(monkeypatch, "Bandana", None, EGBERT, eigen=225, op_mp=False,
                       module=_oude_jobs())
    assert oud == {"soort": "onbekend"}, "vroeger: niet op Marktplaats, dus Bpost"


def test_eigen_bpost_gaat_voor_de_regel(monkeypatch):
    nu, vragen = _uitgifte(monkeypatch, "Rugpatch", {"soort": "zelf", "cents": 495}, EGBERT,
                           eigen="bpost")
    assert nu == {"soort": "standaard"} and vragen == []
    oud, _ = _uitgifte(monkeypatch, "Rugpatch", {"soort": "zelf", "cents": 495}, EGBERT,
                       eigen="bpost", module=_oude_jobs())
    assert oud == {"soort": "zelf", "cents": 495}


def test_eigen_keuzes_niet_te_lezen_legt_niets_vast(monkeypatch):
    nu, vragen = _uitgifte(monkeypatch, "Rugpatch", {"soort": "zelf", "cents": 495}, EGBERT,
                           eigen_fout=True)
    assert nu is None and vragen == [], "een storing is geen antwoord"


def test_standaard_vraagt_marktplaats_niets(monkeypatch):
    nu, vragen = _uitgifte(monkeypatch, "Rugpatch", {"soort": "zelf", "cents": 495},
                           {**EGBERT, "modus": "standaard"})
    assert nu == {"soort": "standaard"} and vragen == []


# ── de ronde over wat al online staat ─────────────────────────────────────────
class _Q:
    def __init__(self, db, t):
        self.db, self.t, self.f, self.sel, self.ins, self.ups = db, t, {}, "", None, None

    def select(self, x, *a, **k):
        self.sel = x
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def in_(self, k, v):
        self.f[k] = list(v)
        return self

    @property
    def not_(self):
        return self

    def is_(self, *_a):
        return self

    def __getattr__(self, _n):
        return lambda *_a, **_k: self

    def insert(self, rij):
        self.ins = rij
        return self

    def upsert(self, rij, **_k):
        self.ups = rij
        return self

    def execute(self):
        return type("R", (), {"data": self.db.doe(self)})()


class _Wereld:
    """Database, Marktplaats en 2dehands in één, voor een of meer verkopers."""

    def __init__(self):
        self.rijen, self.listings, self.jobs, self.items = {}, [], [], {}
        self.mp, self.dh, self.mp_vragen, self.dh_vragen, self.lijsten = {}, {}, [], [], 0

    def artikel(self, user, item, titel, mp=None, dh="platform", mp_nummer=True):
        self.items[item] = (user, titel)
        self.listings.append({"item_id": item, "platform": "2dehands",
                              "platform_listing_id": f"m{abs(hash(item)) % 10**9}",
                              "platform_listing_url": None, "status": "active"})
        if mp_nummer:
            self.listings.append({"item_id": item, "platform": "marktplaats",
                                  "platform_listing_id": f"mp-{item}", "status": "active"})
        self.mp[f"mp-{item}"] = mp
        self.dh[self.listings[-2 if mp_nummer else -1]["platform_listing_id"]] = \
            {"soort": dh} if isinstance(dh, str) and dh not in ("weg",) else dh

    def table(self, t):
        return _Q(self, t)

    def doe(self, q):
        f = q.f
        if q.t == "platform_credentials":
            if q.ups is not None:
                self.rijen[(q.ups["user_id"], q.ups["platform"])] = json.loads(json.dumps(q.ups["extra_data"]))
                return []
            rijen = [(u, p, d) for (u, p), d in self.rijen.items()
                     if p == f.get("platform") and f.get("user_id", u) == u
                     and f.get("extra_data->>status", d.get("status")) == d.get("status")]
            if q.sel.startswith("gestart:"):
                return [{"gestart": d.get("gestart_op"), "eigenaar": d.get("eigenaar"),
                         "lease": d.get("lease_tot"), "status": d.get("status")} for _, _, d in rijen]
            return [{"user_id": u, "extra_data": json.loads(json.dumps(d))} for u, _, d in rijen]
        if q.t == "listings":
            if "items.user_id" in f and "item_id" not in f:
                self.lijsten += 1
            uit = []
            for li in self.listings:
                user, titel = self.items[li["item_id"]]
                plat = f.get("platform")
                if (f.get("items.user_id", user) != user or f.get("status", li["status"]) != li["status"]
                        or f.get("item_id", li["item_id"]) != li["item_id"]
                        or (isinstance(plat, list) and li["platform"] not in plat)
                        or (isinstance(plat, str) and li["platform"] != plat)):
                    continue
                uit.append({**li, "id": li["item_id"] + li["platform"],
                            "items": {"title": titel, "user_id": user}})
            return uit
        if q.t == "jobs":
            if q.ins is not None:
                self.jobs.append(json.loads(json.dumps(q.ins)))
                return [q.ins]
            return [{"id": i} for i, j in enumerate(self.jobs)
                    if j["user_id"] == f.get("user_id") and j["item_id"] == f.get("item_id")
                    and j["status"] in f.get("status", [j["status"]])]
        if q.t == "items":
            return [{"id": i} for i, (u, _) in self.items.items() if u == f.get("user_id")]
        return []

    async def lees_mp(self, nummer, user_id):
        self.mp_vragen.append(nummer)
        antwoord = self.mp.get(nummer)
        return antwoord() if callable(antwoord) else antwoord

    async def lees_dh(self, lid):
        self.dh_vragen.append(lid)
        return self.dh.get(lid)


@pytest.fixture
def wereld(monkeypatch):
    w = _Wereld()
    for mod in (RO, V):
        monkeypatch.setattr(mod, "fetch_all", lambda bouw, order_by="id", page_size=500: bouw().execute().data)
        monkeypatch.setattr(mod, "get_db", lambda: w)
    for naam in ("_RONDES", "_LIJST", "_EIGEN_CACHE", "_GESCHREVEN"):
        getattr(RO, naam).clear()
    monkeypatch.setattr(RO, "_GELADEN", [0.0])
    monkeypatch.setattr(RO, "_MP_RUST_TOT", [0.0])
    monkeypatch.setattr(RO, "MP_RUST_NA_BLOKKADE", 0)
    monkeypatch.setattr(RO, "LADEN_ELKE", 0)
    monkeypatch.setattr(RO, "WACHT_VOOR_HERKANSING", RO.timedelta(seconds=0))
    monkeypatch.setattr(I, "verzending_2dh_regel", lambda user_id, db=None: dict(EGBERT))
    return w


def _draai(w, keer=500):
    for _ in range(keer):
        asyncio.run(RO.tik(w, w.lees_mp, w.lees_dh))
        if not any(st.get("status") == "loopt" for st in RO._RONDES.values()):
            return
    raise AssertionError("de ronde werd niet klaar")


def _stand(w, user):
    return w.rijen[(user, RO.RIJ_RONDE)]


def test_ronde_zet_alleen_klaar_wat_anders_moet(wereld):
    w, u = wereld, "egbert"
    w.artikel(u, "a", "Rugpatch", {"soort": "zelf", "cents": 495}, dh="platform")
    w.artikel(u, "b", "Koelkast magneet", {"soort": "zelf", "cents": 225}, dh={"soort": "zelf", "cents": 225})
    w.artikel(u, "c", "Mok", {"soort": "zelf", "cents": 695})
    w.artikel(u, "d", "Plectrum", {"soort": "zelf", "cents": 295}, dh="geen")
    w.artikel(u, "e", "Sleutelhanger", mp_nummer=False)
    w.artikel(u, "f", "Rugpatch groot", {"soort": "zelf", "cents": 495})
    w.jobs.append({"user_id": u, "item_id": "f", "platform": "2dehands",
                   "action": "content_refresh", "status": "pending"})
    w.artikel(u, "g", "Bandana", mp_nummer=False)
    w.rijen[(u, V.RIJ_EIGEN)] = {"artikelen": {"g": 300}}
    RO.start(u, db=w)
    _draai(w)
    st = _stand(w, u)
    assert st["status"] == "klaar" and st["aantal"] == 7 and st["bekeken"] == 7
    assert st["tel"] == {"aangepast": 2, "onderweg": 1, "al_goed": 1, "bpost": 1,
                         "niet_op_mp": 1, "ophalen": 1, "weg": 0}
    nieuw = {j["item_id"]: j["payload"]["verzending"] for j in w.jobs if "payload" in j}
    assert nieuw == {"a": {"soort": "zelf", "cents": 495}, "g": {"soort": "zelf", "cents": 300}}
    assert all(j["payload"]["_verzending_bijwerken"] for j in w.jobs if "payload" in j)
    assert "mp-g" not in w.mp_vragen and "mp-f" not in w.mp_vragen


def test_een_blokkade_is_geen_antwoord_en_krijgt_drie_kansen(wereld):
    w, u = wereld, "egbert"
    antwoorden = iter([None, None, {"soort": "zelf", "cents": 295}])
    w.artikel(u, "a", "Plectrum", lambda: next(antwoorden))
    w.artikel(u, "b", "Magneet", None)                      # blijft 403 geven
    RO.start(u, db=w)
    _draai(w)
    st = _stand(w, u)
    assert st["tel"]["aangepast"] == 1 and st["tel"]["bpost"] == 0
    assert st["niet_gelezen_ids"] == ["b"] and st["blokkades"] == 5
    assert w.mp_vragen.count("mp-b") == RO.MAX_POGINGEN
    assert [j["item_id"] for j in w.jobs] == ["a"]
    assert RO.openbaar(st)["niet_gelezen"] == 1
    # "Try again" doet alleen die ene.
    w.mp["mp-b"] = {"soort": "zelf", "cents": 225}
    RO.start(u, opnieuw_niet_gelezen=True, db=w)
    _draai(w)
    assert _stand(w, u)["tel"]["aangepast"] == 1 and _stand(w, u)["aantal"] == 1
    assert [j["item_id"] for j in w.jobs] == ["a", "b"]


def test_blokkades_achter_elkaar_wachten_steeds_langer(wereld, monkeypatch):
    """Gemeten 27-09-2026: eerst 1 op de 18 geweigerd, een kwartier later bijna
    de helft. Een vaste halve minuut verbrandde elke keer een kans."""
    w, u = wereld, "egbert"
    monkeypatch.setattr(RO, "MP_RUST_NA_BLOKKADE", 30)
    monkeypatch.setattr(RO, "_MP_OP_RIJ", [0])
    monkeypatch.setattr(RO.time, "monotonic", lambda: 1000.0)
    for i in range(7):
        w.artikel(u, f"b{i}", "Magneet", None)
    w.artikel(u, "goed", "Magneet", {"soort": "zelf", "cents": 225})
    st = RO._nieuwe_stand(dict(EGBERT), False, [])
    rust = []
    for i in range(6):
        asyncio.run(RO.bekijk(w, u, st, f"b{i}", w.lees_mp, w.lees_dh))
        rust.append(RO._MP_RUST_TOT[0] - 1000.0)
    assert rust == [30, 60, 120, 240, 300, 300]
    asyncio.run(RO.bekijk(w, u, st, "goed", w.lees_mp, w.lees_dh))
    asyncio.run(RO.bekijk(w, u, st, "b6", w.lees_mp, w.lees_dh))
    assert RO._MP_RUST_TOT[0] - 1000.0 == 30, "na een geslaagde pagina weer een halve minuut"
    assert st["opnieuw"] == [f"b{i}" for i in range(7)] and st["blokkades"] == 7


def test_afbreken_en_hervatten_geeft_geen_dubbele_bijwerkingen(wereld, monkeypatch):
    w, u = wereld, "egbert"
    for i in range(30):
        w.artikel(u, f"i{i:02}", "Rugpatch", {"soort": "zelf", "cents": 495})
    RO.start(u, db=w)
    for _ in range(12):
        asyncio.run(RO.tik(w, w.lees_mp, w.lees_dh))
    halverwege = len(w.jobs)
    assert 0 < halverwege < 30
    # Deploy: het proces is weg, zijn geheugen ook. De lease verloopt.
    for naam in ("_RONDES", "_LIJST", "_GESCHREVEN"):
        getattr(RO, naam).clear()
    monkeypatch.setattr(RO, "_EIGENAAR", "nieuw-proces")
    _stand(w, u)["lease_tot"] = "2000-01-01T00:00:00+00:00"
    _draai(w)
    st = _stand(w, u)
    items = [j["item_id"] for j in w.jobs]
    assert sorted(items) == sorted(set(items)) and len(items) == 30, "elk zoekertje precies één keer"
    assert st["tel"]["aangepast"] == 30 and st["tel"]["onderweg"] == 0
    assert st["bekeken"] == 30


def test_een_ander_proces_neemt_een_lopende_ronde_niet_over(wereld, monkeypatch):
    w, u = wereld, "egbert"
    w.artikel(u, "a", "Rugpatch", {"soort": "zelf", "cents": 495})
    RO.start(u, db=w)
    RO._RONDES.clear()
    monkeypatch.setattr(RO, "_EIGENAAR", "tweede-proces")
    asyncio.run(RO.tik(w, w.lees_mp, w.lees_dh))
    assert w.jobs == [] and u not in RO._RONDES, "de lease van het eerste proces geldt nog"


def test_twee_verkopers_om_de_beurt_en_de_lijst_een_keer(wereld):
    w = wereld
    for u in ("egbert", "jaap"):
        for i in range(5):
            w.artikel(u, f"{u}{i}", "Rugpatch", {"soort": "zelf", "cents": 495})
        RO.start(u, db=w)
    _draai(w)
    assert all(_stand(w, u)["tel"]["aangepast"] == 5 for u in ("egbert", "jaap"))
    assert w.lijsten == 2, "de lijst per verkoper wordt één keer opgehaald, niet per tik"


def test_tweede_klik_andere_keuze_en_stoppen(wereld, monkeypatch):
    w, u = wereld, "egbert"
    w.artikel(u, "a", "Rugpatch", {"soort": "zelf", "cents": 495})
    eerste = RO.start(u, db=w)["gestart_op"]
    assert RO.start(u, db=w)["gestart_op"] == eerste, "een tweede klik toont de lopende ronde"
    anders = {**EGBERT, "modus": "alles"}
    assert RO.stop_als_verouderd(u, anders, db=w) is True
    assert _stand(w, u)["status"] == "gestopt"
    monkeypatch.setattr(I, "verzending_2dh_regel", lambda user_id, db=None: anders)
    assert RO.start(u, db=w)["instelling"] == anders
    assert RO.stop_als_verouderd(u, anders, db=w) is False


def test_eigen_keuze_tijdens_een_ronde_komt_erachteraan(wereld):
    w, u = wereld, "egbert"
    w.artikel(u, "a", "Rugpatch", {"soort": "zelf", "cents": 495})
    w.artikel(u, "g", "Bandana", mp_nummer=False)
    RO.start(u, db=w)
    uit = V.zet_eigen_keuze(u, ["g", "van-een-ander"], 250, db=w)
    assert uit == {"gezet": 1, "ids": ["g"]}, "alleen eigen artikelen"
    RO.start(u, item_ids=["g"], db=w)
    _draai(w)
    st = _stand(w, u)
    assert {j["item_id"]: j["payload"]["verzending"]["cents"] for j in w.jobs} == {"a": 495, "g": 250}
    assert st["aantal"] == 3 and st["bekeken"] == 3, "g telt twee keer: in de lijst en als eigen keuze"


def test_eigen_keuze_volg_haalt_hem_weg(wereld):
    w, u = wereld, "egbert"
    w.artikel(u, "g", "Bandana", mp_nummer=False)
    V.zet_eigen_keuze(u, ["g"], "bpost", db=w)
    assert V.eigen_keuzes(u, w) == {"g": "bpost"}
    V.zet_eigen_keuze(u, ["g"], "volg", db=w)
    assert V.eigen_keuzes(u, w) == {}
