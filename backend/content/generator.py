"""
Content-generatie voor programmatic SEO/GEO-pagina's — bouwt op het
delimiter-outputformat dat we al gebruiken bij Revaleur/AXONGEAR
(marker-gescheiden tekst i.p.v. JSON, robuuster tegen HTML met quotes in
de body), maar met de GEO/AEO-structuur uit de Omnivaleur briefing:
quick-answer blockquote, H2's als vragen, key takeaways, FAQ- en
Article-schema, en verplichte citaten naar echte (niet-hallucinerende) bronnen.
"""
import logging
import re
from pathlib import Path

import anthropic

from backend.config import settings
from backend.content.dashboard_images import figure_html as dashboard_figure_html
from backend.content.dashboard_images import relevant_shots
from backend.content.figures import contains_figures, spread_figures

logger = logging.getLogger(__name__)

# Article generation uses Sonnet (strong SEO quality at ~1/5 the cost of Opus);
# translation is mechanical HTML-preserving work, so Haiku handles it far cheaper.
GEN_MODEL = "claude-sonnet-5"
TRANSLATE_MODEL = "claude-haiku-4-5-20251001"
CURRENT_YEAR = 2026
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def _extract_text(message) -> str:
    """Join all text blocks from a Claude response.

    Newer models (Sonnet 5 / the 5 family) can return a thinking block as the
    first content block, so blindly reading content[0].text yields empty/errors.
    """
    parts = []
    for block in message.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()

# Every article is written in English first (zie CLAUDE-memory: "Language:
# English only"). EVERY article — every pillar, every region — additionally
# gets an auto-translated Dutch companion page, so nothing is EN-only or
# NL-only; readers can switch between the two on the page itself (see
# linking.py / pipeline.py for how the two rows get linked via
# `translation_of`). This used to be limited to Marktplaats/2dehands
# articles in nl/be-nl — broadened after Daniel flagged that comparison
# articles (Pillar C) and others were missing an NL version entirely.
def needs_dutch_translation(keyword: str, region: str) -> bool:
    return True


# Publicly-hosted marketing screenshots competitors show on their own sites —
# hotlinked (never re-hosted) so there's no copyright/storage question, standard
# practice for honest comparison content. Verify these URLs still resolve
# periodically; if one 404s, drop that competitor's image rather than guess a new one.
COMPETITOR_SCREENSHOTS = {
    "vendoo": [
        {
            "src": "https://cdn.prod.website-files.com/5f622c6681d34140afb9d542/6a206d0df658ff951485abb4_CROSSLISTING%20features%20images%403x.webp",
            "alt": "Vendoo crosslisting feature screenshot (via vendoo.co)",
            "caption": "Vendoo's crosslisting screen (source: vendoo.co) — built around eBay, Poshmark, Depop and Mercari. No Marktplaats, no 2dehands, no EU-first marketplace at all.",
        },
        {
            "src": "https://cdn.prod.website-files.com/5f622c6681d34140afb9d542/6a206d326d3a3ec89baf9dba_BULK%20ACTIONS%20DELIST%20features%20images%403x.webp",
            "alt": "Vendoo bulk delist/relist feature screenshot (via vendoo.co)",
            "caption": "Vendoo's bulk delist/relist screen (source: vendoo.co) — comparable in spirit to Omnivaleur's refresh tool, but without a stated per-day cap or an explicit ban-risk disclosure.",
        },
        {
            "src": "https://cdn.prod.website-files.com/5f622c6681d34140afb9d542/6a206e401eaf43f976069aad_SALE%20DETECTION%20feature%20images%403x.webp",
            "alt": "Vendoo sale-detection feature screenshot (via vendoo.co)",
            "caption": "Vendoo's automated sale-detection screen (source: vendoo.co), showing cross-platform delisting once an item sells — priced in USD, like the rest of the app.",
        },
        {
            "src": "https://cdn.prod.website-files.com/5f622c6681d34140afb9d542/6a206e5481306dd5c79fcf91_ANALYTICS%20features%20images%403x.webp",
            "alt": "Vendoo analytics feature screenshot (via vendoo.co)",
            "caption": "Vendoo's analytics screen (source: vendoo.co) — tracks the same kind of revenue/profit split Omnivaleur shows, but without EU marketplaces in the platform mix.",
        },
    ],
}


