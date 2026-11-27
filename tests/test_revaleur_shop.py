"""Revaleur-webshop: verzendregels, reserveren, betalen, afmelden (herbouw 27-11-2026)."""
import asyncio
from types import SimpleNamespace

import pytest

from backend.api import revaleur_shop as rs
from backend.services import revaleur_mail


def test_verzendregels_volgen_het_beleid():
    assert rs.verzendkosten("NL", 10) == 0 and rs.verzendkosten("BE", 10) == 0
    assert rs.verzendkosten("EU", 99.99) == 3.95 and rs.verzendkosten("EU", 100) == 0
    assert rs.verzendkosten("INT", 20) == 4.95 and rs.verzendkosten("INT", 100) == 0
    assert rs.zone_van_land("de") == "EU" and rs.zone_van_land("US") == "INT" and rs.zone_van_land("nl") == "NL"


class _Q:
    def __init__(self, db, tabel):
        self.db, self.t, self.op, self.filt = db, tabel, "select", {}
        self.payload = None

    def select(self, *_): self.op = "select"; return self
    def insert(self, p): self.op, self.payload = "insert", p; return self
    def update(self, p): self.op, self.payload = "update", p; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, k, v): self.filt[k] = ("eq", v); return self
    def in_(self, k, v): self.filt[k] = ("in", list(v)); return self
    def lt(self, k, v): self.filt[k] = ("lt", v); return self

    def _passt(self, r):
        for k, (soort, v) in self.filt.items():
            if soort == "eq" and r.get(k) != v: return False
            if soort == "in" and r.get(k) not in v: return False
            if soort == "lt" and not str(r.get(k)) < str(v): return False
        return True

    def execute(self):
        rijen = self.db.tabellen.setdefault(self.t, [])
        if self.op == "select":
            return SimpleNamespace(data=[dict(r) for r in rijen if self._passt(r)])
        if self.op == "insert":
            if self.t == "revaleur_reserveringen" and any(r["item_id"] == self.payload["item_id"] for r in rijen):
                raise RuntimeError("duplicate key")
            if self.t == "revaleur_bestellingen":
                self.payload = {"id": "b1", "nummer": 1001, **self.payload}
            rijen.append(dict(self.payload))
            return SimpleNamespace(data=[dict(self.payload)])
        if self.op == "update":
            for r in rijen:
                if self._passt(r): r.update(self.payload)
            return SimpleNamespace(data=[])
        if self.op == "delete":
            rijen[:] = [r for r in rijen if not self._passt(r)]
            return SimpleNamespace(data=[])


class FakeDb:
    def __init__(self):
        self.tabellen = {
            "listings": [{"item_id": "i1", "platform_listing_id": "p1", "status": "active", "platform": "shopify"},
                         {"item_id": "i2", "platform_listing_id": "p2", "status": "active", "platform": "shopify"}],
            "items": [{"id": "i1", "sku": "1", "title": "A", "shopify_title": None, "price": 30.0, "price_shopify": None,
                       "photo_urls": [], "user_id": rs.settings.revaleur_user_id},
                      {"id": "i2", "sku": "2", "title": "B", "shopify_title": "B titel", "price": 20.0, "price_shopify": 25.0,
                       "photo_urls": [], "user_id": rs.settings.revaleur_user_id}],
        }

    def table(self, t): return _Q(self, t)


@pytest.fixture
def db(monkeypatch):
    d = FakeDb()
    monkeypatch.setattr(rs, "get_db", lambda: d)
    monkeypatch.setattr(rs.settings, "stripe_secret_key", "sk_test_x")
    aanroepen = []

    def maak(**kw):
        aanroepen.append(kw)
        return SimpleNamespace(id="cs_1", url="https://stripe.test/pay")
    monkeypatch.setattr(rs.stripe.checkout.Session, "create", staticmethod(maak))
    d.stripe = aanroepen
    return d


def run(c):
    return asyncio.run(c)


