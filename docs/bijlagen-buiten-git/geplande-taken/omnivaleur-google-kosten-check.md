---
name: omnivaleur-google-kosten-check
description: Eenmalig: kijkt wat de betaalde Google-sleutel (Gemini) sinds 28-10-2026 kostte en of de rubriekvraag weer werkt.
---

Je werkt voor Daniel aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Volg CLAUDE.md van die repo en van ~ (Nederlands, gewone taal, de vier blokjes met urgentie per actiepunt, geen gedachtestreepjes, geen subagents, zuinig met beurten). Begin met `git log --since="3 days ago" --oneline` en lees in docs/team-notes.md de kopjes van 28-10-2026 over "Rubrieken zonder betaald taalmodel" en "Rubriek uit het Shopify-producttype" plus de regel "Vervolg 11:20".

Achtergrond: op 28-10-2026 om ~11:15 zette Daniel betaling aan op de Google-sleutel die de server gebruikt (Gemini, vingerafdruk 27d2bcd9 op /health), met 10 euro. Daarvoor gaf de gratis sleutel bijna alleen HTTP 429 en bleven rubrieken leeg. Daniel verwacht een paar euro per maand. Jij kijkt wat het echt kost en of het werkt.

Doe dit, alleen lezen, niets wijzigen of betalen:
1. Kosten: open in de ingebouwde browser https://aistudio.google.com (Usage/Billing of Spend) en daarna https://console.cloud.google.com/billing. Is Daniel daar ingelogd, lees dan het bedrag sinds 28-10 en het verbruik per dag. Is hij niet ingelogd: log nergens in, noteer dat je het niet kon zien.
2. Werkt het: curl https://omnivaleur.com/health en noteer taalmodel_sinds_start (google_codes http_200 tegen http_429, antwoord_door). Let op: die tellers beginnen opnieuw bij elke deploy.
3. Rubrieken: met /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 en backend.database.get_db, tel per user_id de items zonder rubriek (category leeg of null; op 28-10 waren het er 252, vooral 31d28378 Janneke 158, 5aae4954 Goudlief 39, 96e30080 Toon 30, 0b28c1ce 22) en lees de nieuwste rubriek_gepoogd_op. Alleen per user_id of met een filter op category, nooit jobs.result over meerdere klanten.
4. Hoger dan ~1 euro per dag, of veel meer vragen dan verwacht: zoek wat de vragen opslokt (backend/services/taalmodel.py, gemini_vertaling.py; vertalen bij grote plaatsingsrondes is de bekende verdachte) en beschrijf het met getallen. Repareer niets zonder bewezen oorzaak.
5. Zet de uitkomst onderaan docs/team-notes.md onder "## DD-MM-JJJJ: Google-kosten na betaling" en commit en push.

Rapporteer aan Daniel in de vier blokjes: wat het kostte (of dat je het niet kon zien), of Google antwoordt, hoeveel lege rubrieken er nog zijn tegen 252, en of hij iets moet doen. Kon je de kosten niet zien, dan is het actiepunt voor hem: zelf in AI Studio kijken, met de exacte plek.