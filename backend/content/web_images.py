"""
Relevante, echte web-afbeeldingen voor content_pages — geen AI-gegenereerde
beelden, maar de officiële merk-logo's van de platforms die een artikel
noemt (Marktplaats, 2dehands, Vinted, eBay, Etsy, Shopify).

Waarom logo's i.p.v. willekeurige stockfoto's: dit zijn de meest relevante,
herkenbare én licentie-veilige beelden voor artikelen die letterlijk over
die platforms gaan. De bestanden zijn éénmalig van het web gehaald
(simpleicons.org voor de vier internationale merken, de officiële favicon
van Marktplaats/2dehands zelf) en LOKAAL gehost in
frontend/assets/platforms/ — precies zoals CROSSLIST_SCREENSHOTS in
generator.py. Lokaal hosten voorkomt de hotlink-/CDN-hash-breuk die remote
URLs vroeg of laat geven.

Wil je de logo's verversen (nieuwe huisstijl van een platform), vervang dan
het bestand in frontend/assets/platforms/ met dezelfde bestandsnaam.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Elk platform: bestandspad + zoekwoorden om het in de tekst te herkennen +
# een korte, feitelijke bijschrift-zin in EN en NL. De bijschriften zijn
# bewust kort en neutraal (geen marketing), zodat ze niet als reclame lezen.
PLATFORMS = [
    {
        "key": "marktplaats",
        "src": "/assets/platforms/marktplaats.png",
        "name": "Marktplaats",
        "aliases": ["marktplaats"],
        "alt_en": "Marktplaats logo",
        "alt_nl": "Marktplaats-logo",
        "cap_en": "Marktplaats — the largest general marketplace in the Netherlands.",
        "cap_nl": "Marktplaats — het grootste algemene handelsplatform van Nederland.",
    },
    {
        "key": "2dehands",
        "src": "/assets/platforms/2dehands.png",
        "name": "2dehands",
        "aliases": ["2dehands", "2ehands", "tweedehands.be"],
        "alt_en": "2dehands logo",
        "alt_nl": "2dehands-logo",
        "cap_en": "2dehands — the Belgian sister marketplace of Marktplaats.",
        "cap_nl": "2dehands — het Belgische zusterplatform van Marktplaats.",
    },
    {
        "key": "vinted",
        "src": "/assets/platforms/vinted.svg",
        "name": "Vinted",
        "aliases": ["vinted"],
        "alt_en": "Vinted logo",
        "alt_nl": "Vinted-logo",
        "cap_en": "Vinted — a fee-free fashion resale app popular across Europe.",
        "cap_nl": "Vinted — een gratis mode-resale-app, populair in heel Europa.",
    },
    {
        "key": "ebay",
        "src": "/assets/platforms/ebay.svg",
        "name": "eBay",
        "aliases": ["ebay", "e-bay"],
        "alt_en": "eBay logo",
        "alt_nl": "eBay-logo",
        "cap_en": "eBay — a global marketplace with a large cross-border buyer base.",
        "cap_nl": "eBay — een wereldwijd platform met een groot internationaal koperspubliek.",
    },
    {
        "key": "etsy",
        "src": "/assets/platforms/etsy.svg",
        "name": "Etsy",
        "aliases": ["etsy"],
        "alt_en": "Etsy logo",
        "alt_nl": "Etsy-logo",
        "cap_en": "Etsy — a marketplace focused on handmade, vintage and craft items.",
        "cap_nl": "Etsy — een platform voor handgemaakte, vintage en creatieve producten.",
    },
    {
        "key": "shopify",
        "src": "/assets/platforms/shopify.svg",
        "name": "Shopify",
        "aliases": ["shopify"],
        "alt_en": "Shopify logo",
        "alt_nl": "Shopify-logo",
        "cap_en": "Shopify — powers your own branded webshop alongside the marketplaces.",
        "cap_nl": "Shopify — draait je eigen webshop naast de marktplaatsen.",
    },
]


def _exists_on_disk(src: str) -> bool:
    return (FRONTEND_DIR / src.lstrip("/")).is_file()


def platforms_in(text: str) -> list[dict]:
    """
    Platforms die in de tekst voorkomen, in volgorde van eerste vermelding,
    zonder dubbelen en alleen als het logobestand echt op schijf staat.
    """
    lower = text.lower()
    found = []
    for p in PLATFORMS:
        pos = min(
            (lower.find(a) for a in p["aliases"] if a in lower),
            default=-1,
        )
        if pos != -1 and _exists_on_disk(p["src"]):
            found.append((pos, p))
        elif pos != -1:
            logger.warning(f"Platform-logo ontbreekt op schijf, overslaan: {p['src']}")
    found.sort(key=lambda pair: pair[0])
    return [p for _, p in found]


def _logo_figure_html(p: dict, language: str) -> str:
    alt = p["alt_nl"] if language == "nl" else p["alt_en"]
    caption = p["cap_nl"] if language == "nl" else p["cap_en"]
    # Logo's zijn géén full-bleed foto's: gecentreerd op een lichte kaart met
    # een vaste hoogte, zodat een klein SVG/PNG niet uitgerekt oogt.
    return (
        f'<figure style="margin:24px 0"><div style="display:flex;align-items:center;'
        f'justify-content:center;background:#f8fafc;border:1px solid #e2e8f0;'
        f'border-radius:10px;padding:28px">'
        f'<img src="{p["src"]}" alt="{alt}" loading="lazy" '
        f'style="height:52px;width:auto;max-width:70%;object-fit:contain"></div>'
        f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px;'
        f'text-align:center">{caption}</figcaption></figure>'
    )


def _h2_positions(body_html: str) -> list[int]:
    return [m.start() for m in re.finditer(r"<h2", body_html)]


def inject_platform_images(body_html: str, keyword: str, language: str = "en", max_images: int = 4) -> str:
    """
    Verspreidt de logo's van de genoemde platforms over de H2-secties van een
    artikel (één beeld ongeveer per sectie), zodat blogs die over andere
    platforms gaan er ook echt beelden van dat platform bij krijgen.

    - Zoekt platforms in zowel het keyword als de body.
    - Slaat de eerste H2 over (intro opent niet op een beeld).
    - Injecteert NIET als de body al platform-logo's bevat (idempotent — veilig
      om nog eens over bestaande pagina's te draaien bij een backfill).
    """
    if "/assets/platforms/" in body_html:
        return body_html  # al voorzien, niet dubbel injecteren

    detected = platforms_in(keyword + " " + body_html)[:max_images]
    if not detected:
        return body_html

    figures = [_logo_figure_html(p, language) for p in detected]

    positions = _h2_positions(body_html)
    usable = positions[1:]  # eerste H2 overslaan

    if not usable:
        # Geen sectiestructuur — plak het eerste logo bovenaan de body.
        return figures[0] + body_html

    step = max(len(usable) // max(len(figures), 1), 1)
    slots = usable[::step][: len(figures)]
    # Van achteren naar voren invoegen zodat eerdere offsets geldig blijven.
    for pos, fig in sorted(zip(slots, figures), key=lambda pair: pair[0], reverse=True):
        body_html = body_html[:pos] + fig + body_html[pos:]

    return body_html
