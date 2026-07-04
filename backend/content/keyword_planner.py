"""
Autonomous keyword expansion — runs whenever scripts/content_keywords.json
has no pending items left, so the daily publish cron never runs dry. Claude
proposes new platform-combination and niche/audience keywords, grounded in
CrossList EU's actual supported platforms (never invents unsupported ones),
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

MODEL = "claude-opus-4-8"

# The only platforms CrossList EU actually supports — keeps suggestions grounded,
# never invents a "Wallapop" or "Facebook Marketplace" combo we can't back up.
PLATFORMS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify"]
NL_PLATFORM_TERMS = ("marktplaats", "2dehands")

# Real competing cross-listing tools — used only for Pillar C (honest comparison
# pages). Never invent a competitor name that isn't in this list.
COMPETITORS = ["Vendoo", "List Perfectly", "Crosslist", "Zenlister", "OneShop"]


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def _build_prompt(existing_keywords: list[str]) -> str:
    existing_block = "\n".join(f"- {k}" for k in existing_keywords) or "(none yet)"
    return f"""You are a programmatic SEO strategist for CrossList EU, a SaaS that cross-lists items across exactly these platforms: {', '.join(PLATFORMS)}. Never propose a combination involving any other platform.

Propose 5 new content page ideas we have not covered yet. Roughly rotate across all three types below — don't cluster all 5 in one type, and don't skip Pillar C:
- Pillar A (platform combo): "{{platform}} to {{platform}} crosslisting" style, e.g. "vinted to ebay crosslisting" — pick pairs resellers actually care about.
- Pillar B (niche/audience): "{{niche}} selling automation" style, e.g. "sneaker reselling automation", "vintage clothing crosslisting".
- Pillar C (honest competitor comparison): "CrossList EU vs {{competitor}}" style, comparing CrossList EU against one named competitor from this list only: {', '.join(COMPETITORS)}. Never invent a competitor name outside this list.

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
        raw = message.content[0].text if message.content else ""
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
