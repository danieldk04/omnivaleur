#!/usr/bin/env python3
"""
Genereert de twee persoonlijke zinnen (opener + fit-reden) voor creators in
"Creator Outreach (TikTok)" die nog geen "Concept bericht" hebben, en zet het
resultaat in Notion. Gebruikt Sonnet 5, niet Opus — dit is een kort, simpel
schrijftaakje en geen zware redenering.

WAAROM ALLEEN DE CIJFERS EN NIETS ANDERS
    Op 11-09-2026 bleek een AI-verzonnen persoonlijk detail over iemands
    content (een Hermes-tas die niet op haar account voorkwam) een
    geforceerde, foute opener. Dit script geeft het model daarom NOOIT
    content-informatie — alleen de cijfers die al in Notion staan
    (gemiddelde views, totaal views, verkoopscore, aantal video's). Het
    model mag daar wél warm en persoonlijk over schrijven, maar kan niets
    over een specifieke video of post verzinnen omdat het die informatie
    niet krijgt.

Gebruik:
    export NOTION_TOKEN=... ANTHROPIC_API_KEY=...
    python3 scripts/leadgen_creators_openers.py run              # echt schrijven naar Notion
    python3 scripts/leadgen_creators_openers.py run --dry-run    # alleen tonen
    python3 scripts/leadgen_creators_openers.py run --limit 20   # per beurt max N (default 20)
"""
from __future__ import annotations

import argparse
import os
import re
import time

import httpx

DB_ID = "b49ee78e-8c0e-418e-b516-4a432753b499"  # Creator Outreach (TikTok)
NOTION_API = "https://api.notion.com/v1"
MODEL = "claude-sonnet-5"

SYSTEM = """Je schrijft namens Daniel de Koning, oprichter van Omnivaleur, twee losse
zinnen voor een koud, eerste contactbericht aan een TikTok-creator die tweedehands
kleding verkoopt via Vinted/Marktplaats/2dehands.

HARDE REGEL: je krijgt ALLEEN cijfers over deze creator (geen video's, geen bio,
geen content). Baseer je tekst uitsluitend op die cijfers. Verzin NOOIT iets over
een specifieke video, post, merk, product of levensverhaal — dat mag alleen als het
letterlijk in de input staat, en dat staat het hier nooit.

Schrijf twee stukken tekst die in een vaste sjabloonmail worden geplakt, dus
schrijf GEEN volledige, zelfstandige zinnen met hoofdletter en punt — het zijn
losse fragmenten die al in een grotere zin vallen.

1. OPENER wordt gevolgd door: "Ik werk aan Omnivaleur, ..." — schrijf dus één
   fragment dat op zichzelf kan staan vóór die zin, zonder aanhef ("Hi ..."),
   zonder hoofdletter nodig, over het bereik of aantal video's van de creator.
   Losse, persoonlijke toon, geen marketingtaal.
2. FIT vult de zin aan: "ik denk dat je een perfecte fit bent omdat ___." —
   schrijf dus een fragment dat na "omdat" past, met kleine letter beginnend,
   ZONDER punt aan het einde, en herhaal het woord "fit" of "perfecte fit"
   niet nog eens (dat staat al in de zin ervoor).

Antwoord EXACT in dit formaat, niets ervoor of erna:
OPENER: <fragment>
FIT: <fragment>"""

TEMPLATE = """Hi {voornaam},

{opener} Ik werk aan Omnivaleur, een tool waarmee je een artikel in een keer op Marktplaats, 2dehands en Vinted tegelijk plaatst in plaats van het drie keer apart te doen.

Ik zou je graag uitnodigen voor onze betaalde social media campagne, ik denk dat je een perfecte fit bent omdat {fit_reason}.

Als je wil, stuur ik je graag meer informatie over Omnivaleur en de details. Hoe klinkt voor jou het volgende?

- Lifetime gratis en volledige toegang tot de software.
- Een persoonlijke affiliate-link met 20% recurring commissie op elke verkoper die zich via jou aanmeldt.

Klinkt dit als iets wat bij jou past?

Groetjes,
Daniel"""


