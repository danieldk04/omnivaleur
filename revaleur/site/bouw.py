"""Revaleur-herbouw: bouwt de statische winkel (EN op /, NL op /nl/) uit catalogus.json.

Gebruik:
    python3 -m revaleur.site.import_shopify          # catalogus ophalen (later: uit de Revaleur-database)
    python3 -m revaleur.site.bouw                    # site bouwen in revaleur/site/dist

Alle URL's blijven gelijk aan Shopify (/products/x, /collections/x, /pages/x, /policies/x,
/blogs/news/x, /nl/...), zodat zoekverkeer en advertenties niets merken. Zie revaleur/docs/revaleur-ontwerp.md.
"""
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DOMEIN = "https://revaleur.com"
API = "https://api.revaleur.com/api/revaleur"
MAIL = "info@revaleur.com"
GOUD, ROOD, INKT = "#B89A50", "#E02229", "#121212"

# ---------------------------------------------------------------- vertalingen
T = {
    "nl": {
        "Categories": "Categorieën", "Brands": "Merken", "Blog": "Blog", "Our mission": "Onze missie",
        "Search": "Zoeken", "Cart": "Winkelmand", "Add to cart": "In winkelmand", "In your cart": "In je winkelmand",
        "Sold": "Verkocht", "Retail": "Nieuwprijs", "Free shipping to NL & BE": "Gratis verzending naar NL & BE",
        "Hurry up: only 1 available": "Snel zijn: nog maar 1 beschikbaar",
        "100% authentic or 200% money-back": "100% authentiek of 200% geld terug",
        "Not satisfied? Easy returns": "Niet tevreden? Eenvoudig retourneren",
        "Unique item — only 1 available. Once it's gone, it's gone forever.":
            "Uniek item, maar 1 beschikbaar. Weg is weg.",
        "Verified Authentic & Cleaned": "Geverifieerd authentiek en gereinigd",
        "See size chart & measurements": "Bekijk maattabel en afmetingen",
        "Description": "Omschrijving", "Shipping": "Verzending", "Returns": "Retourneren",
        "Our latest products, live now": "Onze nieuwste producten, nu live",
        "Shop the latest products": "Shop de nieuwste producten",
        "Vintage designer fashion for a timeless wardrobe": "Vintage designermode voor een tijdloze garderobe",
        "Your #1 in vintage designer fashion": "Jouw nr. 1 in vintage designermode",
        "715+ happy customers": "715+ tevreden klanten",
        "Sort by": "Sorteren", "Newest": "Nieuwste", "Price: low to high": "Prijs: laag naar hoog",
        "Price: high to low": "Prijs: hoog naar laag", "Brand": "Merk", "All": "Alle", "products": "producten",
        "Your cart": "Je winkelmand", "Your cart is empty": "Je winkelmand is leeg", "Continue shopping": "Verder winkelen",
        "Remove": "Verwijderen", "Subtotal": "Subtotaal", "Shipping costs": "Verzendkosten", "Total": "Totaal",
        "Free": "Gratis", "Checkout": "Afrekenen", "Country": "Land", "Netherlands": "Nederland", "Belgium": "België",
        "Rest of Europe": "Rest van Europa", "Outside Europe": "Buiten Europa",
        "Checkout is temporarily unavailable. Your cart is saved, please try again in a few minutes.":
            "Afrekenen is even niet beschikbaar. Je winkelmand blijft bewaard, probeer het over een paar minuten opnieuw.",
        "Sorry, this item was just sold.": "Dit artikel is zojuist verkocht.",
        "Checking…": "Controleren…", "Contact us": "Contact", "Policies": "Voorwaarden",
        "Shipping policy": "Verzendbeleid", "Refund policy": "Retourbeleid", "Terms of service": "Algemene voorwaarden",
        "Privacy policy": "Privacybeleid", "News": "Nieuws", "Read more": "Lees verder",
        "Thank you for your order": "Bedankt voor je bestelling",
        "We have sent a confirmation to your email. You will get a tracking link when your order ships.":
            "We hebben een bevestiging naar je e-mail gestuurd. Zodra je bestelling verzonden is, krijg je een trackinglink.",
        "Nothing found": "Niets gevonden", "Search results": "Zoekresultaten", "Page not found": "Pagina niet gevonden",
        "Back to the shop": "Terug naar de winkel", "Size": "Maat", "Condition": "Staat",
        "Secure checkout via Stripe: iDEAL and cards": "Veilig afrekenen via Stripe: iDEAL en kaart",
        "Free from €100": "Gratis vanaf €100", "Free shipping from €100": "Gratis verzending vanaf €100",
        "Quick delivery worldwide": "Snelle levering wereldwijd", "14 days return policy": "14 dagen retour",
        "Professionally reviewed": "Professioneel gecontroleerd", "Saving 2,700 liters of water": "Bespaart 2.700 liter water",
        "Name": "Naam", "Email": "E-mail", "Phone number": "Telefoonnummer", "Comment": "Opmerking", "Send": "Verstuur",
        "Message sent": "Bericht verzonden",
    }
}


class Tx:
    def __init__(self, taal):
        self.taal = taal

    def __call__(self, s):
        return T["nl"].get(s, s) if self.taal == "nl" else s


def esc(s):
    return html.escape(str(s), quote=True)


def euro(x, taal):
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if taal == "nl" else f"{x:,.2f}"
    return "€" + s


def pre(taal):
    return "/nl" if taal == "nl" else ""


