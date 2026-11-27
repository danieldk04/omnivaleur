# Opdracht: revaleur.com herbouwen als eigen AI-webshop (Daniel, 27-11-2026)

Voor de andere developer. Ga door tot het VOLLEDIG staat en live is; stop niet bij een deel en
vraag Daniel niet om tussentijdse goedkeuring behalve bij de punten onder "Alleen Daniel".
Dit vervangt de eerdere notitie "NIET herbouwen" in docs/team-notes.md (die was een misverstand).

## Doel
revaleur.com (nu Shopify, €28 per maand, alleen plan, geen appkosten) wordt een eigen webshop op
de Omnivaleur-stack, met een maandbedrag van bijna nul (alleen domein, Stripe per bestelling).
Daniel verkoopt er weinig; het gaat om lagere kosten ZONDER kwaliteitsverlies.

## Harde eisen van Daniel
1. UX en UI minstens zo goed als nu. Het is een betrouwbare, oude site; klanten mogen geen verschil
   zien behalve dat het sneller is. Neem de huidige look over (kleuren, lettertypes, collectiepagina's,
   productpagina, maattabel) en vergelijk naast elkaar, op mobiel en desktop.
2. Geen extra onderhoud voor Daniel. Hij moet nooit een uitgevallen site zelf herstellen. Dus: statische
   winkelkant op een gratis host met CDN (bv. Cloudflare Pages) die bij uitval van onze backend de
   productpagina's blijft tonen; alleen checkout hangt van de backend af, met een duidelijke melding
   als die even stilligt. Geen eigen server of plugin die updates nodig heeft.
3. Er komt een routine die de site bewaakt (zie onder). Daniel vraagt aanpassingen aan Claude of de developer.
4. Nederlands en Engels, zoals nu (/nl op Shopify). Alle klanttekst tweetalig, zie CLAUDE.md (i18n).

## Wat er nu is (gemeten 27-11-2026)
- Shopify-winkel ywqad3-xb.myshopify.com, domein revaleur.com, 250+ producten (products.json geeft er 250 per pagina), 18 collecties
  (all, hoodies, outerwear, shoes, chinos, suits-blazers, tops-shirts, trousers, shorts, activewear, jumpers-sweaters-1,
  latest-products-1, 1-2-vintage-deal en merken: ralph-lauren, stone-island, suitsupply, profuomo, massimo-dutti),
  pagina's: contact-us, our-mission, size-chart-men, data-sharing-opt-out. Blog en artikelen bestaan in de sitemap.
- Producten hebben titel in het formaat "(nummer) Kleur Merk Type - Men M - Very Good", SKU = artikelnummer, ca. 11 foto's, prijs.
- Omnivaleur koppelt nu aan Shopify (backend/platforms/shopify.py, backend/services/shopify_*.py, webhook orders/paid in
  backend/api/webhooks.py, controle om de paar minuten). 241 artikelen zijn gekoppeld. De Omnivaleur-database (Supabase, tabel items,
  listings) is al de bron van waarheid voor artikelen, foto's, prijzen en voorraad. Stripe (stripe_secret_key) en Resend staan al in backend/config.py.
- Er is al een WooCommerce-platform in backend/platforms/woocommerce.py als referentie voor een webshop-kanaal.
- Shopify-apps: Microsoft Clarity, Search & Discovery, TinySEO, Translate & Adapt, Pendora Downloads, Order Printer Pro, Judge.me Reviews,
  Flow, Forms, Messaging, Omnivaleur demo. Daniel gebruikt ze grotendeels niet. Zoek per app uit of er iets zichtbaar aan hangt
  (reviews op productpagina's, SEO-velden, vertaling, factuurprint) en bouw alleen na wat echt gebruikt wordt.

## Aanpak (fases; ga zonder te vragen door naar de volgende)
1. Inventaris: scrape revaleur.com volledig (pagina's, collecties, productvelden, metafields, menu's, redirects, SEO-titels, blog) en leg het vast.
   Haal de Shopify-instellingen op voor verzending (zones, tarieven), btw/marge, betaalmethoden, e-mailsjablonen.
2. Ontwerp: opzet op de Omnivaleur-database; catalogus via een publieke, gecachete API of statische export; checkout met Stripe Checkout
   (iDEAL, kaart); bestelling schrijft naar een nieuwe tabel en gebruikt de bestaande verkoopafhandeling (handle_item_sold) zodat het artikel
   direct van Marktplaats, Vinted en eBay af gaat. Eén exemplaar per artikel: reserveer bij checkout, geef vrij bij mislukte betaling.
3. Bouwen: winkelkant, productpagina's, collecties met filter en zoeken, winkelmand, checkout, orderbevestiging en verzendmail (Resend,
   in Daniels stijl, docs/schrijfstijl-daniel.md; nooit "sorry" of schuld aantrekken), accountloze bestelling, retourpagina, voorwaarden, privacy, cookiebanner.
4. Wettelijk en fiscaal (uitzoeken VOOR bouwen en met bron vastleggen): margeregeling, factuur zonder btw-bedrag, bewaarplicht,
   herroepingsrecht 14 dagen, verzendkosten per land, btw-regels voor andere EU-landen (OSS staat in docs/routines/oss-aangifte.md).
5. Zoekmachines en advertenties: alle URL's 301'en van /products/... en /collections/... naar de nieuwe, sitemap, robots, structured data,
   Meta-catalogus en pixel, Google Merchant-feed. Controleer in Google Search Console dat verkeer niet wegvalt.
6. Verzending: labels via Sendcloud of MyParcel (kies de goedkoopste die bij Daniels huidige werkwijze past), trackingmail.
7. Parallel draaien: nieuwe site op een testdomein, naast Shopify. Doe echte testbestellingen (Stripe testmodus, dan één echte van €1 met terugbetaling
   door Daniel), controleer factuur, mails, afmelding op andere kanalen en voorraad.
8. Omzetten: DNS van revaleur.com naar de nieuwe site, redirects live, Shopify 30 dagen aanhouden als vangnet en pas daarna opzeggen (Daniel).
9. Bewaking: breid docs/routines/revaleur-sitecheck.md uit voor de nieuwe site (bereikbaarheid, testbestelling-simulatie, kapotte foto's,
   Stripe-webhook, mail). De geplande taak `omnivaleur-revaleur-sitecheck` draait al elke maandag.

## Klaar als
- Alle actieve producten, collecties, pagina's en blog staan er, tweetalig, zichtbaar gelijkwaardig aan nu.
- Een echte bestelling loopt van betaling tot verzendmail en het artikel is op alle kanalen afgemeld.
- 301's getest op een steekproef van minstens 50 oude URL's, Merchant- en Meta-feed werken, Search Console meldt geen fouten.
- Sitecheck-routine bewaakt de nieuwe site en is één keer groen gedraaid.
- docs/overdracht.md, docs/team-notes.md en de kennisbank zijn bijgewerkt; gemerged naar main en /health gecontroleerd (CLAUDE.md).

## Alleen Daniel
Betaalde dingen (domeinverhuizing, Stripe-account koppelen), DNS omzetten, Shopify opzeggen, en de echte testbestelling terugbetalen.
Zet die als taak in zijn lijst (skill omnivaleur-taken) en ga met de rest door.
