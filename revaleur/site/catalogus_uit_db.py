"""Revaleur: catalogus.json uit de EIGEN Revaleur-database (de bron na de omzetting). Draait bij elke Cloudflare-build.

Vraagt REVALEUR_SUPABASE_URL en REVALEUR_SUPABASE_PUBLISHABLE_KEY (alleen lezen; de service key mag ook). Niets van Omnivaleur.
Verborgen producten (status 'verborgen') komen er niet in; verkochte staan er als "Sold" op.
Mislukt het lezen, dan stopt de bouw met een foutcode: Cloudflare houdt dan de vorige werkende site live.
"""
import html
import json
import re
import sys
from pathlib import Path

import os

from supabase import create_client

HIER = Path(__file__).parent


def _alles(db, tabel: str, kolommen: str = "*") -> list:
    uit, o = [], 0
    while True:
        r = db.table(tabel).select(kolommen).range(o, o + 999).execute().data or []
        uit += r
        o += 1000
        if len(r) < 1000:
            return uit


def _tekst(h: str) -> str:
    h = re.sub(r"<br\s*/?>|</p>|</li>", "\n", h or "")
    return re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def _client():
    """Bij voorkeur de publishable key (alleen lezen, REVALEUR_SUPABASE_PUBLISHABLE_KEY): de bouw hoeft nooit te schrijven."""
    url = os.environ.get("REVALEUR_SUPABASE_URL", "")
    sleutel = os.environ.get("REVALEUR_SUPABASE_PUBLISHABLE_KEY") or os.environ.get("REVALEUR_SUPABASE_SERVICE_KEY", "")
    if not (url and sleutel):
        raise SystemExit("REVALEUR_SUPABASE_URL en REVALEUR_SUPABASE_PUBLISHABLE_KEY ontbreken")
    return create_client(url, sleutel)


def bouw(uitvoer: Path = HIER / "data") -> dict:
    db = _client()
    producten = [{
        "id": p["id"], "handle": p["handle"], "titel": p["titel"], "merk": p["merk"] or "", "type": p["type"] or "", "sku": p["sku"],
        "prijs": float(p["prijs"]), "retail": float(p["retail"]) if p["retail"] else None, "beschikbaar": p["status"] == "beschikbaar",
        "beschrijving": p["beschrijving_html"] or "", "tekst": _tekst(p["beschrijving_html"]), "fotos": p["fotos"] or [],
        "gemaakt": p["gemaakt_op"], "tags": p["tags"] or [],
    } for p in _alles(db, "producten") if p["status"] != "verborgen"]
    if not producten:
        raise SystemExit("Geen producten in de Revaleur-database: bouw afgebroken")
    zichtbaar = {p["id"] for p in producten}
    collecties = [{"handle": c["handle"], "titel": c["titel"], "omschrijving": c["omschrijving"] or "", "aantal": 0,
                   "producten": [i for i in (c["producten"] or []) if i in zichtbaar]} for c in _alles(db, "collecties")]
    artikelen = [{"handle": a["handle"], "titel": a["titel"], "datum": a["datum"], "html": a["html"] or ""} for a in _alles(db, "artikelen")]
    omleidingen = json.loads((HIER / "omleidingen.json").read_text()) if (HIER / "omleidingen.json").exists() else {}
    cat = {"producten": producten, "collecties": collecties, "artikelen": artikelen, "omleidingen": omleidingen}
    uitvoer.mkdir(parents=True, exist_ok=True)
    (uitvoer / "catalogus.json").write_text(json.dumps(cat, ensure_ascii=False))
    return cat


if __name__ == "__main__":
    c = bouw()
    print(len(c["producten"]), "producten,", len(c["collecties"]), "collecties,", len(c["artikelen"]), "artikelen uit de Revaleur-database")