# ---------------------------------------------------------------- statische pagina's
def lees_beleid(naam):
    p = ROOT / "docs" / "beleid" / f"{naam}.txt"
    return p.read_text() if p.exists() else ""


def tekst_naar_html(t):
    uit, lijst = [], []
    for r in [x.strip() for x in t.splitlines() if x.strip()]:
        uit.append(f"<p>{esc(r)}</p>")
    return "\n".join(uit + lijst)


PAGINA_NL = {}
_pn = SITE / "pagina_nl.json"
if _pn.exists():
    PAGINA_NL = json.loads(_pn.read_text())

CSS = """
@font-face{font-family:Montserrat;font-weight:500;src:url(/assets/m500.woff2) format('woff2');font-display:swap}
@font-face{font-family:Montserrat;font-weight:700;src:url(/assets/m700.woff2) format('woff2');font-display:swap}
:root{--goud:#B89A50;--rood:#E02229;--inkt:#121212;--grijs:#f3f3f3;--lijn:#e5e5e5}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:500 15px/1.6 Montserrat,system-ui,sans-serif;color:var(--inkt);background:#fff}
a{color:inherit}img{max-width:100%;height:auto;display:block}
.wrap{max-width:1600px;margin:0 auto;padding:0 20px}
.bar1{background:var(--rood);color:#fff;text-align:center;font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;padding:10px 12px}
.bar2{background:var(--goud);color:var(--inkt);font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;padding:8px 20px;display:flex;align-items:center;justify-content:center;gap:16px;position:relative}
.bar2 .soc{position:absolute;left:20px;display:flex;gap:14px}.bar2 .soc a{text-decoration:none;font-size:12px}
header.top{border-bottom:1px solid var(--lijn);background:#fff;position:sticky;top:0;z-index:20}
header.top .wrap{display:flex;align-items:center;gap:28px;height:78px}
header.top .logo img{height:62px;width:auto}
nav.main{display:flex;gap:22px;flex:1;align-items:center}
nav.main a,nav.main summary{text-transform:uppercase;font-size:13px;letter-spacing:.08em;text-decoration:none;cursor:pointer;list-style:none;opacity:.82}
nav.main a:hover,nav.main summary:hover{opacity:1}
nav.main details{position:relative}nav.main details>div{position:absolute;top:100%;left:0;background:#fff;border:1px solid var(--lijn);padding:10px 0;min-width:220px;box-shadow:0 8px 24px #0001}
nav.main details>div a{display:block;padding:7px 18px;text-transform:none;letter-spacing:0;font-size:14px;opacity:1}
.tools{display:flex;gap:18px;align-items:center;font-size:13px}.tools a{text-decoration:none}
.cartlink{position:relative;font-size:20px}.cartlink b{position:absolute;top:-8px;right:-12px;background:var(--inkt);color:#fff;border-radius:99px;font-size:11px;min-width:18px;height:18px;line-height:18px;text-align:center}
#menuknop{display:none;background:none;border:0;font-size:24px;cursor:pointer}
h1,h2{text-transform:uppercase;letter-spacing:.02em;line-height:1.2}h1{font-size:30px;margin:28px 0 12px}h2{font-size:22px}
.hero{position:relative;min-height:560px;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:#0b1220;overflow:hidden}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.55}.hero>div{position:relative;padding:20px}
.hero h1{font-size:44px;margin:0 0 10px}.hero p{font-weight:700;text-transform:uppercase;opacity:.85;margin:0 0 24px}
.knop{display:inline-block;background:var(--inkt);color:#fff;border:0;border-radius:8px;padding:15px 30px;font:700 14px Montserrat,sans-serif;letter-spacing:.08em;text-transform:uppercase;text-decoration:none;cursor:pointer;text-align:center}
.knop.wit{background:#fff;color:var(--inkt)}.knop.rand{background:#fff;color:var(--inkt);border:1px solid var(--inkt)}.knop:disabled{background:#bbb;cursor:not-allowed}
.raster{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0 40px}
.kaart{text-decoration:none;position:relative;display:block}.kaart .foto{aspect-ratio:3/4;background:var(--grijs);overflow:hidden}.kaart .foto img{width:100%;height:100%;object-fit:cover}
.kaart .merk{font-size:12px;opacity:.6;text-transform:uppercase;letter-spacing:.06em;margin-top:8px}.kaart .tit{font-size:14px;margin:2px 0}
.prijs{font-weight:700}.prijs s{opacity:.55;font-weight:500;margin-right:6px}.prijs .nu{color:var(--inkt)}
.badge{position:absolute;top:8px;left:8px;background:var(--rood);color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:99px}.badge.uit{background:var(--inkt)}
.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:8px 0 8px}.filters select,.filters input,input.veld,select.veld,textarea.veld{font:500 14px Montserrat,sans-serif;padding:10px 12px;border:1px solid #bbb;border-radius:8px;background:#fff}
.pp{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:48px;margin:36px 0}
.galerij .groot{background:var(--grijs)}.galerij .groot img{width:100%}.galerij .thumbs{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:8px}.galerij .thumbs img{cursor:pointer;aspect-ratio:1;object-fit:cover;border:2px solid transparent}.galerij .thumbs img.aan{border-color:var(--inkt)}
.info{text-align:center}.info h1{font-size:25px}.info .prijsregel{font-size:20px;font-weight:700;margin:8px 0}.info .prijsregel s{color:var(--rood);margin-right:8px}
.info .groen{color:#1a7a1a;font-size:13px;font-weight:700}.punten{list-style:none;padding:0;margin:20px 0;text-align:left;display:grid;gap:10px;font-weight:700;text-transform:uppercase;font-size:14px}.punten li:before{content:"✓ ";}
.unik{color:#c0392b;font-weight:700;font-size:14px;margin:16px 0}.info .knop{width:100%;margin:6px 0}
.beschr{text-align:left;margin-top:24px;font-weight:500}.beschr details{border-top:1px solid var(--lijn);padding:12px 0}.beschr summary{font-weight:700;text-transform:uppercase;font-size:13px;letter-spacing:.06em;cursor:pointer}
.inhoud{max-width:860px;margin:0 auto;padding:12px 20px 60px}.inhoud h2,.inhoud h3{margin-top:30px}
footer{background:var(--grijs);margin-top:60px;padding:40px 0;font-size:14px}footer .wrap{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:30px}footer a{display:block;text-decoration:none;margin:4px 0}footer .klein{grid-column:1/-1;opacity:.7;font-size:12px}
.winkelmand table{width:100%;border-collapse:collapse}.winkelmand td{padding:14px 8px;border-bottom:1px solid var(--lijn);vertical-align:middle}.winkelmand td:first-child{width:96px}.winkelmand td img{width:80px;min-width:80px;aspect-ratio:1;object-fit:cover}
.melding{background:#fdecea;color:#7a1b13;border-radius:8px;padding:12px 16px;margin:14px 0}
.zoek{display:none;background:#fff;border-bottom:1px solid var(--lijn);padding:12px 0}.zoek.aan{display:block}
.pillen{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.pillen a{border:1px solid var(--lijn);padding:7px 14px;border-radius:99px;text-decoration:none;font-size:13px}
.taal a{font-weight:700;text-decoration:none}.taal a.huidig{text-decoration:underline}
@media(max-width:900px){.raster{grid-template-columns:repeat(2,1fr);gap:10px}.pp{grid-template-columns:1fr;gap:20px}footer .wrap{grid-template-columns:1fr 1fr}
 .hero h1{font-size:28px}.hero{min-height:420px}nav.main{display:none;position:absolute;top:78px;left:0;right:0;background:#fff;flex-direction:column;align-items:flex-start;padding:14px 20px;border-bottom:1px solid var(--lijn)}nav.main.open{display:flex}
 #menuknop{display:block}header.top .wrap{gap:12px;height:64px}header.top .logo img{height:46px;width:46px}header.top .tools{margin-left:auto}.tools .land{display:none}.bar2 .soc{display:none}nav.main details>div{position:static;box-shadow:none;border:0}}
"""

