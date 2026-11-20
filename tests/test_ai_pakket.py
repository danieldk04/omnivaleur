"""AI-pakket: bulkopdracht, veiligheid, ongedaan maken, plafond, vlag uit.

De kern die bewezen wordt: het model mag zich vergissen, maar een vergissing
wordt nooit uitgevoerd. De misser van 19-11 ("1 euro erbij" werd prijs_vast 1)
is hier een test, en hij gaat rood zodra `controleer` eruit is.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import ai_pakket as route
from backend.api.deps import get_current_user
from backend.config import settings
from backend.services import ai_bulk, ai_quota, ai_tekst, instellingen


def ok(opdracht, antwoord):
    bew = ai_bulk.valideer(json.dumps(antwoord))
    return None if bew is None else ai_bulk.controleer(opdracht, bew)


# ── het model kiest, gewone code controleert ────────────────────────────────

def test_de_misser_van_19_11_wordt_geweigerd():
    # Het model zei prijs_vast 1; de klant bedoelde 1 euro erbij.
    assert ok("1 euro erbij", {"actie": "prijs_vast", "kanaal": "alle", "waarde": 1}) is not None


def test_goede_prijsopdrachten_komen_door():
    assert ok("1 euro erbij", {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": 1}) is None
    assert ok("alles 10% hoger", {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10}) is None
    assert ok("2,50 eraf", {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": -2.5}) is None
    assert ok("zet de prijs op 15 euro", {"actie": "prijs_vast", "kanaal": "alle", "waarde": 15}) is None


def test_verkeerd_teken_wordt_geweigerd():
    assert ok("3 euro eraf", {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": 3}) is not None
    assert ok("10% omhoog", {"actie": "prijs_procent", "kanaal": "alle", "waarde": -10}) is not None


def test_verzonnen_bedrag_of_zonder_richting_wordt_geweigerd():
    assert ok("prijzen een beetje omhoog", {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10}) is not None
    assert ok("prijs met 1 euro", {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": 1}) is not None


@pytest.mark.parametrize("antwoord", [
    "[]", "kapot{", '[{"actie":"prijs_procent","waarde":10},{"actie":"tekst_toevoegen","tekst":"x"}]',
    '{"actie":"onbekend"}', '{"actie":"verwijder_alles"}', '{"actie":"prijs_procent","waarde":0}',
    '{"actie":"prijs_procent","waarde":500}', '{"actie":"prijs_procent","waarde":true}',
    '{"actie":"prijs_vast","waarde":0.5}', '{"actie":"prijs_vast","waarde":-3}',
    '{"actie":"tekst_verwijderen"}', '{"actie":"tekst_toevoegen","tekst":""}',
    '{"actie":"prijs_procent","kanaal":"bol","waarde":5}'])
def test_ongeldig_antwoord_wordt_nooit_een_bewerking(antwoord):
    assert ai_bulk.valideer(antwoord) is None


def test_tekst_die_niet_in_de_opdracht_staat_wordt_geweigerd():
    antw = {"actie": "tekst_toevoegen", "tekst": "Gratis verzending", "veld": "beschrijving"}
    assert ok("zet onderaan 'Rookvrij huis'", antw) is not None
    assert ok("zet onderaan 'Gratis verzending'", antw) is None


def test_vraag_model_weigert_twee_bewerkingen_en_storing(monkeypatch):
    from backend.services import taalmodel
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: '[{"actie":"prijs_procent","waarde":10}]')
    assert ai_bulk.vraag_model("10% erbij en tekst toevoegen") == (None, "onduidelijk")

    def stuk(*a, **k):
        raise taalmodel.TaalmodelOnbeschikbaar("x")
    monkeypatch.setattr(taalmodel, "vraag", stuk)
    assert ai_bulk.vraag_model("10% erbij")[1] == "storing"


# ── voorbeeld, afronding en bewakers ────────────────────────────────────────

ITEMS = [
    {"id": "a", "title": "Rode jas nieuw", "description": "Mooie jas, maat M", "price": 10.0,
     "price_vinted": 12.0, "price_marktplaats": None},
    {"id": "b", "title": "Blauwe broek", "description": "Broek", "price": 1.5,
     "price_vinted": None, "price_marktplaats": None},
]


def test_prijs_procent_alle_kanalen_rondt_af():
    p = ai_bulk.plan(ITEMS, {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10})
    d = {(x["id"], x["veld"]): x["nieuw"] for x in p["wijzigingen"]}
    assert d == {("a", "price"): 11.0, ("a", "price_vinted"): 13.2, ("b", "price"): 1.65}


def test_prijs_per_kanaal_raakt_alleen_dat_kanaal():
    p = ai_bulk.plan(ITEMS, {"actie": "prijs_bedrag", "kanaal": "vinted", "waarde": 1})
    assert {(x["id"], x["veld"]): x["nieuw"] for x in p["wijzigingen"]} == {
        ("a", "price_vinted"): 13.0, ("b", "price_vinted"): 2.5}


def test_onder_een_euro_en_verdubbeling_vragen_extra_bevestiging():
    v = ai_bulk.voorbeeld(ITEMS, {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": -1})
    assert v["extra_bevestiging"] and v["onder_1"] == 1      # 1,50 wordt 0,50
    v = ai_bulk.voorbeeld(ITEMS, {"actie": "prijs_procent", "kanaal": "alle", "waarde": 150})
    assert v["extra_bevestiging"] and v["dubbel"] >= 1
    v = ai_bulk.voorbeeld(ITEMS, {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10})
    assert not v["extra_bevestiging"]


def test_voorbeeld_toont_hooguit_vijf_artikelen_en_het_totaal():
    items = [{"id": str(i), "title": f"t{i}", "price": 10.0} for i in range(40)]
    v = ai_bulk.voorbeeld(items, {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10})
    assert v["artikelen"] == 40 and len(v["voorbeeld"]) == 5


def test_tekst_bewerkingen():
    toe = ai_bulk.plan(ITEMS, {"actie": "tekst_toevoegen", "kanaal": "alle", "veld": "beschrijving",
                               "tekst": "Rookvrij", "positie": "einde"})
    assert toe["wijzigingen"][0]["nieuw"] == "Mooie jas, maat M\nRookvrij"
    weg = ai_bulk.plan(ITEMS, {"actie": "tekst_verwijderen", "kanaal": "alle", "veld": "titel", "zoek": "NIEUW"})
    assert [x["nieuw"] for x in weg["wijzigingen"]] == ["Rode jas"]
    lang = ai_bulk.plan([{"id": "x", "title": "a" * 98}], {"actie": "tekst_toevoegen", "kanaal": "alle",
                        "veld": "titel", "tekst": "bbbbb", "positie": "einde"})
    assert lang["wijzigingen"] == [] and lang["te_lang"] == 1


def test_ongedaan_blok_te_groot_wordt_geweigerd():
    w = [{"id": str(i), "veld": "description", "oud": "x" * 2000, "nieuw": "y" * 2000} for i in range(500)]
    assert ai_bulk.ongedaan_blok(w) is None
    assert ai_bulk.ongedaan_blok(w[:50]) is not None


# ── de routes, met een nep-database ─────────────────────────────────────────

class Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.upd, self.lim = db, tabel, [], None, None

    def select(self, *_): return self
    def order(self, *_): return self
    def eq(self, k, v): self.f.append(lambda r: r.get(k) == v); return self
    def in_(self, k, vs): self.f.append(lambda r: r.get(k) in vs); return self
    def range(self, a, b): self.lim = (a, b); return self
    def update(self, d): self.upd = d; return self

    def execute(self):
        rijen = [r for r in self.db.rijen if all(f(r) for f in self.f)]
        if self.upd is not None:
            for r in rijen:
                r.update(self.upd)
            return type("R", (), {"data": [dict(r) for r in rijen]})
        if self.lim:
            rijen = rijen[self.lim[0]:self.lim[1] + 1]
        return type("R", (), {"data": [dict(r) for r in rijen]})


class Db:
    def __init__(self, rijen): self.rijen = rijen
    def table(self, naam): return Q(self, naam)


@pytest.fixture
def omgeving(monkeypatch):
    rijen = [{"id": "a", "user_id": "u1", "title": "Rode jas", "description": "Jas", "price": 10.0,
              "price_vinted": None, "price_marktplaats": None, "price_2dehands": None,
              "price_ebay": None, "price_shopify": None, "price_woocommerce": None},
             {"id": "z", "user_id": "ander", "title": "Andermans jas", "description": "x", "price": 10.0}]
    db = Db(rijen)
    winkel: dict = {}
    monkeypatch.setattr(route, "get_db", lambda: db)
    monkeypatch.setattr(instellingen, "lees", lambda u: {"ai_pakket": winkel.get(u)} if winkel.get(u) else {})
    monkeypatch.setattr(instellingen, "schrijf", lambda u, w: winkel.__setitem__(u, w["ai_pakket"]))
    monkeypatch.setattr(route, "_prijzen_doorgeven", _geen_taak)
    app = FastAPI()
    app.include_router(route.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: "u1"
    return TestClient(app), rijen, winkel


async def _geen_taak(*a, **k):
    return None


def modelzegt(monkeypatch, antwoord):
    from backend.services import taalmodel
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: json.dumps(antwoord))


def test_vlag_uit_is_overal_404_en_er_gebeurt_niets(omgeving, monkeypatch):
    client, rijen, winkel = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", False)
    called = []
    from backend.services import taalmodel
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: called.append(1) or "{}")
    for pad in ("/api/ai-pakket/bulk/voorbeeld", "/api/ai-pakket/bulk/uitvoeren", "/api/ai-pakket/bulk/ongedaan"):
        assert client.post(pad, json={"opdracht": "10% erbij"}).status_code == 404
    assert client.get("/api/ai-pakket/status").status_code == 404
    assert not called and not winkel and rijen[0]["price"] == 10.0


def test_voorbeeld_uitvoeren_ongedaan_en_vreemde_artikelen_blijven_heel(omgeving, monkeypatch):
    client, rijen, winkel = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    modelzegt(monkeypatch, {"actie": "prijs_procent", "kanaal": "alle", "waarde": 10})
    v = client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "alles 10% hoger"}).json()
    assert v["uitvoerbaar"] and v["artikelen"] == 1 and rijen[0]["price"] == 10.0   # voorbeeld schrijft niets
    # zonder bevestiging gebeurt niets
    assert client.post("/api/ai-pakket/bulk/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"]}).status_code == 400
    assert rijen[0]["price"] == 10.0
    r = client.post("/api/ai-pakket/bulk/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).json()
    assert r["gewijzigd"] == 1 and rijen[0]["price"] == 11.0 and rijen[1]["price"] == 10.0
    # hetzelfde voorbeeld nog eens gebruiken kan niet
    assert client.post("/api/ai-pakket/bulk/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).status_code == 409
    # klant past daarna zelf een andere prijs aan: ongedaan maken laat die staan
    u = client.post("/api/ai-pakket/bulk/ongedaan", json={"ongedaan_id": r["ongedaan_id"]}).json()
    assert u["teruggezet"] == 1 and rijen[0]["price"] == 10.0
    assert client.post("/api/ai-pakket/bulk/ongedaan", json={"ongedaan_id": r["ongedaan_id"]}).status_code == 404


def test_ongedaan_laat_een_latere_eigen_wijziging_staan(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    modelzegt(monkeypatch, {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": 1})
    v = client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "1 euro erbij"}).json()
    r = client.post("/api/ai-pakket/bulk/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).json()
    rijen[0]["price"] = 25.0                      # de klant past zelf aan
    u = client.post("/api/ai-pakket/bulk/ongedaan", json={"ongedaan_id": r["ongedaan_id"]}).json()
    assert u == {"teruggezet": 0, "overgeslagen": 1} and rijen[0]["price"] == 25.0


def test_prijs_onder_een_euro_eist_extra_bevestiging(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    rijen[0]["price"] = 1.5
    modelzegt(monkeypatch, {"actie": "prijs_bedrag", "kanaal": "alle", "waarde": -1})
    v = client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "1 euro eraf"}).json()
    assert v["extra_bevestiging"]
    gewoon = client.post("/api/ai-pakket/bulk/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True})
    assert gewoon.status_code == 409 and rijen[0]["price"] == 1.5
    extra = client.post("/api/ai-pakket/bulk/uitvoeren",
                        json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True, "bevestig_extra": True})
    assert extra.status_code == 200 and rijen[0]["price"] == 0.5


def test_onduidelijke_opdracht_voert_niets_uit(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    modelzegt(monkeypatch, [{"actie": "prijs_procent", "kanaal": "alle", "waarde": 10}])
    v = client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "maak het mooier"}).json()
    assert v["begrepen"] is False and rijen[0]["price"] == 10.0


def test_maandplafond_overleeft_herstart_en_nieuwe_maand_begint_leeg(omgeving, monkeypatch):
    client, rijen, winkel = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    modelzegt(monkeypatch, {"actie": "onbekend"})
    for _ in range(ai_quota.PLAFOND["bulk"]):
        assert client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "x"}).status_code == 200
    assert client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "x"}).status_code == 429
    assert winkel["u1"]["bulk"] == ai_quota.PLAFOND["bulk"]      # staat in de opslag, niet in het geheugen
    monkeypatch.setattr(ai_quota, "maand", lambda: "2099-01")
    assert client.post("/api/ai-pakket/bulk/voorbeeld", json={"opdracht": "x"}).status_code == 200


def test_klant_kan_zijn_eigen_plafond_niet_zetten():
    import inspect
    from backend.api import items
    assert '"ai_pakket"' in inspect.getsource(items.write_settings)


# ── titels en beschrijvingen: de harde controle ─────────────────────────────

ITEM = {"id": "1", "title": "(658) Ralph Lauren Polo Heren Trui Navy Maat S Excellent", "brand": "Ralph Lauren",
        "color": "Blauw", "size": "S", "material": "Katoen", "description": "Trui, maat S, 100% katoen. Weinig gedragen."}


def test_titelcontrole():
    f = ai_tekst.titel_fout
    assert f(ITEM, "marktplaats", "(658) Ralph Lauren trui heren maat S katoen") is None
    assert "not in the item data" in f(ITEM, "marktplaats", "(658) Ralph Lauren trui prachtige maat S")
    assert "brand" in f(ITEM, "marktplaats", "(658) trui heren maat S")
    assert "code" in f(ITEM, "marktplaats", "Ralph Lauren trui (658) maat S")
    assert "'s' is missing" in f(ITEM, "marktplaats", "(658) Ralph Lauren trui heren")
    assert "longer" in f(ITEM, "marktplaats", "(658) Ralph Lauren Polo Heren Trui Navy Maat S Excellent Katoen Blauw")


def test_beschrijvingscontrole():
    f = ai_tekst.beschrijving_fout
    assert f(ITEM, "vinted", "Trui in maat S, 100% katoen. Weinig gedragen.") is None
    assert "numbers" in f(ITEM, "vinted", "Trui maat S, 100% katoen, 30 cm breed. Weinig gedragen.")
    assert "missing" in f(ITEM, "vinted", "Trui in maat S, katoen. Weinig gedragen.")
    assert "link" in f(ITEM, "vinted", "Trui maat S 100% katoen. Weinig gedragen. www.winkel.nl")
    assert "new words" in f(ITEM, "vinted", "Trui maat S 100% katoen. Weinig gedragen, prachtige zachte comfortabele "
                                           "stijlvolle tijdloze luxe uitstraling dus pakken")


def test_beschrijving_tweede_poging_krijgt_de_reden_en_mislukt_veilig(monkeypatch):
    from backend.services import taalmodel
    prompts = []

    def vraag(opdracht, **k):
        prompts.append(opdracht)
        return "Trui maat S, 100% katoen, 45 cm." if len(prompts) == 1 else "Trui maat S, 100% katoen. Weinig gedragen."
    monkeypatch.setattr(taalmodel, "vraag", vraag)
    nieuw, t = ai_tekst.herschrijf_beschrijving(ITEM, "vinted")
    assert nieuw and t == {"goed_2": 1} and "rejected because" in prompts[1]
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: "Trui 999 cm")
    assert ai_tekst.herschrijf_beschrijving(ITEM, "vinted")[0] is None      # oude tekst blijft staan


def test_titels_alleen_goedgekeurde_voorstellen_gaan_door(monkeypatch):
    from backend.services import taalmodel
    antw = iter([json.dumps(["(658) Ralph Lauren trui heren maat S"]),
                 json.dumps(["(658) Ralph Lauren trui heren maat S"])])
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: next(antw))
    uit, t = ai_tekst.zoekslimme_titels([ITEM], "marktplaats")
    assert uit == {"1": "(658) Ralph Lauren trui heren maat S"} and t["goed_1"] == 1
    monkeypatch.setattr(taalmodel, "vraag", lambda *a, **k: json.dumps(["Verzonnen luxe trui"]))
    uit, t = ai_tekst.zoekslimme_titels([ITEM], "marktplaats")
    assert uit == {} and t["afgekeurd"] == 1
