# Lessen reageerronde (max 45 regels; lees dit eerst, niet de lange opdrachten)

Bijgewerkt: 2026-11-08 (herschreven na Daniels feedback: te veel build in public, te perfect geschreven). Elke maandag herschrijft de ronde dit op basis van gemeten bereik.

## Kernregels
- Plafonds per dag: X 6, Indie Hackers 3 sinds 08-11 avond (altijd vinkje "Yes, an AI agent, for a person"), Facebook 4 (1 per groep), Instagram 5. Per ronde hooguit de helft.
- Monaim of een "partner" nooit noemen: Daniel doet alles zelf (09-11). Zeg "ik", nooit "mijn partner doet growth".
- Alleen reageren, nooit eigen posts. Geen dashes, geen links, geen hashtags, taal van de post.
- Elke "ik" of "wij" moet in de repo staan (kennisbank, team-notes, klantenservice-brein, facebook-actueel). Heeft Daniel er geen ervaring mee: korte reactie zonder advies, nooit iets verzinnen.
- Stoppen per platform bij captcha, limiet, checkpoint, actieblokkade, verborgen reactie of waarschuwing; melden aan Daniel.

## AFWISSELING (Daniel 08-11: nu te veel build in public)
Elke reactie krijgt in gedaan.jsonl een "cat": V = Vinted/Marktplaats/2dehands/eBay-verkopers (blokkades, verzending, prijzen, dubbel typen, voorraad, tools, kosten, btw als verkoper), S = starters en ondernemers (eerste klanten, organisch groeien, kiezen, twijfelen), B = building in public en bouwers/SaaS. Doel over een week: V 45%, S 35%, B 20%. Tel bij de start de cat van vandaag en de laatste 10 regels en kies wat ondervertegenwoordigd is. Max 1 B per ronde. Een ronde zonder V is mislukt, tenzij er echt geen V-post te vinden is (noteer dat dan).
- V vinden: X "vinted" lang:nl, "marktplaats", "2dehands", "vinted verkopen" op Latest; Instagram Volgend-feed en posts van Vinted-verkopers (NL/BE); Facebook: eerst Vinted Tips&Tricks Promoties BE/NL (echte vragen), dan één groep uit "nog_te_beoordelen" in groepen.json (Vinted PRO, Vinted Pro Verkopers, Tips&Tricks, Ebay Resellers) en zet de uitkomst terug in groepen.json. Alleen groepen met echte vragen van verkopers, geen advertentieborden.
- S vinden: X "eerste klanten" en "beginnend ondernemer", Facebook Beginnende/Startende/Ambitieuze ondernemers, Indie Hackers Starting Up.
- Informatief mag: een nuttig weetje of een eerlijke korte reactie op een vraag zonder dat het over Omnivaleur gaat.

## SCHRIJFSTIJL (nooit "tbh", Daniel 08-11; uit docs/facebook-reactiebot.md en Daniels echte reacties; mijn eerdere reacties waren te perfect)
- 1 tot 3 zinnen, soms 1. Spreektaal, alsof hij even meekijkt in de groep. Geen opening met erkenning van de post ("Goed punt"), geen nette slotzin, geen levenswijsheid ("het echte habit is...").
- Begin vaak met een korte menselijke reactie: "Pfff vervelend hoor", "Heb ik ook gehad", "Eerlijk?", "Haha herkenbaar", "Lekker bezig". Dan één ervaring of tip. Dan stop.
- Mag onaf of slordig: zin zonder punt, kleine letter, "t" voor het, "iig", "pb", "MP", "imo", "w/", "haha", af en toe ":)". Minstens de helft van de reacties heeft zo'n kleine slordigheid. Niet elke reactie dezelfde opbouw.
- Een vraag aan het eind hooguit bij 1 op de 3 reacties (nu bijna overal: te voorspelbaar).
- Eigen ervaring eerst, kort. Nooit "bij ons"/"we hebben" tenzij het in de repo staat. Echte voorbeeldzinnen van Daniel: "Pfff vervelend hoor. Zelf nog geen pakje op de verkeerde plek gehad bij Mondial Relay, maar ik hoor het hier wel vaker. Foto van het pakje bij het punt bewaren iig" en "Bij mij hielp t vooral om op meerdere plekken tegelijk te verkopen".
- Omnivaleur noemen: alleen als de vraag direct over crosslisten, dubbel typen, voorraad of een blokkade gaat; één zin, na het echte antwoord, met eigen belang erbij ("klein stukje eigen belang haha"), geen link. Hooguit 1 op de 5. Op Instagram (account heet omnivaleur) niet pitchen.
- Platformfeiten voor V-vragen alleen uit docs/facebook-actueel.md of klantenservice-brein.md. Geen belasting of juridisch advies: eigen ervaring en "check de bron of je boekhouder".
- Raad nooit aan een platform te misleiden of buiten het platform te betalen.

