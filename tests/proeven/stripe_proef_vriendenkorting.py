"""Proef in Stripe-TESTMODUS voor de korting per betalende vriend.

Draai met de gepinde server-SDK (stripe==10.12.0) en met de nieuwste:
  <venv>/bin/python tests/proeven/stripe_proef_vriendenkorting.py
Sleutel: ~/.omnivaleur/stripe-test.txt (sk_test_...). Weigert elke andere sleutel.
Maakt eigen testklanten aan en ruimt ze op. Raakt nooit echte klanten.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import stripe

sleutel = (Path.home() / ".omnivaleur" / "stripe-test.txt").read_text().strip()
assert sleutel.startswith("sk_test_"), "alleen testsleutel"
stripe.api_key = sleutel
assert stripe.Balance.retrieve()["livemode"] is False

from backend.config import settings
from backend.services import referral_vriendenkorting as rv

print("SDK", stripe.VERSION)
gemaakt = []
fouten = []


def check(naam, waar, detail=""):
    print(("OK   " if waar else "FOUT ") + naam + (f"  ({detail})" if detail else ""))
    if not waar:
        fouten.append(naam)


def klant(naam, prijs):
    c = stripe.Customer.create(name=naam)
    gemaakt.append(c["id"])
    pm = stripe.PaymentMethod.attach("pm_card_visa", customer=c["id"])
    stripe.Customer.modify(c["id"], invoice_settings={"default_payment_method": pm["id"]})
    sub = stripe.Subscription.create(customer=c["id"], items=[{"price": prijs}])
    return c["id"], sub["id"]


def wacht_op_betaling(cid):
    for _ in range(20):
        if rv.facturen_van_klant(cid):
            return
        time.sleep(1)
    raise RuntimeError("factuur niet betaald")


prod = stripe.Product.create(name="proef vriendenkorting")
pro = stripe.Price.create(unit_amount=1999, currency="eur", recurring={"interval": "month"}, product=prod["id"])
light = stripe.Price.create(unit_amount=999, currency="eur", recurring={"interval": "month"}, product=prod["id"])
settings.stripe_price_id_light = light["id"]

try:
    R, Rsub = klant("proef aanbrenger", pro["id"])
    F1, F1sub = klant("proef vriend pro", pro["id"])
    F2, F2sub = klant("proef vriend light", light["id"])
    wacht_op_betaling(R); wacht_op_betaling(F1); wacht_op_betaling(F2)
    prijsR = rv.maandprijs_cents(stripe.Subscription.retrieve(Rsub))
    check("maandprijs aanbrenger uit abonnement", prijsR == 1999, str(prijsR))
    check("plan pro herkend", rv.plan_van_abonnement(stripe.Subscription.retrieve(F1sub)) == "pro")
    check("plan light herkend", rv.plan_van_abonnement(stripe.Subscription.retrieve(F2sub)) == "light")

    def ronde(vriend, plan, *, prijs=1999):
        return rv.verwerk_vriend(aanbrenger_klant_id=R, eigen_maandprijs_cents=prijs, vriend_id=vriend,
                                 vriend_plan=plan, facturen=rv.facturen_van_klant(vriend))

    f = rv.facturen_van_klant(F1)
    check("factuur van pro-vriend gelezen met bedrag 1999", len(f) == 1 and f[0]["bruto_cents"] == 1999, str(f))
    check("teruggave nul voor de refund", f[0]["terug_cents"] == 0)

    r1 = ronde(F1, "pro")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("pro-vriend geeft 999 tegoed", r1["toegekend"] == 999 and saldo == -999, f"{r1} saldo {saldo}")

    r2 = ronde(F1, "pro")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("tweede ronde geeft niets extra (geen dubbel)", r2["toegekend"] == 0 and saldo == -999, f"{r2} saldo {saldo}")

    r3 = ronde(F2, "light")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("light-vriend geeft niets", r3["toegekend"] == 0 and saldo == -999, f"{r3} saldo {saldo}")

    charge = [c for c in stripe.Charge.list(customer=F1, limit=5).auto_paging_iter()][0]
    stripe.Refund.create(charge=charge["id"])
    time.sleep(2)
    f = rv.facturen_van_klant(F1)
    check("teruggave wordt gelezen", f[0]["terug_cents"] == 1999, str(f))
    r4 = ronde(F1, "pro")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("volledige teruggave draait het tegoed terug", r4["teruggedraaid"] == 999 and saldo == 0, f"{r4} saldo {saldo}")
    r5 = ronde(F1, "pro")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("terugdraaien gebeurt maar een keer", r5["teruggedraaid"] == 0 and r5["toegekend"] == 0 and saldo == 0, f"{r5} saldo {saldo}")

    # Tegoed stapelt niet boven een maandprijs: nog twee pro-vrienden.
    F3, _ = klant("proef vriend pro 3", pro["id"]); F4, _ = klant("proef vriend pro 4", pro["id"])
    wacht_op_betaling(F3); wacht_op_betaling(F4)
    a = ronde(F3, "pro"); b = ronde(F4, "pro")
    saldo = stripe.Customer.retrieve(R)["balance"]
    check("tegoed blijft binnen een maandprijs", -saldo <= 1999 and a["toegekend"] == 999, f"{a} {b} saldo {saldo}")
finally:
    for cid in gemaakt:
        try:
            stripe.Customer.delete(cid)
        except Exception as e:
            print("opruimen mislukt", cid, e)
    try:
        stripe.Product.modify(prod["id"], active=False)
    except Exception:
        pass

print("\nALLES OK" if not fouten else f"\nFOUTEN: {fouten}")
sys.exit(1 if fouten else 0)
