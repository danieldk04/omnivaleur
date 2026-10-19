# Te bouwen: de centrale lijst

Eén plek voor alles wat klanten vragen of wat we zelf willen bouwen. Daniel, Claude en de
tweede ontwikkelaar kijken hier eerst. Daniel mag overal in schrijven, Claude werkt het
bij in dezelfde beurt als er iets nieuws binnenkomt.

Laatst bijgewerkt: 19-10-2026. De eerste vulling komt uit team-notes en overdracht; wat daar
niet in staat, ontbreekt hier ook. Vul gerust aan.

## Hoe je dit leest

Status: **Gepland** (we gaan het doen), **Overwegen** (nog geen besluit), **Uitgesteld** (Daniel
zei bewust "later"), **Bezig**, **Klaar** (blijft hieronder staan met datum), **Nee** (besloten
niet te doen, met reden).

Prioriteit: **Hoog** (kost klanten of omzet), **Midden**, **Laag**.

"Keer gevraagd" telt verschillende klanten die erom vroegen. Elke nieuwe vraag: teller omhoog,
klantnaam erbij. Zo zie je wat het vaakst terugkomt.

## Wat nu op de planning staat

| Wat | Status | Prio | Keer gevraagd | Wie vroeg erom | Bron en opmerking |
|---|---|---|---|---|---|
| Etsy als kanaal (echte koppeling met inlog) | Gepland | Hoog | 1 | Voordeelsieraden | Daniel zei 19-10 "binnen afzienbare tijd" toe. In de code staat alleen een kale aanzet uit juli (`backend/platforms/etsy.py`), niet bruikbaar. Etsy is voor hen de plek voor de duurdere stukken. |
| Alle Shopify-tags meenemen bij import | Bezig | Midden | 2 | Voordeelsieraden, Janneke | SKU komt al mee. Tags deels, zie ook geslacht uit labels. |
| Doorplaatsen vanuit Shopify zonder eigen klik | Overwegen | Midden | 2 | Voordeelsieraden, Toon | Nu draait de import elk uur, plaatsen is een eigen klik. Daniels advies aan klanten is plaatsen vanuit Omnivaleur. |
| AI-titels voor Marktplaats en 2dehands (titels boven 60 tekens) | Uitgesteld | Midden | 1 | Goudlief | Module `backend/services/titel_ai.py` is gebouwd en getest, niet aangesloten. Kost ~0,2 cent per 15 titels. Detail in team-notes 07-10-2026. |
| Rubriekvraag bij importeren kleiner maken | Uitgesteld | Laag | 0 | Intern | Nu ~9.000 tokens per product. Alleen de passende tak meesturen scheelt ~10x, maar raakt rubriekkwaliteit: eerst voor en na meten. |
| Omzet uit voorraadverkopen in Analytics | Uitgesteld | Laag | 0 | Intern | Daniel 08-10: "gaan we ooit doen, niet nu". Niet zelf oppakken. |
| Aangevuld voorraadartikel komt vanzelf terug op andere kanalen | Uitgesteld | Laag | 0 | Intern | Zelfde besluit van 08-10. |
| Prijs naar aantal advertenties | Uitgesteld | Laag | 1 | Toon (280 advertenties, zelfde prijs als 25) | Eerst moet het dashboard echt goed werken. |
| Land en woonplaats van de verkoper in Omnivaleur zetten (voor Marktplaats-formulier) | Overwegen | Midden | 0 | Intern | Wacht op Daniels besluit, vraagt een Web Store-release van weken. Team-notes 10-09. |
| Regel bovenaan dashboard: "X artikelen staan maar op één kanaal" met klik die ze selecteert | Overwegen | Laag | 1 | Janneke | Voorstel van 10-09, nooit besloten. |
| Marktplaats gratis verlengen (zoals 2dehands) onderzoeken | Overwegen | Laag | 0 | Intern | Onbekend of Marktplaats dezelfde knop heeft. Herplaatsen is bij ons weghalen en opnieuw plaatsen en kan geld kosten. |

## Wat klanten het vaakst vragen

Telt alleen wat in de notities staat. Vul aan bij elke nieuwe vraag.

| Vraag of wens | Keer | Klanten | Antwoord nu |
|---|---|---|---|
| Koppeling met WooCommerce | 2 | Borstelbeer, Vianen Telecom | Klaar sinds 09-10 (één klik via /wc-auth). |
| Dashboard in het Nederlands | 1 | Klant uit 08-2026 | Klaar sinds 24-09. |
| Vanaf eigen webshop doorplaatsen | 2 | Toon, Voordeelsieraden | Via Shopify-import, daarna eigen klik. Zie boven. |
| Shopify-import van producten | 1 | Budgetheld | Klaar. |
| Etsy | 1 | Voordeelsieraden | Gepland. Zie boven. |
| AI die vanaf een foto de rest invult | 1 | Vianen Telecom | Niet gebouwd, geen besluit. |
| Titels verbeteren met AI | 1 | Goudlief | Uitgesteld. Zie boven. |
| Herplaatsen op vaste dag en uur | 1 | Voordeelsieraden | Klaar 19-10. |

## Klaar

| Wat | Datum | Opmerking |
|---|---|---|
| Herplaatsen op vaste dagen en een vast uur | 19-10-2026 | Niet getest: een echte herplaatsronde op een gekozen uur. |
| WooCommerce-koppeling | 09-10-2026 | |
| Nederlandse vertaling dashboard | 24-09-2026 | |
| Omnivaleur Light (9,99, tot 20 artikelen) | 30-09-2026 | |

## Nee, bewust niet

| Wat | Reden |
|---|---|
| Bol.com-koppeling | Tweedehands alleen boeken, muziek, games, films, en EAN en KvK zijn verplicht (29-09). |
| Foto's croppen om herkenning te ontwijken | Vinted eist onbewerkte eigen foto's. |
