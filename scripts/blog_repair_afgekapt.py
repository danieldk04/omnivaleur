#!/usr/bin/env python3
"""
Repareert blogartikelen die middenin een zin ophouden.

WAT ER MIS WAS
Het model kreeg 8.000 tokens en liep daar bij lange artikelen tegenaan. Wat er op
dat moment stond werd gewoon opgeslagen en gepubliceerd: vijf artikelen eindigden
midden in een zin en één FAQ-antwoord bestond uit het woord "It". Niemand merkte
het, want de publicatienorm keek wel naar lengte en links, maar niet naar of de
tekst af was.

Dat kan nu niet meer gebeuren: de generator stopt bij een afgekapte respons
(`_afgekapt` in generator.py), de norm herkent het (`AFGEKAPT:` in quality.py) en
de pijplijn weigert zo'n artikel te publiceren. Dit script is voor wat er al
stond.

WAAROM REPAREREN EN NIET OPNIEUW GENEREREN
De artikelen zijn verder in orde: de afbeeldingen, interne links en screenshots
staan erin en de tekst is goed. Alleen het staartje ontbreekt. Opnieuw genereren
gooit al dat werk weg en levert een ander artikel op dezelfde URL op.

Gebruik:
    export ANTHROPIC_API_KEY=... SUPABASE_URL=... SUPABASE_KEY=...
    python3 scripts/blog_repair_afgekapt.py            # tonen wat er stuk is
    python3 scripts/blog_repair_afgekapt.py --repareer # ook echt herstellen
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from backend.content.quality import check_article

MODEL = "claude-sonnet-5"
SLUIT_BLOK = re.compile(r"</(p|ul|ol|h[1-6]|table|div|blockquote|figure)>", re.I)


def _db() -> tuple[str, dict]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sleutel = os.environ.get("SUPABASE_KEY", "")
    if not (url and sleutel):
        sys.exit("Zet SUPABASE_URL en SUPABASE_KEY in je omgeving.")
    return url, {"apikey": sleutel, "Authorization": f"Bearer {sleutel}",
                 "Content-Type": "application/json"}


def _paginas() -> list[dict]:
    url, headers = _db()
    rijen, offset = [], 0
    while True:
        deel = httpx.get(f"{url}/rest/v1/content_pages?select=*&limit=100&offset={offset}",
                         headers=headers, timeout=60).json()
        rijen += deel
        if len(deel) < 100:
            break
        offset += 100
    for rij in rijen:
        for veld in ("faq", "takeaways"):
            if isinstance(rij.get(veld), str):
                try:
                    rij[veld] = json.loads(rij[veld])
                except json.JSONDecodeError:
                    rij[veld] = []
    return rijen


def _bewaar(slug: str, velden: dict) -> None:
    url, headers = _db()
    r = httpx.patch(f"{url}/rest/v1/content_pages?slug=eq.{slug}",
                    headers=headers, json=velden, timeout=60)
    r.raise_for_status()


def _claude(prompt: str, max_tokens: int = 4000) -> str:
    import anthropic

    sleutel = os.environ.get("ANTHROPIC_API_KEY")
    if not sleutel:
        sys.exit("Zet ANTHROPIC_API_KEY in je omgeving.")
    client = anthropic.Anthropic(api_key=sleutel)
    bericht = client.messages.create(
        model=MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}])
    if getattr(bericht, "stop_reason", None) == "max_tokens":
        raise RuntimeError("de reparatie liep zelf tegen de tokenlimiet aan")
    return "".join(b.text for b in (bericht.content or []) if getattr(b, "text", None)).strip()


def _knip_halve_staart(body: str) -> tuple[str, str]:
    """Alles ná het laatste netjes afgesloten blok is de halve zin. Geef het hele
    deel terug plus wat eraf gaat, zodat je kunt zien wat je weggooit."""
    laatste = None
    for m in SLUIT_BLOK.finditer(body):
        laatste = m
    if not laatste:
        return body, ""
    return body[: laatste.end()], body[laatste.end():].strip()


def _herschrijf_slot(pagina: dict, body: str) -> str:
    taal = "Dutch (Netherlands)" if pagina.get("language") == "nl" else "English"
    staart = body[-1500:]
    prompt = f"""You are finishing a blog article that was accidentally cut off mid-sentence by a token limit. Write ONLY the missing ending — do not repeat or rewrite what is already there.

