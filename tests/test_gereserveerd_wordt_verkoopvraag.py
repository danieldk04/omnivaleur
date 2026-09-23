"""Gereserveerd op Marktplaats of 2dehands wordt de vraag "is dit verkocht?".

GEMETEN 23-09-2026 (De Juiste Toon). Zes lederhosen stonden gereserveerd op
Marktplaats; bij ons alle zes "live", vijf nog te koop op 2dehands. Zie
backend/services/gereserveerd.py.
"""
import asyncio

from backend.services import gereserveerd as G

REDEN, NEE = "reden-gereserveerd", "nee-gereserveerd"


def rij(nr, status="active", melding=None):
    return {"id": f"l-{nr}", "item_id": f"i-{nr}", "platform_listing_id": nr,
            "status": status, "error_message": melding}


def test_gereserveerd_wordt_een_vraag_en_de_rest_niet():
    lijst = {"m1": {"reserved": True}, "m2": {"reserved": False}, "m3": {}}
    vragen, intrekken, vergeten, te_veel = G.gereserveerd_beslissing(
        lijst, [rij("m1"), rij("m2"), rij("m3")], REDEN, NEE)
    assert [r["platform_listing_id"] for r in vragen] == ["m1"]
    assert intrekken == vergeten == [] and te_veel is False


def test_klaargezette_herplaatsing_telt_ook():
    vragen, *_ = G.gereserveerd_beslissing({"m1": {"reserved": True}},
                                           [rij("m1", "relisting")], REDEN, NEE)
    assert len(vragen) == 1


def test_reservering_vervallen_trekt_de_vraag_in():
    lijst = {"m1": {"reserved": False}}
    _, intrekken, _, _ = G.gereserveerd_beslissing(
        lijst, [rij("m1", "sold_unconfirmed", REDEN)], REDEN, NEE)
    assert [r["platform_listing_id"] for r in intrekken] == ["m1"]
    # Een vraag met een ANDERE reden (verdwenen, label) blijft staan.
    _, intrekken, _, _ = G.gereserveerd_beslissing(
        lijst, [rij("m1", "sold_unconfirmed", "Mogelijk verkocht: weg")], REDEN, NEE)
    assert intrekken == []


def test_nee_wordt_niet_opnieuw_gevraagd_tot_de_reservering_weg_is():
    vragen, *_ = G.gereserveerd_beslissing({"m1": {"reserved": True}},
                                           [rij("m1", "active", NEE)], REDEN, NEE)
    assert vragen == []
    _, _, vergeten, _ = G.gereserveerd_beslissing({"m1": {"reserved": False}},
                                                  [rij("m1", "active", NEE)], REDEN, NEE)
    assert len(vergeten) == 1


def test_ontbrekend_nummer_zegt_hier_niets():
    uit = G.gereserveerd_beslissing({}, [rij("m1", "sold_unconfirmed", REDEN)], REDEN, NEE)
    assert uit == ([], [], [], False)


def test_een_groot_deel_ineens_gereserveerd_is_een_meetfout():
    lijst = {f"m{i}": {"reserved": True} for i in range(40)}
    vragen, _, _, te_veel = G.gereserveerd_beslissing(
        lijst, [rij(f"m{i}") for i in range(40)], REDEN, NEE)
    assert te_veel is True and vragen == []
    # Toons echte verhouding (6 op 1096) is geen meetfout.
    lijst = {f"m{i}": {"reserved": i < 6} for i in range(1096)}
    vragen, _, _, te_veel = G.gereserveerd_beslissing(
        lijst, [rij(f"m{i}") for i in range(6)], REDEN, NEE)
    assert te_veel is False and len(vragen) == 6


def test_verwerk_lijst_schrijft_de_vraag_en_neemt_de_herplaatsing_terug(monkeypatch):
    from backend.api.listings import VERDENKING_REDENEN

    updates, teruggenomen = [], []

    class Q:
        def __init__(self): self.v, self.f = None, {}
        def update(self, v): self.v = v; return self
        def eq(self, k, w): self.f[k] = w; return self
        def in_(self, *_a): return self
        def execute(self):
            updates.append((self.f.get("id"), dict(self.v)))

    class DB:
        def table(self, _t): return Q()

    async def direct(fn, *a, **k): return fn()
    monkeypatch.setattr(G, "naast_de_lus", direct)
    monkeypatch.setattr("backend.services.instellingen.verkoopvraag_aan", lambda _u: True)
    monkeypatch.setattr(G, "_onze_rijen", lambda *_a: [rij("m1", "relisting")])
    monkeypatch.setattr(G, "_neem_herplaatsingen_terug",
                        lambda _db, u, item, p: teruggenomen.append((u, item, p)) or 2)

    n = asyncio.run(G.verwerk_lijst(DB(), "u", "marktplaats", {"m1": {"reserved": True}}))
    assert n == 1
    assert updates[0][0] == "l-m1"
    assert updates[0][1]["status"] == "sold_unconfirmed"
    assert updates[0][1]["error_message"] == VERDENKING_REDENEN["gereserveerd"]
    assert teruggenomen == [("u", "i-m1", "marktplaats")]


def test_verkoopvraag_uit_doet_niets(monkeypatch):
    async def direct(fn, *a, **k): return fn()
    monkeypatch.setattr(G, "naast_de_lus", direct)
    monkeypatch.setattr("backend.services.instellingen.verkoopvraag_aan", lambda _u: False)
    monkeypatch.setattr(G, "_onze_rijen", lambda *_a: (_ for _ in ()).throw(AssertionError))
    assert asyncio.run(G.verwerk_lijst(object(), "u", "marktplaats", {"m1": {"reserved": True}})) == 0


def test_reden_bevat_geen_woorden_die_het_herplaatsoverzicht_verwarren():
    import re
    from backend.api.listings import VERDENKING_REDENEN, GERESERVEERD_NEE
    for tekst in (VERDENKING_REDENEN["gereserveerd"], GERESERVEERD_NEE):
        assert not re.search(r"relist|delist|still live", tekst, re.I)
    # Het dashboard herkent de vraag aan dit stuk tekst (frontend/app.html).
    assert "zelf op 'gereserveerd'" in VERDENKING_REDENEN["gereserveerd"]
