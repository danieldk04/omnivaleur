"""Achtergrond verwijderen op een T4-videokaart bij Modal (live sinds 20-11-2026).

BiRefNet lite (MIT). Kostenbegrenzing zit in drie lagen, zie docs/overdracht.md:
max_containers hier, een dag- en maandplafond in onze eigen code, en een
uitgavenlimiet in het Modal-dashboard. Hier staat geen sleutel in.

Proef:   modal run scripts/modal_achtergrond.py --urls lijst.txt
Uitrol:  modal deploy scripts/modal_achtergrond.py   (geheim: modal secret omnivaleur-achtergrond, sleutel ACHTERGROND_SLEUTEL)
De server (backend/services/achtergrond.py) roept de poort `knip` aan met die sleutel.
"""
import io
import time

import modal
from fastapi import Request, Response

app = modal.App("omnivaleur-achtergrond")


# Vaste versie van het model: een latere wijziging aan de bron kan niets stilletjes veranderen.
REVISIE = "aa62cd87eafb9cc43056d08ef3615a14628b831d"
MAX_BYTES = 12 * 1024 * 1024


def _download():
    from transformers import AutoModelForImageSegmentation
    AutoModelForImageSegmentation.from_pretrained(
        "ZhengPeng7/BiRefNet_lite", revision=REVISIE, trust_remote_code=True)


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.4.1", "torchvision==0.19.1", "transformers==4.44.2", "pillow",
                 "numpy", "kornia", "timm", "einops", "requests", "fastapi[standard]")
    .run_function(_download)
)


@app.cls(image=image, gpu="T4", max_containers=2, scaledown_window=30, timeout=120,
         secrets=[modal.Secret.from_name("omnivaleur-achtergrond")])
class Achtergrond:
    @modal.enter()
    def laad(self):
        import torch
        from transformers import AutoModelForImageSegmentation
        self.torch = torch
        self.model = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet_lite", revision=REVISIE, trust_remote_code=True).to("cuda").eval().half()

    @modal.method()
    def masker(self, foto: bytes) -> tuple[bytes, float]:
        """Geeft het masker als PNG (zelfde grootte als de foto) en de rekentijd in seconden."""
        import numpy as np
        from PIL import Image
        t0 = time.time()
        im = Image.open(io.BytesIO(foto)).convert("RGB")
        x = np.asarray(im.resize((1024, 1024)), dtype=np.float32) / 255.0
        x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        t = self.torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).half().to("cuda")
        with self.torch.no_grad():
            p = self.model(t)[-1].sigmoid().float().cpu()[0, 0].numpy()
        m = Image.fromarray((p * 255).astype("uint8")).resize(im.size)
        buf = io.BytesIO(); m.save(buf, "PNG")
        return buf.getvalue(), time.time() - t0


    @modal.asgi_app(label="omnivaleur-achtergrond-knip")
    def web(self):
        from fastapi import FastAPI
        api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @api.post("/")
        async def knip(request: Request):
            return await self._knip(request)
        return api

    async def _knip(self, request: Request):
        """De poort voor de server: foto in (bytes), JPEG op witte achtergrond uit."""
        import hmac
        import os
        sleutel = os.environ.get("ACHTERGROND_SLEUTEL", "")
        gegeven = request.headers.get("x-sleutel", "")
        if not sleutel or not hmac.compare_digest(sleutel, gegeven):
            return Response(status_code=401)
        from PIL import Image
        raw = await request.body()
        if not raw or len(raw) > MAX_BYTES:
            return Response(status_code=413)
        try:
            im = Image.open(io.BytesIO(raw))
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width * im.height > 40_000_000:
                return Response(status_code=413)
            buf0 = io.BytesIO(); im.save(buf0, "JPEG", quality=95)
        except Exception:
            return Response(status_code=415)
        m, _ = self.masker.local(buf0.getvalue())
        mask = Image.open(io.BytesIO(m)).convert("L")
        wit = Image.new("RGB", im.size, (255, 255, 255)); wit.paste(im, mask=mask)
        buf = io.BytesIO(); wit.save(buf, "JPEG", quality=90)
        return Response(content=buf.getvalue(), media_type="image/jpeg")


@app.local_entrypoint()
def proef(urls: str, uit: str = "blad5.jpg"):
    import requests
    from PIL import Image
    regels = open(urls).read().split()
    tegels = []
    a = Achtergrond()
    for i, u in enumerate(regels):
        try:
            raw = requests.get(u, timeout=30).content
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            print(i, "overgeslagen", e); continue
        t0 = time.time()
        m, sec = a.masker.remote(raw)
        tot = time.time() - t0
        print(i, f"gpu {sec:.2f}s totaal {tot:.2f}s", flush=True)
        mask = Image.open(io.BytesIO(m)).convert("L")
        bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=mask)
        bg.thumbnail((500, 500)); tegels.append(bg)
    blad = Image.new("RGB", (2000, 500 * ((len(tegels) + 3) // 4)), (255, 255, 255))
    for n, t in enumerate(tegels):
        blad.paste(t, ((n % 4) * 500, (n // 4) * 500))
    blad.thumbnail((1800, 2400)); blad.save(uit, quality=85)
