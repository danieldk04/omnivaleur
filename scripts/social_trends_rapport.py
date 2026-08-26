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
import base64
import asyncio
import gzip
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
    bundel_per_creator, schrijf_pagina, verzamel_instagram, verzamel_tiktok,
    verzamel_youtube,
)

UITVOER = Path(__file__).parent / "output"
ONTVANGER = "daniel@omnivaleur.nl"
NOTION_OUDER = "3c3b0954-fb72-81e1-983a-c36ff2959359"  # pagina "Trendmotor"
MODEL = "claude-opus-5"


# ── Het archief ─────────────────────────────────────────────────────────────
# Zonder dit begint elke week bij nul en zijn "30 dagen" en "90 dagen" niets
# anders dan de video's die deze ochtend toevallig in beeld kwamen. Daarmee kun
# je geen enkel patroon hard maken. Daarom houden we alles vast en tellen we
# elke week op: dezelfde video die opnieuw langskomt krijgt zijn nieuwste
# cijfers, een nieuwe video komt erbij. Na een paar weken staat er een paar
# duizend video's aan bewijs in plaats van één ochtendvangst.
ARCHIEF = Path(__file__).parent.parent / "data" / "trends-archief.json.gz"
ARCHIEF_DAGEN = 130   # iets meer dan 90, zodat de 90-dagenlaag altijd vol is


def _archief_lees() -> list[dict]:
    if not ARCHIEF.exists():
        return []
    try:
        with gzip.open(ARCHIEF, "rt", encoding="utf-8") as f:
            return json.load(f).get("videos", [])
    except Exception as e:
        print(f"! archief onleesbaar ({type(e).__name__}) — deze week telt alleen "
              f"de verse meting", file=sys.stderr)
        return []


def _archief_schrijf(videos: list[dict]) -> None:
    ARCHIEF.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(ARCHIEF, "wt", encoding="utf-8") as f:
        json.dump({"bijgewerkt": datetime.now(timezone.utc).isoformat(),
                   "aantal": len(videos), "videos": videos}, f, ensure_ascii=False)


def voeg_samen(oud: list[dict], nieuw: list[dict]) -> list[dict]:
    """
    Oud en nieuw samenvoegen op videonummer.

    De verse cijfers winnen altijd: een video die vorige week 40.000 views had
    en nu 90.000 moet met 90.000 meetellen, anders meten we de leeftijd van ons
    archief in plaats van de video. Wat we uit het oude wél overnemen is het
    gesproken woord — dat verandert niet en de ondertitellink is inmiddels dood.
    """
    per_id = {}
    for v in oud:
        sleutel = (v.get("platform"), v.get("video_id"))
        if sleutel[1]:
            per_id[sleutel] = v
    for v in nieuw:
        sleutel = (v.get("platform"), v.get("video_id"))
        if not sleutel[1]:
            continue
        bestaand = per_id.get(sleutel)
        if bestaand and not v.get("gesproken_3s") and bestaand.get("gesproken_3s"):
            for veld in ("gesproken_3s", "gesproken_15s", "spreektempo"):
                v[veld] = bestaand.get(veld)
        per_id[sleutel] = v

    grens = datetime.now(timezone.utc).date().toordinal() - ARCHIEF_DAGEN
    bewaard = []
    for v in per_id.values():
        datum = v.get("datum") or ""
        if datum:
            try:
                if datetime.strptime(datum, "%Y-%m-%d").date().toordinal() < grens:
                    continue
            except ValueError:
                pass
        bewaard.append(v)
    return bewaard


# Het merkbriefje. Twee roosterbeurten per dinsdag (voor zomer- en wintertijd)
# mogen samen precies één mail opleveren. Dit bestand staat in de repo naast het
# archief en wordt door dezelfde stap teruggeschreven.
MERK = Path(__file__).parent.parent / "data" / "laatste-rapport.txt"


def _al_verstuurd_vandaag() -> bool:
    try:
        return MERK.read_text(encoding="utf-8").strip() == datetime.now().strftime("%Y-%m-%d")
    except OSError:
        return False


def _noteer_verstuurd() -> None:
    MERK.parent.mkdir(parents=True, exist_ok=True)
    MERK.write_text(datetime.now().strftime("%Y-%m-%d") + "\n", encoding="utf-8")


