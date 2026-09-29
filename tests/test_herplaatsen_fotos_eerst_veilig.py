"""Herplaatsen haalt pas weg als de foto's bij ons staan.

GEMETEN 29-09-2026, Zilverwebsite. Herplaatsen is eerst weghalen, dan opnieuw
plaatsen. Drie advertenties hadden alleen foto's op images.marktplaats.com; die
verdwijnen samen met de advertentie (404 op alle vijf, minuten later). De
plaatsing daarna meldde "None of the 5 photo(s) could be downloaded" en de
advertentie was definitief weg. Er stonden er nog 48 zo klaar bij twee klanten.
"""
import asyncio
import inspect
from types import SimpleNamespace

import pytest

from backend.services import photo_mirror
from backend.services import relist as R

MP = "https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/ab/abcdef?rule=ecg_mp_eps$_85"
EIGEN = "https://img.omnivaleur.com/u/foto1.jpg"
SHOPIFY = "https://cdn.shopify.com/s/files/1/foto.jpg"


class _DB:
    def __init__(self):
        self.bijgewerkt = []

    def table(self, naam):
        db = self

        class Q:
            def update(self, patch): self.patch = patch; return self
            def eq(self, *_a): return self
            def execute(self):
                db.bijgewerkt.append((naam, self.patch))
                return SimpleNamespace(data=[{}])
        return Q()


def _item(fotos):
    return {"id": "i1", "user_id": "u", "photo_urls": list(fotos)}


def test_marktplaats_fotos_worden_eerst_gekopieerd(monkeypatch):
    async def kopie(urls, _u, _sem=None):
        return [u.replace("images.marktplaats.com", "img.omnivaleur.com") for u in urls]
    monkeypatch.setattr(photo_mirror, "mirror_photos", kopie)
    db = _DB()
    uit = asyncio.run(R._fotos_veiligstellen(db, _item([MP, "//images.marktplaats.com/x.jpg"]), "marktplaats"))
    assert not any("marktplaats.com" in u for u in uit["photo_urls"])
    assert db.bijgewerkt and db.bijgewerkt[0][0] == "items"
    assert db.bijgewerkt[0][1]["photo_urls"] == uit["photo_urls"]


def test_lukt_kopieren_niet_dan_wordt_er_niets_weggehaald(monkeypatch):
    async def mislukt(urls, _u, _sem=None):
        return list(urls)               # zo meldt mirror_photos een mislukte kopie
    monkeypatch.setattr(photo_mirror, "mirror_photos", mislukt)
    db = _DB()
    with pytest.raises(R.RefreshError) as fout:
        asyncio.run(R._fotos_veiligstellen(db, _item([EIGEN, MP]), "marktplaats"))
    assert "nothing was removed" in str(fout.value)
    assert db.bijgewerkt == []


@pytest.mark.parametrize("fotos", [[EIGEN], [SHOPIFY, EIGEN], []])
def test_foto_elders_hoeft_niet_gekopieerd(monkeypatch, fotos):
    async def mag_niet(*_a, **_k):
        raise AssertionError("niets te kopiëren")
    monkeypatch.setattr(photo_mirror, "mirror_photos", mag_niet)
    assert asyncio.run(R._fotos_veiligstellen(_DB(), _item(fotos), "marktplaats"))["photo_urls"] == fotos


def test_2dehands_fotoserver_telt_ook():
    assert R._sterft_met_advertentie("https://images.2dehands.com/api/x.jpg", "2dehands")
    assert not R._sterft_met_advertentie(MP, "vinted")


def test_de_kopie_gebeurt_voor_de_verwijderopdracht():
    bron = inspect.getsource(R.refresh_listing)
    assert "_fotos_veiligstellen" in bron
    assert bron.index("_fotos_veiligstellen") < bron.index('db.table("jobs").insert')


def test_verouderde_adressen_worden_vervangen_door_de_live_advertentie(monkeypatch):
    """Zilverwebsite, 29-09-2026: 451 van 451 opgeslagen adressen dood, de live
    advertentie toont alle vijf foto's onder nieuwe adressen."""
    live = [f"https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/nieuw{i}?rule=ecg_mp_eps$_85" for i in range(5)]

    async def van_de_pagina(_p, _l):
        return live

    async def kopie(urls, _u, _sem=None):
        # alleen de live adressen zijn nog te downloaden
        return [u.replace("images.marktplaats.com", "img.omnivaleur.com") if "nieuw" in u else u for u in urls]
    monkeypatch.setattr(R, "_live_fotos", van_de_pagina)
    monkeypatch.setattr(photo_mirror, "mirror_photos", kopie)
    db = _DB()
    uit = asyncio.run(R._fotos_veiligstellen(db, _item([MP] * 5), "marktplaats",
                                             {"platform_listing_id": "m1"}))
    assert len(uit["photo_urls"]) == 5 and all("img.omnivaleur.com" in u for u in uit["photo_urls"])


def test_pagina_met_minder_fotos_wordt_niet_overgenomen(monkeypatch):
    async def te_weinig(_p, _l):
        return ["https://images.marktplaats.com/x/nieuw0"]

    async def kopie(urls, _u, _sem=None):
        return [u.replace("images.marktplaats.com", "img.omnivaleur.com") for u in urls]
    monkeypatch.setattr(R, "_live_fotos", te_weinig)
    monkeypatch.setattr(photo_mirror, "mirror_photos", kopie)
    uit = asyncio.run(R._fotos_veiligstellen(_DB(), _item([MP] * 3), "marktplaats",
                                             {"platform_listing_id": "m1"}))
    assert len(uit["photo_urls"]) == 3
