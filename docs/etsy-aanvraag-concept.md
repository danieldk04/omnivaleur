# Etsy API-aanvraag: concept voor een nieuwe poging (25-11-2026)

Status: CONCEPT, niet ingediend. De tekst van de eerste aanvraag (16-11) staat in geen enkel
bestand of sessielog; Daniel kan hem terugvinden in de ontwikkelaarsportal onder "Apps You've Made".
Vergelijk dit concept daarmee voor je iets indient.

Uitgangspunten (bronnen: etsy.com/nl/legal/api, bijgewerkt 05-11-2026, en developer.etsy.com/documentation):
- Eerlijk en concreet. Niets verzwijgen over meerdere verkopers; een Personal App is volgens Etsy juist
  bedoeld voor "tools die andere kopers of verkopers op beperkte schaal kunnen gebruiken".
- Geen Commercial Access aanvragen in dezelfde ronde. Meldingen op GitHub (etsy/open-api #1663) zeggen dat
  dat een hele app kan laten blokkeren. Niet geverifieerd.
- Geen nieuw account of andere naam om een blokkade te omzeilen.

## Tekst voor het veld "wat doet je app" (Engels, zoals het formulier)

Omnivaleur is a listing-management tool for sellers of second-hand and vintage goods in Europe who already
sell on other marketplaces (Vinted, Marktplaats, eBay). For sellers who connect their own Etsy shop through
OAuth, the app does four things, and nothing else:

1. Creates a listing in the seller's own shop from an item the seller has already prepared in Omnivaleur
   (title, description, tags, photos, price, who_made/when_made/taxonomy). Only items that qualify as vintage
   (20+ years) or other categories Etsy allows are offered for Etsy. One-of-a-kind items, quantity 1.
   Scopes: listings_w.
2. Reads the seller's own listing state, to avoid creating duplicates (listings_r).
3. When the same item sells on another marketplace, deactivates or removes that seller's Etsy listing so it
   cannot be sold twice (listings_w, listings_d).
4. Reads the seller's own receipts, to detect an Etsy sale so the item can be removed elsewhere
   (transactions_r). We do not request buyer_email.

Etsy remains the sales and payment platform: we do not redirect buyers, do not process payments, do not
replace any Etsy feature, do not scrape, do not use a browser extension on Etsy, do not use Etsy data for AI
training, analytics or advertising, and do not share data with third parties. Initial scale: fewer than 10
sellers, each connecting only their own shop. Requested access level: Personal App.

## Voor je het indient (alles moet waar zijn)
- [ ] De openbare site noemt de zin: "The term 'Etsy' is a trademark of Etsy, Inc. This application uses the
      Etsy API but is not endorsed or certified by Etsy, Inc." op de pagina die je bij de aanvraag opgeeft.
- [ ] Zichtbaar supportadres, voorwaarden met click-through en een garantieafwijzing, privacybeleid (API-voorwaarden §3).
- [ ] Een aparte pagina "Etsy" die precies de vier punten hierboven beschrijft, zonder beloftes over datum.
- [ ] Prijs: API-voorwaarden §5 verbiedt kosten voor "een deel dat Etsy gratis aanbiedt". Besluit van Daniel
      nodig: Etsy zonder extra kosten in elk plan, of juridisch toetsen. Nu staat Etsy als Ultra-voordeel (49 euro).
- [ ] Geen "Etsy" in de appnaam. "omnivaleur" is goed.
- [ ] Aanvrager en Etsy-account kloppen met wie de app beheert; het geblokkeerde account eerst oplossen.
- [ ] Opslag: Etsy-listinginhoud niet langer dan 6 uur oud tonen, overige Etsy-inhoud 24 uur (§5).

## Het echte formulier (etsy.com/developers/register, geplakt door Daniel 25-11) en wat ik invul

Nieuw uit het formulier zelf:
- Etsy schrijft: gebruikers opdragen hun eigen API-sleutel te maken is tegen de API-voorwaarden. Een
  sleutel per klant (Seller-App-route) valt dus af.
- API-testbeleid: voldoen je Etsy-account en shop niet aan Etsy's beleid, dan "wordt je aanvraag mogelijk
  afgewezen". Daniels account is geblokkeerd. Dat is een concrete, waarschijnlijke reden voor de afwijzing
  van 16-11 en moet eerst opgelost zijn, ook met een perfecte tekst.

Velden:
| Veld | Antwoord | Waarom |
|---|---|---|
| Name | omnivaleur | Geen "Etsy" in de naam. |
| Describe your application (max 500, alleen Etsy ziet het) | zie tekst hieronder (483 tekens) | Concreet doel, vooraf te beoordelen (§3). |
| Website URL | omnivaleur.com, bij voorkeur een eigen Etsy-pagina met trademarktekst, support, voorwaarden, privacy | Etsy beoordeelt ook de site. |
| Type | Seller Tools | |
| Gebruikers | A small group of users | Eerlijk: beperkte schaal, geen "general public". |
| Commercial? (rekenen jullie geld om de app te gebruiken) | Yes | De app is betaald; "No" zou onwaar zijn. Het Etsy-deel zelf is gratis (zie tekst). |
| Upload or edit listings | aan | |
| Read sales data | aan | Nodig om een Etsy-verkoop elders weg te halen. |
| Send email | uit | We mailen niet via Etsy. |

Tekst voor "Describe your application":

> Omnivaleur helps second-hand and vintage sellers keep one-of-a-kind items in sync across marketplaces (Vinted, Marktplaats, eBay). With each seller's own OAuth consent, the app (1) creates listings in their own shop for vintage items, (2) reads their listings to avoid duplicates, (3) removes a listing when the item sells elsewhere, (4) reads their receipts to detect Etsy sales. No scraping, no extension on Etsy. Start: under 10 sellers. The Etsy connection is free in every plan.

Prijs: de zin "free in every plan" is alleen toegestaan als dat bij livegang ook zo is. Besluit Daniel 25-11:
voor de aanvraag nemen we Etsy op in elk plan; het dashboard, de plannen en de Ultra-tekst veranderen NIET
(geen instelling, niets doorgevoerd). Let op: wordt Etsy later toch alleen voor Ultra, dan wijkt de app af van
het goedgekeurde doel (API-voorwaarden §3 en §5) en kan Etsy de toegang intrekken. Beslis dat voor je indient.