# ── Meten ───────────────────────────────────────────────────────────────────
def meet() -> dict:
    vers = asyncio.run(verzamel_tiktok(scrolls=3, hashtag_limiet=None))
    vers += verzamel_youtube(query_limiet=None)
    vers += verzamel_instagram(hashtag_limiet=None)

    archief = _archief_lees()
    videos = voeg_samen(archief, vers)
    _archief_schrijf(videos)
    print(f"  archief: {len(archief)} bewaard + {len(vers)} vers "
          f"= {len(videos)} video's om op te oordelen", flush=True)

    UITVOER.mkdir(parents=True, exist_ok=True)
    pad = UITVOER / f"trends-verkenning-{datetime.now():%Y%m%d-%H%M}.json"
    pad.write_text(json.dumps({
        "gedraaid_op": datetime.now(timezone.utc).isoformat(),
        "aantal_videos": len(videos), "vers_deze_ronde": len(vers), "videos": videos,
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
                f"  tekst: {(v['tekst'] or '')[:150]}"
                + (f"\n  gezegd in de eerste 3 sec: \"{v['gesproken_3s']}\""
                   if v.get("gesproken_3s") else ""))
        if d.get("spreekhooks"):
            regels.append(
                f"GESPROKEN OPENINGEN — wat er in de eerste 3 seconden gezegd "
                f"wordt ({d.get('met_stem', 0)} video's met gesproken tekst). "
                f"'zeker' is hoe vaak het verschil overeind blijft bij hertrekken; "
                f"onder de 90 is het ruis en mag je er geen advies op bouwen:")
            for h in d["spreekhooks"]:
                merk = "HARD" if h.get("hard") else "zwak"
                regels.append(
                    f"- [{merk}] {h['patroon']}: n={h['aantal']} video's van "
                    f"{h['makers']} makers, zeker {h['zekerheid']}%, "
                    f"{h['eng']}% vs {h['eng_rest']}% ({h['eng_lift']:+d}%)\n"
                    f"  voorbeeld gezegd: \"{h['voorbeeld']}\" ({h['voorbeeld_url']})")
        if d.get("spreektempo"):
            regels.append("Spreektempo: " + " | ".join(
                f"{r['patroon']} n={r['aantal']} {r['eng']}% ({r['eng_lift']:+d}%, "
                f"zeker {r['zekerheid']}%)" for r in d["spreektempo"]))
        if d["hooks"]:
            regels.append("Bijschrift-openingen (los van wat er gezegd wordt):")
            for h in d["hooks"]:
                merk = "HARD" if h.get("hard") else "zwak"
                regels.append(f"- [{merk}] {h['patroon']}: n={h['aantal']} van "
                              f"{h['makers']} makers, zeker {h['zekerheid']}%, "
                              f"{h['eng']}% vs {h['eng_rest']}% ({h['eng_lift']:+d}%)")
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
- Bouw je advies op patronen die met [HARD] gemarkeerd zijn. Een patroon met
  [zwak] mag je noemen als "nog niet zeker", maar er nooit een opdracht op
  baseren. Zet in "waarom" altijd het aantal video's en de zekerheid erbij.
- De "hook" die je schrijft is wat hij UITSPREEKT in de eerste drie seconden.
  Leun daarbij op de gemeten gesproken openingen, niet op het bijschrift: uit de
  meting blijkt dat het bijschrift nauwelijks iets doet en het gesproken woord
  wel. Schrijf de hook zoals iemand praat, niet zoals iemand schrijft.
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
   "waarom": "welk gemeten getal dit onderbouwt, met n en zekerheid",
   "bewijs": "hoe hard dit is: 'hard' of 'voorzichtig'",
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


def _n(g) -> str:
    """1234567 -> 1,2 mln. Een mail leest niemand met een rekenmachine erbij."""
    g = int(g or 0)
    if g >= 1_000_000:
        return f"{g/1_000_000:.1f}".replace(".", ",") + " mln"
    if g >= 1_000:
        return f"{g/1_000:.0f}K"
    return str(g)


def _beeld_tag(v: dict, beelden: dict, breedte: int = 104) -> str:
    """
    Het beeldje van een video, als losse bijlage in de mail.

    Bewust niet als data-URI in de HTML: Gmail weigert die en dan zie je in
    precies het programma waar jij je mail leest helemaal niets. Een bijlage met
    een cid-verwijzing toont Gmail wél. Dat is het hele verschil tussen een mail
    met bewijs en een mail met lege vakjes.
    """
    data = v.get("beeld_data") or ""
    hoogte = round(breedte * 4 / 3)
    if not data.startswith("data:image"):
        return (f'<div style="width:{breedte}px;height:{hoogte}px;background:#E2E8E7;'
                f'border:1px solid #D2DAD9"></div>')
    cid = f"v{v.get('platform','x')[:1]}{v.get('video_id','')}"
    if cid not in beelden:
        try:
            beelden[cid] = base64.b64decode(data.split(",", 1)[1])
        except Exception:
            return ""
    return (f'<img src="cid:{cid}" width="{breedte}" height="{hoogte}" alt="" '
            f'style="display:block;width:{breedte}px;height:{hoogte}px;'
            f'object-fit:cover;border:1px solid #D2DAD9">')


def _cijfers(v: dict) -> str:
    """De cijfers van één video, in één regel."""
    stukken = [f"{_n(v.get('views'))} views"]
    if v.get("uitschieter"):
        # Twee heel verschillende dingen die allebei "keer" heten. Zien we drie of
        # meer video's van deze maker, dan is dit hoeveel keer beter dan hij
        # normaal doet — dat is bewijs. Zien we er maar één, dan wordt hij tegen
        # de hele niche afgezet en kan er 1200x uitkomen zonder dat het iets
        # zegt. Ze onder dezelfde vlag zetten maakt het grootste getal het
        # overtuigendste, en dat is precies verkeerd om.
        eigen = v.get("basis_herkomst") == "eigen"
        stukken.append(f"{v['uitschieter']}&times; boven zijn eigen normaal" if eigen
                       else f"{v['uitschieter']}&times; de niche-mediaan "
                            f"(1e video van deze maker)")
    if v.get("eng_ratio"):
        stukken.append(f"{v['eng_ratio']}% engagement")
    return " &middot; ".join(stukken)


def _bewijskaart(v: dict, beelden: dict) -> str:
    """Eén bewijsstuk: beeld, wat er gezegd wordt, en de cijfers eronder."""
    gezegd = (v.get("gesproken_3s") or "").strip()
    return (
        f'<td width="120" valign="top" style="padding:0 10px 0 0">'
        f'<a href="{_e(v["url"])}" style="text-decoration:none">'
        f'{_beeld_tag(v, beelden, 110)}</a>'
        f'<div style="font:400 11px/1.35 Georgia,serif;color:#151B1B;'
        f'margin:5px 0 0;width:110px">'
        + (f'&ldquo;{_e(gezegd[:70])}&rdquo;' if gezegd
           else f'@{_e(v["handle"])}') +
        f'</div>'
        f'<div style="font:400 10px/1.3 monospace;color:#5A6867;margin:3px 0 0;'
        f'width:110px">{_n(v.get("views"))} &middot; '
        f'{v.get("uitschieter", 0)}&times; '
        f'{"eigen" if v.get("basis_herkomst") == "eigen" else "niche"}</div></td>')


def _bewijsrij(videos: list[dict], beelden: dict) -> str:
    if not videos:
        return ""
    return ('<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
            + "".join(_bewijskaart(v, beelden) for v in videos[:4])
            + "</tr></table>")


def mail_html(data: dict, opdrachten: list[dict], dashboard_url: str) -> tuple[str, dict]:
    """
    De weekmail. Geeft de HTML terug én de beeldjes die eraan vast moeten.

    De opzet volgt één regel: geen bewering zonder beeld en zonder getal. Elke
    opdracht toont de video waar hij vandaan komt, elk patroon toont vier
    video's van vier verschillende makers waarin het patroon zit. Wat ik niet
    kan laten zien, staat er niet in.
    """
    beelden: dict[str, bytes] = {}
    week = datetime.now().strftime("%d-%m-%Y")
    d7, d30, d90 = data["7d"], data["30d"], data["90d"]
    per_url = {v["url"]: v for v in data.get("alles", [])}

    # ── De opdrachten, elk met de video waar hij op gebaseerd is ─────────────
    if opdrachten:
        rijen = []
        for i, o in enumerate(opdrachten, 1):
            bron = per_url.get(o.get("bron") or "")
            beeldcel = (
                f'<td width="126" valign="top" style="padding:0 16px 0 0">'
                f'<a href="{_e(o.get("bron"))}" style="text-decoration:none">'
                f'{_beeld_tag(bron, beelden, 116)}</a>'
                f'<div style="font:400 10px/1.3 monospace;color:#5A6867;'
                f'margin:5px 0 0;width:116px">{_cijfers(bron)}</div>'
                f'<div style="font:400 10px/1.3 monospace;color:#5A6867;'
                f'width:116px">@{_e(bron["handle"])}</div></td>'
            ) if bron else ""
            hard = str(o.get("bewijs", "")).startswith("hard")
            rijen.append(f"""
      <tr><td style="padding:0 0 26px">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>
          {beeldcel}
          <td valign="top">
            <div style="font:600 17px/1.3 Georgia,serif;color:#151B1B">
              {i}. {_e(o.get('titel'))}</div>
            <div style="font:400 15px/1.5 Georgia,serif;color:#151B1B;margin:8px 0 0">
              <b>Zeg dit:</b> &ldquo;{_e(o.get('hook'))}&rdquo;</div>
            <div style="font:400 15px/1.5 Georgia,serif;color:#151B1B;margin:5px 0 0">
              <b>Film:</b> {_e(o.get('beeld'))}</div>
            <div style="font:400 14px/1.5 Georgia,serif;color:#5A6867;margin:5px 0 0">
              {_e(o.get('lengte'))} &middot; sound: {_e(o.get('sound'))}</div>
            <div style="font:400 14px/1.5 Georgia,serif;color:#5A6867;margin:5px 0 0">
              <b>Waarom:</b> {_e(o.get('waarom'))}</div>
            <div style="margin:6px 0 0">
              <span style="font:600 10px/1 monospace;letter-spacing:.08em;
                text-transform:uppercase;padding:3px 6px;
                background:{'#DCEFE4' if hard else '#EEF1F1'};
                color:{'#1E7A4C' if hard else '#5A6867'}">
                bewijs: {_e(o.get('bewijs') or 'onbekend')}</span>
              <a href="{_e(o.get('bron'))}" style="color:#0E6F6B;font:400 13px
                Georgia,serif;margin-left:8px">bekijk de bronvideo</a></div>
          </td>
        </tr></table>
      </td></tr>""")
        blok = "".join(rijen)
    else:
        blok = ('<tr><td style="padding:0 0 22px;font:400 15px/1.5 Georgia,serif;'
                'color:#A8441C">Deze week geen opdrachten: er was te weinig '
                'gemeten materiaal om iets te onderbouwen. Liever niets dan '
                'iets verzonnens.</td></tr>')

    # ── De patronen, elk met vier video's waarin je het kunt zien ────────────
    stem_bron = d90 if (d90.get("spreekhooks") or d90.get("spreekwoorden")) else d30
    harde = [h for h in (stem_bron.get("spreekhooks") or []) if h.get("hard")][:3]
    harde_woorden = [h for h in (stem_bron.get("spreekwoorden") or [])
                     if h.get("hard")][:3]

    def patroonblok(h: dict, wat: str) -> str:
        richting = "#1E7A4C" if h["eng_lift"] > 0 else "#A8441C"
        return (
            f'<tr><td style="padding:0 0 24px">'
            f'<div style="font:600 15px/1.3 Georgia,serif;color:#151B1B">'
            f'{_e(h["patroon"])} '
            f'<span style="font:600 15px monospace;color:{richting}">'
            f'{h["eng_lift"]:+d}%</span></div>'
            f'<div style="font:400 12px/1.4 monospace;color:#5A6867;margin:3px 0 8px">'
            f'{h["aantal"]} video&rsquo;s &middot; {h["makers"]} verschillende makers '
            f'&middot; {h["zekerheid"]}% zeker &middot; {wat}</div>'
            f'{_bewijsrij(h.get("voorbeelden") or [], beelden)}'
            f'</td></tr>')

    if harde or harde_woorden:
        patronen = "".join(
            [patroonblok(h, "gesproken opening") for h in harde]
            + [patroonblok(h, "woord in de eerste 3 seconden")
               for h in harde_woorden])
        stem_inleiding = (
            f"Gemeten op {stem_bron.get('met_stem', 0)} video&rsquo;s waarvan we "
            f"het gesproken woord hebben. Alleen patronen die genoeg "
            f"video&rsquo;s halen, van genoeg verschillende makers, en die "
            f"overeind blijven als de steekproef 1.500 keer opnieuw getrokken "
            f"wordt. Onder elk patroon staan vier video&rsquo;s van vier "
            f"verschillende makers waarin je het kunt zien.")
    else:
        patronen = ""
        stem_inleiding = (
            f"Er is deze ronde nog geen gesproken patroon dat de toets haalt: "
            f"{stem_bron.get('met_stem', 0)} video&rsquo;s met gesproken tekst is "
            f"te weinig om iets hard te maken. Dat wordt elke week beter, want "
            f"de meting stapelt op.")

    # ── De sterkste video's van deze week, gewoon om te zien ─────────────────
    toppers = [v for v in d7["top"] if v.get("views", 0) >= 5000][:8]
    toprij = ""
    if toppers:
        cellen = "".join(_bewijskaart(v, beelden) for v in toppers[:4])
        cellen2 = "".join(_bewijskaart(v, beelden) for v in toppers[4:8])
        toprij = (f'<table role="presentation" cellpadding="0" cellspacing="0">'
                  f'<tr>{cellen}</tr>'
                  + (f'<tr><td colspan="4" height="14"></td></tr><tr>{cellen2}</tr>'
                     if cellen2 else "")
                  + '</table>')

    def tagrij(rijen):
        return "".join(
            f'<tr><td style="padding:4px 10px 4px 0;font:400 14px Georgia,serif">'
            f'#{_e(h["tag"])}</td>'
            f'<td style="padding:4px 10px 4px 0;font:400 14px monospace;color:#5A6867">'
            f'n={h["aantal"]}</td>'
            f'<td style="padding:4px 0;font:600 14px monospace;'
            f'color:{"#1E7A4C" if h["lift"] > 0 else "#A8441C"}">{h["lift"]:+d}%</td></tr>'
            for h in rijen[:6])

    html = f"""<!doctype html><html><body style="margin:0;background:#EEF1F1;padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="620" cellpadding="0" cellspacing="0"
       style="max-width:620px;background:#F8FAFA;border:1px solid #D2DAD9;padding:30px">
  <tr><td style="font:600 11px/1 monospace;letter-spacing:.16em;color:#0E6F6B;
      text-transform:uppercase;padding:0 0 8px">Trendmotor &middot; {week}</td></tr>
  <tr><td style="font:700 26px/1.2 Georgia,serif;color:#151B1B;padding:0 0 6px">
      Wat je deze week zou moeten maken</td></tr>
  <tr><td style="font:400 15px/1.5 Georgia,serif;color:#5A6867;padding:0 0 26px">
      Gemeten over {d7['aantal']} video&rsquo;s van de afgelopen 7 dagen,
      {d30['aantal']} over 30 dagen en {d90['aantal']} over 90 dagen, waarvan
      {data.get('met_stem_totaal', 0)} met het gesproken woord erbij.
      Alle cijfers komen rechtstreeks van het platform.</td></tr>
  {blok}
  <tr><td style="border-top:1px solid #D2DAD9;padding:22px 0 8px;
      font:700 17px/1.2 Georgia,serif;color:#151B1B">Het bewijs onder deze
      opdrachten</td></tr>
  <tr><td style="font:400 14px/1.5 Georgia,serif;color:#5A6867;padding:0 0 16px">
      {stem_inleiding}</td></tr>
  {patronen}
  {'<tr><td style="border-top:1px solid #D2DAD9;padding:22px 0 8px;font:700 17px/1.2 Georgia,serif;color:#151B1B">De sterkste video&rsquo;s van deze week</td></tr><tr><td style="font:400 14px/1.5 Georgia,serif;color:#5A6867;padding:0 0 14px">Gerangschikt op hoeveel keer ze boven het eigen normaal van hun maker uitkomen, niet op views &mdash; anders staan hier alleen de grote accounts.</td></tr><tr><td style="padding:0 0 22px">' + toprij + '</td></tr>' if toprij else ''}
  <tr><td style="border-top:1px solid #D2DAD9;padding:22px 0 10px;
      font:700 17px/1.2 Georgia,serif;color:#151B1B">Hashtags</td></tr>
  <tr><td style="font:400 14px/1.5 Georgia,serif;color:#5A6867;padding:0 0 10px">
      Hoogste engagement, laatste 7 dagen:</td></tr>
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
      Elk beeldje hierboven is een video die echt bestaat en echt zo presteerde.
      Klik erop om hem te bekijken. Kon een opdracht niet aan zo&rsquo;n video
      gekoppeld worden, dan staat hij er niet in.</td></tr>
</table></td></tr></table></body></html>"""
    return html, beelden


def verstuur(html: str, onderwerp: str, bijlage: Path | None = None,
             beelden: dict | None = None) -> bool:
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
    # De beeldjes gaan als losse onderdelen mee, met een cid waar de HTML naar
    # verwijst. Dat is de enige vorm die Gmail toont: een plaatje dat rechtstreeks
    # in de HTML gebakken zit (data:) laat Gmail weg, en dan is de hele mail een
    # rij lege vakjes zonder dat iets een fout meldt.
    if beelden:
        html_deel = bericht.get_payload()[-1]
        for cid, rauw in beelden.items():
            html_deel.add_related(rauw, maintype="image", subtype="jpeg",
                                  cid=f"<{cid}>")
        print(f"  {len(beelden)} beeldjes meegestuurd in de mail", flush=True)
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
    # Notion weigert een link met een lege url met een 400, en dan gaat de hele
    # pagina niet door. Er ís geen webversie van het dashboard ingesteld, dus dit
    # blok was elke week leeg en sloopte elke week het hele archief.
    if dashboard_url:
        blokken.append({"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Dashboard van deze week",
                "link": {"url": dashboard_url}}}]}})
    else:
        blokken.append({"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Het dashboard met alle video's zit als bijlage bij de "
                           "mail van deze week."}}]}})
    for i, o in enumerate(opdrachten, 1):
        blokken.append({"object": "block", "type": "heading_3", "heading_3": {
            "rich_text": [{"type": "text",
                           "text": {"content": f"{i}. {o.get('titel', '')}"[:190]}}]}})
        for label, sleutel in (("Zeg dit", "hook"), ("Film", "beeld"),
                               ("Waarom", "waarom")):
            blokken.append({"object": "block", "type": "paragraph", "paragraph": {
                "rich_text": [{"type": "text", "text": {
                    "content": f"{label}: {str(o.get(sleutel, ''))[:1800]}"}}]}})
        if o.get("bron"):
            blokken.append({"object": "block", "type": "paragraph", "paragraph": {
                "rich_text": [{"type": "text", "text": {
                    "content": "bewijs", "link": {"url": o["bron"]}}}]}})
    # Het gesproken-hookblok. Alleen de patronen die de hardheidstoets halen —
    # in het archief hoort geen percentage waar je later op terugkijkt en denkt
    # dat het bewezen was.
    stem_bron = data["90d"] if (data["90d"].get("spreekhooks")) else data["30d"]
    harde = [h for h in (stem_bron.get("spreekhooks") or []) if h.get("hard")][:6]
    if harde:
        blokken.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {
                "content": "Gesproken hooks die standhouden"}}]}})
        for h in harde:
            blokken.append({"object": "block", "type": "bulleted_list_item",
                            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {
                                "content": (f"{h['patroon']}: {h['eng_lift']:+d}% "
                                            f"engagement · {h['aantal']} video's van "
                                            f"{h['makers']} makers · {h['zekerheid']}% "
                                            f"zeker · voorbeeld: \"{h['voorbeeld'][:120]}\"")
                                            [:1900]}}]}})

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
        # Notion zegt in het antwoord zelf precies wat er mis is. Dat alleen als
        # "HTTPStatusError" loggen kostte een ronde van een kwartier om níets
        # wijzer te worden; nu staat de reden er meteen bij.
        antwoord = getattr(e, "response", None)
        details = ""
        if antwoord is not None:
            try:
                details = f" [{antwoord.status_code}] {antwoord.text[:400]}"
            except Exception:
                details = f" [{antwoord.status_code}]"
            if antwoord.status_code == 404:
                details += (" — koppel de Notion-integratie aan de pagina "
                            "Trendmotor (··· → Connections)")
        print(f"! Notion-archief mislukt: {type(e).__name__}{details}", file=sys.stderr)
        return ""


