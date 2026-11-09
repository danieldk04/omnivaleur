"""Rekenregels van de korting per betalende vriend (besluit Daniel 09-11-2026)."""
from datetime import datetime, timezone

from backend.services.referral_korting import (
    bedrag_per_vriend_cents, korting_cents, telt_mee, trede, volgende_trede,
)

VOOR = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
NA = datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)


def _k(**kw):
    basis = dict(vriend_plan="pro", vriend_betaald_cents=1999, vriend_eerste_betaling_op=VOOR,
                 eigen_maandprijs_cents=1999, huidig_tegoed_cents=0)
    basis.update(kw)
    return korting_cents(**basis)


def test_pro_vriend_voor_einddatum_geeft_tien_euro():
    # Pro betaalt 19,99 incl. btw: de helft is 9,99, dus net onder de 10 euro.
    assert _k() == 999
    assert _k(vriend_betaald_cents=2500) == 1000


def test_na_einddatum_vijf_euro():
    assert _k(vriend_eerste_betaling_op=NA, vriend_betaald_cents=2500) == 500


def test_vriend_die_voor_einddatum_begon_houdt_tien_euro_ook_later():
    # De datum die telt is die van zijn EERSTE betaling, niet van de factuur.
    assert bedrag_per_vriend_cents(VOOR) == 1000


def test_light_vriend_telt_niet():
    assert _k(vriend_plan="light", vriend_betaald_cents=825) == 0
    assert not telt_mee("light")
    assert telt_mee("Pro") and telt_mee("plus") and telt_mee("ultra")


def test_onbekend_plan_of_geen_betaling_geeft_niets():
    assert _k(vriend_plan=None) == 0
    assert _k(vriend_plan="") == 0
    assert _k(vriend_betaald_cents=0) == 0
    assert _k(vriend_betaald_cents=-5) == 0


def test_nooit_meer_dan_helft_van_wat_vriend_betaalde():
    for netto in (1, 99, 250, 1000, 1652, 1999, 4900):
        assert _k(vriend_betaald_cents=netto) <= netto // 2


def test_zelfverwijzing_loont_nooit():
    # Wie zelf een tweede account betaalt, betaalt altijd meer dan hij terugkrijgt.
    for netto in (500, 825, 1652, 4049):
        assert _k(vriend_betaald_cents=netto) < netto


def test_nooit_meer_dan_eigen_rekening_en_geen_tegoed_opstapelen():
    assert _k(vriend_betaald_cents=4000, eigen_maandprijs_cents=1999, huidig_tegoed_cents=1500) == 499
    assert _k(vriend_betaald_cents=4000, eigen_maandprijs_cents=1999, huidig_tegoed_cents=1999) == 0
    assert _k(vriend_betaald_cents=4000, eigen_maandprijs_cents=1999, huidig_tegoed_cents=5000) == 0


def test_onder_een_euro_boekt_niets():
    assert _k(vriend_betaald_cents=4000, eigen_maandprijs_cents=1999, huidig_tegoed_cents=1950) == 0
    assert _k(vriend_betaald_cents=150) == 0


def test_datum_zonder_tijdzone_wordt_als_utc_gelezen():
    assert bedrag_per_vriend_cents(datetime(2026, 12, 31, 12, 0)) == 1000
    assert bedrag_per_vriend_cents(datetime(2027, 1, 1, 0, 0)) == 500
    assert bedrag_per_vriend_cents(None) == 500


def test_trap():
    assert [trede(n) for n in (0, 1, 2, 3, 4, 5, 9)] == [0, 1, 1, 3, 3, 5, 5]
    assert volgende_trede(0) == (1, 1)
    assert volgende_trede(2) == (3, 1)
    assert volgende_trede(4) == (5, 1)
    assert volgende_trede(5) is None
    assert trede(-3) == 0
