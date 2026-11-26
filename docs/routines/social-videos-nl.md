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
- Aantal: 3 tot 5 video's per week, drie verschillende formats en stijlen (A lowpoly, B zacht cartoon, C realistisch, 2D motion), plus minstens één format dat nog nooit gemaakt is.

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


## Zelflerend systeem, langetermijn en eigen initiatief (Daniel, 26-11-2026)
Doel: een volledig geautomatiseerd systeem dat elke week beter wordt. Streef elke run naar de best mogelijke uitkomst.
- Aantal video's: 3 tot 5 per week. Leer zelf wat het beste aantal is: noteer per week het aantal, de totale en gemiddelde cijfers per video en per platform
  en of meer video's het gemiddelde per video drukken (publiek verzadigd, platform dempt, kwaliteit zakt) of juist het totaalbereik laten stijgen.
  Kies het aantal voor de komende week op basis daarvan en schrijf de afweging in het leerlog (tabel "aantal per week"). Harde conclusie pas bij minstens 4 weken data.
- Extra bronnen voor trending onderwerpen (alleen lezen): Google Search Console (`backend/services/search_console.py`: `query_window`, `get_top_pages`) en
  Google Analytics (`backend/services/ga4.py`: `top_pages`, `social_posts`, `by_country`) voor welke zoekwoorden en pagina's bezoekers nu aanspreken;
  verder Google Trends, TikTok Creative Center, YouTube-zoeksuggesties en tools die laten zien welke content nu relevant is. Maak van een stijgend zoekwoord of populaire pagina een video-hoek.
  Zoek zelf verder naar bronnen die helpen en noteer welke bruikbaar bleken.
- Lange termijn: houd per week een trendlijn bij (volgers, bereik, kijkduur, aanmeldingen per bron) en kijk naar maand-op-maand verschil, seizoen en terugkerende pieken.
  Herken je iets wat beter kan (plaatstijd, lengte, stem, hooktype, platformkeuze, een vermoeide serie, dode formats, een meetgat), meld het Daniel in het rapport onder "Wat beter kan", ook als hij er niet om vroeg.
- Eigen initiatief: je mag extra controles doen en verbeteringen doorvoeren die hier niet staan, zolang ze de prestaties verbeteren, op sociale accounts alleen lezen blijven en geen kosten of risico voor Daniel meebrengen.
  Nooit zelf posten, reageren of accounts wijzigen. Wat je extra deed noem je in het rapport.
- Daniel maakt daarnaast zelf menselijke content (gezicht of eigen stem). Neem die posts mee in de meting (zelfde accounts) en vergelijk animatie met menselijk: wat leert het ene van het andere? Noteer het in het leerlog.

## Schedchie-accounts (gecontroleerd 26-11-2026)
Groep "Omnivaleur NL" (groupId 6b07f01d87d4ece77bc618c9), alle drie verbonden en gezond:
- Instagram `danieldevs_`, accountId 17841414777576496
- TikTok `Danieldevs`, accountId -0003p2PBO-ByBdyPWD6vix3hacSBIYJf_No
- YouTube `Danieldevs`, accountId UCjKSTShsYatnNS8IRuiz_2A
De gebruikersnamen zijn dus niet "omnivaleurnl" (dat stond in de Engelse routine). Meet alleen deze drie.
TikTok is nu in Schedchie gekoppeld (ook de EN-groep: TikTok `Omnivaleur`, accountId -000jAO5295WHmDeEmPpZ_0rAz-do__Rh_46): haal TikTok-cijfers eerst via de connector, Chrome alleen als dat niet lukt.