def test_afrekenen_reserveert_en_rekent_serverprijs(db):
    r = run(rs.checkout(rs.CheckoutIn(ids=["p1", "p2"], prijzen={"p1": 30.0, "p2": 25.0}, land="NL")))
    assert r == {"url": "https://stripe.test/pay"}
    kw = db.stripe[0]
    assert [l["price_data"]["unit_amount"] for l in kw["line_items"]] == [3000, 2500]   # price_shopify wint van price
    assert kw["shipping_options"][0]["shipping_rate_data"]["fixed_amount"]["amount"] == 0
    assert {r["item_id"] for r in db.tabellen["revaleur_reserveringen"]} == {"i1", "i2"}
    assert all(r["sessie_id"] == "cs_1" for r in db.tabellen["revaleur_reserveringen"])


def test_tweede_koper_krijgt_verkocht_en_niets_blijft_hangen(db):
    run(rs.checkout(rs.CheckoutIn(ids=["p1"])))
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p2", "p1"])))
    assert e.value.status_code == 409 and e.value.detail == {"verkocht": ["p1"]}
    assert [r["item_id"] for r in db.tabellen["revaleur_reserveringen"]] == ["i1"]    # p2 weer vrijgegeven


def test_onbekend_of_verkocht_artikel_wordt_geweigerd(db):
    db.tabellen["listings"][0]["status"] = "sold"
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p1", "p2"])))
    assert e.value.detail == {"verkocht": ["p1"]} and not db.tabellen.get("revaleur_reserveringen")


def test_prijsverschil_wordt_nooit_stil_geind(db):
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p2"], prijzen={"p2": 20.0})))
    assert e.value.status_code == 409 and e.value.detail == {"prijs_gewijzigd": ["p2"]}
    assert not db.tabellen.get("revaleur_reserveringen")


def test_stripe_storing_geeft_artikelen_vrij(db, monkeypatch):
    def stuk(**kw): raise RuntimeError("stripe plat")
    monkeypatch.setattr(rs.stripe.checkout.Session, "create", staticmethod(stuk))
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p1"])))
    assert e.value.status_code == 503 and not db.tabellen["revaleur_reserveringen"]


def test_betaling_meldt_artikelen_af_idempotent_en_mailt(db, monkeypatch):
    verkocht, mails = [], []

    async def sold(item_id, platform, sold_price=None, bewijs=None, **kw):
        verkocht.append((item_id, platform, sold_price, bewijs))
    import backend.services.crosslist as cl
    monkeypatch.setattr(cl, "handle_item_sold", sold)
    monkeypatch.setattr(revaleur_mail, "stuur_bevestiging", lambda b: mails.append(b))
    db.tabellen["revaleur_reserveringen"] = [{"item_id": "i1", "sessie_id": "cs_9", "tot": "x"}]
    sessie = {"id": "cs_9", "payment_status": "paid", "amount_total": 3000, "total_details": {"amount_shipping": 0},
              "metadata": {"bron": "revaleur", "item_ids": "i1", "taal": "nl"},
              "customer_details": {"email": "k@x.nl", "name": "Kim Jansen"},
              "shipping_details": {"name": "Kim Jansen", "address": {"country": "NL"}}}
    run(rs.verwerk_betaling(db, sessie))
    run(rs.verwerk_betaling(db, sessie))          # Stripe stuurt de melding twee keer
    assert verkocht == [("i1", "revaleur", 30.0, "bestelling")]
    assert len(db.tabellen["revaleur_bestellingen"]) == 1 and len(mails) == 1
    assert not db.tabellen["revaleur_reserveringen"]


def test_mail_zonder_schuld_en_in_de_taal_van_de_klant():
    best = {"nummer": 1001, "taal": "nl", "naam": "Kim Jansen", "totaal": 30, "verzendkosten": 0,
            "artikelen": [{"titel": "Beige fleece", "prijs": 30}]}
    onderwerp, tekst = revaleur_mail.bericht(best)
    assert "#1001" in onderwerp and "Hoi Kim" in tekst and "€30,00" in tekst and "gratis" in tekst
    for woord in ("sorry", "onze fout", "ligt aan ons"):
        assert woord not in tekst.lower()
    assert revaleur_mail.bericht({**best, "taal": "en"})[1].startswith("Hi Kim")
