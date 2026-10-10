"""Een titelsuggestie van de scan heet geen "zelfde nummer".

WAAROM DIT ER IS (10-10-2026, Janneke 31d28378). Na de reparatie van 09-10
bleven 140 Shopify-producten ("* Jas" 27 keer, "* Set" 47 keer, "Broek Noppies
maat 80" acht keer) toch onder Te controleren staan als dubbel product in haar
winkel. Gemeten in haar winkel: geen van de 140 deelt een artikelnummer met het
product dat al aan het voorgestelde item hangt. Mechanisme: de scan koppelt op
een unieke gelijke titel en bewaart dat als suggested_item_id. Kwamen er daarna
meer items met die titel bij, dan vond _best_match geen unieke titel meer en
viel _match_candidate terug op die bewaarde suggestie, met als reden
"same_code". Dat werd shopify_duplicate, en de dagelijkse achterstandsronde liet
ze dus liggen. Draagt het item geen eigen nummer van de verkoper (alleen ons
IMP-nummer), dan kan de suggestie niet op een nummer berusten: same_title.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api.imports import _match_candidate, _twijfelreden, _shopify_van_item  # noqa: E402

ITEMS = [
    {"id": "jas-1", "title": "* Jas", "sku": "IMP-E3D0C6F8", "created_at": "2026-10-07"},
    {"id": "jas-2", "title": "* Jas", "sku": "IMP-0A7F5597", "created_at": "2026-10-08"},
]
LISTINGS = {("shopify", "111"): "jas-1", ("shopify", "333"): "jas-2"}
CAND = {"platform": "shopify", "platform_listing_id": "222", "title": "* Jas",
        "suggested_item_id": "jas-1", "price": 12.5}


def test_titelsuggestie_zonder_nummer_is_same_title():
    item_id, reden = _match_candidate(CAND, ITEMS, LISTINGS, set(), set())
    assert (item_id, reden) == ("jas-1", "same_title")


def test_en_dus_geen_dubbel_product_meer():
    item_id, reden = _match_candidate(CAND, ITEMS, LISTINGS, set(), set())
    assert _twijfelreden(CAND, item_id, reden, set(), _shopify_van_item(LISTINGS), LISTINGS) is None


def test_item_met_eigen_nummer_blijft_same_code():
    items = [{**ITEMS[0], "sku": "04.000.08.W1250"}, ITEMS[1]]
    item_id, reden = _match_candidate(CAND, items, LISTINGS, set(), set())
    assert (item_id, reden) == ("jas-1", "same_code")
