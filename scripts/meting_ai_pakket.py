"""Meet het AI-pakket op echte artikelen (alleen lezen). 20-11-2026.

Gebruik (gratis sleutel, nooit tonen):
  GOOGLE_API_KEY=$(cat ~/.omnivaleur/gemini-gratis.txt) python3.13 scripts/meting_ai_pakket.py steekproef
  ... bulk | titels | beschrijvingen | samenvatting

Leest per user_id (nooit jobs.result, nooit over klanten heen in een zware vraag),
schrijft niets naar de database. Wacht 5 s tussen modelvragen (gratis laag knijpt
bij ~15 per minuut). Uitkomsten in ~/.omnivaleur/meting_ai/.
"""
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MAP = Path.home() / ".omnivaleur" / "meting_ai"
MAP.mkdir(parents=True, exist_ok=True)
PAUZE = 5.0

BULK_TESTS = [  # (opdracht, verwacht (actie, kanaal, waarde of tekst) of None = moet geweigerd worden)
    ("alle prijzen 10% omhoog", ("prijs_procent", "alle", 10)),
    ("verhoog alles met 15 procent", ("prijs_procent", "alle", 15)),
    ("alles 5% goedkoper", ("prijs_procent", "alle", -5)),
    ("geef overal 20% korting", ("prijs_procent", "alle", -20)),
    ("prijzen op vinted 10% hoger", ("prijs_procent", "vinted", 10)),
    ("marktplaats 1 euro erbij", ("prijs_bedrag", "marktplaats", 1)),
    ("zet er overal 2 euro bij", ("prijs_bedrag", "alle", 2)),
    ("op 2dehands 50 cent erbij", ("prijs_bedrag", "2dehands", 0.5)),
    ("alle prijzen 3 euro eraf", ("prijs_bedrag", "alle", -3)),
    ("haal 1,50 van elke prijs af", ("prijs_bedrag", "alle", -1.5)),
    ("verhoog de prijzen op eBay met 4 euro", ("prijs_bedrag", "ebay", 4)),
    ("zet alle prijzen op 15 euro", ("prijs_vast", "alle", 15)),
    ("maak de vintedprijs 12,50", ("prijs_vast", "vinted", 12.5)),
    ("raise all prices by 10%", ("prijs_procent", "alle", 10)),
    ("add 2 euro to everything", ("prijs_bedrag", "alle", 2)),
    ("take 1 euro off all prices", ("prijs_bedrag", "alle", -1)),
    ("set the price to 20 euro", ("prijs_vast", "alle", 20)),
    ("voeg onderaan de beschrijving 'Verzending binnen 2 dagen' toe", ("tekst_toevoegen", "alle", "Verzending binnen 2 dagen")),
    ("zet 'Rookvrij huis' aan het begin van de beschrijving", ("tekst_toevoegen", "alle", "Rookvrij huis")),
    ("vervang 'Marktplaats' door 'online' in de beschrijving", ("tekst_vervangen", "alle", "Marktplaats")),
    ("verwijder het woord 'nieuw' uit de titels", ("tekst_verwijderen", "alle", "nieuw")),
    ("haal 'Zo goed als nieuw' weg uit de beschrijving", ("tekst_verwijderen", "alle", "Zo goed als nieuw")),
    ("vervang 'jas' door 'jack' in de titel", ("tekst_vervangen", "alle", "jas")),
    ("alles 10% omhoog en voeg 'Kijk ook mijn andere advertenties' toe", None),
    ("maak het mooier", None),
    ("verdubbel alle prijzen", None),
    ("verwijder alle artikelen", None),
    ("prijzen aanpassen", None),
    ("zet alles op 0", None),
    ("prijs met 1 euro", None),
]


def _db():
    from backend.database import get_db
    return get_db()


