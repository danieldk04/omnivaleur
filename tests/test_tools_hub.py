"""De gratis tools-hub (28-10-2026): /tools, /nl/tools en elke tool daaronder.

Wat hier bewaakt wordt:
- elke tool staat overal waar hij hoort (pagina's, sitemap, menu, footer, llms.txt);
- elke pagina heeft precies een kopregel en voettekst, canonical, hreflang en geldig schema,
  en het FAQ-schema is exact de zichtbare vragen;
- de formuliervelden die de scripts gebruiken bestaan op de pagina;
- de rekenregels (titel, DAC7, margeregeling, afprijsladder) kloppen met de bron, en de
  afprijsladder is gelijk aan die in het dashboard;
- de aanmelding voor de download: validatie, lokveld, tempolimiet, en een adres dat nooit
  verloren gaat als de database weigert;
- de spreadsheets hebben echte formules.
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

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import tools as tools_api  # noqa: E402
from backend.tools_data import HUB, TOOLS, sitemap_paden, tool_pad  # noqa: E402

ASSETS = REPO / "frontend" / "assets"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")
TALEN = ("en", "nl")

# Velden die het script van elke tool nodig heeft.
VELDEN = {
    "kostenrekenaar": ["kr-inkoop", "kr-winst", "kr-prijs", "kr-verzend", "kr-betaalverzoek", "kr-verkoper", "kr-rubriek", "kr-resultaten", "kr-rubriek-rij"],
    "titelchecker": ["tc-titel", "tc-teller", "tc-resultaten"],
    "dac7": [f"d7-{p}-{s}" for p in ("marktplaats", "2dehands", "vinted", "ebay", "anders") for s in ("n", "o", "n-fout", "o-fout")] + ["d7-resultaten"],
    "margeregeling": ["mr-inkoop", "mr-verkoop", "mr-inkoop-fout", "mr-verkoop-fout", "mr-resultaten"],
    "afprijsplanner": ["ap-prijs", "ap-dagen", "ap-inkoop", "ap-prijs-fout", "ap-dagen-fout", "ap-inkoop-fout", "ap-resultaten"],
    "belastingcheck": ["bc-herkomst", "bc-prijs", "bc-inkoop", "bc-omzet", "bc-kosten", "bc-inkoop-fout", "bc-omzet-fout", "bc-kosten-fout", "bc-resultaten"],
    "winstmarge": [f"wm-{x}" for x in ("inkoop", "verkoop", "kosten", "fee", "doelmarge", "doelopslag")] + [f"wm-{x}-fout" for x in ("inkoop", "verkoop", "kosten", "fee", "doelmarge", "doelopslag")] + ["wm-resultaten"],
    "advertentietekst": [f"at-{x}" for x in ("kanaal", "taal", "product", "merk", "model", "maat", "kleur", "staat", "afm", "extra", "gebreken", "levering", "resultaten")],
    "voorraadsheet": ["vs-form", "vs-email", "vs-website", "vs-toestemming", "vs-knop", "vs-melding"],
}


def _pagina(taal: str, tool):
    return tools_api._render(taal, tool=tool).body.decode("utf-8")


def _ld(html: str) -> dict:
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))


ALLE = [(taal, t) for t in TOOLS for taal in TALEN]


def test_elke_tool_heeft_een_script_formulier_en_beide_talen():
    assert {t["key"] for t in TOOLS} == set(VELDEN)
    for t in TOOLS:
        for taal in TALEN:
            assert (REPO / "frontend" / "templates" / "tools" / f"{t['key']}.{taal}.html").exists()
            assert t["slug"][taal] and t[taal]["naam"] and len(t[taal]["meta"]) <= 200
        for s in t["scripts"]:
            assert (ASSETS / s).exists(), s


@pytest.mark.parametrize("taal,tool", ALLE)
def test_toolpagina_heeft_kop_voet_canonical_hreflang_en_velden(taal, tool):
    html = _pagina(taal, tool)
    pad = tool_pad(tool, taal)
    assert f'<html lang="{taal}">' in html
    assert f'rel="canonical" href="https://omnivaleur.com{pad}"' in html
    assert f'hreflang="en" href="https://omnivaleur.com{tool_pad(tool, "en")}"' in html
    assert f'hreflang="nl" href="https://omnivaleur.com{tool_pad(tool, "nl")}"' in html
    assert f'hreflang="x-default" href="https://omnivaleur.com{tool_pad(tool, "en")}"' in html
    assert html.count('<nav class="site-nav">') == 1 and html.count('<footer class="site-footer">') == 1
    assert html.count("</head>") == 1 and html.count("<h1>") == 1
    for veld in VELDEN[tool["key"]]:
        assert f'id="{veld}"' in html, f"{tool['key']} {taal} mist #{veld}"
    for s in tool["scripts"]:
        assert f'src="/assets/{s}?v=' in html
    # taalwissel wijst naar dezelfde tool in de andere taal
    andere = tool_pad(tool, "en" if taal == "nl" else "nl")
    assert f'href="{andere}" hreflang=' in html


@pytest.mark.parametrize("taal,tool", ALLE)
def test_schema_is_geldig_en_faq_is_precies_de_zichtbare_tekst(taal, tool):
    html = _pagina(taal, tool)
    graaf = _ld(html)["@graph"]
    types = [n["@type"] for n in graaf]
    assert types[0] == ("WebPage" if tool["gated"] else "WebApplication")
    assert "BreadcrumbList" in types and "FAQPage" in types
    zichtbaar = re.findall(r"<details><summary>(.*?)</summary>", html)
    faq = next(n for n in graaf if n["@type"] == "FAQPage")["mainEntity"]
    assert len(faq) == len(zichtbaar) >= 3
    assert all(q["acceptedAnswer"]["text"] for q in faq)
    kruimels = next(n for n in graaf if n["@type"] == "BreadcrumbList")["itemListElement"]
    assert [k["position"] for k in kruimels] == [1, 2, 3]


@pytest.mark.parametrize("taal", TALEN)
def test_hub_toont_elke_tool_met_itemlist(taal):
    html = _pagina(taal, None)
    graaf = _ld(html)["@graph"]
    lijst = next(n for n in graaf if n["@type"] == "CollectionPage")["mainEntity"]["itemListElement"]
    assert [i["url"] for i in lijst] == [f"https://omnivaleur.com{tool_pad(t, taal)}" for t in TOOLS]
    for t in TOOLS:
        assert f'href="{tool_pad(t, taal)}"' in html
    assert html.count('<nav class="site-nav">') == 1 and html.count("<h1>") == 1
    assert f'rel="canonical" href="https://omnivaleur.com{HUB[taal]["pad"]}"' in html


def test_sitemap_menu_footer_en_llms_kennen_elke_tool():
    paden = {p for p, *_ in sitemap_paden()}
    from backend.api.content import STATIC_SITEMAP_URLS
    in_sitemap = {p for p, *_ in STATIC_SITEMAP_URLS}
    llms = (REPO / "frontend" / "llms.txt").read_text(encoding="utf-8")
    assert {"/tools", "/nl/tools"} <= paden <= in_sitemap
    for t in TOOLS:
        for taal in TALEN:
            assert tool_pad(t, taal) in paden and tool_pad(t, taal) in in_sitemap
        assert f"https://omnivaleur.com{tool_pad(t, 'en')}" in llms, f"llms.txt mist {t['key']}"
    assert "https://omnivaleur.com/tools" in llms
    nav = (REPO / "frontend" / "templates" / "_nav.html").read_text(encoding="utf-8")
    footer = (REPO / "frontend" / "templates" / "_footer.html").read_text(encoding="utf-8")
    assert "/nl/tools' if nl else '/tools'" in nav and "/nl/tools' if nl else '/tools'" in footer


def test_oude_kostenrekenaaradressen_sturen_door_en_onbekende_slug_is_404():
    app = FastAPI()
    app.include_router(tools_api.router)
    c = TestClient(app)
    r = c.get("/fee-calculator", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/tools/fee-calculator"
    r = c.get("/nl/kostenrekenaar", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/nl/tools/kostenrekenaar"
    assert c.get("/tools/bestaat-niet").status_code == 404
    assert c.get("/nl/tools/fee-calculator").status_code == 404   # slug van de andere taal
    assert c.get("/tools/fee-calculator").status_code == 200


# ── Rekenregels (node) ────────────────────────────────────────────────────

def _node(bestanden, code):
    voor = "".join(f"const {n}=require({json.dumps(str(ASSETS / 'tools' / b))});" for n, b in bestanden)
    uit = subprocess.run(["node", "-e", voor + "\n" + code], capture_output=True, text=True, timeout=30)
    assert uit.returncode == 0, uit.stderr
    return json.loads(uit.stdout)


@node
def test_titelchecker_telt_en_kapt_af_zoals_de_extensie():
    g = _node([("T", "titelchecker.js")], textwrap.dedent("""
        const lang='Burberry wollen jas heren maat 50 - Zwart - Vintage - Nieuwstaat met kaartjes';
        console.log(JSON.stringify({
          a: T.tel('Jas'), b: T.tel('Jas \\n  zwart'), c: T.tel('😀ab'),
          kap60: T.afkap(lang,60), kap30: T.afkap('Heel lange titel zonder streepjes erin hoor', 30),
          kort: T.afkap('kort',60), grenzen: T.KANALEN.map(k=>[k.key,k.max]),
          tel60: T.tel(T.afkap(lang,60)), tel30: T.tel(T.afkap('Heel lange titel zonder streepjes erin hoor', 30)),
        }));
    """))
    assert g["a"] == 3 and g["b"] == 9 and g["c"] == 3   # nieuwe regel (met omringende spaties) wordt een spatie, emoji telt als een teken
    assert g["kap60"] == "Burberry wollen jas heren maat 50 - Zwart - Vintage"   # hele " - "-stukken eraf
    assert g["kap30"] == "Heel lange titel zonder"       # anders op een heel woord
    assert g["kort"] == "kort"
    assert g["tel60"] <= 60 and g["tel30"] <= 30
    assert g["grenzen"] == [["marktplaats", 60], ["2dehands", 60], ["ebay", 80], ["facebook", 100]]


@node
def test_dac7_grens_is_30_verkopen_of_meer_dan_2000():
    g = _node([("D", "dac7.js")], textwrap.dedent("""
        console.log(JSON.stringify([
          D.beoordeel(null,null), D.beoordeel(0,0), D.beoordeel(29,1999), D.beoordeel(30,0), D.beoordeel(1,2000),
          D.beoordeel(1,2000.01), D.beoordeel(24,100), D.beoordeel(5,1600), D.beoordeel(5,1599.99), D.beoordeel(100,5),
        ]));
    """))
    assert g == [None, "onder", "dichtbij", "gemeld", "dichtbij", "gemeld", "dichtbij", "dichtbij", "onder", "gemeld"]


@node
def test_margeregeling_is_21_over_121_van_de_marge():
    g = _node([("M", "margeregeling.js")], textwrap.dedent("""
        console.log(JSON.stringify({ m: M.btwMarge(400,700), g: M.btwGewoon(700), verlies: M.btwMarge(700,400), nul: M.btwMarge(500,500), marge: M.marge(400,700) }));
    """))
    assert g["m"] == pytest.approx(300 * 21 / 121) and round(g["m"], 2) == 52.07
    assert g["g"] == pytest.approx(700 * 21 / 121) and round(g["g"], 2) == 121.49
    assert g["verlies"] == 0 and g["nul"] == 0 and g["marge"] == 300


@node
def test_afprijsplanner_gebruikt_dezelfde_ladder_als_het_dashboard():
    """De ladder en de afronding in app.html worden hier letterlijk uit het dashboard gehaald
    en tegen de openbare planner gelegd. Wijzigt iemand er een van, dan faalt deze proef."""
    app = (REPO / "frontend" / "app.html").read_text(encoding="utf-8")
    ladder = re.search(r"const STALE_LADDER = .*?;", app).group(0)
    pct = re.search(r"function stalePctFor\(days\) \{.*?\n\}", app, re.S).group(0)
    r99 = re.search(r"function round99\(v\) \{.*?\n\}", app, re.S).group(0)
    code = f"""
      {ladder}\n{pct}\n{r99}
      const A=require({json.dumps(str(ASSETS / 'tools' / 'afprijsplanner.js'))});
      const uit=[];
      for (const dagen of [0,29,30,59,60,89,90,179,180,400]) for (const prijs of [0.5,9.5,19.99,49,120.4,999]) {{
        const p=stalePctFor(dagen); const dash=p? round99(prijs*(1-p)) : null;
        const ons=A.advies(prijs,dagen,null);
        uit.push([dagen,prijs,dash,ons.voorstel,p,ons.pct]);
      }}
      console.log(JSON.stringify(uit));
    """
    for dagen, prijs, dash, ons, p_dash, p_ons in json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout):
        assert dash == ons and p_dash == p_ons, (dagen, prijs)


@node
def test_afprijsplanner_stelt_nooit_onder_de_inkoop_voor():
    g = _node([("A", "afprijsplanner.js")], textwrap.dedent("""
        console.log(JSON.stringify([A.advies(49,75,20), A.advies(49,75,45), A.advies(49,10,45), A.advies(49,200,39)]));
    """))
    assert g[0] == {"pct": 0.1, "voorstel": 43.99, "onderInkoop": False}
    assert g[1] == {"pct": 0.1, "voorstel": None, "onderInkoop": True}     # 43,99 ligt onder inkoop 45
    assert g[2] == {"pct": 0, "voorstel": None, "onderInkoop": False}
    assert g[3] == {"pct": 0.2, "voorstel": None, "onderInkoop": True}     # 38,99 onder 39


# ── Aanmelding ────────────────────────────────────────────────────────────

class _FakeTabel:
    def __init__(self, db): self.db = db
    def upsert(self, rij, on_conflict=None):
        if self.db.kapot: raise RuntimeError("relation tool_aanmeldingen does not exist")
        self.db.rijen.append((rij, on_conflict)); return self
    def execute(self): return self


class _FakeDb:
    def __init__(self, kapot=False): self.rijen, self.kapot = [], kapot
    def table(self, naam):
        assert naam == "tool_aanmeldingen"
        return _FakeTabel(self)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(tools_api.router)
    tools_api._per_ip.clear()
    tools_api._mail_per_ip.clear()
    tools_api._mail_per_adres.clear()
    tools_api._aanmeld_per_adres.clear()
    mails = []
    naar = []

    def stuur(onderwerp, tekst, **k):
        mails.append((onderwerp, tekst)); naar.append((k.get("to"), onderwerp, tekst)); return True
    monkeypatch.setattr(tools_api, "send_email", stuur)
    db = _FakeDb()
    monkeypatch.setattr(tools_api, "get_db", lambda: db)
    c = TestClient(app)
    c.db, c.mails, c.naar = db, mails, naar
    return c


def _post(c, **kw):
    body = {"email": "Anna@Voorbeeld.nl", "taal": "nl", "bron": "voorraadsheet", "toestemming": True, "website": ""}
    body.update(kw)
    return c.post("/api/tools/aanmelden", json=body)


def _link(client, taal="nl"):
    """De downloadlink uit de laatst verstuurde mail (relatief gemaakt voor de TestClient)."""
    m = re.search(r"https://omnivaleur\.com(/api/tools/download/\S+)", client.naar[-1][2])
    assert m, client.naar[-1][2]
    return m.group(1)


def test_aanmelding_mailt_de_spreadsheet_en_bewaart_het_adres_pas_bij_openen(client):
    r = _post(client)
    assert r.status_code == 200 and r.json() == {"ok": True, "verstuurd": True}      # geen downloadlink in het antwoord
    assert client.db.rijen == []                                                       # nog niets bewaard
    to, onderwerp, tekst = client.naar[0]
    assert to == "anna@voorbeeld.nl" and "spreadsheet" in onderwerp and "info@omnivaleur.com" in tekst
    assert "*" not in tekst and "—" not in tekst and "–" not in tekst
    d = client.get(_link(client))
    assert d.status_code == 200 and d.content[:2] == b"PK"                             # een xlsx is een zipbestand
    assert "voorraad-winst-spreadsheet-nl.xlsx" in d.headers["content-disposition"]
    assert client.db.rijen == [({"email": "anna@voorbeeld.nl", "taal": "nl", "bron": "voorraadsheet", "toestemming": True}, "email")]
    _post(client, email="b+tag@b.nl", taal="en")
    en = client.get(_link(client))                                                     # een + in het adres blijft heel
    assert en.status_code == 200 and "inventory-profit-spreadsheet-en.xlsx" in en.headers["content-disposition"]
    assert client.db.rijen[-1][0]["email"] == "b+tag@b.nl" and client.db.rijen[-1][0]["taal"] == "en"


def test_download_vraagt_een_geldig_token_voor_dat_adres(client):
    _post(client)
    url = _link(client)
    assert client.get(url).status_code == 200
    n = len(client.db.rijen)
    assert client.get(url.replace("anna%40voorbeeld.nl", "ander%40voorbeeld.nl")).status_code == 404
    assert client.get(re.sub(r"t=\w+", "t=" + "0" * 32, url)).status_code == 404
    assert client.get("/api/tools/download/voorraad-winst-nl").status_code == 404
    assert client.get("/api/tools/download/onbekend?e=a@b.nl&t=x").status_code == 404
    assert len(client.db.rijen) == n                                                   # een afgewezen link bewaart niets


def test_mail_die_niet_verstuurd_kan_worden_geeft_een_fout_en_bewaart_niets(client, monkeypatch):
    monkeypatch.setattr(tools_api, "send_email", lambda *a, **k: False)
    r = _post(client)
    assert r.status_code == 503 and client.db.rijen == []


def test_per_adres_hooguit_drie_aanvragen_per_dag(client):
    codes = [_post(client, taal="nl").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


@pytest.mark.parametrize("email", ["", "geen-adres", "a@b", "a b@c.nl", "@c.nl", "a@@c.nl"])
def test_ongeldig_adres_wordt_geweigerd(client, email):
    assert _post(client, email=email).status_code == 422
    assert client.db.rijen == []


def test_zonder_toestemming_geen_download_en_geen_opslag(client):
    r = _post(client, toestemming=False)
    assert r.status_code == 422 and r.json()["detail"] == "toestemming" and client.db.rijen == []


def test_lokveld_wordt_stil_genegeerd(client):
    r = _post(client, website="http://spam.example")
    assert r.status_code == 200 and client.db.rijen == [] and client.naar == []


def test_tempolimiet_per_ip(client):
    codes = [_post(client, email=f"m{i}@voorbeeld.nl").status_code for i in range(tools_api.MAX_PER_UUR + 2)]
    assert codes[:tools_api.MAX_PER_UUR] == [200] * tools_api.MAX_PER_UUR and codes[-2:] == [429, 429]


def test_kapotte_database_verliest_het_adres_niet(client):
    """Voor-en-na: de tabel bestaat pas als Daniel schema.sql heeft uitgevoerd. Tot dan mag een
    bevestigd adres niet stil verdwijnen: het gaat per mail naar de eigenaar en de bezoeker
    krijgt zijn bestand."""
    _post(client)
    url = _link(client)
    client.db.kapot = True
    d = client.get(url)
    assert d.status_code == 200 and d.content[:2] == b"PK"
    assert len(client.mails) == 2 and "anna@voorbeeld.nl" in client.mails[1][1]      # 1e mail: naar de bezoeker


def test_tabel_staat_in_schema_sql():
    sql = (REPO / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS tool_aanmeldingen" in sql and "email         TEXT NOT NULL UNIQUE" in sql


# ── Spreadsheets ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bestand,kolommen", [("voorraad-winst-spreadsheet-nl.xlsx", 12), ("inventory-profit-spreadsheet-en.xlsx", 12)])
def test_spreadsheet_heeft_echte_formules(bestand, kolommen):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(REPO / "backend" / "downloads" / bestand)
    inv, jaar = wb.worksheets
    assert inv.max_column == kolommen and inv.max_row == 3 + 500
    assert inv["J4"].value == '=IF(G4="","",G4-C4-H4-I4)'
    assert inv["K503"].value.startswith("=IF(E503") and inv["L503"].value.startswith("=IF(F503")
    assert jaar["B1"].value == 2026
    assert jaar["B4"].value.startswith("=COUNTIFS(") and "$B$1" in jaar["B4"].value
    assert ">=30" in jaar["E4"].value and ">2000" in jaar["E4"].value
    assert inv.data_validations.dataValidation, "keuzelijst voor kanaal ontbreekt"


# ── Opfrisbeurt 28-10-2026: nieuwe tools, kopblok, acties, mail-resultaat ──

@pytest.mark.parametrize("taal,tool", ALLE)
def test_elke_pagina_heeft_antwoord_vooraan_chips_en_ux_script(taal, tool):
    html = _pagina(taal, tool)
    assert html.count('class="kr-kort"') == 1 and html.count('class="kr-chips"') == 1
    assert tool["antwoord"][taal][:40].replace("'", "&#39;") in html or tool["antwoord"][taal][:20] in html
    assert f'src="/assets/tools/ux.js?v=' in html and f'data-tool="{tool["key"]}"' in html
    assert html.index('class="kr-kort"') > html.index("</h1>")


def test_hub_groepeert_en_alle_groepen_hebben_tools():
    from backend.tools_data import GROEPEN
    assert {t["groep"] for t in TOOLS} <= set(GROEPEN)
    for taal in TALEN:
        html = _pagina(taal, None)
        assert html.count('class="kr-groep"') == len(GROEPEN)
        assert html.count('class="kr-nieuw"') == sum(1 for t in TOOLS if t["nieuw"]) == 3


@node
def test_winstmarge_marge_is_van_de_verkoopprijs_en_opslag_van_de_inkoop():
    g = _node([("W", "winstmarge.js")], textwrap.dedent("""
        const a=W.bereken(20,30,0,0), b=W.bereken(20,30,2,0.1), v=W.bereken(20,15,0,0);
        console.log(JSON.stringify({a, b, v,
          pm: W.prijsVoorMarge(20,0,0,0.4), po: W.prijsVoorOpslag(20,0,0,1.0),
          pmFee: W.prijsVoorMarge(20,2,0.1,0.3), onm: W.prijsVoorMarge(20,0,0.6,0.5), leeg: W.bereken(20,0,0,0)}));
    """))
    assert g["a"]["winst"] == 10 and g["a"]["marge"] == pytest.approx(1 / 3) and g["a"]["opslag"] == pytest.approx(0.5)
    assert g["b"]["winst"] == pytest.approx(30 * 0.9 - 20 - 2)          # kanaalkosten over de verkoopprijs
    assert g["v"]["winst"] == -5 and g["v"]["marge"] < 0
    assert g["pm"] == 33.34 and g["po"] == 40
    # de prijs voor een marge geeft die marge ook echt terug
    check = _node([("W", "winstmarge.js")], "console.log(JSON.stringify(W.bereken(20,%s,2,0.1)))" % g["pmFee"])
    assert check["marge"] >= 0.3 - 1e-9 and check["marge"] < 0.301
    assert g["onm"] is None and g["leeg"] is None


@node
def test_belastingcheck_volgt_de_regels_van_de_belastingdienst():
    g = _node([("B", "belastingcheck.js")], textwrap.dedent("""
        const f=(o)=>B.beoordeel(o).uitslag;
        console.log(JSON.stringify({
          eigen: f({herkomst:'eigen',prijs:'meer'}),
          inkoopMeer: f({herkomst:'inkoop',prijs:'meer'}),
          inkoopMinder: f({herkomst:'inkoop',prijs:'minder'}),
          mix: f({herkomst:'mix',prijs:'meer'}),
          voorbeeld: B.beoordeel({herkomst:'inkoop',prijs:'meer',inkoop:1000,omzet:2100,kosten:0}),
          verlies: f({herkomst:'inkoop',prijs:'meer',inkoop:500,omzet:150}),
          kosten: B.beoordeel({herkomst:'inkoop',prijs:'meer',inkoop:1000,omzet:2100,kosten:150}).winst,
          leeg: f({}),
        }));
    """))
    assert g["eigen"] == "geen" and g["inkoopMeer"] == "wel" and g["inkoopMinder"] == "geen" and g["mix"] == "twijfel"
    assert g["voorbeeld"] == {"uitslag": "wel", "winst": 1100}        # voorbeeld op de pagina van de Belastingdienst
    assert g["verlies"] == "geen"                                      # babykleding € 500 voor € 150
    assert g["kosten"] == 950 and g["leeg"] is None


@node
def test_advertentietekst_kapt_af_zoals_de_titelchecker_en_verzint_niets():
    inv = {"product": "wollen jas heren", "merk": "Burberry", "model": "Kensington", "maat": "maat 50", "kleur": "zwart",
           "staat": "goed", "afm": "", "extra": "", "gebreken": "", "levering": "beide"}
    g = _node([("A", "advertentietekst.js"), ("T", "titelchecker.js")], textwrap.dedent("""
        const inv=%s;
        const m=A.maak(inv,'marktplaats','nl'), v=A.maak(inv,'vinted','en'), e=A.maak(inv,'ebay','fr');
        const lang='Burberry wollen jas heren maat 50 - Zwart - Vintage - Nieuwstaat met kaartjes';
        console.log(JSON.stringify({m,v,e, gelijk: A.afkap(lang,60)===T.afkap(lang,60) && A.afkap('Heel lange titel zonder streepjes erin hoor',30)===T.afkap('Heel lange titel zonder streepjes erin hoor',30),
          grenzen: A.LIMIET, tk: T.KANALEN.map(k=>[k.key,k.max])}));
    """ % json.dumps(inv)))
    assert g["gelijk"]
    assert g["m"]["tekens"] <= 60 and g["m"]["limiet"] == 60 and g["v"]["limiet"] is None
    assert "Staat: Goed" in g["m"]["beschrijving"] and "Gebreken" not in g["m"]["beschrijving"]   # niets bijverzonnen
    assert g["m"]["zonderGebreken"] is True
    assert "Condition: Good" in g["v"]["beschrijving"] and "État: Bon état" in g["e"]["beschrijving"]
    for k, mx in g["tk"]:
        assert g["grenzen"][k] == mx


def _mail(c, **kw):
    body = {"email": "Anna@Voorbeeld.nl", "taal": "nl", "bron": "winstmarge", "tekst": "Winst € 10,00\nMarge 33,3%",
            "link": "https://omnivaleur.com/nl/tools/winstmarge-berekenen?wm-inkoop=20", "tips": False, "website": ""}
    body.update(kw)
    return c.post("/api/tools/mail-resultaat", json=body)


def test_mail_resultaat_verstuurt_naar_de_bezoeker_en_bewaart_geen_adres_zonder_tips(client):
    r = _mail(client)
    assert r.status_code == 200
    to, onderwerp, tekst = client.naar[0]
    assert to == "anna@voorbeeld.nl" and "Winstmarge berekenen" in onderwerp
    assert "Winst € 10,00" in tekst and "wm-inkoop=20" in tekst and "/register" in tekst
    assert "*" not in tekst and "—" not in tekst and "–" not in tekst          # platte tekst, geen streepjes als leesteken
    assert client.db.rijen == []                                               # geen toestemming, dus niets bewaard


def test_mail_resultaat_met_tips_bewaart_het_adres_met_toestemming(client):
    assert _mail(client, tips=True).status_code == 200
    assert client.db.rijen == [({"email": "anna@voorbeeld.nl", "taal": "nl", "bron": "mail-winstmarge", "toestemming": True}, "email")]


@pytest.mark.parametrize("kw", [{"email": "geen-adres"}, {"bron": "voorraadsheet"}, {"bron": "bestaat-niet"}, {"tekst": "  "}])
def test_mail_resultaat_weigert_slechte_invoer(client, kw):
    assert _mail(client, **kw).status_code == 422 and client.db.rijen == []


def test_mail_resultaat_lokveld_tempo_en_vreemde_links(client):
    assert _mail(client, website="x").status_code == 200 and client.mails == []
    _mail(client, link="https://boos.example/phishing")
    assert "boos.example" not in client.naar[0][2]                                       # alleen eigen links in de mail
    for i in range(2):
        assert _mail(client).status_code == 200
    assert _mail(client).status_code == 429                                    # 3 per adres per dag
