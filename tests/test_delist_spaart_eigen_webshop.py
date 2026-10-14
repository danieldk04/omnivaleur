"""De knop Delist wist een product uit de eigen webshop van de verkoper niet.

WAAROM (14-10-2026, Janneke 31d28378). Haar Shopify-logboek: op 12-10 om 16:19
en 16:26 verwijderde "Omnivaleur" de producten 16134692176197 en 16134748340549,
twee jassen "Tussenjas Name it maat 128" die niet verkocht waren. Dat gebeurde
toen ze op Marktplaats en Vinted werden weggehaald (Delist) en opnieuw geplaatst.
Haar webshop is de bron: die producten stonden er sinds 02-09, de artikelen
kwamen pas op 09-10 in Omnivaleur. Een gewist product is niet terug te halen.

Na een echte verkoop (vangnet, zonder bronwinkel_sparen) blijft het oude gedrag:
een uniek stuk moet dan wél uit de winkel, anders wordt het twee keer verkocht.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402
from tests.test_vinted_titelgenoot_niet_koppelen import _DB  # noqa: E402

VOOR_DE_REPARATIE = "c8b2071"
JAS = "7f872a5e"


def _db(shop_listed_at="2026-09-02T12:16:43+00:00"):
    return _DB(
        items=[{"id": JAS, "user_id": "u1", "title": "Tussenjas Name it maat 128",
                "created_at": "2026-10-09T14:35:20.473659+00:00"}],
        listings=[
            {"id": "l-shop", "item_id": JAS, "platform": "shopify", "status": "active",
             "platform_listing_id": "16134748340549", "platform_listing_url": None, "platform_offer_id": None, "listed_at": shop_listed_at},
            {"id": "l-mp", "item_id": JAS, "platform": "marktplaats", "status": "active",
             "platform_listing_id": "m2452315406", "platform_listing_url": None, "platform_offer_id": None, "listed_at": "2026-10-10T18:09:13+00:00"},
        ],
        jobs=[], platform_credentials=[])


def _draai(functie, db, **kw):
    gewist = []

    async def nep_delist_one(listing):
        gewist.append(listing["platform"])
        return True

    oud = (cl.get_db, cl._delist_one)
    cl.get_db, cl._delist_one = (lambda: db), nep_delist_one
    try:
        uit = asyncio.run(functie(JAS, "u1", **kw))
    finally:
        cl.get_db, cl._delist_one = oud
    return gewist, uit


def _oude_functie():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/services/crosslist.py"],
                                   cwd=ROOT, text=True)
    begin = bron.index("async def delist_all_platforms(")
    eind = bron.index("\nasync def ", begin + 10)
    eind = min(eind, bron.index("\ndef ", begin + 10))
    ns = vars(cl)
    code = compile(bron[begin:eind], "oud_crosslist", "exec")
    lokaal = {}
    exec(code, ns, lokaal)  # noqa: S102 — eigen code uit git, alleen in de proef
    return lokaal["delist_all_platforms"]


def test_oud_wiste_het_product_uit_haar_webshop():
    gewist, _ = _draai(_oude_functie(), _db())
    assert "shopify" in gewist


def test_nieuw_laat_haar_webshop_met_rust_bij_de_knop():
    db = _db()
    gewist, uit = _draai(cl.delist_all_platforms, db, bronwinkel_sparen=True)
    assert "shopify" not in gewist
    assert {"platform": "shopify", "status": "kept_in_shop"}.items() <= next(
        r for r in uit if r.get("platform") == "shopify").items()
    # Marktplaats gaat wél weg: daar is het een kanaal.
    assert any(j["platform"] == "marktplaats" and j["action"] == "delete" for j in db.tabellen["jobs"])


def test_door_omnivaleur_zelf_geplaatst_product_gaat_wel_weg():
    # Shopify als kanaal: het product kwam pas na het artikel in de winkel.
    gewist, _ = _draai(cl.delist_all_platforms, _db("2026-10-10T08:00:00+00:00"), bronwinkel_sparen=True)
    assert "shopify" in gewist


def test_na_een_verkoop_blijft_het_vangnet_zoals_het_was():
    gewist, _ = _draai(cl.delist_all_platforms, _db())
    assert "shopify" in gewist
