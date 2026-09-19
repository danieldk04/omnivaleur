"""De verversrondes zetten geen werk klaar dat toch nooit kan lopen.

19-09-2026. De rondes lopen langs ADVERTENTIES, niet langs klanten, en keken
alleen naar de schakelaar auto_relist. Daardoor stonden er op 17-09 om 21:32
ineens 26 en 8 opdrachten klaar voor twee accounts waarvan het abonnement al weg
was: een opzegging van 08-09 en een proef die op 13-09 afliep. Bij een van de
twee bestond de inlog niet eens meer.

De extensie krijgt op zo'n account een 402 en er gebeurt niets. Bij een
verlenging is dat alleen ruis, maar bij een herplaatsing is het schade: de
advertentie gaat op 'relisting' en er komt dagenlang niets voor terug, tot de
driedagenveger de herplaatsing terugneemt.

Twijfel telt als ja: een ontbrekende abonnementsrij en een database die hikt
mogen niemands herplaatsing tegenhouden.
"""
import pytest

from backend.services import crosslist


class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Tabel:
    def __init__(self, db):
        self._db, self._filters = db, {}

    def select(self, *_a, **_k):
        return self

    def eq(self, kolom, waarde):
        self._filters[kolom] = waarde
        return self

    def limit(self, _n):
        return self

    def execute(self):
        rijen = [r for r in self._db.subs
                 if all(r.get(k) == v for k, v in self._filters.items())]
        return _Antwoord(rijen)


class _DB:
    def __init__(self, subs, stuk=False):
        self.subs, self.stuk = subs, stuk

    def table(self, _naam):
        if self.stuk:
            raise RuntimeError("supabase hikt")
        return _Tabel(self)


def _zet_db(monkeypatch, subs, stuk=False):
    monkeypatch.setattr(crosslist, "get_db", lambda: _DB(subs, stuk))


def test_een_lopende_proef_mag_gewoon_werken(monkeypatch):
    _zet_db(monkeypatch, [{"user_id": "u", "status": "trialing",
                           "trial_ends_at": "2099-01-01T00:00:00+00:00",
                           "current_period_end": "2099-01-01T00:00:00+00:00"}])
    assert crosslist._mag_nog_werken("u") is True


@pytest.mark.parametrize("status,tot", [
    ("canceled", "2026-09-08T13:47:24+00:00"),
    ("trial_expired", "2026-09-13T07:26:17+00:00"),
])
def test_zonder_lopend_abonnement_wordt_er_niets_klaargezet(monkeypatch, status, tot):
    _zet_db(monkeypatch, [{"user_id": "u", "status": status,
                           "trial_ends_at": tot, "current_period_end": tot}])
    assert crosslist._mag_nog_werken("u") is False


def test_een_account_zonder_abonnementsrij_wordt_niet_buitengesloten(monkeypatch):
    """Die rij is er eerder door RLS niet gekomen; iemand daarom stilzetten is
    erger dan er een keer eentje doorlaten."""
    _zet_db(monkeypatch, [])
    assert crosslist._mag_nog_werken("u") is True


def test_een_hik_in_de_database_houdt_niemand_tegen(monkeypatch):
    _zet_db(monkeypatch, [], stuk=True)
    assert crosslist._mag_nog_werken("u") is True


def test_beide_rondes_vragen_het_ook_echt_na():
    """Zonder deze aanroep staat de reparatie er wel maar doet ze niets."""
    from pathlib import Path
    bron = (Path(__file__).resolve().parents[1]
            / "backend/services/crosslist.py").read_text(encoding="utf-8")
    mp = bron.split("async def relist_expiring_marktplaats(")[1] \
             .split("async def ")[0]
    tweedehands = bron.split("async def extend_expiring_2dehands(")[1] \
                      .split("\nasync def ")[0]
    assert "if not mag_werken(eigenaar):" in mp, "Marktplaats-ronde vraagt het niet na"
    assert "if not mag_werken(eigenaar):" in tweedehands, "2dehands-ronde vraagt het niet na"
