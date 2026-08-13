"""
Genereert hyperrelevante infographics voor content_pages — als inline SVG,
deterministisch afgeleid uit de inhoud van het artikel zelf.

Waarom geen AI-image-model: infographics bestaan uit TEKST (platformnamen,
getallen, labels), en beeldmodellen renderen tekst onbetrouwbaar tot
onleesbaar. Een SVG die uit de eigen tabellen en stappenlijsten van het artikel
wordt opgebouwd is scherp op elk scherm, kost niets, kan nooit een cijfer
verzinnen dat niet in de tekst staat, en de labels blijven echte <text> — dus
leesbaar voor Google en voor screenreaders, in tegenstelling tot een PNG.

Drie vormen, elk alleen ingezet als de data er daadwerkelijk om vraagt:
  1. bereik-balken  — tabelkolom met getallen/bereiken ("18–30 dagen")
  2. ja/nee-matrix  — tabelkolom met Ja/Nee/Deels-achtige waarden
  3. stappenflow    — genummerde lijst van 3-6 korte stappen

De brontabel/-lijst blijft ALTIJD staan; de infographic komt eruit boven. Dat is
bewust: de tabel is de toegankelijke, exacte weergave van dezelfde data (en de
vorm waarin AI-zoekmachines hem het makkelijkst citeren), de infographic is de
snelle visuele samenvatting. Nooit vervangen, alleen aanvullen.
"""
from __future__ import annotations

import html
import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Maximaal aantal infographics per artikel — meer wordt behang en duwt de tekst
# uit beeld.
MAX_PER_PAGE = 2

# Merkblauw uit frontend/templates/_chrome_style.html, gevalideerd op contrast
# tegen de witte artikelachtergrond.
#
# Bewust ÉÉN kleur voor alle balken/bolletjes, geen regenboog per rij: de rijen
# zijn categorieën op de as (platformen, stappen), geen aparte datareeksen. Elke
# rij een eigen kleur geven suggereert een betekenisverschil dat er niet is —
# de kleur zou dan de volgorde coderen in plaats van de data. De merk-mint
# (#34d399) is hier sowieso onbruikbaar: 1.87:1 contrast tegen wit.
MEASURE = "#2563eb"
INK = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"
TRACK = "#f1f5f9"
GOOD = "#059669"
BAD = "#b91c1c"
PARTIAL = "#b45309"

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"

# Ja/nee-herkenning in NL, EN en FR — de drie talen waarin content_pages draait.
YES_WORDS = {"ja", "yes", "oui", "wel", "volledig", "full", "supported"}
NO_WORDS = {"nee", "no", "non", "niet", "geen", "none", "unsupported"}
PARTIAL_WORDS = {"deels", "partly", "partial", "beperkt", "limited", "soms", "sometimes", "gedeeltelijk"}

CAPTIONS = {
    # Bewust ZONDER "per platform": het label is de kolomkop uit de tabel, en die
    # is lang niet altijd een meeteenheid. Op een fee-vergelijking heet de kolom
    # gewoon "eBay (2026)", en dan kwam er "Visual summary — eBay (2026) per
    # platform" te staan. Onzin. De neutrale formulering klopt in beide gevallen.
    "range": {
        "en": "Visual summary of the table below: {label}.",
        "nl": "Visuele samenvatting van de tabel hieronder: {label}.",
    },
    "matrix": {
        "en": "Visual summary of the table below: {label}.",
        "nl": "Visuele samenvatting van de tabel hieronder: {label}.",
    },
    "steps": {
        "en": "The steps below at a glance.",
        "nl": "De stappen hieronder in één oogopslag.",
    },
}


def _txt(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# SVG breekt tekst niet zelf af. Vroeger knipten we daarom af op een vast aantal
# tekens, met "…" tot gevolg — 108 regels over 33 pagina's eindigden halverwege een
# woord. Nu breken we netjes af over meerdere regels, en tekenen we een infographic
# liever niet dan hem verminkt te tonen.
def _wrap(text: str, limit: int, max_regels: int) -> list[str] | None:
    """De tekst over hooguit `max_regels` regels verdelen. None = past niet."""
    regels, huidig = [], ""
    for woord in (text or "").split():
        kandidaat = f"{huidig} {woord}".strip()
        if len(kandidaat) <= limit or not huidig:
            huidig = kandidaat
        else:
            regels.append(huidig)
            huidig = woord
            if len(regels) >= max_regels:
                return None
    if huidig:
        regels.append(huidig)
    return regels if regels and len(regels) <= max_regels else None


def _regels(x: int, y: int, regels: list[str], size: int, fill: str,
            gewicht: str = "", regelhoogte: int = 17, anchor: str = "") -> str:
    """Meerdere regels binnen één <text>, met tspans die telkens op dezelfde x
    beginnen. Zo blijft de tekst selecteerbaar en leesbaar voor schermlezers."""
    extra = f' font-weight="{gewicht}"' if gewicht else ""
    extra += f' text-anchor="{anchor}"' if anchor else ""
    inhoud = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else regelhoogte}">{_esc(r)}</tspan>'
        for i, r in enumerate(regels))
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}"{extra}>{inhoud}</text>"'.rstrip('"')