JS = r"""
(function(){
var L=document.documentElement.lang,NL=L==='nl',P=NL?'/nl':'';
var API=window.REVALEUR_API,KEY='revaleur_cart_v1';
function get(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){return[]}}
function set(c){try{localStorage.setItem(KEY,JSON.stringify(c))}catch(e){}badge()}
function badge(){var n=get().length,b=document.querySelector('.cartlink b');if(b){b.textContent=n;b.style.display=n?'block':'none'}}
window.rvCart={get:get,set:set,add:function(p){var c=get();if(!c.some(function(x){return x.id===p.id}))c.push(p);set(c)},rm:function(id){set(get().filter(function(x){return x.id!==id}))}};
badge();
document.querySelectorAll('[data-add]').forEach(function(b){
 var p=JSON.parse(b.getAttribute('data-add'));
 function sync(){if(get().some(function(x){return x.id===p.id})){b.textContent=b.dataset.in;b.onclick=function(){location.href=P+'/cart'}}else{b.textContent=b.dataset.add_t}}
 b.dataset.add_t=b.textContent;sync();
 b.addEventListener('click',function(){if(!get().some(function(x){return x.id===p.id})){rvCart.add(p);sync();location.href=P+'/cart'}});
});
var m=document.getElementById('menuknop');if(m)m.onclick=function(){document.querySelector('nav.main').classList.toggle('open')};
var zk=document.getElementById('zoekknop');if(zk)zk.onclick=function(e){e.preventDefault();var z=document.getElementById('zoek');z.classList.toggle('aan');var i=z.querySelector('input');i.focus()};
document.querySelectorAll('.thumbs img').forEach(function(t){t.onclick=function(){document.querySelector('.groot img').src=t.dataset.groot;document.querySelectorAll('.thumbs img').forEach(function(x){x.classList.remove('aan')});t.classList.add('aan')}});
// collectie: sorteren en filteren op merk
var raster=document.getElementById('raster');
if(raster&&document.getElementById('sorteer')){
 var kaarten=[].slice.call(raster.children);
 function toepas(){var s=document.getElementById('sorteer').value,m=document.getElementById('merkfilter').value;
  var z=kaarten.filter(function(k){return !m||k.dataset.merk===m});
  z.sort(function(a,b){return s==='laag'?a.dataset.prijs-b.dataset.prijs:s==='hoog'?b.dataset.prijs-a.dataset.prijs:b.dataset.nr-a.dataset.nr});
  kaarten.forEach(function(k){k.style.display='none'});z.forEach(function(k){k.style.display='';raster.appendChild(k)});
  var t=document.getElementById('telling');if(t)t.textContent=z.length}
 document.getElementById('sorteer').onchange=toepas;document.getElementById('merkfilter').onchange=toepas;toepas();
}
// zoeken
var zi=document.getElementById('zoekveld');
if(zi){var idx=null;zi.addEventListener('focus',function(){if(!idx)fetch('/search-index.json').then(function(r){return r.json()}).then(function(d){idx=d})});
 zi.closest('form').addEventListener('submit',function(e){e.preventDefault();location.href=P+'/search?q='+encodeURIComponent(zi.value)});}
var sr=document.getElementById('zoekresultaat');
if(sr){var q=(new URLSearchParams(location.search).get('q')||'').toLowerCase().trim();document.getElementById('zoekterm').textContent=q;
 fetch('/search-index.json').then(function(r){return r.json()}).then(function(d){var w=q.split(/\s+/).filter(Boolean);
  var hit=d.filter(function(p){var s=(p.t+' '+p.m+' '+p.y).toLowerCase();return w.every(function(x){return s.indexOf(x)>-1})});
  sr.innerHTML=hit.length?hit.map(function(p){return '<a class="kaart" href="'+P+'/products/'+p.h+'"><div class="foto"><img loading="lazy" src="'+p.i+'" alt=""></div><div class="merk">'+p.m+'</div><div class="tit">'+p.t+'</div><div class="prijs">'+p.p+'</div></a>'}).join(''):'<p>'+sr.dataset.leeg+'</p>'});}
// winkelmand
var wm=document.getElementById('winkelmand');
if(wm){
 var fmt=function(x){var s=x.toFixed(2);return '€'+(NL?s.replace('.',','):s)};
 var land=document.getElementById('land');
 function ship(sub){var z=land.value;if(z==='NL'||z==='BE')return 0;if(sub>=100)return 0;return z==='EU'?3.95:4.95}
 function teken(){var c=get(),b=document.getElementById('mandbody');
  if(!c.length){wm.querySelector('.vol').style.display='none';wm.querySelector('.leeg').style.display='block';return}
  wm.querySelector('.vol').style.display='';wm.querySelector('.leeg').style.display='none';
  b.innerHTML=c.map(function(x){return '<tr><td><img src="'+x.img+'" alt=""></td><td><a href="'+P+'/products/'+x.h+'">'+x.t+'</a></td><td>'+fmt(x.p)+'</td><td><button class="knop rand" data-rm="'+x.id+'">'+wm.dataset.rm+'</button></td></tr>'}).join('');
  var sub=c.reduce(function(a,x){return a+x.p},0),sh=ship(sub);
  document.getElementById('sub').textContent=fmt(sub);document.getElementById('sh').textContent=sh?fmt(sh):wm.dataset.gratis;document.getElementById('tot').textContent=fmt(sub+sh);
  b.querySelectorAll('[data-rm]').forEach(function(k){k.onclick=function(){rvCart.rm(k.dataset.rm);teken()}})}
 land.onchange=teken;teken();
 document.getElementById('afrekenen').onclick=function(){var k=this,m=document.getElementById('fout');m.style.display='none';
  k.disabled=true;var o=k.textContent;k.textContent=wm.dataset.bezig;
  fetch(API+'/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:get().map(function(x){return x.id}),land:land.value,taal:NL?'nl':'en'})})
  .then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j}})})
  .then(function(r){if(r.ok&&r.j.url){location.href=r.j.url;return}
    if(r.j&&r.j.verkocht&&r.j.verkocht.length){set(get().filter(function(x){return r.j.verkocht.indexOf(x.id)<0}));teken();m.textContent=wm.dataset.verkocht}else{m.textContent=wm.dataset.storing}
    m.style.display='block';k.disabled=false;k.textContent=o})
  .catch(function(){m.textContent=wm.dataset.storing;m.style.display='block';k.disabled=false;k.textContent=o})};
}
if(document.getElementById('bedankt'))try{localStorage.removeItem(KEY)}catch(e){}
})();
"""


