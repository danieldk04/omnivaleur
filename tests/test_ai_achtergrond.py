"""Achtergrond verwijderen: kosten begrensd, foto's nooit kwijt, ongedaan maken, vlag uit."""
import io

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import ai_pakket as route
from backend.api.deps import get_current_user
from backend.config import settings
from backend.services import achtergrond, ai_quota, instellingen, photo_mirror
from tests.test_ai_pakket import Db


def jpeg(kleur=(200, 30, 30), maat=(128, 128)) -> bytes:
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", maat, kleur).save(b, "JPEG"); return b.getvalue()


@pytest.fixture(autouse=True)
def poort(monkeypatch):
    monkeypatch.setattr(settings, "achtergrond_url", "https://modal.test/knip")
    monkeypatch.setattr(settings, "achtergrond_sleutel", "geheim")
    achtergrond._dag.update({"dag": "", "n": 0})


def client_met(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ── de poort naar Modal ─────────────────────────────────────────────────────

def test_knip_stuurt_de_sleutel_mee_en_geeft_de_jpeg_terug():
    gezien = {}
    def h(req):
        gezien["sleutel"] = req.headers["x-sleutel"]
        return httpx.Response(200, content=jpeg())
    assert achtergrond.knip(jpeg(), client_met(h))[:2] == b"\xff\xd8"
    assert gezien["sleutel"] == "geheim"


def test_niet_ingesteld_betekent_geen_foto_de_deur_uit(monkeypatch):
    monkeypatch.setattr(settings, "achtergrond_url", "")
    calls = []
    with pytest.raises(achtergrond.NietBeschikbaar):
        achtergrond.knip(jpeg(), client_met(lambda r: calls.append(1) or httpx.Response(200)))
    assert not calls


def test_een_antwoord_dat_geen_foto_is_wordt_geweigerd():
    for inhoud in (b"<html>fout</html>", b'{"detail": "x"}', b""):
        with pytest.raises(achtergrond.NietBeschikbaar):
            achtergrond.knip(jpeg(), client_met(lambda r, i=inhoud: httpx.Response(200, content=i)))


def test_koude_start_krijgt_een_tweede_poging_maar_verkeerde_sleutel_niet():
    n = []
    def h(req):
        n.append(1)
        return httpx.Response(500) if len(n) == 1 else httpx.Response(200, content=jpeg())
    assert achtergrond.knip(jpeg(), client_met(h))
    assert len(n) == 2
    n.clear()
    with pytest.raises(achtergrond.NietBeschikbaar):
        achtergrond.knip(jpeg(), client_met(lambda r: n.append(1) or httpx.Response(401)))
    assert len(n) == 1


def test_dagplafond_stopt_alles_voor_er_een_aanroep_is(monkeypatch):
    monkeypatch.setattr(achtergrond, "DAGPLAFOND", 2)
    n = []
    def h(req):
        n.append(1); return httpx.Response(200, content=jpeg())
    achtergrond.knip(jpeg(), client_met(h)); achtergrond.knip(jpeg(), client_met(h))
    with pytest.raises(achtergrond.NietBeschikbaar):
        achtergrond.knip(jpeg(), client_met(h))
    assert len(n) == 2


def test_te_grote_foto_gaat_niet_weg():
    with pytest.raises(ValueError):
        achtergrond.knip(b"x" * (achtergrond.MAX_BYTES + 1), client_met(lambda r: httpx.Response(200)))


# ── de routes ───────────────────────────────────────────────────────────────

EIGEN = "https://img.omnivaleur.com/a.jpg"


@pytest.fixture
def omgeving(monkeypatch):
    rijen = [{"id": "a", "user_id": "u1", "photo_urls": [EIGEN, "https://img.omnivaleur.com/b.jpg"]},
             {"id": "v", "user_id": "u1", "photo_urls": ["https://winkel.nl/x.jpg"]},
             {"id": "z", "user_id": "ander", "photo_urls": [EIGEN]}]
    db = Db(rijen); winkel: dict = {}
    monkeypatch.setattr(settings, "ai_pakket_aan", True)
    monkeypatch.setattr(route, "get_db", lambda: db)
    monkeypatch.setattr(instellingen, "lees", lambda u: {"ai_pakket": winkel.get(u)} if winkel.get(u) else {})
    monkeypatch.setattr(instellingen, "schrijf", lambda u, w: winkel.__setitem__(u, w["ai_pakket"]))
    monkeypatch.setattr(route, "heeft_pakket", lambda u: True)
    monkeypatch.setattr(photo_mirror, "is_mirrored", lambda u: u.startswith("https://img.omnivaleur.com/"))
    monkeypatch.setattr(route, "_haal_foto", lambda url: jpeg())
    monkeypatch.setattr(achtergrond, "knip", lambda foto, client=None: jpeg((255, 255, 255)))
    from backend.services import image_upload
    monkeypatch.setattr(image_upload, "upload_image_sync", lambda data, naam: "https://img.omnivaleur.com/" + naam)
    app = FastAPI(); app.include_router(route.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: "u1"
    return TestClient(app), rijen, winkel


def test_vlag_uit_is_404_en_er_gebeurt_niets(omgeving, monkeypatch):
    client, rijen, winkel = omgeving
    monkeypatch.setattr(settings, "ai_pakket_aan", False)
    for pad in ("voorbeeld", "uitvoeren", "ongedaan"):
        assert client.post(f"/api/ai-pakket/achtergrond/{pad}", json={"ids": ["a"]}).status_code == 404
    assert not winkel and rijen[0]["photo_urls"][0] == EIGEN


def test_volledige_ronde_voorbeeld_uitvoeren_ongedaan(omgeving):
    client, rijen, winkel = omgeving
    v = client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).json()
    assert v["uitvoerbaar"] and rijen[0]["photo_urls"][0] == EIGEN        # voorbeeld schrijft niets
    nieuw = v["artikelen"][0]["nieuw"]
    assert client.post("/api/ai-pakket/achtergrond/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"]}).status_code == 400
    assert rijen[0]["photo_urls"][0] == EIGEN                             # zonder bevestiging niets
    u = client.post("/api/ai-pakket/achtergrond/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).json()
    assert u["gewijzigd"] == 1
    assert rijen[0]["photo_urls"] == [nieuw, "https://img.omnivaleur.com/b.jpg"]   # alleen plek 1, rest blijft
    o = client.post("/api/ai-pakket/achtergrond/ongedaan", json={"ongedaan_id": u["ongedaan_id"]}).json()
    assert o["teruggezet"] == 1 and rijen[0]["photo_urls"][0] == EIGEN
    assert client.post("/api/ai-pakket/achtergrond/ongedaan", json={"ongedaan_id": u["ongedaan_id"]}).status_code == 404


def test_andermans_artikel_en_vreemde_fotohost_blijven_met_rust(omgeving):
    client, rijen, _ = omgeving
    v = client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["z", "v"]}).json()
    assert v["uitvoerbaar"] is False
    assert [x.get("overgeslagen") for x in v["artikelen"]] == ["geen_eigen_foto"]   # z bestaat voor u1 niet
    assert rijen[2]["photo_urls"] == [EIGEN] and rijen[1]["photo_urls"] == ["https://winkel.nl/x.jpg"]


