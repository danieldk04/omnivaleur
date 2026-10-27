"""Commissie voor creators: 25% over wat hun klanten echt betalen. Aantoonbaar.

WAT ER BEPROEFD WORDT, en waarom juist dit:

  * Het bedrag klopt: commissie is een percentage van het NETTO bedrag (zonder
    btw, naar rato bij korting). De oude teller rekende een vast bedrag van 25
    euro per klant; bij 19,99 per maand scheelt dat een factor zes.
  * Dezelfde factuur telt nooit twee keer, ook niet als de ronde hem honderd
    keer ziet. Dat is de enige plek waar dit Daniel geld kan kosten.
  * Een teruggave haalt de commissie weg, tot nul bij een volledige teruggave.
  * Een creator met de oude bounty (percentage 0) krijgt hier niets bij.
  * Pas 60 dagen na de betaling is een bedrag uitbetaalbaar, en uitbetaald is
    bevroren: een latere ronde schrijft er niets meer overheen.
  * DE VOOR-EN-NA-PROEF: zonder het bestand backend/services/creator_commissie.py
    (de situatie van vóór 27-10) faalt deze hele module bij het laden.
"""
from datetime import datetime, timedelta, timezone

import pytest

from test_verwijzing_gratis_maand import NepDb as _NepDb

CREATOR = "creator-code"
KLANT = "u-klant"
NU = datetime.now(timezone.utc)


class NepDb(_NepDb):
    uniek = {**_NepDb.uniek, "creator_commissie": "invoice_id"}


def _factuur(fid, bruto=1999, zonder_btw=1652, totaal=None, dagen_geleden=1):
    betaald = int((NU - timedelta(days=dagen_geleden)).timestamp())
    return {"id": fid, "amount_paid": bruto, "total": totaal if totaal is not None else bruto,
            "total_excluding_tax": zonder_btw, "created": betaald,
            "status_transitions": {"paid_at": betaald}}


class NepStripe:
    def __init__(self, facturen, teruggaven=None):
        self.facturen = facturen
        self.teruggaven = teruggaven or {}
        zelf = self

        class Invoice:
            @staticmethod
            def list(**kw):
                assert kw["status"] == "paid"
                return {"data": list(zelf.facturen)}

        class Charge:
            @staticmethod
            def list(**kw):
                return {"data": [{"invoice": fid, "amount_refunded": cent}
                                 for fid, cent in zelf.teruggaven.items()]}

        self.Invoice, self.Charge = Invoice, Charge


def _db(pct=25, rijen=None):
    return NepDb(
        referral_codes=[{"code": CREATOR, "kind": "creator", "commission_pct": pct}],
        referrals=[{"user_id": KLANT, "code": CREATOR}],
        subscriptions=[{"user_id": KLANT, "stripe_customer_id": "cus_1"}],
        creator_commissie=rijen or [],
    )


@pytest.fixture()
def cc(monkeypatch):
    from backend.services import creator_commissie as m
    return m


async def _ronde(cc, monkeypatch, db, stripe):
    monkeypatch.setattr(cc, "get_db", lambda: db)
    monkeypatch.setattr(cc, "stripe", stripe)
    return await cc.verwerk_commissie()


# ── 1. Het bedrag klopt ─────────────────────────────────────────────────────

def test_commissie_is_percentage_van_netto_niet_vast_bedrag(cc):
    bruto, netto = cc.netto_van_factuur(_factuur("in_1"))
    assert (bruto, netto) == (1999, 1652), "de btw hoort er niet in te zitten"
    assert cc.commissie_cents(netto, 0, bruto, 25) == 413
    # De oude teller zou hier 2500 hebben gegeven: zes keer te veel per maand.


def test_korting_wordt_naar_rato_meegenomen(cc):
    # Factuur van 19,99 waarvan 10,00 betaald is (tegoed voor de rest).
    bruto, netto = cc.netto_van_factuur(_factuur("in_2", bruto=1000, totaal=1999, zonder_btw=1652))
    assert bruto == 1000 and netto == 826


