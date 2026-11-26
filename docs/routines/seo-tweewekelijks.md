# SEO-routine, elke twee weken (Daniel, 26-11-2026)

Doel: meetbaar meer klikken uit Google zonder Google te storen. Rustig en lang meten, weinig wijzigen.

## Regels die niet onderhandelbaar zijn
- Een pagina krijgt hoogstens één titel- of omschrijvingswijziging per 8 weken. Zie het leerlog voor de datum van de laatste wijziging.
- Beoordeel altijd met 28-dagenvensters uit Search Console (CTR en positie), nooit met losse dagen. Vergelijk met het venster ervoor.
- Maximaal 3 pagina's wijzigen per ronde. Geen massale herschrijving.
- Geen nieuwe artikelen toevoegen en niets publiceren. Dat doet de bestaande dagelijkse blogmachine.
- Titel in de taal van de pagina. Klanttekst blijft tweetalig volgens CLAUDE.md. Geen streepje als leesteken.

## Stappen
1. Lees `docs/seo-leerlog.md` (maak hem aan als hij niet bestaat: kolommen pagina, datum wijziging, oude titel, nieuwe titel, CTR/vertoningen/positie ervoor).
2. Meet in Daniels Chrome (Claude in Chrome, eigen tabblad, daarna sluiten; niet uitloggen, niets wijzigen in Search Console of Ahrefs): Search Console, 28 dagen, per pagina, 250 rijen. Is Chrome niet verbonden of Ahrefs niet ingelogd: zeg het in het rapport en doe de rest.
3. Beoordeel wijzigingen die 28 dagen of ouder zijn: CTR omhoog, gelijk, of omlaag bij gelijke positie? Schrijf het oordeel in het leerlog. Werkte een titel niet, draai hem pas terug als hij 8 weken oud is, anders laten staan.
4. Kies de kandidaten voor deze ronde: boven 500 vertoningen in 28 dagen, positie onder 10, CTR onder 1%, en niet gewijzigd in de laatste 8 weken. Sorteer op gemiste klikken (vertoningen maal 1% min klikken). Neem de top 3.
4b. Concurrentieanalyse per kandidaat (blogartikel of toolpagina, Daniel 26-11-2026):
   - Het zoekwoord is de zoekopdracht met de meeste vertoningen voor die pagina in Search Console (tab Zoekopdrachten, gefilterd op de pagina).
   - Zoek dat zoekwoord op in Google (google.nl voor NL-pagina's, google.com voor EN, in Daniels Chrome) en noteer de top 5 organische resultaten. Stuit je op een CAPTCHA of toestemmingsmuur: omzeil hem niet, gebruik dan WebSearch en zeg in het rapport dat de volgorde bij benadering is.
   - Open elk van die 5 pagina's en noteer: titel en omschrijving, H1 en H2's, lengte, soort pagina (gids, tool, vergelijking), wat ze behandelen, tabellen, voorbeelden of rekentools, FAQ, datum van bijwerken, structured data, hoe snel de belofte van de titel wordt ingelost.
   - Zet naast onze pagina: wat zij allemaal hebben en wij niet (hiaten), wat wij hebben en zij niet (voordeel), wat zij zwak doen (verouderd, te algemeen, geen tool, geen cijfers), en wat het zoekopzet is (informatie, vergelijken, rekenen).
   - Schrijf dat als korte tabel in `docs/seo-leerlog.md` bij de pagina, met de datum.
   - Gebruik het zo: de titel en omschrijving sluiten aan op wat de top 5 laat zien dat zoekers willen en wat zij missen. Ontbreekt er inhoud die alle top-5-pagina's hebben (een tabel, een rekentool, een sectie), voeg die dan aan onze pagina toe, in eigen woorden en met onze eigen cijfers. Nooit tekst of structuur van een concurrent overnemen. Bij een hiaat dat te groot is voor deze ronde: zet het als voorstel in het rapport en in de te-bouwen-sheet.
   - Reken geen cijfers van concurrenten als feit: noem alleen wat je zelf op hun pagina hebt gezien.
5. Schrijf per kandidaat een nieuwe titel (hooguit 60 tekens, het zoekwoord vooraan, een concrete belofte of getal) en omschrijving (hooguit 155 tekens). Pas de bron aan (database `content_pages` of het template), test, push, controleer `https://omnivaleur.com/health` op jouw commit en controleer de titel op de live pagina.
6. Ahrefs: start "New crawl" in Site Audit (project 10426457), wacht tot hij klaar is en lees Health Score, fouten en waarschuwingen. Nieuwe fouten die in onze code zitten: repareer en push. Controleer ook dat een gelijktijdige belasting geen 502 geeft (zie team-notes 26-11).
7. Eens per kwartaal (eerste ronde van januari, april, juli, oktober): pagina's met 0 vertoningen en 0 klikken over 90 dagen voorstellen om samen te voegen of door te verwijzen, zoals op 25-09-2026. Alleen voorstellen in het rapport, niets verwijderen zonder Daniel.
8. Werk `docs/seo-leerlog.md` en `docs/team-notes.md` bij, commit en push, rapporteer in de vier blokjes van CLAUDE.md.

## Wat deze routine bewust niet doet
Geen nieuwe zoekwoorden zoeken (doet `keyword_planner.py`), geen social trends (doet de trendmotor), geen wijzigingen aan pagina's jonger dan 8 weken sinds de laatste wijziging.
