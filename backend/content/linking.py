"""
Interne link-engine: linkt de eerste veilige vermelding van gerelateerde
platform/niche-termen tussen content_pages, zodat geen enkele pagina orphan
blijft. Zelfde blocked-ranges-aanpak als het Revaleur relink-algoritme (nooit
binnen bestaande <a>- of <h1-3>-tags linken).
"""
import re


def _escape(term: str) -> str:
    return re.escape(term)


def _blocked_ranges(html: str) -> list[tuple[int, int]]:
    ranges = []
    for m in re.finditer(r"<(?:a\b[^>]*|h[1-3][^>]*)>.*?</(?:a|h[1-3])>", html, re.DOTALL | re.IGNORECASE):
        ranges.append((m.start(), m.end()))
    # Ook alle tag-markup zelf blokkeren (alles tussen < en >), zodat een term die
    # binnen een attribuutwaarde staat — bv. "vinted" in
    # src="/assets/platforms/vinted.jpg" — nooit gelinkt wordt. Zonder dit brak de
    # link-engine <img>/<figure>-tags kapot (anchor midden in de src).
    for m in re.finditer(r"<[^>]+>", html, re.DOTALL):
        ranges.append((m.start(), m.end()))
    return ranges


def _is_blocked(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start >= rs and end <= re_ for rs, re_ in ranges)


def link_first_mention(body_html: str, term: str, url: str) -> str:
    pattern = re.compile(rf"(?<![\w-]){_escape(term)}(?![\w-])", re.IGNORECASE)
    blocked = _blocked_ranges(body_html)
    for m in pattern.finditer(body_html):
        if not _is_blocked(m.start(), m.end(), blocked):
            return body_html[: m.start()] + f'<a href="{url}">{m.group(0)}</a>' + body_html[m.end():]
    return body_html


_INLINE_ANCHOR = re.compile(r"<a\b[^>]*>[^<]*</a>")
_ANCHOR_TEXT = re.compile(r"<a\b[^>]*>([^<]*)</a>")


def _tag_depth_before(html: str, pos: int) -> int:
    """Aantal open '<' minus gesloten '>' vóór pos. >0 betekent: binnen tag-markup."""
    return html.count("<", 0, pos) - html.count(">", 0, pos)


def repair_anchors_in_tags(body_html: str) -> str:
    """
    Repareert HTML waar de link-engine een <a>…</a> midden ín een tag-attribuut
    heeft geïnjecteerd (bv. src="/assets/platforms/<a href=...>vinted</a>.jpg").
    Zulke anchors staan op tag-diepte >0 en worden uitgepakt naar hun linktekst.
    Anchors in gewone body-tekst (diepte 0) blijven ongemoeid.
    """
    result = body_html
    while True:
        for m in _INLINE_ANCHOR.finditer(result):
            if _tag_depth_before(result, m.start()) != 0:
                inner = _ANCHOR_TEXT.match(m.group(0)).group(1)
                result = result[: m.start()] + inner + result[m.end():]
                break
        else:
            return result


def apply_internal_links(body_html: str, candidates: list[dict], self_intent_key: str, min_links: int = 5) -> tuple[str, list[str]]:
    """
    `candidates`: [{intent_key, title, url_path, link_terms: [str, ...]}, ...] — other
    published pages to link to. Returns (updated_body, list of intent_keys actually linked).

    Standaard 5 in plaats van 2: met twee links per artikel bleef het interne
    linkweb zo dun dat pagina's elkaar nauwelijks omhoog trokken. De kandidaten
    komen al gesorteerd op echte Search Console-clicks binnen (zie pipeline.py),
    dus de sterkste pagina's worden als eerste gelinkt.
    """
    body = body_html
    linked: list[str] = []

    for cand in candidates:
        if len(linked) >= max(min_links, 2):
            break
        if cand["intent_key"] == self_intent_key:
            continue
        if f'href="{cand["url_path"]}"' in body:
            continue
        for term in cand.get("link_terms", []):
            new_body = link_first_mention(body, term, cand["url_path"])
            if new_body != body:
                body = new_body
                linked.append(cand["intent_key"])
                break

    return body, linked
