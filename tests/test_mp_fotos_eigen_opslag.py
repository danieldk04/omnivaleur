"""Foto's van Marktplaats komen in onze eigen opslag, niet als kaal bronadres.

25-10-2026, gemeten bij 9 klanten: 883 artikelen met foto's op
images.marktplaats.com. Oorzaak bij 0b28c1ce bewezen: de import kopieerde het
omslagplaatje, daarna zette de aanvulstap (mp_enrich) de hele fotoreeks erover
met de kale Marktplaats-adressen (74 van de 74 van haar import van 24-10). Zo'n
adres gaat dood zodra de advertentie vervangen wordt.

Draaien:  python3 -m pytest tests/test_mp_fotos_eigen_opslag.py -q
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import mp_enrich, photo_mirror, relist  # noqa: E402

MP = "https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/{}?rule=ecg_mp_eps$_86"
EIGEN = "https://img.omnivaleur.com/u1/imported/{}.jpg"


def _kopie(levend):
    """Nep-mirror: kopieert alleen wat in `levend` staat, de rest blijft bronadres."""
    async def mirror(urls, user_id, **kw):
        return [EIGEN.format(u.rsplit("/", 1)[1][:6]) if u in levend else u for u in urls]
    return mirror


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.velden = db, tabel, None

    def update(self, velden):
        self.velden = velden
        return self

    def execute(self):
        if self.velden is not None:
            self.db.wijzigingen.append((self.tabel, self.velden))
            return type("R", (), {"data": []})()
        return type("R", (), {"data": self.db.rijen.get(self.tabel, [])})()

    def __getattr__(self, _n):
        return lambda *a, **k: self


class _Db:
    def __init__(self, rijen=None):
        self.rijen, self.wijzigingen = rijen or {}, []

    def table(self, naam):
        return _Q(self, naam)


# ── De aanvulstap ─────────────────────────────────────────────────────────────

def test_aanvullen_zet_gekopieerde_fotos_op_het_artikel(monkeypatch):
    reeks = [MP.format(f"aaaaaa{i}") for i in range(4)]

    async def pagina(client, url):
        return {"photo_urls": reeks}
    monkeypatch.setattr(mp_enrich, "volledige_advertentie", pagina)
    monkeypatch.setattr(photo_mirror, "mirror_photos", _kopie(set(reeks)))
    db = _Db()
    item = {"id": "i1", "user_id": "u1", "description": "x",
            "photo_urls": [EIGEN.format("omslag")]}
    asyncio.run(mp_enrich.vul_item_aan_uit_advertentie(db, item, "https://www.marktplaats.nl/v/a/b/m1-x"))
    fotos = [v["photo_urls"] for t, v in db.wijzigingen if t == "items" and "photo_urls" in v]
    assert fotos, "de fotoreeks hoort wel op het artikel te komen"
    assert not any("images.marktplaats" in u for u in fotos[0]), fotos[0]
    assert len(fotos[0]) == 4


def test_de_grote_aanvulronde_kopieert_ook():
    bron = (ROOT / "backend" / "services" / "mp_enrich.py").read_text(encoding="utf-8")
    blok = bron.split("async def verrijk(", 1)[1]
    blok = blok.split('fotos = pagina.get("photo_urls") or []', 1)[1][:600]
    assert "_eigen_kopie(fotos, user_id)" in blok.split('patch["photo_urls"] = fotos')[0]


# ── De inhaalronde ────────────────────────────────────────────────────────────

def _inhalen(monkeypatch, oud, levend, live=None, listing=True):
    from backend.services import mp_fotos_inhalen as m
    monkeypatch.setattr(photo_mirror, "mirror_photos", _kopie(levend))

    async def niets(*a, **k):
        return None
    monkeypatch.setattr(photo_mirror, "_wachtende_plaatsingen_bijwerken", niets)

    async def live_fotos(platform, rij):
        return list(live or [])
    monkeypatch.setattr(relist, "_live_fotos", live_fotos)
    db = _Db({"listings": [{"platform_listing_id": "m1", "status": "active"}] if listing else []})
    budget = {"paginas": 5}
    uit = asyncio.run(m.artikel_inhalen(db, {"id": "i1", "user_id": "u1", "photo_urls": oud}, budget))
    return uit, [v["photo_urls"] for t, v in db.wijzigingen if t == "items"], budget


def test_levende_bronfotos_worden_gekopieerd_zonder_pagina(monkeypatch):
    oud = [MP.format("bbbbbb1"), MP.format("bbbbbb2")]
    uit, fotos, budget = _inhalen(monkeypatch, oud, set(oud))
    assert uit == "hersteld" and budget["paginas"] == 5
    assert not any("marktplaats" in u for u in fotos[0])


def test_dode_bronfotos_komen_van_de_live_advertentie(monkeypatch):
    oud = [MP.format("dood01"), MP.format("dood02")]
    live = [MP.format("nieuw1"), MP.format("nieuw2"), MP.format("nieuw3")]
    uit, fotos, budget = _inhalen(monkeypatch, oud, set(live), live=live)
    assert uit == "hersteld" and budget["paginas"] == 4
    assert len(fotos[0]) == 3 and not any("marktplaats" in u for u in fotos[0])


def test_minder_fotos_op_de_pagina_dan_wordt_er_niets_geschreven(monkeypatch):
    oud = [MP.format("dood01"), MP.format("dood02")]
    live = [MP.format("nieuw1")]
    uit, fotos, _ = _inhalen(monkeypatch, oud, set(live), live=live)
    assert uit == "niet_gelukt" and fotos == []


def test_half_gekopieerd_wordt_niet_geschreven(monkeypatch):
    oud = [MP.format("dood01"), MP.format("dood02")]
    live = [MP.format("nieuw1"), MP.format("nieuw2")]
    uit, fotos, _ = _inhalen(monkeypatch, oud, {live[0]}, live=live)
    assert uit == "niet_gelukt" and fotos == []


def test_zonder_live_advertentie_blijft_alles_staan(monkeypatch):
    oud = [MP.format("dood01")]
    uit, fotos, _ = _inhalen(monkeypatch, oud, set(), listing=False)
    assert uit == "niet_gelukt" and fotos == []