def head(titel, omschr, pad, taal, kanon_en=None, kanon_nl=None, og=None, extra=""):
    nl = DOMEIN + "/nl" + (pad if pad != "/" else "")
    en = DOMEIN + (pad if pad != "/" else "/")
    t = Tx(taal)
    kanon = nl if taal == "nl" else en
    hreflang = ""
    if kanon_en is not False:
        hreflang = (f'<link rel="alternate" hreflang="en" href="{en}">'
                    f'<link rel="alternate" hreflang="nl" href="{nl}">'
                    f'<link rel="alternate" hreflang="x-default" href="{en}">')
    ogimg = f'<meta property="og:image" content="{esc(og)}">' if og else ""
    return (f'<!doctype html><html lang="{taal}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(titel)}</title><meta name="description" content="{esc(omschr)}">'
            f'<link rel="canonical" href="{kanon}">{hreflang}'
            f'<meta property="og:title" content="{esc(titel)}"><meta property="og:description" content="{esc(omschr)}">{ogimg}'
            f'<link rel="icon" href="/assets/logo.jpg"><link rel="preload" href="/assets/m500.woff2" as="font" type="font/woff2" crossorigin>'
            f'<style>{CSS}</style>{extra}</head>')


def kop(taal, pad, cat):
    t = Tx(taal)
    p = pre(taal)
    merken = [c for c in cat["collecties"] if c["handle"] in ("ralph-lauren", "suitsupply", "profuomo", "massimo-dutti", "stone-island")]
    cats = [c for c in cat["collecties"] if c["handle"] in ("hoodies", "outerwear", "shoes", "chinos", "suits-blazers", "tops-shirts",
                                                             "trousers", "shorts", "activewear", "jumpers-sweaters-1")]
    nm = {"nl": {"hoodies": "Hoodies", "outerwear": "Jassen", "shoes": "Schoenen", "chinos": "Chino's", "suits-blazers": "Pakken & blazers",
                 "tops-shirts": "Tops & overhemden", "trousers": "Broeken", "shorts": "Shorts", "activewear": "Sportkleding",
                 "jumpers-sweaters-1": "Truien"}}
    def naam(c):
        return nm["nl"].get(c["handle"], c["titel"]) if taal == "nl" else c["titel"]
    cm = "".join(f'<a href="{p}/collections/{c["handle"]}">{esc(naam(c))}</a>' for c in cats)
    mm = "".join(f'<a href="{p}/collections/{c["handle"]}">{esc(c["titel"])}</a>' for c in merken)
    anders = ("/" + pad.lstrip("/")) if pad != "/" else "/"
    en_href, nl_href = anders, "/nl" + (anders if anders != "/" else "")
    return (f'<div class="bar1">{esc(t("€100 bonus mystery 3-for-1 flash deal — ends Sunday")) if taal=="nl" else "€100 BONUS MYSTERY 3-FOR-1 FLASH DEAL — ENDS SUNDAY"}</div>'
            f'<div class="bar2"><span class="soc"><a href="https://www.instagram.com/revaleur_official/">IG</a><a href="https://www.youtube.com/@revaleur">YT</a><a href="https://www.tiktok.com/@revaleur">TT</a><a href="https://nl.pinterest.com/revaleur/">PI</a></span>'
            f'<span>{esc(t("715+ happy customers"))}</span></div>'
            f'<div class="zoek" id="zoek"><div class="wrap"><form action="{p}/search" role="search"><input class="veld" id="zoekveld" name="q" placeholder="{esc(t("Search"))}" style="width:100%" autocomplete="off"></form></div></div>'
            f'<header class="top"><div class="wrap"><button id="menuknop" aria-label="Menu">☰</button>'
            f'<a class="logo" href="{p or "/"}"><img src="/assets/logo.jpg" alt="Revaleur" width="62" height="62"></a>'
            f'<nav class="main"><details><summary>{esc(t("Categories"))} ▾</summary><div><a href="{p}/collections/all">{esc(t("All"))}</a>{cm}</div></details>'
            f'<details><summary>{esc(t("Brands"))} ▾</summary><div>{mm}</div></details>'
            f'<a href="{p}/blogs/news">{esc(t("Blog"))}</a><a href="{p}/pages/our-mission">{esc(t("Our mission"))}</a></nav>'
            f'<div class="tools"><span class="taal"><a href="{en_href}" class="{"huidig" if taal=="en" else ""}">EN</a> · <a href="{nl_href}" class="{"huidig" if taal=="nl" else ""}">NL</a></span>'
            f'<a href="#" id="zoekknop" aria-label="{esc(t("Search"))}">⌕</a>'
            f'<a class="cartlink" href="{p}/cart" aria-label="{esc(t("Cart"))}">🛍<b style="display:none">0</b></a></div></div></header>')


