"""Een net geplaatste Vinted-advertentie is nooit "weg uit de kast".

WAAROM DIT ER IS (09-10-2026, Janneke 31d28378). Haar "Winterjas Noppies maat
98" stond in de balk "Is dit item verkocht?" met "staat niet meer in je
Vinted-kast", online for 0 dagen, terwijl hij gewoon op Vinted stond. Een scan
leest de kast en meldt minuten later; wat ertussen geplaatst werd ontbrak in
de momentopname. Afwezigheid telt nu pas na een dag, en een onterechte vraag
gaat vanzelf terug naar live zodra een volledige scan hem in de kast ziet.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from backend.api import jobs as J  # noqa: E402
from backend.api.listings import VERDENKING_REDENEN  # noqa: E402
from test_vinted_weg_wordt_een_vraag import _DB, _draai  # noqa: E402


def _rijen(listed_at):
    items = [{"id": "i1", "user_id": "u1", "sku": None, "title": "Winterjas Noppies maat 98"}]
    listings = [
        {"id": "l1", "item_id": "i1", "platform": "vinted", "status": "active",
         "platform_listing_id": "111", "listed_at": listed_at},
        {"id": "l2", "item_id": "i1", "platform": "shopify", "status": "active",
         "platform_listing_id": "s1"},
    ]
    return items, listings


ANDER = [{"platform_listing_id": "999", "title": "Iets anders", "is_closed": False}]


def test_net_geplaatst_en_nog_niet_in_de_kast_is_geen_vraag():
    nu = datetime.now(timezone.utc)
    items, listings = _rijen((nu - timedelta(minutes=5)).isoformat())
    _draai(_DB(items, listings), ANDER)
    assert listings[0]["status"] == "active"


def test_na_een_dag_weg_blijft_wel_een_vraag():
    nu = datetime.now(timezone.utc)
    items, listings = _rijen((nu - timedelta(hours=30)).isoformat())
    _draai(_DB(items, listings), ANDER)
    assert listings[0]["status"] == "sold_unconfirmed"


def test_onterechte_vraag_gaat_terug_naar_live_als_hij_in_de_kast_staat():
    items, listings = _rijen(None)
    listings[0].update(status="sold_unconfirmed", error_message=VERDENKING_REDENEN["vinted_weg"])
    _draai(_DB(items, listings), [{"platform_listing_id": "111",
                                   "title": "Winterjas Noppies maat 98", "is_closed": False}])
    assert listings[0]["status"] == "active"
    assert listings[0]["error_message"] is None


def test_een_andere_vraag_blijft_staan():
    # Een vraag om een andere reden (bijv. gereserveerd) raakt dit herstel niet.
    items, listings = _rijen(None)
    listings[0].update(status="sold_unconfirmed", error_message=VERDENKING_REDENEN["gereserveerd"])
    _draai(_DB(items, listings), [{"platform_listing_id": "111",
                                   "title": "Winterjas Noppies maat 98", "is_closed": False}])
    assert listings[0]["status"] == "sold_unconfirmed"


def test_tijdgrens():
    nu = datetime.now(timezone.utc)
    assert J._te_jong_om_weg_te_zijn({"listed_at": (nu - timedelta(hours=1)).isoformat()}, nu)
    assert not J._te_jong_om_weg_te_zijn({"listed_at": (nu - timedelta(hours=25)).isoformat()}, nu)
    assert not J._te_jong_om_weg_te_zijn({}, nu)