def _competitor_key_in(keyword: str) -> str | None:
    for key in COMPETITOR_SCREENSHOTS:
        if key in keyword.lower():
            return key
    return None


def _competitor_figure_html(img: dict) -> str:
    return (
        f'<figure class="competitor-shot" style="margin:24px 0"><img src="{img["src"]}" alt="{img["alt"]}" '
        f'loading="lazy" decoding="async" style="width:100%;height:auto;border-radius:10px;border:1px solid #e2e8f0">'
        f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px;text-align:center">{img["caption"]}</figcaption></figure>'
    )


def inject_article_screenshots(
    body_html: str,
    pillar: str,
    keyword: str,
    title: str,
    slug: str,
    language: str = "en",
) -> str:
    """
    Zet echte app-screenshots in het artikel: die van Omnivaleur zelf (relevant
    voor het onderwerp, per slug geroteerd — zie dashboard_images.py) en, alleen
    op vergelijkingspagina's, de eigen publieke marketing-screenshots van de
    genoemde concurrent ertussen.

    Dit verving een oudere versie die ALLEEN op Pillar C draaide en daar altijd
    dezelfde vijf beelden in dezelfde volgorde neerzette. Nu krijgt elk artikel
    beeld, en krijgt geen twee artikelen dezelfde reeks.
    """
    if contains_figures(body_html, "/assets/dashboard/"):
        return body_html  # al voorzien — idempotent voor backfills

    our_figures = [
        dashboard_figure_html(shot, language)
        for shot in relevant_shots(keyword, title, slug, body_html)
    ]

    competitor_figures: list[str] = []
    if pillar == "C":
        competitor_key = _competitor_key_in(keyword)
        competitor_figures = [
            _competitor_figure_html(img)
            for img in (COMPETITOR_SCREENSHOTS.get(competitor_key, []) if competitor_key else [])
        ]

    # Om en om "onze UI" / "hun UI": op een vergelijkingspagina is dat precies de
    # vergelijking die de lezer wil zien.
    figures: list[str] = []
    for i in range(max(len(our_figures), len(competitor_figures))):
        if i < len(our_figures):
            figures.append(our_figures[i])
        if i < len(competitor_figures):
            figures.append(competitor_figures[i])

    return spread_figures(body_html, figures)


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


# Pillar D specifically — official Terms of Service / Acceptable Use / API policy
# pages for every platform Omnivaleur touches, plus general data-protection
# authorities. These back the "how it works / trust & safety / compliance" pillar,
# so claims about what a platform does or doesn't allow are always sourced to the
# platform's own legal text, never paraphrased from memory.
PLATFORM_TOS_SOURCES = [
    {"name": "Vinted Terms & Conditions", "url": "https://www.vinted.com/terms-of-service", "topic": "Vinted ToS"},
    {"name": "Vinted Help — Selling", "url": "https://www.vinted.com/help/4-selling", "topic": "Vinted selling rules"},
    {"name": "eBay User Agreement", "url": "https://www.ebay.com/help/policies/member-behaviour-policies/user-agreement?id=4259", "topic": "eBay ToS"},
    {"name": "eBay Help — creating and managing listings", "url": "https://www.ebay.com/help/selling/listings/creating-managing-listings?id=4102", "topic": "eBay listing rules"},
    {"name": "Shopify Terms of Service", "url": "https://www.shopify.com/legal/terms", "topic": "Shopify ToS"},
    {"name": "Shopify Acceptable Use Policy", "url": "https://www.shopify.com/legal/aup", "topic": "Shopify acceptable use"},
    {"name": "Shopify API License and Terms of Use", "url": "https://www.shopify.com/legal/api-terms", "topic": "Shopify API terms"},
    {"name": "Marktplaats Algemene Voorwaarden", "url": "https://www.marktplaats.nl/paginas/algemenevoorwaarden.html", "topic": "Marktplaats ToS"},
    {"name": "Marktplaats Help & Info", "url": "https://help.marktplaats.nl/s/", "topic": "Marktplaats policies"},
    {"name": "2dehands Help & Info", "url": "https://help.2dehands.be/s/", "topic": "2dehands policies"},
    {"name": "Etsy Seller Policy", "url": "https://www.etsy.com/legal/sellers/", "topic": "Etsy seller policy"},
    {"name": "European Commission — GDPR overview", "url": "https://commission.europa.eu/law/law-topic/data-protection/data-protection-eu_en", "topic": "GDPR / data protection"},
]


