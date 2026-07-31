#!/usr/bin/env python3
"""
Legt de platform-interface-screenshots vast die in blogs worden gezet
(frontend/assets/platforms/*.webp), met een echte browser in plaats van een
anonieme screenshot-service.

Waarom niet meer via mshots (scripts/capture_platform_screenshots.py): die
service legt vast wat een kale bot te zien krijgt, en dat is bij deze sites een
cookiebanner of een "Where do you live?"-landenkiezer over de hele pagina heen.
De Vinted-screenshot die maandenlang in élk artikel stond, was precies dat: een
modal, geen catalogus. Een echte browser kan die dialogen wegklikken en daarna
de interface vastleggen zoals een bezoeker hem ziet.

Gebruik:
    python3 scripts/capture_marketplace_screenshots.py            # alle platforms
    python3 scripts/capture_marketplace_screenshots.py vinted ebay

Elke shot komt in frontend/assets/platforms/_review/ — BEKIJK HEM ZELF voordat je
hem live zet, en promoveer dan:
    mv frontend/assets/platforms/_review/vinted.webp frontend/assets/platforms/vinted.webp
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "frontend" / "assets" / "platforms"
REVIEW = ASSETS / "_review"

VIEWPORT = {"width": 1440, "height": 900}
SCALE = 2
TARGET_WIDTH = 1200
WEBP_QUALITY = 82

PLATFORMS = {
    "marktplaats": "https://www.marktplaats.nl",
    "2dehands": "https://www.2dehands.be",
    "vinted": "https://www.vinted.nl/catalog?catalog[]=2050",
    "ebay": "https://www.ebay.nl",
    "shopify": "https://www.shopify.com",
}

# Knoppen die een cookie-/landen-/toestemmingsdialoog wegklikken. Bewust de
# WEIGER-variant waar die bestaat: we accepteren geen tracking om een plaatje te
# maken. Volgorde = volgorde van proberen.
DISMISS_SELECTORS = [
    "#onetrust-reject-all-handler",
    "button#gdpr-banner-decline",
    "[data-testid='reject-all-button']",
    "button[data-testid='domain-select-modal--close-button']",
    "button[aria-label='Close']",
    "button[aria-label='Sluiten']",
    "#gdpr-banner-accept",
    "#onetrust-accept-btn-handler",
    "button:has-text('Alles weigeren')",
    "button:has-text('Weigeren')",
    "button:has-text('Reject all')",
    "button:has-text('Alleen noodzakelijke')",
    # Marktplaats/2dehands zetten de weiger-optie als LINK onderin de dialoog,
    # niet als knop — zonder deze regel bleef de cookiemuur over de hele
    # interface staan en was de screenshot onbruikbaar.
    "a:has-text('Doorgaan zonder te accepteren')",
    "a:has-text('Verdergaan zonder te accepteren')",
    "a:has-text('Continue without accepting')",
]

# Tekst die verraadt dat we een block-/consent-/botmuur hebben vastgelegd i.p.v.
# de echte interface. In beide talen: de NL-variant ontbrak, waardoor een
# Vinted-botcontrole ("Verifieer dat u een mens bent") als geslaagd werd gemeld.
BLOCK_PHRASES = [
    "where do you live",
    "waar woon je",
    "access is temporarily restricted",
    "verify you are human",
    "verifieer dat u een mens bent",
    "please wait",
    "even geduld",
    "enable javascript and cookies",
    "mogen we cookies gebruiken",
]


def _dismiss_overlays(page) -> list[str]:
    """Klikt alles weg wat over de interface heen ligt. Geeft terug wat er is
    geklikt, zodat je in de output ziet of er iets is gebeurd."""
    clicked = []
    for selector in DISMISS_SELECTORS:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=1200):
                element.click(timeout=2500)
                clicked.append(selector)
                page.wait_for_timeout(700)
        except Exception:
            continue
    # Laatste redmiddel: Escape sluit de meeste modals ook.
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    return clicked


def _looks_blocked(page) -> str | None:
    """Grove check op een block-/consent-pagina i.p.v. de echte interface."""
    text = (page.evaluate("document.body.innerText") or "")[:4000].lower()
    for phrase in BLOCK_PHRASES:
        if phrase in text:
            return phrase
    return None


def _optimise(raw_png: bytes, dest: Path) -> dict:
    from io import BytesIO

    from PIL import Image

    im = Image.open(BytesIO(raw_png)).convert("RGB")
    if im.width > TARGET_WIDTH:
        im = im.resize((TARGET_WIDTH, round(im.height * TARGET_WIDTH / im.width)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
    meta = {"width": im.width, "height": im.height, "bytes": dest.stat().st_size}
    dest.with_suffix(".json").write_text(json.dumps(meta) + "\n")
    return meta


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    keys = [a for a in argv if not a.startswith("--")] or list(PLATFORMS)
    unknown = [k for k in keys if k not in PLATFORMS]
    if unknown:
        print(f"Onbekend platform: {unknown}. Bekend: {list(PLATFORMS)}")
        return 2

    REVIEW.mkdir(parents=True, exist_ok=True)
    problems = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=SCALE,
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        for key in keys:
            url = PLATFORMS[key]
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                clicked = _dismiss_overlays(page)
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollTo(0,0)")

                blocked = _looks_blocked(page)
                png = page.screenshot(clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 800})
                meta = _optimise(png, REVIEW / f"{key}.webp")

                status = "⚠️  MOGELIJK GEBLOKKEERD" if blocked else "✅"
                note = f" — gevonden: '{blocked}'" if blocked else ""
                dismissed = f" (weggeklikt: {len(clicked)})" if clicked else ""
                print(f"  {status} {key:14s} {meta['width']}x{meta['height']} {meta['bytes'] // 1000} kB{dismissed}{note}")
                if blocked:
                    problems += 1
            except Exception as e:
                problems += 1
                print(f"  ❌ {key:14s} mislukt: {e}")

        ctx.close()
        browser.close()

    print(f"\nBeelden staan in {REVIEW.relative_to(ROOT)}.")
    print("BEKIJK ELK BESTAND ZELF voordat je het live zet — een block-/consentpagina")
    print("in een artikel is erger dan geen beeld. Promoveren:")
    print(f"    mv {REVIEW.relative_to(ROOT)}/<platform>.webp {ASSETS.relative_to(ROOT)}/")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
