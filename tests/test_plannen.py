"""De vier plannen (donker gebouwd): met de schakelaar uit verandert er niets."""
import pytest

from backend.services import light, plannen


def _zet(monkeypatch, aan, **ids):
    monkeypatch.setattr(plannen.settings, "nieuwe_plannen_aan", aan, raising=False)
    for veld in ("stripe_price_id", "stripe_price_id_light", "stripe_price_id_plus", "stripe_price_id_ultra",
                 "stripe_price_id_light_jaar", "stripe_price_id_pro_jaar", "stripe_price_id_plus_jaar",
                 "stripe_price_id_ultra_jaar"):
        monkeypatch.setattr(plannen.settings, veld, ids.get(veld, ""), raising=False)


def test_schakelaar_uit_alleen_light_heeft_grens(monkeypatch):
    _zet(monkeypatch, False)
    assert plannen.grens("light") == 20
    assert plannen.grens("pro") is None and plannen.grens("plus") is None and plannen.grens("ultra") is None


def test_schakelaar_aan_grenzen_met_marge(monkeypatch):
    _zet(monkeypatch, True)
    assert plannen.grens("light") == 20          # Light blijft strikt
    assert plannen.grens("pro") == 275           # 250 + 10%
    assert plannen.grens("plus") == 1650         # 1.500 + 10%
    assert plannen.grens("ultra") is None


def test_onbekend_plan_is_pro(monkeypatch):
    _zet(monkeypatch, True)
    assert plannen.grens(None) == 275
    assert plannen.plan_uit_prijs_id("price_onbekend") == "pro"
    assert plannen.plan_uit_prijs_id(None) == "pro"


def test_prijs_naar_plan_maand_en_jaar(monkeypatch):
    _zet(monkeypatch, False, stripe_price_id="p_pro", stripe_price_id_light="p_l", stripe_price_id_plus="p_plus",
         stripe_price_id_ultra="p_u", stripe_price_id_light_jaar="p_lj", stripe_price_id_plus_jaar="p_pj",
         stripe_price_id_ultra_jaar="p_uj", stripe_price_id_pro_jaar="p_prj")
    uit = {p: plannen.plan_uit_prijs_id(p) for p in
           ("p_pro", "p_prj", "p_l", "p_lj", "p_plus", "p_pj", "p_u", "p_uj")}
    assert uit == {"p_pro": "pro", "p_prj": "pro", "p_l": "light", "p_lj": "light",
                   "p_plus": "plus", "p_pj": "plus", "p_u": "ultra", "p_uj": "ultra"}


def test_lege_instellingen_matchen_nooit(monkeypatch):
    _zet(monkeypatch, False)
    assert plannen.plan_uit_prijs_id("") == "pro"


def test_plan_uit_stripe_herkent_plus_en_ultra(monkeypatch):
    _zet(monkeypatch, False, stripe_price_id_plus="p_plus", stripe_price_id_ultra="p_u")
    monkeypatch.setattr(light.settings, "stripe_price_id_light", "", raising=False)
    sub = lambda pid: {"items": {"data": [{"price": {"id": pid}}]}}
    assert light.plan_uit_stripe(sub("p_plus")) == "plus"
    assert light.plan_uit_stripe(sub("p_u")) == "ultra"
    assert light.plan_uit_stripe(sub("iets_anders")) == "pro"
    assert light.plan_uit_stripe(None) == "pro"


def _met(monkeypatch, plan, n):
    monkeypatch.setattr(light, "plan_van_gebruiker", lambda uid: plan)
    monkeypatch.setattr(light, "actieve_artikelen", lambda db, uid, st=None: {f"i{k}" for k in range(n)})


def test_pro_met_schakelaar_uit_blijft_onbeperkt(monkeypatch):
    _zet(monkeypatch, False)
    _met(monkeypatch, "pro", 900)
    assert light.ruimte_over(None, "u") is None
    assert light.publicatie_geblokkeerd(None, "u", "nieuw") is None


def test_pro_met_schakelaar_aan_geweigerd_boven_marge(monkeypatch):
    _zet(monkeypatch, True)
    _met(monkeypatch, "pro", 274)
    assert light.publicatie_geblokkeerd(None, "u", "nieuw") is None
    _met(monkeypatch, "pro", 275)
    assert "275" in light.publicatie_geblokkeerd(None, "u", "nieuw")
    assert light.publicatie_geblokkeerd(None, "u", "i3") is None     # al draaiend artikel mag door
    assert light.ruimte_over(None, "u") == 0


def test_ultra_nooit_geweigerd(monkeypatch):
    _zet(monkeypatch, True)
    _met(monkeypatch, "ultra", 99999)
    assert light.publicatie_geblokkeerd(None, "u", "nieuw") is None
    assert light.ruimte_over(None, "u") is None


def test_light_melding_blijft_zoals_hij_was(monkeypatch):
    _zet(monkeypatch, False)
    _met(monkeypatch, "light", 20)
    assert light.publicatie_geblokkeerd(None, "u", "nieuw") == light.LIGHT_LIMIET_MELDING
