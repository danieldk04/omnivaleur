"""De server geeft geen verwijt door dat hij zelf kan weerleggen.

WAT ER GEBEURDE (Egbert Brouwer, papas-plectrums, 06-09-2026)

Twee metingen op precies dezelfde URL, in dezelfde browser, dezelfde minuut:

    21:07:35  vanuit een tabblad OP www.2dehands.be    HTTP 200
    21:07:48  vanuit de service worker van de extensie  HTTP 401
    21:11:22  weer vanuit het tabblad                   HTTP 200
    21:11:27  weer vanuit de service worker             HTTP 401

HTTP 200 op /my-account/sell/api/listings krijg je alleen met een geldige
sessie; dat is precies de aanname waarop de inlogcontrole van de extensie is
gebouwd. Hij was dus ingelogd. Toch is op grond van die 401 zijn hele wachtrij
van 346 opdrachten teruggenomen met de mededeling dat hij niet was ingelogd. Dat
was de derde keer dat deze verkoper dat verwijt kreeg terwijl hij gelijk had.

De extensie is gerepareerd (zij vraagt het nu na vanuit een tabblad op de site
zelf), maar een nieuwe extensie is er pas na de Web Store; bij hem duurde dat
eerder drie weken. Daarom staat deze rem óók op de server: die weet uit de scans
van dezelfde verkoper of zijn eigen browser wél bij zijn account kon.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402

VERWIJT = ("You are not signed in to 2dehands (2dehands.be) in this browser, so nothing was "
           "published and no tab was opened. We asked 2dehands (2dehands.be) itself and it "
           "refused (HTTP 401).")


def _tijd(uren_geleden: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=uren_geleden)).isoformat()


class _NepDb:
    """Genoeg van de databasebouwer om de scanvraag te beantwoorden."""

    def __init__(self, rijen):
        self._rijen = rijen

    def table(self, _naam):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rijen})()


def _scan(api_status, uren_geleden=0.1):
    return {"result": {"scan_meta": {"api_status": api_status}}, "done_at": _tijd(uren_geleden)}


def test_verwijt_verdwijnt_als_zijn_eigen_browser_er_wel_bij_kon():
    db = _NepDb([_scan(200)])
    uit = api._reden_zonder_vals_verwijt(db, "u", "2dehands", VERWIJT)
    assert "not signed in" not in uit
    assert "fault on our side" in uit
    assert "HTTP 200" in uit


def test_zonder_tegenbewijs_blijft_de_melding_staan():
    db = _NepDb([_scan(401)])
    assert api._reden_zonder_vals_verwijt(db, "u", "2dehands", VERWIJT) == VERWIJT


def test_een_meting_van_vorige_week_telt_niet_meer():
    db = _NepDb([_scan(200, uren_geleden=200)])
    assert api._reden_zonder_vals_verwijt(db, "u", "2dehands", VERWIJT) == VERWIJT


def test_zonder_scans_blijft_de_melding_staan():
    db = _NepDb([])
    assert api._reden_zonder_vals_verwijt(db, "u", "2dehands", VERWIJT) == VERWIJT


def test_een_andere_reden_wordt_nooit_herschreven():
    andere = "The 2dehands (2dehands.be) listing form never opened: the page never reported back."
    db = _NepDb([_scan(200)])
    assert api._reden_zonder_vals_verwijt(db, "u", "2dehands", andere) == andere


def test_een_kapotte_database_houdt_het_stoppen_niet_tegen():
    class Stuk(_NepDb):
        def execute(self):
            raise RuntimeError("PostgREST down")

    assert api._reden_zonder_vals_verwijt(Stuk([]), "u", "2dehands", VERWIJT) == VERWIJT


def test_de_vervangende_tekst_zegt_wat_er_niet_gebeurd_is():
    uit = api._reden_zonder_vals_verwijt(_NepDb([_scan(200)]), "u", "2dehands", VERWIJT)
    assert "Nothing was published" in uit
    # Geen gedachtestreepjes: deze tekst komt zo in het dashboard te staan.
    assert " — " not in uit and " – " not in uit
