"""De wachtrij staat stil omdat de computer slaapt, en dat hoort er te staan.

WAAROM DIT ER IS (12-09-2026, De Juiste Toon)
"Deze pc staat de hele dag aan en toch zie ik nog steeds 50 stuks staan."
Gemeten op zijn eigen rij: tussen 07:51 en 11:12 UTC werd er geen enkele
opdracht opgepakt terwijl er honderd klaarstonden, en daarna nog eens 54
minuten niet. In diezelfde uren liepen bij twee andere verkopers 46 en 24
opdrachten per uur door, dus de server deelde gewoon uit.

Het gemeten tempo gooit zulke gaten er bewust uit, anders verziekt één nacht de
snelheid. Daardoor beloofde de balk "deze 50 duren een uur" terwijl het een hele
dag werd. Die stille uren tellen we nu apart, zodat het scherm kan zeggen wat er
werkelijk gebeurde in plaats van een looptijd te beloven die niemand haalt.

De valkuil zit in het bewijs dat er écht werk lag te wachten: kijken naar de
opdracht die ná het gat werd opgepakt is fout, want een verse klik gaat vóór de
nachtronde. Op Toons echte rij gaf die kortere weg 0 stille uren waar er ruim
vier waren.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402

NU = datetime.now(timezone.utc)


def t(uren_geleden: float) -> str:
    return (NU - timedelta(hours=uren_geleden)).isoformat()


class _Q:
    def __init__(self, rijen):
        self.rijen = rijen

    def select(self, *_a, **_k): return self
    def eq(self, *_a, **_k): return self
    def in_(self, *_a, **_k): return self
    def gte(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a, **_k): return self

    def execute(self):
        return type("R", (), {"data": list(self.rijen)})()


class _DB:
    def __init__(self, rijen): self.rijen = rijen
    def table(self, _naam): return _Q(self.rijen)


def opdracht(gemaakt, opgepakt=None, klaar=None, status="done"):
    return {"created_at": t(gemaakt),
            "claimed_at": t(opgepakt) if opgepakt is not None else None,
            "done_at": t(klaar) if klaar is not None else None,
            "status": status}


def test_slapende_computer_telt_als_stille_uren():
    # Werk klaargezet om 10 uur geleden. Twee opdrachten liepen meteen, daarna
    # drie uur niets, en pas daarna ging de rest weer lopen.
    rijen = [
        opdracht(10, 9.9, 9.85),
        opdracht(10, 9.8, 9.75),
        opdracht(10, 6.8, 6.75),   # pas na de stilstand aan de beurt
        opdracht(10, 6.7, 6.65),
    ]
    stil = J._stille_uren(_DB(rijen), "u")
    assert stil["idle_gaps"] == 1
    assert 2.9 * 3600 < stil["idle_seconds"] < 3.1 * 3600, stil


def test_rustige_rij_telt_niet_mee():
    # Zelfde gat, maar er lag niets te wachten: het latere werk werd pas ná de
    # stilte klaargezet. Dat is geen stilstand, dat is een rustige middag.
    rijen = [
        opdracht(10, 9.9, 9.85),
        opdracht(10, 9.8, 9.75),
        opdracht(6.9, 6.8, 6.75),
        opdracht(6.9, 6.7, 6.65),
    ]
    stil = J._stille_uren(_DB(rijen), "u")
    assert stil["idle_seconds"] == 0, stil
    assert stil["idle_gaps"] == 0


def test_stilstand_die_nu_nog_doorloopt_krijgt_een_begintijd():
    rijen = [
        opdracht(9, 8.9, 8.85),
        opdracht(9, 8.8, 8.75),
        opdracht(9, None, None, status="pending"),   # wacht nog steeds
    ]
    stil = J._stille_uren(_DB(rijen), "u")
    assert stil["idle_since"], stil
    assert stil["idle_seconds"] > 8 * 3600, stil


def test_verse_klik_na_de_stilstand_verbergt_de_stilstand_niet():
    # De opdracht die als eerste door het gat heen gaat is een verse klik van de
    # verkoper zelf. Wie alleen daarnaar kijkt ziet nul stille uren, terwijl de
    # nachtronde van tien uur geleden al die tijd stond te wachten.
    rijen = [
        opdracht(10, 9.9, 9.85),
        opdracht(10, None, None, status="pending"),  # nachtronde, wacht nog
        opdracht(6.85, 6.8, 6.75),                   # verse klik, meteen gedaan
        opdracht(6.85, 6.7, 6.65),
    ]
    stil = J._stille_uren(_DB(rijen), "u")
    assert stil["idle_gaps"] >= 1, stil
    assert stil["idle_seconds"] > 3 * 3600, stil
