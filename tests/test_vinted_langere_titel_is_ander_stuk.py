"""Een langere Vinted-titel is een ander stuk, en Delist schrapt een wachtende plaatsing.

WAAROM (14-10-2026, Janneke 31d28378). Om 20:05 UTC plaatste de extensie
"Trui Lyle & Scott maat 110-116 (donkerblauw)"; Vinted stuurde niet door, de
koppeling werd geweigerd, maar de advertentie (10380360699) stond er wel. Om
20:07 plaatste ze de groene "Trui Lyle & Scott maat 110-116"; ook die stuurde
niet door, en resolveCreatedVintedItem zocht in de kast met "de ene titel bevat
de andere". De nieuwste die de korte titel bevatte was de donkerblauwe, dus de
groene kreeg die advertentie. Om 20:09 haalde Delist op de groene trui hem van
Vinted (de vastgelegde advertentie in die opdracht heet "...(donkerblauw)"), en
daarna kon Delist op de donkerblauwe trui niets meer vinden.

Daarbij stond voor de donkerblauwe nog een Vinted-plaatsing klaar (df4fafbb).
Na Delist zou die hem weer online hebben gezet.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402
from tests.test_vinted_titelgenoot_niet_koppelen import _DB, _functie, _vinted_js  # noqa: E402
from tests.test_delist_spaart_eigen_webshop import JAS, _draai  # noqa: E402

VOOR_DE_REPARATIE = "409cccc7"
NODE = shutil.which("node")
GROEN = {"title": "Trui Lyle & Scott maat 110-116", "_vinted_bezet": ["10380316482", "10380266841"]}
KAST = [
    {"id": 10380360699, "title": "Trui Lyle & Scott maat 110-116 (donkerblauw)", "is_closed": False, "is_draft": False},
    {"id": 10380316482, "title": "Trui Lyle & Scott maat 110-116", "is_closed": False, "is_draft": False},
    {"id": 10380266841, "title": "Trui Lyle & Scott maat 110-116", "is_closed": False, "is_draft": False},
]


def _na_trage_plaatsing(commit, payload, kast, opts=None):
    """Het zoeken na een plaatsing die niet doorstuurde, zoals vinted.js het aanroept."""
    if NODE is None:
        pytest.skip("node is niet geïnstalleerd")
    driver = f"""
const sleep = async () => {{}};
const getVintedUserId = async () => "1";
const fetch = async () => ({{ ok: true, json: async () => ({{ items: {json.dumps(kast)} }}) }});
{_functie(_vinted_js(commit), "resolveCreatedVintedItem")}
const item = {json.dumps(payload)};
resolveCreatedVintedItem(item, item.platform_listing_id, 5, {json.dumps(opts or {})}).then((r) => console.log(JSON.stringify(r)));
"""
    r = subprocess.run([NODE, "-e", driver], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    uit = json.loads(r.stdout.strip())
    return uit["id"] if uit else None


def test_oud_gaf_de_groene_trui_de_advertentie_van_de_donkerblauwe():
    assert _na_trage_plaatsing(VOOR_DE_REPARATIE, GROEN, KAST) == "10380360699"


def test_nieuw_pakt_geen_langere_titel():
    assert _na_trage_plaatsing(None, GROEN, KAST) is None


def test_nieuw_vindt_nog_steeds_de_eigen_advertentie():
    # Sinds 16-10 met titelgenoten alleen wat ná de eigen klik verscheen (het
    # hoogste nummer in de kast vlak ervoor), zie test_vinted_titelgenoten_hard_bewijs.
    kast = [{"id": 10380424025, "title": GROEN["title"], "is_closed": False, "is_draft": False}] + KAST
    assert _na_trage_plaatsing(None, GROEN, kast, {"naId": 10380360699}) == "10380424025"


def test_nieuw_vindt_een_op_100_tekens_afgekapte_titel():
    lang = "Trui " + "heel mooi en zacht " * 8
    kast = [{"id": 1, "title": lang[:100], "is_closed": False, "is_draft": False}]
    assert _na_trage_plaatsing(None, {"title": lang}, kast) == "1"


# ── Delist schrapt de plaatsing die nog klaarstaat ──────────────────────────
TRUI = JAS  # _draai roept de functie met dit artikel aan


def _db():
    return _DB(
        items=[{"id": TRUI, "user_id": "u1", "title": "Trui Lyle & Scott maat 110-116 (donkerblauw)",
                "created_at": "2026-10-08T13:39:29+00:00"}],
        listings=[{"id": "l-v", "item_id": TRUI, "platform": "vinted", "status": "pending",
                   "platform_listing_id": None, "platform_listing_url": None, "platform_offer_id": None,
                   "listed_at": None}],
        # Zoals in het echt (gemeten 22-10): om 20:05 liep er al een Vinted-plaatsing
        # die op een fout eindigde maar de trui wél online zette. Zonder die
        # eerdere plaatsing stond er niets, en dan hoort Delist niets te verwijderen
        # (test_delist_nooit_geplaatst).
        jobs=[{"id": "eerder", "user_id": "u1", "item_id": TRUI, "platform": "vinted",
               "action": "create", "status": "error", "claimed_at": "2026-10-14T20:05:33+00:00",
               "payload": {}},
              {"id": "df4fafbb", "user_id": "u1", "item_id": TRUI, "platform": "vinted",
               "action": "create", "status": "pending", "payload": {}},
              {"id": "loopt", "user_id": "u1", "item_id": TRUI, "platform": "marktplaats",
               "action": "create", "status": "claimed", "payload": {}}],
        platform_credentials=[])


def _oude_functie():
    bron = subprocess.check_output(["git", "show", f"{VOOR_DE_REPARATIE}:backend/services/crosslist.py"],
                                   cwd=ROOT, text=True)
    begin = bron.index("async def delist_all_platforms(")
    eind = min(bron.index("\nasync def ", begin + 10), bron.index("\ndef ", begin + 10))
    lokaal = {}
    exec(compile(bron[begin:eind], "oud_crosslist", "exec"), vars(cl), lokaal)  # noqa: S102
    return lokaal["delist_all_platforms"]


def _status(db, job_id):
    return next(j["status"] for j in db.tabellen["jobs"] if j["id"] == job_id)


def test_oud_liet_de_wachtende_plaatsing_staan():
    db = _db()
    _draai(_oude_functie(), db, bronwinkel_sparen=True)
    assert _status(db, "df4fafbb") == "pending"


def test_nieuw_schrapt_de_wachtende_plaatsing():
    db = _db()
    _draai(cl.delist_all_platforms, db, bronwinkel_sparen=True)
    assert _status(db, "df4fafbb") == "cancelled"
    # Een plaatsing die al loopt, en die op een kanaal zonder levende rij, blijven.
    assert _status(db, "loopt") == "claimed"
    # De verwijdering gaat gewoon de deur uit.
    assert any(j["action"] == "delete" and j["platform"] == "vinted" for j in db.tabellen["jobs"])