def _caption_label(header: str) -> str:
    """
    Koptekst als bijschrift-fragment. Bewust NIET lowercase: kopteksten bevatten
    merknamen ("Past op Vinted in 2026?") en die mag je niet naar "vinted"
    verminken. Alleen afsluitende leestekens gaan eraf, zodat er geen "…in 2026?."
    ontstaat.
    """
    return header.rstrip(" ?:.!")


def _parse_table(table) -> tuple[list[str], list[list[str]]]:
    """Kopteksten + rijen als platte tekst. Lege of vormloze tabellen → ([], [])."""
    rows = table.find_all("tr")
    if len(rows) < 3:
        return [], []

    header_cells = rows[0].find_all(["th", "td"])
    headers = [_txt(c) for c in header_cells]
    body = []
    for tr in rows[1:]:
        cells = [_txt(c) for c in tr.find_all(["th", "td"])]
        if len(cells) == len(headers) and any(cells):
            body.append(cells)
    return (headers, body) if len(body) >= 3 else ([], [])


def _parse_range(cell: str) -> tuple[float, float] | None:
    """
    '18–30' → (18, 30), '7 dagen' → (7, 7), '€12,50' → (12.5, 12.5).
    Geeft None terug zodra de cel geen bruikbaar getal bevat — dan is de kolom
    simpelweg niet numeriek en wordt hij overgeslagen.
    """
    numbers = re.findall(r"\d+(?:[.,]\d+)?", cell)
    if not numbers:
        return None
    values = [float(n.replace(",", ".")) for n in numbers[:2]]
    return (values[0], values[-1]) if values[0] <= values[-1] else (values[-1], values[0])


def _classify_cell(cell: str) -> str | None:
    """Ja/nee/deels-classificatie van een tabelcel; None als het geen van drie is."""
    low = cell.lower()
    first = re.split(r"[\s,;(—–-]", low.strip(), maxsplit=1)[0]
    if first in PARTIAL_WORDS or any(w in low for w in PARTIAL_WORDS):
        return "partial"
    if first in YES_WORDS:
        return "yes"
    if first in NO_WORDS:
        return "no"
    return None


def _svg_open(width: int, height: int, title: str, desc: str) -> str:
    return (
        # Geen width/height-ATTRIBUTEN: 'height="auto"' is geen geldige SVG-lengte,
        # waardoor de browser terugvalt op 100% hoogte en er een enorm leeg vak
        # boven de tekening ontstaat. Via CSS respecteert de browser wél de
        # verhouding uit de viewBox.
        f'<svg viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{_esc(title)}" '
        f'style="width:100%;height:auto;max-width:{width}px;font-family:{FONT}">'
        f"<title>{_esc(title)}</title><desc>{_esc(desc)}</desc>"
    )


def _figure(svg: str, caption: str) -> str:
    return (
        '<figure class="infographic" style="margin:32px 0;">'
        f"{svg}"
        f'<figcaption style="font-size:14px;color:{MUTED};margin-top:8px;">{_esc(caption)}</figcaption>'
        "</figure>"
    )


