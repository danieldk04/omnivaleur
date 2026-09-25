"""
Concurrentieanalyse: zoekt de top-3 organische resultaten voor een keyword
(via DuckDuckGo HTML, geen API-key nodig) en brengt per pagina in kaart wat de
generator moet overtreffen: titel, metabeschrijving, lengte, kopjes, de vragen
die ze beantwoorden en welke structuur (tabellen, afbeeldingen, schema) ze
gebruiken.

Waarom meer dan alleen kopjes (25-09-2026): met alleen H2's wist de generator
wélke onderwerpen de top 3 noemt, maar niet hoe lang ze zijn, welke vragen ze
beantwoorden of met welke titel ze de klik winnen. Zo schreef hij 1400 woorden
tegen concurrenten van 3000, en telde omnivaleur.com zichzelf soms als
concurrent mee (5 van de 36 onderzochte artikelen).

Blogoverzichten van concurrenten (`competitor_blog_topics`) voeden de
onderwerpkeuze in keyword_planner.py: daar staat wat zij schrijven en wij niet.
"""
import json
import logging
import re
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# ccTLD → DuckDuckGo regio-code, voor lokale top-3 resultaten per submap.
REGION_DDG = {
    "nl": "nl-nl",
    "be-nl": "nl-be",
    "be-fr": "fr-be",
    "fr": "fr-fr",
    "de": "de-de",
}

# Resultaten die geen concurrerend artikel zijn: onze eigen site, winkel- en
# videopagina's en sociale media. Die hebben geen kopjes om te overtreffen en
# verdrongen echte artikelen uit de top 3 (Amazon-boeken bij "vintage books").
_SKIP_DOMAINS = (
    "omnivaleur.com", "amazon.", "youtube.com", "facebook.com", "instagram.com",
    "tiktok.com", "pinterest.", "linkedin.com", "x.com", "twitter.com",
)

# Blogoverzichten van echte concurrenten (Daniels lijst "Crosslisting
# Concurrenten", 25-09-2026), gecontroleerd op die datum: deze gaven titels
# terug. Flyp, Zeedrop en Listelf hebben geen /blog (404); fluf.io en
# oneshop.com renderen hun lijst met JavaScript en leveren niets op.
COMPETITOR_BLOGS = [
    "https://crosslist.com/blog/",
    "https://vendoo.co/blog",
    "https://www.listperfectly.com/blog",
    "https://nifty.ai/blog",
    "https://www.sellraze.com/blog",
    "https://www.resylr.com/blog",
    "https://selleraider.com/blog",
    "https://www.zipsale.co.uk/blog",
    "https://www.exportyourstore.com/blog",
    "https://ruit.es/nl/blog",
    "https://www.evriwhere.co.uk/blog",
    "https://closo.co/blogs/news",
    "https://www.vintieplus.com/blog",
]


def _ddg_search(query: str, region: str, max_results: int = 3) -> list[str]:
    """Haalt de top-N organische resultaat-URLs op via DuckDuckGo's HTML-only endpoint."""
    kl = REGION_DDG.get(region, "nl-nl")
    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query, "kl": kl},
        headers={"User-Agent": UA},
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    urls = []
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        # DDG's HTML endpoint wrapt externe links soms in /l/?uddg=<encoded>
        m = re.search(r"uddg=([^&]+)", href)
        real_url = unquote(m.group(1)) if m else href
        host = urlparse(real_url).netloc.lower()
        if not (real_url.startswith("http") and host):
            continue
        if any(d in host for d in _SKIP_DOMAINS) or "duckduckgo.com" in host:
            continue
        if real_url in urls:
            continue
        urls.append(real_url)
        if len(urls) >= max_results:
            break
    return urls


def _faq_questions(soup: BeautifulSoup) -> list[str]:
    """Vragen uit FAQPage-schema plus kopjes die als vraag geschreven zijn."""
    vragen: list[str] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "FAQPage":
                for q in item.get("mainEntity") or []:
                    if isinstance(q, dict) and q.get("name"):
                        vragen.append(str(q["name"]).strip())
    for h in soup.find_all(["h2", "h3", "h4"]):
        t = h.get_text(" ", strip=True)
        if t.endswith("?") and 10 < len(t) < 160:
            vragen.append(t)
    return list(dict.fromkeys(vragen))[:15]


