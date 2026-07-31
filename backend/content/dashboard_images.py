"""
Catalogus van échte Omnivaleur-app-screenshots die in artikelen worden gezet.

Vervangt de vaste vijf beelden uit generator.py die in ELK Pillar C-artikel in
dezelfde volgorde met dezelfde bijschriften stonden. Twee dingen veranderen hier:

1. RELEVANTIE — elke screenshot heeft `topics`: alleen als het artikel daar echt
   over gaat, komt hij in aanmerking. Een artikel over verkoopcijfers krijgt de
   analytics-shot, een artikel over bulk-import de import-shot. Voorheen kreeg
   elk artikel dezelfde reeks, ongeacht onderwerp.
2. VARIATIE — welke van de in aanmerking komende beelden je krijgt, en in welke
   volgorde, hangt af van de slug. Twee artikelen over hetzelfde onderwerp tonen
   dus niet dezelfde reeks, terwijl één artikel bij elke hergeneratie wél
   hetzelfde blijft (deterministisch, geen beeld dat zomaar verspringt).

De bestanden komen uit scripts/capture_dashboard_screenshots.py — één run tegen
het gevulde demo-account, dus alle beelden tonen dezelfde dataset en dezelfde
UI-versie. Ververs ze door dat script opnieuw te draaien; de paden blijven gelijk.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Onderwerp-trefwoorden per screenshot. Leeg `topics` = altijd bruikbaar (het
# dashboard past bij elk crosslisting-artikel).
SHOTS = [
    {
        "src": "/assets/dashboard/dashboard-overview.webp",
        "topics": [],
        "alt_en": "Omnivaleur dashboard showing 40 items live across Marktplaats, 2dehands, Vinted, eBay and Shopify",
        "alt_nl": "Omnivaleur-dashboard met 40 items live op Marktplaats, 2dehands, Vinted, eBay en Shopify",
        "cap_en": "The Omnivaleur dashboard: 40 items, 159 active listings spread over five marketplaces, with the per-platform count broken out underneath.",
        "cap_nl": "Het Omnivaleur-dashboard: 40 items, 159 actieve advertenties verdeeld over vijf marktplaatsen, met daaronder het aantal per platform.",
    },
    {
        "src": "/assets/dashboard/items-crosslisted.webp",
        "topics": ["list", "listing", "crosslist", "cross-list", "publish", "inventory", "stock", "bulk"],
        "alt_en": "Omnivaleur item list showing per-platform publish status for every item",
        "alt_nl": "Omnivaleur-itemlijst met per item de publicatiestatus per platform",
        "cap_en": "Every item shows its status per marketplace at a glance — which platforms it is already live on, and which still need publishing.",
        "cap_nl": "Elk item toont in één oogopslag zijn status per marktplaats — waar het al live staat en waar het nog gepubliceerd moet worden.",
    },
    {
        "src": "/assets/dashboard/analytics-revenue.webp",
        "topics": ["revenue", "profit", "margin", "earn", "money", "price", "pricing", "fee", "fees", "analytic", "sales", "income", "tax", "dac7"],
        "alt_en": "Omnivaleur analytics with revenue, profit and average sale price broken down per marketplace",
        "alt_nl": "Omnivaleur-analytics met omzet, winst en gemiddelde verkoopprijs per marktplaats",
        "cap_en": "Revenue and profit split per marketplace, based on the real sale price rather than the asking price — no spreadsheet export needed.",
        "cap_nl": "Omzet en winst per marktplaats, gerekend met de échte verkoopprijs in plaats van de vraagprijs — zonder export naar een spreadsheet.",
    },
    {
        "src": "/assets/dashboard/platforms-connected.webp",
        "topics": ["connect", "account", "api", "integration", "platform", "setup", "sync", "link"],
        "alt_en": "Omnivaleur platform connection screen for Marktplaats, 2dehands, Vinted, eBay, Etsy and Shopify",
        "alt_nl": "Omnivaleur-koppelscherm voor Marktplaats, 2dehands, Vinted, eBay, Etsy en Shopify",
        "cap_en": "Each marketplace is connected once from this screen; after that, publishing and stock sync run against all of them together.",
        "cap_nl": "Elke marktplaats koppel je hier één keer; daarna lopen publiceren en voorraadsynchronisatie automatisch over alle platforms tegelijk.",
    },
    {
        "src": "/assets/dashboard/margin-calculator.webp",
        "topics": ["margin", "profit", "fee", "fees", "price", "pricing", "cost", "calculat", "money", "worth"],
        "alt_en": "Omnivaleur margin calculator working out profit after platform fees and shipping",
        "alt_nl": "Omnivaleur-margecalculator die winst berekent na platformkosten en verzending",
        "cap_en": "The margin calculator works backwards from the profit you want, so a platform's fee percentage never quietly eats the difference.",
        "cap_nl": "De margecalculator rekent terug vanaf de winst die je wilt overhouden, zodat het feepercentage van een platform het verschil niet stilletjes opeet.",
    },
    {
        "src": "/assets/dashboard/bulk-import.webp",
        "topics": ["import", "bulk", "migrate", "move", "switch", "existing", "transfer", "start"],
        "alt_en": "Omnivaleur bulk import screen pulling in existing listings from a marketplace",
        "alt_nl": "Omnivaleur bulk-importscherm dat bestaande advertenties van een marktplaats ophaalt",
        # Bijschrift zegt er eerlijk bij dat alleen Vinted-import nu werkt: het
        # scherm zelf toont "Coming soon" bij de andere marktplaatsen, en een
        # bijschrift dat meer belooft dan de screenshot laat zien is precies het
        # soort detail waar een lezer een tool op afrekent.
        "cap_en": "Bulk import scans a marketplace's own \"my listings\" page and turns what it finds into items. Vinted import is live today; the other marketplaces are still in progress.",
        "cap_nl": "Bulk-import scant de eigen \"mijn advertenties\"-pagina van een marktplaats en maakt er items van. Vinted-import werkt nu; de andere marktplaatsen zijn nog in aanbouw.",
    },
    {
        "src": "/assets/dashboard/refresh-tool.webp",
        "topics": ["refresh", "bump", "relist", "visibility", "vinted", "rank", "ranking", "views", "boost"],
        "alt_en": "Omnivaleur Vinted refresh tool showing its daily cap and an explicit risk disclosure",
        "alt_nl": "Omnivaleur Vinted-verversingstool met daglimiet en expliciete risicomelding",
        "cap_en": "The refresh tool caps itself per day and states plainly that no tool can guarantee a marketplace won't flag an account — a disclosure most competitors leave out.",
        "cap_nl": "De verversingstool begrenst zichzelf per dag en zegt er ronduit bij dat geen enkele tool kan garanderen dat een marktplaats een account niet markeert — een melding die de meeste concurrenten weglaten.",
    },
    {
        "src": "/assets/dashboard/price-advice.webp",
        "topics": ["price", "pricing", "worth", "value", "compare", "competitor", "market", "demand"],
        "alt_en": "Omnivaleur price advice screen comparing what similar items sell for",
        "alt_nl": "Omnivaleur-prijsadviesscherm dat vergelijkt waarvoor soortgelijke items weggaan",
        "cap_en": "Price advice compares an item against what comparable stock actually sold for, instead of guessing from the original retail price.",
        "cap_nl": "Het prijsadvies vergelijkt een item met waarvoor vergelijkbare voorraad écht is verkocht, in plaats van te gokken op de oorspronkelijke winkelprijs.",
    },
    {
        "src": "/assets/dashboard/stale-listings.webp",
        "topics": ["stale", "old", "unsold", "slow", "sitting", "dead", "clear", "inventory", "stock", "aging"],
        "alt_en": "Omnivaleur stale stock screen flagging listings that have been sitting unsold",
        "alt_nl": "Omnivaleur-scherm voor blijven liggen voorraad, met advertenties die al lang niet verkopen",
        "cap_en": "Stale stock is flagged automatically, so the items quietly sitting unsold for months surface instead of disappearing down the list.",
        "cap_nl": "Blijvende voorraad wordt automatisch gemarkeerd, zodat items die al maanden onverkocht liggen bovendrijven in plaats van onderaan te verdwijnen.",
    },
]

# Nooit meer dan dit aantal app-screenshots per artikel — daarboven wordt het een
# brochure in plaats van een artikel, en duwen de beelden de tekst uit beeld.
MAX_PER_ARTICLE = 3


def _exists(src: str) -> bool:
    return (FRONTEND_DIR / src.lstrip("/")).is_file()


def dimensions(src: str) -> tuple[int, int] | None:
    """
    Afmetingen uit het .json-zijbestand dat de capture-tool meeschrijft. Nodig om
    width/height op de <img> te zetten: zonder die twee reserveert de browser geen
    ruimte en springt de tekst omlaag zodra het beeld inlaadt (layout shift, en
    dat telt mee in Google's Core Web Vitals).
    """
    meta_path = (FRONTEND_DIR / src.lstrip("/")).with_suffix(".json")
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        return int(meta["width"]), int(meta["height"])
    except Exception:
        return None


def relevant_shots(keyword: str, title: str, slug: str, body_html: str = "") -> list[dict]:
    """
    De screenshots die bij dít artikel horen, in een volgorde die per slug
    verschilt. Matcht op keyword + titel + koppen — bewust NIET op de volledige
    body: één terloopse vermelding van "price" ergens in een alinea zou anders al
    genoeg zijn om een prijsscherm binnen te halen dat nergens op slaat.
    """
    import re

    headings = " ".join(re.findall(r"<h[23][^>]*>(.*?)</h[23]>", body_html, re.S | re.I))
    haystack = f"{keyword} {title} {re.sub(r'<[^>]+>', ' ', headings)}".lower()

    matched = []
    generic = []
    for shot in SHOTS:
        if not _exists(shot["src"]):
            logger.warning("App-screenshot ontbreekt op schijf, overslaan: %s", shot["src"])
            continue
        if not shot["topics"]:
            generic.append(shot)
        elif any(topic in haystack for topic in shot["topics"]):
            matched.append(shot)

    # Slug bepaalt de rotatie: hetzelfde artikel krijgt altijd dezelfde reeks,
    # twee verschillende artikelen over hetzelfde onderwerp niet.
    #
    # De generieke shot(s) draaien MEE in de rotatie in plaats van altijd
    # vooraan te staan. Stonden ze vast op plek één, dan opende de helft van de
    # artikelen alsnog op precies hetzelfde dashboardbeeld — hetzelfde probleem
    # in het klein als waar deze module voor gebouwd is.
    pool = matched + generic
    if pool:
        offset = int(hashlib.sha256(slug.encode()).hexdigest()[:8], 16) % len(pool)
        pool = pool[offset:] + pool[:offset]

    return pool[:MAX_PER_ARTICLE]


def figure_html(shot: dict, language: str = "en") -> str:
    alt = shot["alt_nl"] if language == "nl" else shot["alt_en"]
    caption = shot["cap_nl"] if language == "nl" else shot["cap_en"]
    dims = dimensions(shot["src"])
    size_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
    return (
        f'<figure class="app-shot" style="margin:28px 0"><img src="{shot["src"]}" alt="{alt}"'
        f'{size_attrs} loading="lazy" decoding="async" '
        f'style="width:100%;height:auto;border-radius:10px;border:1px solid #e2e8f0">'
        f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px;text-align:center">{caption}</figcaption></figure>'
    )