def _range_infographic(headers: list[str], body: list[list[str]], language: str) -> str | None:
    """
    Zoekt de eerste kolom (niet de eerste, want dat is het label) waarin minstens
    3 rijen een getal of bereik bevatten, en tekent daar horizontale balken van.
    """
    for col in range(1, len(headers)):
        parsed = [(row[0], _parse_range(row[col])) for row in body]
        usable = [(label, rng) for label, rng in parsed if rng]
        if len(usable) < 3:
            continue

        max_value = max(rng[1] for _, rng in usable)
        if max_value <= 0:
            continue

        kop = _wrap(headers[col], 46, 2)
        labels = [_wrap(label, 26, 3) for label, _ in usable]
        if kop is None or any(l is None for l in labels):
            continue                      # past niet: dan liever de volgende kolom
        metric = " ".join(kop)

        bar_x, bar_w = 210, 340
        row_h = 40 + 18 * (max(len(l) for l in labels) - 1)
        top = 36 + 18 * len(kop)
        width, height = 620, top + row_h * len(usable) + 16

        parts = [
            _svg_open(
                width,
                height,
                metric,
                "; ".join(
                    f"{label}: {rng[0]:g}" + (f"–{rng[1]:g}" if rng[0] != rng[1] else "")
                    for label, rng in usable
                ),
            ),
            _regels(0, 20, kop, 15, INK, gewicht="700"),
        ]
        for i, (label, (low, high)) in enumerate(usable):
            y = top + i * row_h
            x0 = bar_x + (low / max_value) * bar_w
            # Minimale zichtbare breedte: een exact getal (low == high) zou anders
            # een balk van 0px opleveren.
            w = max((high - low) / max_value * bar_w, 6)
            value_label = f"{low:g}–{high:g}" if low != high else f"{low:g}"
            parts.append(
                _regels(0, y + 15, labels[i], 14, INK)
                + f'<rect x="{bar_x}" y="{y + 4}" width="{bar_w}" height="14" rx="7" fill="{TRACK}"/>'
                f'<rect x="{x0:.1f}" y="{y + 4}" width="{w:.1f}" height="14" rx="4" fill="{MEASURE}"/>'
                f'<text x="{min(x0 + w + 8, width - 4):.1f}" y="{y + 15}" font-size="13" fill="{MUTED}">{_esc(value_label)}</text>'
            )
        parts.append("</svg>")
        caption = CAPTIONS["range"].get(language, CAPTIONS["range"]["en"]).format(label=_caption_label(metric))
        return _figure("".join(parts), caption)
    return None


def _matrix_infographic(headers: list[str], body: list[list[str]], language: str) -> str | None:
    """Kolom met Ja/Nee/Deels → vinkjes-matrix met expliciet woordlabel ernaast."""
    for col in range(1, len(headers)):
        parsed = [(row[0], _classify_cell(row[col]), row[col]) for row in body]
        usable = [p for p in parsed if p[1]]
        if len(usable) < 3 or len({p[1] for p in usable}) < 2:
            continue

        kop = _wrap(headers[col], 60, 2)
        labels = [_wrap(label, 44, 3) for label, _, _ in usable]
        waarden = [_wrap(raw, 30, 2) for _, _, raw in usable]
        if kop is None or any(l is None for l in labels) or any(w is None for w in waarden):
            continue
        metric = " ".join(kop)

        row_h = 34 + 18 * (max(len(l) for l in labels) - 1)
        top = 36 + 18 * len(kop)
        width, height = 620, top + row_h * len(usable) + 12

        parts = [
            _svg_open(width, height, metric, "; ".join(f"{label}: {raw}" for label, _, raw in usable)),
            _regels(0, 20, kop, 15, INK, gewicht="700"),
        ]
        marks = {
            "yes": (GOOD, "M0 5 L4 9 L11 0"),
            "no": (BAD, "M0 0 L10 10 M10 0 L0 10"),
            "partial": (PARTIAL, "M0 5 L11 5"),
        }
        for i, (label, verdict, raw) in enumerate(usable):
            y = top + i * row_h
            color, path = marks[verdict]
            parts.append(
                f'<line x1="0" y1="{y - 6}" x2="{width}" y2="{y - 6}" stroke="{BORDER}" stroke-width="1"/>'
                + _regels(0, y + 14, labels[i], 14, INK)
                + f'<g transform="translate(400,{y + 4})" stroke="{color}" stroke-width="2.5" fill="none" '
                f'stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></g>'
                # Het woord staat er altijd bij: kleur en vinkje mogen nooit de enige
                # drager van de betekenis zijn (kleurenblindheid, printen).
                + _regels(428, y + 14, waarden[i], 13, color, gewicht="600")
            )
        parts.append("</svg>")
        caption = CAPTIONS["matrix"].get(language, CAPTIONS["matrix"]["en"]).format(label=_caption_label(metric))
        return _figure("".join(parts), caption)
    return None


