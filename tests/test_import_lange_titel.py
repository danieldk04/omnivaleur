"""Een product met een titel boven de 100 tekens komt gewoon binnen.

WAAROM DIT ER IS (07-10-2026, Goudlief)
ItemCreate staat hooguit 100 tekens toe, Shopify 255. Bij Goudlief vielen zeven
producten ("14K vergulde keramische armbandensets met bloemenmotief, casual,
dagelijks en romantisch, damessieraden", 103 tekens) stil op "failed", en 243
wachtende producten zouden hetzelfde doen. Nu wordt de titel op een heel woord
ingekort en blijft de volle naam de Shopify-titel.

Met IMPORTS_BRON=<pad> draait dezelfde proef tegen een oude versie.
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.models import ItemCreate  # noqa: E402


def _laad():
    bron = os.environ.get("IMPORTS_BRON") or str(ROOT / "backend/api/imports.py")
    spec = importlib.util.spec_from_file_location("imports_lange_titel_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


imp = _laad()

# Letterlijk uit import_candidates van Goudlief, 07-10-2026.
ECHT = [
    "14K vergulde keramische armbandensets met bloemenmotief, casual, dagelijks en romantisch, damessieraden",
    "14K vergulde acryl kralenarmbanden met onregelmatige vorm, romantische serie voor dames, "
    "geschikt voor feestjes/bijeenkomsten.",
]


def _kandidaat(titel):
    return {"title": titel, "price": 11.99, "platform": "shopify",
            "photo_url": "https://cdn.shopify.com/x.jpg"}


def test_lange_titel_wordt_een_geldig_artikel():
    for titel in ECHT:
        data = imp._item_data_from_candidate(_kandidaat(titel), None, inferred={})
        ItemCreate(**data)  # gooide ValidationError: dat was de "failed"
        assert len(data["title"]) <= 100
        assert titel.startswith(data["title"])
        assert not data["title"].endswith((",", " ")), data["title"]
        # Heel woord: het volgende teken in het origineel is een spatie.
        assert titel[len(data["title"])] in " ,."
        assert data["shopify_title"] == titel


def test_korte_titel_blijft_onaangeroerd():
    titel = "14K verguld roestvrijstalen bedelarmband met strik"
    data = imp._item_data_from_candidate(_kandidaat(titel), None, inferred={})
    assert data["title"] == titel
    assert data["shopify_title"] is None


def test_eigen_shopify_titel_van_de_verkoper_wint():
    data = imp._item_data_from_candidate(
        _kandidaat(ECHT[0]), {"shopify_title": "Mijn eigen titel"}, inferred={})
    assert data["shopify_title"] == "Mijn eigen titel"
