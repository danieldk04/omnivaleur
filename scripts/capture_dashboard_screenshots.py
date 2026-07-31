#!/usr/bin/env python3
"""
Legt verse screenshots van de échte Omnivaleur-app vast voor gebruik in de blogs.

Waarom dit bestaat: de content-pijplijn hergebruikte vijf handmatig gemaakte
screenshots uit juli 2026 in ALLE artikelen, met identieke bijschriften. Elk blog
zag er daardoor hetzelfde uit, en zodra de UI veranderde stonden er verouderde
beelden live. Dit script maakt die set opnieuw — uit het gevulde demo-account, in
één run, zodat alle beelden dezelfde dataset en dezelfde UI-versie tonen.

Draai eerst `python3 scripts/seed_demo_account.py` zodat het account gevuld is.

Gebruik:
    python3 scripts/capture_dashboard_screenshots.py            # alles
    python3 scripts/capture_dashboard_screenshots.py dashboard analytics
    python3 scripts/capture_dashboard_screenshots.py --local    # tegen localhost:8000

De beelden komen als WebP in frontend/assets/dashboard/ (1200px breed, ~40-90 kB
per stuk i.p.v. de 300-700 kB PNG's van de vorige set). Elke shot krijgt een
`.json` zijbestand met de gemeten afmetingen, zodat de blogtemplate
width/height kan meegeven en de pagina niet verspringt tijdens het laden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "assets" / "dashboard"

EMAIL = "danieldekoning66+demo@gmail.com"
PASSWORD = "CrossListDemo2026!"
BASE = "https://omnivaleur.com"

# Retina vastleggen en daarna terugschalen naar 1200px — dat geeft scherpe tekst
# in de screenshot zonder een bestand van megabytes.
VIEWPORT = {"width": 1440, "height": 900}
SCALE = 2
TARGET_WIDTH = 1200
WEBP_QUALITY = 82

# Elke shot: welke view, hoe hoog het uitgesneden gebied is, en of er extra
# wachttijd nodig is (grafieken hebben een animatie).
SHOTS = [
    {"key": "dashboard-overview", "view": "dashboard", "height": 820, "wait": 900},
    {"key": "items-crosslisted", "view": "items", "height": 900, "wait": 700},
    {"key": "platforms-connected", "view": "platforms", "height": 760, "wait": 600},
    {"key": "analytics-revenue", "view": "analytics", "height": 900, "wait": 1600},
    {"key": "margin-calculator", "view": "calculator", "height": 700, "wait": 500},
    {"key": "bulk-import", "view": "import", "height": 700, "wait": 700},
    {"key": "refresh-tool", "view": "refresh", "height": 760, "wait": 700},
    {"key": "price-advice", "view": "prijs", "height": 700, "wait": 700},
    {"key": "stale-listings", "view": "stale", "height": 760, "wait": 700},
]


def _login(page, base: str) -> None:
    # De extensie-installatie-overlay dekt de hele app af. app.html declareert
    # showExtOverlay zelf, dus een JS-override wordt overschreven — een
    # !important CSS-regel overleeft ongeacht scriptvolgorde.
    page.add_init_script(
        "document.addEventListener('DOMContentLoaded', () => {"
        "  const s = document.createElement('style');"
        "  s.textContent = '#ext-overlay{display:none !important}';"
        "  document.head.appendChild(s);"
        "});"
    )
    page.goto(f"{base}/login")
    page.fill("#email", EMAIL)
    page.fill("#password", PASSWORD)
    page.click("form button")
    page.wait_for_url(f"{base}/app", timeout=20000)
    page.wait_for_function(
        "document.getElementById('stat-items') && "
        "!['','—'].includes(document.getElementById('stat-items').textContent.trim())",
        timeout=20000,
    )
    page.wait_for_timeout(900)
    page.evaluate("if (typeof dismissExtOverlay === 'function') dismissExtOverlay();")
    page.wait_for_timeout(200)


def _mark_platforms_connected(page) -> None:
    """
    Toont de platform-pagina zoals een gebruiker met gekoppelde accounts hem ziet.
    Puur front-end (state + rerender), niets wordt weggeschreven: het demo-account
    heeft geen echte eBay-/Shopify-koppeling, en een pagina vol "niet verbonden"
    laat de functie zien die je juist wilt tonen niet werken.
    """
    page.evaluate(
        """() => {
            try {
              ['marktplaats','2dehands','vinted','ebay','shopify'].forEach(p => {
                if (state && state.connected && !state.connected.includes(p)) state.connected.push(p);
              });
            } catch (e) {}
            if (typeof renderPlatforms === 'function') renderPlatforms();
        }"""
    )
    page.wait_for_timeout(300)


def _optimise(raw_png: bytes, dest: Path) -> dict:
    from io import BytesIO

    from PIL import Image

    im = Image.open(BytesIO(raw_png)).convert("RGB")
    if im.width > TARGET_WIDTH:
        ratio = TARGET_WIDTH / im.width
        im = im.resize((TARGET_WIDTH, round(im.height * ratio)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
    meta = {"width": im.width, "height": im.height, "bytes": dest.stat().st_size}
    dest.with_suffix(".json").write_text(json.dumps(meta) + "\n")
    return meta


def capture(keys: list[str], base: str) -> int:
    from playwright.sync_api import sync_playwright

    wanted = [s for s in SHOTS if not keys or s["key"] in keys or s["view"] in keys]
    if not wanted:
        print(f"Geen shots die matchen op {keys}. Beschikbaar: {[s['key'] for s in SHOTS]}")
        return 2

    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        page = ctx.new_page()
        _login(page, base)

        for shot in wanted:
            try:
                page.evaluate(f"showView('{shot['view']}')")
                page.wait_for_timeout(shot["wait"])
                if shot["view"] == "platforms":
                    _mark_platforms_connected(page)
                if shot["view"] == "analytics":
                    _widen_analytics_range(page)
                page.evaluate("window.scrollTo(0,0)")
                png = page.screenshot(
                    clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": shot["height"]}
                )
                meta = _optimise(png, OUT / f"{shot['key']}.webp")
                print(f"  ✅ {shot['key']:22s} {meta['width']}x{meta['height']}  {meta['bytes'] // 1000} kB")
            except Exception as e:
                failures += 1
                print(f"  ❌ {shot['key']:22s} mislukt: {e}")

        ctx.close()
        browser.close()

    print()
    if failures:
        print(f"⚠️  {failures} shot(s) mislukt — de bestaande beelden blijven staan.")
    else:
        print(f"Alle screenshots ververst in {OUT.relative_to(ROOT)}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    base = "http://localhost:8000" if "--local" in argv else BASE
    keys = [a for a in argv if not a.startswith("--")]
    print(f"Screenshots vastleggen via {base} (demo-account)…\n")
    return capture(keys, base)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
