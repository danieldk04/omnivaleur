"""De Juiste Toon, 15-10-2026: SiteGround houdt onze server tegen, een GitHub-machine
niet. De GitHub-taak haalt de foto's op en levert ze af; alleen onze eigen taak op
main komt erin, en alleen de adressen die nog op het artikel staan worden vervangen."""
import asyncio
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwk, jwt

from backend.api import bronfotos as api
from backend.services import github_oidc as oidc
from backend.services import photo_mirror as pm

BRON = "https://dejuistetoon.eu/wp-content/uploads/{}.jpg"
EIGEN = "https://img.omnivaleur.com/u1/imported/{}.jpg"


def _sleutel():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.PEM,
                                      serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem, pub


GOED, _ = _sleutel()


@pytest.fixture
def github(monkeypatch):
    pem, pub = _sleutel()
    sleutel = jwk.construct(pub, "RS256").to_dict()
    sleutel["kid"] = "k1"

    async def sleutels(vers=False): return {"keys": [sleutel]}
    monkeypatch.setattr(oidc, "_sleutels", sleutels)

    def maak(_pem=pem, **anders):
        inhoud = {"iss": oidc.UITGEVER, "aud": "omnivaleur-bronfotos", "exp": int(time.time()) + 300,
                  "repository": "danieldk04/omnivaleur", "ref": "refs/heads/main",
                  "workflow_ref": "danieldk04/omnivaleur/.github/workflows/bronfotos.yml@refs/heads/main",
                  "event_name": "schedule"}
        inhoud.update(anders)
        return jwt.encode(inhoud, _pem, algorithm="RS256", headers={"kid": "k1"})
    return maak


def _toets(token):
    return asyncio.run(oidc.controleer(token, "omnivaleur-bronfotos", "bronfotos.yml"))


def test_eigen_taak_op_main_komt_erin(github):
    assert _toets(github())["repository"] == "danieldk04/omnivaleur"
    assert _toets(github(event_name="workflow_dispatch"))


@pytest.mark.parametrize("anders", [
    {"repository": "iemand/omnivaleur"},
    {"ref": "refs/heads/aanval"},
    {"workflow_ref": "danieldk04/omnivaleur/.github/workflows/ander.yml@refs/heads/main"},
    {"workflow_ref": "danieldk04/omnivaleur/.github/workflows/bronfotos.yml@refs/heads/aanval"},
    {"event_name": "pull_request"},
    {"event_name": "pull_request_target"},
    {"aud": "iets-anders"},
    {"iss": "https://nep.example"},
    {"exp": int(time.time()) - 60},
])
def test_al_het_andere_wordt_geweigerd(github, anders):
    with pytest.raises(oidc.Geweigerd):
        _toets(github(**anders))


def test_andere_handtekening_wordt_geweigerd(github):
    with pytest.raises(oidc.Geweigerd):
        _toets(github(_pem=GOED))
    with pytest.raises(oidc.Geweigerd):
        _toets("geen.token.hier")


def _app():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_zonder_of_met_vals_bewijs_geen_toegang(github, monkeypatch):
    geroepen = []

    async def nooit(*a, **k): geroepen.append(1)
    monkeypatch.setattr(pm, "bronfotos_wachtrij", nooit)
    monkeypatch.setattr(pm, "aangeleverde_fotos_opslaan", nooit)
    c = _app()
    assert c.get("/api/intern/bronfotos").status_code == 401
    assert c.get("/api/intern/bronfotos", headers={"Authorization": "Bearer " + github(_pem=GOED)}).status_code == 403
    assert c.post("/api/intern/bronfotos/i1", json={"user_id": "u1", "fotos": []},
                  headers={"Authorization": "Bearer " + github(ref="refs/heads/x")}).status_code == 403
    assert not geroepen


def test_echte_taak_mag_afleveren(github, monkeypatch):
    gekregen = {}

    async def opslaan(uid, iid, fotos):
        gekregen.update(uid=uid, iid=iid, fotos=fotos)
        return {"vervangen": 1, "over": 0}
    monkeypatch.setattr(pm, "aangeleverde_fotos_opslaan", opslaan)
    r = _app().post("/api/intern/bronfotos/i1", headers={"Authorization": "Bearer " + github()},
                    json={"user_id": "u1", "fotos": [{"url": BRON.format("a"), "type": "image/jpeg", "b64": "/9j/AA=="},
                                                     {"url": BRON.format("b"), "type": "text/html", "b64": "PGh0bWw+"}]})
    assert r.status_code == 200 and r.json() == {"vervangen": 1, "over": 0}
    assert gekregen["uid"] == "u1" and gekregen["iid"] == "i1"
    assert list(gekregen["fotos"]) == [BRON.format("a")]          # html valt af


