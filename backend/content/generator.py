"""
Content-generatie voor programmatic SEO/GEO-pagina's — bouwt op het
delimiter-outputformat dat we al gebruiken bij Revaleur/AXONGEAR
(marker-gescheiden tekst i.p.v. JSON, robuuster tegen HTML met quotes in
de body), maar met de GEO/AEO-structuur uit de CrossList EU briefing:
quick-answer blockquote, H2's als vragen, key takeaways, FAQ- en
Article-schema, en verplichte citaten naar echte (niet-hallucinerende) bronnen.
"""
import logging
import re

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
CURRENT_YEAR = 2026

# Site is Engelstalig by default (zie CLAUDE-memory: "Language: English only").
# Uitzondering: content die specifiek over Marktplaats/2dehands gaat EN in een
# nl/be-nl regio wordt gepubliceerd, krijgt automatisch een Nederlandse versie —
# dat is precies waar de doelgroep zit en waar Marktplaats/2dehands zelf Nederlands is.
NL_PLATFORM_TERMS = ("marktplaats", "2dehands")


def _resolve_language(keyword: str, region: str) -> str:
    if region in ("nl", "be-nl") and any(t in keyword.lower() for t in NL_PLATFORM_TERMS):
        return "Dutch"
    return "English"


AI_CLICHES = [
    "in today's fast-paced world", "in the dynamic world of", "crucial", "it is important to remember",
    "moreover", "in conclusion", "to sum up", "seamless", "unlock", "leverage", "delve into",
]

# Alleen echte, HTTP-geverifieerde URLs (gecheckt op 200, geen 404-risico). Claude
# mag ALLEEN uit deze lijst citeren — nooit zelf een bron-URL verzinnen.
AUTHORITY_SOURCES = [
    {"name": "Belastingdienst — DAC7 information for sellers", "url": "https://www.belastingdienst.nl/wps/wcm/connect/nl/ondernemers/content/informatie-voor-verkopers-DAC7", "topic": "DAC7 tax reporting NL"},
    {"name": "European Commission — DAC7 overview", "url": "https://taxation-customs.ec.europa.eu/taxation/tax-transparency-cooperation/administrative-co-operation-and-mutual-assistance/dac7_en", "topic": "DAC7 tax reporting EU"},
    {"name": "Your Europe (EU) — consumer shopping rights", "url": "https://europa.eu/youreurope/citizens/consumers/shopping/index_en.htm", "topic": "EU consumer rights"},
    {"name": "Vinted Help Centre", "url": "https://www.vinted.com/help", "topic": "Vinted policies"},
    {"name": "Vinted Help — Selling", "url": "https://www.vinted.com/help/4-selling", "topic": "Vinted selling rules"},
    {"name": "Marktplaats Help & Info", "url": "https://help.marktplaats.nl/s/", "topic": "Marktplaats policies"},
    {"name": "eBay Help — creating and managing listings", "url": "https://www.ebay.com/help/selling/listings/creating-managing-listings?id=4102", "topic": "eBay listing rules"},
]


