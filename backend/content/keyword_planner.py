"""
Autonomous keyword expansion — runs whenever scripts/content_keywords.json
has no pending items left, so the daily publish cron never runs dry. Claude
proposes new topic ideas, grounded in Omnivaleur's actual supported platforms
(never invents unsupported ones), and avoids duplicating any keyword/slug
already in the queue.

Variatie wordt sinds 25-09-2026 in code afgedwongen, niet aan het model
overgelaten. De oude prompt kende drie soorten (platformcombinatie, niche,
vergelijking) en gaf "{niche} selling automation" als voorbeeld; vanaf augustus
waren 34 van de 36 artikelen "X reselling automation", waaronder drie keer
boeken en drie keer meubels. Concurrenten (crosslist.com, vendoo, nifty, zipsale,
selleraider) schrijven vooral praktische gidsen: kosten, verzenden, prijzen,
"is X legit", "how to increase sales on Vinted". Daarom:
- `FORMATS` beschrijft zes soorten artikelen; elke aanvulling vraagt een vaste mix;
- de titels van de concurrentenblogs gaan als inspiratie mee in de prompt;
- zoekvragen uit Search Console waarop we half zichtbaar zijn gaan mee;
- `_intent_fingerprint` vangt synoniemen (used/vintage/second hand, meervoud).
"""
import json
import logging
import re
from datetime import date, timedelta

import anthropic

from backend.config import settings
from backend.services.google_ads import meets_volume_threshold
from backend.services.search_console import get_top_pages, query_window

logger = logging.getLogger(__name__)

# Keyword planning is simple structured output — Haiku is plenty and much cheaper.
MODEL = "claude-haiku-4-5-20251001"

# The only platforms Omnivaleur actually supports — keeps suggestions grounded,
# never invents a "Wallapop" or "Facebook Marketplace" combo we can't back up.
PLATFORMS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify"]
NL_PLATFORM_TERMS = ("marktplaats", "2dehands")

# Real competing cross-listing tools — used only for honest comparison pages.
# Uit Daniels lijst "Crosslisting Concurrenten" (25-09-2026) plus de al
# gepubliceerde vergelijkingen. Never invent a competitor name outside this list.
COMPETITORS = [
    "Vendoo", "List Perfectly", "Crosslist", "Flyp", "SellRaze", "Nifty",
    "Resylr", "Zeedrop", "Evriwhere", "Zipsale", "Fluf", "Foxtail",
    "Ruit.es", "Zenlister", "OneShop", "Export Your Store",
]

# Soort artikel → (pijler in de database, beschrijving voor het model).
# De pijler bepaalt alleen de map in de URL; B heet op /blog "Verkopersgidsen".
FORMATS = {
    "howto": ("B", "Practical platform guide a seller searches for, e.g. \"how to sell faster on Vinted\", \"Marktplaats fees explained\", \"how to ship a parcel via 2dehands\", \"best time to post on Vinted\", \"how to photograph clothes for Vinted\". One platform, one concrete task or question."),
    "money_rules": ("B", "Money, law and rules for sellers in the Netherlands and Belgium, e.g. \"DAC7 Vinted reporting\", \"do I pay tax when selling on Marktplaats\", \"when does reselling become a business (KvK)\", \"return rights on second-hand sales\". Factual, EU/NL/BE-specific."),
    "strategy": ("B", "Reseller business strategy not tied to one niche, e.g. \"how to price second-hand items\", \"where to source stock to resell\", \"how to avoid selling the same item twice\", \"relisting vs bumping\", \"how many listings do you need\"."),
    "combo": ("A", "Platform-to-platform crosslisting, e.g. \"vinted to ebay crosslisting\". Only pairs of the supported platforms."),
    "competitor": ("C", "Honest comparison \"Omnivaleur vs {competitor}\" or \"best {competitor} alternative\", against one competitor from the allowed list only."),
    "niche": ("B", "Niche/audience page, e.g. \"sneaker reselling automation\". Use sparingly: many already exist."),
}
_PILLAR_DEFAULT_FORMAT = {"A": "combo", "C": "competitor", "B": "niche"}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


