"""De gratis tools op één plek (hub /tools en /nl/tools).

Eén lijst dient voor alles: de hub, elke toolpagina, het menu, de sitemap en
frontend/llms.txt. Een tool toevoegen = hier één regel, twee tekstbestanden in
frontend/templates/tools/ (<key>.nl.html en <key>.en.html) en eventueel een
script in frontend/assets/tools/. Vergeet niet llms.txt bij te werken; de proef
tests/test_tools_hub.py controleert dat elke tool overal staat waar hij hoort.

`gated` = de tool vraagt een e-mailadres (alleen downloads). Rekentools zijn
bewust vrij te gebruiken: Crosslist houdt zijn maattabellen ook zonder poort, en
een poort voor een rekenmachine kost meer bezoekers dan aanmeldingen.
"""
from __future__ import annotations

SITE = "https://omnivaleur.com"
GEWIJZIGD = "2026-10-28"

TOOLS: list[dict] = [
    {
        "key": "kostenrekenaar", "icon": "💶", "gated": False, "scripts": ["kostenrekenaar.js"],
        "slug": {"en": "fee-calculator", "nl": "kostenrekenaar"},
        "en": {"naam": "Fee calculator",
               "kort": "What price to ask on Marktplaats, 2dehands, Vinted and eBay to keep your profit.",
               "titel": "Marktplaats, Vinted and eBay fee calculator | Omnivaleur",
               "meta": "Free fee calculator for Marktplaats, 2dehands, Vinted and eBay.nl. Enter your purchase price and the profit you want and see the asking price per marketplace. Fees checked on 28 October 2026."},
        "nl": {"naam": "Kostenrekenaar",
               "kort": "Welke prijs je moet vragen op Marktplaats, 2dehands, Vinted en eBay om je winst te houden.",
               "titel": "Kostenrekenaar Marktplaats, Vinted en eBay | Omnivaleur",
               "meta": "Gratis kostenrekenaar voor Marktplaats, 2dehands, Vinted en eBay.nl. Vul je inkoopprijs en gewenste winst in en zie per kanaal welke prijs je moet vragen. Tarieven gecontroleerd op 28 oktober 2026."},
    },
    {
        "key": "titelchecker", "icon": "🔤", "gated": False, "scripts": ["tools/gedeeld.js", "tools/titelchecker.js"],
        "slug": {"en": "title-length-checker", "nl": "titel-tekenteller"},
        "en": {"naam": "Title length checker",
               "kort": "Count your listing title against the character limit of Marktplaats, 2dehands, eBay and Facebook.",
               "titel": "Listing title length checker for Marktplaats and eBay | Omnivaleur",
               "meta": "Free title length checker: see how many characters your listing title has and where Marktplaats, 2dehands, eBay and Facebook Marketplace cut it off."},
        "nl": {"naam": "Titel-tekenteller",
               "kort": "Tel de tekens van je titel en zie waar Marktplaats, 2dehands, eBay en Facebook hem afkappen.",
               "titel": "Titel tekenteller voor Marktplaats en eBay | Omnivaleur",
               "meta": "Gratis tekenteller voor advertentietitels: zie hoeveel tekens je titel heeft en waar Marktplaats, 2dehands, eBay en Facebook Marketplace hem afkappen."},
    },
    {
        "key": "dac7", "icon": "🧾", "gated": False, "scripts": ["tools/gedeeld.js", "tools/dac7.js"],
        "slug": {"en": "dac7-checker", "nl": "dac7-check"},
        "en": {"naam": "DAC7 checker",
               "kort": "Will Marktplaats, Vinted or eBay report your sales to the Belastingdienst this year?",
               "titel": "DAC7 checker: will your sales be reported? | Omnivaleur",
               "meta": "Free DAC7 checker for sellers on Marktplaats, Vinted and eBay: enter your sales and revenue per platform and see whether you pass the 30 sales or EUR 2,000 reporting threshold."},
        "nl": {"naam": "DAC7-check",
               "kort": "Meldt Marktplaats, Vinted of eBay jouw verkopen dit jaar door aan de Belastingdienst?",
               "titel": "DAC7-check: worden je verkopen doorgegeven? | Omnivaleur",
               "meta": "Gratis DAC7-check voor verkopers op Marktplaats, Vinted en eBay: vul je verkopen en omzet per platform in en zie of je boven de grens van 30 verkopen of 2.000 euro komt."},
    },
    {
        "key": "margeregeling", "icon": "🧮", "gated": False, "scripts": ["tools/gedeeld.js", "tools/margeregeling.js"],
        "slug": {"en": "vat-margin-scheme-calculator", "nl": "btw-margeregeling-rekenhulp"},
        "en": {"naam": "VAT margin scheme calculator",
               "kort": "How much VAT you owe on a second-hand item under the Dutch margin scheme, against normal VAT.",
               "titel": "VAT margin scheme calculator for second-hand goods | Omnivaleur",
               "meta": "Free calculator for the Dutch VAT margin scheme (margeregeling): enter purchase and selling price and see the VAT on the margin against normal VAT on the full price."},
        "nl": {"naam": "Btw-margeregeling rekenhulp",
               "kort": "Hoeveel btw je afdraagt over een tweedehands artikel met de margeregeling, tegenover gewone btw.",
               "titel": "Btw-margeregeling rekenhulp voor tweedehands | Omnivaleur",
               "meta": "Gratis rekenhulp voor de btw-margeregeling: vul inkoop- en verkoopprijs in en zie de btw over de marge, naast de btw over de volle verkoopprijs."},
    },
    {
        "key": "afprijsplanner", "icon": "📉", "gated": False, "scripts": ["tools/gedeeld.js", "tools/afprijsplanner.js"],
        "slug": {"en": "price-drop-planner", "nl": "afprijsplanner"},
        "en": {"naam": "Price drop planner",
               "kort": "When an unsold item should get cheaper, and by how much, without selling at a loss.",
               "titel": "Price drop planner for unsold second-hand items | Omnivaleur",
               "meta": "Free price drop planner: enter the price, the days online and what you paid, and see the suggested lower price for an item that has not sold, never below your purchase price."},
        "nl": {"naam": "Afprijsplanner",
               "kort": "Wanneer een onverkocht artikel goedkoper moet en met hoeveel, zonder verlies te verkopen.",
               "titel": "Afprijsplanner voor onverkochte tweedehands artikelen | Omnivaleur",
               "meta": "Gratis afprijsplanner: vul prijs, dagen online en inkoop in en zie welke lagere prijs past bij een artikel dat niet verkoopt, nooit onder je inkoopprijs."},
    },
    {
        "key": "voorraadsheet", "icon": "📊", "gated": True, "scripts": ["tools/gedeeld.js", "tools/voorraadsheet.js"],
        "slug": {"en": "inventory-profit-spreadsheet", "nl": "voorraad-winst-spreadsheet"},
        "en": {"naam": "Inventory and profit spreadsheet",
               "kort": "Excel sheet with profit per item, days in stock and a yearly DAC7 check per platform. Free for your email address.",
               "titel": "Free inventory and profit spreadsheet for resellers | Omnivaleur",
               "meta": "Free Excel spreadsheet for resellers: inventory, profit per item, days in stock and a yearly overview per platform with a DAC7 check. Download in exchange for your email address."},
        "nl": {"naam": "Voorraad- en winstspreadsheet",
               "kort": "Excel met winst per artikel, dagen in voorraad en een jaaroverzicht met DAC7-check per platform. Gratis voor je e-mailadres.",
               "titel": "Gratis voorraad- en winstspreadsheet voor resellers | Omnivaleur",
               "meta": "Gratis Excel voor resellers: voorraad, winst per artikel, dagen in voorraad en een jaaroverzicht per platform met DAC7-check. Download in ruil voor je e-mailadres."},
    },
]

