"""De meting achter de ochtendroutine voor nieuwe klanten.

WAAROM DIT ER IS (29-09-2026)
De routine beslist op deze uitkomst wie aandacht krijgt. Een lege of verkeerde
meting mag nooit lijken op "alles loopt", en de meting draait op de
productiedatabase, die twee keer omviel op `jobs.result` over een bereik.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL / "scripts"))
import nieuwe_klanten as N  # noqa: E402

NU = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)


class _Antwoord:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.kolommen, self.filters, self.telling = db, tabel, "", {}, False

    def select(self, k, count=None):
        self.kolommen, self.telling = k, bool(count)
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def gte(self, k, v):
        self.filters[k] = (">=", v)
        return self

    def in_(self, k, v):
        self.filters[k] = ("in", list(v))
        return self

    def order(self, *_):
        return self

    def limit(self, *_):
        return self

    def range(self, a, b):
        self.filters["_range"] = (a, b)
        return self

    def execute(self):
        self.db.vragen.append(self)
        rijen = self.db.tabellen.get(self.tabel, [])
        if self.telling:
            return _Antwoord([], count=0)
        if "_range" in self.filters:
            a, b = self.filters["_range"]
            return _Antwoord(rijen[a:b + 1])
        if isinstance(self.filters.get("id"), tuple):
            ids = self.filters["id"][1]
            return _Antwoord([r for r in rijen if r["id"] in ids])
        return _Antwoord(rijen)


class _DB:
    def __init__(self, **tabellen):
        self.tabellen, self.vragen = tabellen, []

    def table(self, naam):
        return _Vraag(self, naam)


def _t(uur_geleden):
    return (NU - timedelta(hours=uur_geleden)).isoformat()


def _account(uur_geleden=20):
    return {"email": "klant@voorbeeld.nl", "aangemeld": NU - timedelta(hours=uur_geleden),
            "laatste_login": NU - timedelta(hours=1)}


@pytest.fixture(autouse=True)
def _vaste_indeling(monkeypatch):
    # De echte indeling komt uit het beheerdashboard; hier alleen wat de proef nodig heeft.
    monkeypatch.setattr(N, "categoriegroep",
                        lambda c: "Kleding" if c and "heren" in c else "Sieraden" if c else "Onbekend")
    monkeypatch.setattr(N, "nieuwste_extensie", lambda: "1.0.358")
    monkeypatch.setattr(N, "winkelversie", lambda: "1.0.355")


def test_nieuwe_klanten_binnen_venster_zonder_eigen_accounts():
    alle = {"a": {"email": "x@y.nl", "aangemeld": NU - timedelta(days=2)},
            "b": {"email": "oud@y.nl", "aangemeld": NU - timedelta(days=9)},
            "c": {"email": "daniel@omnivaleur.com", "aangemeld": NU - timedelta(days=1)},
            "d": {"email": "z@y.nl", "aangemeld": NU - timedelta(hours=3)}}
    assert N.nieuwe(alle, 7, NU) == ["d", "a"]


def test_nul_accounts_is_een_kapotte_meting():
    class _Admin:
        class auth:
            class admin:
                @staticmethod
                def list_users(page, per_page):
                    return []
    with pytest.raises(RuntimeError):
        N.accounts(_Admin)


def test_profiel_leest_result_alleen_per_id_van_foutrijen():
    jobs = [{"id": f"j{i}", "platform": "marktplaats", "action": "create", "status": "error",
             "created_at": _t(5), "done_at": _t(4), "scheduled_for": None,
             "fout": "Maat is verplicht"} for i in range(3)]
    jobs.append({"id": "ok", "platform": "vinted", "action": "create", "status": "done",
                 "created_at": _t(6), "done_at": _t(5), "scheduled_for": None})
    db = _DB(jobs=jobs, items=[{"id": "i1", "category": "heren truien", "brand": "Nike",
                                "size": "Overige", "price": 20, "created_at": _t(10)}])
    p = N.profiel(db, "u1", _account(), NU)

    for v in db.vragen:
        if v.tabel == "jobs" and "result" in v.kolommen:
            assert v.filters.get("id", ("",))[0] == "in", "result gelezen zonder id-filter"
            assert len(v.filters["id"][1]) <= 20
    assert p["fouten"][0]["aantal"] == 3
    assert p["eerste_gelukt"]["vinted"] == NU - timedelta(hours=5)
    assert any(s.startswith("MAAT_OVERIGE") for s in p["signalen"])
    assert any(s.startswith("FOUTEN") for s in p["signalen"])


def _profiel(**over):
    p = {"aangemeld": NU - timedelta(hours=20), "afgekapt": [], "fouten": [], "vast": [],
         "vast_oudste": None, "opdrachten": [], "eerste_gelukt": {},
         "extensie": {"versie": "1.0.358", "laatst": NU - timedelta(minutes=5)},
         "abonnement": {"status": "trialing", "proef_tot": NU + timedelta(days=5), "kaart": False},
         "voorraad": {"aantal": 150, "zonder_prijs": 0, "zonder_foto": 0, "maat_overige": 0}}
    p.update(over)
    return p


def test_alles_goed_geeft_geen_signalen():
    assert N.signalen(_profiel(opdrachten=[("marktplaats create:done", 3)],
                               eerste_gelukt={"marktplaats": NU}), NU) == []


def test_zonder_extensie_en_zonder_voorraad():
    s = N.signalen(_profiel(extensie={"versie": None, "laatst": None},
                            voorraad={"aantal": 0, "zonder_prijs": 0, "zonder_foto": 0,
                                      "maat_overige": 0}), NU)
    assert [x.split(":")[0] for x in s] == ["GEEN_EXTENSIE", "NIETS_INGELEZEN"]


def test_stille_extensie_en_oude_versie_en_proef_bijna_om():
    s = N.signalen(_profiel(extensie={"versie": "1.0.349", "laatst": NU - timedelta(days=5)},
                            abonnement={"status": "trialing", "proef_tot": NU + timedelta(hours=14),
                                        "kaart": False}), NU)
    soorten = [x.split(":")[0] for x in s]
    assert "NIET_ACTIEF" in soorten and "OUDE_EXTENSIE" in soorten and "PROEF_BIJNA_OM" in soorten


def test_plaatsopdrachten_zonder_enig_succes():
    s = N.signalen(_profiel(opdrachten=[("marktplaats create:error", 4)]), NU)
    assert any(x.startswith("NOG_NIETS_GELUKT") for x in s)


def test_versies_vergelijken_als_getallen():
    assert N._versie("1.0.99") < N._versie("1.0.358")


def test_gezien_telt_rondes_en_weigert_bij_onleesbare_opslag(monkeypatch):
    opslag = {}
    monkeypatch.setattr(N.A, "_bereikbaar", lambda: "")
    monkeypatch.setattr(N.A, "_lees", lambda k, d: opslag.get(k, d))
    monkeypatch.setattr(N.A, "_schrijf", lambda k, v: opslag.__setitem__(k, v) or True)
    assert N.gezien("u1", "eerste ronde")
    assert N.gezien("u1", "tweede ronde")
    assert opslag[N.STAAT_SLEUTEL]["u1"]["rondes"] == 2
    assert opslag[N.STAAT_SLEUTEL]["u1"]["samenvatting"] == "tweede ronde"

    monkeypatch.setattr(N.A, "_bereikbaar", lambda: "time-out")
    assert not N.gezien("u1", "derde ronde")
    assert opslag[N.STAAT_SLEUTEL]["u1"]["rondes"] == 2


def test_tekst_toont_vorige_ronde():
    p = _profiel(user_id="u1", email="k@v.nl", laatste_login=None,
                 voorraad={"aantal": 1, "eerste": None, "groepen": [], "rubrieken": [], "merken": [],
                           "prijs": None, "zonder_prijs": 0, "zonder_foto": 0, "maat_overige": 0},
                 koppelingen=[], voorkeuren_ingevuld=False, advertenties=[], signalen=[])
    p["import"] = []
    uit = N.tekst(p, {"rondes": 1, "laatst": "2026-09-28T05:00", "samenvatting": "mail klaargezet"}, NU)
    assert "volgen, ronde 2" in uit and "mail klaargezet" in uit


def test_klant_op_winkelversie_wacht_op_google_niet_op_zichzelf():
    s = N.signalen(_profiel(extensie={"versie": "1.0.355", "laatst": NU},
                            opdrachten=[("marktplaats create:done", 3)],
                            eerste_gelukt={"marktplaats": NU}), NU)
    assert [x.split(":")[0] for x in s] == ["WACHT_OP_WEB_STORE"]


def test_koude_mail_met_antwoord_en_onleesbaar(monkeypatch):
    opslag = {"mail_state": {"vagif@x.nl": {"verstuurd": [{"op": "2026-09-20T14:54:41", "beurt": "mail1"}],
                                            "daniel_antwoordde": 1790145301.0}},
              "mail_reacties": [{"op": "2026-09-23T04:53:32", "adres": "Vagif@X.nl", "soort": "warm",
                                 "tekst": "Ja hoor, wat kost het?"}]}
    monkeypatch.setattr(N.A, "_lees", lambda k, d: opslag.get(k, d))
    k = N.koude_mail(["vagif@x.nl", "nieuw@x.nl"])
    assert k["vagif@x.nl"]["verstuurd"][0][0] == "mail1"
    assert k["vagif@x.nl"]["antwoorden"][0][1] == "warm"
    assert k["vagif@x.nl"]["daniel_antwoordde"] is not None
    assert k["nieuw@x.nl"]["verstuurd"] == []

    monkeypatch.setattr(N.A, "_lees", lambda k, d: d)
    assert isinstance(N.koude_mail(["vagif@x.nl"]), str)


def test_postvak_leest_wachtwoord_uit_sleutelhanger(monkeypatch):
    monkeypatch.delenv("MAIL_PASS", raising=False)
    monkeypatch.setattr(N.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="uit-keychain\n"))
    ingelogd = []

    class NepImap:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, gebruiker, wachtwoord): ingelogd.append(wachtwoord)
        def select(self, *a, **k): return ("OK", [b"0"])
        def search(self, *a): return ("OK", [b""])

    monkeypatch.setattr(N.imaplib, "IMAP4_SSL", NepImap)
    assert N.postvak(["a@b.nl"]) == {"a@b.nl": []}
    assert ingelogd == ["uit-keychain"]


def test_postvak_zonder_wachtwoord_zegt_niet_gelezen(monkeypatch):
    monkeypatch.delenv("MAIL_PASS", raising=False)
    monkeypatch.setattr(N.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=44, stdout=""))
    uit = N.postvak(["a@b.nl"])
    assert isinstance(uit, str) and "niet gelezen" in uit
    regels = N._contactregels({"koude_mail": "koude-mailgeschiedenis niet te lezen", "postvak": uit,
                               "vermeldingen": []})
    assert "niet gelezen" in regels[1] and "geen mail" not in regels[1]
    assert "niet te lezen" in regels[0] and "nooit koud gemaild" not in regels[0]


def test_vermeldingen_vindt_kopje_met_adres_en_geheugen(monkeypatch, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "team-notes.md").write_text(
        "## 28-09: iets anders\ntekst\n## 29-09: Vagif (vagif@x.nl) voor het gesprek van vanmiddag\nstand\n")
    (tmp_path / "docs" / "kennisbank.md").write_text("# Les\nbij 1ba42900 ging het mis\n")
    geheugen = tmp_path / "mem"
    geheugen.mkdir()
    (geheugen / "vinted-kleur.md").write_text("51 van 86 bij vagif@x.nl")
    monkeypatch.setattr(N, "REPO", tmp_path)
    monkeypatch.setattr(N, "GEHEUGEN", geheugen)
    v = N.vermeldingen("vagif@x.nl", "1ba42900-77ec")
    assert v == ["team-notes: 29-09: Vagif (vagif@x.nl) voor het gesprek van vanmiddag",
                 "kennisbank: Les", "geheugen: vinted-kleur"]
    monkeypatch.setattr(N, "GEHEUGEN", tmp_path / "bestaat-niet")
    assert N.vermeldingen("vagif@x.nl", "1ba42900")[-1] == "geheugen: niet op deze machine"
