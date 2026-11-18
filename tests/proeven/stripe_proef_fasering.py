"""Proef in Stripe-TESTMODUS voor de fasering van de grote drie (29,99, 39, 49).

Draai met de gepinde server-SDK en met de nieuwste:
  /usr/bin/python3 tests/proeven/stripe_proef_fasering.py      (stripe 10.12.0)
  python3.13 tests/proeven/stripe_proef_fasering.py            (stripe 15.x)
Sleutel: ~/.omnivaleur/stripe-test.txt (sk_test_...). Weigert elke andere sleutel.
Zet de tijd vooruit met een testklok tot na de laatste stap en leest de facturen.
Raakt nooit echte klanten; ruimt klok, klant en coupons op.
"""
import sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import stripe

sleutel = (Path.home() / ".omnivaleur" / "stripe-test.txt").read_text().strip()
assert sleutel.startswith("sk_test_"), "alleen testsleutel"
stripe.api_key = sleutel
assert stripe.Balance.retrieve()["livemode"] is False

from backend.config import settings
from backend.services import fasering, plannen

print("SDK", stripe.VERSION)
fouten = []


def check(naam, waar, detail=""):
    print(("OK   " if waar else "FOUT ") + naam + (f"  ({detail})" if detail else ""))
    if not waar:
        fouten.append(naam)


def d(o):
    return o.to_dict() if hasattr(o, "to_dict") else dict(o)


prod = stripe.Product.create(name="proef fasering")
pro = stripe.Price.create(unit_amount=1999, currency="eur", recurring={"interval": "month"}, product=prod["id"])
ultra = stripe.Price.create(unit_amount=4900, currency="eur", recurring={"interval": "month"}, product=prod["id"])
settings.stripe_price_id = pro["id"]
settings.stripe_price_id_ultra = ultra["id"]
check("plan uit Ultra-prijs is ultra", plannen.plan_uit_prijs_id(ultra["id"]) == "ultra")

coupons = []
klok = None
try:
    start = int(time.time())
    klok = stripe.test_helpers.TestClock.create(frozen_time=start, name="proef fasering")
    c = stripe.Customer.create(name="proef grote klant", test_clock=klok["id"])
    pm = stripe.PaymentMethod.attach("pm_card_visa", customer=c["id"])
    stripe.Customer.modify(c["id"], invoice_settings={"default_payment_method": pm["id"]})
    sub = stripe.Subscription.create(customer=c["id"], items=[{"price": pro["id"]}])

    # Precies wat scripts/fasering_grote_drie.py doet.
    for k in fasering.benodigde_kortingen():
        cid = fasering.coupon_id(k)
        try:
            stripe.Coupon.retrieve(cid)
        except stripe.InvalidRequestError:
            stripe.Coupon.create(id=cid, amount_off=k, currency="eur", duration="forever", name=f"proef {k}")
        coupons.append(cid)
    schema = stripe.SubscriptionSchedule.create(from_subscription=sub["id"])
    fase0 = d(schema)["phases"][0]
    fasen = fasering.fasen_voor(fase0, ultra["id"], nu=datetime.fromtimestamp(start, tz=timezone.utc))
    stripe.SubscriptionSchedule.modify(schema["id"], end_behavior="release", phases=fasen)
    gelezen = d(stripe.SubscriptionSchedule.retrieve(schema["id"]))
    check("schema heeft vier fasen", len(gelezen["phases"]) == 4, str(len(gelezen["phases"])))

    def vooruit(tot):
        stripe.test_helpers.TestClock.advance(klok["id"], frozen_time=int(tot.timestamp()))
        for _ in range(90):
            if d(stripe.test_helpers.TestClock.retrieve(klok["id"]))["status"] == "ready":
                return
            time.sleep(1)
        raise RuntimeError("klok niet klaar")

    # Elke stap hoogstens twee factuurperiodes, anders weigert Stripe.
    nu = datetime.fromtimestamp(start, tz=timezone.utc)
    for tot in ("2026-12-28", "2027-02-10", "2027-04-05", "2027-05-25", "2027-07-15", "2027-08-25"):
        vooruit(datetime.fromisoformat(tot).replace(tzinfo=timezone.utc))

    fac = sorted(d(stripe.Invoice.list(customer=c["id"], limit=24)).get("data", []), key=lambda f: f["created"])
    print("Facturen (datum, voor korting, na korting excl. btw, totaal):")
    reeks = []
    for f in fac:
        dt = datetime.fromtimestamp(f["created"], tz=timezone.utc).strftime("%Y-%m-%d")
        print("  ", dt, f["subtotal"], f["total_excluding_tax"], f["total"], f["status"])
        reeks.append((dt, f["total_excluding_tax"]))
    bedragen = [b for _, b in reeks]
    # Verwacht: eerste factuur direct (Pro 19,99), dan maandelijks.
    check("eerste factuur is Pro 19,99", bedragen[0] == 1999, str(bedragen[:1]))
    na_jan = [b for dt, b in reeks if "2027-01-01" <= dt < "2027-04-01"]
    na_apr = [b for dt, b in reeks if "2027-04-01" <= dt < "2027-07-01"]
    na_jul = [b for dt, b in reeks if dt >= "2027-07-01"]
    check("januari tot en met maart: 29,99", na_jan and all(b == 2999 for b in na_jan), str(na_jan))
    check("april tot en met juni: 39", na_apr and all(b == 3900 for b in na_apr), str(na_apr))
    check("vanaf juli: 49", na_jul and all(b == 4900 for b in na_jul), str(na_jul))
    check("alle facturen betaald", all(f["status"] == "paid" for f in fac), str([f["status"] for f in fac]))
    s2 = d(stripe.Subscription.retrieve(sub["id"]))
    check("abonnement loopt door op Ultra", s2["items"]["data"][0]["price"]["id"] == ultra["id"])
    check("schema is losgelaten na de laatste fase", not s2.get("schedule"), str(s2.get("schedule")))
    check("geen korting meer na de laatste fase", not s2.get("discount"), str(s2.get("discount")))
finally:
    if klok:
        try:
            stripe.test_helpers.TestClock.delete(klok["id"])
        except Exception as e:  # noqa: BLE001
            print("klok niet verwijderd:", e)
    for cid in coupons:
        try:
            stripe.Coupon.delete(cid)
        except Exception:  # noqa: BLE001
            pass

print("\nKlaar:", "ALLES OK" if not fouten else f"{len(fouten)} FOUT(EN): {fouten}")
sys.exit(1 if fouten else 0)