HUB = {
    "en": {"pad": "/tools", "titel": "Free tools for second-hand sellers | Omnivaleur",
           "meta": "Free tools for second-hand sellers on Marktplaats, 2dehands, Vinted and eBay: fee calculator, title length checker, DAC7 check, VAT margin scheme calculator, price drop planner and an inventory spreadsheet.",
           "h1": "Free tools for second-hand sellers"},
    "nl": {"pad": "/nl/tools", "titel": "Gratis tools voor tweedehands verkopers | Omnivaleur",
           "meta": "Gratis tools voor tweedehands verkopers op Marktplaats, 2dehands, Vinted en eBay: kostenrekenaar, titel-tekenteller, DAC7-check, btw-margeregeling rekenhulp, afprijsplanner en een voorraadspreadsheet.",
           "h1": "Gratis tools voor tweedehands verkopers"},
}


def tool_pad(tool: dict, taal: str) -> str:
    return f"/nl/tools/{tool['slug']['nl']}" if taal == "nl" else f"/tools/{tool['slug']['en']}"


def vind_tool(taal: str, slug: str) -> dict | None:
    for t in TOOLS:
        if t["slug"][taal] == slug:
            return t
    return None


def sitemap_paden() -> list[tuple[str, str, str]]:
    uit = [("/tools", "weekly", "0.9"), ("/nl/tools", "weekly", "0.9")]
    for t in TOOLS:
        uit += [(tool_pad(t, "en"), "monthly", "0.8"), (tool_pad(t, "nl"), "monthly", "0.8")]
    return uit
