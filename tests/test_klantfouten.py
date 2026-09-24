"""De wachter: wanneer een klantfout wél en wanneer niet een sessie waard is.

WAAROM DIT ER IS (23-09-2026)
Een fout bij een klant moet vanzelf opgepakt worden, zonder Daniel, maar ook niet
elke tien minuten opnieuw: elke sessie kost abonnement. En de meting draait op
de productiedatabase, die twee keer omviel op `jobs.result` over alle klanten.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL / "scripts"))
import klantfouten as K  # noqa: E402
import dev_starter as S  # noqa: E402

NU = datetime(2026, 9, 23, 20, 0, tzinfo=timezone.utc)


def _t(min_geleden):
    return (NU - timedelta(minutes=min_geleden)).isoformat()


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.kolommen, self.filters = db, tabel, "", {}

    def select(self, k):
        self.kolommen = k
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def in_(self, k, v):
        self.filters[k] = ("in", list(v))
        return self

    def gte(self, k, v):
        self.filters[k] = (">=", v)
        return self

    def lte(self, k, v):
        self.filters[k] = ("<=", v)
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        self.db.vragen.append((self.tabel, self.kolommen, dict(self.filters)))
        rijen = [r for r in self.db.rijen.get(self.tabel, []) if self._past(r)]
        return type("A", (), {"data": rijen})()

    def _past(self, r):
        for k, v in self.filters.items():
            if isinstance(v, tuple):
                op, w = v
                if op == "in" and r.get(k) not in w:
                    return False
                if op == ">=" and not (r.get(k) and r[k] >= w):
                    return False
                if op == "<=" and not (r.get(k) and r[k] <= w):
                    return False
            elif r.get(k) != v:
                return False
        return True


class NepDb:
    def __init__(self, jobs=(), hartslag=()):
        self.rijen = {"jobs": list(jobs), "extension_heartbeat": list(hartslag)}
        self.vragen = []

    def table(self, naam):
        return _Vraag(self, naam)


def _fout(id_, uid="aaaaaaaa-1", fout="Delete control not found on item 123",
          platform="vinted", action="delete", min_geleden=20):
    return {"id": id_, "user_id": uid, "platform": platform, "action": action,
            "status": "error", "done_at": _t(min_geleden), "fout": fout}


@pytest.fixture
def kast(monkeypatch):
    inhoud: dict = {}
    monkeypatch.setattr(K.A.L, "_db_lees", lambda naam, standaard: inhoud.get(naam, standaard))
    monkeypatch.setattr(K.A.L, "_db_schrijf",
                        lambda naam, waarde: inhoud.__setitem__(naam, waarde) or True)
    monkeypatch.setattr(K, "_nu", lambda: NU)
    return inhoud


def _klantfouten(sig):
    return sig


# ── zien ───────────────────────────────────────────────────────────────────
def test_een_klantfout_wordt_een_ronde_die_de_starter_oppakt(kast):
    db = NepDb([_fout(1), _fout(2, fout="Delete control not found on item 456")])
    sig = _klantfouten(K.signalen({}, db, NU))
    assert len(sig) == 1
    ronde = next(iter(sig.values()))
    assert len(ronde["sleutels"]) == 1          # zelfde fout, ander nummer: één soort
    assert S._te_doen(sig, {}) and "Delete control" in S.opdracht(*next(iter(sig.items())))


def test_result_wordt_alleen_per_klant_gelezen(kast):
    db = NepDb([_fout(1, uid="a"), _fout(2, uid="b")])
    K.meet(db, NU)
    for tabel, kolommen, filters in db.vragen:
        if "result" in kolommen:
            assert "user_id" in filters and filters.get("id", ("",))[0] == "in"


def test_werk_dat_vastzit_terwijl_chrome_aanstaat(kast):
    wacht = [{"id": i, "user_id": "f8c0cce9-x", "platform": "vinted", "status": "pending",
              "created_at": _t(80)} for i in range(3)]
    db = NepDb(wacht, [{"user_id": "f8c0cce9-x", "last_seen": _t(2)}])
    assert "vast-f8c0cce9" in K.meet(db, NU)
    # Staat Chrome uit, dan is het wachten van de klant zelf.
    db = NepDb(wacht, [{"user_id": "f8c0cce9-x", "last_seen": _t(120)}])
    assert "vast-f8c0cce9" not in K.meet(db, NU)


def test_een_kapotte_meting_start_niets(kast):
    class Kapot:
        def table(self, _):
            raise RuntimeError("PGRST002")
    assert not _klantfouten(K.signalen({}, Kapot(), NU))


# ── niet eindeloos opnieuw ────────────────────────────────────────────────
def test_klant_eigen_oorzaak_blijft_een_week_stil(kast):
    db = NepDb([_fout(1)])
    sleutel = next(iter(K.meet(db, NU)))
    kast[K.OORDEEL_SLEUTEL] = {sleutel: {"oordeel": "klant", "wanneer": _t(60)}}
    db = NepDb([_fout(1), _fout(2, min_geleden=5)])
    assert not _klantfouten(K.signalen({}, db, NU))


def test_een_gerepareerde_fout_die_terugkomt_gaat_weer_open(kast):
    db = NepDb([_fout(1, min_geleden=300)])
    sleutel = next(iter(K.meet(db, NU)))
    kast[K.OORDEEL_SLEUTEL] = {sleutel: {"oordeel": "gerepareerd", "wanneer": _t(290)}}
    assert not _klantfouten(K.signalen({}, db, NU))
    db = NepDb([_fout(1, min_geleden=300), _fout(2, min_geleden=10)])
    assert _klantfouten(K.signalen({}, db, NU))


def test_een_sessie_die_niet_terugmeldt_houdt_hem_een_dag_stil(kast):
    db = NepDb([_fout(1, min_geleden=120), _fout(2, min_geleden=5)])
    sleutel = next(iter(K.meet(db, NU)))
    staat = {"klantfouten-x": {"status": "afgerond", "sleutels": [sleutel],
                               "gestart": _t(100), "afgerond_op": _t(60)}}
    assert not _klantfouten(K.signalen(staat, db, NU))


def test_een_sessie_die_er_nog_op_zit_houdt_hem_stil(kast):
    db = NepDb([_fout(1, min_geleden=5)])
    sleutel = next(iter(K.meet(db, NU)))
    staat = {"klantfouten-x": {"status": "gestart", "sleutels": [sleutel], "gestart": _t(10)}}
    assert not _klantfouten(K.signalen(staat, db, NU))


def test_na_een_volle_limiet_wordt_dezelfde_ronde_opnieuw_geprobeerd(kast):
    db = NepDb([_fout(1, min_geleden=100)])
    naam = next(iter(_klantfouten(K.signalen({}, db, NU))))
    sleutel = next(iter(K.meet(db, NU)))
    staat = {naam: {"status": "mislukt", "mislukt": "limiet", "sleutels": [sleutel],
                    "gestart": _t(90)}}
    sig = _klantfouten(K.signalen(staat, db, NU))
    assert naam in sig and S._te_doen(sig, staat)


def test_terugmelden_legt_het_oordeel_vast(kast):
    assert K.oordeel_vastleggen("fout-x", "klant", "Chrome stond uit")
    assert kast[K.OORDEEL_SLEUTEL]["fout-x"]["oordeel"] == "klant"
    assert not K.oordeel_vastleggen("fout-x", "misschien", "")


def test_een_verlopen_inlog_wordt_herkend(tmp_path):
    log = tmp_path / "s.log"
    log.write_text("Failed to authenticate: OAuth session expired and could not be refreshed\n")
    assert "/login" in S._waarom_niets_geworden(str(log))


def test_een_dode_sessie_geeft_zijn_fouten_in_dezelfde_ronde_vrij(kast, monkeypatch, tmp_path):
    """Na de herstart van 24-09 bleef het een ronde stil: eerst gekeken, toen opgeruimd."""
    db = NepDb([_fout(1, min_geleden=30)])
    sleutel = next(iter(K.meet(db, NU)))
    log = tmp_path / "s.log"
    log.write_text("# sessie\n")
    kast[S.STAAT_SLEUTEL] = {"klantfouten-oud": {"status": "gestart", "pid": 1, "log": str(log),
                                                  "sleutels": [sleutel], "gestart": _t(600)}}
    monkeypatch.setattr(S, "_leeft", lambda pid: False)
    monkeypatch.setattr(S, "_werkmap_schoon", lambda: (True, ""))
    monkeypatch.setattr(S, "_iemand_aan_het_werk", lambda staat: "")
    echte = K.signalen
    monkeypatch.setattr(S.K, "signalen", lambda staat: echte(staat, db, NU))
    gestart = []
    monkeypatch.setattr(S, "_start", lambda k, s, st: gestart.append(k) or True)
    S.ronde()
    assert gestart and gestart[0].startswith("klantfouten-")



def test_een_geplande_herplaatsing_zit_niet_vast(kast):
    # 24-09-2026, f8c0cce9: een herplaatsing aangemaakt om 13:03 maar gepland
    # voor 17:03 UTC. De uitdeler geeft hem pas dan uit; toch meldde de wachter
    # om 15:15 "werk zit vast". Wachten telt pas vanaf het geplande moment.
    hartslag = [{"user_id": "f8c0cce9-x", "last_seen": _t(2)}]
    gepland = {"id": 1, "user_id": "f8c0cce9-x", "platform": "2dehands",
               "status": "pending", "created_at": _t(130), "scheduled_for": _t(-110)}
    assert "vast-f8c0cce9" not in K.meet(NepDb([gepland], hartslag), NU)
    # Al 80 minuten aan de beurt en nog niet opgepakt: dat zit wel vast.
    te_laat = dict(gepland, scheduled_for=_t(80))
    assert "vast-f8c0cce9" in K.meet(NepDb([te_laat], hartslag), NU)
