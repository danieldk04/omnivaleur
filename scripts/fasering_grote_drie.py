"""Zet de fasering (29,99, 39, 49) op het abonnement van een grote klant.

Gebruik (eerst altijd zonder --toepassen, dat laat alleen zien wat er zou gebeuren):
  python3 scripts/fasering_grote_drie.py sub_xxx [--ultra-prijs price_xxx] [--toepassen]

Besluit en regels: backend/services/fasering.py. Dit script raakt maar een abonnement
tegelijk, en alleen als dat abonnement nog geen schema heeft. Draai het nooit voor
een klant die Daniel niet heeft aangewezen.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stripe

from backend.config import settings
from backend.services import fasering


def zorg_voor_coupons():
    for k in fasering.benodigde_kortingen():
        cid = fasering.coupon_id(k)
        try:
            stripe.Coupon.retrieve(cid)
        except stripe.InvalidRequestError:
            stripe.Coupon.create(id=cid, amount_off=k, currency="eur", duration="forever",
                                 name=f"Fasering Ultra {k / 100:.2f} korting")


def main(arg):
    toepassen = "--toepassen" in arg
    ultra = settings.stripe_price_id_ultra
    if "--ultra-prijs" in arg:
        ultra = arg[arg.index("--ultra-prijs") + 1]
    subs = [a for a in arg if a.startswith("sub_")]
    if len(subs) != 1 or not ultra:
        print("Geef precies een abonnement (sub_...) en zorg voor de Ultra-prijs (--ultra-prijs).")
        return 2
    stripe.api_key = settings.stripe_secret_key
    sub = stripe.Subscription.retrieve(subs[0]).to_dict()
    if sub.get("schedule"):
        print("Dit abonnement heeft al een schema:", sub["schedule"], "Niets gedaan.")
        return 1
    if sub["status"] not in ("active", "trialing"):
        print("Status is", sub["status"], "niets gedaan.")
        return 1
    # Het schema maken kost niets en verandert de prijs niet; het wordt pas
    # betekenisvol als de fasen erop staan.
    huidig = {"start_date": sub["items"]["data"][0].get("current_period_start") or sub["start_date"],
              "items": [{"price": sub["items"]["data"][0]["price"]["id"],
                         "quantity": sub["items"]["data"][0].get("quantity", 1)}],
              "automatic_tax": sub.get("automatic_tax"), "default_tax_rates": sub.get("default_tax_rates")}
    print("Abonnement", sub["id"], "klant", sub["customer"], "prijs nu", huidig["items"][0]["price"])
    if not toepassen:
        for f in fasering.fasen_voor(huidig, ultra):
            print(" fase:", {k: v for k, v in f.items() if k != "items"}, "prijs", f["items"][0]["price"])
        print("Zonder --toepassen niets veranderd.")
        return 0
    zorg_voor_coupons()
    schema = stripe.SubscriptionSchedule.create(from_subscription=sub["id"])
    fase0 = schema.to_dict()["phases"][0]
    fasen = fasering.fasen_voor(fase0, ultra)
    stripe.SubscriptionSchedule.modify(schema["id"], end_behavior="release", phases=fasen)
    print("Schema", schema["id"], "gezet met", len(fasen), "fasen.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
