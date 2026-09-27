"""De echte routes achter het scherm "Shipping cost on 2dehands", met precies de
verzoeken die frontend/app.html stuurt (saveVerzending2dh, startVerzending2dhRonde,
laadVerzending2dhRonde, doBulkVerzending2dh). De proefpagina van 27-09-2026 sprak
een nagebootste server; deze proef bewijst dat de echte hetzelfde antwoordt.
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]

import backend.api.items as ITEMS  # noqa: E402
import backend.api.verzending as API  # noqa: E402
import backend.services.instellingen as I  # noqa: E402
import backend.services.verzending_2dh as V  # noqa: E402
import backend.services.verzending_2dh_ronde as RO  # noqa: E402
from backend.api.deps import get_current_user, require_active_subscription  # noqa: E402

spec = importlib.util.spec_from_file_location("ronde_proef", ROOT / "tests" / "test_verzending_2dh_keuze_en_ronde.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

U = "egbert"


@pytest.fixture
def klant(monkeypatch):
    w = P._Wereld()
    alles = lambda bouw, order_by="id", page_size=500: bouw().execute().data  # noqa: E731
    for mod in (RO, V, API):
        monkeypatch.setattr(mod, "fetch_all", alles, raising=False)
        monkeypatch.setattr(mod, "get_db", lambda: w, raising=False)
    monkeypatch.setattr(I, "get_db", lambda: w)
    for naam in ("_RONDES", "_LIJST", "_EIGEN_CACHE", "_GESCHREVEN"):
        getattr(RO, naam).clear()
    w.rijen[(U, I.RIJ)] = {I.VERZENDING_2DH_WOORDEN: ["patch"], I.VERZENDING_2DH_BRIEF_ONDER: 495}
    w.artikel(U, "a", "Rugpatch", {"soort": "zelf", "cents": 495})
    w.artikel(U, "g", "Bandana", mp_nummer=False)
    app = FastAPI()
    app.include_router(API.router, prefix="/api")
    app.include_router(ITEMS.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: U
    app.dependency_overrides[require_active_subscription] = lambda: U
    return w, TestClient(app)


def test_opslaan_toepassen_en_voortgang_zoals_het_scherm_het_vraagt(klant):
    w, c = klant
    r = c.put("/api/items/settings", json={"verzending_2dh_modus": "alles",
                                            "verzending_2dh_brief_onder": 495,
                                            "verzending_2dh_woorden": ["patch"]})
    assert r.status_code == 200 and r.json()["verzending_2dh_modus"] == "alles"
    r = c.post("/api/verzending-2dh/ronde", json={"opnieuw": False})
    assert r.status_code == 200
    ronde = r.json()["ronde"]
    assert ronde["status"] == "loopt" and ronde["instelling"]["modus"] == "alles"
    for veld in ("aantal", "bekeken", "tel", "niet_gelezen", "klaar_op", "wacht_op_herkansing"):
        assert veld in ronde, f"het scherm leest {veld}"
    lees = c.get("/api/verzending-2dh").json()
    assert set(lees) == {"ronde", "extensie_kan_bijwerken"}
    # Een andere keuze opslaan stopt de lopende ronde.
    c.put("/api/items/settings", json={"verzending_2dh_modus": "standaard"})
    assert c.get("/api/verzending-2dh").json()["ronde"]["status"] == "gestopt"


def test_eigen_bedrag_per_artikel_zoals_het_scherm_het_stuurt(klant):
    w, c = klant
    r = c.post("/api/verzending-2dh/artikelen", json={"item_ids": ["a", "g", "niet-van-hem"], "keuze": 225})
    assert r.status_code == 200
    body = r.json()
    assert body["gezet"] == 2 and body["op_2dehands"] == 2 and body["ronde"]["status"] == "loopt"
    assert c.get("/api/verzending-2dh/artikelen").json() == {"artikelen": {"a": 225, "g": 225}}
    r = c.post("/api/verzending-2dh/artikelen", json={"item_ids": ["g"], "keuze": "bpost"})
    assert r.json()["gezet"] == 1
    assert c.get("/api/verzending-2dh/artikelen").json()["artikelen"]["g"] == "bpost"


@pytest.mark.parametrize("fout", [{"item_ids": [], "keuze": 225}, {"item_ids": ["a"], "keuze": 10000},
                                  {"item_ids": ["a"], "keuze": "gratis"}, {"keuze": 225}])
def test_onzin_wordt_geweigerd(klant, fout):
    _, c = klant
    assert c.post("/api/verzending-2dh/artikelen", json=fout).status_code == 400
