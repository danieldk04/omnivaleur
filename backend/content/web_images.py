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
import json
import logging
import re
from pathlib import Path

from backend.content.figures import contains_figures, spread_figures, strip_figures

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Elk platform: pad naar de screenshot + zoekwoorden om het in de tekst te
# herkennen + een korte, feitelijke bijschrift-zin in EN en NL. De bijschriften
# beschrijven wat op de screenshot te zien is (de interface), bewust kort en
# neutraal — geen marketing.
PLATFORMS = [
    {
        "key": "marktplaats",
        "src": "/assets/platforms/marktplaats.webp",
        "name": "Marktplaats",
        "aliases": ["marktplaats"],
        "alt_en": "Screenshot of the Marktplaats marketplace interface",
        "alt_nl": "Screenshot van de Marktplaats-interface",
        "cap_en": "The Marktplaats interface — search bar, categories and the listing grid sellers publish into.",
        "cap_nl": "De Marktplaats-interface — zoekbalk, categorieën en het advertentie-overzicht waar verkopers in plaatsen.",
    },
    {
        "key": "2dehands",
        "src": "/assets/platforms/2dehands.webp",
        "name": "2dehands",
        "aliases": ["2dehands", "2ehands", "tweedehands.be"],
        "alt_en": "Screenshot of the 2dehands marketplace interface",
        "alt_nl": "Screenshot van de 2dehands-interface",
        "cap_en": "2dehands — the Belgian sister site of Marktplaats, with the same listing layout.",
        "cap_nl": "2dehands — de Belgische zustersite van Marktplaats, met dezelfde advertentie-indeling.",
    },
    # Vinted staat er bewust NIET bij. Twee redenen, allebei hard:
    #   1. Het beeld dat hier maandenlang stond, was geen catalogus maar Vinted's
    #      "Where do you live?"-landenkiezer over de hele pagina heen — dat stond
    #      dus in élk artikel dat Vinted noemde.
    #   2. Vinted serveert een botcontrole ("Verifieer dat u een mens bent") aan
    #      geautomatiseerde browsers. Dat is een bewuste maatregel van hun kant en
    #      die omzeilen we niet.
    # Artikelen over Vinted verliezen hier weinig mee: de eigen app-screenshots
    # (dashboard_images.py) tonen Vinted-listings gewoon in de interface.
    {
        "key": "ebay",
        "src": "/assets/platforms/ebay.webp",
        "name": "eBay",
        "aliases": ["ebay", "e-bay"],
        "alt_en": "Screenshot of the eBay marketplace homepage",
        "alt_nl": "Screenshot van de eBay-marktplaats",
        "cap_en": "The eBay interface — global reach and a category structure listings must be mapped into.",
        "cap_nl": "De eBay-interface — wereldwijd bereik en een rubriekenstructuur waar advertenties in moeten passen.",
    },
    # Etsy is bewust WEGGELATEN: het serveert bot-/screenshot-verkeer een
    # "Access is temporarily restricted"-blokpagina i.p.v. de echte interface,
    # via elke anonieme screenshot-service. Liever géén beeld dan een blokpagina
    # in een artikel. Wil je Etsy alsnog toevoegen, maak dan een echte screenshot
    # vanuit een ingelogde/echte browsersessie, leg 'm neer als
    # frontend/assets/platforms/etsy.jpg en zet dit blok terug.
    {
        "key": "shopify",
        "src": "/assets/platforms/shopify.webp",
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


def _dimensions(src: str) -> tuple[int, int] | None:
    """Afmetingen uit het .json-zijbestand naast de screenshot, voor width/height
    op de <img> — zonder die twee springt de tekst omlaag zodra het beeld inlaadt."""
    meta_path = (FRONTEND_DIR / src.lstrip("/")).with_suffix(".json")
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        return int(meta["width"]), int(meta["height"])
    except Exception:
        return None


def platforms_in(text: str) -> list[dict]:
    """
    Platforms die in de tekst voorkomen, in volgorde van eerste vermelding,
    zonder dubbelen en alleen als het screenshotbestand echt op schijf staat.
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
            logger.warning(f"Platform-screenshot ontbreekt op schijf, overslaan: {p['src']}")
    found.sort(key=lambda pair: pair[0])
    return [p for _, p in found]


def topic_platforms(keyword: str, title: str, body_html: str = "") -> list[dict]:
    """
    De platforms waar het artikel ECHT over gaat.

    Waarom dit niet meer de hele body afzoekt: dat deed het wél, en daardoor
    kreeg het artikel "Vinted naar eBay" een Marktplaats-screenshot én een
    Shopify-screenshot — puur omdat die woorden in een interne link onderaan
    stonden. Volslagen irrelevant beeld bij de tekst.

    Nu telt alleen het keyword en de titel; komt daar niets uit (bv. een
    niche-artikel als "sneaker reselling automation" dat geen platformnaam in de
    titel heeft), dan vallen we terug op de H2-koppen. De body zelf nooit.
    """
    primary = platforms_in(f"{keyword} {title}")
    if primary:
        return primary

    headings = " ".join(re.findall(r"<h2[^>]*>(.*?)</h2>", body_html, re.S | re.I))
    return platforms_in(re.sub(r"<[^>]+>", " ", headings))


def _screenshot_figure_html(p: dict, language: str) -> str:
    alt = p["alt_nl"] if language == "nl" else p["alt_en"]
    caption = p["cap_nl"] if language == "nl" else p["cap_en"]
    dims = _dimensions(p["src"])
    size_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
    # Zelfde styling als de app-screenshots (dashboard_images.py), zodat beide
    # soorten beeld er in één artikel consistent uitzien.
    return (
        f'<figure class="platform-shot" style="margin:24px 0"><img src="{p["src"]}" alt="{alt}"'
        f'{size_attrs} loading="lazy" decoding="async" '
        f'style="width:100%;height:auto;border-radius:10px;border:1px solid #e2e8f0">'
        f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px;'
        f'text-align:center">{caption}</figcaption></figure>'
    )


def strip_platform_images(body_html: str) -> str:
    """Verwijdert eerder ingevoegde platform-figuren. Nodig bij een backfill:
    de oude (irrelevante, ongecomprimeerde .jpg) beelden moeten eruit vóór de
    nieuwe erin, anders stapelen ze op."""
    return strip_figures(body_html, "/assets/platforms/")


def inject_platform_images(
    body_html: str,
    keyword: str,
    language: str = "en",
    max_images: int = 3,
    title: str = "",
) -> str:
    """
    Verspreidt screenshots van de platforms waar het artikel over gaat over de
    H2-secties. Idempotent: staat er al zo'n beeld in, dan gebeurt er niets
    (veilig om nog eens over bestaande pagina's te draaien).
    """
    if contains_figures(body_html, "/assets/platforms/"):
        return body_html

    detected = topic_platforms(keyword, title, body_html)[:max_images]
    if not detected:
        return body_html

    return spread_figures(body_html, [_screenshot_figure_html(p, language) for p in detected])