def _refresh_block(refresh_context: dict | None) -> str:
    """
    Briefing voor een HERSCHRIJVING van een bestaande, ondermaats presterende
    pagina (zie backend/content/evaluator.py). Leeg bij een gewone eerste
    publicatie. De 'missed queries' zijn het sterkste signaal in het hele proces:
    het is letterlijk waarop mensen zoeken als ze deze pagina te zien krijgen
    zonder erop te klikken of zonder hem hoog te zien staan.
    """
    if not refresh_context:
        return ""

    queries = refresh_context.get("missed_queries") or []
    queries_block = "\n".join(
        f"- \"{q['query']}\" — {q['impressions']} impressions, {q['clicks']} clicks, avg position {q['position']:.1f}"
        for q in queries
    ) or "(no per-query data available)"

    ctr_note = ""
    if refresh_context.get("verdict") == "low_ctr":
        ctr_note = (
            "\nThis page ALREADY RANKS WELL — the problem is that nobody clicks it. Treat the TITLE and "
            "META_DESCRIPTION as the main deliverable: make them concretely more compelling and specific "
            f"(the current title is \"{refresh_context.get('current_title', '')}\", which is evidently not "
            "earning clicks). Keep the body's factual substance, but sharpen it too."
        )

    return f"""
THIS IS A REWRITE OF AN EXISTING PAGE THAT IS UNDERPERFORMING IN GOOGLE.
Current performance: average position {refresh_context.get('position', 0):.1f}, {refresh_context.get('impressions', 0)} impressions, CTR {refresh_context.get('ctr', 0):.1%}.
Diagnosis: {refresh_context.get('reason', '')}{ctr_note}

REAL SEARCH QUERIES this page is already shown for but does NOT satisfy well enough — these are your highest-value targets. Answer each of these directly and explicitly somewhere in the article (as an <h2> question, an FAQ entry, or a clearly-labelled section), using the searcher's own phrasing:
{queries_block}

Write a genuinely BETTER article than whatever is currently there — deeper, more specific, more current. Do not merely reword it.
"""


def _build_prompt(
    keyword: str,
    region: str,
    pillar: str,
    slug: str,
    research: dict,
    existing_pages: list[dict],
    refresh_context: dict | None = None,
) -> str:
    language = "English"

    competitors_summary = "\n".join(
        f"- {c['url']}\n  H1: {c['h1']}\n  H2's: {c['h2']}"
        for c in research.get("competitors", [])
    ) or "(no competitor data available — write from platform expertise)"

    internal_links_block = "\n".join(
        f'- "{p["title"]}" → https://omnivaleur.com{p["url_path"]}'
        for p in existing_pages
    ) or "(no other pages published yet)"

    sources_block = "\n".join(f'- {s["name"]} ({s["topic"]}): {s["url"]}' for s in AUTHORITY_SOURCES)

    return f"""You are an experienced European reseller and full-stack SEO/GEO expert writing for Omnivaleur, a SaaS that automatically cross-lists items across Marktplaats, 2dehands, Vinted, eBay, Etsy and Shopify. You write like a reseller helping a colleague, not a marketing department.

CRITICAL LANGUAGE RULE: the target keyword and competitor research below may be phrased in Dutch (that is simply what people search for). You must nonetheless write the ENTIRE article — title, meta description, H1, quick answer, body, FAQ, everything — in {language}. Translate the concept and intent of the Dutch keyword into a natural {language} article. Do NOT copy or echo any Dutch phrasing anywhere in your output, including the H1. If you catch yourself writing a Dutch word, stop and translate it.

CRITICAL BRAND RULE: "Omnivaleur" is a brand/product name ONLY — it is a noun, never a verb. NEVER use it as an action. The action of listing an item on multiple marketplaces is "cross-list" / "cross-listing" (the Dutch keyword "crosslisten" translates to the verb "cross-list", NOT to "Omnivaleur"). Wrong: "How to Omnivaleur from Marktplaats to Vinted". Right: "How to cross-list from Marktplaats to Vinted". Use the brand name "Omnivaleur" only to refer to the product itself (e.g. "with Omnivaleur you can…").

Write a COMPLETE programmatic SEO article in {language} for the concept behind this search keyword: "{keyword}"
Content pillar: {"A (platform-to-platform comparison/combo page)" if pillar == "A" else "C (honest Omnivaleur vs. named competitor comparison)" if pillar == "C" else "B (niche/audience automation page)"}
URL will be: /{region}/{"crosslisten" if pillar == "A" else "vergelijking" if pillar == "C" else "reseller-tools"}/{slug}
{"""
PILLAR C SPECIAL RULES (competitor comparison page): Be scrupulously honest and fair — this is a comparison, not an ad. Include a real Markdown comparison table (pricing, supported platforms, sync behavior, ease of use). Acknowledge at least one genuine strength of the competitor. Never fabricate a competitor feature, price or limitation you don't actually know — if unsure, describe it in general/neutral terms instead of inventing specifics. End with an honest verdict on who each tool is actually best for, not a blanket "Omnivaleur wins". Structure the body as AT LEAST 7 distinct <h2> sections (not counting the comparison table's own heading) so screenshots can be spread naturally through the article — e.g. platforms supported, pricing, ease of use/setup, sync & relist behavior, EU-specific handling (Marktplaats/2dehands/Vinted/euro pricing), support/reliability, and the final verdict. Aim for 2200-2800 words of visible text for this pillar specifically (longer than other pillars) — there is a real screenshot of Omnivaleur's own dashboard being inserted into this article, and the text needs enough depth to carry it.""" if pillar == "C" else ""}

