"""Advertenties zonder vraagprijs: "Bieden", "Zie omschrijving" en "Gratis".

De Juiste Toon, 13-09-2026. Zijn advertentie "Schapenvachten diverse maten Luxe
modellen" staat op Marktplaats als "Zie omschrijving": de prijzen staan in de
tekst (35 tot 50 euro) en de vacht bepaalt het bedrag. Bij ons kwam die binnen
met prijs 0, en omdat wij een prijs verplicht stelden konden we hem niet meer
publiceren. Er zelf een verzinnen is erger dan niet plaatsen: met 35 euro erop
heeft elke koper recht op de duurste vacht voor de laagste prijs.

Deze proef draait de echte controle en de echte publicatieroute uit
backend/services/crosslist.py, met een nagebouwde database.

Draaien: python3 tests/prijsvorm-test.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import crosslist as cl

mislukt = 0


def check(naam, voorwaarde, uitleg=""):
    global mislukt
    if voorwaarde:
        print(f"  ok   {naam}")
        return
    mislukt += 1
    print(f"  FOUT {naam}{' — ' + str(uitleg) if uitleg else ''}")


ARTIKEL = {
    "id": "i1", "user_id": "u1",
    "title": "Schapenvachten diverse maten Luxe modellen",
    "description": "Prijzen 35 tot 50 euro", "photo_urls": ["https://x/1.jpg"],
    "category": "wonen vachten", "price": 0,
}


# ── 1. Wat er ontbreekt ──────────────────────────────────────────────────────
def proef_ontbrekende_velden():
    print("\nWanneer is een prijs verplicht:")
    check("zonder prijs en zonder vorm blijft het een gebrek",
          cl._missing_fields_per_platform(ARTIKEL, ["marktplaats"]) == {"marktplaats": ["price"]})
    for vorm in ("FAST_BID", "SEE_DESCRIPTION", "FREE"):
        check(f"met vorm {vorm} mag het zonder bedrag",
              cl._missing_fields_per_platform({**ARTIKEL, "price_type": vorm},
                                              ["marktplaats", "2dehands"]) == {},
              cl._missing_fields_per_platform({**ARTIKEL, "price_type": vorm},
                                              ["marktplaats", "2dehands"]))
    check("Vinted kent deze vormen niet, daar blijft een prijs verplicht",
          cl._missing_fields_per_platform({**ARTIKEL, "price_type": "SEE_DESCRIPTION"},
                                          ["vinted"]) == {"vinted": ["price"]})
    check("FIXED is gewoon een vraagprijs, dus die is dan wél nodig",
          cl._missing_fields_per_platform({**ARTIKEL, "price_type": "FIXED"},
                                          ["marktplaats"]) == {"marktplaats": ["price"]})
    check("een waarde die niet bestaat telt niet mee",
          cl._missing_fields_per_platform({**ARTIKEL, "price_type": "GOKJE"},
                                          ["marktplaats"]) == {"marktplaats": ["price"]})


# ── 2. De echte publicatieroute, met een nagebouwde database ─────────────────
class Antwoord:
    def __init__(self, data): self.data = data


class Vraag:
    def __init__(self, db, tabel): self.db, self.tabel, self.velden = db, tabel, None

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def in_(self, *a, **k): return self
    def is_(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self
    def gte(self, *a, **k): return self

    @property
    def not_(self): return self

    def insert(self, rij, *a, **k):
        self.db.geschreven.setdefault(self.tabel, []).append(rij)
        return _Klaar(Antwoord([rij]))

    def update(self, patch, *a, **k):
        self.db.bijgewerkt.setdefault(self.tabel, []).append(patch)
        return _Klaar(Antwoord([patch]))

    def execute(self):
        return Antwoord(self.db.rijen.get(self.tabel, []))


class _Klaar:
    """Een insert/update die pas bij execute() iets teruggeeft, net als postgrest."""
    def __init__(self, antwoord): self.antwoord = antwoord
    def eq(self, *a, **k): return self
    def execute(self): return self.antwoord


class NepDb:
    def __init__(self, rijen):
        self.rijen, self.geschreven, self.bijgewerkt = rijen, {}, {}

    def table(self, naam): return Vraag(self, naam)


async def publiceer(artikel, listings=None):
    """De echte publish_to_platforms, zonder database en zonder Marktplaats."""
    db = NepDb({"items": [artikel], "listings": listings or [], "jobs": []})
    cl.get_db = lambda: db

    async def _exec(vraag, *a, **k):
        uit = vraag.execute()
        return uit

    cl._exec = _exec
    # De verkoperinstellingen horen niet bij deze proef.
    import backend.services.instellingen as inst
    inst.fabrikant = lambda uid: {}
    inst.fabrikant_verplicht = lambda uid: False
    inst.verzendkeuzes = lambda uid, prijs=None: {}
    inst.locatie = lambda uid: {}
    cl.slottekst_van = lambda uid: ""
    await cl.publish_to_platforms(artikel["id"], ["marktplaats"], artikel["user_id"])
    return db


def proef_opdracht():
    print("\nWat er in de opdracht voor de extensie komt te staan:")
    db = asyncio.run(publiceer({**ARTIKEL, "price_type": "SEE_DESCRIPTION"}))
    banen = db.geschreven.get("jobs", [])
    check("er staat één publicatie klaar", len(banen) == 1, banen)
    lading = (banen[0] if banen else {}).get("payload") or {}
    check("met de prijsvorm erin",
          (lading.get("mp_prijstype") or {}).get("soort") == "SEE_DESCRIPTION",
          lading.get("mp_prijstype"))
    check("en zonder bedrag, anders kiest het formulier alsnog Vraagprijs",
          lading.get("price") == 0, lading.get("price"))

    db2 = asyncio.run(publiceer({**ARTIKEL, "price": 25.0}))
    lading2 = (db2.geschreven.get("jobs", [{}])[0]).get("payload") or {}
    check("een gewone vraagprijs krijgt géén prijsvorm mee",
          "mp_prijstype" not in lading2 and lading2.get("price") == 25.0,
          lading2.get("mp_prijstype"))


# ── 3. De vorm terughalen van een advertentie die nog draait ────────────────
def proef_herstel():
    print("\nDe vorm overnemen van zijn eigen, nog draaiende advertentie:")
    db = NepDb({"listings": [{"platform": "2dehands", "status": "active",
                              "platform_listing_url": "https://www.2dehands.be/v/x/m2282395812"}]})

    async def _exec(vraag, *a, **k): return vraag.execute()
    cl._exec = _exec

    import backend.services.mp_enrich as enrich

    async def nep_kenmerken(url):
        return {"mp_category": {}, "mp_prijstype": {"soort": "SEE_DESCRIPTION", "cents": 0}}
    enrich.advertentie_kenmerken = nep_kenmerken
    from backend import database as dbmod
    dbmod._KOLOM_BEKEND[("items", "price_type")] = False   # migratie nog niet gedraaid

    uit = asyncio.run(cl._prijsvorm_uit_eigen_advertentie(db, dict(ARTIKEL)))
    check("de vorm komt van de advertentie zelf", uit.get("price_type") == "SEE_DESCRIPTION", uit.get("price_type"))
    check("en er wordt niets weggeschreven zolang de kolom niet bestaat",
          not db.bijgewerkt.get("items"), db.bijgewerkt)

    dbmod._KOLOM_BEKEND[("items", "price_type")] = True
    db2 = NepDb({"listings": [{"platform": "marktplaats", "status": "active",
                               "platform_listing_url": "https://www.marktplaats.nl/v/x/m2400185992"}]})
    asyncio.run(cl._prijsvorm_uit_eigen_advertentie(db2, dict(ARTIKEL)))
    check("met kolom wordt hij wél onthouden",
          db2.bijgewerkt.get("items") == [{"price_type": "SEE_DESCRIPTION"}], db2.bijgewerkt)

    async def geen_kenmerken(url): return {}
    enrich.advertentie_kenmerken = geen_kenmerken
    uit3 = asyncio.run(cl._prijsvorm_uit_eigen_advertentie(db2, dict(ARTIKEL)))
    check("zegt de pagina niets, dan verzinnen we niets",
          not uit3.get("price_type"), uit3.get("price_type"))


proef_ontbrekende_velden()
proef_opdracht()
proef_herstel()
print(f"\n{mislukt} controle(s) mislukt" if mislukt else "\nAlles in orde")
sys.exit(1 if mislukt else 0)