def voet(taal):
    t = Tx(taal)
    p = pre(taal)
    return (f'<footer><div class="wrap"><div><strong>REVALEUR</strong><p>{esc(t("Quick delivery worldwide"))} · {esc(t("14 days return policy"))} · {esc(t("Professionally reviewed"))}</p>'
            f'<p>{esc(t("Secure checkout via Stripe: iDEAL and cards"))}</p></div>'
            f'<div><strong>{esc(t("Policies"))}</strong><a href="{p}/policies/shipping-policy">{esc(t("Shipping policy"))}</a><a href="{p}/policies/refund-policy">{esc(t("Refund policy"))}</a>'
            f'<a href="{p}/policies/terms-of-service">{esc(t("Terms of service"))}</a><a href="{p}/policies/privacy-policy">{esc(t("Privacy policy"))}</a></div>'
            f'<div><strong>Revaleur</strong><a href="{p}/pages/our-mission">{esc(t("Our mission"))}</a><a href="{p}/blogs/news">{esc(t("Blog"))}</a><a href="{p}/pages/size-chart-men">{esc(t("See size chart & measurements"))}</a></div>'
            f'<div><strong>{esc(t("Contact us"))}</strong><a href="{p}/pages/contact-us">{esc(t("Contact us"))}</a><a href="mailto:{MAIL}">{MAIL}</a></div>'
            f'<div class="klein">© {date.today().year} Revaleur · Kleine Melanen 5, 4614RG Bergen op Zoom</div></div></footer>'
            f'<script>window.REVALEUR_API="{API}";</script><script>{JS}</script></body></html>')


def pagina(taal, pad, cat, titel, omschr, body, og=None, extra="", hreflang=True):
    return (head(titel, omschr, pad, taal, None if hreflang else False, og=og, extra=extra) + "<body>" + kop(taal, pad, cat) + body + voet(taal) + "")


# ---------------------------------------------------------------- onderdelen
def kaart(p, taal, nr):
    t = Tx(taal)
    pr = pre(taal)
    foto = p["fotos"][0]["src"] if p["fotos"] else ""
    koop = f'<span class="nu">{euro(p["prijs"], taal)}</span>'
    if p["retail"] and p["retail"] > p["prijs"]:
        koop = f'<s>{euro(p["retail"], taal)}</s>' + koop
    badge = "" if p["beschikbaar"] else f'<span class="badge uit">{esc(t("Sold"))}</span>'
    return (f'<a class="kaart" href="{pr}/products/{p["handle"]}" data-merk="{esc(p["merk"])}" data-prijs="{p["prijs"]}" data-nr="{nr}">'
            f'<div class="foto"><img loading="lazy" src="{esc(foto)}&width=600" alt="{esc(p["titel"])}" width="600" height="800">{badge}</div>'
            f'<div class="merk">{esc(p["merk"])}</div><div class="tit">{esc(p["titel"])}</div><div class="prijs">{koop}</div></a>')


