"""Fototweeling: hetzelfde stuk herkennen aan de foto (19-11-2026, Esther).

Zonder dit werd bij haar Shopify-import elk product dat al via Marktplaats bij ons
stond een tweede artikel; een webshopverkoop haalde de Marktplaats-advertentie
dan nergens weg.
"""
import asyncio
import io
import random

from PIL import Image, ImageDraw

from backend.services import foto_tweeling as ft


def _foto(zaad: int, kwaliteit: int = 90) -> bytes:
    rnd = random.Random(zaad)
    im = Image.new("RGB", (400, 400), (230, 220, 200))
    d = ImageDraw.Draw(im)
    for _ in range(12):
        x, y = rnd.randint(0, 350), rnd.randint(0, 350)
        d.ellipse([x, y, x + rnd.randint(20, 120), y + rnd.randint(20, 120)],
                  fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=kwaliteit)
    return buf.getvalue()


def test_zelfde_foto_anders_gecomprimeerd_is_hetzelfde_stuk():
    a = ft.verschilhash(_foto(1, 95))
    b = ft.verschilhash(_foto(1, 60))
    assert ft.verschil(a, b) <= ft.MAX_VERSCHIL


def test_andere_foto_is_ander_stuk():
    a = ft.verschilhash(_foto(1))
    for z in range(2, 12):
        assert ft.verschil(a, ft.verschilhash(_foto(z))) > ft.MAX_VERSCHIL


def test_kapotte_foto_bewijst_niets():
    assert ft.verschilhash(b"geen plaatje") is None


def test_alleen_een_op_een(monkeypatch):
    fotos = {"k1": _foto(1), "k2": _foto(1, 70), "k3": _foto(3), "a1": _foto(1, 80),
             "a3": _foto(3, 75), "a9": _foto(9)}

    async def nep(client, url, rem):
        return ft.verschilhash(fotos[url.split("/")[-1]])

    monkeypatch.setattr(ft, "_hash_van", nep)
    kand = [{"id": "c1", "photo_url": "http://x/k1"}, {"id": "c2", "photo_url": "http://x/k2"},
            {"id": "c3", "photo_urls": ["http://x/k3"]}]
    art = [{"id": "i1", "photo_urls": ["http://x/a1"]}, {"id": "i3", "photo_urls": ["http://x/a3"]},
           {"id": "i9", "photo_urls": ["http://x/a9"]}]
    uit = asyncio.run(ft.foto_tweelingen(kand, art))
    # c1 en c2 claimen allebei i1: niet raden. c3 hoort ondubbelzinnig bij i3.
    assert uit == {"c3": "i3"}
