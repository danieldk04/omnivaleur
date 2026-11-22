---
name: omnivaleur-seo-nameting-26-nov
description: Eenmalige nameting op 26-11-2026 van de SEO-reparaties van 29 en 30-10-2026: beide rondes artikelen, hygiëne en Ahrefs-score.
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Lees eerst CLAUDE.md in die repo en volg de rapportagevorm (vier blokjes, Nederlands, gewone taal, nooit een streepje als leesteken, zekerheid in procenten, actiepunten met urgentielabel). Dit is een NAMETING: wijzig niets aan code, database of Cloudflare, tenzij Daniel er daarna zelf om vraagt.

Achtergrond: op 29-10-2026 zijn (1) de titel en omschrijving van acht artikelen herschreven en (2) de mailto-links in de footer buiten Cloudflare's e-mailherschrijving gezet (`<!--email_off-->`), omdat Ahrefs het adres /cdn-cgi/l/email-protection als kapotte link op 201 pagina's telde. Op 30-10-2026 volgden (3) een tweede ronde van acht artikelen, (4) kortere omschrijvingen op homepage, /nl, /register, /ai-info en alle toolpagina's, en (5) twitter:card en Open Graph op pagina's waar die misten. Zie docs/team-notes.md, secties "2026-10-29: Ahrefs en Search Console doorgelicht", "2026-10-29: Trustpilot..." en "2026-10-30: SEO-hygiëne en tweede ronde titels". Daar staan ook de oude titels.

Meet in Daniels Chrome (Claude in Chrome tools, laad ze met ToolSearch; open een eigen tabblad en sluit het daarna). Is Chrome niet verbonden, zeg dat dan in je rapport en meet wat zonder Chrome kan (curl).

A. Google Search Console, https://search.google.com/search-console/performance/search-analytics?resource_id=sc-domain%3Aomnivaleur.com&num_of_days=28&metrics=CLICKS%2CIMPRESSIONS%2CCTR%2CPOSITION&breakdown=page (28 dagen tot en met ongeveer 24-11; zet rijen per pagina op 100). Vergelijk per pagina met de meting van 30-09 tot 27-10-2026 (klikken / vertoningen / gemiddelde positie).
Eerste ronde (29-10), pad onder /reseller-tools/:
- best-time-to-post-on-vinted: 9 / 3.050 / 7,1
- marktplaats-fees-explained: 3 / 839 / 12,0
- how-does-marktplaats-buyer-protection-work: 1 / 607 / 7,3
- second-hand-sales-tax-belgium: 0 / 344 / 5,1
- how-to-avoid-selling-the-same-item-twice: 0 / 324 / 8,2
- how-to-create-bundles-on-vinted: 0 / 189 / 10,1
- dac7-vinted-reporting-rules-netherlands: 2 / 291 / 6,1
- how-to-photograph-clothes-for-vinted: 0 / 126 / 7,0
Tweede ronde (30-10), met het pad ervoor:
- /reseller-tools/margin-scheme-vat-second-hand-goods: 0 / 109 / 8,8
- /vs/omnivaleur-vs-crosslist: 0 / 77 / 5,2
- /vs/omnivaleur-vs-list-perfectly: 0 / 41 / 8,2
- /crosslisting/marktplaats-to-2dehands-crosslisting: 0 / 53 / 6,7
- /reseller-tools/how-to-price-second-hand-items: 0 / 38 / 6,9
- /crosslisting/shopify-to-vinted-crosslisting: 5 / 336 / 6,9
- /reseller-tools/vintage-book-reselling-automation: 0 / 121 / 7,9
- /vs/omnivaleur-vs-vendoo: 1 / 58 / 13,0
Totaal toen: 134 klikken, 9,4K vertoningen, CTR 1,4%, positie 8,1; waarvan 59 klikken op de zoekopdracht "omnivaleur". Noem het totaal nu en de CTR per pagina, en geef de twee rondes apart een oordeel (de tweede ronde had maar 4 weken tot de meting minus een dag). Let op: vertoningen schommelen, dus kijk naar CTR, niet alleen naar klikken. Staat de pagina er niet meer in, schrijf dat op.

B. Ahrefs, project Omnivaleur (id 10426457): https://app.ahrefs.com/site-audit/10426457/overview . Toen: Health Score 53, AI Discoverability 84, "4XX page" 1 pagina, "Page has links to broken page" 200, "Meta description too long" 20, "X (Twitter) card missing" 25, referring domains 289, Domain Rating 0. Noem de waarden nu. Is de laatste crawl niet recent (kijk de datum), zeg dat; start dan eenmaal "New crawl" als dat gratis kan en vermeld dat de uitkomst nog moet komen. Controleer ook via curl dat https://omnivaleur.com/ geen "cdn-cgi/l/email-protection" bevat, en dat het Trustpilot-blok (aggregateRating 4.0 uit 3 reviews) nog op / staat; kijk op https://nl.trustpilot.com/review/omnivaleur.com of het cijfer en het aantal reviews daar nog gelijk zijn. Zijn ze veranderd, meld dat dan als actiepunt (index.html en nl.html moeten mee), pas niets zelf aan.

C. Eindig met een eerlijk oordeel per reparatie: werkte het, niet te zeggen, of werkte het niet, met in één zin waarom. Is een titelwijziging niet beter, stel dan een nieuwe titel voor maar voer hem NIET door. Zet een korte regel met de uitkomst onderaan docs/team-notes.md (datum 2026-11-26), commit en push alleen dat bestand.

Gebruik Daniels Chrome-sessies zoals ze zijn; log nergens uit en wijzig niets in Ahrefs, Search Console of Cloudflare.