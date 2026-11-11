"""Proef in Stripe-TESTMODUS voor /api/billing/wijzig-plan (verschil betalen).

Draai met de gepinde server-SDK (stripe==10.12.0) en met de nieuwste:
  <venv>/bin/python tests/proeven/stripe_proef_planwissel.py
Sleutel: ~/.omnivaleur/stripe-test.txt (sk_test_...). Weigert elke andere sleutel.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import stripe
from types import SimpleNamespace
from fastapi import HTTPException
import backend.api.billing as b   # zet bij het importeren de echte sleutel uit .env: daarom hieronder pas

sleutel = (Path.home() / ".omnivaleur" / "stripe-test.txt").read_text().strip()
assert sleutel.startswith("sk_test_"), "alleen testsleutel"
stripe.api_key = sleutel          # NA de import van billing, anders praat de proef met de echte Stripe
assert stripe.Balance.retrieve()["livemode"] is False

print("SDK", stripe.VERSION)
fouten = []


def check(naam, waar, detail=""):
    print(("OK   " if waar else "FOUT ") + naam + (f"  ({detail})" if detail else ""))
    if not waar:
        fouten.append(naam)


prod = stripe.Product.create(name="proef planwissel")
def prijs(cent, interval):
    return stripe.Price.create(unit_amount=cent, currency="eur", recurring={"interval": interval},
                               product=prod["id"])["id"]
P = {"pro": prijs(1999, "month"), "pro_j": prijs(19900, "year"), "plus": prijs(2999, "month"),
     "plus_j": prijs(29900, "year"), "ultra": prijs(4900, "month")}
s = b.settings
s.stripe_secret_key = sleutel
s.nieuwe_plannen_aan = True
s.stripe_price_id, s.stripe_price_id_pro_jaar = P["pro"], P["pro_j"]
s.stripe_price_id_plus, s.stripe_price_id_plus_jaar = P["plus"], P["plus_j"]
s.stripe_price_id_ultra = P["ultra"]

c = stripe.Customer.create(name="proef planwissel")
try:
    pm = stripe.PaymentMethod.attach("pm_card_visa", customer=c["id"])
    stripe.Customer.modify(c["id"], invoice_settings={"default_payment_method": pm["id"]})
    sub = stripe.Subscription.create(customer=c["id"], items=[{"price": P["pro"]}])
    db_schrijf = []

    class Q:
        def update(self, v): db_schrijf.append(v); return self
        def eq(self, *a): return self
        def execute(self): return None
    b.get_db = lambda: SimpleNamespace(table=lambda t: Q())
    b._get_or_create_subscription = lambda uid: {"stripe_subscription_id": sub["id"]}
    b.invalidate_access_cache = lambda uid: None
    user = SimpleNamespace(id="proefgebruiker")

    def laatste_factuur():
        return stripe.Invoice.list(customer=c["id"], limit=1)["data"][0]

    def prijs_nu():
        return stripe.Subscription.retrieve(sub["id"])["items"]["data"][0]["price"]["id"]

    # 1. Pro maand naar Plus maand: alleen het verschil, meteen
    r = b.wijzig_plan(user=user, body={"plan": "plus"})
    f = laatste_factuur()
    check("pro naar plus: gelukt", r["changed"] and prijs_nu() == P["plus"])
    check("pro naar plus: verschil ongeveer 10,00 en betaald", abs(f["amount_paid"] - 1000) <= 5 and f["status"] == "paid",
          f"betaald {f['amount_paid']} cent, status {f['status']}")
    check("plan in onze rij bijgewerkt", db_schrijf and db_schrijf[-1]["plan"] == "plus")

    # 2. Plus maand naar Plus jaar: jaarprijs min tegoed voor wat er over is van de maand
    r = b.wijzig_plan(user=user, body={"plan": "plus", "interval": "year"})
    f = laatste_factuur()
    check("plus maand naar plus jaar: gelukt", r["changed"] and prijs_nu() == P["plus_j"])
    check("jaarfactuur ongeveer 299 min restant maand", 26800 <= f["amount_paid"] <= 27000 and f["status"] == "paid",
          f"betaald {f['amount_paid']} cent")

    # 3. Omlaag, terug naar maand, gelijke keuze: geweigerd, niets veranderd
    voor = prijs_nu()
    for body in ({"plan": "pro"}, {"plan": "plus"}, {"plan": "plus", "interval": "year"}):
        try:
            b.wijzig_plan(user=user, body=body)
            check(f"geweigerd {body}", False)
        except HTTPException as e:
            check(f"geweigerd {body}", e.status_code == 400)
    check("abonnement bleef ongemoeid", prijs_nu() == voor)

    # 4. Niet-bestaand plan en schakelaar uit
    s.nieuwe_plannen_aan = False
    try:
        b.wijzig_plan(user=user, body={"plan": "ultra"})
        check("schakelaar uit: geweigerd", False)
    except HTTPException as e:
        check("schakelaar uit: geweigerd", e.status_code == 503)
finally:
    try:
        stripe.Customer.delete(c["id"])
    except Exception:
        pass
    for p in P.values():
        try: stripe.Price.modify(p, active=False)
        except Exception: pass
    try: stripe.Product.modify(prod["id"], active=False)
    except Exception: pass

print("\nGEFAALD:" if fouten else "\nALLES OK", fouten or "")
sys.exit(1 if fouten else 0)