def test_onbekend_btwbedrag_telt_bruto_liever_te_veel_dan_creator_korten(cc):
    assert cc.netto_van_factuur({"amount_paid": 1999}) == (1999, 1999)


def test_niet_betaalde_factuur_levert_niets(cc):
    assert cc.netto_van_factuur({"amount_paid": 0, "total": 1999}) == (0, 0)


# ── 2. Nooit dubbel ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_zelfde_factuur_in_vijf_rondes_is_een_rij(cc, monkeypatch):
    db = _db()
    stripe = NepStripe([_factuur("in_1")])
    for _ in range(5):
        await _ronde(cc, monkeypatch, db, stripe)
    rijen = db.data["creator_commissie"]
    assert len(rijen) == 1
    assert rijen[0]["commission_cents"] == 413 and rijen[0]["commission_pct"] == 25


@pytest.mark.asyncio
async def test_elke_maand_een_nieuwe_factuur_komt_erbij(cc, monkeypatch):
    db = _db()
    await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")]))
    uit = await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1"), _factuur("in_2")]))
    assert uit["nieuw"] == 1
    assert sum(r["commission_cents"] for r in db.data["creator_commissie"]) == 826


# ── 3. Teruggave, oude bounty, uitbetaald ───────────────────────────────────

@pytest.mark.asyncio
async def test_volledige_teruggave_geeft_nul_commissie(cc, monkeypatch):
    db = _db()
    await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")], {"in_1": 1999}))
    assert db.data["creator_commissie"][0]["commission_cents"] == 0


@pytest.mark.asyncio
async def test_teruggave_na_de_eerste_ronde_haalt_commissie_alsnog_weg(cc, monkeypatch):
    db = _db()
    await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")]))
    assert db.data["creator_commissie"][0]["commission_cents"] == 413
    await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")], {"in_1": 1999}))
    assert db.data["creator_commissie"][0]["commission_cents"] == 0


@pytest.mark.asyncio
async def test_code_met_oude_bounty_krijgt_geen_commissie(cc, monkeypatch):
    db = _db(pct=0)
    uit = await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")]))
    assert db.data["creator_commissie"] == [] and uit["nieuw"] == 0


@pytest.mark.asyncio
async def test_uitbetaald_is_bevroren(cc, monkeypatch):
    oud = {"invoice_id": "in_1", "code": CREATOR, "referred_user_id": KLANT,
           "paid_at": (NU - timedelta(days=90)).isoformat(), "bruto_cents": 1999,
           "netto_cents": 1652, "terugbetaald_cents": 0, "commission_pct": 25,
           "commission_cents": 413, "status": "uitbetaald", "uitbetaling_ref": "bank"}
    db = _db(rijen=[oud])
    # Zelfs een latere volledige teruggave verandert een uitbetaalde regel niet.
    await _ronde(cc, monkeypatch, db, NepStripe([_factuur("in_1")], {"in_1": 1999}))
    assert db.data["creator_commissie"][0]["commission_cents"] == 413


def test_uitbetaalbaar_pas_na_zestig_dagen(cc):
    def rij(dagen):
        return {"status": "open", "paid_at": (NU - timedelta(days=dagen)).isoformat()}
    assert not cc.uitbetaalbaar(rij(59))
    assert cc.uitbetaalbaar(rij(60))
    assert not cc.uitbetaalbaar({**rij(90), "status": "uitbetaald"})


# ── 4. Een Stripe-object van de gepinde SDK én van een nieuwe SDK ───────────

def test_leest_echte_stripe_objecten_van_beide_sdkversies(cc):
    import stripe
    f = stripe.Invoice.construct_from(_factuur("in_9"), "sk_test")
    assert cc.netto_van_factuur(f) == (1999, 1652)
