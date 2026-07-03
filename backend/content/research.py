"""
Concurrentieanalyse: scrapet de top-3 organische resultaten voor een keyword
(via DuckDuckGo HTML, geen API-key nodig) en brengt hun heading-structuur
(H1/H2/H3) in kaart, zodat de content-generator een content-gap kan invullen
in plaats van de concurrentie te herhalen.
"""
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
        if real_url.startswith("http") and urlparse(real_url).netloc:
            urls.append(real_url)
        if len(urls) >= max_results:
            break
    return urls


def _extract_headings(url: str) -> dict:
    """Scrapet H1/H2/H3 van een concurrent-pagina. Faalt zacht (lege headings) bij blokkades."""
    try:
        resp = httpx.get(url, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return {
            "url": url,
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")][:1],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")][:12],
            "h3": [h.get_text(strip=True) for h in soup.find_all("h3")][:12],
        }
    except Exception as e:
        logger.warning(f"Kon headings niet ophalen voor {url}: {e}")
        return {"url": url, "h1": [], "h2": [], "h3": []}


def research_competitors(keyword: str, region: str = "nl") -> dict:
    """
    Retourneert een snapshot van de top-3 resultaten voor `keyword`, incl.
    heading-structuur — direct bruikbaar als input voor de content-generator
    en opgeslagen in content_pages.competitor_research voor audit/re-runs.
    """
    try:
        urls = _ddg_search(keyword, region)
    except Exception as e:
        logger.error(f"SERP-lookup mislukt voor '{keyword}' ({region}): {e}")
        urls = []

    competitors = [_extract_headings(u) for u in urls]

    all_h2 = [h.lower() for c in competitors for h in c["h2"]]
    return {
        "keyword": keyword,
        "region": region,
        "competitors": competitors,
        "covered_subtopics": sorted(set(all_h2)),
    }
