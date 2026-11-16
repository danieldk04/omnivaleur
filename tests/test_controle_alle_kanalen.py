"""Elk kanaal met een verkoopcontrole zet een stempel (16-11-2026).

Daniel zag op het dashboard alleen Vinted nagekeken, terwijl Shopify, WooCommerce
en eBay op de server wel elke vijf minuten bestellingen nalopen. Zonder stempel
liet het dashboard hen weg, en dat las als "niet gecontroleerd".

Wat hier vastligt:
  1. Shopify en WooCommerce stempelen pas NA een geslaagde ronde (niet bij een fout).
  2. eBay stempelt via de server-poll, één keer per verkoper, alleen bij een echt antwoord.
  3. Marktplaats en 2dehands stempelt de server-poll NIET (alleen de extensie).
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from backend.services import controle, polling, shopify_orders, woocommerce_orders  # noqa: E402
from tests.test_verkoopcontrole_wachtrij import _Db, _listing, _NepPlatform  # noqa: E402


@pytest.fixture
def stempels(monkeypatch):
    gezet = []
    monkeypatch.setattr(controle, "zet", lambda uid, kanaal, db=None, nu=None: gezet.append((uid, kanaal)) or True)
    return gezet


def _ebay_db(n=3, eigenaar="u1"):
    ls = []
    for i in range(n):
        l = _listing(i, None, eigenaar)
        l["platform"] = "ebay"
        l["platform_offer_id"] = f"o{i}"
        ls.append(l)
    db = _Db({
        "listings": ls,
        "items": [{"id": l["item_id"], "user_id": eigenaar} for l in ls],
        "platform_credentials": [{"user_id": eigenaar, "platform": "ebay", "token": "x" * 50}],
    })
    return db


def _omgeving(monkeypatch, db, platform):
    monkeypatch.setattr(polling, "get_db", lambda: db)
    monkeypatch.setattr(polling, "get_platform", lambda naam: platform)

    async def _niets(*a, **k):
        return None
    monkeypatch.setattr(polling, "handle_item_sold", _niets)


def test_ebay_krijgt_een_stempel_een_keer_per_verkoper(monkeypatch, stempels):
    _omgeving(monkeypatch, _ebay_db(3), _NepPlatform("active"))
    asyncio.run(polling.poll_platform_statuses())
    assert stempels == [("u1", "ebay")]


def test_ebay_zonder_echt_antwoord_krijgt_geen_stempel(monkeypatch, stempels):
    _omgeving(monkeypatch, _ebay_db(2), _NepPlatform(RuntimeError("eBay ligt eruit")))
    asyncio.run(polling.poll_platform_statuses())
    assert stempels == []
    _omgeving(monkeypatch, _ebay_db(2), _NepPlatform("error"))
    asyncio.run(polling.poll_platform_statuses())
    assert stempels == []


def test_de_server_poll_stempelt_marktplaats_niet(monkeypatch, stempels):
    db = _ebay_db(2)
    for l in db.tabellen["listings"]:
        l["platform"] = "marktplaats"
    db.tabellen["platform_credentials"][0]["platform"] = "marktplaats"
    _omgeving(monkeypatch, db, _NepPlatform("active"))
    asyncio.run(polling.poll_platform_statuses())
    assert stempels == []


class _Rij:
    def __init__(self, db, naam): self.db, self.naam = db, naam
    def select(self, *a): return self
    def eq(self, *a): return self
    def limit(self, *a): return self
    def update(self, v): self.upd = v; return self
    def execute(self):
        if hasattr(self, "upd"):
            self.db.geschreven.append(self.upd)
            return type("R", (), {"data": []})()
        return type("R", (), {"data": self.db.rijen})()


class _Winkel:
    def __init__(self, rijen): self.rijen, self.geschreven = rijen, []
    def table(self, naam): return _Rij(self, naam)


def test_shopify_stempelt_na_een_geslaagde_ronde_en_niet_na_een_fout(monkeypatch, stempels):
    import backend.platforms.shopify as sh
    rij = {"user_id": "u9", "access_token": "t", "extra_data": {"shop_domain": "x.myshopify.com"}}
    db = _Winkel([rij])
    monkeypatch.setattr(shopify_orders, "get_db", lambda: db)

    async def creds(r): return ("x.myshopify.com", "tok")
    monkeypatch.setattr(sh, "_shop_creds", creds)

    async def goed(shop, token, sinds): return []
    monkeypatch.setattr(shopify_orders, "_bestellingen", goed)
    asyncio.run(shopify_orders.controleer_shopify_verkopen())
    assert stempels == [("u9", "shopify")]

    stempels.clear()

    async def stuk(shop, token, sinds): raise RuntimeError("Shopify 500")
    monkeypatch.setattr(shopify_orders, "_bestellingen", stuk)
    asyncio.run(shopify_orders.controleer_shopify_verkopen())
    assert stempels == []


def test_woocommerce_stempelt_na_de_ronde_en_niet_bij_een_fout(monkeypatch, stempels):
    db = _Winkel([{"extra_data": {}}])

    class Client:
        async def bestellingen(self, sinds): return []
    monkeypatch.setattr(woocommerce_orders, "client_uit", lambda rij: Client())

    async def modus(*a, **k): return None
    import backend.services.woocommerce_scan as ws
    monkeypatch.setattr(ws, "bewaar_modus", modus)
    from datetime import datetime, timezone
    asyncio.run(woocommerce_orders.controleer_winkel(db, {"user_id": "u7", "extra_data": {}}, datetime.now(timezone.utc)))
    assert stempels == [("u7", "woocommerce")]

    stempels.clear()

    class Stuk:
        async def bestellingen(self, sinds): raise RuntimeError("winkel dicht")
    monkeypatch.setattr(woocommerce_orders, "client_uit", lambda rij: Stuk())
    with pytest.raises(RuntimeError):
        asyncio.run(woocommerce_orders.controleer_winkel(db, {"user_id": "u7", "extra_data": {}}, datetime.now(timezone.utc)))
    assert stempels == []


def test_alle_kanalen_staan_in_de_toegestane_lijst():
    assert {"shopify", "woocommerce", "ebay", "facebook"} <= set(controle.KANALEN)


def test_facebook_verkoopcontrole_hangt_aan_beide_startplekken_en_meldt_alleen():
    """De extensie draait de Facebook-controle op dezelfde twee plekken als
    Marktplaats, en meldt ter bevestiging: nooit zelf afmelden. De leesfunctie
    is op een nagebouwde pagina bewezen (16-11-2026); de echte Facebook-pagina
    is nog niet gezien, daarom stempelt hij alleen bij echt gelezen kaarten."""
    bron = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
    assert bron.count("checkVintedOrders(); checkFacebookSold();") == 2
    fn = bron.split("async function checkFacebookSold()")[1].split("\n}\n")[0]
    assert "meldMogelijkeVerkopen(" in fn and "handle_item_sold" not in fn
    assert 'meldControle("facebook", "leeg")' in fn
    assert fn.index('meldControle("facebook", "leeg")') < fn.index('meldControle("facebook");')
