# Revaleur-herbouw, fase 2: ontwerp (27-11-2026)

## Architectuur
```
Omnivaleur-database (items, listings)  --export-->  catalogus.json  --bouw-->  statische site (EN + NL)
                                                                                  |  Cloudflare Pages (gratis, CDN)
browser --(winkelmand in localStorage)--> /api/revaleur/checkout (Railway, bestaande backend)
                                              |  reserveert artikelen, maakt Stripe Checkout-sessie
Stripe --webhook--> /api/revaleur/stripe-webhook --> order opslaan, handle_item_sold(bewijs=bestelling), mail via Resend
```
- Winkelkant is volledig statisch: productpagina's, collecties, zoeken (client-side index), maattabel, beleid. Valt onze backend uit, dan blijft alles zichtbaar; alleen "Afrekenen" toont een duidelijke melding en een nieuwe poging.
- Eén exemplaar per artikel: checkout reserveert de artikelen 30 minuten (tabel `revaleur_reserveringen`), een tweede koper krijgt "net verkocht". Mislukte of verlopen betaling geeft vrij (Stripe-event `checkout.session.expired`).
- Voorraad en prijzen: bron is de Omnivaleur-database. Een koppeling (bouwtaak, elke 10 minuten en na elke verkoop) bouwt alleen opnieuw als de catalogus veranderd is en zet de site via Cloudflare Pages deploy hook live. Verkocht artikel verdwijnt binnen minuten; tot die tijd vangt de checkout het af.

## Catalogus (gemeten)
- Winkel toont 258 producten; alle 258 zijn in de database een actieve Shopify-advertentie van gebruiker 3bfbed2c (Revaleur, SKU-voorvoegsel REV-/nummers). Er zijn 48 extra actieve advertenties die niet publiek staan (concept of verborgen): die komen NIET op de nieuwe site.
- 52 van de 258 hebben in de database een andere prijs dan Shopify nu toont. Voor de gelijkwaardigheid geldt de Shopify-prijs (`price_shopify`, anders `price`); verschil eerst naast elkaar leggen voor de omzetting (fase 7).
- Titels hebben het Shopify-formaat; NL-teksten komen uit `title_en`/vertaalvelden of worden met de bestaande vertaalstap aangemaakt.

## Betalen
Stripe Checkout (iDEAL, kaart; PayPal en Klarna alleen als Stripe ze voor dit account aanzet). Verzendkosten volgens het huidige beleid: NL en BE gratis, EU €3,95 en buiten EU €4,95, gratis vanaf €100. Stripe-account: Daniel beslist of dit het Omnivaleur-account is of een apart Revaleur-account (aanbevolen: aparte, voor boekhouding en margeregeling); sleutels via request_credential/Railway door Daniel.

## Wettelijk (VOOR bouwen vastleggen, bron erbij)
Nog uit te zoeken en met bron in `docs/revaleur-wettelijk.md` te zetten: margeregeling tweedehands (factuur zonder btw-bedrag, vermelding), bewaarplicht 7 jaar, 14 dagen herroeping, OSS bij verkoop naar andere EU-landen (zie `docs/routines/oss-aangifte.md`), cookiebanner (alleen noodzakelijke cookies = geen banner nodig; Meta-pixel vraagt wel toestemming).

## Bouwvolgorde
1. `scripts/revaleur_catalogus.py` (database naar catalogus.json) en `scripts/revaleur_bouw.py` (statische site, EN+NL, sitemap, 301-lijst, JSON-LD, Merchant- en Meta-feed).
2. `backend/api/revaleur_shop.py` plus `schema`-wijziging: checkout, webhook, reserveringen, orders, mails.
3. Testdomein op Cloudflare Pages (Daniel maakt het account en koppelt de repo, eenmalig), proefbestellingen.
4. Omzetten, bewaking (`docs/routines/revaleur-sitecheck.md`).