def _need(naam: str) -> str:
    v = os.environ.get(naam, "").strip()
    if not v:
        raise RuntimeError(f"{naam} ontbreekt in de omgeving")
    return v


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {_need('NOTION_TOKEN')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _voornaam(naam: str) -> str:
    schoon = re.sub(r"[^\w\s]", "", naam, flags=re.UNICODE).strip()
    return schoon.split()[0] if schoon.split() else naam.strip()


def _te_doen() -> list[dict]:
    """Rijen met Status Nieuw, e-mail aanwezig, geen concept, minstens 1 cijfer."""
    r = httpx.post(f"{NOTION_API}/databases/{DB_ID}/query", headers=_notion_headers(),
                    json={"page_size": 100}, timeout=20)
    r.raise_for_status()
    gevonden = []
    for row in r.json().get("results", []):
        p = row["properties"]
        status = (p.get("Status", {}).get("select") or {}).get("name")
        concept = "".join(t.get("plain_text", "") for t in p.get("Concept bericht", {}).get("rich_text", []))
        email = p.get("E-mail", {}).get("email")
        naam = ""
        for _, val in p.items():
            if val["type"] == "title":
                naam = "".join(t.get("plain_text", "") for t in val["title"])
        cijfers = {
            "gem_views": p.get("Gem. views", {}).get("number"),
            "totaal_views": p.get("Totaal views", {}).get("number"),
            "verkoopscore": p.get("Verkoopscore", {}).get("number"),
            "videos": p.get("Videos", {}).get("number"),
        }
        heeft_cijfer = any(v is not None for v in cijfers.values())
        if status == "Nieuw" and email and not concept.strip() and heeft_cijfer:
            gevonden.append({"id": row["id"], "naam": naam, "cijfers": cijfers})
    return gevonden


def _genereer(client, naam: str, cijfers: dict) -> tuple[str, str] | None:
    regels = []
    if cijfers["gem_views"]:
        regels.append(f"Gemiddelde views per video: {cijfers['gem_views']}")
    if cijfers["totaal_views"]:
        regels.append(f"Totaal views (sweep): {cijfers['totaal_views']}")
    if cijfers["verkoopscore"]:
        regels.append(f"Verkoopscore: {cijfers['verkoopscore']}")
    if cijfers["videos"]:
        regels.append(f"Aantal video's in de sweep: {cijfers['videos']}")
    prompt = f"Creator: {naam}\n\nCijfers:\n" + "\n".join(regels)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:  # noqa: BLE001
        print(f"  !! generatie mislukt voor {naam}: {type(e).__name__}: {e}")
        return None
    tekst = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    m_opener = re.search(r"OPENER:\s*(.+)", tekst)
    m_fit = re.search(r"FIT:\s*(.+)", tekst)
    if not m_opener or not m_fit:
        print(f"  !! onverwacht antwoordformaat voor {naam}: {tekst[:200]!r}")
        return None
    opener = _opschonen_opener(m_opener.group(1).strip())
    fit_reason = _opschonen_fit(m_fit.group(1).strip())
    return opener, fit_reason


def _opschonen_opener(opener: str) -> str:
    """Haalt een eventuele aanhef weg die het model er toch voor plakte."""
    opener = re.sub(r"^(hi|hoi|hey)\s+[\w' ]{1,25},\s*", "", opener, flags=re.I).strip()
    if opener and not opener[0].isupper():
        opener = opener[0].upper() + opener[1:]
    if opener and opener[-1] not in ".!?":
        opener += "."
    return opener


def _opschonen_fit(fit_reason: str) -> str:
    """Fragment na 'omdat': kleine letter, geen punt, geen dubbele 'fit'-vermelding."""
    fit_reason = re.sub(r",?\s*en dat maakt je een perfecte fit[^.]*\.?$", "", fit_reason, flags=re.I).strip()
    fit_reason = fit_reason.rstrip(".")
    if fit_reason:
        fit_reason = fit_reason[0].lower() + fit_reason[1:]
    return fit_reason


def _zet_concept(page_id: str, tekst: str) -> None:
    r = httpx.patch(f"{NOTION_API}/pages/{page_id}", headers=_notion_headers(),
                     json={"properties": {"Concept bericht": {"rich_text": [{"type": "text", "text": {"content": tekst}}]}}},
                     timeout=20)
    r.raise_for_status()


def run(limit: int, dry_run: bool) -> None:
    import anthropic
    client = anthropic.Anthropic()
    rijen = _te_doen()
    print(f"{len(rijen)} rij(en) met Status Nieuw + e-mail + geen concept + minstens 1 cijfer.")
    for rij in rijen[:limit]:
        resultaat = _genereer(client, rij["naam"], rij["cijfers"])
        if resultaat is None:
            continue
        opener, fit_reason = resultaat
        voornaam = _voornaam(rij["naam"])
        tekst = TEMPLATE.format(voornaam=voornaam, opener=opener, fit_reason=fit_reason)
        if dry_run:
            print(f"  [dry-run] {rij['naam']}:\n{tekst}\n")
        else:
            _zet_concept(rij["id"], tekst)
            print(f"  concept klaargezet voor {rij['naam']}")
        time.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("opdracht", choices=["run"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)