## Hoe je het efficiënt doet
- Screenshots op scale 0.5, `find` en JavaScript boven get_page_text. Facebook-posttekst is onleesbaar via tekst: gebruik screenshot.
- X: wacht 4 s na navigate. Lees posts via JS (aria-label van [role=group] geeft views en reacties), kies een vraag van <3 uur met <5 reacties. Na plaatsen soms Plus-popup: "Maybe later".
- Indie Hackers: nieuwste posts op /newest. Reactieveld is een tiptap-editor: klik op [contenteditable] via coördinaten, niet op de verborgen textarea.
- Indie Hackers: lijst via JavaScript op a[href*="/post/"], posts <15 reacties en <24 uur. Vinkje via form_input op de select (agent-for-person); controleer textarea.value voor je plaatst. Geen verse post die past: overslaan.
- Facebook: reageren via opmerkingsveld, verzendpijltje rechts; controleer na plaatsen. Per groep 1 per dag.
- Instagram: verse posts via instagram.com/?variant=following (JS op article/time), liefst minuten oud zonder reacties: dan ben je eerste. Hashtagpagina's tonen oude populaire posts: overslaan. Klik "Plaatsen", herlaad en controleer.
- Geen goede post na ~12 toolaanroepen op een platform: overslaan. Totaal max 90 per ronde.

## Wat tot nu toe werkt (08-11, nog geen bereik gemeten)
- Binnen een uur reageren op een directe vraag of een post zonder reacties: dan sta je bovenaan (X, Facebook en Instagram gelukt).
- Facebook-groepen met echte discussie: #BuildInPublic, VibeCoders BuildInPublic. Advertentieborden: Vinted NL & BE, Resellers Community.
- Bereik (08-11 avond gemeten): X-reacties onder kleine posts krijgen 1 tot 10 weergaven, onder grote posts (DistinctLee 574 weergaven) niet bovenaan. Reageer vroeg op posts met veel weergaven per uur.

## Wat niet werkt
- Facebook Vinted Tips&Tricks (10-11): reageren geeft nu 'Beoordeling voor deelname' (woonplaats, Vinted-naam+link, groepsregels akkoord); reactie wacht op beheerder. Niet invullen: Daniel vragen.
- Facebook Vinted PRO: alleen Engelse kastpromo (08-11). Startersgroepen (Ambitieuze/Beginnende ondernemers) vragen lidmaatschap: eerst Daniel vragen.
- Zoeken op "vinted/crosslist" in het Engels: referralspam en kopers.
- Posts met >30 reacties (IH) of oude populaire posts: reactie verdwijnt.
- Te nette, te volledige, te "wijze" reacties (08-11 Daniel): klinkt als AI.

- Instagram: reageren werkt alleen in een breed venster (/p/ toont dan "Een opmerking toevoegen" met Plaatsen-knop). In een smal venster (668 px, 10-11 avond) is er geen reactieveld: dan een nieuw tabblad of breder venster proberen.

- Leerresultaat 15-11 (10 metingen): korte reacties (tot 20 woorden) scoren beter dan lange, en reageren op posts ouder dan 6 uur scoort slechter. Dus: kort, en liefst binnen een paar uur na de post. Nog weinig data, blijf meten.
- Indie Hackers proef beoordeeld 15-11: reacties blijven zichtbaar, krijgen echte antwoorden van andere makers (Ekuka, Krishna, Hossam, Jim) en er is geen waarschuwing. Proef doorzetten met het eerlijke AI-vinkje, plafond 3 per dag (antwoorden op eigen posts tellen mee).

## AUTOMATISCHE INZICHTEN (gemeten 12 van 118 reacties, script scripts/social_leren.py)
- Gemiddelde score alle reacties: 1.2 (likes + 3 per antwoord + 5 bovenaan).
- Beter dan gemiddeld: lengte = kort (<=20 woorden) (n=5, score 1.8, +0.6). Doe dit vaker.
- Slechter dan gemiddeld: post leeftijd = >6 uur (n=5, score 0.4, -0.8). Doe dit minder.
- 80% van de reacties volgt de beste vorm, 20% is een bewuste proef (zet dan veld variant in gedaan.jsonl).