def _foto(src, b):
    return src + ("&" if "?" in src else "?") + f"width={b}"


def productpagina(p, taal, cat):
    t = Tx(taal)
    pr = pre(taal)
    f = p["fotos"]
    thumbs = "".join(f'<img class="{"aan" if i == 0 else ""}" src="{esc(_foto(x["src"], 160))}" data-groot="{esc(_foto(x["src"], 1200))}" alt="" loading="lazy" width="160" height="160">'
                     for i, x in enumerate(f))
    groot = f'<img src="{esc(_foto(f[0]["src"], 1200))}" alt="{esc(p["titel"])}" width="1200" height="1200">' if f else ""
    retail = f'<s>{esc(t("Retail"))}: {euro(p["retail"], taal)}</s>' if p["retail"] and p["retail"] > p["prijs"] else ""
    data = json.dumps({"id": p["id"], "h": p["handle"], "t": p["titel"], "p": p["prijs"], "img": _foto(f[0]["src"], 160) if f else ""})
    if p["beschikbaar"]:
        knop = f'<button class="knop" data-in="{esc(t("In your cart"))}" data-add=\'{esc(data)}\'>{esc(t("Add to cart"))}</button>'
        voorraad = (f'<div class="punten"><li style="text-transform:uppercase">{esc(t("Hurry up: only 1 available"))}</li></div>')
        unik = f'<div class="unik">● {esc(t("Unique item — only 1 available. Once it\'s gone, it\'s gone forever."))}</div>'
    else:
        knop = f'<button class="knop" disabled>{esc(t("Sold"))}</button>'
        voorraad = unik = ""
    ld = {"@context": "https://schema.org", "@type": "Product", "name": p["titel"], "sku": p["sku"],
          "image": [x["src"] for x in f[:6]], "description": p["tekst"][:500], "brand": {"@type": "Brand", "name": p["merk"]},
          "offers": {"@type": "Offer", "url": f'{DOMEIN}{pr}/products/{p["handle"]}', "priceCurrency": "EUR", "price": f'{p["prijs"]:.2f}',
                     "itemCondition": "https://schema.org/UsedCondition",
                     "availability": "https://schema.org/InStock" if p["beschikbaar"] else "https://schema.org/SoldOut"}}
    body = (f'<div class="wrap"><div class="pp"><div class="galerij"><div class="groot">{groot}</div><div class="thumbs">{thumbs}</div></div>'
            f'<div class="info"><div style="font-size:12px;font-weight:700;letter-spacing:.08em">715+ ★★★★★ REVIEWS</div>'
            f'<h1>{esc(p["titel"])}</h1><div class="prijsregel">{retail} {euro(p["prijs"], taal)}</div>'
            f'<div class="groen">✓ {esc(t("Free shipping to NL & BE"))}</div>{voorraad}'
            f'<ul class="punten"><li>{esc(t("100% authentic or 200% money-back"))}</li><li>{esc(t("Not satisfied? Easy returns"))}</li></ul>{unik}'
            f'{knop}<div style="font-size:12px;margin:8px 0">✓ {esc(t("Verified Authentic & Cleaned"))}</div>'
            f'<p><a href="{pr}/pages/size-chart-men">📏 {esc(t("See size chart & measurements"))}</a></p>'
            f'<div class="beschr"><details open><summary>{esc(t("Description"))}</summary><div>{p["beschrijving"]}</div></details>'
            f'<details><summary>{esc(t("Shipping"))}</summary><p>{esc(t("Free shipping to NL & BE"))} · EU €3,95 · International €4,95 · {esc(t("Free from €100"))}</p></details>'
            f'<details><summary>{esc(t("Returns"))}</summary><p>{esc(t("14 days return policy"))}. <a href="{pr}/policies/refund-policy">{esc(t("Refund policy"))}</a></p></details></div>'
            f'</div></div></div>')
    return pagina(taal, f'/products/{p["handle"]}', cat, f'{p["titel"]} – Revaleur', p["tekst"][:155], body,
                  og=f[0]["src"] if f else None, extra=f'<script type="application/ld+json">{json.dumps(ld)}</script>')


def collectiepagina(c, prods, taal, cat):
    t = Tx(taal)
    pr = pre(taal)
    merken = sorted({p["merk"] for p in prods})
    opties = f'<option value="">{esc(t("Brand"))}: {esc(t("All"))}</option>' + "".join(f'<option>{esc(m)}</option>' for m in merken)
    kaarten = "".join(kaart(p, taal, i) for i, p in enumerate(reversed(prods)))
    body = (f'<div class="wrap"><h1>{esc(c["titel"])}</h1><div class="filters"><select id="merkfilter" class="veld">{opties}</select>'
            f'<select id="sorteer" class="veld"><option value="nieuw">{esc(t("Newest"))}</option><option value="laag">{esc(t("Price: low to high"))}</option><option value="hoog">{esc(t("Price: high to low"))}</option></select>'
            f'<span><b id="telling">{len(prods)}</b> {esc(t("products"))}</span></div><div class="raster" id="raster">{kaarten}</div></div>')
    return pagina(taal, f'/collections/{c["handle"]}', cat, f'{c["titel"]} | Revaleur', f'{c["titel"]} – authentic vintage designer clothing', body)


