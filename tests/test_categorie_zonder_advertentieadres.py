"""Zilverwebsite / Amanda, 30-08 en 05-09-2026: "hij zet deze in de verkeerde categorie".

Bij een verversing haalt de server vlak vóór het verwijderen op in welke
categorie de advertentie ECHT staat, zodat ze daar ook weer terugkomt. Dat werkt
alleen zolang we haar adres kennen. Van een advertentie die WIJ hebben geplaatst
kennen we alleen /seller/view/{nummer}, en die pagina is alleen zichtbaar voor
wie is ingelogd: `advertentie_kenmerken` weigert zo'n adres en geeft een leeg
blok terug. Het herplaatsen viel dan terug op de categorie die ooit uit de titel
is geráden.

GEMETEN IN ZIJN EIGEN GEGEVENS (05-09-2026). Van zijn 968 lopende Marktplaats-
advertenties staan er 398 op zo'n adres, allemaal geplaatst na 19-08. Van die
398 zouden er bij de volgende verversing 82 in een andere categorie terechtkomen
dan waar ze nu staan, en 3 zouden helemaal niet geplaatst kunnen worden omdat
onze eigen lijst hun categorie niet kent.

De openbare zoek-API van Marktplaats kent die advertenties wél, mét het echte
adres (vipUrl). Hier wordt die terugval beproefd, zonder Marktplaats en zonder
database.

Draaien: python -m pytest tests/test_categorie_zonder_advertentieadres.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services import mp_enrich as M


# Letterlijk het antwoord van de openbare zoek-API op 05-09-2026, ingekort tot
# de velden die we gebruiken (verkoper 50417501 = Zilverwebsite).
ADVERTENTIE = {
    "itemId": "m2439448829",
    "title": "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
    "priceInfo": {"priceCents": 12500, "priceType": "FIXED"},
    "sellerInformation": {"sellerId": 50417501, "sellerName": "Zilverwebsite"},
    "categoryId": 13,
    "vipUrl": "/v/sieraden-tassen-en-uiterlijk/antieke-sieraden/m2439448829-zilveren-bijbelslot-broche",
}
# En wat de advertentiepagina zelf prijsgeeft.
PAGINA = ('...{"l1CategoryId":1826,"l1CategoryName":"Sieraden, Tassen en Uiterlijk",'
          '"l2CategoryId":13,"l2CategoryName":"Antieke sieraden"}...'
          '"priceInfo":{"priceCents":12500,"priceType":"FIXED"}...')

VERKOPERSPAGINA = "https://www.marktplaats.nl/seller/view/m2439448829"


class NepDb:
    """Alleen wat _verkopersnummer vraagt: de titels waaronder we plaatsten."""
    def __init__(self, titels): self._titels = titels
    def table(self, _naam): return self
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self):
        class R: pass
        r = R(); r.data = [{"payload": {"title": t}} for t in self._titels]
        return r


TWEEDE = dict(ADVERTENTIE, title="Zilveren lepel, L.J. Leendertsen, Middelburg",
              itemId="m2439448830")


ADVERTENTIE_LIJST = [ADVERTENTIE, TWEEDE]


def _nep_netwerk(monkeypatch, catalogus=None, pagina=PAGINA, gezocht=None):
    """Zoek-API en advertentiepagina nabouwen; onthoudt welke adressen we vroegen.

    De echte API geeft alleen advertenties terug die op de zoekterm lijken, en
    daar hangt alles aan: het verkopersnummer wordt pas aangenomen als twee
    VERSCHILLENDE titels hetzelfde nummer aanwijzen.
    """
    gezocht = gezocht if gezocht is not None else []
    aanbod = ADVERTENTIE_LIJST if catalogus is None else catalogus

    async def nep_json(client, url, params=None):
        gezocht.append(url)
        vraag = M._sleutel((params or {}).get("query") or "")
        rijen = [a for a in aanbod if not vraag or M._sleutel(a["title"]) == vraag]
        return {"listings": rijen}

    async def nep_pagina(client, url):
        gezocht.append(url)
        return pagina

    class NepClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(M, "_json", nep_json)
    monkeypatch.setattr(M, "_pagina", nep_pagina)
    monkeypatch.setattr(M.httpx, "AsyncClient", lambda *a, **k: NepClient())
    M._VERKOPERNUMMERS.clear()
    return gezocht


def test_de_oude_weg_kan_een_verkoperspagina_niet_lezen():
    """Dit is de storing zelf: het adres dat wij bewaren geeft geen kenmerken."""
    uit = asyncio.run(M.advertentie_kenmerken(VERKOPERSPAGINA))
    assert uit == {}


def test_de_advertentie_wordt_alsnog_gevonden_op_titel(monkeypatch):
    _nep_netwerk(monkeypatch)
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
                "Zilveren lepel, L.J. Leendertsen, Middelburg"])
    uit = asyncio.run(M.kenmerken_via_zoeken(
        db, "u1", "marktplaats", "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek"))
    assert uit["mp_category"]["l1"] == 1826
    assert uit["mp_category"]["l2"] == 13          # Antieke sieraden
    assert uit["mp_category"]["l2_naam"] == "Antieke sieraden"
    # De prijsvorm komt in dezelfde ronde mee, net als bij een leesbaar adres.
    assert uit["mp_prijstype"]["soort"] == "FIXED"


def test_2dehands_wordt_op_zijn_eigen_adres_gezocht(monkeypatch):
    gezocht = _nep_netwerk(monkeypatch)
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
                "Zilveren lepel, L.J. Leendertsen, Middelburg"])
    asyncio.run(M.kenmerken_via_zoeken(
        db, "u1", "2dehands", "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek"))
    assert any("2dehands.be" in u for u in gezocht)
    assert not any("marktplaats.nl" in u for u in gezocht)


def test_een_onbekend_platform_doet_niets(monkeypatch):
    gezocht = _nep_netwerk(monkeypatch)
    db = NepDb(["Iets"])
    assert asyncio.run(M.kenmerken_via_zoeken(db, "u1", "vinted", "Iets")) == {}
    assert gezocht == []


def test_geen_verkopersnummer_is_geen_fout(monkeypatch):
    """Eén stem is te weinig: dan weten we het niet, en blijft alles bij het oude."""
    _nep_netwerk(monkeypatch, catalogus=[ADVERTENTIE])
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek"])
    assert asyncio.run(M.kenmerken_via_zoeken(db, "u1", "marktplaats",
                                              "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek")) == {}


def test_een_titel_die_er_niet_bij_staat_levert_niets_op(monkeypatch):
    _nep_netwerk(monkeypatch)
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
                "Zilveren lepel, L.J. Leendertsen, Middelburg"])
    uit = asyncio.run(M.kenmerken_via_zoeken(db, "u1", "marktplaats", "Iets heel anders"))
    assert uit == {}


def test_het_verkopersnummer_wordt_maar_een_keer_opgezocht(monkeypatch):
    gezocht = _nep_netwerk(monkeypatch)
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
                "Zilveren lepel, L.J. Leendertsen, Middelburg"])
    titel = "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek"
    asyncio.run(M.kenmerken_via_zoeken(db, "u1", "marktplaats", titel))
    eerste = len(gezocht)
    asyncio.run(M.kenmerken_via_zoeken(db, "u1", "marktplaats", titel))
    # De tweede ronde kost alleen nog de zoekopdracht en de pagina, geen
    # zoektocht naar het verkopersnummer meer.
    assert len(gezocht) - eerste == 2


def test_een_kapotte_pagina_kost_geen_advertentie(monkeypatch):
    _nep_netwerk(monkeypatch, pagina="niets bruikbaars")
    db = NepDb(["Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek",
                "Zilveren lepel, L.J. Leendertsen, Middelburg"])
    uit = asyncio.run(M.kenmerken_via_zoeken(db, "u1", "marktplaats",
                                             "Zilveren bijbelslot broche, Wed. W. Roelfsema, Sneek"))
    assert uit.get("mp_category") in (None, {})
