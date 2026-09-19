"""De driedagenveger mag niemand de schuld geven die er niets aan kon doen.

19-09-2026. Werk dat langer dan drie dagen blijft staan wordt op fout gezet met
een uitleg. Die uitleg was één vaste zin: "Zet je computer met de
Omnivaleur-extensie aan en probeer het opnieuw."

Bij drie klanten was die zin aantoonbaar onwaar:

- Een klant op proef had op 15-09 in één keer 232 advertenties klaargezet. De
  wachtrij doet er ongeveer één per minuut en loopt alleen door zolang zijn
  browser openstaat. Op 18-09 om 19:04 was zijn extensie nog gezien en had hij
  die dag 55 advertenties geplaatst; om 23:18 kregen twaalf wachtende opdrachten
  te horen dat zijn computer uit had gestaan.
- Twee andere klanten hadden geen lopend abonnement meer (opgezegd op 08-09,
  proef verlopen op 13-09). De server weigert dan werk uit te geven. Hun
  computer aanzetten had niets veranderd.

De uitleg wordt nu afgeleid uit twee dingen die we echt meten: het abonnement en
extension_heartbeat.last_seen.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.services import relist


class _Antwoord:
    def __init__(self, data):
        self.data = data


class _Tabel:
    def __init__(self, db, naam):
        self._db, self._naam, self._filters = db, naam, {}

    def select(self, *_a, **_k):
        return self

    def eq(self, kolom, waarde):
        self._filters[kolom] = waarde
        return self

    def limit(self, _n):
        return self

    def execute(self):
        self._db.gelezen.append(self._naam)
        rijen = self._db.tabellen.get(self._naam, [])
        uit = [r for r in rijen
               if all(r.get(k) == v for k, v in self._filters.items())]
        return _Antwoord(uit)


class _DB:
    def __init__(self, **tabellen):
        self.tabellen = tabellen
        self.gelezen: list[str] = []

    def table(self, naam):
        return _Tabel(self, naam)


NU = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)
KLANT = "klant-1"


def _db(sub_status=None, laatst_gezien=None, loopt_tot="2026-10-19T00:00:00+00:00"):
    """loopt_tot is de echte scheidslijn: een proef of periode die al voorbij is
    geeft geen toegang meer, wat er ook in de statuskolom staat."""
    subs = ([{"user_id": KLANT, "status": sub_status, "plan": "pro",
              "current_period_end": loopt_tot,
              "trial_ends_at": loopt_tot}]
            if sub_status else [])
    hb = ([{"user_id": KLANT, "last_seen": laatst_gezien}] if laatst_gezien else [])
    return _DB(subscriptions=subs, extension_heartbeat=hb)


def test_extensie_draaide_gewoon_dan_is_de_wachtrij_de_reden():
    """Dit is het geval dat fout ging: de computer stond aan."""
    uitleg = relist._waarom_bleef_het_staan(
        _db("trialing", (NU - timedelta(hours=13)).isoformat()), KLANT, NU)
    assert "Aan jou lag het niet" in uitleg
    assert "Zet je computer" not in uitleg
    assert "18-09-2026 om 19:00" in uitleg, uitleg
    assert "drie dagen" in uitleg


def test_zonder_lopend_abonnement_noemen_we_het_abonnement():
    uitleg = relist._waarom_bleef_het_staan(
        _db("canceled", (NU - timedelta(days=9)).isoformat(),
            loopt_tot="2026-09-08T13:47:24+00:00"), KLANT, NU)
    assert "abonnement" in uitleg
    assert "Zet je computer" not in uitleg


def test_een_verlopen_proef_telt_net_zo_goed_als_opgezegd():
    uitleg = relist._waarom_bleef_het_staan(
        _db("trial_expired", (NU - timedelta(days=23)).isoformat(),
            loopt_tot="2026-09-13T07:26:17+00:00"), KLANT, NU)
    assert "abonnement" in uitleg


def test_lang_niet_gezien_noemt_de_datum_erbij():
    """De oude tekst blijft, maar met het bewijs erbij in plaats van een verwijt
    zonder onderbouwing."""
    uitleg = relist._waarom_bleef_het_staan(
        _db("trialing", (NU - timedelta(days=9)).isoformat()), KLANT, NU)
    assert "Zet je computer" in uitleg
    assert "10-09-2026" in uitleg


def test_zonder_enig_spoor_blijft_de_oude_tekst_staan():
    """Weten we niets, dan raden we niets: de oude tekst vraagt niets onmogelijks."""
    uitleg = relist._waarom_bleef_het_staan(_DB(), KLANT, NU)
    assert uitleg.endswith(
        "Zet je computer met de Omnivaleur-extensie aan en probeer het opnieuw.")


def test_een_herplaatsing_zegt_er_ook_bij_dat_de_oude_advertentie_nog_staat():
    uitleg = relist._verlopen_herplaatsing(
        _db("trialing", (NU - timedelta(hours=2)).isoformat()), KLANT, NU)
    assert "nooit weggehaald" in uitleg
    assert "Aan jou lag het niet" in uitleg


@pytest.mark.parametrize("wat", ["subscriptions", "extension_heartbeat"])
def test_een_kapotte_opzoeking_breekt_de_opruimronde_niet(wat, monkeypatch):
    db = _db("trialing", NU.isoformat())
    echt = db.table

    def stuk(naam):
        if naam == wat:
            raise RuntimeError("supabase hikt")
        return echt(naam)

    db.table = stuk
    uitleg = relist._waarom_bleef_het_staan(db, KLANT, NU)
    assert uitleg.startswith("Deze opdracht stond meer dan 3 dagen")
