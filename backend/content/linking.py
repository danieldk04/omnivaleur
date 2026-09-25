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

    # Al aanwezige interne links meetellen. Zonder deze telling voegt elke
    # herhaalde run (backfill, evaluator-refresh) er opnieuw `min_links` bij,
    # tot een artikel bezaaid is met links naar zichzelf-achtige pagina's.
    # Zowel relatieve (/crosslisting/…) als absolute (https://omnivaleur.com/…)
    # interne links tellen: het model schrijft ze absoluut, deze engine relatief.
    # Alleen op de relatieve vorm tellen liet de teller elke run opnieuw bij nul
    # beginnen, waardoor er telkens vijf links bij kwamen.
    hrefs = re.findall(r'href="(?:https?://(?:www\.)?omnivaleur\.com)?(/[^"#][^"]*)"', body)
    existing = len(set(hrefs))
    budget = max(min_links, 2) - existing

    for cand in candidates:
        if len(linked) >= budget:
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


# ── Links in de taal van de pagina ─────────────────────────────────────────
# Tot 25-09-2026 linkten 93 van de 110 blogs naar een pagina in de andere taal
# (344 links): de generator kreeg EN- en NL-pagina's door elkaar als linkdoel, en
# de NL-vertaling nam de Engelse links ongewijzigd over, soms zelfs naar een
# pad dat niet bestaat (/crosslisting/marktplaats-naar-vinted).
_BLOG_HREF = re.compile(
    r'<a\b([^>]*?)\shref="(?:https?://(?:www\.)?omnivaleur\.com)?'
    r'(/(?:nl/)?(?:crosslisting|crosslisten|vs|vergelijking|reseller-tools)/[^"#?]+)"([^>]*)>(.*?)</a>',
    re.S,
)
_MAP_NAAR_NL = {"crosslisting": "crosslisten", "vs": "vergelijking", "reseller-tools": "reseller-tools"}
_MAP_NAAR_EN = {v: k for k, v in _MAP_NAAR_NL.items()}


def _zelfde_pad_andere_taal(pad: str, language: str) -> str:
    delen = pad.strip("/").split("/")
    if delen[0] == "nl":
        delen = delen[1:]
    map_, slug = delen[0], "/".join(delen[1:])
    if language == "nl":
        return f"/nl/{_MAP_NAAR_NL.get(map_, _MAP_NAAR_NL.get(_MAP_NAAR_EN.get(map_, map_), map_))}/{slug}"
    return f"/{_MAP_NAAR_EN.get(map_, map_)}/{slug}"


def herschrijf_taallinks(body_html: str, language: str, index: dict[str, dict]) -> tuple[str, int, int]:
    """
    Laat elke bloglink wijzen naar de pagina in de taal van dít artikel.
    `index`: {pad: {"lang": "en"|"nl", "tegenhanger": pad-in-andere-taal of None,
    "titel": paginatitel (optioneel)}}
    voor alle gepubliceerde pagina's. Een link naar de andere taal gaat naar de
    tegenhanger; bestaat die niet, dan blijft alleen de linktekst over (een link
    naar een Engels artikel midden in Nederlandse tekst is erger dan geen link).
    Was de linktekst letterlijk de titel van de pagina in de andere taal ("Omnivaleur
    vs OneShop: Eerlijke vergelijking 2026" in een Engels artikel), dan wordt
    hij de titel van de pagina waar de link nu naartoe gaat.
    Retourneert (body, omgezet, weggehaald).
    """
    omgezet = weggehaald = 0

    def _tekst_voor(doel: str, tekst: str) -> str:
        doel_info = index.get(doel) or {}
        ander = index.get(doel_info.get("tegenhanger") or "") or {}
        if ander.get("titel") and doel_info.get("titel") and tekst.strip() == ander["titel"].strip():
            return doel_info["titel"]
        return tekst

    def vervang(m: re.Match) -> str:
        nonlocal omgezet, weggehaald
        voor, pad, na, tekst = m.group(1), m.group(2).rstrip("/"), m.group(3), m.group(4)
        info = index.get(pad)
        if info and info["lang"] == language:
            nieuwe_tekst = _tekst_voor(pad, tekst)
            if nieuwe_tekst == tekst:
                return m.group(0)
            omgezet += 1
            return f'<a{voor} href="{m.group(2)}"{na}>{nieuwe_tekst}</a>'
        doel = info.get("tegenhanger") if info else None
        if not doel:
            gok = _zelfde_pad_andere_taal(pad, language)
            doel = gok if index.get(gok, {}).get("lang") == language else None
        if doel:
            omgezet += 1
            return f'<a{voor} href="{doel}"{na}>{_tekst_voor(doel, tekst)}</a>'
        weggehaald += 1
        return tekst

    return _BLOG_HREF.sub(vervang, body_html), omgezet, weggehaald
