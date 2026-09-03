"""De offline-melding: zeggen dat de computer uit staat, in plaats van wachten
tot de klant denkt dat het product stuk is.

WAAROM DIT ER IS (03-09-2026, Toon van dejuistetoon)
Toon zette 50 advertenties klaar en meldde uren later "er gebeurt eigenlijk
niets". Gemeten op dat moment: zijn extensie had zich 196 minuten niet gemeld en
er stonden 62 opdrachten te wachten. Er was niets stuk, zijn computer stond uit,
en niets vertelde hem dat.

Elke regel hieronder bewaakt één manier waarop deze mail juist schade zou doen:
midden in de nacht, bij een verse klik, bij wie allang weg is, of twee keer
achter elkaar.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import extension_offline as mod  # noqa: E402

NU = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)   # 14:00 NL, binnen het venster
NACHT = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)  # 03:00 NL


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters = {}, {}
        self.op, self.velden, self.kolommen = None, None, ""

    def select(self, kolommen="", *_a, **_k):
        self.op, self.kolommen = "select", kolommen; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def in_(self, k, v):
        self.in_filters[k] = list(v); return self

    def limit(self, _n):
        return self

    def execute(self):
        bron = getattr(self.db, self.tabel)
        if self.tabel == "extension_heartbeat" and "offline_mail_sent_at" in self.kolommen \
                and not self.db.kolom_bestaat:
            raise RuntimeError('column extension_heartbeat.offline_mail_sent_at does not exist')
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.in_filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
            self.db.updates.append((self.tabel, dict(self.velden)))
        return type("R", (), {"data": [dict(r) for r in rijen]})()


class _DB:
    def __init__(self, jobs, heartbeats, subs, kolom_bestaat=True):
        self.jobs, self.extension_heartbeat, self.subscriptions = jobs, heartbeats, subs
        self.kolom_bestaat, self.updates = kolom_bestaat, []

    def table(self, naam):
        return _Q(self, naam)


def _opzet(monkeypatch, db, adres="toon@example.com"):
    verzonden = []
    monkeypatch.setattr(mod, "_kolom_ontbreekt", False)
    monkeypatch.setattr(mod, "_gemaild_uit_geheugen", {})
    monkeypatch.setattr("backend.database.get_db", lambda: db)
    gebruiker = type("U", (), {"user": type("X", (), {"email": adres})()})()
    monkeypatch.setattr("backend.database.get_admin_db",
                        lambda: type("A", (), {"auth": type("B", (), {
                            "admin": type("C", (), {"get_user_by_id": staticmethod(lambda _u: gebruiker)})()
                        })()})())
    monkeypatch.setattr("backend.services.email.send_email",
                        lambda **kw: (verzonden.append(kw), True)[1])
    return verzonden


def _jobs(aantal, uren_oud, uid="toon"):
    gemaakt = (NU - timedelta(hours=uren_oud)).isoformat()
    return [{"user_id": uid, "created_at": gemaakt, "action": "create", "status": "pending"}
            for _ in range(aantal)]


def _hart(uren_stil, uid="toon", gemaild=None):
    rij = {"user_id": uid, "last_seen": (NU - timedelta(hours=uren_stil)).isoformat()}
    rij["offline_mail_sent_at"] = gemaild
    return rij


def _abo(uid="toon", status="trialing"):
    return {"user_id": uid, "status": status}


def test_toon_krijgt_de_mail_die_hij_toen_niet_kreeg(monkeypatch):
    """De echte situatie van 03-09-2026: 62 opdrachten, ruim drie uur stil."""
    db = _DB(_jobs(62, 5), [_hart(3.3)], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 1
    assert "62 listings" in verzonden[0]["subject"]
    assert "3 hours" in verzonden[0]["body"]
    assert verzonden[0]["to"] == "toon@example.com"


def test_computer_aan_geen_mail(monkeypatch):
    db = _DB(_jobs(62, 5), [_hart(0.01)], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0
    assert verzonden == []


def test_nooit_midden_in_de_nacht(monkeypatch):
    """De nachtelijke herplaatsronde zet bij iedereen rond 02:30 werk klaar.
    Zonder dit venster kreeg elke klant met een uitgezette computer om drie uur
    's nachts een mail."""
    db = _DB(_jobs(62, 5), [_hart(6)], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NACHT)) == 0
    assert verzonden == []


def test_verse_klik_levert_geen_mail_op(monkeypatch):
    """Wie net op publiceren klikte terwijl zijn computer toevallig even stil is,
    krijgt geen paniekmail."""
    db = _DB(_jobs(5, 0.2), [_hart(4)], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0


def test_hoogstens_een_mail_per_dag(monkeypatch):
    db = _DB(_jobs(62, 5), [_hart(4, gemaild=(NU - timedelta(hours=2)).isoformat())], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0
    assert verzonden == []


def test_na_een_dag_mag_het_weer(monkeypatch):
    db = _DB(_jobs(62, 30), [_hart(26, gemaild=(NU - timedelta(hours=25)).isoformat())], [_abo()])
    _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 1


def test_geen_mail_zonder_lopend_abonnement(monkeypatch):
    """Wie is opgezegd of verlopen is geen klant meer en krijgt geen porren."""
    db = _DB(_jobs(62, 5), [_hart(4)], [_abo(status="canceled")])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0


def test_zonder_hartslag_geen_mail(monkeypatch):
    """Wie de extensie nooit gebruikte, krijgt geen mail over een computer die
    volgens ons offline is: die melding zou nergens op slaan."""
    db = _DB(_jobs(62, 5), [], [_abo()])
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0


def test_vinkje_wordt_gezet(monkeypatch):
    db = _DB(_jobs(62, 5), [_hart(4)], [_abo()])
    _opzet(monkeypatch, db)
    asyncio.run(mod.waarschuw_offline_extensies(NU))
    assert any(t == "extension_heartbeat" and "offline_mail_sent_at" in v for t, v in db.updates)


def test_werkt_ook_als_de_kolom_nog_ontbreekt(monkeypatch):
    """Staat de markeerkolom nog niet in Supabase, dan valt hij terug op het
    geheugen van de server in plaats van stilletjes niets te doen. Zonder dat
    vangnet bleef de hele melding onzichtbaar tot iemand handmatig een kolom
    toevoegde, en dat is hier eerder misgegaan."""
    db = _DB(_jobs(62, 5), [_hart(4)], [_abo()], kolom_bestaat=False)
    verzonden = _opzet(monkeypatch, db)
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 1
    assert asyncio.run(mod.waarschuw_offline_extensies(NU)) == 0  # niet twee keer
    assert len(verzonden) == 1


def test_mail_is_kort_en_zonder_opmaak(monkeypatch):
    """Huisregel: klantmail gaat als platte tekst de deur uit, dus geen sterretjes,
    en nooit een los streepje als leesteken."""
    onderwerp, tekst = mod.offline_mail(62, 4)
    assert "*" not in tekst and "—" not in tekst and " - " not in tekst
    assert "—" not in onderwerp
    assert len(tekst.split()) < 200


def test_lange_stilte_staat_in_dagen():
    """Gemeten op echte gegevens: een stille extensie stond 591 uur stil. Dat als
    "591 hours" in een klantmail zetten leest als een computerfout."""
    _, tekst = mod.offline_mail(15, 591)
    assert "591 hours" not in tekst
    assert "24 days" in tekst
    _, kort = mod.offline_mail(3, 5)
    assert "5 hours" in kort
