# Platformcontrole (dagelijks 06:00)

Daniel, 24-10-2026. Doel: weten dat een platform zijn velden, knoppen of maten heeft veranderd VOORDAT een
klant het merkt. Aanleiding: 23-10 liet Vinted de maat bij kinderschoenen "EU 26" heten, 12 plaatsingen van
Janneke mislukten. Kanalen: Vinted, Marktplaats, 2dehands. (eBay, Facebook, Shopify, WooCommerce bewust niet; Daniel kan ze later toevoegen.)

Besluiten van Daniel: zelf repareren en live zetten; alleen melden bij een afwijking; geen bericht als alles klopt.

## Methode: echte code op de echte pagina, zonder te plaatsen

Niet de HTML vergelijken met een lijst, maar de echte extensiecode (main) op de levende pagina laten invullen en
kijken welke stap faalt. Dat vond op 24-10 de oorzaak in één run.

Vinted: `scripts/platformcontrole/vinted_loader.js`. Open in Daniels Chrome (Claude in Chrome, hij is ingelogd,
geen wachtwoorden invoeren) een NIEUW tabblad op https://www.vinted.nl/items/new, zet `window.__PROEF = {item, ref:"main"}`
en voer het bestand uit via javascript_tool. Na 60 s: `__LOG` filteren op "stap" en `__DONE`. Een stap size, category,
brand, colour, condition of price die "NIET gelukt" meldt is een afwijking. De eindfout over "description" is een
artefact van de proef, negeren. Sluit het tabblad daarna (er staat een half formulier open, nooit opslaan, nooit plaatsen).
Foto's: gebruik `https://img.omnivaleur.com/...` of een publieke afbeelding, bijvoorbeeld
https://raw.githubusercontent.com/danieldk04/omnivaleur/main/frontend/assets/blog/hero/2dehands-naar-ebay-crosslisting-nl.jpg (drie keer).

Proefartikelen (payload zoals de server uitdeelt: title, description, size, brand, color, price, condition, category,
gender, photo_urls). Elke ochtend deze set, één per rubriekgroep, categorie-sleutels uit CAT_HINTS/V_PAD:
1. kinderen schoenen, maat "EU 26" (zo geeft de server hem uit)
2. meisjes kleding (jas), maat "116"
3. sneakers dames, maat "38"
4. heren (shirt), maat "M"
5. babykleding meisjes, maat "74"
6. een niet-kledingrubriek met V_PAD (bijvoorbeeld wonen wanddecoraties of een boek)
Wisselt Vinted de taal of een label, dan zie je dat in dezelfde run.

Marktplaats en 2dehands: dezelfde aanpak met marktplaats.js / tweedehands.js (zelfde berichten: GET_JOB, LOG, JOB_DONE,
JOB_ERROR). Bij de eerste run bouw je de loader zelf naar het model van vinted_loader.js, op https://www.marktplaats.nl/plaats
(en 2dehands.be/plaats), blokkeer elke plaats-POST, en bewaar hem als scripts/platformcontrole/marktplaats_loader.js.
Let op: Marktplaats noemt velden in data-testid en gaf op 21-10 de beschrijvingseditor een nieuw kenmerk
(DescriptionEditor); 14-10 en 23-10 ook vertaalde vensters. Lees bij elke run ook de rubriekboom-ids uit
`tests/fixtures/marktplaats_nieuwe_takken_24-09-2026.json` na op drie willekeurige rubrieken.

## Bij een afwijking

1. Zoek de oorzaak tot je het mechanisme kunt aanwijzen (welke testid of label, wat de code verwacht). Meet, geen gokwerk.
2. Kan de server het opvangen (zoals `_vinted_schoenmaat_als_eu` in backend/api/jobs.py)? Dan daar, werkt direct op elke kopie.
3. Anders de extensiecode repareren, test schrijven die op de oude code faalt (voor en na), manifest bumpen,
   `build-extension.sh`, Daniel vragen de zip op de Web Store te zetten.
4. Test draaien, committen, pushen, uitrol controleren via /health.
5. Raakt het klanttekst: i18n. Raakt het wat klanten merken: updatelog (zie CLAUDE.md).
6. Is er een lopende klant geraakt (mislukte plaatsingen)? Meet via jobs (per user_id), meld het Daniel met de naam. Nooit
   klantdata op eigen initiatief wijzigen.
7. Schrijf een regel in docs/team-notes.md. Meld in de chat de vier blokjes uit CLAUDE.md.

## Klopt alles

Geen bericht aan Daniel. Alleen één regel in docs/team-notes.md met datum, kanalen en "geen afwijking".
Verder niets: geen extra controleronde, geen documentatie.

## Randvoorwaarden

- Draait op Daniels Mac met Chrome open en Claude in Chrome verbonden. Is Chrome niet bereikbaar, schrijf dat in team-notes
  en meld het alleen als het twee dagen achter elkaar gebeurt.
- Eerst lezen wat veranderd is (git log, team-notes), zoals altijd. Raak de werkmap van andere sessies niet aan: commit
  alleen je eigen bestanden.