Article H1: {pagina['h1']}
Language: {taal}

The article currently ends like this (the last part of the HTML body):
{staart}

Write the natural continuation and conclusion: finish the thought that was started, and close the article properly. Two to four paragraphs, optionally one <h2> if the cut-off happened right at a new section heading. Match the existing tone exactly: a reseller talking to a colleague, concrete, no marketing fluff, no bullet-point summaries of what was already said.

Return ONLY raw HTML (<h2> and <p> tags), no markdown, no code fences, no preamble. The last character must be a closing tag."""
    slot = _claude(prompt)
    slot = re.sub(r"^```[a-z]*\n?|```$", "", slot).strip()
    return slot


def _herschrijf_faq(pagina: dict, vraag: str) -> str:
    taal = "Dutch (Netherlands)" if pagina.get("language") == "nl" else "English"
    prompt = f"""Write the answer to one FAQ question for a blog article. The original answer was cut off by a token limit and is missing.

Article H1: {pagina['h1']}
Question: {vraag}
Language: {taal}

Write 40 to 80 words. Concrete and useful, a reseller talking to a colleague, no marketing language, no hedging. Return ONLY the answer text — no question, no quotes, no HTML, no markdown."""
    return _claude(_ := prompt, max_tokens=600).strip()


def repareer(pagina: dict, doen: bool) -> list[str]:
    gedaan = []
    problemen = [p for p in check_article(pagina) if p.startswith("AFGEKAPT")]
    velden: dict = {}

    if any("eindigt niet" in p or "keer <p>" in p for p in problemen):
        heel, weg = _knip_halve_staart(pagina["body_html"] or "")
        if doen:
            slot = _herschrijf_slot(pagina, heel)
            velden["body_html"] = heel + "\n\n" + slot
            gedaan.append(f"staart aangevuld (+{len(slot)} tekens, "
                          f"{len(weg)} tekens halve zin weggehaald)")
        else:
            gedaan.append(f"zou de halve zin weghalen ({weg[:60]!r}...) en afmaken")

    faq = list(pagina.get("faq") or [])
    kort = [i for i, f in enumerate(faq) if len((f.get("answer") or "").strip()) < 40]
    if kort:
        for i in kort:
            if doen:
                faq[i] = {**faq[i], "answer": _herschrijf_faq(pagina, faq[i]["question"])}
                gedaan.append(f"FAQ-antwoord herschreven: {faq[i]['question'][:45]}")
            else:
                gedaan.append(f"zou FAQ-antwoord herschrijven: {faq[i]['question'][:45]}")
        if doen:
            velden["faq"] = faq

    if doen and velden:
        _bewaar(pagina["slug"], velden)
    return gedaan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repareer", action="store_true",
                    help="ook echt herstellen; zonder deze vlag wordt alleen getoond")
    args = ap.parse_args()

    paginas = _paginas()
    stuk = [p for p in paginas
            if any(x.startswith("AFGEKAPT") for x in check_article(p))]
    print(f"{len(stuk)} van {len(paginas)} artikelen zijn afgekapt.\n")

    for pagina in stuk:
        print(f"— {pagina['slug']} [{pagina.get('language')}]")
        for regel in repareer(pagina, args.repareer):
            print(f"    {regel}")

    if not args.repareer:
        print("\nNiets gewijzigd. Draai opnieuw met --repareer om te herstellen.")
        return

    over = [p for p in _paginas()
            if any(x.startswith("AFGEKAPT") for x in check_article(p))]
    print(f"\nNa reparatie: {len(over)} afgekapte artikelen over.")
    for p in over:
        print(f"  ! {p['slug']}")


if __name__ == "__main__":
    main()