## Eerlijke aanscherping voor conversie (26-11-2026, na vraag van Daniel)
Aannemelijk uit praktijk en onze eigen data, niet hard bewezen; toets elk punt als hypothese.
1. Bereik is niet het doel: een video die viraal gaat bij mensen die niet verkopen levert geen aanmeldingen. Meet per video het aandeel reacties en vragen van echte verkopers, en profielbezoeken; stuur bij op haken die een verkoper-pijn noemen (dubbel verkocht, verlopen advertentie, uren per dag plaatsen).
2. Goedkope tests boven zware renders: elke 3D-video kost uren, een screenrecording of tekstvideo met echt dashboard kost minuten. Maak minstens de helft van de weekvolume als snelle variant op dezelfde haak (zelfde script, ander beeld) zodat je per haak meer meetpunten krijgt dan per stijl.
3. Meting met kleine aantallen: vergelijk elke video met de mediaan van het eigen account, niet met anderen, en noem n erbij. Een haak is pas een winnaar na minstens drie plaatsingen of 3x de mediaan.
4. Aanmeldingen toeschrijven: voeg bij aanmelding een vraag "Waar hoorde je van ons?" met Instagram, TikTok en YouTube toe (alleen na akkoord van Daniel, het is een wijziging aan klanttekst), en zet per video een kijkwoord/oproep in het beeld. Zonder dat blijven aanmeldingen per video niet te bewijzen.
5. Reageren in het eerste uur en reactie-op-reactie als video is voor Daniel een groot hefboommiddel; leg in het rapport vast welke reacties kansen waren. Jij reageert niet zelf.
6. Daniels eigen gezicht of stem: voor software die in iemands verkoopaccounts werkt is vertrouwen de bottleneck; verwacht dat menselijke video's beter converteren dan animatie en test dat expliciet (zie meting animatie versus menselijk). Raad Daniel in het rapport aan hoeveel zin dat heeft zodra er data is.
7. Label: platforms (TikTok, YouTube) vragen een AI-label bij synthetische stem of realistische beelden. Zet het in het .txt-bestand per video en meld het als actiepunt.
8. Hergebruik winnaars: na 4 tot 8 weken dezelfde winnende haak opnieuw met nieuw beeld; zet dezelfde video ook op Pinterest en Threads van de EN-groep als dat gratis bereik geeft.
9. Landingspagina: controleer elke week dat `/nl` laadt, dat aanmelden werkt en dat de belofte uit de video (7 dagen gratis, list once) er letterlijk staat; een video die iets belooft wat de pagina niet toont lekt aanmeldingen.

## Onderzoek 26-11-2026: wat is bewezen en wat niet (voor EN en NL)
Gezocht op het web. Bijna alles komt uit marketingblogs, niet uit onafhankelijk onderzoek; behandel het als hypothese en toets met eigen data.
- Instagram bevestigd door Mosseri (jan 2025): kijktijd, likes en sends zijn de top drie signalen; volg gemiddelde kijktijd, likes per bereik en sends per bereik. Sends per bereik drijft bereik naar niet-volgers (blogs, niet officieel). De "3 tot 5 keer zwaarder dan likes" en "60% kijkt tot het einde" zijn niet-officiële vuistregels.
- Haak: de eerste 3 seconden houden is de gangbare eerste maat (richtwaarde 55 tot 60% blijft kijken na 3 s volgens blogs, een andere bron meldt TikTok-gemiddelde 32%). Primaire Meta- of TikTok-bron niet gevonden. Gebruik het als eigen relatieve maat, niet als norm.
- TikTok en Shorts als zoekmachine: zoekwoord in de eerste 3 seconden als tekst op het scherm (liefst met de eigen tekstfunctie van TikTok), natuurlijke bijschriften, 1 tot 2 long-tail zoekwoorden per video uit echte zoekvragen (GSC en GA4 liggen er al). Sinds eind april 2026 kunnen makers de zoekwoorden die TikTok aan een video koppelt bekijken en aanpassen. Voor YouTube Shorts niets gevonden.
- Bron-vraag bij aanmelden: vendorstudies (Recast, Refine Labs) melden een grote kloof tussen software-attributie en zelfgerapporteerde herkomst bij "dark social" (social, podcasts); cijfers niet te verifiëren. Beperkingen: mensen zeggen vaak "Google" of "content", en een deel van de antwoorden is onbruikbaar. Lees het daarom als bereik met n erbij, naast GA4, nooit alleen.
- Niet gevonden: harde conversiecijfers voor social video naar SaaS-aanmelding. Eigen meting is dus de enige echte bron.
- Aanmeldformulier: sinds 26-11-2026 een optionele vraag "Waar hoorde je van ons?" (Instagram, TikTok, YouTube, Pinterest, Threads, Facebook, Bluesky, X, Reddit, Indie Hackers, e-mail van ons, Google, AI-assistent, vriend, community, blog, Trustpilot, anders). Antwoord staat als `signup_bron` in de user_metadata van Supabase en als `bron_antwoord` op het GA4-event sign_up. Tel per week het aantal per antwoord en leg het naast de plaatsdagen.
