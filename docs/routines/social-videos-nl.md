# Social video's NL maken en bijsturen (wekelijks, donderdag)

Opdracht van Daniel, 26-11-2026. Zelfde routine, zelfde pijplijn, zelfde koppelingen en kwaliteitspoorten als
`docs/routines/social-videos.md` (Engels, dinsdag). Lees die eerst; alles daar geldt hier ook, behalve wat hieronder anders staat.
Alle video's zijn NEDERLANDS. Daniel plaatst elke donderdag zelf via Schedchie op het subaccount "Omnivaleur NL":
alleen Instagram, TikTok en YouTube (Shorts). Doel: zoveel mogelijk views en engagement, en uiteindelijk aanmeldingen.

## Wat anders is dan de Engelse routine
- Taal: Nederlands, gesproken en casual ("je", samentrekkingen, korte zinnen). Geen vertaalde Engelse haken: schrijf het zoals een
  Nederlandse reseller het zegt (Vinted, Marktplaats, 2dehands, "verkopen op meerdere platforms", euro's, Nederlandse en Belgische context).
- Stem: ElevenLabs met `genvoice_ts.py` (with-timestamps; Parakeet kent geen Nederlands, dus nooit daarop timen). Kies per video een
  Nederlandse of meertalige premade stem met veel intonatie. Slop-check geeft vals rood op 'geen samentrekking' bij Nederlands: lees dan zelf na.
- Plaatsdag: donderdag. Levering uiterlijk donderdag voor 12:00 zodat hij kan plannen. Run: donderdag 09:00.
- Platforms: alleen Instagram, TikTok, YouTube Shorts. Geen Threads, Pinterest, Bluesky, Facebook.
- Dashboardbeeld: de NL-interface (`/nl`, taal Nederlands) waar het kan, anders Engels dashboard met Nederlandse bijschriften.
- Bio-links voor NL: `/ig-nl`, `/tt-nl`, `/yt-nl` (meting in GA4 per bron en dag, zie Stap 1 van de Engelse routine).
- Eindkaart: omnivaleur.com/nl.
- Aantal: 4 tot 5 video's per week, drie verschillende formats en stijlen (A lowpoly, B zacht cartoon, C realistisch, 2D motion), plus minstens één format dat nog nooit gemaakt is.

## Stap 1: meten wat vorige week deed (NL-accounts)
Zoals Engelse Stap 1, maar alleen het Schedchie-subaccount "Omnivaleur NL" (connector `list_accounts` en analytics; kies de accountIds van
de NL-accounts, nooit die van de EN-accounts) en voor TikTok TikTok Studio in Daniels Chrome. Zet de rijen in
`docs/social-video-metingen-nl.csv` (zelfde kolommen) en draai `python3 scripts/video/format_scores.py docs/social-video-metingen-nl.csv`.
Mix NL en EN data niet in één tabel: de taal is een variabele. Wel mag je de EN-score gebruiken als startvermoeden voor een format
(hoog bij EN = eerste keuze voor NL), en na vier weken NL-data per format vergelijken: werkt het hetzelfde? Schrijf dat op in het leerlog NL.
Eerlijkheid over kleine aantallen: zeg bij n<3 per format "onzeker", trek geen conclusie.

## Stap 2: voorbeelden uit de NL-niche (viral onderzoek)
Zoek in Daniels Chrome (alleen lezen) op Instagram Reels, TikTok en YouTube Shorts in het Nederlands:
- Hashtags en zoektermen: vinted tips, vinted verkopen, marktplaats, 2dehands, reselling, kringloop, thrift, bijverdienen, zzp starter, ondernemen tips, storytime animatie, 3d animatie nederlands.
- Zoek 8 tot 12 accounts die viral gaan met animatie of storytime in NL en BE (ook buiten de niche: grappige animatie-accounts, 3D-poppetjes, kantoorhumor), plus de Engelse voorbeelden uit het Engelse leerlog (renno, semigenius, Dale) en kijk wat daarvan in het Nederlands nog niet bestaat (gat in de markt).
- Per account de laatste 10 video's: weergaven, likes, reacties, delen, lengte, openingszin, sneden per seconde, stijl, stem, onderwerp. Zoek patronen, geen uitschieters; markeer wat 3x boven het accountgemiddelde scoort en waarom (haak, onderwerp, tempo, deel-aanzet, trendgeluid).
- Trendbronnen: TikTok Creative Center (regio Nederland), Google Trends NL, trending audio. Kies één tot twee trends die echt aan een reseller-pijn passen.
- Bewaar tabellen en conclusies in `docs/social-video-leerlog-nl.md`.

## Stap 3: wat de kans op viraal vergroot (toepassen, elke video)
Bewezen of sterk aannemelijk, test elk als hypothese en noteer de uitkomst:
1. Haak in de eerste 1 tot 2 seconden met concreet getal, verlies of herkenbare pijn; de kijker moet binnen 2 seconden weten waarom blijven. Eerste frame is al beweging.
2. Kijktijd en loop: 15 tot 25 seconden, einde dat naadloos terugslaat naar het begin (loop), zodat percentage bekeken en herkijken stijgen.
3. Deelbaarheid: één regel die iemand naar een vriend wil sturen ("Stuur dit naar iemand die op Vinted verkoopt"); deel- en bewaar-aanzet in het beeld.
4. Eén duidelijke storyline met inzet, draai en einde; 1 shot per 1 tot 1,5 s; steeds andere camerahoek en kamer.
5. Ondertitels altijd aan, dik en leesbaar (veel kijkers zonder geluid).
6. Eigen reactie vastgepind per video met een vraag die reacties uitlokt (reacties tellen zwaar voor bereik).
7. Zoekwoorden in beschrijving en op het scherm (YouTube Shorts en TikTok zijn zoekmachines): "Vinted tips", "Marktplaats verkopen".
8. Serie: terugkerend personage en vaste nummering ("Deel 3") als een serie wint; kijkers volgen een vervolg.
9. Plaatstijd: eerste week aanname (do 18:00 tot 20:00 NL), daarna uit de eigen cijfers per platform.
10. Menselijkheidspoort uit de Engelse routine geldt volledig: geen AI-slop, geen verzonnen resultaten of getuigenissen.
Gebruik de adviseur (zwaarder model) als je vastzit of een grote keuze moet maken; noteer het advies in het leerlog NL.

## Stap 4: maken, kwaliteitspoort
Pijplijn, kwaliteitspoort en geluid precies zoals `docs/routines/social-videos.md` (Stap 0, 4, Menselijkheidspoort, Muziek, Kwaliteitspoort, 3D-stijlen) en `docs/video-recept.md`.
Werkmap: `~/omnivaleur-videos/nl-week-JJJJ-WW/`. Tekst volgens huisregels: geen schuld aantrekken, "crosslisten" is de actie, nooit Omnivaleur als werkwoord.
Meld in het rapport ElevenLabs-tekens per video.

## Aanleveren (gescheiden van Engels)
ALLEEN in `~/Downloads/omnivaleur-nl-week-WW/` en in Drive `Omnivaleur/Social media video's Claude NL/Week WW` (hoofdmap NL, per week een submap; maak aan als hij er niet is;
Mac: `~/Library/CloudStorage/GoogleDrive-*/Mijn Drive/Omnivaleur/`). Elders de mp4's wissen zodra de levering klaar is. Bestandsnamen `omnivaleur-nl-weekWW-<nr>-<naam>.mp4` plus `.txt`
(haak, voice-over, bijschrift, vastgepinde reactie, hashtags, titel YouTube, plaatstijd per platform, hypothese, welke video test is en welke herhaling van een winnaar, trendgeluid).
Stuur de mp4's met SendUserFile. Zet een regel in `docs/team-notes.md`. Ook `docs/overdracht.md` bijwerken.

## Rapport aan Daniel
Vier blokjes uit CLAUDE.md, één scherm: wat vorige week werkte (aanmeldingen vooraan), wat dat verandert, zekerheid, actiepunten die alleen hij kan.