class _Db:
    def __init__(self, items, winkels=()):
        self.items, self.winkels, self.updates = items, list(winkels), []

    def table(self, naam): return _T(self, naam)


class _T:
    def __init__(self, db, naam): self.db, self.naam, self.f, self.d = db, naam, {}, None
    def select(self, *a): return self
    def limit(self, *a): return self
    def eq(self, k, v): self.f[k] = v; return self
    def update(self, d): self.d = d; return self

    def execute(self):
        if self.d is not None:
            self.db.updates.append((dict(self.f), self.d))
            return type("R", (), {"data": []})()
        if self.naam == "platform_credentials":
            return type("R", (), {"data": self.db.winkels})()
        rijen = [r for r in self.db.items if all(r.get(k) == v for k, v in self.f.items())]
        return type("R", (), {"data": rijen})()


def _zet(monkeypatch, db):
    import backend.database as bd
    monkeypatch.setattr(bd, "get_db", lambda: db)
    monkeypatch.setattr(bd, "fetch_all", lambda f: f().execute().data)

    async def lus(f): return f()
    monkeypatch.setattr(bd, "naast_de_lus", lus)
    monkeypatch.setattr(pm, "is_mirrored", lambda u: isinstance(u, str) and u.startswith("https://img.omnivaleur.com/"))
    monkeypatch.setattr(pm, "optimize_image", lambda data, ext: (data, ext))
    opgeslagen = []

    async def upload(data, pad):
        opgeslagen.append((data, pad))
        return "https://img.omnivaleur.com/" + pad
    monkeypatch.setattr(pm, "upload_image", upload)
    return opgeslagen


def test_aflevering_vervangt_alleen_wat_nog_op_het_artikel_staat(monkeypatch):
    item = {"id": "i1", "user_id": "u1", "photo_urls": [BRON.format("a"), EIGEN.format("x"), BRON.format("b")]}
    db = _Db([item])
    opgeslagen = _zet(monkeypatch, db)
    uit = asyncio.run(pm.aangeleverde_fotos_opslaan("u1", "i1", {
        BRON.format("a"): (b"\xff\xd8foto-a", "image/jpeg"),
        BRON.format("weg"): (b"\xff\xd8oud", "image/jpeg"),     # staat niet (meer) op het artikel
    }))
    assert uit == {"vervangen": 1, "over": 1}
    assert [d for d, _ in opgeslagen] == [b"\xff\xd8foto-a"]
    (filter_, nieuw), = db.updates
    assert filter_ == {"id": "i1", "user_id": "u1"}
    lijst = nieuw["photo_urls"]
    assert lijst[0].startswith("https://img.omnivaleur.com/u1/imported/") and lijst[1:] == [EIGEN.format("x"), BRON.format("b")]


def test_artikel_van_een_ander_wordt_niet_aangeraakt(monkeypatch):
    db = _Db([{"id": "i1", "user_id": "u2", "photo_urls": [BRON.format("a")]}])
    _zet(monkeypatch, db)
    uit = asyncio.run(pm.aangeleverde_fotos_opslaan("u1", "i1", {BRON.format("a"): (b"x", "image/jpeg")}))
    assert uit["vervangen"] == 0 and not db.updates


def test_wachtrij_noemt_alleen_bronfotos_van_webshopklanten(monkeypatch):
    db = _Db([
        {"id": "i1", "user_id": "u1", "photo_urls": [BRON.format("a"), EIGEN.format("x")]},
        {"id": "i2", "user_id": "u1", "photo_urls": [EIGEN.format("y")]},
        {"id": "i3", "user_id": "u9", "photo_urls": [BRON.format("c")]},     # geen webshop gekoppeld
    ], winkels=[{"user_id": "u1"}])
    _zet(monkeypatch, db)
    assert asyncio.run(pm.bronfotos_wachtrij()) == [{"item_id": "i1", "user_id": "u1", "urls": [BRON.format("a")]}]
