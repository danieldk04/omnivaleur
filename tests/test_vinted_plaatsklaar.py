"""Vinted plaatsklaar: in deze stand raakt Omnivaleur Vinted nooit aan.

Bewijst: standaard verandert er niets (stand 'extensie'); in 'plaatsklaar' krijgt de
extensie geen Vinted-opdracht en geen scan, herplaatsen is uit, publiceren naar Vinted
wordt geweigerd, andere kanalen merken niets; en het pakket, de zip, 'geplaatst' en de
takenlijst werken tegen een nagebouwde database.
"""
import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException

from backend.api import vinted_klaar as vk
from backend.services import instellingen as inst


def _zet(monkeypatch, **instelling):
    monkeypatch.setattr(inst, "lees", lambda u: inst._schoon(instelling))


# ---------- instelling en poorten ----------

def test_standaard_is_extensie_en_rommel_valt_terug():
    assert inst._schoon({})["vinted_modus"] == "extensie"
    assert inst._schoon({"vinted_modus": "onzin"})["vinted_modus"] == "extensie"
    assert inst._schoon({"vinted_modus": "plaatsklaar"})["vinted_modus"] == "plaatsklaar"


def test_standaard_verandert_niets_aan_de_kanalen(monkeypatch):
    _zet(monkeypatch)
    assert inst.kanalen_uit("u") == []
    assert inst.kanaal_uit("u", "vinted") is False


def test_plaatsklaar_sluit_alleen_vinted(monkeypatch):
    _zet(monkeypatch, vinted_modus="plaatsklaar")
    assert inst.kanaal_uit("u", "vinted") is True
    for p in ("marktplaats", "2dehands", "facebook", "ebay"):
        assert inst.kanaal_uit("u", p) is False


def test_plaatsklaar_telt_niet_dubbel_naast_loskoppelen(monkeypatch):
    _zet(monkeypatch, vinted_modus="plaatsklaar", kanalen_uit=["vinted"])
    assert inst.kanalen_uit("u").count("vinted") == 1


def test_herplaatsen_blijft_uit_in_plaatsklaar_ook_als_aangevinkt(monkeypatch):
    _zet(monkeypatch, vinted_modus="plaatsklaar", vinted_herplaatsen=True)
    assert inst.vinted_herplaatsen_toegestaan("u") is False
    _zet(monkeypatch, vinted_herplaatsen=True)
    assert inst.vinted_herplaatsen_toegestaan("u") is True


def test_onleesbare_instelling_laat_alles_zoals_het_was(monkeypatch):
    def stuk(u):
        raise RuntimeError("db")
    monkeypatch.setattr(inst, "lees", stuk)
    assert inst.kanalen_uit("u") == []
    assert inst.vinted_plaatsklaar("u") is False


def test_extensie_krijgt_geen_vinted_werk_maar_andere_kanalen_wel(monkeypatch):
    from backend.api import jobs
    _zet(monkeypatch, vinted_modus="plaatsklaar")
    req = type("R", (), {"headers": {}})()
    assert jobs.get_pending_jobs(req, platform="vinted", user_id="u") == []
    # Marktplaats loopt gewoon door tot de database (die hier bewust ontbreekt).
    monkeypatch.setattr(jobs, "get_db", lambda: (_ for _ in ()).throw(AssertionError("db bereikt")))
    with pytest.raises(AssertionError, match="db bereikt"):
        jobs.get_pending_jobs(req, platform="marktplaats", user_id="u")


def test_scan_op_vinted_wordt_geweigerd_in_plaatsklaar(monkeypatch):
    from backend.api import imports
    _zet(monkeypatch, vinted_modus="plaatsklaar")
    monkeypatch.setattr(imports, "get_db", lambda: (_ for _ in ()).throw(AssertionError("db bereikt")))
    with pytest.raises(HTTPException) as e:
        imports.start_scan("vinted", None, user_id="u")
    assert e.value.status_code == 409 and "ready-to-post" in e.value.detail
    # Marktplaats wordt niet tegengehouden door deze poort.
    with pytest.raises(AssertionError, match="db bereikt"):
        imports.start_scan("marktplaats", None, user_id="u")