def _build_prompt(
    keyword: str,
    region: str,
    pillar: str,
    slug: str,
    research: dict,
    existing_pages: list[dict],
) -> str:
    language = _resolve_language(keyword, region)

    competitors_summary = "\n".join(
        f"- {c['url']}\n  H1: {c['h1']}\n  H2's: {c['h2']}"
        for c in research.get("competitors", [])
    ) or "(no competitor data available — write from platform expertise)"

    internal_links_block = "\n".join(
        f'- "{p["title"]}" → https://crosslisteu.com{p["url_path"]}'
        for p in existing_pages
    ) or "(no other pages published yet)"

    sources_block = "\n".join(f'- {s["name"]} ({s["topic"]}): {s["url"]}' for s in AUTHORITY_SOURCES)

    return f"""You are an experienced European reseller and full-stack SEO/GEO expert writing for CrossList EU, a SaaS that automatically cross-lists items across Marktplaats, 2dehands, Vinted, eBay, Etsy and Shopify. You write like a reseller helping a colleague, not a marketing department.

Write a COMPLETE programmatic SEO article in {language} for the primary keyword: "{keyword}"
Content pillar: {"A (platform-to-platform comparison/combo page)" if pillar == "A" else "B (niche/audience automation page)"}
URL will be: /{region}/{"crosslisten" if pillar == "A" else "reseller-tools"}/{slug}

COMPETITOR RESEARCH (top 3 organic results for this keyword, their heading structure):
{competitors_summary}

Already-covered subtopics across those top 3 (do not just repeat these — find the content gap, i.e. what {CURRENT_YEAR} platform rules, limits, updates or reseller pain points they are missing):
{research.get('covered_subtopics') or '(none found)'}

EXISTING CROSSLIST EU PAGES (weave in 2 contextual internal links where genuinely relevant, using these exact URLs, natural anchor text):
{internal_links_block}

AUTHORITY SOURCES — cite 2-3 of these inline as clickable links where relevant to back up claims (tax rules, platform policies). ONLY use these exact URLs verbatim, never invent or guess a URL yourself:
{sources_block}

HARD STYLE RULES:
- Forbidden AI-cliché phrases (do NOT use, in {language} or English): {', '.join(AI_CLICHES)}, and never repeat the question back in the intro.
- Sentence variation ("burstiness"): deliberately mix short punchy sentences (3-5 words) with longer flowing ones. Never monotone.
- Active, direct voice: "Install the extension", not "It is recommended to install the extension".
- Concrete data: use real numbers, comparison tables in Markdown where useful, bold **key terms**.
- Mention the year {CURRENT_YEAR} naturally at least once (platform rules/limits change yearly).
- Never write a generic intro paragraph before answering the core question — the core answer must be fully delivered within the first 100 words (quick answer + opening line combined).

OUTPUT FORMAT — return EXACTLY this structure, nothing else, no markdown code fences:

TITLE: [meta title, max 60 characters, includes the primary keyword, conversion-focused]
META_DESCRIPTION: [max 155 characters, includes the primary keyword, drives CTR]
H1: [primary long-tail keyword as a full heading, includes {CURRENT_YEAR}]
QUICK_ANSWER: [exactly 40-60 words. Answers the core question directly, factually, with zero preamble. This becomes a <blockquote> right under the H1 — AI search engines (ChatGPT, Perplexity, Google AI Overviews) must be able to lift this verbatim as a citable answer.]
TAKEAWAYS: [3 to 5 short one-line key takeaways, most important facts from the article, each starting with a capital letter, no bullet symbol — just one takeaway per line]
===BODY===
[Full HTML body. Use <h2> headings phrased as complete, grammatically correct questions (integrate the missing subtopics from the content gap analysis). Use <h3> for sub-sections, <p>, <ul>/<ol>, <strong>, <a href="..."> for the internal links AND 2-3 authority-source links listed above, and Markdown-style tables converted to <table> HTML where comparing platforms. Do NOT include an <h1> (already set separately) and do NOT repeat the quick answer. Aim for 1400-1900 words of visible text.]
===FAQ===
[4 to 6 H3-level follow-up questions NOT already covered by the competitors above, each with a short (2-4 sentence) answer. Format each pair EXACTLY as:
Q: [question]
A: [answer]
]
"""


def _parse_output(raw: str) -> dict:
    text = raw.strip()

    def field(name: str) -> str:
        m = re.search(rf"^\s*{name}:\s*(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    takeaways_m = re.search(r"^\s*TAKEAWAYS:\s*(.+?)(?=\n===BODY===)", text, re.MULTILINE | re.DOTALL)
    takeaways = [t.strip("- ").strip() for t in takeaways_m.group(1).strip().split("\n")] if takeaways_m else []
    takeaways = [t for t in takeaways if t]

    body_start = text.find("===BODY===")
    faq_start = text.find("===FAQ===")

    body_html = text[body_start + len("===BODY==="): faq_start].strip() if body_start != -1 else ""
    faq_raw = text[faq_start + len("===FAQ==="):].strip() if faq_start != -1 else ""

    faq = []
    for block in re.split(r"\n(?=Q:)", faq_raw):
        qm = re.search(r"Q:\s*(.+)", block)
        am = re.search(r"A:\s*(.+)", block, re.DOTALL)
        if qm and am:
            faq.append({"question": qm.group(1).strip(), "answer": am.group(1).strip()})

    return {
        "title": field("TITLE"),
        "meta_description": field("META_DESCRIPTION"),
        "h1": field("H1"),
        "quick_answer": field("QUICK_ANSWER"),
        "takeaways": takeaways,
        "body_html": body_html,
        "faq": faq,
    }


def generate_page_content(
    keyword: str,
    region: str,
    pillar: str,
    slug: str,
    research: dict,
    existing_pages: list[dict],
) -> dict | None:
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY ontbreekt — kan geen content genereren")
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(keyword, region, pillar, slug, research, existing_pages)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error(f"Claude API fout voor keyword '{keyword}': {e}")
        return None

    raw = message.content[0].text if message.content else ""
    if not raw:
        logger.error(f"Lege Claude-respons voor keyword '{keyword}'")
        return None

    parsed = _parse_output(raw)
    if not parsed["body_html"] or not parsed["h1"]:
        logger.error(f"Kon body/H1 niet parsen uit Claude-output voor '{keyword}'")
        return None
    return parsed
