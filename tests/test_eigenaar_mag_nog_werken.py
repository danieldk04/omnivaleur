"""De eigenaar mag ook in de nachtrondes werken (16-11-2026).

Daniels eigen account staat in `subscriptions` op 'trial_expired'. Aan de
voordeur (`check_access`) mag de eigenaar altijd door, dus zijn extensie kreeg
gewoon werk. Maar `_mag_nog_werken`, de poort van de verleng- en herplaatsrondes,
keek alleen naar de abonnementsrij en zei nee. Gevolg, gemeten op zijn account:
nul 2dehands-verlengingen sinds 17-09 en nul automatische Marktplaats-
herplaatsingen, terwijl de schakelaar aan stond.

Op de oude code faalt `test_eigenaar_met_verlopen_proef_mag_werken`.

Draaien:  python3 -m pytest tests/test_eigenaar_mag_nog_werken.py -q
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import database                           # noqa: E402
from backend.config import settings                    # noqa: E402
from backend.services import crosslist as cl           # noqa: E402

VERLOPEN = {"user_id": "u1", "status": "trial_expired",
            "trial_ends_at": "2026-08-05T15:11:11+00:00",
            "stripe_subscription_id": None, "current_period_end": None}
LOPEND = {"user_id": "u1", "status": "active",
          "current_period_end": "2099-01-01T00:00:00+00:00",
          "stripe_subscription_id": "sub_x", "trial_ends_at": None}


class _Vraag:
    def __init__(self, rijen):
        self.rijen = rijen

    def select(self, *_a, **_k): return self
    def eq(self, *_a, **_k): return self
    def limit(self, *_a, **_k): return self
    def execute(self): return SimpleNamespace(data=self.rijen)


class _Db:
    def __init__(self, rijen):
        self.rijen = rijen

    def table(self, _naam): return _Vraag(self.rijen)


class _Admin:
    """Doet alsof auth.admin.get_user_by_id; telt hoe vaak het gevraagd is."""
    def __init__(self, email=None, stuk=False):
        self.email, self.stuk, self.gevraagd = email, stuk, 0
        self.auth = SimpleNamespace(admin=self)

    def get_user_by_id(self, _uid):
        self.gevraagd += 1
        if self.stuk:
            raise RuntimeError("User not allowed")
        return SimpleNamespace(user=SimpleNamespace(email=self.email))


def _zet(monkeypatch, sub, admin):
    monkeypatch.setattr(cl, "get_db", lambda: _Db([sub] if sub else []))
    monkeypatch.setattr(database, "get_admin_db", lambda: admin)
    monkeypatch.setattr(settings, "owner_email", "baas@voorbeeld.nl")


def test_eigenaar_met_verlopen_proef_mag_werken(monkeypatch):
    _zet(monkeypatch, VERLOPEN, _Admin("Baas@voorbeeld.nl"))
    assert cl._mag_nog_werken("u1") is True


def test_klant_met_verlopen_proef_mag_niet_werken(monkeypatch):
    _zet(monkeypatch, VERLOPEN, _Admin("klant@voorbeeld.nl"))
    assert cl._mag_nog_werken("u1") is False


def test_lopend_abonnement_vraagt_geen_adres_op(monkeypatch):
    admin = _Admin("klant@voorbeeld.nl")
    _zet(monkeypatch, LOPEND, admin)
    assert cl._mag_nog_werken("u1") is True
    assert admin.gevraagd == 0


def test_adres_niet_op_te_zoeken_blijft_nee(monkeypatch):
    _zet(monkeypatch, VERLOPEN, _Admin(stuk=True))
    assert cl._mag_nog_werken("u1") is False
