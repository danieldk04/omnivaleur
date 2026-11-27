# Revaleur-herbouw, fase 1: inventaris (27-11-2026)

Gemeten op revaleur.com. Ruwe scrape staat lokaal in `data/revaleur-inventaris/` (niet in git; opnieuw te maken met Playwright, want Shopify toont aan gewone curl een bot-controle, alleen `/products.json` en `/collections.json` werken zonder browser). Tekst van beleidspagina's staat in `docs/revaleur/`.

## Cijfers
- 258 producten, 256 beschikbaar, alle met één variant ("Default Title"), prijs €4,99 tot €169,99 (gemiddeld €33,97), 214 met doorgestreepte "Retail"-prijs (compare_at_price). Merken: Ralph Lauren 150, Suitsupply 62, Massimo Dutti 15, Profuomo 11, rest klein. Types: Sweater, Zip Vest, Shirt, Turtleneck, Jumper, Hoodie, Half Zip, Polo Shirt, enz.
- 18 collecties (all, hoodies, outerwear, shoes, chinos, suits-blazers, tops-shirts, trousers, shorts, activewear, jumpers-sweaters-1, latest-products-1, 1-2-vintage-deal, ralph-lauren, stone-island, suitsupply, profuomo, massimo-dutti) plus `latest-products` in het menu.
- Pagina's: contact-us (formulier + FAQ), our-mission, size-chart-men (toont nu de mission-tekst, maattabel zit dus elders, zie productpagina "SEE SIZE CHART & MEASUREMENTS"), data-sharing-opt-out. Beleid: shipping, refund, terms, privacy (legal-notice bestaat niet). Blog `news` met o.a. `where-do-we-get-our-products`.
- Talen: Engels en Nederlands (`/nl/...`, eigen SEO-titels), prijs in EUR.

## Look (Dawn 15.3.0, thema "MAIN WEBSITE")
- Lettertype Montserrat (500 en 700), knopradius 8px, paginabreedte 1600px, knop zwart (18,18,18).
- Kleuren: goud (184,154,80 = #B89A50) voor de tweede aankondigingsbalk en badges, rood (224,34,41 = #E02229) voor de bovenste balk en uitverkoop, donker marineblauw (7,15,28).
- Opbouw: rode balk ("€100 BONUS MYSTERY 3-FOR-1 FLASH DEAL"), gouden balk met sociale iconen en "715+ HAPPY CUSTOMERS", witte header met logo, menu (Categories, Brands, Blog, Our mission), landen-/taalkeuze, zoeken, account, winkelmand. Hero met twee foto's en knop "SHOP THE LATEST PRODUCTS", rij "OUR LATEST PRODUCTS, LIVE NOW".
- Productpagina: galerij (ca. 11 foto's), "715+ reviews", titel, Retail-prijs doorgestreept + prijs, groen "FREE shipping to NL & BE", "HURRY UP: ONLY 1 AVAILABLE", "100% AUTHENTIC OR 200% MONEY-BACK", "EASY RETURNS", rode "Unique item"-regel, ADD TO CART, snelle betaalknop, "Verified Authentic & Cleaned", link naar maattabel.
- Screenshots staan lokaal in de scratchpad; maak ze opnieuw voor de vergelijking in fase 7.

## Verzending en voorwaarden (uit de beleidspagina's)
- NL en BE gratis, 1 tot 2 werkdagen. Rest van EU €3,95, gratis vanaf €100, 2 tot 3 werkdagen. Buiten EU €4,95, gratis vanaf €100, 6 tot 8 werkdagen; invoerrechten voor de koper.
- Verzonden ma t/m za binnen 1 werkdag, altijd met tracking.
- Retour binnen 14 dagen na levering, retourkosten voor de koper, adres Kleine Melanen 5, 4614RG Bergen op Zoom. Terugbetaling na ontvangst en controle, meestal binnen 5 werkdagen, inclusief standaardverzending als de hele bestelling terug gaat.
- Betaalmethoden volgens FAQ: iDEAL, PayPal, Klarna, creditcard. Contact: info@revaleur.com.

## Apps (uit de opdracht, nog te toetsen)
Zichtbaar op de site: Judge.me-achtige "715+ reviews", Essential post-purchase upsell, Klarna/PayPal-knoppen, snelle betaalknop. Rest (Clarity, TinySEO, Search & Discovery, Translate & Adapt, Flow, Forms, Messaging, Order Printer Pro, Pendora) is onzichtbaar of back-office.

## Open punten voor fase 2
1. Shopify-admin (verzendzones, btw/marge, e-mailsjablonen, redirects, menu's) is vanuit hier niet te lezen zonder inlog of API-sleutel: staat bij "Alleen Daniel" of via de bestaande Shopify-koppeling (`backend/platforms/shopify.py`).
2. Maattabel: nog opzoeken waar die nu staat.
3. Hoe `products.json` zich verhoudt tot de Omnivaleur-database (241 gekoppeld van 258).
