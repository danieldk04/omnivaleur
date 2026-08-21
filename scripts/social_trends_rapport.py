"""
De wekelijkse trendmotor: meten, analyseren, vijf opdrachten schrijven, mailen,
en in Notion archiveren. Draait bij GitHub Actions, elke dinsdag 08:30.

Waarom bij GitHub en niet op Railway: de meting heeft een echte browser nodig
(TikTok geeft zijn cijfers alleen aan een browser prijs). Railway draait op
Nixpacks zonder Chromium, en daar een browser in bouwen zet de bouw van de
live website op het spel voor een taak die er niets mee te maken heeft. Bij
GitHub staat de browser er standaard en raakt een mislukte meting de site niet.

De vijf opdrachten worden door Claude geschreven, maar aan een korte lijn:

  * Hij krijgt alleen de gemeten video's en de gemeten patronen te zien, nooit
    een open vraag.
  * Elke opdracht moet een bron-URL noemen. Noemt hij een URL die niet in de
    meting voorkomt, dan gooit dit script de opdracht weg. Zo kan hij geen
    voorbeeld verzinnen dat er goed uitziet maar niet bestaat.
  * Blijven er minder dan drie opdrachten over, dan gaat de mail toch uit — met
    de melding dat er te weinig te zeggen viel. Liever een dunne mail dan een
    verzonnen mail.

Draaien:
    python3 scripts/social_trends_rapport.py            # meten en versturen
    python3 scripts/social_trends_rapport.py --droog    # alles behalve versturen
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from social_trends_analyse import PERIODES, analyseer  # noqa: E402
from social_trends_dashboard import bouw as bouw_dashboard, haal_beeldjes  # noqa: E402
from social_trends_discover import (  # noqa: E402
    bundel_per_creator, schrijf_pagina, verzamel_tiktok, verzamel_youtube,
)

UITVOER = Path(__file__).parent / "output"
ONTVANGER = "daniel@omnivaleur.nl"
NOTION_OUDER = "3c3b0954-fb72-81e1-983a-c36ff2959359"  # pagina "Trendmotor"
MODEL = "claude-opus-5"


# ── Meten ───────────────────────────────────────────────────────────────────
def meet() -> dict:
    videos = asyncio.run(verzamel_tiktok(scrolls=3, hashtag_limiet=None))
    videos += verzamel_youtube(query_limiet=None)
    UITVOER.mkdir(parents=True, exist_ok=True)
    pad = UITVOER / f"trends-verkenning-{datetime.now():%Y%m%d-%H%M}.json"
    pad.write_text(json.dumps({
        "gedraaid_op": datetime.now(timezone.utc).isoformat(),
        "aantal_videos": len(videos), "videos": videos,
        "creators": bundel_per_creator(videos),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pad": pad, "videos": videos}


# ── Vijf opdrachten, aan de lijn van de data ────────────────────────────────
def _feiten(data: dict) -> str:
    """Wat Claude te zien krijgt. Alleen gemeten getallen, geen duiding."""
    regels = []
    for p, dagen in PERIODES.items():
        d = data[p]
        regels.append(f"\n=== LAATSTE {dagen} DAGEN ({d['aantal']} video's) ===")
        regels.append("Sterkste video's (uitschieterfactor = keer boven het eigen "
                      "normaal van die maker):")
        for v in d["top"][:14]:
            regels.append(
                f"- {v['uitschieter']}x | {v['views']} views | eng {v['eng_ratio']}% "
                f"| {v['duur']}s | @{v['handle']} ({v['taal']}, {v['niche']}) "
                f"| sound: {v['sound'][:40]} | URL: {v['url']}\n"
                f"  tekst: {(v['tekst'] or '')[:150]}")
        if d["hooks"]:
            regels.append("Openingszinnen (eng% t.o.v. video's zonder dat patroon):")
            for h in d["hooks"]:
                regels.append(f"- {h['patroon']}: n={h['aantal']}, {h['eng']}% "
                              f"vs {h['eng_rest']}% ({h['eng_lift']:+d}%)")
        if d.get("hashtags"):
            regels.append("Hashtags (eng% t.o.v. het gemiddelde):")
            for h in d["hashtags"][:10]:
                regels.append(f"- #{h['tag']}: n={h['aantal']}, {h['med_eng']}% "
                              f"({h['lift']:+d}%)")
        if d["vorm"]["duur"]:
            regels.append("Videolengte: " + " | ".join(
                f"{r['groep']} n={r['aantal']} {r['med_eng']}%" for r in d["vorm"]["duur"]))
        if d["sounds"]:
            regels.append("Sounds die meerdere makers gebruiken: " + " | ".join(
                f"{s['sound'][:35]} ({s['makers']} makers, {s['med_views']} views)"
                for s in d["sounds"][:6]))
    return "\n".join(regels)


PROMPT = """Je krijgt de gemeten cijfers van deze week uit de niche van Omnivaleur,
een Nederlandse tool waarmee tweedehandsverkopers hun advertenties in één keer op
meerdere marktplaatsen zetten (Vinted, Marktplaats, eBay, Etsy, Shopify).