def test_melding_wijst_naar_het_pakket(monkeypatch):
    _zet(monkeypatch, vinted_modus="plaatsklaar")
    assert "press Prepare" in inst.kanaal_uit_melding("vinted", "u")
    _zet(monkeypatch)
    assert "disconnected" in inst.kanaal_uit_melding("vinted", "u")


# ---------- adres ----------

@pytest.mark.parametrize("url,nummer", [
    ("https://www.vinted.nl/items/1234567890-blauwe-trui", "1234567890"),
    ("https://www.vinted.co.uk/items/55-x", "55"),
])
def test_echt_vinted_adres(url, nummer):
    schoon, n = vk._vinted_nummer_uit_url(url)
    assert schoon == url and n == nummer


@pytest.mark.parametrize("url", [
    "https://evil.example/items/123", "http://www.vinted.nl/items/123",
    "https://vinted.nl.evil.example/items/123", "https://www.vinted.nl/member/12",
    "javascript:alert(1)", "", None, "https://www.vinted.nl/items/12 https://x.y"])
def test_vreemd_adres_wordt_niet_bewaard(url):
    assert vk._vinted_nummer_uit_url(url) == (None, None)


# ---------- nagebouwde database ----------

class _Q:
    def __init__(self, db, tabel):
        self.db, self.t, self.f, self.op, self.data, self.lim = db, tabel, [], "select", None, None

    def select(self, *_): return self
    def eq(self, k, v): self.f.append(lambda r: r.get(k) == v); return self
    def in_(self, k, vs): self.f.append(lambda r: r.get(k) in vs); return self
    def order(self, *_): return self
    def limit(self, n): self.lim = n; return self
    def update(self, d): self.op, self.data = "update", d; return self
    def insert(self, d): self.op, self.data = "insert", d; return self

    def execute(self):
        rijen = self.db.t[self.t]
        if self.op == "insert":
            nieuw = {"id": f"n{len(rijen)}", **self.data}
            rijen.append(nieuw)
            return type("R", (), {"data": [nieuw]})()
        hit = [r for r in rijen if all(f(r) for f in self.f)]
        if self.op == "update":
            for r in hit:
                r.update(self.data)
        return type("R", (), {"data": hit[:self.lim] if self.lim else hit})()


class _Db:
    def __init__(self, **t):
        self.t = {"items": [], "listings": [], "jobs": [], **t}

    def table(self, n): return _Q(self, n)


async def _direct(f, *a, **k):
    return f()


@pytest.fixture
def db(monkeypatch):
    d = _Db(items=[{"id": "i1", "user_id": "u", "title": "Blauwe trui", "description": "Mooi",
                    "price": 20.0, "price_vinted": None, "condition": "good", "brand": "Zara",
                    "size": "M", "color": "blue", "category": "dames", "title_en": "Blue jumper",
                    "description_en": "Nice", "photo_urls": ["https://img.example/a.jpg", "http://x/b.jpg", "rommel"]},
                   {"id": "i2", "user_id": "ander", "title": "Niet van mij", "price": 5}])
    monkeypatch.setattr(vk, "get_db", lambda: d)
    monkeypatch.setattr(vk, "naast_de_lus", _direct)
    monkeypatch.setattr("backend.services.crosslist.slotteksten_van", lambda u: ("", ""), raising=False)
    _zet(monkeypatch, vinted_modus="plaatsklaar")
    return d


def _run(c):
    return asyncio.run(c)


def test_pakket_heeft_alles_en_alleen_https_fotos(db):
    p = _run(vk.pakket("i1", user_id="u"))
    assert p["titel"] == "Blauwe trui" and p["prijs"] == 20.0 and p["omschrijving"] == "Mooi"
    assert p["fotos"] == ["https://img.example/a.jpg"]
    assert p["merk"] == "Zara" and p["maat"] == "M" and p["vinted_status"] is None


def test_pakket_van_een_ander_is_404(db):
    with pytest.raises(HTTPException) as e:
        _run(vk.pakket("i2", user_id="u"))
    assert e.value.status_code == 404


