"""De openbare kostenrekenaar (28-10-2026).

Rekenmodel: frontend/assets/kostenrekenaar.js, getoetst met node tegen bedragen
die met de hand zijn uitgerekend uit de tarieven op de helppagina's van eBay.nl
(particulier id 4822, zakelijk id 4809). Pagina's: tweetalig, met hreflang,
canonical, de gedeelde kopregel en voettekst, in de sitemap en met geldige
JSON-LD.
"""
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

JS = REPO / "frontend" / "assets" / "kostenrekenaar.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def _node(code: str):
    uit = subprocess.run(
        ["node", "-e", f"const K=require({json.dumps(str(JS))});\n{code}"],
        capture_output=True, text=True, timeout=30,
    )
    assert uit.returncode == 0, uit.stderr
    return json.loads(uit.stdout)


@node
def test_ebay_kosten_particulier_en_zakelijk_kloppen_met_de_tarieven():
    g = _node(textwrap.dedent("""
        const p={verkoper:'particulier'}, z=(r)=>({verkoper:'zakelijk',rubriek:r});
        console.log(JSON.stringify({
          p100: K.ebayKosten(100,p),           // 11 + 0,35 + 0,42
          p5: K.ebayKosten(5,p),               // 0,55 + 0,05 + 0,021
          p2090: K.ebayKosten(2090,p),         // 218,9 + 2 + 0,35 + 8,778
          z100: K.ebayKosten(100,z('standaard')),   // 11 + 0,45 + 0,35
          z1090: K.ebayKosten(1090,z('standaard')), // 108,9 + 2 + 0,45 + 3,815
          z10: K.ebayKosten(10,z('standaard')),     // 1,1 + 0,35 + 0,035
          zsier: K.ebayKosten(500,z('sieraden')),   // 44 + 2 + 0,45 + 1,75
          zfoto: K.ebayKosten(400,z('foto')),       // 19,5 + 2 + 0,45 + 1,4
        }));
    """))
    verwacht = {"p100": 11.77, "p5": 0.621, "p2090": 230.028, "z100": 11.80, "z1090": 115.165,
                "z10": 1.485, "zsier": 48.2, "zfoto": 23.35}
    for sleutel, waarde in verwacht.items():
        assert g[sleutel] == pytest.approx(waarde, abs=1e-6), sleutel


@node
def test_vraagprijs_is_de_laagste_cent_die_de_winst_haalt():
    g = _node(textwrap.dedent("""
        const out=[];
        for (const o of [{verkoper:'particulier'},{verkoper:'zakelijk',rubriek:'standaard'},
                         {verkoper:'zakelijk',rubriek:'foto'},{verkoper:'particulier',verzend:6.5}]) {
          for (const [ink,w] of [[20,25],[0,10],[3.5,0.5],[400,150],[2500,300]]) {
            const p=K.vraagprijs('ebay',ink,w,o);
            out.push({p, boven:K.winstBij('ebay',p,ink,o)-w, onder:K.winstBij('ebay',p-0.01,ink,o)-w});
          }
        }
        console.log(JSON.stringify(out));
    """))
    for r in g:
        assert r["boven"] >= -1e-9, r      # haalt de winst
        assert r["onder"] < 0, r           # een cent lager haalt hem niet


@node
def test_gratis_kanalen_vragen_precies_inkoop_plus_winst():
    g = _node("console.log(JSON.stringify(['marktplaats','2dehands','vinted'].map(k=>K.vraagprijs(k,20,25,{}))))")
    assert g == [45, 45, 45]


@node
def test_ebay_is_duurder_dan_de_gratis_kanalen_en_rekent_verzendkosten_mee():
    g = _node(textwrap.dedent("""
        const a=K.vraagprijs('ebay',20,25,{verkoper:'particulier'});
        const b=K.vraagprijs('ebay',20,25,{verkoper:'particulier',verzend:10});
        console.log(JSON.stringify({a,b}));
    """))
    assert g["a"] > 45
    assert g["b"] > g["a"]   # commissie ook over de verzendkosten


@node
def test_oude_dashboardwaarde_week_af_van_de_officiele_tarieven():
    """Voor-en-na: het dashboard rekent nog 13,25% + 0,35 voor eBay. Voor een
    particulier die 45 netto wil houden is dat ruim een euro te hoog."""
    g = _node("console.log(JSON.stringify(K.vraagprijs('ebay',20,25,{verkoper:'particulier'})))")
    oud = (45 + 0.35) / (1 - 0.1325)
    assert oud - g > 1.0


@node
@pytest.mark.parametrize("tekst,verwacht", [
    ("1.360", 1360), ("1.360,50", 1360.5), ("1,360.50", 1360.5), ("12,5", 12.5), ("12.5", 12.5),
    ("€ 20,00", 20), ("1.36", 1.36), ("1,360", 1360), ("0,99", 0.99), ("20", 20),
])
def test_bedragen_worden_goed_gelezen(tekst, verwacht):
    assert _node(f"console.log(JSON.stringify(K.leesBedrag({json.dumps(tekst)})))") == pytest.approx(verwacht)