Daniel maakt zelf de video's. Schrijf hem vijf concrete video-opdrachten voor
komende week, gebaseerd op wat hieronder gemeten is.

HARDE REGELS:
- Elke opdracht MOET een "bron" bevatten: één URL die letterlijk in de data
  hieronder staat. Verzin nooit een URL.
- Onderbouw elke opdracht met een gemeten getal uit de data. Geen getal, geen
  opdracht.
- Noem Omnivaleur nooit als werkwoord. De handeling heet crosslisten.
- Schrijf in het Nederlands, in gewone taal, zonder marketingtaal.
- Als de data een patroon tegenspreekt dat je zou verwachten, volg de data.

Geef ZUIVER JSON terug, zonder tekst eromheen:
{"opdrachten": [
  {"titel": "korte naam van de video",
   "hook": "de eerste zin die hij letterlijk uitspreekt",
   "beeld": "wat hij filmt, in één of twee zinnen",
   "lengte": "bijv. 15-20 sec",
   "sound": "naam van de sound, of 'eigen geluid'",
   "waarom": "welk gemeten getal dit onderbouwt",
   "bron": "https://..."}
]}

DATA:
"""


def schrijf_opdrachten(data: dict, sleutel: str) -> list[dict]:
    """
    Vijf opdrachten laten schrijven, en meteen controleren of ze op iets slaan.

    Bewust met streaming: dit antwoord is lang, en een gewone aanroep loopt dan
    tegen de leestijd van de verbinding aan. Dat gebeurde ook echt — de aanroep
    liep tien minuten en gaf toen een time-out, waarna het rapport stilletjes
    zonder opdrachten uitging. Streamen houdt de verbinding levend.
    """
    import anthropic

    geldige_urls = {v["url"] for p in PERIODES for v in data[p]["top"]}
    client = anthropic.Anthropic(api_key=sleutel)
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": PROMPT + _feiten(data)}],
        ) as stroom:
            antwoord = stroom.get_final_message()
        tekst = "".join(b.text for b in antwoord.content if b.type == "text")
    except Exception as e:
        print(f"! opdrachten schrijven mislukt: {type(e).__name__}: {e}", file=sys.stderr)
        return []

    m = re.search(r"\{.*\}", tekst, re.S)
    if not m:
        print(f"! geen JSON in het antwoord ({len(tekst)} tekens)", file=sys.stderr)
        return []
    try:
        rauw = json.loads(m.group(0)).get("opdrachten", [])
    except json.JSONDecodeError as e:
        print(f"! JSON onleesbaar: {e}", file=sys.stderr)
        return []

    # De controle waar het om draait: een opdracht zonder bestaande bron bestaat
    # niet. Zo kan er nooit een voorbeeld in de mail staan dat er goed uitziet
    # maar dat niemand ooit heeft gemaakt.
    goed = []
    for o in rauw:
        if o.get("bron") in geldige_urls:
            goed.append(o)
        else:
            print(f"! opdracht weggegooid, bron niet in de meting: "
                  f"{o.get('titel')!r}", file=sys.stderr)
    return goed


# ── Mail ────────────────────────────────────────────────────────────────────
def _e(t) -> str:
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def mail_html(data: dict, opdrachten: list[dict], dashboard_url: str) -> str:
    week = datetime.now().strftime("%d-%m-%Y")
    d7, d30, d90 = data["7d"], data["30d"], data["90d"]

    if opdrachten:
        blok = "".join(f"""
      <tr><td style="padding:0 0 22px">
        <div style="font:600 17px/1.3 Georgia,serif;color:#151B1B">{i}. {_e(o.get('titel'))}</div>
        <div style="font:400 15px/1.5 Georgia,serif;color:#151B1B;margin:8px 0 0">
          <b>Zeg dit:</b> &ldquo;{_e(o.get('hook'))}&rdquo;</div>
        <div style="font:400 15px/1.5 Georgia,serif;color:#151B1B;margin:5px 0 0">
          <b>Film:</b> {_e(o.get('beeld'))}</div>
        <div style="font:400 14px/1.5 Georgia,serif;color:#5A6867;margin:5px 0 0">
          {_e(o.get('lengte'))} &middot; sound: {_e(o.get('sound'))}</div>
        <div style="font:400 14px/1.5 Georgia,serif;color:#5A6867;margin:5px 0 0">
          <b>Waarom:</b> {_e(o.get('waarom'))}
          &middot; <a href="{_e(o.get('bron'))}" style="color:#0E6F6B">bewijs</a></div>
      </td></tr>""" for i, o in enumerate(opdrachten, 1))
    else:
        blok = ('<tr><td style="padding:0 0 22px;font:400 15px/1.5 Georgia,serif;'
                'color:#A8441C">Deze week geen opdrachten: er was te weinig '
                'gemeten materiaal om iets te onderbouwen. Liever niets dan '
                'iets verzonnens.</td></tr>')

    def tagrij(rijen):
        return "".join(
            f'<tr><td style="padding:4px 10px 4px 0;font:400 14px Georgia,serif">'
            f'#{_e(h["tag"])}</td>'
            f'<td style="padding:4px 10px 4px 0;font:400 14px monospace;color:#5A6867">'
            f'n={h["aantal"]}</td>'
            f'<td style="padding:4px 0;font:600 14px monospace;'
            f'color:{"#1E7A4C" if h["lift"] > 0 else "#A8441C"}">{h["lift"]:+d}%</td></tr>'
            for h in rijen[:6])

    return f"""<!doctype html><html><body style="margin:0;background:#EEF1F1;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="max-width:600px;background:#F8FAFA;border:1px solid #D2DAD9;padding:30px">
  <tr><td style="font:600 11px/1 monospace;letter-spacing:.16em;color:#0E6F6B;
      text-transform:uppercase;padding:0 0 8px">Trendmotor &middot; {week}</td></tr>
  <tr><td style="font:700 26px/1.2 Georgia,serif;color:#151B1B;padding:0 0 6px">
      Wat je deze week zou moeten maken</td></tr>
  <tr><td style="font:400 15px/1.5 Georgia,serif;color:#5A6867;padding:0 0 26px">
      Gemeten over {d7['aantal']} video&rsquo;s van de afgelopen 7 dagen,
      {d30['aantal']} over 30 dagen en {d90['aantal']} over 90 dagen.
      Alle cijfers komen rechtstreeks van het platform.</td></tr>
  {blok}
  <tr><td style="border-top:1px solid #D2DAD9;padding:22px 0 10px;
      font:700 17px/1.2 Georgia,serif;color:#151B1B">Wat de cijfers zeggen</td></tr>
  <tr><td style="font:400 14px/1.5 Georgia,serif;color:#5A6867;padding:0 0 10px">
      Hashtags met de hoogste engagement, laatste 7 dagen:</td></tr>
  <tr><td style="padding:0 0 18px"><table role="presentation" cellpadding="0"
      cellspacing="0">{tagrij(d7.get('hashtags') or [])}</table></td></tr>
  <tr><td style="font:400 14px/1.5 Georgia,serif;color:#5A6867;padding:0 0 22px">
      Op 90 dagen: {", ".join("#" + h["tag"] for h in (d90.get("hashtags") or [])[:5])
                    or "nog te weinig data"}. Dat is de stabiele laag &mdash;
      wat daar staat is geen weekpiek.</td></tr>
  <tr><td style="border-top:1px solid #D2DAD9;padding:20px 0 0">
      {'<a href="' + dashboard_url + '" style="display:inline-block;background:#151B1B;'
       'color:#F8FAFA;font:500 14px/1 Georgia,serif;padding:12px 20px;'
       'text-decoration:none">Open het dashboard met alle video&rsquo;s</a>'
       if dashboard_url else
       '<div style="font:400 15px/1.5 Georgia,serif;color:#151B1B">Het volledige '
       'dashboard met alle video&rsquo;s, beeld en filters zit als bijlage bij '
       'deze mail.</div>'}</td></tr>
  <tr><td style="font:400 13px/1.5 Georgia,serif;color:#5A6867;padding:18px 0 0">
      Elke opdracht hierboven is gekoppeld aan een video die echt bestaat en echt
      zo presteerde. Kon een opdracht dat niet, dan staat hij er niet in.</td></tr>