def test_pakket_gebruikt_engels_als_de_verkoper_dat_koos(db, monkeypatch):
    _zet(monkeypatch, vinted_modus="plaatsklaar", vinted_taal="en")
    p = _run(vk.pakket("i1", user_id="u"))
    assert p["titel"] == "Blue jumper" and p["omschrijving"] == "Nice"


def test_vinted_prijs_gaat_voor(db):
    db.t["items"][0]["price_vinted"] = 18.5
    assert _run(vk.pakket("i1", user_id="u"))["prijs"] == 18.5


def test_zip_bevat_de_fotos_in_volgorde(db, monkeypatch):
    class _R:
        headers = {"content-type": "image/jpeg"}
        content = b"jpegdata"
        def raise_for_status(self): pass

    class _C:
        def __init__(self, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, u): return _R()
    monkeypatch.setattr(vk.httpx, "Client", _C)
    r = _run(vk.foto_zip("i1", user_id="u"))
    z = zipfile.ZipFile(io.BytesIO(r.body))
    assert z.namelist() == ["01.jpg"] and z.read("01.jpg") == b"jpegdata"
    assert "attachment" in r.headers["content-disposition"]


def test_zip_zonder_fotos_is_404(db):
    db.t["items"][0]["photo_urls"] = []
    with pytest.raises(HTTPException) as e:
        _run(vk.foto_zip("i1", user_id="u"))
    assert e.value.status_code == 404


def test_geplaatst_maakt_actieve_rij_en_bewaart_alleen_vinted_adres(db):
    _run(vk.geplaatst("i1", {"url": "https://www.vinted.nl/items/99-trui"}, user_id="u"))
    rij = db.t["listings"][0]
    assert rij["status"] == "active" and rij["platform"] == "vinted"
    assert rij["platform_listing_id"] == "99" and rij["platform_listing_url"].endswith("99-trui")
    _run(vk.geplaatst("i1", {"url": "https://evil.example/items/5"}, user_id="u"))
    assert len(db.t["listings"]) == 1 and db.t["listings"][0]["platform_listing_id"] == "99"


def test_geplaatst_zonder_adres_werkt_ook(db):
    out = _run(vk.geplaatst("i1", None, user_id="u"))
    assert out["url_bewaard"] is False and db.t["listings"][0]["status"] == "active"


def test_geplaatst_van_andermans_artikel_mislukt(db):
    with pytest.raises(HTTPException):
        _run(vk.geplaatst("i2", None, user_id="u"))
    assert db.t["listings"] == []


def test_taken_en_klaarmelden_van_een_verwijdering(db):
    db.t["listings"].append({"id": "l1", "item_id": "i1", "platform": "vinted", "status": "active"})
    db.t["jobs"] += [
        {"id": "j1", "user_id": "u", "item_id": "i1", "platform": "vinted", "action": "delete",
         "status": "pending", "payload": {"platform_listing_url": "https://www.vinted.nl/items/9"}, "created_at": "1"},
        {"id": "j2", "user_id": "u", "item_id": "i1", "platform": "vinted", "action": "scan",
         "status": "pending", "payload": {}, "created_at": "2"},
        {"id": "j3", "user_id": "u", "item_id": "i1", "platform": "marktplaats", "action": "delete",
         "status": "pending", "payload": {}, "created_at": "3"},
    ]
    t = _run(vk.taken(user_id="u"))["taken"]
    assert [x["job_id"] for x in t] == ["j1"] and t[0]["titel"] == "Blauwe trui"
    _run(vk.taak_klaar("j1", user_id="u"))
    assert db.t["listings"][0]["status"] == "delisted"
    assert db.t["jobs"][0]["status"] == "cancelled"
    assert db.t["jobs"][2]["status"] == "pending", "andere kanalen blijven onaangeroerd"
    with pytest.raises(HTTPException):
        _run(vk.taak_klaar("j1", user_id="u"))
    with pytest.raises(HTTPException):
        _run(vk.taak_klaar("j3", user_id="u"))
    with pytest.raises(HTTPException):
        _run(vk.taak_klaar("j1", user_id="ander"))