# ── Aansturing ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--droog", action="store_true", help="niet versturen, wel bouwen")
    ap.add_argument("--venster", metavar="VAN-TOT", default=None,
                    help="stop tenzij het nu binnen dit lokale uurvenster is, "
                         "en tenzij het rapport vandaag nog niet uitging")
    ap.add_argument("--notion-test", action="store_true",
                    help="alleen een testpagina in Notion schrijven en stoppen")
    ap.add_argument("--hergebruik", metavar="JSON",
                    help="niet opnieuw meten maar deze meting gebruiken")
    args = ap.parse_args()

    # GitHub roostert in UTC, Nederland schuift twee keer per jaar een uur op, en
    # — dat was de fout — GitHub start een geroosterde taak vaak een half uur tot
    # een uur te laat. De oude controle eiste precies 08:xx en stuurde daardoor op
    # 25-08 béide beurten weg: ze startten om 09:24 en 10:06. Het rapport ging dus
    # nooit uit, en niets meldde dat.
    #
    # Nu een venster in plaats van één uur, en een merkbriefje tegen dubbele mail:
    # zodra het rapport van vandaag verstuurd is, staat de datum in het archief en
    # slaat elke volgende beurt van diezelfde dag zichzelf over.
    if args.venster:
        van, _, tot = args.venster.partition("-")
        nu = datetime.now()
        if not (int(van) <= nu.hour <= int(tot)):
            print(f"nu {nu:%H:%M} lokaal, buiten {args.venster} — overslaan")
            return 0
        if _al_verstuurd_vandaag():
            print(f"het rapport van {nu:%d-%m} is al verstuurd — overslaan")
            return 0

    if args.notion_test:
        leeg = {p: {"aantal": 0, "spreekhooks": []} for p in PERIODES}
        url = naar_notion(leeg, [], "")
        print(f"Notion-testpagina: {url}" if url else "Notion-testpagina mislukt")
        return 0 if url else 1

    if args.hergebruik:
        pad = Path(args.hergebruik)
        videos = json.loads(pad.read_text(encoding="utf-8"))["videos"]
    else:
        gemeten = meet()
        pad, videos = gemeten["pad"], gemeten["videos"]

    data = analyseer(videos)
    print(f"gemeten: {data['totaal']} video's "
          f"({data['7d']['aantal']}/{data['30d']['aantal']}/{data['90d']['aantal']})")

    # Alles waar straks een beeldje bij moet: de sterkste video's per periode én
    # elk bewijsstuk onder elk patroon. Zonder deze tweede groep staan er in de
    # mail wel patronen maar geen video's eronder, en dan is het weer mijn woord
    # tegen het jouwe.
    nodig = {id(v): v for p in PERIODES for v in data[p]["top"]}
    for p in PERIODES:
        for sleutel in ("spreekhooks", "spreekwoorden", "spreektempo", "hooks",
                        "hashtags", "sounds"):
            for patroon in data[p].get(sleutel) or []:
                for v in patroon.get("voorbeelden") or []:
                    nodig[id(v)] = v
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

    # De bronvideo van elke opdracht krijgt ook een beeldje. Die staat vaak niet
    # in de toplijsten — juist een video die het patroon goed laat zien hoeft
    # geen uitschieter te zijn.
    per_url = {v["url"]: v for v in data["alles"]}
    bronnen = [per_url[o["bron"]] for o in opdrachten
               if o.get("bron") in per_url and not per_url[o["bron"]].get("beeld_data")]
    if bronnen:
        haal_beeldjes(bronnen)

    # Zonder ingestelde webversie wijst de knop naar de bijlage; die zit er altijd bij.
    dash_url = os.environ.get("DASHBOARD_URL", "")
    html, beelden = mail_html(data, opdrachten, dash_url)
    (UITVOER / "laatste-mail.html").write_text(html, encoding="utf-8")

    if args.droog:
        print(f"droge ronde — mail niet verstuurd, dashboard: {dash}")
        return 0

    notion_url = naar_notion(data, opdrachten, dash_url)
    if notion_url:
        print(f"Notion: {notion_url}")
    verstuurd = verstuur(html, f"Trendmotor — wat je deze week zou moeten maken "
                               f"({datetime.now():%d-%m})", bijlage=dash,
                         beelden=beelden)
    if verstuurd:
        _noteer_verstuurd()
    print("mail verstuurd" if verstuurd else "mail NIET verstuurd")
    return 0 if verstuurd else 1


if __name__ == "__main__":
    sys.exit(main())