def home(cat, taal):
    t = Tx(taal)
    pr = pre(taal)
    nieuw = sorted([p for p in cat["producten"] if p["beschikbaar"]], key=lambda p: p["gemaakt"], reverse=True)[:8]
    hero = nieuw[0]["fotos"][0]["src"] if nieuw else ""
    body = (f'<section class="hero"><img src="{esc(_foto(hero, 1600))}" alt=""><div><h1>{esc(t("Vintage designer fashion for a timeless wardrobe"))}</h1>'
            f'<p>{esc(t("Your #1 in vintage designer fashion"))}</p><a class="knop wit" href="{pr}/collections/latest-products-1">{esc(t("Shop the latest products"))}</a></div></section>'
            f'<div class="wrap"><h2 style="text-align:center;margin-top:36px">{esc(t("Our latest products, live now"))}</h2>'
            f'<div class="raster">{"".join(kaart(p, taal, i) for i, p in enumerate(nieuw))}</div></div>')
    titel = "Revaleur | Authentieke Vintage Designer Kleding" if taal == "nl" else "Revaleur | Authentic Vintage Designer Clothing"
    return pagina(taal, "/", cat, titel, t("Vintage designer fashion for a timeless wardrobe"), body)


def tekstpagina(titel, tekst, taal, cat, pad, omschr=""):
    body = f'<div class="inhoud"><h1>{esc(titel)}</h1>{tekst_naar_html(tekst)}</div>'
    return pagina(taal, pad, cat, f"{titel} – Revaleur", omschr or tekst[:150], body)


def winkelmand(taal, cat):
    t = Tx(taal)
    pr = pre(taal)
    attrs = (f'data-rm="{esc(t("Remove"))}" data-gratis="{esc(t("Free"))}" data-bezig="{esc(t("Checking…"))}" '
             f'data-verkocht="{esc(t("Sorry, this item was just sold."))}" '
             f'data-storing="{esc(t("Checkout is temporarily unavailable. Your cart is saved, please try again in a few minutes."))}"')
    body = (f'<div class="wrap winkelmand" id="winkelmand" {attrs}><h1>{esc(t("Your cart"))}</h1>'
            f'<div class="leeg" style="display:none"><p>{esc(t("Your cart is empty"))}</p><a class="knop" href="{pr}/collections/all">{esc(t("Continue shopping"))}</a></div>'
            f'<div class="vol"><table><tbody id="mandbody"></tbody></table>'
            f'<p><label>{esc(t("Country"))} <select id="land" class="veld"><option value="NL">{esc(t("Netherlands"))}</option><option value="BE">{esc(t("Belgium"))}</option>'
            f'<option value="EU">{esc(t("Rest of Europe"))}</option><option value="INT">{esc(t("Outside Europe"))}</option></select></label></p>'
            f'<p>{esc(t("Subtotal"))}: <b id="sub"></b><br>{esc(t("Shipping costs"))}: <b id="sh"></b><br>{esc(t("Total"))}: <b id="tot"></b></p>'
            f'<div class="melding" id="fout" style="display:none"></div>'
            f'<button class="knop" id="afrekenen">{esc(t("Checkout"))}</button><p style="font-size:12px">{esc(t("Secure checkout via Stripe: iDEAL and cards"))}</p></div></div>')
    return pagina(taal, "/cart", cat, f'{t("Your cart")} – Revaleur', "", body, hreflang=False)


def zoekpagina(taal, cat):
    t = Tx(taal)
    body = (f'<div class="wrap"><h1>{esc(t("Search results"))}: <span id="zoekterm"></span></h1>'
            f'<div class="raster" id="zoekresultaat" data-leeg="{esc(t("Nothing found"))}"></div></div>')
    return pagina(taal, "/search", cat, f'{t("Search results")} – Revaleur', "", body, hreflang=False)


def bedankt(taal, cat):
    t = Tx(taal)
    body = (f'<div class="inhoud" id="bedankt"><h1>{esc(t("Thank you for your order"))}</h1>'
            f'<p>{esc(t("We have sent a confirmation to your email. You will get a tracking link when your order ships."))}</p>'
            f'<a class="knop" href="{pre(taal) or "/"}">{esc(t("Back to the shop"))}</a></div>')
    return pagina(taal, "/bedankt", cat, f'{t("Thank you for your order")} – Revaleur', "", body, hreflang=False)


def blogindex(taal, cat):
    t = Tx(taal)
    pr = pre(taal)
    li = "".join(f'<li style="margin:14px 0"><a href="{pr}/blogs/news/{a["handle"]}"><b>{esc(a["titel"])}</b></a><br><small>{a["datum"]}</small></li>'
                 for a in sorted(cat["artikelen"], key=lambda a: a["datum"], reverse=True))
    return pagina(taal, "/blogs/news", cat, "News – Revaleur", "Revaleur news", f'<div class="inhoud"><h1>{esc(t("News"))}</h1><ul style="list-style:none;padding:0">{li}</ul></div>')


def artikel(a, taal, cat):
    return pagina(taal, f'/blogs/news/{a["handle"]}', cat, f'{a["titel"]} – Revaleur', _kort(a["html"]),
                  f'<div class="inhoud"><h1>{esc(a["titel"])}</h1><small>{a["datum"]}</small>{a["html"]}</div>')


def _kort(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))[:155]


