"""
Unieke hero-/deelafbeelding per artikel.

Waarom dit bestaat: elk blog toonde bovenaan hetzelfde blauw-groene kleurvlak met
een ∞-teken, en 24 van de 25 pagina's hadden helemaal geen og:image — deel je een
artikel, dan kwam er een leeg blok. Eén generiek beeld voor 25 artikelen is
bovendien precies het signaal ("massaal geproduceerd, niets eigens") dat je bij
programmatic SEO juist niet wilt afgeven.

Waarom geen AI-beeldmodel: een hero moet de ARTIKELTITEL leesbaar tonen, en
beeldmodellen renderen tekst onbetrouwbaar tot onleesbaar (zie dezelfde afweging
in infographics.py). Dit tekent het beeld deterministisch met PIL: de titel staat
er gegarandeerd goed op, elk artikel krijgt een eigen kleurstelling afgeleid uit
zijn slug, en het kost geen API-call.

Deterministisch per slug: dezelfde slug levert altijd exact hetzelfde beeld op.
Een hergenereerd artikel (evaluator-refresh) krijgt dus geen ander plaatje, en er
ontstaan geen dubbele bestanden.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
HERO_DIR = FRONTEND_DIR / "assets" / "blog" / "hero"
HERO_URL_PREFIX = "/assets/blog/hero"

# 1200x630 is het formaat dat Open Graph, LinkedIn, X en WhatsApp allemaal zonder
# bijsnijden tonen. Ook het formaat dat Google voor Article-schema verwacht.
WIDTH, HEIGHT = 1200, 630

# Kandidaat-fontpaden, in volgorde van voorkeur: macOS (lokaal draaien) en de
# DejaVu-set die op ubuntu-runners staat (de GitHub Action die dagelijks
# publiceert). Zonder werkbaar font valt de generatie zacht terug op None en
# publiceert het artikel gewoon zonder hero.
FONT_CANDIDATES_BOLD = [
    str(FRONTEND_DIR / "assets" / "site" / "fonts" / "clash-grotesk-600.woff2"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
FONT_CANDIDATES_REGULAR = [
    str(FRONTEND_DIR / "assets" / "site" / "fonts" / "hanken-grotesk-var.woff2"),
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

# Kleuren uit frontend/assets/site/site.css (sinds de nieuwe site van 06-11-2026):
# vlak merkblauw, inktblauw en mint, geen verloop. Kleur per PILLAR, zodat een
# terugkerende lezer aan de kleur ziet wat voor artikel het is.
PALETTES = {
    "A": ((6, 75, 199), (250, 251, 253)),    # platformgids: kobalt met witte letters
    "B": ((10, 27, 58), (250, 251, 253)),    # verkopersgids: inkt met witte letters
    "C": ((134, 239, 186), (10, 27, 58)),    # vergelijking: mint met inkt letters
}

PLATFORM_WORDS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify", "WooCommerce"]


def _slug_seed(slug: str) -> int:
    return int(hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8], 16)


def _load_font(candidates: list[str], size: int):
    from PIL import ImageFont

    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _platforms_in(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in PLATFORM_WORDS if p.lower() in lower]


# JPEG, geen PNG: een verloop met tekst wordt als PNG ~130 kB en als JPEG ~45 kB
# bij visueel gelijk resultaat. WebP zou nóg kleiner zijn, maar niet elk platform
# dat og:image uitleest ondersteunt het — en dit beeld moet het overal doen.
def hero_url(slug: str) -> str:
    return f"{HERO_URL_PREFIX}/{slug}.jpg"


def hero_path(slug: str) -> Path:
    return HERO_DIR / f"{slug}.jpg"


def generate_hero(slug: str, title: str, pillar: str, keyword: str = "", force: bool = False) -> str | None:
    """
    Tekent de hero voor één artikel en geeft het publieke pad terug
    (/assets/blog/hero/{slug}.png), of None als het niet lukte — een mislukte
    hero mag een publicatie nooit blokkeren.

    Bestaat het bestand al, dan wordt het niet opnieuw getekend tenzij
    `force=True`. Zo blijft een dagelijkse cron goedkoop en verandert een
    bestaande gedeelde link nooit van beeld.
    """
    dest = hero_path(slug)
    if dest.is_file() and not force:
        return hero_url(slug)

    try:
        from PIL import Image, ImageDraw

        veld, inkt = PALETTES.get(pillar, PALETTES["B"])
        img = Image.new("RGB", (WIDTH, HEIGHT), veld)
        draw = ImageDraw.Draw(img)

        font_brand = _load_font(FONT_CANDIDATES_BOLD, 34)
        font_meta = _load_font(FONT_CANDIDATES_REGULAR, 26)
        if not font_brand:
            logger.warning("Geen bruikbaar font gevonden, hero overgeslagen voor %s", slug)
            return None

        margin = 72
        draw.text((margin, 60), "Omnivaleur", font=font_brand, fill=inkt)

        # Titel: schaalt terug tot hij in maximaal 4 regels past. Lange
        # programmatic titels ("... Crosslisting in 2026: The Complete Guide")
        # zouden anders van het beeld af lopen.
        title = re.sub(r"\s+", " ", title or "").strip()
        lines: list[str] = []
        for size in (76, 68, 60, 52, 46):
            font_title = _load_font(FONT_CANDIDATES_BOLD, size)
            lines = _wrap(draw, title, font_title, WIDTH - margin * 2)
            if len(lines) <= 4:
                break
        lines = lines[:4]

        # Onderaan gelijnd, boven de platformregel: dezelfde kop-links-onder als de site.
        line_height = round(size * 1.12)
        y = HEIGHT - 128 - line_height * len(lines)
        for line in lines:
            draw.text((margin, y), line, font=font_title, fill=inkt)
            y += line_height

        # Platformregel onderaan: vertelt in één blik waar het artikel over gaat.
        platforms = _platforms_in(f"{title} {keyword}") or ["Marktplaats", "Vinted", "eBay", "Shopify"]
        footer = "  ·  ".join(platforms[:5])
        if font_meta:
            draw.text((margin, HEIGHT - 92), footer, font=font_meta, fill=inkt)

        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=88, optimize=True, progressive=True)
        logger.info("Hero gegenereerd voor %s (%d kB)", slug, dest.stat().st_size // 1000)
        return hero_url(slug)
    except Exception as e:
        logger.error("Hero-generatie mislukt voor %s (artikel publiceert zonder): %s", slug, e)
        return None