def _steps_infographic(items: list[str], language: str) -> str | None:
    """Genummerde stappenflow. Alleen bij 3-6 stappen die kort genoeg zijn om te tonen."""
    if not 3 <= len(items) <= 6:
        return None
    zinnen = [re.split(r"(?<=[.!?])\s", s)[0] for s in items]
    if any(len(z) < 4 for z in zinnen):
        return None
    # Drie regels is het maximum: daarboven is het geen stappenflow meer maar een
    # lap tekst met een bolletje ervoor, en dan kun je beter de lijst zelf tonen.
    gewikkeld = [_wrap(z, 62, 3) for z in zinnen]
    if any(g is None for g in gewikkeld):
        return None

    regel_max = max(len(g) for g in gewikkeld)
    row_h, top = 40 + 18 * regel_max, 16
    steps = [" ".join(g) for g in gewikkeld]
    width, height = 620, top + row_h * len(steps)
    parts = [
        _svg_open(width, height, "Stappenoverzicht" if language == "nl" else "Step overview", " → ".join(steps)),
    ]
    for i, step in enumerate(steps):
        y = top + i * row_h
        # Verbindingslijn naar de volgende stap — maakt er een flow van in plaats
        # van een losse lijst met bolletjes.
        if i < len(steps) - 1:
            parts.append(f'<line x1="18" y1="{y + 36}" x2="18" y2="{y + row_h}" stroke="{BORDER}" stroke-width="2"/>')
        parts.append(
            f'<circle cx="18" cy="{y + 18}" r="16" fill="{MEASURE}"/>'
            f'<text x="18" y="{y + 23}" font-size="14" font-weight="700" fill="#ffffff" text-anchor="middle">{i + 1}</text>'
            + _regels(48, y + 23, gewikkeld[i], 14, INK)
        )
    parts.append("</svg>")
    return _figure("".join(parts), CAPTIONS["steps"].get(language, CAPTIONS["steps"]["en"]))


def inject_infographics(body_html: str, language: str = "en") -> str:
    """
    Zet infographics vóór de tabellen/lijsten waar ze uit voortkomen. Faalt zacht:
    bij welke fout dan ook komt de originele HTML onveranderd terug — een
    infographic mag nooit een publicatie tegenhouden of tekst kwijtmaken.
    """
    if not body_html:
        return body_html

    # Idempotent: draait deze functie twee keer over dezelfde HTML (backfill na een
    # eerdere backfill, of een refresh van een al verrijkt artikel), dan komt er
    # geen tweede set infographics bij.
    if 'class="infographic"' in body_html:
        return body_html

    try:
        # BeautifulSoup wordt hier alleen gebruikt om te BESLISSEN wat er getekend
        # moet worden; de uiteindelijke HTML wordt met pure string-splicing
        # opgebouwd uit het origineel. str(soup) zou namelijk de hele body
        # herserialiseren — attributen herordenen, tags self-closing maken,
        # entities herschrijven — en dat soort stille markup-herschrijving heeft
        # in dit project al eens img-src'en beschadigd. Zo blijft elk byte dat we
        # niet zelf toevoegen gegarandeerd exact zoals het was.
        inserts: list[tuple[int, str]] = []

        for match in re.finditer(r"<table[\s>].*?</table>", body_html, re.S | re.I):
            if len(inserts) >= MAX_PER_PAGE:
                break
            table = BeautifulSoup(match.group(0), "html.parser").find("table")
            if not table:
                continue
            headers, body = _parse_table(table)
            if not headers:
                continue
            svg = _range_infographic(headers, body, language) or _matrix_infographic(headers, body, language)
            if svg:
                inserts.append((match.start(), svg))

        if len(inserts) < MAX_PER_PAGE:
            for match in re.finditer(r"<ol[\s>].*?</ol>", body_html, re.S | re.I):
                ol = BeautifulSoup(match.group(0), "html.parser").find("ol")
                if not ol:
                    continue
                items = [_txt(li) for li in ol.find_all("li", recursive=False)]
                svg = _steps_infographic(items, language)
                if svg:
                    inserts.append((match.start(), svg))
                    break

        if not inserts:
            return body_html

        result = []
        cursor = 0
        for position, svg in sorted(inserts):
            result.append(body_html[cursor:position])
            result.append(svg)
            cursor = position
        result.append(body_html[cursor:])

        logger.info(f"{len(inserts)} infographic(s) toegevoegd aan artikel")
        return "".join(result)
    except Exception as e:
        logger.error(f"Infographic-generatie mislukt (artikel blijft ongewijzigd): {e}")
        return body_html