def faq_pagina(taal, cat):
    t = Tx(taal)
    tekst = lees_beleid("pages_contact-us")
    vorm = (f'<form action="mailto:{MAIL}" method="post" enctype="text/plain" style="display:grid;gap:10px;max-width:520px">'
            f'<input class="veld" name="naam" placeholder="{esc(t("Name"))}"><input class="veld" type="email" name="email" placeholder="{esc(t("Email"))}" required>'
            f'<textarea class="veld" name="bericht" rows="5" placeholder="{esc(t("Comment"))}"></textarea><button class="knop">{esc(t("Send"))}</button></form>')
    body = f'<div class="inhoud"><h1>{esc(t("Contact us"))}</h1><p>{MAIL}</p>{vorm}<hr style="margin:30px 0">{tekst_naar_html(tekst.split("Frequently Asked Questions",1)[-1])}</div>'
    return pagina(taal, "/pages/contact-us", cat, f'{t("Contact us")} – Revaleur', "", body)


# ---------------------------------------------------------------- hoofd
def schrijf(dist, pad, inhoud):
    f = dist / pad.lstrip("/")
    if pad.endswith("/") or not Path(pad).suffix:
        f = f / "index.html" if not pad.endswith(".html") else f
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(inhoud, encoding="utf-8")


def bouw(dist: Path = SITE / "dist"):
    cat = json.loads((SITE / "data" / "catalogus.json").read_text())
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    shutil.copytree(SITE / "assets", dist / "assets")
    by_id = {p["id"]: p for p in cat["producten"]}
    urls = []
    for taal in ("en", "nl"):
        pr = pre(taal)
        schrijf(dist, f"{pr}/", home(cat, taal))
        urls.append(f"{pr}/")
        alle = {"handle": "all", "titel": "All products" if taal == "en" else "Alle producten", "producten": [p["id"] for p in cat["producten"]]}
        for c in cat["collecties"] + ([] if any(c["handle"] == "all" for c in cat["collecties"]) else [alle]):
            leden = [by_id[i] for i in c["producten"] if i in by_id]
            if c["handle"] == "all":
                leden = cat["producten"]
            schrijf(dist, f"{pr}/collections/{c['handle']}/", collectiepagina(c, leden, taal, cat))
            urls.append(f"{pr}/collections/{c['handle']}")
        for p in cat["producten"]:
            schrijf(dist, f"{pr}/products/{p['handle']}/", productpagina(p, taal, cat))
            urls.append(f"{pr}/products/{p['handle']}")
        T_ = Tx(taal)
        for naam, titel in (("shipping-policy", "Shipping policy"), ("refund-policy", "Refund policy"),
                            ("terms-of-service", "Terms of service"), ("privacy-policy", "Privacy policy")):
            txt = PAGINA_NL.get(naam, "") if taal == "nl" else ""
            txt = txt or lees_beleid(f"policies_{naam}") or lees_beleid(f"pages_{naam}") or titel
            schrijf(dist, f"{pr}/policies/{naam}/", tekstpagina(T_(titel), txt, taal, cat, f"/policies/{naam}"))
            urls.append(f"{pr}/policies/{naam}")
        mis = PAGINA_NL.get("our-mission", "") if taal == "nl" else ""
        schrijf(dist, f"{pr}/pages/our-mission/", tekstpagina(T_("Our mission"), mis or lees_beleid("pages_our-mission"), taal, cat, "/pages/our-mission"))
        schrijf(dist, f"{pr}/pages/contact-us/", faq_pagina(taal, cat))
        maat = lees_beleid("pages_size-chart-men")
        schrijf(dist, f"{pr}/pages/size-chart-men/", tekstpagina(T_("See size chart & measurements"), PAGINA_NL.get("size-chart-men", "") if taal == "nl" and PAGINA_NL.get("size-chart-men") else (maat or "Measurements are in the product pictures."), taal, cat, "/pages/size-chart-men"))
        urls += [f"{pr}/pages/our-mission", f"{pr}/pages/contact-us", f"{pr}/pages/size-chart-men"]
        schrijf(dist, f"{pr}/blogs/news/", blogindex(taal, cat))
        urls.append(f"{pr}/blogs/news")
        for a in cat["artikelen"]:
            schrijf(dist, f"{pr}/blogs/news/{a['handle']}/", artikel(a, taal, cat))
            urls.append(f"{pr}/blogs/news/{a['handle']}")
        schrijf(dist, f"{pr}/cart/", winkelmand(taal, cat))
        schrijf(dist, f"{pr}/search/", zoekpagina(taal, cat))
        schrijf(dist, f"{pr}/bedankt/", bedankt(taal, cat))
    # zoekindex, sitemap, robots, headers
    idx = [{"h": p["handle"], "t": p["titel"], "m": p["merk"], "y": p["type"], "i": _foto(p["fotos"][0]["src"], 600) if p["fotos"] else "",
            "p": euro(p["prijs"], "en")} for p in cat["producten"] if p["beschikbaar"]]
    (dist / "search-index.json").write_text(json.dumps(idx, ensure_ascii=False))
    sm = "".join(f"<url><loc>{DOMEIN}{u if u != '/' else '/'}</loc></url>" for u in urls)
    (dist / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    (dist / "robots.txt").write_text(f"User-agent: *\nDisallow: /cart\nDisallow: /nl/cart\nDisallow: /search\nDisallow: /nl/search\nDisallow: /bedankt\nSitemap: {DOMEIN}/sitemap.xml\n")
    (dist / "_headers").write_text("/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    (dist / "_redirects").write_text("/collections/*/products/* /products/:splat 301\n/nl/collections/*/products/* /nl/products/:splat 301\n")
    return len(urls)


if __name__ == "__main__":
    n = bouw(Path(sys.argv[1]) if len(sys.argv) > 1 else SITE / "dist")
    print(n, "pagina's gebouwd")
