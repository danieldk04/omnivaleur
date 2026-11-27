"""Revaleur-webshop: verzendregels, reserveren, betalen, koppeling (eigen database, los van Omnivaleur)."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from revaleur.shop_api import checkout as rs, koppeling, mail


def test_verzendregels_volgen_het_beleid():
    assert rs.verzendkosten("NL", 10) == 0 and rs.verzendkosten("BE", 10) == 0
    assert rs.verzendkosten("EU", 99.99) == 3.95 and rs.verzendkosten("EU", 100) == 0
    assert rs.verzendkosten("INT", 20) == 4.95 and rs.verzendkosten("INT", 100) == 0
    assert rs.zone_van_land("de") == "EU" and rs.zone_van_land("US") == "INT" and rs.zone_van_land("nl") == "NL"


class _Q:
    def __init__(self, db, tabel):
        self.db, self.t, self.op, self.filt, self.payload = db, tabel, "select", {}, None

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
            if self.t == "reserveringen" and any(r["product_id"] == self.payload["product_id"] for r in rijen):
                raise RuntimeError("duplicate key")
            if self.t == "bestellingen":
                self.payload = {"id": "b1", "nummer": 1001, **self.payload}
            rijen.append(dict(self.payload))
            return SimpleNamespace(data=[dict(self.payload)])
        if self.op == "update":
            for r in rijen:
                if self._passt(r): r.update(self.payload)
            return SimpleNamespace(data=[])
        rijen[:] = [r for r in rijen if not self._passt(r)]
        return SimpleNamespace(data=[])


class FakeDb:
    def __init__(self):
        self.tabellen = {"producten": [
            {"id": "p1", "sku": "1", "titel": "A", "prijs": 30.0, "fotos": [], "status": "beschikbaar"},
            {"id": "p2", "sku": "2", "titel": "B titel", "prijs": 25.0, "fotos": [{"src": "x"}], "status": "beschikbaar"},
            {"id": "p1b", "sku": "1", "titel": "A dubbel", "prijs": 35.0, "fotos": [], "status": "beschikbaar"}]}

    def table(self, t): return _Q(self, t)


@pytest.fixture
def db(monkeypatch):
    d = FakeDb()
    monkeypatch.setattr(rs, "get_db", lambda: d)
    monkeypatch.setattr(rs.settings, "stripe_secret_key", "sk_test_x")
    d.stripe = []

    def maak(**kw):
        d.stripe.append(kw)
        return SimpleNamespace(id="cs_1", url="https://stripe.test/pay")
    monkeypatch.setattr(rs.stripe.checkout.Session, "create", staticmethod(maak))
    return d


def run(c):
    return asyncio.run(c)


def test_afrekenen_reserveert_en_rekent_serverprijs(db):
    r = run(rs.checkout(rs.CheckoutIn(ids=["p1", "p2"], prijzen={"p1": 30.0, "p2": 25.0}, land="NL")))
    assert r == {"url": "https://stripe.test/pay"}
    kw = db.stripe[0]
    assert [l["price_data"]["unit_amount"] for l in kw["line_items"]] == [3000, 2500]
    assert kw["shipping_options"][0]["shipping_rate_data"]["fixed_amount"]["amount"] == 0
    assert all(r["sessie_id"] == "cs_1" for r in db.tabellen["reserveringen"])


def test_tweede_koper_krijgt_verkocht_en_niets_blijft_hangen(db):
    run(rs.checkout(rs.CheckoutIn(ids=["p1"])))
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p2", "p1"])))
    assert e.value.status_code == 409 and e.value.detail == {"verkocht": ["p1"]}
    assert [r["product_id"] for r in db.tabellen["reserveringen"]] == ["p1"]


def test_verkocht_artikel_wordt_geweigerd(db):
    db.tabellen["producten"][0]["status"] = "verkocht"
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p1", "p2"])))
    assert e.value.detail == {"verkocht": ["p1"]} and not db.tabellen.get("reserveringen")


def test_prijsverschil_wordt_nooit_stil_geind(db):
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p2"], prijzen={"p2": 20.0})))
    assert e.value.status_code == 409 and e.value.detail == {"prijs_gewijzigd": ["p2"]}


def test_stripe_storing_geeft_artikelen_vrij(db, monkeypatch):
    def stuk(**kw): raise RuntimeError("stripe plat")
    monkeypatch.setattr(rs.stripe.checkout.Session, "create", staticmethod(stuk))
    with pytest.raises(rs.HTTPException) as e:
        run(rs.checkout(rs.CheckoutIn(ids=["p1"])))
    assert e.value.status_code == 503 and not db.tabellen["reserveringen"]


def test_betaling_boekt_meldt_omnivaleur_idempotent_en_mailt(db, monkeypatch):
    gemeld, mails, builds = [], [], []
    monkeypatch.setattr(koppeling, "meld_verkoop_aan_omnivaleur", lambda sku, nr, prijs: gemeld.append((sku, nr, prijs)) or True)
    monkeypatch.setattr(koppeling, "bouw_site_opnieuw", lambda: builds.append(1))
    monkeypatch.setattr(mail, "stuur_bevestiging", lambda b: mails.append(b))
    db.tabellen["reserveringen"] = [{"product_id": "p1", "sessie_id": "cs_9", "tot": "x"}]
    sessie = {"id": "cs_9", "payment_status": "paid", "amount_total": 3000, "total_details": {"amount_shipping": 0},
              "metadata": {"bron": "revaleur", "product_ids": "p1", "taal": "nl"},
              "customer_details": {"email": "k@x.nl", "name": "Kim Jansen"},
              "shipping_details": {"name": "Kim Jansen", "address": {"country": "NL"}}}
    rs.verwerk_betaling(db, sessie)
    rs.verwerk_betaling(db, sessie)                 # Stripe stuurt de melding twee keer
    assert gemeld == [("1", 1001, 30.0)] and len(mails) == 1 and len(builds) == 1
    assert db.tabellen["producten"][0]["status"] == "verkocht"
    assert db.tabellen["producten"][2]["status"] == "verkocht"      # dubbele advertentie van hetzelfde stuk (sku 1) mee
    assert db.tabellen["producten"][1]["status"] == "beschikbaar"
    assert db.tabellen["bestellingen"][0]["omnivaleur_gemeld_op"] and not db.tabellen["reserveringen"]


def test_mislukte_melding_aan_omnivaleur_blijft_zichtbaar_en_blokkeert_niets(db, monkeypatch):
    monkeypatch.setattr(koppeling, "meld_verkoop_aan_omnivaleur", lambda *a: False)
    monkeypatch.setattr(koppeling, "bouw_site_opnieuw", lambda: None)
    monkeypatch.setattr(mail, "stuur_bevestiging", lambda b: None)
    sessie = {"id": "cs_8", "payment_status": "paid", "amount_total": 3000, "metadata": {"product_ids": "p1"},
              "customer_details": {"email": "k@x.nl"}}
    rs.verwerk_betaling(db, sessie)
    b = db.tabellen["bestellingen"][0]
    assert "omnivaleur_gemeld_op" not in b or not b.get("omnivaleur_gemeld_op")   # blijft leeg: opnieuw te proberen


def test_afmelden_vraagt_geldige_handtekening(db, monkeypatch):
    monkeypatch.setattr(koppeling.settings, "koppeling_geheim", "geheim")
    monkeypatch.setattr(koppeling, "bouw_site_opnieuw", lambda: None)
    body = json.dumps({"sku": "2"}).encode()

    class R:
        def __init__(self, h): self.headers = {koppeling.KOP: h}
        async def body(self): return body
    with pytest.raises(rs.HTTPException) as e:
        run(rs.afmelden(R("fout")))
    assert e.value.status_code == 401 and db.tabellen["producten"][1]["status"] == "beschikbaar"
    run(rs.afmelden(R(koppeling.onderteken(body))))
    assert db.tabellen["producten"][1]["status"] == "verkocht"


def test_zonder_geheim_wordt_niets_geaccepteerd(monkeypatch):
    monkeypatch.setattr(koppeling.settings, "koppeling_geheim", "")
    assert not koppeling.klopt(b"x", koppeling.onderteken(b"x", "a"))


def test_mail_zonder_schuld_en_in_de_taal_van_de_klant():
    best = {"nummer": 1001, "taal": "nl", "naam": "Kim Jansen", "totaal": 30, "verzendkosten": 0,
            "artikelen": [{"titel": "Beige fleece", "prijs": 30}]}
    onderwerp, tekst = mail.bericht(best)
    assert "#1001" in onderwerp and "Hoi Kim" in tekst and "€30,00" in tekst and "gratis" in tekst
    for woord in ("sorry", "onze fout", "ligt aan ons"):
        assert woord not in tekst.lower()
    assert mail.bericht({**best, "taal": "en"})[1].startswith("Hi Kim")


def test_factuurlink_in_de_mail_als_die_er_is_en_zonder_gaat_de_mail_gewoon():
    best = {"nummer": 5, "taal": "nl", "naam": "Kim", "totaal": 30, "verzendkosten": 0, "artikelen": [{"titel": "X", "prijs": 30}]}
    assert "Je factuur (pdf): https://pay.stripe.com/i/x" in mail.bericht({**best, "factuur_url": "https://pay.stripe.com/i/x"})[1]
    assert "Your invoice (pdf): https://pay.stripe.com/i/x" in mail.bericht({**best, "taal": "en", "factuur_url": "https://pay.stripe.com/i/x"})[1]
    assert "factuur" not in mail.bericht(best)[1].lower()


def test_factuur_url_haalt_pdf_op_en_faalt_stil(monkeypatch):
    class F(dict):
        pass
    monkeypatch.setattr(rs.stripe.Invoice, "retrieve", staticmethod(lambda i, api_key=None: F(invoice_pdf="https://pdf", hosted_invoice_url="https://h")))
    assert rs.factuur_url({"invoice": "in_1"}) == "https://pdf"
    assert rs.factuur_url({}) is None
    def boem(*a, **k): raise RuntimeError("x")
    monkeypatch.setattr(rs.stripe.Invoice, "retrieve", staticmethod(boem))
    assert rs.factuur_url({"invoice": "in_1"}) is None