def test_latere_wijziging_door_de_klant_wordt_nooit_overschreven(omgeving):
    client, rijen, _ = omgeving
    v = client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).json()
    rijen[0]["photo_urls"] = ["https://img.omnivaleur.com/nieuwe-eigen-foto.jpg"]
    u = client.post("/api/ai-pakket/achtergrond/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).json()
    assert u["gewijzigd"] == 0 and rijen[0]["photo_urls"] == ["https://img.omnivaleur.com/nieuwe-eigen-foto.jpg"]


def test_ongedaan_zet_niet_terug_als_de_klant_intussen_zelf_wijzigde(omgeving):
    client, rijen, _ = omgeving
    v = client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).json()
    u = client.post("/api/ai-pakket/achtergrond/uitvoeren", json={"voorbeeld_id": v["voorbeeld_id"], "bevestig": True}).json()
    rijen[0]["photo_urls"][0] = "https://img.omnivaleur.com/zelf.jpg"
    o = client.post("/api/ai-pakket/achtergrond/ongedaan", json={"ongedaan_id": u["ongedaan_id"]}).json()
    assert o["teruggezet"] == 0 and o["overgeslagen"] == 1
    assert rijen[0]["photo_urls"][0] == "https://img.omnivaleur.com/zelf.jpg"


def test_maandplafond_per_klant_geeft_429_en_kost_niets(omgeving, monkeypatch):
    client, rijen, winkel = omgeving
    ai_quota.bewaar("u1", "achtergronden", ai_quota.PLAFOND["achtergronden"])
    aangeroepen = []
    monkeypatch.setattr(achtergrond, "knip", lambda *a, **k: aangeroepen.append(1))
    assert client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).status_code == 429
    assert not aangeroepen


def test_niet_ingesteld_geeft_503_en_laat_alles_staan(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    monkeypatch.setattr(settings, "achtergrond_url", "")
    assert client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).status_code == 503
    assert rijen[0]["photo_urls"][0] == EIGEN


def test_dienst_valt_weg_midden_in_de_opdracht_geeft_503_zonder_wijziging(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    def stuk(*a, **k): raise achtergrond.NietBeschikbaar("modal weg")
    monkeypatch.setattr(achtergrond, "knip", stuk)
    assert client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": ["a"]}).status_code == 503
    assert rijen[0]["photo_urls"][0] == EIGEN


def test_maximaal_tien_per_keer(omgeving, monkeypatch):
    client, rijen, _ = omgeving
    gezien = []
    monkeypatch.setattr(route, "_bewerk_een", lambda u, it: gezien.append(it["id"]) or {"id": it["id"], "overgeslagen": "mislukt"})
    for i in range(15):
        rijen.append({"id": f"x{i}", "user_id": "u1", "photo_urls": [EIGEN]})
    client.post("/api/ai-pakket/achtergrond/voorbeeld", json={"ids": [f"x{i}" for i in range(15)]})
    assert len(gezien) == achtergrond.MAX_PER_KEER