# Woorden die niets aan de zoekintentie toevoegen maar wél een tweede URL
# opleveren voor dezelfde vraag. "omnivaleur-vs-list-perfectly" en
# "omnivaleur-vs-list-perfectly-comparison-2026" gingen zo allebei live en
# vochten om exact dezelfde zoekopdracht.
_FILLER_SLUG_WORDS = {
    "comparison", "compare", "vergelijking", "guide", "gids", "review",
    "crosslisting", "crosslisten", "cross", "listing", "automation", "tool",
    "tools", "platforms", "platform", "best", "beste", "full", "complete",
    "2024", "2025", "2026", "2027",
    # Synoniemen voor "tweedehands": used-book, second-hand-book en vintage-books
    # gingen alle drie live (augustus/september 2026). Idem voor meubels.
    "used", "vintage", "second", "hand", "secondhand", "preowned", "pre", "owned",
    "antique", "retro", "reselling", "resale", "selling", "reseller",
    # Vraagwoorden: "Omnivaleur vs Vendoo: which crosslisting tool is better"
    # werd op 25-09-2026 opnieuw voorgesteld naast het bestaande omnivaleur-vs-vendoo.
    "how", "to", "from", "which", "is", "better", "the", "a", "an", "for", "on",
    "in", "of", "do", "i", "you", "your", "vs", "and", "with", "can", "what",
}


def _stam(woord: str) -> str:
    """Meervoud weg, zodat 'books' en 'book' dezelfde vingerafdruk geven."""
    if len(woord) > 4 and woord.endswith("ies"):
        return woord[:-3] + "y"
    if len(woord) > 4 and woord.endswith("s") and not woord.endswith("ss"):
        return woord[:-1]
    return woord


def _intent_fingerprint(slug: str) -> str:
    """
    De betekenisdragende kern van een slug, als vergelijkingssleutel. Twee slugs
    met dezelfde vingerafdruk beantwoorden dezelfde vraag en mogen niet allebei
    bestaan — welke van de twee formuleringen het model toevallig koos, maakt
    voor de zoeker niets uit.
    """
    words = sorted({_stam(w) for w in slug.split("-") if w and w not in _FILLER_SLUG_WORDS})
    return "-".join(words)


def _is_duplicate_intent(slug: str, existing_slugs: list[str]) -> bool:
    fingerprint = _intent_fingerprint(slug)
    return any(fingerprint == _intent_fingerprint(s) for s in existing_slugs)


def _performance_block() -> str:
    """Real GSC performance data on already-published pages, if configured — biases new
    suggestions toward topics that are actually getting impressions/clicks."""
    top_pages = get_top_pages(days=90, row_limit=10)
    if not top_pages:
        return "(no Search Console data available)"
    return "\n".join(
        f"- {p['url']}: {p['clicks']} clicks, {p['impressions']} impressions, avg position {p['position']:.1f}"
        for p in top_pages
    )


def _query_block() -> str:
    """Zoekvragen waarop Google ons al toont maar niet bovenaan: bewezen vraag
    waar we nog geen goed antwoord op hebben. Dit is het sterkste signaal voor
    een nieuw onderwerp, sterker dan wat al klikken krijgt."""
    eind = date.today() - timedelta(days=3)
    rijen = query_window(["query"], (eind - timedelta(days=90)).isoformat(), eind.isoformat(), row_limit=250)
    kansen = [r for r in rijen if r.get("impressions", 0) >= 5 and r.get("position", 0) > 8]
    kansen.sort(key=lambda r: -r["impressions"])
    if not kansen:
        return "(no Search Console query data available)"
    return "\n".join(
        f"- \"{r['keys'][0]}\": {r['impressions']} impressions, position {r['position']:.1f}"
        for r in kansen[:25]
    )


def _recent_formats(published: list[dict], n: int = 12) -> list[str]:
    return [p.get("format") or _PILLAR_DEFAULT_FORMAT.get(p.get("pillar", "B"), "niche")
            for p in published[-n:]]


def plan_mix(published: list[dict]) -> list[str]:
    """
    De vaste mix voor één aanvulling (zes artikelen = zes dagen), in de volgorde
    waarin ze verschijnen, zodat nooit twee dezelfde soorten na elkaar komen.
    Het zesde plekje wisselt tussen platformcombinatie en niche, naar wat de
    laatste twaalf artikelen het minst hadden; een niche alleen als er in de
    laatste vijf geen zat.
    """
    recent = _recent_formats(published)
    laatste_vijf = recent[-5:]
    zesde = "niche" if (recent.count("niche") < recent.count("combo") and "niche" not in laatste_vijf) else "combo"
    return ["howto", "competitor", "money_rules", "howto", "strategy", zesde]


