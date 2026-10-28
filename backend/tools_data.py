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
        "key": "kostenrekenaar", "groep": "kosten", "nieuw": False, "antwoord": {"nl": 'Op Marktplaats, 2dehands en Vinted betaalt de verkoper geen commissie, dus je vraagprijs is je inkoop plus je winst. eBay houdt commissie in, dus daar moet de prijs hoger.', "en": 'On Marktplaats, 2dehands and Vinted the seller pays no commission, so your asking price is your purchase price plus your profit. eBay takes a commission, so the price has to be higher there.'}, "icon": "💶", "gated": False, "scripts": ["kostenrekenaar.js"],
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
        "key": "titelchecker", "groep": "advertenties", "nieuw": False, "antwoord": {"nl": 'Marktplaats en 2dehands kappen een titel af op 60 tekens, eBay op 80 en Facebook Marketplace op 100.', "en": 'Marktplaats and 2dehands cut a title at 60 characters, eBay at 80 and Facebook Marketplace at 100.'}, "icon": "🔤", "gated": False, "scripts": ["tools/gedeeld.js", "tools/titelchecker.js"],
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
        "key": "dac7", "groep": "belasting", "nieuw": False, "antwoord": {"nl": 'Een platform geeft je door aan de Belastingdienst bij 30 verkopen of meer, of bij meer dan € 2.000 omzet, per platform per kalenderjaar. Doorgegeven betekent niet dat je belasting betaalt.', "en": 'A platform reports you to the Belastingdienst at 30 sales or more, or more than EUR 2,000 revenue, per platform per calendar year. Being reported does not mean you pay tax.'}, "icon": "🧾", "gated": False, "scripts": ["tools/gedeeld.js", "tools/dac7.js"],
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
        "key": "margeregeling", "groep": "belasting", "nieuw": False, "antwoord": {"nl": 'Onder de margeregeling betaal je btw over je winstmarge: marge maal 21 gedeeld door 121. Maak je geen winst, dan is de btw nul.', "en": 'Under the margin scheme you pay VAT on your profit margin: margin times 21 divided by 121. If you make no profit, the VAT is zero.'}, "icon": "🧮", "gated": False, "scripts": ["tools/gedeeld.js", "tools/margeregeling.js"],
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
        "key": "afprijsplanner", "groep": "kosten", "nieuw": False, "antwoord": {"nl": 'De ladder: 5% omlaag vanaf 30 dagen online, 10% vanaf 60, 15% vanaf 90 en 20% vanaf 180 dagen, afgerond op ,99 en nooit onder je inkoopprijs.', "en": 'The ladder: 5% lower from 30 days online, 10% from 60, 15% from 90 and 20% from 180 days, rounded to .99 and never below your purchase price.'}, "icon": "📉", "gated": False, "scripts": ["tools/gedeeld.js", "tools/afprijsplanner.js"],
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
        "key": "voorraadsheet", "groep": "downloads", "nieuw": False, "antwoord": {"nl": 'Een Excel met 500 regels: winst per artikel, dagen in voorraad en een jaaroverzicht per platform met DAC7-controle.', "en": 'An Excel sheet with 500 rows: profit per item, days in stock and a yearly overview per platform with a DAC7 check.'}, "icon": "📊", "gated": True, "scripts": ["tools/gedeeld.js", "tools/voorraadsheet.js"],
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
    {
        "key": "belastingcheck", "groep": "belasting", "nieuw": True, "icon": "⚖️", "gated": False,
        "scripts": ["tools/gedeeld.js", "tools/belastingcheck.js"],
        "slug": {"en": "second-hand-sales-tax-check", "nl": "belasting-check-vinted-marktplaats"},
        "antwoord": {"nl": "Verkoop je je eigen spullen, hobbymatig of voor minder dan je betaalde, dan is dat volgens de Belastingdienst geen bron van inkomen. Koop je spullen in om ze met winst door te verkopen, dan wel, en er geldt geen minimumbedrag aan winst.",
                     "en": "If you sell your own things, as a hobby or for less than you paid, the Belastingdienst says that is not a source of income. If you buy things to resell at a profit it is, and there is no minimum amount of profit."},
        "en": {"naam": "Second-hand sales tax check",
               "kort": "Do you owe tax on what you sell on Vinted or Marktplaats? Answer four questions and see where you stand.",
               "titel": "Do I pay tax on Vinted and Marktplaats sales? Free check | Omnivaleur",
               "meta": "Free check: do you owe income tax on what you sell on Vinted, Marktplaats or eBay in the Netherlands? Based on the Belastingdienst rules for hobby sales and buying to resell."},
        "nl": {"naam": "Belastingcheck voor Vinted en Marktplaats",
               "kort": "Moet je belasting betalen over wat je op Vinted of Marktplaats verkoopt? Beantwoord vier vragen en zie waar je staat.",
               "titel": "Belasting betalen over Vinted en Marktplaats? Gratis check | Omnivaleur",
               "meta": "Gratis check: moet je inkomstenbelasting betalen over wat je verkoopt op Vinted, Marktplaats of eBay? Gebaseerd op de regels van de Belastingdienst voor hobby en inkopen om door te verkopen."},
    },
    {
        "key": "winstmarge", "groep": "kosten", "nieuw": True, "icon": "📈", "gated": False,
        "scripts": ["tools/gedeeld.js", "tools/winstmarge.js"],
        "slug": {"en": "profit-margin-calculator", "nl": "winstmarge-berekenen"},
        "antwoord": {"nl": "Marge is winst gedeeld door verkoopprijs, opslag is winst gedeeld door inkoopprijs. Koop je voor € 20 en verkoop je voor € 30, dan is de winst € 10, de marge 33,3% en de opslag 50%.",
                     "en": "Margin is profit divided by selling price, markup is profit divided by purchase price. Buy for EUR 20 and sell for EUR 30 and the profit is EUR 10, the margin 33.3% and the markup 50%."},
        "en": {"naam": "Profit margin calculator",
               "kort": "Profit, margin and markup of an item after fees and shipping, and the price you need for the margin you want.",
               "titel": "Profit margin and markup calculator for resellers | Omnivaleur",
               "meta": "Free profit margin calculator for resellers: enter purchase price, selling price, fees and shipping and see profit, margin and markup, or the price you need for a target margin."},
        "nl": {"naam": "Winstmarge berekenen",
               "kort": "Winst, marge en opslag van een artikel na kosten en verzending, en de prijs die je nodig hebt voor je gewenste marge.",
               "titel": "Winstmarge berekenen voor tweedehands verkoop | Omnivaleur",
               "meta": "Gratis winstmarge berekenen voor verkopers: vul inkoop, verkoopprijs, kosten en verzending in en zie winst, marge en opslag, of de prijs die past bij je gewenste marge."},
    },
    {
        "key": "advertentietekst", "groep": "advertenties", "nieuw": True, "icon": "✍️", "gated": False,
        "scripts": ["tools/gedeeld.js", "tools/titelchecker.js", "tools/advertentietekst.js"],
        "slug": {"en": "listing-description-generator", "nl": "advertentietekst-generator"},
        "antwoord": {"nl": "Vul in wat je weet en je krijgt een titel binnen de tekengrens van het kanaal en een nette beschrijving, in het Nederlands, Engels, Frans of Duits. Zonder AI, dus er wordt niets bijverzonnen.",
                     "en": "Fill in what you know and you get a title within the channel's character limit and a clean description, in Dutch, English, French or German. No AI, so nothing is made up."},
        "en": {"naam": "Listing description generator",
               "kort": "A title within the limit and a clear description for Marktplaats, Vinted or eBay, in four languages.",
               "titel": "Listing title and description generator | Omnivaleur",
               "meta": "Free listing generator for Marktplaats, 2dehands, Vinted and eBay: fill in brand, size and condition and get a title within the limit plus a clear description in Dutch, English, French or German."},
        "nl": {"naam": "Advertentietekst-generator",
               "kort": "Een titel binnen de grens en een heldere beschrijving voor Marktplaats, Vinted of eBay, in vier talen.",
               "titel": "Advertentietekst en titel maken voor Marktplaats en Vinted | Omnivaleur",
               "meta": "Gratis advertentietekst-generator voor Marktplaats, 2dehands, Vinted en eBay: vul merk, maat en staat in en krijg een titel binnen de grens en een heldere beschrijving in vier talen."},
    },
]

GROEPEN = ["kosten", "belasting", "advertenties", "downloads"]
GROEP_NAAM = {
    "en": {"kosten": "Price and profit", "belasting": "Tax and rules", "advertenties": "Listings", "downloads": "Downloads"},
    "nl": {"kosten": "Prijs en winst", "belasting": "Belasting en regels", "advertenties": "Advertenties", "downloads": "Downloads"},
}
TOOLS.sort(key=lambda t: GROEPEN.index(t["groep"]))  # stabiel: binnen een groep blijft de volgorde

HUB = {
    "en": {"pad": "/tools", "titel": "Free tools for second-hand sellers | Omnivaleur",
           "meta": "Free tools for second-hand sellers on Marktplaats, 2dehands, Vinted and eBay: fee and profit calculators, tax checks, a listing text generator, a title checker and an inventory spreadsheet.",
           "h1": "Free tools for second-hand sellers"},
    "nl": {"pad": "/nl/tools", "titel": "Gratis tools voor tweedehands verkopers | Omnivaleur",
           "meta": "Gratis tools voor tweedehands verkopers op Marktplaats, 2dehands, Vinted en eBay: kosten- en winstrekenaars, belastingchecks, een advertentietekst-generator, titelchecker en een voorraadspreadsheet.",
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