@node
@pytest.mark.parametrize("tekst", ["abc", "", "12,5,5x", "--3"])
def test_onzin_is_geen_bedrag(tekst):
    assert _node(f"console.log(JSON.stringify(Number.isNaN(K.leesBedrag({json.dumps(tekst)}))))") is True


# ── Pagina's ──────────────────────────────────────────────────────────────

from backend.site_chrome import met_site_chrome  # noqa: E402

PAGINAS = [("fee-calculator.html", "en", "/fee-calculator", "/nl/kostenrekenaar"),
           ("kostenrekenaar.html", "nl", "/nl/kostenrekenaar", "/fee-calculator")]


@pytest.mark.parametrize("bestand,taal,pad,andere", PAGINAS)
def test_pagina_heeft_kop_voet_canonical_en_hreflang(bestand, taal, pad, andere):
    bron = (REPO / "frontend" / bestand).read_text(encoding="utf-8")
    assert f'<html lang="{taal}">' in bron
    assert f'rel="canonical" href="https://omnivaleur.com{pad}"' in bron
    assert f'hreflang="x-default" href="https://omnivaleur.com/fee-calculator"' in bron
    assert f'hreflang="{"nl" if taal == "en" else "en"}" href="https://omnivaleur.com{andere}"' in bron
    assert not re.search(r"<nav[ >]", bron) and "<footer" not in bron
    html = met_site_chrome(bestand, taal, pad).body.decode("utf-8")
    assert html.count('<nav class="site-nav">') == 1 and html.count('<footer class="site-footer">') == 1
    assert "<!--site-" not in html
    assert "/assets/kostenrekenaar.js" in html
    assert html.count("</head>") == 1


@pytest.mark.parametrize("bestand,taal,pad,andere", PAGINAS)
def test_json_ld_is_geldig_en_bevat_faq_breadcrumb_en_app(bestand, taal, pad, andere):
    bron = (REPO / "frontend" / bestand).read_text(encoding="utf-8")
    blok = re.search(r'<script type="application/ld\+json">(.*?)</script>', bron, re.S).group(1)
    types = {n["@type"] for n in json.loads(blok)["@graph"]}
    assert types == {"WebApplication", "BreadcrumbList", "FAQPage"}


@pytest.mark.parametrize("bestand,taal,pad,andere", PAGINAS)
def test_alle_formulier_ids_die_het_script_gebruikt_bestaan(bestand, taal, pad, andere):
    bron = (REPO / "frontend" / bestand).read_text(encoding="utf-8")
    ids = set(re.findall(r"""el\('([a-z-]+)'\)|veld\('([a-z-]+)'\)|\['([a-z-]+)'""", JS.read_text(encoding="utf-8")))
    gebruikt = {i for tpl in ids for i in tpl if i.startswith("kr-")}
    assert {"kr-inkoop", "kr-winst", "kr-prijs", "kr-verzend", "kr-verkoper", "kr-rubriek", "kr-resultaten", "kr-rubriek-rij"} <= gebruikt
    for i in gebruikt:
        assert f'id="{i}"' in bron, f"{bestand} mist #{i}"


def test_sitemap_footer_en_routes():
    from backend.api.content import STATIC_SITEMAP_URLS
    paden = {p for p, *_ in STATIC_SITEMAP_URLS}
    assert {"/fee-calculator", "/nl/kostenrekenaar"} <= paden
    footer = (REPO / "frontend" / "templates" / "_footer.html").read_text(encoding="utf-8")
    assert "/nl/kostenrekenaar" in footer and "/fee-calculator" in footer
    main = (REPO / "backend" / "main.py").read_text(encoding="utf-8")
    assert '"/fee-calculator"' in main and '"/nl/kostenrekenaar"' in main


@node
def test_dashboard_rekent_ebay_met_hetzelfde_tarief_als_de_openbare_rekenaar():
    """Voor-en-na (28-10-2026): het dashboard had 13,25% + 0,35, de officiele
    zakelijke tarieven zijn 11% + 0,35% + 0,45 per bestelling."""
    app = (REPO / "frontend" / "app.html").read_text(encoding="utf-8")
    m = re.search(r"key: 'ebay',\s+label: 'eBay',\s+commission: ([0-9.]+), fixed: ([0-9.]+)", app)
    assert m, "eBay-regel van de margecalculator niet gevonden"
    commissie, vast = float(m.group(1)), float(m.group(2))
    for nodig in (45, 120, 300):
        dashboard = (nodig + vast) / (1 - commissie)
        model = _node(f"console.log(JSON.stringify(K.vraagprijs('ebay',{nodig},0,{{verkoper:'zakelijk'}})))")
        assert dashboard == pytest.approx(model, abs=0.011), nodig
    assert "13.25" not in app
