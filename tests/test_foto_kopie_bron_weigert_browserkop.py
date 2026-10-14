"""De Juiste Toon, 14-10-2026: zijn WordPress-hosting weigert onze nagemaakte
Chrome-UA met een 403-pagina en geeft dezelfde foto zonder UA gewoon. De import
hield daardoor zijn bron-url, waar de extensie niet bij kan, en elke plaatsing
faalde met "None of the 7 photo(s) could be downloaded". Bij een 403 vragen we
nu nog één keer zonder nagemaakte browserkop."""
import asyncio

import httpx

from backend.services import photo_mirror

URL = "https://dejuistetoon.eu/wp-content/uploads/2024/12/img_1451.jpeg"


def _bron(verzoek: httpx.Request) -> httpx.Response:
    if "Chrome" in verzoek.headers.get("user-agent", ""):
        return httpx.Response(403, headers={"content-type": "text/html"}, content=b"<title>403</title>")
    return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8\xff jpeg")


def _draai(monkeypatch, bron):
    echt = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(bron), timeout=kw.get("timeout")))
    monkeypatch.setattr(photo_mirror, "optimize_image", lambda data, ext: (data, ext))
    geupload = []

    async def _upload(data, path):
        geupload.append(path)
        return "https://img.omnivaleur.com/" + path
    monkeypatch.setattr(photo_mirror, "upload_image", _upload)
    return asyncio.run(photo_mirror.mirror_photos([URL], "u1")), geupload


def test_bron_die_de_browserkop_weigert_wordt_toch_gekopieerd(monkeypatch):
    uit, geupload = _draai(monkeypatch, _bron)
    assert len(geupload) == 1
    assert uit[0].startswith("https://img.omnivaleur.com/u1/imported/")


def test_bron_die_alles_weigert_houdt_zijn_url(monkeypatch):
    uit, geupload = _draai(monkeypatch, lambda r: httpx.Response(403, content=b"nee"))
    assert uit == [URL] and geupload == []
