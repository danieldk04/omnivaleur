"""iPhone-foto's (MPO) moeten verkleind worden; echte animaties niet."""
import io

from PIL import Image

from backend.services.image_optimize import optimize_image


def _foto(formaat, kant=3000, extra=None, **kw):
    img = Image.effect_noise((kant, kant), 60).convert("RGB")
    buf = io.BytesIO()
    if extra:
        img.save(buf, formaat, save_all=True, append_images=[img.resize((300, 300))], **kw)
    else:
        img.save(buf, formaat, **kw)
    return buf.getvalue()


def test_mpo_iphone_foto_wordt_verkleind():
    data = _foto("MPO", extra=True)
    assert Image.open(io.BytesIO(data)).format == "MPO"
    uit, ext = optimize_image(data, "jpg")
    assert ext == "jpg"
    assert len(uit) < len(data) * 0.5
    assert max(Image.open(io.BytesIO(uit)).size) <= 1600


def test_geanimeerde_gif_blijft_ongemoeid():
    a = Image.new("P", (2000, 2000), 1)
    b = Image.new("P", (2000, 2000), 2)
    buf = io.BytesIO()
    a.save(buf, "GIF", save_all=True, append_images=[b])
    uit, _ = optimize_image(buf.getvalue(), "gif")
    assert uit == buf.getvalue()
