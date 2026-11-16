"""De mail na een uur stilstand (Daniel, 16-11-2026).

Elke proef bewaakt één manier waarop deze mail schade zou doen: te vroeg, 's nachts,
twee keer, of aan wie al een artikel heeft of betaalt.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.database as database  # noqa: E402
from backend.services import email as email_mod  # noqa: E402
from backend.services import stil_na_aanmelding as mod  # noqa: E402

NU = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)  # 13:00 NL
NACHT = datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc)


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.op, self.rij = db, tabel, [], "select", None

    def select(self, *_a, **_k): return self
    def limit(self, _n): return self

    def eq(self, k, v):
        self.filters.append(lambda r: r.get(k) == v); return self

    def in_(self, k, v):
        v = list(v); self.filters.append(lambda r: r.get(k) in v); return self

    def gte(self, k, v):
        self.filters.append(lambda r: str(r.get(k)) >= v); return self

    def upsert(self, rij, on_conflict=None):
        self.op, self.rij = "upsert", rij; return self

    def execute(self):
        if self.op == "upsert":
            self.db.opslag[self.rij["naam"]] = self.rij["inhoud"]
            return type("A", (), {"data": [self.rij]})()
        if self.tabel == "leadgen_opslag":
            rijen = [{"naam": k, "inhoud": v} for k, v in self.db.opslag.items()]
        else:
            rijen = getattr(self.db, self.tabel)
        return type("A", (), {"data": [r for r in rijen if all(f(r) for f in self.filters)]})()


class _DB:
    class auth:
        class admin:
            @staticmethod
            def get_user_by_id(uid):
                return type("U", (), {"user": type("G", (), {"email": f"{uid}@klant.nl"})()})()

    def __init__(self):
        self.opslag, self.items, self.jobs, self.extension_heartbeat, self.mail_lukt = {}, [], [], [], True
        self.subscriptions = [{"user_id": "nieuw", "status": "trialing", "stripe_subscription_id": None,
                               "trial_ends_at": (NU + timedelta(days=6)).isoformat(),
                               "created_at": (NU - timedelta(hours=2)).isoformat()}]

    def table(self, naam): return _Q(self, naam)


@pytest.fixture
def omgeving(monkeypatch):
    db, verstuurd = _DB(), []
    mod._gemaild_uit_geheugen.clear()
    monkeypatch.setattr(database, "get_db", lambda: db)
    monkeypatch.setattr(database, "get_admin_db", lambda: db)
    monkeypatch.setattr(email_mod, "send_email",
                        lambda subject, body, to=None, reply_to=None, **_k: verstuurd.append((to, subject, body)) or db.mail_lukt)
    return db, verstuurd


def _draai(now=NU):
    return asyncio.run(mod.mail_wie_stil_zit(now=now))


def test_stille_klant_krijgt_na_een_uur_een_mail_over_installeren(omgeving):
    db, mails = omgeving
    assert _draai() == 1
    assert mails[0][0] == "nieuw@klant.nl" and "Add to Chrome" in mails[0][2]


def test_extensie_gezien_dan_gaat_het_over_het_eerste_artikel(omgeving):
    db, mails = omgeving
    db.extension_heartbeat.append({"user_id": "nieuw"})
    _draai()
    assert "Plaats nu" in mails[0][2] and "Add to Chrome" not in mails[0][2]


def test_binnen_het_uur_nog_niet(omgeving):
    db, mails = omgeving
    db.subscriptions[0]["created_at"] = (NU - timedelta(minutes=30)).isoformat()
    assert _draai() == 0


def test_nachts_niet(omgeving):
    assert _draai(NACHT) == 0


def test_maar_een_keer(omgeving):
    db, mails = omgeving
    _draai(); _draai(NU + timedelta(hours=1))
    assert len(mails) == 1


@pytest.mark.parametrize("wijzig", [
    lambda db: db.items.append({"id": "i", "user_id": "nieuw"}),
    lambda db: db.jobs.append({"id": "j", "user_id": "nieuw", "status": "done"}),
    lambda db: db.subscriptions[0].update(stripe_subscription_id="sub_1"),
    lambda db: db.subscriptions[0].update(created_at=(NU - timedelta(hours=60)).isoformat()),
    lambda db: db.subscriptions[0].update(trial_ends_at=(NU - timedelta(days=3)).isoformat()),
])
def test_wie_al_iets_heeft_of_betaalt_krijgt_niets(omgeving, wijzig):
    db, mails = omgeving
    wijzig(db)
    assert _draai() == 0 and not mails


def test_mislukt_versturen_geeft_een_nieuwe_kans(omgeving):
    db, mails = omgeving
    db.mail_lukt = False
    assert _draai() == 0
    db.mail_lukt = True
    assert _draai(NU + timedelta(hours=1)) == 1


def test_opslag_kapot_dan_niemand(omgeving, monkeypatch):
    db, mails = omgeving
    monkeypatch.setattr(mod, "_lees_opslag", lambda _db: None)
    assert _draai() == 0 and not mails


def test_tekst_zonder_streepjes_of_opmaak():
    for gezien in (True, False):
        t = mod.stil_mail(gezien)[1]
        assert " - " not in t and "—" not in t and "*" not in t
