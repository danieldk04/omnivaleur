"""De Juiste Toon, 15-10-2026: 239 van zijn 1606 artikelen hielden foto-adressen
op dejuistetoon.eu (SiteGround weigerde de kopie bij het inlezen). De extensie kan
daar niet bij, dus elke plaatsing op Marktplaats, 2dehands en Vinted gaf "None of
the 7 photo(s) could be downloaded". Bij het plaatsen kopiëren we ze nu alsnog."""
import asyncio

from backend.services import crosslist as cl
from backend.services import photo_mirror

BRON = ["https://dejuistetoon.eu/a.jpg", "https://dejuistetoon.eu/b.jpg"]


class _Tabel:
    def __init__(self, db): self.db = db
    def update(self, d): self.db.update = d; return self
    def eq(self, *a): return self
    def execute(self): return type("R", (), {"data": []})()


class _Db:
    update = None
    def table(self, n): return _Tabel(self)


def _zet(monkeypatch, mirror):
    async def _exec(q): return q.execute()
    monkeypatch.setattr(cl, "_exec", _exec)
    monkeypatch.setattr(photo_mirror, "mirror_photos", mirror)


def test_bronfotos_worden_gekopieerd_en_bewaard(monkeypatch):
    async def mirror(urls, uid): return ["https://img.omnivaleur.com/" + u[-5:] for u in urls]
    _zet(monkeypatch, mirror)
    db, item = _Db(), {"photo_urls": list(BRON)}
    uit = asyncio.run(cl._kopieer_bronfotos(db, item, "i1", "u1"))
    assert all(u.startswith("https://img.omnivaleur.com/") for u in uit["photo_urls"])
    assert db.update == {"photo_urls": uit["photo_urls"]}


def test_mislukte_kopie_laat_het_artikel_ongemoeid(monkeypatch):
    async def mirror(urls, uid): return list(urls)
    _zet(monkeypatch, mirror)
    db, item = _Db(), {"photo_urls": list(BRON)}
    uit = asyncio.run(cl._kopieer_bronfotos(db, item, "i1", "u1"))
    assert uit["photo_urls"] == BRON and db.update is None


def test_een_storing_in_de_kopie_gooit_niet(monkeypatch):
    async def mirror(urls, uid): raise RuntimeError("stuk")
    _zet(monkeypatch, mirror)
    uit = asyncio.run(cl._kopieer_bronfotos(_Db(), {"photo_urls": list(BRON)}, "i1", "u1"))
    assert uit["photo_urls"] == BRON


def test_eigen_foto_s_worden_niet_aangeraakt(monkeypatch):
    async def mirror(urls, uid): raise AssertionError("mocht niet draaien")
    _zet(monkeypatch, mirror)
    eigen = ["https://img.omnivaleur.com/u1/imported/x.jpg"]
    uit = asyncio.run(cl._kopieer_bronfotos(_Db(), {"photo_urls": eigen}, "i1", "u1"))
    assert uit["photo_urls"] == eigen