def _schema_types(soup: BeautifulSoup) -> list[str]:
    types: set[str] = set()
    for tag in soup.find_all("script", type="application/ld+json"):
        for t in re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', tag.string or ""):
            types.add(t)
    return sorted(types)


def _extract_page(url: str) -> dict:
    """Leest één concurrent-pagina uit. Faalt zacht (lege velden) bij blokkades."""
    leeg = {"url": url, "title": "", "meta_description": "", "h1": [], "h2": [], "h3": [],
            "word_count": 0, "questions": [], "tables": 0, "images": 0, "schema": []}
    try:
        resp = httpx.get(url, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        meta = soup.find("meta", attrs={"name": "description"})
        questions = _faq_questions(soup)
        schema = _schema_types(soup)
        # Lengte meten op de artikeltekst, niet op menu, voettekst en scripts.
        for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
            t.decompose()
        main = soup.find("article") or soup.find("main") or soup.body or soup
        return {
            "url": url,
            "title": title[:200],
            "meta_description": (meta.get("content", "") if meta else "")[:300],
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")][:1],
            "h2": [h.get_text(strip=True) for h in main.find_all("h2")][:15],
            "h3": [h.get_text(strip=True) for h in main.find_all("h3")][:15],
            "word_count": len(main.get_text(" ", strip=True).split()),
            "questions": questions,
            "tables": len(main.find_all("table")),
            "images": len(main.find_all("img")),
            "schema": schema,
        }
    except Exception as e:
        logger.warning(f"Kon concurrent-pagina niet lezen: {url}: {e}")
        return leeg


def research_competitors(keyword: str, region: str = "nl") -> dict:
    """
    Retourneert een snapshot van de top-3 bruikbare resultaten voor `keyword` —
    direct bruikbaar als input voor de content-generator en opgeslagen in
    content_pages.competitor_research voor audit/re-runs.

    Er worden tot acht resultaten opgehaald; een pagina die niets oplevert
    (geblokkeerd, geen kopjes, nauwelijks tekst) schuift door naar de volgende,
    zodat de generator zo vaak mogelijk echt drie concurrenten ziet.
    """
    try:
        urls = _ddg_search(keyword, region, max_results=8)
    except Exception as e:
        logger.error(f"SERP-lookup mislukt voor '{keyword}' ({region}): {e}")
        urls = []

    competitors = []
    for u in urls:
        page = _extract_page(u)
        if page["h2"] or page["word_count"] >= 300:
            competitors.append(page)
        if len(competitors) >= 3:
            break

    all_h2 = [h.lower() for c in competitors for h in c["h2"]]
    words = [c["word_count"] for c in competitors if c["word_count"]]
    return {
        "keyword": keyword,
        "region": region,
        "competitors": competitors,
        "covered_subtopics": sorted(set(all_h2)),
        "questions": list(dict.fromkeys(q for c in competitors for q in c["questions"]))[:20],
        "max_words": max(words) if words else 0,
    }


def competitor_blog_topics(limit_per_blog: int = 12) -> list[str]:
    """Titels van recente artikelen op de blogs van concurrenten. Faalt zacht:
    een blog die niets teruggeeft, levert gewoon geen titels."""
    titels: list[str] = []
    for url in COMPETITOR_BLOGS:
        try:
            resp = httpx.get(url, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            gevonden = [h.get_text(" ", strip=True) for h in soup.select(
                "h2 a, h3 a, article h2, article h3, a h2, a h3, .post-title, .blog-post-title")]
            gevonden = [t for t in dict.fromkeys(gevonden) if 15 < len(t) < 120]
            titels += [f"{t} ({urlparse(url).netloc})" for t in gevonden[:limit_per_blog]]
        except Exception as e:
            logger.warning(f"Blogoverzicht van concurrent niet gelezen: {url}: {e}")
    return titels