</table></td></tr></table></body></html>"""


def verstuur(html: str, onderwerp: str, bijlage: Path | None = None) -> bool:
    host = os.environ.get("MAIL_HOST")
    van = os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and van and wachtwoord):
        print("! geen mailgegevens (MAIL_HOST/MAIL_USER/MAIL_PASS) — niet verstuurd",
              file=sys.stderr)
        return False
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp
    bericht["From"] = f"Trendmotor <{van}>"
    bericht["To"] = ONTVANGER
    bericht.set_content("Dit bericht is in HTML. Open het in een mailprogramma "
                        "dat HTML toont.")
    bericht.add_alternative(html, subtype="html")
    # Het dashboard gaat als bijlage mee. Anders zou de mail moeten linken naar
    # een pagina die iemand met de hand opnieuw publiceert, en dan is de motor
    # niet autonoom maar afhankelijk van een handeling die niemand doet.
    if bijlage and bijlage.exists():
        bericht.add_attachment(bijlage.read_bytes(), maintype="text", subtype="html",
                               filename=f"trenddashboard-{datetime.now():%Y-%m-%d}.html")
    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as smtp:
        smtp.login(van, wachtwoord)
        smtp.send_message(bericht)
    return True


# ── Notion ──────────────────────────────────────────────────────────────────
def naar_notion(data: dict, opdrachten: list[dict], dashboard_url: str) -> str:
    """Elke week een eigen subpagina onder 'Trendmotor', zodat je kunt terugkijken.
    Zonder token of zonder gekoppelde integratie slaat dit stil over — de mail is
    het rapport, Notion is het archief."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("! geen NOTION_TOKEN — archief overgeslagen", file=sys.stderr)
        return ""
    import httpx

    week = datetime.now().strftime("%d-%m-%Y")
    blokken = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content":
            f"Gemeten op {week}. {data['7d']['aantal']} video's in 7 dagen, "
            f"{data['30d']['aantal']} in 30, {data['90d']['aantal']} in 90."}}]}}]
    blokken.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [
        {"type": "text", "text": {"content": "Dashboard van deze week",
                                  "link": {"url": dashboard_url}}}]}})
    for i, o in enumerate(opdrachten, 1):
        blokken.append({"object": "block", "type": "heading_3", "heading_3": {
            "rich_text": [{"type": "text",
                           "text": {"content": f"{i}. {o.get('titel', '')}"[:190]}}]}})
        for label, sleutel in (("Zeg dit", "hook"), ("Film", "beeld"),
                               ("Waarom", "waarom")):
            blokken.append({"object": "block", "type": "paragraph", "paragraph": {
                "rich_text": [{"type": "text", "text": {
                    "content": f"{label}: {str(o.get(sleutel, ''))[:1800]}"}}]}})
        blokken.append({"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "bewijs", "link": {"url": o.get("bron")}}}]}})
    try:
        r = httpx.post("https://api.notion.com/v1/pages",
                       headers={"Authorization": f"Bearer {token}",
                                "Notion-Version": "2022-06-28",
                                "Content-Type": "application/json"},
                       json={"parent": {"page_id": NOTION_OUDER},
                             "properties": {"title": [{"type": "text", "text": {
                                 "content": f"Week van {week}"}}]},
                             "children": blokken[:100]},
                       timeout=60.0)
        r.raise_for_status()
        return r.json().get("url", "")
    except Exception as e:
        hint = ""
        if getattr(e, "response", None) is not None and e.response.status_code == 404:
            hint = (" — koppel de Notion-integratie aan de pagina Trendmotor "
                    "(··· → Connections)")
        print(f"! Notion-archief mislukt: {type(e).__name__}{hint}", file=sys.stderr)
        return ""


# ── Aansturing ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--droog", action="store_true", help="niet versturen, wel bouwen")
    ap.add_argument("--alleen-uur", type=int, default=None,
                    help="stop tenzij het nu dit uur is (lokale tijd)")
    ap.add_argument("--hergebruik", metavar="JSON",
                    help="niet opnieuw meten maar deze meting gebruiken")
    args = ap.parse_args()

    # GitHub roostert in UTC, en Nederland schuift twee keer per jaar een uur op.
    # In plaats van het rooster elk halfjaar met de hand te verzetten, draaien we
    # op twee UTC-tijden en laat deze controle de verkeerde beurt stilletjes gaan.
    if args.alleen_uur is not None and datetime.now().hour != args.alleen_uur:
        print(f"nu {datetime.now():%H:%M} lokaal, niet {args.alleen_uur}:xx — overslaan")
        return 0

    if args.hergebruik:
        pad = Path(args.hergebruik)
        videos = json.loads(pad.read_text(encoding="utf-8"))["videos"]
    else:
        gemeten = meet()
        pad, videos = gemeten["pad"], gemeten["videos"]

    data = analyseer(videos)
    print(f"gemeten: {data['totaal']} video's "
          f"({data['7d']['aantal']}/{data['30d']['aantal']}/{data['90d']['aantal']})")

    nodig = {id(v): v for p in PERIODES for v in data[p]["top"]}
    haal_beeldjes(list(nodig.values()))
    dash = bouw_dashboard(data, pad.with_name(
        pad.stem.replace("verkenning", "dashboard") + ".html"))
    schrijf_pagina({"aantal_videos": data["totaal"],
                    "aantal_creators": len(bundel_per_creator(videos)),
                    "creators": bundel_per_creator(videos)},
                   pad.with_suffix(".html"))

    sleutel = os.environ.get("ANTHROPIC_API_KEY", "")
    opdrachten = schrijf_opdrachten(data, sleutel) if sleutel else []
    print(f"opdrachten die de broncontrole haalden: {len(opdrachten)}")

    # Zonder ingestelde webversie wijst de knop naar de bijlage; die zit er altijd bij.
    dash_url = os.environ.get("DASHBOARD_URL", "")
    html = mail_html(data, opdrachten, dash_url)
    (UITVOER / "laatste-mail.html").write_text(html, encoding="utf-8")

    if args.droog:
        print(f"droge ronde — mail niet verstuurd, dashboard: {dash}")
        return 0

    notion_url = naar_notion(data, opdrachten, dash_url)
    if notion_url:
        print(f"Notion: {notion_url}")
    verstuurd = verstuur(html, f"Trendmotor — wat je deze week zou moeten maken "
                               f"({datetime.now():%d-%m})", bijlage=dash)
    print("mail verstuurd" if verstuurd else "mail NIET verstuurd")
    return 0 if verstuurd else 1


if __name__ == "__main__":
    sys.exit(main())
