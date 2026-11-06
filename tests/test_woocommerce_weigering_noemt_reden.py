"""Toon, 06-11-2026: "WooCommerce mislukt: Je webshop antwoordde met HTTP 400. Probeer het zo
opnieuw." Woo had een reden (dubbel artikelnummer, foto geweigerd, ...) maar die viel weg,
dus niemand kon zien wat er mis was.

Draaien:  python3.13 -m pytest tests/test_woocommerce_weigering_noemt_reden.py -q
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.platforms.woocommerce import _lees_fout  # noqa: E402


def _r(status, json=None, text=None, ct="application/json"):
    return httpx.Response(status, json=json, text=text, headers={"content-type": ct}) \
        if json is not None else httpx.Response(status, text=text or "", headers={"content-type": ct})


def test_400_noemt_de_reden_van_de_winkel():
    f = _lees_fout(_r(400, {"code": "product_invalid_sku", "message": "Ongeldig of dubbel artikelnummer."}))
    assert "Ongeldig of dubbel artikelnummer" in str(f)
    assert f.soort == "geweigerd" and f.status == 400


def test_400_zonder_reden_blijft_de_oude_melding():
    assert "HTTP 400" in str(_lees_fout(_r(400, text="", ct="text/html")))
    assert "Try again in a moment" in str(_lees_fout(_r(400, {"code": "x"})))
