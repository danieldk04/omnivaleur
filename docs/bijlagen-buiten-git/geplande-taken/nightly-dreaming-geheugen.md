---
name: nightly-dreaming-geheugen
description: Nachtelijke Dreaming-sessie: leest de gesprekken van de afgelopen dag en werkt Daniels geheugen-notities bij
---

Je draait een autonome "Dreaming"-sessie voor Daniel. Doel: leren van de gesprekken van de afgelopen 24 uur en zijn persistente geheugen bijwerken, zonder dat hij iets hoeft goed te keuren.

STAP 1 — Verzamel de gesprekken van de afgelopen dag:
Draai: find /Users/Danie/.claude/projects -name "*.jsonl" -mtime -1
Lees per bestand alleen de user-berichten en de laatste assistant-tekst eruit, bijvoorbeeld met een klein python3-script dat elke regel als JSON parst en velden pakt waar type == "user" of "assistant" en message.content een string is. Grote bestanden: beperk tot de laatste ~400 regels per bestand (tail). Sla het transcript van deze Dreaming-taak zelf over.

STAP 2 — Filter slim:
Zoek naar terugkerende signalen over HOE Daniel wil werken en wie hij is:
- correcties ("nee, niet zo", "ik wil dat je...", "stop met...", herhaalde herformuleringen)
- expliciete voorkeuren over toon, taal, lengte, tools, workflow
- vaste feiten over zijn projecten, bedrijven en doelen die niet uit de code of git-historie blijken
- externe bronnen die hij vaker gebruikt (URL's, dashboards, sheets)
Negeer: eenmalige toevalligheden, alles wat al in /Users/Danie/CLAUDE.md of in een bestaande geheugen-notitie staat, en alles wat alleen binnen één gesprek relevant was. Sla NOOIT tokens, wachtwoorden, API-keys of andere credentials op — als je die tegenkomt, noteer alleen dat ze in de chat stonden en dat ze geroteerd moeten worden.

STAP 3 — Schrijf geheugen:
Map: /Users/Danie/.claude/projects/-Users-Danie-Downloads/memory/
Eén feit per bestand, met frontmatter:
---
name: <korte-kebab-case-slug>
description: <één regel samenvatting>
metadata:
  type: user | feedback | project | reference
---
Daarna de inhoud; bij feedback/project ook regels **Why:** en **How to apply:**. Verwijs naar verwante notities met [[naam]]. Zet relatieve datums om naar absolute datums.
Controleer eerst of er al een bestand bestaat dat dit onderwerp dekt — werk dat dan bij in plaats van een duplicaat aan te maken. Verwijder notities die inmiddels aantoonbaar onjuist zijn.
Voeg voor elke nieuwe notitie één regel toe aan MEMORY.md in dezelfde map: - [Titel](bestand.md) — korte haak. MEMORY.md bevat alleen die index-regels, nooit inhoud.

STAP 4 — Rapporteer kort:
Sluit af met maximaal 5 regels in het Nederlands, in gewone taal: wat je hebt geleerd, wat je hebt bijgewerkt, en wat er is weggelaten. Geen jargon, geen codeblokken. Als er niets nieuws te leren viel, schrijf dan alleen: "Niets nieuws geleerd vannacht."