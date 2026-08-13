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


# ---------------------------------------------------------------- u → je
# Omnivaleur tutoyeert. Via de NL-vertaling is "u" op zes pagina's binnengekomen.
# Zoeken-en-vervangen kan hier niet: bij "u" hoort een andere werkwoordsvorm
# ("kunt u" → "kun je", "u heeft" → "je hebt"), dus dit moet door het model.

U_VORM = re.compile(r"\b(u|uw|uzelf)\b")


def _tel_opmaak(html: str) -> tuple[int, int, int]:
    """Afbeeldingen, links en alinea's tellen. Na het omzetten moeten dat er
    precies evenveel zijn — anders heeft het model meer gedaan dan gevraagd en
    gooien we het resultaat weg."""
    return (len(re.findall(r"<img\b", html, re.I)),
            len(re.findall(r"<a\s", html, re.I)),
            len(re.findall(r"<p>", html, re.I)))


def _naar_je(tekst: str, is_html: bool = False) -> str:
    """Losse tekst (titel, takeaway, FAQ) omzetten."""
    return _vraag_om_je_vorm([tekst])[0]


BLOK = re.compile(r"(<(p|li|h[1-6]|blockquote|td|figcaption)\b[^>]*>)(.*?)(</\2>)",
                  re.I | re.S)


def _vraag_om_je_vorm(stukken: list[str]) -> list[str]:
    """Meerdere korte stukjes tekst in één keer omzetten. Genummerd heen en terug,
    zodat je kunt controleren dat je evenveel terugkrijgt als je verstuurde."""
    genummerd = "\n".join(f"[{i}] {t}" for i, t in enumerate(stukken))
    prompt = f"""Rewrite each numbered Dutch fragment so it addresses the reader informally with "je" instead of the formal "u".

Change ONLY the second-person forms and the verb conjugations that depend on them:
  "u kunt" -> "je kunt", "kunt u" -> "kun je", "u heeft" -> "je hebt",
  "heeft u" -> "heb je", "uw" -> "je" or "jouw", "uzelf" -> "jezelf",
  "u bent" -> "je bent", "bent u" -> "ben je", "u wilt" -> "je wilt".

Change NOTHING else: no rephrasing, no improving, no shortening, no translating. Leave HTML tags, attributes, URLs, numbers and brand names exactly as they are. If a fragment contains no formal form, return it unchanged.

Return EXACTLY {len(stukken)} lines, each starting with its own [number] marker and nothing else — no preamble, no code fences, no blank lines between them.

{genummerd}"""
    uit = _claude(prompt, max_tokens=16000)
    uit = re.sub(r"^```[a-z]*\n?|```$", "", uit).strip()
    terug = {}
    for regel in re.split(r"\n(?=\[\d+\])", uit):
        m = re.match(r"\[(\d+)\]\s?(.*)", regel, re.S)
        if m:
            terug[int(m.group(1))] = m.group(2).strip()
    if len(terug) != len(stukken):
        raise RuntimeError(f"{len(terug)} stukken terug op {len(stukken)} verstuurd")
    return [terug[i] for i in range(len(stukken))]


def _body_naar_je(body: str) -> str:
    """Alleen de alinea's aanpakken waar echt "u" in staat, en de nieuwe tekst er
    met string-splicing weer in zetten. De rest van de HTML wordt niet aangeraakt,
    dus afbeeldingen, links en opmaak kunnen niet sneuvelen."""
    treffers = [m for m in BLOK.finditer(body) if U_VORM.search(re.sub(r"<[^>]+>", " ", m.group(3)))]
    if not treffers:
        return body
    nieuw = []
    # Eén alinea per keer. Grotere porties liepen zelf tegen de tokenlimiet aan —
    # het model moet immers alles wat het krijgt ook weer uitschrijven.
    for i in range(0, len(treffers), 3):
        groep = treffers[i:i + 3]
        nieuw += _vraag_om_je_vorm([m.group(3) for m in groep])

    # Per alinea controleren. Wat het model heeft laten staan proberen we nog één
    # keer alleen; wat dán nog niet klopt laten we onaangeroerd staan in plaats van
    # de hele pagina te laten mislukken. Half omgezet is beter dan niet omgezet.
    for i, (m, vervanging) in enumerate(zip(treffers, nieuw)):
        if U_VORM.search(re.sub(r"<[^>]+>", " ", vervanging)):
            nieuw[i] = _vraag_om_je_vorm([m.group(3)])[0]

    uit, vorig, overgeslagen = [], 0, 0
    for m, vervanging in zip(treffers, nieuw):
        if U_VORM.search(re.sub(r"<[^>]+>", " ", vervanging)):
            overgeslagen += 1
            continue                              # laat deze alinea staan zoals hij was
        uit.append(body[vorig:m.start(3)])
        uit.append(vervanging)
        vorig = m.end(3)
    uit.append(body[vorig:])
    if overgeslagen:
        print(f"      ({overgeslagen} alinea's bleven staan — het model kreeg ze niet omgezet)")
    return "".join(uit)


