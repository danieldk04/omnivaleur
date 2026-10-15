"""Wie zijn webshop zelf bijhoudt, krijgt na een verkoop elders niets aangeraakt in die webshop.

WAAROM DIT ER IS (15-10-2026, Janneke 31d28378). Gemeten in haar Shopify-logboek:
op 08-10 en 12-10 wiste "Omnivaleur" twee jassen uit haar webshop nadat ze op
Vinted verkocht waren. Janneke: "Ik denk dat ik sowieso liever zelf de aantallen
terugzet in de webshop. Voelt wat veiliger." Met instellingen.WEBSHOP_MET_RUST
aan blijft de webshop onaangeroerd; de andere kanalen gaan wel offline.

Draait de ECHTE handle_item_sold, nu en van vóór de reparatie (ef85fbd3).
"""
import subprocess
import tempfile
import importlib.util
from pathlib import Path

from tests.test_voorraadwinkel_verkoop import ROOT, _situatie, _verkoop
from backend.services import crosslist as cl
from backend.services import instellingen

VOOR = "ef85fbd3"


def _met_rust(monkeypatch, aan):
    monkeypatch.setattr(instellingen, "webshop_met_rust", lambda _u: aan)


def test_uniek_stuk_verkocht_op_vinted_blijft_in_de_webshop(monkeypatch):
    _met_rust(monkeypatch, True)
    db, winkel = _situatie(1, vlag=False)
    g = _verkoop(cl, monkeypatch, db, winkel, "vinted")
    assert not g["shopify_gewist"]
    assert g["stuk_eraf"] == 0
    assert sorted(g["extensie_weg"]) == ["2dehands", "marktplaats"]
    shopify = [r for r in db.t["listings"] if r["platform"] == "shopify"][0]
    assert shopify["status"] == "active"


def test_voorraadwinkel_verkocht_op_marktplaats_haalt_geen_stuk_af(monkeypatch):
    _met_rust(monkeypatch, True)
    db, winkel = _situatie(3, vlag=True)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["stuk_eraf"] == 0 and not g["shopify_gewist"]
    assert winkel["varianten"][0]["inventory_quantity"] == 3
    assert g["extensie_weg"] == ["2dehands"]


def test_verkoop_in_de_webshop_haalt_elders_nog_steeds_alles_weg(monkeypatch):
    _met_rust(monkeypatch, True)
    db, winkel = _situatie(1, vlag=False)
    g = _verkoop(cl, monkeypatch, db, winkel, "shopify")
    assert sorted(g["extensie_weg"]) == ["2dehands", "marktplaats"]


def test_uit_is_het_oude_gedrag(monkeypatch):
    _met_rust(monkeypatch, False)
    db, winkel = _situatie(1, vlag=False)
    assert _verkoop(cl, monkeypatch, db, winkel, "vinted")["shopify_gewist"]
    db, winkel = _situatie(3, vlag=True)
    assert _verkoop(cl, monkeypatch, db, winkel, "marktplaats")["stuk_eraf"] == 1


def test_de_oude_code_wiste_het_product_wel(monkeypatch):
    """Voor-en-na: dezelfde verkoop op de code van vóór de reparatie."""
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/services/crosslist.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "webshop_met_rust" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_crosslist_webshop.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_crosslist_webshop", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    _met_rust(monkeypatch, True)
    db, winkel = _situatie(1, vlag=False)
    assert _verkoop(oud, monkeypatch, db, winkel, "vinted")["shopify_gewist"]


def test_instelling_wordt_bewaard_als_ja_of_nee():
    assert instellingen._schoon({})[instellingen.WEBSHOP_MET_RUST] is False
    assert instellingen._schoon({instellingen.WEBSHOP_MET_RUST: 1})[instellingen.WEBSHOP_MET_RUST] is True
