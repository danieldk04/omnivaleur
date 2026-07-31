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
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
FONT_CANDIDATES_REGULAR = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

PILLAR_LABELS = {
    "A": "PLATFORM GUIDE",
    "B": "RESELLER GUIDE",
    "C": "HONEST COMPARISON",
}

# Merkkleuren uit frontend/templates/_chrome_style.html. De hero varieert binnen
# deze familie — nooit erbuiten, anders herkent niemand het als Omnivaleur.
# Vier paren, gekozen op slug-hash: genoeg variatie om 25+ artikelen visueel uit
# elkaar te houden, weinig genoeg om één huisstijl te blijven.
PALETTES = [
    ((37, 99, 235), (52, 211, 153)),    # merkblauw → mint
    ((30, 64, 175), (56, 189, 248)),    # diepblauw → hemelsblauw
    ((67, 56, 202), (139, 92, 246)),    # indigo → paars
    ((15, 118, 110), (52, 211, 153)),   # teal → mint
]

PLATFORM_WORDS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify"]


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


def _gradient(size: tuple[int, int], start: tuple, end: tuple, angle_down: bool):
    """Diagonale verloop-achtergrond. `angle_down` kantelt 'm de andere kant op,
    wat twee visueel duidelijk verschillende beelden uit hetzelfde kleurpaar geeft."""
    from PIL import Image

    w, h = size
    base = Image.new("RGB", (w, h))
    pixels = base.load()
    for y in range(h):
        for x in range(0, w, 4):  # om de 4px berekenen en invullen — 4x sneller, niet zichtbaar
            t = ((x / w) + (1 - y / h if angle_down else y / h)) / 2
            color = tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))
            for dx in range(4):
                if x + dx < w:
                    pixels[x + dx, y] = color
    return base


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


def hero_url(slug: str) -> str:
    return f"{HERO_URL_PREFIX}/{slug}.png"


def hero_path(slug: str) -> Path:
    return HERO_DIR / f"{slug}.png"


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
        from PIL import Image, ImageDraw, ImageFilter

        seed = _slug_seed(slug)
        start, end = PALETTES[seed % len(PALETTES)]
        img = _gradient((WIDTH, HEIGHT), start, end, angle_down=bool((seed >> 3) & 1))
        draw = ImageDraw.Draw(img, "RGBA")

        # Zachte lichtcirkels: geven diepte en maken twee artikelen met hetzelfde
        # kleurpaar alsnog van elkaar te onderscheiden (positie hangt aan de slug).
        glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        for i in range(3):
            r = 160 + ((seed >> (i * 5)) % 200)
            cx = 260 + ((seed >> (i * 7)) % (WIDTH - 200))
            cy = ((seed >> (i * 11)) % HEIGHT)
            gdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 22))
        img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(70))).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        font_brand = _load_font(FONT_CANDIDATES_BOLD, 30)
        font_chip = _load_font(FONT_CANDIDATES_BOLD, 20)
        font_meta = _load_font(FONT_CANDIDATES_REGULAR, 24)
        if not font_brand:
            logger.warning("Geen bruikbaar font gevonden — hero overgeslagen voor %s", slug)
            return None

        margin = 72

        # Merkregel bovenaan.
        draw.text((margin, 56), "OMNIVALEUR", font=font_brand, fill=(255, 255, 255))

        # Pillar-chip rechtsboven.
        label = PILLAR_LABELS.get(pillar, "RESELLER GUIDE")
        chip_w = draw.textlength(label, font=font_chip) + 36
        chip_x = WIDTH - margin - chip_w
        draw.rounded_rectangle([chip_x, 52, chip_x + chip_w, 92], radius=20, fill=(255, 255, 255, 46))
        draw.text((chip_x + 18, 62), label, font=font_chip, fill=(255, 255, 255))

        # Titel: schaalt terug tot hij in maximaal 4 regels past. Lange
        # programmatic titels ("... Crosslisting in 2026: The Complete Guide")
        # zouden anders van het beeld af lopen.
        title = re.sub(r"\s+", " ", title or "").strip()
        lines: list[str] = []
        for size in (64, 58, 52, 46, 40):
            font_title = _load_font(FONT_CANDIDATES_BOLD, size)
            lines = _wrap(draw, title, font_title, WIDTH - margin * 2)
            if len(lines) <= 4:
                break
        lines = lines[:4]

        line_height = round(size * 1.22)
        block_height = line_height * len(lines)
        y = (HEIGHT - block_height) // 2 + 10
        for line in lines:
            # Lichte schaduw houdt de tekst leesbaar boven de lichtste plek van
            # het verloop (WCAG-contrast wisselt over de breedte van het beeld).
            draw.text((margin + 2, y + 2), line, font=font_title, fill=(15, 23, 42, 70))
            draw.text((margin, y), line, font=font_title, fill=(255, 255, 255))
            y += line_height

        # Platformregel onderaan — vertelt in één blik waar het artikel over gaat.
        platforms = _platforms_in(f"{title} {keyword}") or ["Marktplaats", "Vinted", "eBay", "Shopify"]
        footer = "  ·  ".join(platforms[:5])
        if font_meta:
            draw.line([(margin, HEIGHT - 108), (margin + 56, HEIGHT - 108)], fill=(255, 255, 255, 200), width=4)
            draw.text((margin, HEIGHT - 88), footer, font=font_meta, fill=(255, 255, 255, 232))

        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "PNG", optimize=True)
        logger.info("Hero gegenereerd voor %s (%d kB)", slug, dest.stat().st_size // 1000)
        return hero_url(slug)
    except Exception as e:
        logger.error("Hero-generatie mislukt voor %s (artikel publiceert zonder): %s", slug, e)
        return None