def repareer_u_vorm(pagina: dict, doen: bool) -> list[str]:
    velden, gedaan = {}, []
    for veld in ("title", "meta_description", "h1", "quick_answer", "body_html"):
        waarde = pagina.get(veld) or ""
        if not U_VORM.search(re.sub(r"<[^>]+>", " ", waarde)):
            continue
        if not doen:
            gedaan.append(f"zou {veld} omzetten ({len(U_VORM.findall(waarde))}x)")
            continue
        nieuw = _body_naar_je(waarde) if veld == "body_html" else _naar_je(waarde)
        if veld == "body_html" and _tel_opmaak(waarde) != _tel_opmaak(nieuw):
            gedaan.append(f"!! {veld} OVERGESLAGEN: opmaak veranderde "
                          f"{_tel_opmaak(waarde)} -> {_tel_opmaak(nieuw)}")
            continue
        if veld != "body_html" and U_VORM.search(re.sub(r"<[^>]+>", " ", nieuw)):
            gedaan.append(f"!! {veld} OVERGESLAGEN: er staat nog steeds 'u' in")
            continue
        velden[veld] = nieuw
        gedaan.append(f"{veld} omgezet naar je-vorm")

    # Takeaways en FAQ per stukje tekst omzetten, niet als één brok JSON: één
    # aanhalingsteken verkeerd en je hebt geen lijst meer.
    takeaways = list(pagina.get("takeaways") or [])
    if any(U_VORM.search(str(t)) for t in takeaways):
        if not doen:
            gedaan.append("zou takeaways omzetten")
        else:
            velden["takeaways"] = _vraag_om_je_vorm([str(t) for t in takeaways])
            gedaan.append("takeaways omgezet naar je-vorm")

    faq = [dict(f) for f in (pagina.get("faq") or [])]
    plekken = [(i, sleutel) for i, f in enumerate(faq) for sleutel in ("question", "answer")
               if U_VORM.search(f.get(sleutel) or "")]
    if plekken:
        if not doen:
            gedaan.append(f"zou {len(plekken)} FAQ-teksten omzetten")
        else:
            omgezet = _vraag_om_je_vorm([faq[i][k] for i, k in plekken])
            for (i, k), tekst in zip(plekken, omgezet):
                faq[i][k] = tekst
            velden["faq"] = faq
            gedaan.append(f"{len(plekken)} FAQ-teksten omgezet naar je-vorm")

    if doen and velden:
        _bewaar(pagina["slug"], velden)
    return gedaan


def _heeft_u_vorm(pagina: dict) -> bool:
    if (pagina.get("language") or "").lower() != "nl":
        return False
    alles = " ".join([
        pagina.get(k) or "" for k in ("title", "meta_description", "h1", "quick_answer")
    ] + [re.sub(r"<[^>]+>", " ", pagina.get("body_html") or ""),
         json.dumps(pagina.get("takeaways") or [], ensure_ascii=False),
         json.dumps(pagina.get("faq") or [], ensure_ascii=False)])
    return bool(U_VORM.search(alles))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repareer", action="store_true",
                    help="ook echt herstellen; zonder deze vlag wordt alleen getoond")
    ap.add_argument("--u-vorm", action="store_true",
                    help="ook 'u' omzetten naar 'je' op Nederlandse pagina's")
    args = ap.parse_args()

    paginas = _paginas()
    stuk = [p for p in paginas
            if any(x.startswith("AFGEKAPT") for x in check_article(p))]
    print(f"{len(stuk)} van {len(paginas)} artikelen zijn afgekapt.\n")

    for pagina in stuk:
        print(f"— {pagina['slug']} [{pagina.get('language')}]")
        for regel in repareer(pagina, args.repareer):
            print(f"    {regel}")

    if args.u_vorm:
        met_u = [p for p in paginas if _heeft_u_vorm(p)]
        print(f"\n{len(met_u)} Nederlandse pagina's spreken de lezer met 'u' aan.\n")
        for pagina in met_u:
            print(f"— {pagina['slug']}")
            for regel in repareer_u_vorm(pagina, args.repareer):
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