{_refresh_block(refresh_context)}
COMPETITOR RESEARCH (top 3 organic results for this keyword, their heading structure):
{competitors_summary}

Already-covered subtopics across those top 3 (do not just repeat these — find the content gap, i.e. what {CURRENT_YEAR} platform rules, limits, updates or reseller pain points they are missing):
{research.get('covered_subtopics') or '(none found)'}

EXISTING Omnivaleur PAGES (weave in 2 contextual internal links where genuinely relevant, using these exact URLs, natural anchor text):
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
- Reminder: every single field below (including TITLE and H1) must be written in {language}, never Dutch, even though the keyword you were given is Dutch.

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


# Markdown die het model in de HTML-body laat staan. De prompt vraagt om HTML én
# om "bold **key terms**" — die twee vechten met elkaar, en op de live pagina
# stonden daardoor letterlijke sterretjes in de lopende tekst
# ("Vinted made its name on **zero seller fees**"). Dit ruimt het op na afloop
# i.p.v. te hopen dat het model het niet doet.
_MD_BOLD = re.compile(r"\*\*(?!\s)([^*\n]{1,200}?)(?<!\s)\*\*")
_MD_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]{1,200}?)(?<!\s)\*(?![\w*])")
_TAG_SPAN = re.compile(r"<[^>]+>")


def _outside_tags(html: str, transform) -> str:
    """Past `transform` alleen toe op tekst BUITEN tag-markup. Zonder deze splitsing
    zou een sterretje in een attribuutwaarde de tag kunnen breken."""
    parts = []
    cursor = 0
    for m in _TAG_SPAN.finditer(html):
        parts.append(transform(html[cursor:m.start()]))
        parts.append(m.group(0))
        cursor = m.end()
    parts.append(transform(html[cursor:]))
    return "".join(parts)


def strip_markdown_leftovers(html: str) -> str:
    """Zet achtergebleven markdown-nadruk om naar echte HTML-tags."""
    if not html or "*" not in html:
        return html

    def convert(text: str) -> str:
        text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
        return _MD_ITALIC.sub(r"<em>\1</em>", text)

    return _outside_tags(html, convert)


# "Omnivaleur" is een merknaam, nooit een werkwoord. De prompt zegt dat expliciet,
# maar op de live site stond alsnog een meta-description die begon met
# "Omnivaleur from Vinted to eBay in 2026…" — kromme zin, direct zichtbaar in
# Google, en dat kost kliks. Dit is de vangnet-controle achteraf: het model mag
# het fout doen, de pagina niet.
_BRAND_AS_VERB = re.compile(
    r"\bOmnivaleur\b(?=\s+(?:from|to|your|their|our|it|items?|listings?|stock|inventory|between|across|everything|anything)\b)",
    re.IGNORECASE,
)