def _build_prompt(existing_keywords: list[str], mix: list[str], competitor_titles: list[str]) -> str:
    existing_block = "\n".join(f"- {k}" for k in existing_keywords) or "(none yet)"
    formats_block = "\n".join(f"- {f}: {FORMATS[f][1]}" for f in dict.fromkeys(mix))
    mix_block = ", ".join(f"{mix.count(f)}x {f}" for f in dict.fromkeys(mix))
    titles_block = "\n".join(f"- {t}" for t in competitor_titles[:80]) or "(not available)"
    return f"""You are an SEO content strategist for Omnivaleur, a SaaS for second-hand sellers in the Netherlands and Belgium that cross-lists items across exactly these platforms: {', '.join(PLATFORMS)}. Never propose a topic about any other marketplace (no Poshmark, Mercari, Depop, Whatnot, Facebook Marketplace).

Propose exactly {len(mix)} new article ideas with this mix: {mix_block}. The article types:
{formats_block}

Allowed competitors for comparison articles (never invent another): {', '.join(COMPETITORS)}.

WHAT COMPETING CROSSLISTING TOOLS PUBLISH ON THEIR BLOGS (recent titles). These show what resellers search for. Adapt the best ideas to OUR platforms and the Dutch/Belgian market; never copy a title, never pick a US-only platform:
{titles_block}

SEARCH QUERIES WHERE GOOGLE ALREADY SHOWS US BUT NOT AT THE TOP (last 90 days). Proven demand: prefer topics that answer these directly:
{_query_block()}

OUR BEST-PERFORMING PAGES (last 90 days):
{_performance_block()}

ALREADY COVERED (do not repeat these or close variants; "used", "vintage" and "second-hand" versions of the same niche count as the same topic):
{existing_block}

Keywords must be what a real person types into Google: short, natural, in English. For every idea also give the natural Dutch search phrase a Dutch or Belgian seller would type for the same question (every article also gets a Dutch version).

Return ONLY a JSON array, no prose, no markdown fences, in this exact shape:
[
  {{"format": "howto", "keyword": "natural English search phrase", "nl_keyword": "natural Dutch search phrase"}},
  ...
]
"""


def suggest_keywords(
    existing_keywords: list[str],
    existing_slugs: list[str] | None = None,
    published: list[dict] | None = None,
) -> list[dict]:
    from backend.content.research import competitor_blog_topics

    mix = plan_mix(published or [])
    prompt = _build_prompt(existing_keywords, mix, competitor_blog_topics())

    try:
        # Sinds 23-09-2026 eerst Gemini, dan Claude (backend/services/taalmodel.py).
        from backend.services import taalmodel
        raw = taalmodel.vraag(prompt, max_tokens=2000, claude_model=MODEL,
                              tijdslimiet=120.0, wat="trefwoordplanner")
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ideas = json.loads(raw)
    except Exception as e:
        logger.error(f"Keyword-suggestie mislukt: {e}")
        return []

    known_slugs = list(existing_slugs or []) + [_slugify(k) for k in existing_keywords]
    # Het model houdt zich niet altijd aan de mix; per soort nooit meer dan gevraagd.
    ruimte = {f: mix.count(f) for f in mix}

    queue_items = []
    for idea in ideas:
        keyword = idea.get("keyword", "").strip()
        fmt = idea.get("format")
        if not keyword or fmt not in FORMATS:
            continue
        if ruimte.get(fmt, 0) <= 0:
            logger.info(f"Keyword overgeslagen (soort {fmt} is al vol in deze ronde): {keyword}")
            continue
        if not meets_volume_threshold(keyword):
            logger.info(f"Keyword overgeslagen (te weinig zoekvolume): {keyword}")
            continue
        slug = _slugify(keyword)
        if _is_duplicate_intent(slug, known_slugs):
            logger.info(f"Keyword overgeslagen (bestaande pagina beantwoordt dezelfde vraag): {keyword}")
            continue
        known_slugs.append(slug)
        ruimte[fmt] -= 1
        item = {
            "keyword": keyword,
            "region": "nl",
            "pillar": FORMATS[fmt][0],
            "format": fmt,
            "slug": slug,
            "status": "pending",
        }
        if idea.get("nl_keyword"):
            item["nl_slug"] = _slugify(idea["nl_keyword"])
        queue_items.append(item)
    # In de volgorde van de mix, zodat de soorten elkaar dag na dag afwisselen.
    volgorde = {f: i for i, f in enumerate(dict.fromkeys(mix))}
    queue_items.sort(key=lambda it: volgorde.get(it["format"], 99))
    return _afwisselen(queue_items)


def _afwisselen(items: list[dict]) -> list[dict]:
    """Zet de ideeën zo neer dat twee opeenvolgende nooit dezelfde soort zijn,
    als dat kan."""
    uit: list[dict] = []
    rest = list(items)
    while rest:
        keuze = next((i for i in rest if not uit or i["format"] != uit[-1]["format"]), rest[0])
        uit.append(keuze)
        rest.remove(keuze)
    return uit