def steekproef(n_klanten=24, per_klant=7):
    db = _db()
    users = [r["user_id"] for r in db.table("platform_credentials").select("user_id")
             .eq("platform", "_settings").limit(300).execute().data]
    random.seed(20112026)
    random.shuffle(users)
    uit, klanten = [], 0
    for u in users:
        rijen = (db.table("items").select("id,user_id,title,description,brand,color,size,material,category,price")
                 .eq("user_id", u).order("created_at", desc=True).limit(40).execute().data or [])
        rijen = [r for r in rijen if r.get("title") and len(r.get("description") or "") > 40]
        if len(rijen) < 3:
            continue
        random.shuffle(rijen)
        uit.extend(rijen[:per_klant])
        klanten += 1
        if klanten >= n_klanten:
            break
    (MAP / "steekproef.json").write_text(json.dumps(uit, ensure_ascii=False))
    print(len(uit), "artikelen van", klanten, "klanten")


def _rem():
    from backend.services import taalmodel
    orig = taalmodel.vraag

    def traag(*a, **k):
        time.sleep(PAUZE)
        return orig(*a, **k)
    taalmodel.vraag = traag


def _tokens():
    from backend.services import gemini_vertaling as g
    return dict(g.TOKENS)


def bulk():
    from backend.services import ai_bulk
    _rem()
    uit = []
    for opdracht, verwacht in BULK_TESTS:
        for _ in range(3):  # storing of limiet: opnieuw, dat meet het model niet
            bew, reden = ai_bulk.vraag_model(opdracht)
            if reden != "storing":
                break
            time.sleep(20)
        if verwacht is None:
            oordeel = "goed_geweigerd" if bew is None else "GEVAARLIJK_uitgevoerd"
        elif bew is None:
            oordeel = "geweigerd_" + reden
        else:
            sleutel = "waarde" if verwacht[0].startswith("prijs") else ("tekst" if verwacht[0] == "tekst_toevoegen" else "zoek")
            w = bew.get(sleutel)
            klopt = (bew["actie"] == verwacht[0] and bew["kanaal"] == verwacht[1]
                     and (abs(float(w) - verwacht[2]) < 1e-9 if isinstance(verwacht[2], (int, float)) else str(w).lower() == str(verwacht[2]).lower()))
            oordeel = "goed" if klopt else "FOUT_uitgevoerd"
        uit.append({"opdracht": opdracht, "verwacht": verwacht, "bew": bew, "reden": reden, "oordeel": oordeel})
        print(oordeel, "|", opdracht)
    (MAP / "bulk.json").write_text(json.dumps(uit, ensure_ascii=False, indent=1))
    print(Counter(x["oordeel"] for x in uit), _tokens())


def titels():
    from backend.services import ai_tekst
    _rem()
    items = json.loads((MAP / "steekproef.json").read_text())
    uit = []
    tel = Counter()
    for kanaal in ("marktplaats", "vinted"):
        res, t = ai_tekst.zoekslimme_titels(items, kanaal)
        tel.update({f"{kanaal}_{k}": v for k, v in t.items()})
        for it in items:
            uit.append({"kanaal": kanaal, "id": it["id"], "oud": it["title"], "nieuw": res.get(it["id"]),
                        "merk": it.get("brand")})
        print(kanaal, t, _tokens())
    (MAP / "titels.json").write_text(json.dumps(uit, ensure_ascii=False, indent=1))
    print(tel)


def beschrijvingen():
    from backend.services import ai_tekst
    _rem()
    items = json.loads((MAP / "steekproef.json").read_text())
    uit = []
    tel = Counter()
    for it in items:
        kanaal = random.choice(["marktplaats", "vinted", "ebay"])
        nieuw, t = ai_tekst.herschrijf_beschrijving(it, kanaal)
        tel.update(t if "reden" not in t else {"afgekeurd": 1})
        uit.append({"kanaal": kanaal, "id": it["id"], "oud": it["description"], "nieuw": nieuw, **t})
        print(len(uit), dict(tel))
    (MAP / "beschrijvingen.json").write_text(json.dumps(uit, ensure_ascii=False, indent=1))
    print(tel, _tokens())


if __name__ == "__main__":
    opdracht = sys.argv[1] if len(sys.argv) > 1 else ""
    {"steekproef": steekproef, "bulk": bulk, "titels": titels, "beschrijvingen": beschrijvingen}[opdracht]()
