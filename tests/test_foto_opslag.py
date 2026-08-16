"""Vangnet voor het verkleinen en opruimen van foto's.

De inzet hier is niet opslagruimte maar de foto zelf: een fout in deze twee
paden laat een advertentie zonder beeld achter, en dat merk je pas als een
kanaal hem weigert. Deze tests leggen de veiligheidsgaranties vast.
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.image_optimize import optimize_image  # noqa: E402
from backend.services.image_upload import storage_path_from_url  # noqa: E402

BUCKET_URL = "https://xyz.supabase.co/storage/v1/object/public/photos/"


def _foto(w, h, fmt="JPEG", mode="RGB"):
    from PIL import Image
    im = Image.new(mode, (w, h))
    px = im.load()
    vulling = (200, 30, 90, 255) if mode == "RGBA" else (200, 30, 90)
    for x in range(0, w, 3):
        for y in range(0, h, 2):
            px[x, y] = vulling
    buf = io.BytesIO()
    im.save(buf, format=fmt, **({"quality": 95} if fmt == "JPEG" else {}))
    return buf.getvalue()


# --- verkleinen -----------------------------------------------------------

def test_grote_foto_wordt_kleiner_en_blijft_een_jpeg():
    from PIL import Image
    origineel = _foto(3000, 2000)
    uit, ext = optimize_image(origineel, "jpg")
    assert ext == "jpg"
    assert len(uit) < len(origineel)
    assert max(Image.open(io.BytesIO(uit)).size) <= 1600


def test_transparantie_blijft_behouden():
    from PIL import Image
    uit, ext = optimize_image(_foto(2000, 2000, "PNG", "RGBA"), "png")
    assert ext == "png"
    assert Image.open(io.BytesIO(uit)).mode in ("RGBA", "LA", "P")


def test_nooit_webp_want_kanalen_weigeren_dat():
    for bron, ext_in in ((_foto(2400, 1800), "jpg"), (_foto(1200, 900, "PNG"), "png")):
        _, ext = optimize_image(bron, ext_in)
        assert ext in ("jpg", "png", "gif")


def test_kapotte_of_lege_bytes_komen_ongewijzigd_terug():
    rommel = b"dit is geen plaatje"
    assert optimize_image(rommel, "jpg")[0] == rommel
    assert optimize_image(b"", "jpg")[0] == b""


def test_animatie_blijft_onaangeraakt():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("P", (600, 600)).save(
        buf, format="GIF", save_all=True, append_images=[Image.new("P", (600, 600), 5)]
    )
    gif = buf.getvalue()
    assert optimize_image(gif, "gif")[0] == gif


def test_exif_draaiing_wordt_vastgelegd():
    """Een telefoonfoto staat rechtop dankzij EXIF. Opnieuw opslaan gooit EXIF
    weg, dus de draaiing moet vooraf in de pixels zitten — anders ligt de foto
    op elk kanaal op zijn kant."""
    from PIL import Image
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6  # 90 graden gedraaid
    Image.new("RGB", (1200, 600), (10, 20, 30)).save(buf, format="JPEG", exif=exif)
    uit, _ = optimize_image(buf.getvalue(), "jpg")
    assert Image.open(io.BytesIO(uit)).size == (600, 1200)


# --- opruimen -------------------------------------------------------------

@pytest.mark.parametrize("url,verwacht", [
    (BUCKET_URL + "u1/imported/aaa.jpg", "u1/imported/aaa.jpg"),
    (BUCKET_URL + "u1/aaa.png?t=1", "u1/aaa.png"),
    ("https://images1.vinted.net/t/f800/foto.jpeg", None),   # niet van ons
    (BUCKET_URL, None),                                      # leeg pad
    (BUCKET_URL + "../../etc", None),                        # traversal
    (None, None), ("", None), (42, None),
])
def test_alleen_onze_eigen_objecten_worden_herkend(url, verwacht):
    assert storage_path_from_url(url) == verwacht


R2_URL = "https://img.omnivaleur.com/"


@pytest.fixture
def r2_aan(monkeypatch):
    """Doet alsof R2 ingesteld is, zonder ooit een verbinding te maken."""
    from backend.services import r2_storage
    monkeypatch.setattr(r2_storage, "is_configured", lambda: True)
    monkeypatch.setattr(r2_storage, "public_base", lambda: "https://img.omnivaleur.com")
    return r2_storage


def test_zonder_r2_verandert_er_niets():
    """De terugweg: geen sleutels betekent dat alles op Supabase blijft draaien."""
    from backend.services import r2_storage
    from backend.services.image_upload import locate_object
    assert r2_storage.is_configured() is False
    assert r2_storage.path_from_url(R2_URL + "u1/aaa.jpg") is None
    assert locate_object(BUCKET_URL + "u1/aaa.jpg") == ("supabase", "u1/aaa.jpg")


def test_beide_opslagplekken_worden_herkend(r2_aan):
    from backend.services.image_upload import locate_object
    assert locate_object(R2_URL + "u1/aaa.jpg") == ("r2", "u1/aaa.jpg")
    assert locate_object(BUCKET_URL + "u1/aaa.jpg") == ("supabase", "u1/aaa.jpg")
    assert locate_object("https://images1.vinted.net/foto.jpg") is None
    assert locate_object(R2_URL + "../geheim") is None


def test_een_foto_op_r2_wordt_niet_opnieuw_gekopieerd(r2_aan):
    """Anders zou elke herimport dezelfde foto nog een keer binnenhalen."""
    from backend.services.photo_mirror import is_mirrored
    assert is_mirrored(R2_URL + "u1/aaa.jpg") is True
    assert is_mirrored(BUCKET_URL + "u1/aaa.jpg") is True
    assert is_mirrored("https://images1.vinted.net/foto.jpg") is False


def test_upload_valt_terug_op_supabase_als_r2_stuk_is(r2_aan, monkeypatch):
    """Een storing bij R2 mag nooit een foto kosten."""
    from backend.services import r2_storage
    import backend.services.image_upload as iu

    def _kapot(*a, **kw):
        raise RuntimeError("R2 onbereikbaar")

    monkeypatch.setattr(r2_storage, "upload", _kapot)
    gebruikt = {}

    class _Opslag:
        def from_(self, bucket):
            gebruikt["bucket"] = bucket
            return self
        def upload(self, **kw):
            return None
        def get_public_url(self, naam):
            return BUCKET_URL + naam

    monkeypatch.setattr(iu, "get_db", lambda: type("D", (), {"storage": _Opslag()})())
    assert iu.upload_image_sync(b"bytes", "u1/aaa.jpg") == BUCKET_URL + "u1/aaa.jpg"
    assert gebruikt["bucket"] == "photos"


class _Res:
    def __init__(self, data): self.data = data


class _Tabel:
    def __init__(self, rijen): self._r = rijen
    def select(self, *a): return self
    def eq(self, *a): return self
    def execute(self): return _Res(self._r)


class _DB:
    def __init__(self, items, kandidaten): self.i, self.k = items, kandidaten
    def table(self, naam): return _Tabel(self.i if naam == "items" else self.k)


@pytest.fixture
def gewist(monkeypatch):
    verzameld = []
    import backend.services.image_upload as iu
    monkeypatch.setattr(iu, "delete_objects", lambda refs: verzameld.extend(refs))
    return verzameld


def test_gedeelde_foto_blijft_staan(gewist):
    """Foto's worden op inhoud geadresseerd, dus twee items kunnen dezelfde
    foto delen. En de opgeslagen url is niet overal letterlijk gelijk — oudere
    Supabase-clients plakken er een '?' achter. Vergelijken op tekst zou hier
    een foto wissen die nog in gebruik is."""
    from backend.api.items import _release_photos
    db = _DB(items=[{"photo_urls": [BUCKET_URL + "u1/imported/aaa.jpg?"]}], kandidaten=[])
    _release_photos(db, "u1", [BUCKET_URL + "u1/imported/aaa.jpg",
                               BUCKET_URL + "u1/imported/bbb.jpg"])
    assert gewist == ["u1/imported/bbb.jpg"]


def test_foto_van_een_importkandidaat_blijft_staan(gewist):
    from backend.api.items import _release_photos
    db = _DB(items=[], kandidaten=[{"photo_url": BUCKET_URL + "u1/aaa.jpg", "photo_urls": None}])
    _release_photos(db, "u1", [BUCKET_URL + "u1/aaa.jpg"])
    assert gewist == []


def test_databasefout_wist_nooit_iets(gewist):
    """Als de database niet antwoordt weten we niet wat nog in gebruik is.
    Dan hoort er niets weg te gaan — en het verwijderen van het item zelf,
    dat al gelukt is, mag hier niet alsnog op stuklopen."""
    from backend.api.items import _release_photos

    class _Plat:
        def table(self, naam): raise RuntimeError("database plat")

    _release_photos(_Plat(), "u1", [BUCKET_URL + "u1/aaa.jpg"])
    assert gewist == []
