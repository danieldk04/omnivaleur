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


def apply_internal_links(body_html: str, candidates: list[dict], self_intent_key: str, min_links: int = 2) -> tuple[str, list[str]]:
    """
    `candidates`: [{intent_key, title, url_path, link_terms: [str, ...]}, ...] — other
    published pages to link to. Returns (updated_body, list of intent_keys actually linked).
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
        if len(linked) >= max(min_links, 2):
            break

    return body, linked
