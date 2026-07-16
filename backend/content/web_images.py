"""
Relevante, echte web-afbeeldingen voor content_pages — geen AI-gegenereerde
beelden, maar echte SCREENSHOTS van de interface van elk platform dat een
artikel noemt (Marktplaats, 2dehands, Vinted, eBay, Etsy, Shopify): precies
hoe die site er nu uitziet als je hem opent.

Waarom screenshots i.p.v. logo's of stockfoto's: een artikel dat over
crosslisten tussen deze platforms gaat, wordt concreter als de lezer de échte
interface ziet (zoekbalk, categorieën, listinggrid) — geen willekeurige foto
van "iemand die iets fotografeert". De bestanden zijn éénmalig via een gratis
screenshot-service van de live site gehaald (WordPress mShots / thum.io) en
LOKAAL gehost in frontend/assets/platforms/ — precies zoals
CROSSLIST_SCREENSHOTS in generator.py. Lokaal hosten voorkomt de
hotlink-/generatie-latentie die remote screenshot-URLs geven.

Wil je een screenshot verversen (het platform heeft z'n interface vernieuwd),
haal 'm opnieuw op en vervang het bestand in frontend/assets/platforms/ met
dezelfde bestandsnaam. Voorbeeld om er één te hergenereren:
    https://s0.wp.com/mshots/v1/<url-encoded platform-url>?w=1280&h=800
(poll tot je een echte JPEG/PNG krijgt i.p.v. de 'generating'-placeholder).
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Elk platform: pad naar de screenshot + zoekwoorden om het in de tekst te
# herkennen + een korte, feitelijke bijschrift-zin in EN en NL. De bijschriften
# beschrijven wat op de screenshot te zien is (de interface), bewust kort en
# neutraal — geen marketing.
PLATFORMS = [
    {
        "key": "marktplaats",
        "src": "/assets/platforms/marktplaats.jpg",
        "name": "Marktplaats",
        "aliases": ["marktplaats"],
        "alt_en": "Screenshot of the Marktplaats marketplace interface",
        "alt_nl": "Screenshot van de Marktplaats-interface",
        "cap_en": "The Marktplaats interface — search bar, categories and the listing grid sellers publish into.",
        "cap_nl": "De Marktplaats-interface — zoekbalk, categorieën en het advertentie-overzicht waar verkopers in plaatsen.",
    },
    {
        "key": "2dehands",
        "src": "/assets/platforms/2dehands.jpg",
        "name": "2dehands",
        "aliases": ["2dehands", "2ehands", "tweedehands.be"],
        "alt_en": "Screenshot of the 2dehands marketplace interface",
        "alt_nl": "Screenshot van de 2dehands-interface",
        "cap_en": "2dehands — the Belgian sister site of Marktplaats, with the same listing layout.",
        "cap_nl": "2dehands — de Belgische zustersite van Marktplaats, met dezelfde advertentie-indeling.",
    },
    {
        "key": "vinted",
        "src": "/assets/platforms/vinted.jpg",
        "name": "Vinted",
        "aliases": ["vinted"],
        "alt_en": "Screenshot of the Vinted catalog interface with filters",
        "alt_nl": "Screenshot van de Vinted-catalogus met filters",
        "cap_en": "The Vinted catalog — category filters (size, brand, condition) that map to the fields you fill per listing.",
        "cap_nl": "De Vinted-catalogus — filters op maat, merk en staat, die aansluiten op de velden die je per advertentie invult.",
    },
    {
        "key": "ebay",
        "src": "/assets/platforms/ebay.jpg",
        "name": "eBay",
        "aliases": ["ebay", "e-bay"],
        "alt_en": "Screenshot of the eBay marketplace homepage",
        "alt_nl": "Screenshot van de eBay-marktplaats",
        "cap_en": "The eBay interface — global reach and a category structure listings must be mapped into.",
        "cap_nl": "De eBay-interface — wereldwijd bereik en een rubriekenstructuur waar advertenties in moeten passen.",
    },
    {
        "key": "etsy",
        "src": "/assets/platforms/etsy.jpg",
        "name": "Etsy",
        "aliases": ["etsy"],
        "alt_en": "Screenshot of the Etsy marketplace interface",
        "alt_nl": "Screenshot van de Etsy-interface",
        "cap_en": "The Etsy storefront — built around handmade, vintage and craft listings.",
        "cap_nl": "De Etsy-etalage — opgezet rond handgemaakte, vintage en creatieve advertenties.",
    },
    {
        "key": "shopify",
        "src": "/assets/platforms/shopify.jpg",
        "name": "Shopify",
        "aliases": ["shopify"],
        "alt_en": "Screenshot of the Shopify website",
        "alt_nl": "Screenshot van de Shopify-website",
        "cap_en": "Shopify — your own branded webshop running alongside the marketplaces.",
        "cap_nl": "Shopify — je eigen webshop met eigen huisstijl, naast de marktplaatsen.",
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


def _screenshot_figure_html(p: dict, language: str) -> str:
    alt = p["alt_nl"] if language == "nl" else p["alt_en"]
    caption = p["cap_nl"] if language == "nl" else p["cap_en"]
    # Full-width screenshot, identiek gestyled aan CROSSLIST_SCREENSHOTS in
    # generator.py zodat platform-screenshots en eigen dashboard-screenshots er
    # in één artikel consistent uitzien.
    return (
        f'<figure style="margin:24px 0"><img src="{p["src"]}" alt="{alt}" '
        f'loading="lazy" style="width:100%;border-radius:10px;border:1px solid #e2e8f0">'
        f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px;'
        f'text-align:center">{caption}</figcaption></figure>'
    )


def _h2_positions(body_html: str) -> list[int]:
    return [m.start() for m in re.finditer(r"<h2", body_html)]


# Verwijdert eerder-geïnjecteerde platform-figuren (elke <figure> die naar
# /assets/platforms/ verwijst). Nodig bij een re-backfill: als de screenshots
# vervangen worden of het figuur-formaat wijzigt, moeten de oude eruit vóórdat
# de nieuwe erin gaan — anders blijven gebroken/verouderde beelden staan.
_PLATFORM_FIGURE_RE = re.compile(r"<figure\b[^>]*>(?:(?!</figure>).)*?/assets/platforms/(?:(?!</figure>).)*?</figure>", re.DOTALL)


def strip_platform_images(body_html: str) -> str:
    return _PLATFORM_FIGURE_RE.sub("", body_html)


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

    figures = [_screenshot_figure_html(p, language) for p in detected]

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
