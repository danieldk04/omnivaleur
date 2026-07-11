"""
Autonomous keyword expansion — runs whenever scripts/content_keywords.json
has no pending items left, so the daily publish cron never runs dry. Claude
proposes new platform-combination and niche/audience keywords, grounded in
Omnivaleur's actual supported platforms (never invents unsupported ones),
and avoids duplicating any keyword/slug already in the queue.
"""
import json
import logging
import re

import anthropic

from backend.config import settings
from backend.services.google_ads import meets_volume_threshold
from backend.services.search_console import get_top_pages

logger = logging.getLogger(__name__)

# Keyword planning is simple structured output — Haiku is plenty and much cheaper.
MODEL = "claude-haiku-4-5-20251001"

# The only platforms Omnivaleur actually supports — keeps suggestions grounded,
# never invents a "Wallapop" or "Facebook Marketplace" combo we can't back up.
PLATFORMS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify"]
NL_PLATFORM_TERMS = ("marktplaats", "2dehands")

# Real competing cross-listing tools — used only for Pillar C (honest comparison
# pages). Never invent a competitor name that isn't in this list.
COMPETITORS = ["Vendoo", "List Perfectly", "Omnivaleur", "Zenlister", "OneShop"]


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def _performance_block() -> str:
    """Real GSC performance data on already-published pages, if configured — biases new
    suggestions toward pillars/topics that are actually getting impressions/clicks
    instead of guessing cold every cycle."""
    top_pages = get_top_pages(days=90, row_limit=10)
    if not top_pages:
        return "(no Search Console data available yet)"
    return "\n".join(
        f"- {p['url']}: {p['clicks']} clicks, {p['impressions']} impressions, avg position {p['position']:.1f}"
        for p in top_pages
    )


def _build_prompt(existing_keywords: list[str]) -> str:
    existing_block = "\n".join(f"- {k}" for k in existing_keywords) or "(none yet)"
    return f"""You are a programmatic SEO strategist for Omnivaleur, a SaaS that cross-lists items across exactly these platforms: {', '.join(PLATFORMS)}. Never propose a combination involving any other platform.

Propose 5 new content page ideas we have not covered yet. Roughly rotate across all three types below — don't cluster all 5 in one type, and don't skip Pillar C:
- Pillar A (platform combo): "{{platform}} to {{platform}} crosslisting" style, e.g. "vinted to ebay crosslisting" — pick pairs resellers actually care about.
- Pillar B (niche/audience): "{{niche}} selling automation" style, e.g. "sneaker reselling automation", "vintage clothing crosslisting".
- Pillar C (honest competitor comparison): "Omnivaleur vs {{competitor}}" style, comparing Omnivaleur against one named competitor from this list only: {', '.join(COMPETITORS)}. Never invent a competitor name outside this list.

REAL SEARCH CONSOLE PERFORMANCE of already-published pages (last 90 days) — lean toward proposing more ideas similar to whatever is already getting clicks/impressions here, and be more cautious about pillars/topics that show zero traction:
{_performance_block()}

ALREADY COVERED (do not repeat these or close variants):
{existing_block}

For each idea, decide if it should ALSO get a Dutch translation: only if the primary keyword concept centers on Marktplaats or 2dehands specifically (they're Dutch/Belgian-market platforms, so Dutch searchers actively search in Dutch for these). Platform combos involving only Vinted/eBay/Etsy/Shopify, and all Pillar C comparisons, should stay English-only (these are English-language search markets).

Return ONLY a JSON array, no prose, no markdown fences, in this exact shape:
[
  {{"keyword": "natural English search phrase", "pillar": "A", "needs_nl": true, "nl_keyword": "natural Dutch search phrase or null"}},
  ...
]
"""


def suggest_keywords(existing_keywords: list[str]) -> list[dict]:
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY ontbreekt — kan geen keywords voorstellen")
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(existing_keywords)

    try:
        message = client.messages.create(model=MODEL, max_tokens=2000, messages=[{"role": "user", "content": prompt}])
        raw = "".join(getattr(b, "text", "") or "" for b in (message.content or []))
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ideas = json.loads(raw)
    except Exception as e:
        logger.error(f"Keyword-suggestie mislukt: {e}")
        return []

    queue_items = []
    for idea in ideas:
        keyword = idea.get("keyword", "").strip()
        if not keyword:
            continue
        if not meets_volume_threshold(keyword):
            logger.info(f"Keyword overgeslagen (te weinig zoekvolume): {keyword}")
            continue
        slug = _slugify(keyword)
        item = {
            "keyword": keyword,
            "region": "nl",
            "pillar": idea.get("pillar", "A"),
            "slug": slug,
            "status": "pending",
        }
        if idea.get("needs_nl") and idea.get("nl_keyword"):
            item["nl_slug"] = _slugify(idea["nl_keyword"])
        queue_items.append(item)
    return queue_items
