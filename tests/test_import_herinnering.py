"""De importherinnering: één seintje voor wie liet scannen maar nooit importeerde.

WAAROM DIT ER IS (29-09-2026, Matthijs)
Zijn scan vond 22 advertenties, hij klikte nooit op "Alles importeren", en zijn
proefweek ging voorbij met nul artikelen. Daniel koos voor één automatische
herinnering na 24 uur. Elke proef hieronder bewaakt één manier waarop die mail
juist schade zou doen: te vroeg, 's nachts, twee keer, of aan wie het al snapt.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as database  # noqa: E402
from backend.services import email as email_mod  # noqa: E402
from backend.services import import_herinnering as mod  # noqa: E402

NU = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)    # 14:00 NL
NACHT = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)  # 03:00 NL


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.op, self.rij = db, tabel, [], "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v)
        return self

    def in_(self, k, v):
        v = list(v)
        self.filters.append(lambda r: r.get(k) in v)
        return self

    def gte(self, k, v):
        self.filters.append(lambda r: str(r.get(k)) >= v)
        return self

    def order(self, k):
        self._order = k
        return self

    def limit(self, _n):
        return self

    def upsert(self, rij, on_conflict=None):
        self.op, self.rij = "upsert", rij
        return self

    def execute(self):
        if self.tabel == "leadgen_opslag" and self.db.opslag_kapot:
            raise RuntimeError("time-out")
        if self.op == "upsert":
            self.db.opslag[self.rij["naam"]] = self.rij["inhoud"]
            return type("A", (), {"data": [self.rij]})()
        if self.tabel == "leadgen_opslag":
            rijen = [{"naam": k, "inhoud": v} for k, v in self.db.opslag.items()]
        else:
            rijen = getattr(self.db, self.tabel)
        rijen = [r for r in rijen if all(f(r) for f in self.filters)]
        if getattr(self, "_order", None):
            rijen = sorted(rijen, key=lambda r: str(r.get(self._order)))
        return type("A", (), {"data": rijen})()


class _Admin:
    class auth:
        class admin:
            @staticmethod
            def get_user_by_id(uid):
                return type("U", (), {"user": type("G", (), {"email": f"{uid}@klant.nl"})()})()


class _DB(_Admin):
    def __init__(self):
        self.opslag, self.opslag_kapot = {}, False
        self.subscriptions = [{"user_id": "matthijs", "status": "trialing", "stripe_subscription_id": None,
                               "trial_ends_at": (NU + timedelta(hours=7)).isoformat(),
                               "created_at": (NU - timedelta(days=7)).isoformat()}]
        self.import_candidates = [{"id": f"c{i}", "user_id": "matthijs", "platform": "marktplaats",
                                   "status": "pending", "created_at": (NU - timedelta(days=7)).isoformat()}
                                  for i in range(22)]

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture
def omgeving(monkeypatch):
    db, verstuurd = _DB(), []
    mod._gemaild_uit_geheugen.clear()
    monkeypatch.setattr(database, "get_db", lambda: db)
    monkeypatch.setattr(database, "get_admin_db", lambda: db)
    monkeypatch.setattr(email_mod, "send_email",
                        lambda subject, body, to=None, reply_to=None: verstuurd.append((to, subject, body)) or db.mail_lukt)
    db.mail_lukt = True
    return db, verstuurd


def _draai(now=NU):
    return asyncio.run(mod.herinner_niet_geimporteerd(now=now))


def test_een_keer_na_een_dag_scannen_zonder_importeren(omgeving):
    db, verstuurd = omgeving
    assert _draai() == 1
    assert verstuurd[0][0] == "matthijs@klant.nl"
    assert "22 advertenties" in verstuurd[0][2] and "Marktplaats" in verstuurd[0][2]
    assert "matthijs" in db.opslag[mod.OPSLAG]

    mod._gemaild_uit_geheugen.clear()     # ook na een herstart van de server niet opnieuw
    assert _draai(NU + timedelta(hours=1)) == 0
    assert len(verstuurd) == 1


def test_niet_voor_de_scan_een_dag_oud_is(omgeving):
    db, verstuurd = omgeving
    for c in db.import_candidates:
        c["created_at"] = (NU - timedelta(hours=20)).isoformat()
    assert _draai() == 0 and not verstuurd


def test_niet_bij_wie_al_iets_importeerde(omgeving):
    db, verstuurd = omgeving
    db.import_candidates[0]["status"] = "imported"
    assert _draai() == 0 and not verstuurd


def test_niet_s_nachts(omgeving):
    _, verstuurd = omgeving
    assert _draai(NACHT) == 0 and not verstuurd


def test_niemand_als_de_opslag_niet_te_lezen_is(omgeving):
    db, verstuurd = omgeving
    db.opslag_kapot = True
    assert _draai() == 0 and not verstuurd


def test_niet_als_proef_en_respijt_voorbij_zijn(omgeving):
    db, verstuurd = omgeving
    db.subscriptions[0]["trial_ends_at"] = (NU - timedelta(days=3)).isoformat()
    assert _draai() == 0 and not verstuurd


def test_niet_voor_oude_accounts(omgeving):
    db, verstuurd = omgeving
    db.subscriptions[0]["created_at"] = (NU - timedelta(days=30)).isoformat()
    assert _draai() == 0 and not verstuurd


def test_mislukte_mail_mag_het_volgende_uur_opnieuw(omgeving):
    db, verstuurd = omgeving
    db.mail_lukt = False
    assert _draai() == 0
    assert "matthijs" not in db.opslag[mod.OPSLAG]
    db.mail_lukt = True
    assert _draai(NU + timedelta(hours=1)) == 1


def test_mail_tekst_twee_talen_een_link_geen_streepjes():
    onderwerp, tekst = mod.herinnering_mail(1, ["marktplaats", "2dehands"])
    assert "1 advertentie van je op Marktplaats en 2dehands, maar die staat" in tekst
    assert "1 of your listings on Marktplaats and 2dehands, but it is" in tekst
    assert tekst.count(mod.IMPORT_LINK) == 2
    assert "Alles importeren" in tekst and "Import all" in tekst
    assert " — " not in tekst + onderwerp and " - " not in tekst
