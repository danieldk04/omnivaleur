"""
Bouwt het trenddashboard: één pagina met de sterkste video's, de patronen
eronder, en filters om er zelf doorheen te lopen.

Twee dingen die het anders maken dan een lijstje:

  * De beeldjes zitten in de pagina zelf gebakken, niet als link. TikToks
    CDN-adressen verlopen na een paar dagen, dus een dashboard dat ernaar
    linkt is over een week een raster van kapotte plaatjes. We halen ze één
    keer op, verkleinen ze en zetten ze als data in de pagina. Dat kost
    megabytes maar levert een dashboard dat over een maand nog klopt.

  * Filteren gebeurt in de pagina zelf, zonder server. Alle video's staan als
    data in het bestand; de filters verbergen rijen. Daardoor werkt het ook
    offline en op de telefoon.

Draaien:
    python3 scripts/social_trends_dashboard.py scripts/output/trends-verkenning-*.json
"""
from __future__ import annotations

import base64
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from social_trends_analyse import PERIODES, analyseer  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


# ── Beeldjes ────────────────────────────────────────────────────────────────
def _haal_beeld(url: str) -> str:
    """Eén beeldje ophalen, verkleinen en als data-URI teruggeven. Mislukt het,
    dan een lege string: een kaart zonder plaatje is prima, een kapot dashboard
    niet."""
    if not url:
        return ""
    try:
        from PIL import Image
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Referer": "https://www.tiktok.com/"})
        rauw = urllib.request.urlopen(req, timeout=20).read()
        im = Image.open(io.BytesIO(rauw))
        im = im.convert("RGB")
        im.thumbnail((240, 320))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=62, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def haal_beeldjes(videos: list[dict]) -> None:
    """Parallel, want honderd beeldjes achter elkaar duurt minuten."""
    todo = [v for v in videos if v.get("beeld") and not v.get("beeld_data")]
    print(f"  {len(todo)} beeldjes ophalen …", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for v, data in zip(todo, pool.map(lambda x: _haal_beeld(x["beeld"]), todo)):
            v["beeld_data"] = data
    gelukt = sum(1 for v in todo if v.get("beeld_data"))
    print(f"  {gelukt} van {len(todo)} gelukt", flush=True)


# ── Pagina ──────────────────────────────────────────────────────────────────
STIJL = """<title>Trendmotor Omnivaleur</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Newsreader:opsz,wght@6..72,400;6..72,600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{
  --papier:#EEF1F1; --kaart:#F8FAFA; --rand:#D2DAD9; --rand-zacht:#E2E8E7;
  --inkt:#151B1B; --zacht:#5A6867; --accent:#0E6F6B; --accent-zacht:#DCEAE8;
  --goed:#1E7A4C; --slecht:#A8441C; --veld:#FFFFFF;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --papier:#0D1212; --kaart:#151D1D; --rand:#293636; --rand-zacht:#1E2828;
  --inkt:#E9EFEE; --zacht:#93A3A1; --accent:#5FD3C8; --accent-zacht:#16302E;
  --goed:#5BC98C; --slecht:#E08A5F; --veld:#101818;
}}
:root[data-theme="dark"]{
  --papier:#0D1212; --kaart:#151D1D; --rand:#293636; --rand-zacht:#1E2828;
  --inkt:#E9EFEE; --zacht:#93A3A1; --accent:#5FD3C8; --accent-zacht:#16302E;
  --goed:#5BC98C; --slecht:#E08A5F; --veld:#101818;
}
*{box-sizing:border-box}
body{background:var(--papier);color:var(--inkt);margin:0;
  font-family:"Newsreader",Georgia,serif;font-size:16px;line-height:1.55;
  padding:clamp(16px,3vw,44px)}
.wrap{max-width:1240px;margin:0 auto;display:flex;flex-direction:column;gap:36px}
h1,h2,h3{font-family:"Bricolage Grotesque",system-ui,sans-serif;margin:0;
  line-height:1.15;text-wrap:balance;font-weight:700}
h1{font-size:clamp(28px,4vw,42px);letter-spacing:-.02em}
h2{font-size:21px;letter-spacing:-.01em}
h3{font-size:14px;font-weight:500;text-transform:uppercase;letter-spacing:.1em;
  color:var(--zacht)}
p{margin:0}
.eyebrow{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent)}
.lead{color:var(--zacht);max-width:64ch}
header{display:flex;flex-direction:column;gap:12px;
  border-bottom:2px solid var(--inkt);padding-bottom:22px}
section{display:flex;flex-direction:column;gap:14px}
.sectiekop{display:flex;flex-direction:column;gap:3px}

/* periodeschakelaar */
.tabs{display:flex;gap:0;border:1px solid var(--rand);border-radius:3px;
  overflow:hidden;width:fit-content;background:var(--kaart)}
.tabs button{font-family:"Bricolage Grotesque",sans-serif;font-size:13px;
  font-weight:500;padding:9px 18px;border:0;background:transparent;
  color:var(--zacht);cursor:pointer;border-right:1px solid var(--rand)}
.tabs button:last-child{border-right:0}
.tabs button[aria-selected="true"]{background:var(--inkt);color:var(--papier)}
.tabs button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}

/* patroonkaarten */
.raster{display:grid;gap:14px;
  grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
.kaart{background:var(--kaart);border:1px solid var(--rand);border-radius:3px;
  padding:16px 18px;display:flex;flex-direction:column;gap:10px}
.tabelbox{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font-family:"Bricolage Grotesque",sans-serif;font-size:10px;font-weight:500;
  text-transform:uppercase;letter-spacing:.09em;color:var(--zacht);text-align:left;
  padding:7px 9px;border-bottom:1px solid var(--rand);white-space:nowrap}
td{padding:8px 9px;border-bottom:1px solid var(--rand-zacht);vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-family:"JetBrains Mono",monospace;
  font-variant-numeric:tabular-nums;white-space:nowrap}
.lift{font-family:"JetBrains Mono",monospace;font-weight:600}
.lift.op{color:var(--goed)} .lift.neer{color:var(--slecht)}
.staaf{height:5px;background:var(--rand-zacht);border-radius:3px;overflow:hidden;
  min-width:52px}
.staaf i{display:block;height:100%;background:var(--accent)}
.chip{display:inline-flex;align-items:baseline;gap:6px;padding:4px 10px;
  border:1px solid var(--rand);border-radius:14px;background:var(--kaart);
  font-family:"JetBrains Mono",monospace;font-size:12px}
.chip b{font-weight:600} .chip span{color:var(--zacht);font-size:11px}
.chips{display:flex;flex-wrap:wrap;gap:7px}

/* filterbalk */
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;
  background:var(--kaart);border:1px solid var(--rand);border-radius:3px;
  padding:14px 16px}
.veld{display:flex;flex-direction:column;gap:4px}
.veld label{font-family:"Bricolage Grotesque",sans-serif;font-size:10px;
  text-transform:uppercase;letter-spacing:.09em;color:var(--zacht)}
.veld select,.veld input{font-family:"JetBrains Mono",monospace;font-size:13px;
  padding:6px 9px;border:1px solid var(--rand);border-radius:2px;
  background:var(--veld);color:var(--inkt);min-width:130px}
.veld select:focus-visible,.veld input:focus-visible{outline:2px solid var(--accent);
  outline-offset:1px}
.telling{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--zacht);
  margin-left:auto}

/* videoraster */
.videos{display:grid;gap:16px;
  grid-template-columns:repeat(auto-fill,minmax(190px,1fr))}
.vid{display:flex;flex-direction:column;gap:8px;text-decoration:none;color:inherit}
.vid figure{margin:0;position:relative;aspect-ratio:9/14;overflow:hidden;
  border-radius:3px;background:var(--rand-zacht);border:1px solid var(--rand)}
.vid img{width:100%;height:100%;object-fit:cover;display:block}
.vid .leeg{display:flex;align-items:center;justify-content:center;height:100%;
  color:var(--zacht);font-family:"JetBrains Mono",monospace;font-size:11px}
.badge{position:absolute;top:7px;left:7px;background:var(--inkt);color:var(--papier);
  font-family:"JetBrains Mono",monospace;font-size:11px;font-weight:600;
  padding:3px 7px;border-radius:2px}
.plat{position:absolute;top:7px;right:7px;background:var(--accent);color:#fff;
  font-family:"Bricolage Grotesque",sans-serif;font-size:9px;letter-spacing:.08em;
  text-transform:uppercase;padding:3px 6px;border-radius:2px}
.vid h4{margin:0;font-family:"Newsreader",serif;font-size:13.5px;font-weight:400;
  line-height:1.4;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;
  overflow:hidden}
.vid .maker{font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--accent)}
.vid .stats{font-family:"JetBrains Mono",monospace;font-size:11px;color:var(--zacht);
  display:flex;flex-wrap:wrap;gap:8px;font-variant-numeric:tabular-nums}
.vid:hover img{opacity:.86}
.vid:focus-visible figure{outline:2px solid var(--accent);outline-offset:2px}
.let{border-left:3px solid var(--slecht);padding:2px 0 2px 14px;color:var(--zacht);
  max-width:64ch;font-size:15px}
footer{border-top:1px solid var(--rand);padding-top:18px;font-size:14px;
  color:var(--zacht);max-width:66ch}
.verborgen{display:none!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>"""


def _n(x) -> str:
    return f"{int(x):,}".replace(",", ".")


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lift(w: int) -> str:
    klasse = "op" if w > 0 else ("neer" if w < 0 else "")
    return f'<span class="lift {klasse}">{w:+d}%</span>'


def _hooktabel(rijen: list[dict]) -> str:
    if not rijen:
        return '<p class="lead">Te weinig video&rsquo;s in deze periode om patronen op te baseren.</p>'
    r = ['<div class="tabelbox"><table><thead><tr><th>Opening</th>'
         '<th class="num">n</th><th class="num">Eng.%</th>'
         '<th class="num">vs. rest</th><th class="num">Med. views</th>'
         '<th>Best presterende voorbeeld</th></tr></thead><tbody>']
    for h in rijen:
        r.append(f'<tr><td><b>{h["patroon"]}</b></td>'
                 f'<td class="num">{h["aantal"]}</td>'
                 f'<td class="num">{h["eng"]}</td>'
                 f'<td class="num">{_lift(h["eng_lift"])}</td>'
                 f'<td class="num">{_n(h["views"])}</td>'
                 f'<td><a href="{h["voorbeeld_url"]}" target="_blank" rel="noopener">'
                 f'{_esc(h["voorbeeld"])}</a></td></tr>')
    return "".join(r) + "</tbody></table></div>"


def _bucketkaart(titel: str, rijen: list[dict]) -> str:
    if not rijen:
        return ""
    top = max(r["med_eng"] for r in rijen) or 1
    regels = "".join(
        f'<tr><td>{r["groep"]}</td><td class="num">{r["aantal"]}</td>'
        f'<td class="num">{r["med_eng"]}</td>'
        f'<td style="width:34%"><span class="staaf"><i style="width:'
        f'{round(r["med_eng"]/top*100)}%"></i></span></td></tr>'
        for r in rijen)
    return (f'<div class="kaart"><h3>{titel}</h3><table><thead><tr><th>Groep</th>'
            f'<th class="num">n</th><th class="num">Eng.%</th><th></th></tr></thead>'
            f'<tbody>{regels}</tbody></table></div>')


def _onderwerpen(rijen: list[dict]) -> str:
    if not rijen:
        return '<p class="lead">Te weinig materiaal voor woordanalyse.</p>'
    return '<div class="chips">' + "".join(
        f'<span class="chip"><b>{_esc(r["woord"])}</b> '
        f'<span>{r["aandeel_boven"]}% in top &middot; n={r["aantal"]} &middot; '
        f'{r["med_eng"]}%</span></span>' for r in rijen) + "</div>"


def _hashtags(rijen: list[dict]) -> str:
    if not rijen:
        return '<p class="lead">Te weinig video&rsquo;s per hashtag om iets te zeggen.</p>'
    r = ['<div class="tabelbox"><table><thead><tr><th>Hashtag</th>'
         '<th class="num">n</th><th class="num">Eng.%</th>'
         '<th class="num">vs. gemiddeld</th><th class="num">Med. views</th>'
         '</tr></thead><tbody>']
    for h in rijen:
        r.append(f'<tr><td>#{_esc(h["tag"])}</td><td class="num">{h["aantal"]}</td>'
                 f'<td class="num">{h["med_eng"]}</td>'
                 f'<td class="num">{_lift(h["lift"])}</td>'
                 f'<td class="num">{_n(h["med_views"])}</td></tr>')
    return "".join(r) + "</tbody></table></div>"


def _sounds(rijen: list[dict]) -> str:
    if not rijen:
        return '<p class="lead">Geen sound die door meerdere makers gebruikt wordt.</p>'
    r = ['<div class="tabelbox"><table><thead><tr><th>Sound</th>'
         '<th class="num">Makers</th><th class="num">Video&rsquo;s</th>'
         '<th class="num">Med. views</th><th class="num">Eng.%</th>'
         '</tr></thead><tbody>']
    for s in rijen:
        r.append(f'<tr><td><a href="{s["url"]}" target="_blank" rel="noopener">'
                 f'{_esc(s["sound"])}</a></td>'
                 f'<td class="num">{s["makers"]}</td><td class="num">{s["videos"]}</td>'
                 f'<td class="num">{_n(s["med_views"])}</td>'
                 f'<td class="num">{s["med_eng"]}</td></tr>')
    return "".join(r) + "</tbody></table></div>"


def _videokaart(v: dict) -> str:
    beeld = (f'<img src="{v["beeld_data"]}" alt="" loading="lazy">'
             if v.get("beeld_data") else '<div class="leeg">geen beeld</div>')
    basis = "eigen normaal" if v["basis_herkomst"] == "eigen" else "niche-normaal"
    viraal = f'<span title="viraliteitsscore">V {v["viraal"]}</span>' if v["viraal"] else ""
    verval = 999999 if v["leeftijd_dagen"] is None else v["leeftijd_dagen"]
    return (f'<a class="vid" href="{v["url"]}" target="_blank" rel="noopener"'
            f' data-platform="{v["platform"]}" data-niche="{v["niche"]}"'
            f' data-taal="{v["taal"]}" data-views="{v["views"]}"'
            f' data-uitschieter="{v["uitschieter"]}" data-eng="{v["eng_ratio"]}"'
            f' data-viraal="{v["viraal"] or 0}" data-vers="{-verval}">'
            f'<figure>{beeld}<span class="badge" title="keer boven {basis}">'
            f'{v["uitschieter"]}&times;</span>'
            f'<span class="plat">{v["platform"]}</span></figure>'
            f'<span class="maker">@{_esc(v["handle"])}</span>'
            f'<h4>{_esc(v["tekst"][:120])}</h4>'
            f'<span class="stats"><span>{_n(v["views"])} views</span>'
            f'<span>{v["eng_ratio"]}%</span>{viraal}</span></a>')


SCRIPT = """
<script>
(function(){
  // Eén actieve periode tegelijk. De filters werken alleen op het raster dat je
  // op dat moment ziet — anders telt de teller video's mee die verborgen zijn
  // en klopt het getal nooit met wat er op je scherm staat.
  let actief = '7d';
  const blokken = document.querySelectorAll('[data-periode]');
  const tabs = document.querySelectorAll('.tabs button');
  const telling = document.querySelector('.telling');
  const f = {
    platform: document.getElementById('f-platform'),
    niche: document.getElementById('f-niche'),
    taal: document.getElementById('f-taal'),
    minviews: document.getElementById('f-minviews'),
    sort: document.getElementById('f-sort'),
  };

  function filter(){
    const grid = document.querySelector('[data-periode="' + actief + '"] .videos');
    if (!grid) return;
    const kaarten = Array.from(grid.querySelectorAll('.vid'));
    let zichtbaar = 0;
    for (const k of kaarten){
      const d = k.dataset;
      const ok = (f.platform.value === '*' || d.platform === f.platform.value)
              && (f.niche.value === '*' || d.niche === f.niche.value)
              && (f.taal.value === '*' || d.taal === f.taal.value)
              && (Number(d.views) >= Number(f.minviews.value || 0));
      k.classList.toggle('verborgen', !ok);
      if (ok) zichtbaar++;
    }
    const s = f.sort.value;
    kaarten.sort((a,b) => Number(b.dataset[s]) - Number(a.dataset[s]))
           .forEach(k => grid.appendChild(k));
    telling.textContent = zichtbaar === kaarten.length
      ? zichtbaar + " video's"
      : zichtbaar + ' van ' + kaarten.length + " video's";
  }

  function toon(p){
    actief = p;
    blokken.forEach(el => el.classList.toggle('verborgen', el.dataset.periode !== p));
    tabs.forEach(b => b.setAttribute('aria-selected', String(b.dataset.p === p)));
    filter();
  }

  tabs.forEach(b => b.addEventListener('click', () => toon(b.dataset.p)));
  Object.values(f).forEach(el => {
    el.addEventListener('change', filter);
    el.addEventListener('input', filter);
  });
  toon('7d');
})();
</script>"""


def bouw(data: dict, pad: Path) -> Path:
    nu = datetime.now()
    delen = [STIJL, '<div class="wrap"><header>',
             f'<p class="eyebrow">Gemeten op {nu.strftime("%d-%m-%Y om %H:%M")}</p>',
             '<h1>Wat werkt er in jouw niche?</h1>',
             f'<p class="lead">{_n(data["totaal"])} video&rsquo;s gescand, '
             f'{_n(data["met_datum"])} met een bruikbare datum. Alle cijfers komen '
             'rechtstreeks van het platform. De uitschieterfactor is hoeveel keer '
             'beter een video deed dan het gewone werk van diezelfde maker &mdash; '
             'daarmee telt het idee, niet de beroemdheid.</p>',
             '<div class="tabs" role="tablist">'
             + "".join(f'<button role="tab" data-p="{p}" aria-selected="false">'
                       f'Laatste {PERIODES[p]} dagen ({data[p]["aantal"]})</button>'
                       for p in PERIODES) + '</div>',
             '</header>']

    # filterbalk (geldt voor alle periodes tegelijk)
    platforms = sorted({v["platform"] for v in data["alles"]})
    niches = sorted({v["niche"] for v in data["alles"]})
    delen.append(
        '<section><div class="sectiekop"><p class="eyebrow">Filteren</p>'
        '<h2>De sterkste video&rsquo;s</h2>'
        '<p class="lead">Gesorteerd op uitschieterfactor. Klik een kaart om de '
        'video zelf te bekijken.</p></div>'
        '<div class="filters">'
        '<div class="veld"><label for="f-platform">Platform</label>'
        '<select id="f-platform"><option value="*">alle</option>'
        + "".join(f'<option>{p}</option>' for p in platforms) + '</select></div>'
        '<div class="veld"><label for="f-niche">Hoek</label>'
        '<select id="f-niche"><option value="*">alle</option>'
        + "".join(f'<option>{n}</option>' for n in niches) + '</select></div>'
        '<div class="veld"><label for="f-taal">Taal</label>'
        '<select id="f-taal"><option value="*">alle</option>'
        '<option value="nl">nl</option><option value="en">en</option></select></div>'
        '<div class="veld"><label for="f-minviews">Minimaal views</label>'
        '<input id="f-minviews" type="number" value="5000" step="5000" min="0"></div>'
        '<div class="veld"><label for="f-sort">Sorteren op</label>'
        '<select id="f-sort">'
        '<option value="uitschieter">uitschieterfactor</option>'
        '<option value="eng">engagement hoog</option>'
        '<option value="views">views</option>'
        '<option value="viraal">viraliteitsscore</option>'
        '<option value="vers">nieuwste</option>'
        '</select></div>'
        '<span class="telling"></span></div>')

    for p in PERIODES:
        kaarten = "".join(_videokaart(v) for v in data[p]["top"])
        delen.append(f'<div data-periode="{p}" class="verborgen">'
                     f'<div class="videos">{kaarten}</div></div>')
    delen.append('</section>')

    # patronen per periode
    for p in PERIODES:
        d = data[p]
        blok = [f'<div data-periode="{p}" class="verborgen" '
                'style="display:flex;flex-direction:column;gap:30px">']
        blok.append('<section><div class="sectiekop">'
                    '<p class="eyebrow">Openingszinnen</p><h2>Welke hook werkt?</h2>'
                    '<p class="lead">Per patroon: hoeveel video&rsquo;s ermee openen, '
                    'hun mediane engagement, en hoeveel dat scheelt met alle video&rsquo;s '
                    'die dat patroon níet gebruiken. Patronen met minder dan acht '
                    'video&rsquo;s staan er niet in.</p></div>'
                    + _hooktabel(d["hooks"]) + '</section>')
        blok.append('<section><div class="sectiekop">'
                    '<p class="eyebrow">Onderwerpen</p><h2>Waar gaat het over?</h2>'
                    '<p class="lead">Woorden die vaker in de best presterende helft '
                    'staan dan in de rest. Het percentage is hoeveel van de video&rsquo;s '
                    'met dit woord in de bovenste helft zitten.</p></div>'
                    + _onderwerpen(d["onderwerpen"]) + '</section>')
        blok.append('<section><div class="sectiekop">'
                    '<p class="eyebrow">Hashtags</p><h2>Welk label hangt samen met '
                    'betere cijfers?</h2>'
                    '<p class="lead">Let op de richting: een hashtag veroorzaakt geen '
                    'views, hij markeert een sóórt video. Lees dit als &ldquo;dit type '
                    'content loont&rdquo;, niet als knop.</p></div>'
                    + _hashtags(d.get("hashtags") or []) + '</section>')
        blok.append('<section><div class="sectiekop">'
                    '<p class="eyebrow">Vorm</p><h2>Lengte, tekst en hashtags</h2></div>'
                    '<div class="raster">'
                    + _bucketkaart("Videolengte", d["vorm"]["duur"])
                    + _bucketkaart("Lengte beschrijving", d["vorm"]["tekstlengte"])
                    + _bucketkaart("Aantal hashtags", d["vorm"]["hashtags"])
                    + '</div></section>')
        blok.append('<section><div class="sectiekop">'
                    '<p class="eyebrow">Sounds</p><h2>Wat meerdere makers gebruiken</h2>'
                    '<p class="lead">Eén video op een sound is toeval. Drie of meer '
                    'verschillende makers is een trend.</p></div>'
                    + _sounds(d["sounds"]) + '</section>')
        blok.append('</div>')
        delen.append("".join(blok))

    delen.append('<section><h2>Wat hier nog niet in staat</h2>'
                 '<p class="let">Instagram ontbreekt: hashtagpagina&rsquo;s zijn daar '
                 'alleen na inloggen te zien.</p>'
                 '<p class="let">YouTube heeft geen engagement-cijfers en geen datum '
                 'in de zoekpagina, dus die video&rsquo;s tellen niet mee in de '
                 'periodes en niet in de patronen. Ze staan er als bereiksignaal.</p>'
                 '</section>')
    delen.append('<footer>Uitschieterfactor = views gedeeld door de mediaan van '
                 'diezelfde maker. Heeft een maker minder dan drie video&rsquo;s in '
                 'deze meting, dan is de mediaan van zijn niche gebruikt. '
                 'Viraliteitsscore weegt shares het zwaarst, dan saves, dan reacties, '
                 'dan likes &mdash; de volgorde waarin TikTok bereik toekent.'
                 '</footer></div>' + SCRIPT)

    pad.write_text("\n".join(delen), encoding="utf-8")
    return pad


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    bron = Path(sys.argv[1])
    rauw = json.loads(bron.read_text(encoding="utf-8"))
    data = analyseer(rauw["videos"])

    nodig = {id(v): v for p in PERIODES for v in data[p]["top"]}
    haal_beeldjes(list(nodig.values()))

    uit = bouw(data, bron.with_name(bron.stem.replace("verkenning", "dashboard") + ".html"))
    mb = uit.stat().st_size / 1024 / 1024
    print(f"dashboard → {uit} ({mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