def fix_brand_as_verb(text: str) -> str:
    """Vervangt de merknaam waar hij als werkwoord gebruikt wordt door 'Cross-list'.
    Behoudt hoofdletter aan het begin van een zin."""
    if not text or "omnivaleur" not in text.lower():
        return text

    def replace(m: re.Match) -> str:
        start = m.start()
        at_sentence_start = start == 0 or text[:start].rstrip().endswith((".", "!", "?", ":"))
        return "Cross-list" if at_sentence_start else "cross-list"

    return _BRAND_AS_VERB.sub(replace, text)


def clean_generated(parsed: dict) -> dict:
    """Alle naverwerking die op elk gegenereerd én elk vertaald artikel moet
    draaien, op één plek zodat de twee paden niet uit elkaar lopen."""
    for field in ("title", "meta_description", "h1", "quick_answer"):
        parsed[field] = fix_brand_as_verb(strip_markdown_leftovers(parsed.get(field, "")))
    parsed["takeaways"] = [
        fix_brand_as_verb(strip_markdown_leftovers(t)) for t in (parsed.get("takeaways") or [])
    ]
    parsed["body_html"] = fix_brand_as_verb(strip_markdown_leftovers(parsed.get("body_html", "")))
    for item in parsed.get("faq") or []:
        item["question"] = fix_brand_as_verb(strip_markdown_leftovers(item.get("question", "")))
        item["answer"] = fix_brand_as_verb(strip_markdown_leftovers(item.get("answer", "")))
    return parsed


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
    refresh_context: dict | None = None,
) -> dict | None:
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY ontbreekt — kan geen content genereren")
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(keyword, region, pillar, slug, research, existing_pages, refresh_context)

    try:
        message = client.messages.create(
            model=GEN_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error(f"Claude API fout voor keyword '{keyword}': {e}")
        return None

    raw = _extract_text(message)
    if not raw:
        logger.error(f"Lege Claude-respons voor keyword '{keyword}'")
        return None

    parsed = _parse_output(raw)
    if not parsed["body_html"] or not parsed["h1"]:
        logger.error(f"Kon body/H1 niet parsen uit Claude-output voor '{keyword}'")
        return None
    return parsed


def _build_translation_prompt(generated: dict) -> str:
    takeaways_block = "\n".join(generated["takeaways"])
    faq_block = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in generated["faq"])

    return f"""Translate the following English article into natural, fluent Dutch (Netherlands) for Omnivaleur, a cross-listing SaaS. Keep the exact same meaning, tone (helpful reseller talking to a colleague) and HTML structure — do not add or remove headings, links or paragraphs, just translate the text inside them. Keep all <a href="..."> URLs and platform/brand names (Marktplaats, Vinted, eBay, etc.) unchanged. Keep numbers, prices and the year 2026 unchanged. Translate the verb "cross-list"/"cross-listing" to the Dutch verb "crosslisten"/"crosslisting" — NEVER to the brand name "Omnivaleur" ("Omnivaleur" is a product name, never a verb).

OUTPUT FORMAT — return EXACTLY this structure, nothing else, no markdown code fences:

TITLE: [Dutch translation, max 60 characters]
META_DESCRIPTION: [Dutch translation, max 155 characters]
H1: [Dutch translation]
QUICK_ANSWER: [Dutch translation, 40-60 words]
TAKEAWAYS: [Dutch translation, one per line, same count as source]
===BODY===
[Dutch translation of the full HTML body, same tags and links, translated text only]
===FAQ===
[Dutch translation, same Q:/A: format, same number of pairs]

SOURCE TITLE: {generated['title']}
SOURCE META_DESCRIPTION: {generated['meta_description']}
SOURCE H1: {generated['h1']}
SOURCE QUICK_ANSWER: {generated['quick_answer']}
SOURCE TAKEAWAYS:
{takeaways_block}
SOURCE BODY:
{generated['body_html']}
SOURCE FAQ:
{faq_block}
"""


def translate_to_dutch(generated: dict) -> dict | None:
    """Translates an already-generated English article into Dutch, preserving HTML structure and links."""
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY ontbreekt — kan niet vertalen")
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_translation_prompt(generated)

    try:
        message = client.messages.create(
            model=TRANSLATE_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error(f"Claude vertaal-fout: {e}")
        return None

    raw = _extract_text(message)
    if not raw:
        logger.error("Lege Claude-vertaalrespons")
        return None

    parsed = _parse_output(raw)
    if not parsed["body_html"] or not parsed["h1"]:
        logger.error("Kon vertaalde body/H1 niet parsen")
        return None
    return parsed
