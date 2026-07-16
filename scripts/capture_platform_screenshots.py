#!/usr/bin/env python3
"""
Vastleggen én valideren van de platform-interface-screenshots die de
content-pijplijn in blogs injecteert (frontend/assets/platforms/*.jpg).

Waarom deze tool bestaat: anonieme screenshot-services serveren soms een
bot-/block-pagina ("Access is temporarily restricted") of een blanco render
i.p.v. de echte interface. Zo'n beeld mag NOOIT live gaan. Deze tool detecteert
dat automatisch met een beeld-heuristiek, en dwingt een menselijke visuele
controle af vóór publicatie.

Gebruik:
    # Audit alle huidige live screenshots (draai dit ALTIJD na een wijziging):
    python3 scripts/capture_platform_screenshots.py --check

    # (Her)leg een platform vast — komt in _review/, NIET direct live:
    python3 scripts/capture_platform_screenshots.py --capture vinted
    python3 scripts/capture_platform_screenshots.py --capture ebay https://www.ebay.nl

Een vastgelegde screenshot belandt in frontend/assets/platforms/_review/. Bekijk
'm met eigen ogen (open het bestand!), en pas als hij de échte interface toont
promoveer je 'm naar live:
    mv frontend/assets/platforms/_review/vinted.jpg frontend/assets/platforms/vinted.jpg
"""
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

ASSETS = Path(__file__).parent.parent / "frontend" / "assets" / "platforms"
REVIEW = ASSETS / "_review"

# Standaard-URL per platform. Etsy staat er bewust NIET bij: het blokkeert
# screenshot-verkeer structureel (zie web_images.py). Voeg 'm alleen toe met een
# echte, ingelogde screenshot.
PLATFORM_URLS = {
    "marktplaats": "https://www.marktplaats.nl",
    "2dehands": "https://www.2dehands.be",
    "vinted": "https://www.vinted.nl/catalog?catalog[]=2050",
    "ebay": "https://www.ebay.nl",
    "shopify": "https://www.shopify.com",
}

# Drempels gekalibreerd op echte interfaces (white≤0.66, colors≥91, std≥47) vs.
# een block/blank-pagina (white 0.97, colors 19, std 14). Ruime marge ertussen.
MAX_WHITE_FRAC = 0.85
MIN_COLORS = 40
MIN_STD = 25.0
MIN_BYTES = 20_000


def _metrics(path: Path):
    """(white_frac, n_colors, std) — grove maat voor 'hoe druk/echt' een beeld is."""
    from PIL import Image
    import numpy as np

    im = Image.open(path).convert("RGB").resize((320, 200))
    a = np.asarray(im).astype(int)
    white = float((a.min(axis=2) > 240).mean())
    q = a // 32
    ncol = len({tuple(px) for px in q.reshape(-1, 3)})
    std = float(a.std())
    return white, ncol, std


def validate(path: Path) -> tuple[bool, str]:
    """True + reden als het beeld er als een echte interface uitziet; anders False + reden."""
    if not path.is_file():
        return False, "bestand ontbreekt"
    size = path.stat().st_size
    if size < MIN_BYTES:
        return False, f"te klein ({size} bytes) — waarschijnlijk placeholder/blanco"
    try:
        white, ncol, std = _metrics(path)
    except Exception as e:
        return False, f"kon beeld niet analyseren: {e}"
    reasons = []
    if white > MAX_WHITE_FRAC:
        reasons.append(f"{white:.0%} wit — waarschijnlijk block-/blanco-pagina")
    if ncol < MIN_COLORS:
        reasons.append(f"slechts {ncol} kleuren — te kaal voor een echte interface")
    if std < MIN_STD:
        reasons.append(f"lage variatie (std {std:.0f}) — waarschijnlijk block-/blanco-pagina")
    detail = f"white={white:.0%} colors={ncol} std={std:.0f} size={size//1000}KB"
    if reasons:
        return False, f"{detail} → " + "; ".join(reasons)
    return True, detail


def check_all() -> int:
    print("Audit van live platform-screenshots:\n")
    bad = 0
    for jpg in sorted(ASSETS.glob("*.jpg")):
        ok, detail = validate(jpg)
        print(f"  {'✅' if ok else '❌'} {jpg.name:18s} {detail}")
        if not ok:
            bad += 1
    print()
    if bad:
        print(f"⚠️  {bad} screenshot(s) zien er verdacht uit — vervang ze vóór publicatie.")
    else:
        print("Alle live screenshots zien er als echte interfaces uit.")
    return 1 if bad else 0


def capture(key: str, url: str | None):
    url = url or PLATFORM_URLS.get(key)
    if not url:
        print(f"Geen standaard-URL voor '{key}'. Geef er expliciet één mee.")
        return 2
    REVIEW.mkdir(exist_ok=True)
    dest = REVIEW / f"{key}.jpg"
    ms = f"https://s0.wp.com/mshots/v1/{quote(url, safe='')}?w=1280&h=800"
    print(f"Vastleggen van {url} …")
    H = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(15):
        r = httpx.get(ms, headers=H, timeout=60, follow_redirects=True)
        ct = r.headers.get("content-type", "")
        if ("jpeg" in ct or "png" in ct) and len(r.content) > MIN_BYTES:
            dest.write_bytes(r.content)
            ok, detail = validate(dest)
            print(f"\nOpgeslagen: {dest}")
            print(f"  {'✅ ziet er goed uit' if ok else '❌ VERDACHT'}: {detail}")
            print("\n⚠️  Bekijk het bestand ZELF vóór je het live zet. Pas na visuele")
            print("    bevestiging dat het de échte interface toont:")
            print(f"    mv {dest} {ASSETS / f'{key}.jpg'}")
            return 0 if ok else 1
        time.sleep(6)
    print("Screenshot bleef genereren (placeholder) — later opnieuw proberen.")
    return 2


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check_all()
    if "--capture" in argv:
        i = argv.index("--capture")
        rest = argv[i + 1:]
        if not rest:
            print("Gebruik: --capture <platform> [url]")
            return 2
        return capture(rest[0], rest[1] if len(rest) > 1 else None)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    raise SystemExit(main(sys.argv[1:]))
