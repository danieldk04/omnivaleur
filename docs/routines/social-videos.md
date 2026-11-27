# Social video's maken en bijsturen (wekelijks, dinsdag)

Opdracht van Daniel, 10-11-2026. Elke dinsdag lever je 3 tot 5 video's voor sociale media aan met een GROTE variatie in format, hook, stem en situatie
(catalogus: `docs/social-video-formats.md`), en je leert elke week van de cijfers van de week ervoor.
Daniel, 12-11-2026: variatie en veel opties, leren van de echte data, altijd testen op maximale menselijkheid, hooks optimaliseren,
over tijd vanzelf bij de best werkende opties uitkomen, en het mag nooit als AI-slop beoordeeld worden.
Daniel plaatst zelf (TikTok, Instagram, YouTube Shorts, Threads, Pinterest). Jij levert aan en meet.
Het gaat niet om views alleen: het doel is dat mensen aanmelden en betalen.

## Wat Daniel toestond
- Je mag zijn groei bijsturen waar dat nodig is (onderwerp, hoek, openingszin, tempo, formaat, plaatstijd).
- Zijn eigen dashboardaccount mag in beeld, ook met echte cijfers (bevestigd 10-11-2026).
- Klikken op de link in de video meten hoeft niet: niemand typt die over. Mensen gaan via de bio.

## Stap 0: skills echt lezen en toepassen
Lees voor je begint (kort, gericht, niet alles): 
- `~/claude-animation-skills/` (kit voor stem, woordtiming, render; skill `zach-d-films` en `stick-figure`),
- `~/huashu-art-motion/SKILL.md` (regels voor verhaal, tempo, shotlijst, rendersnelheid),
- `~/huashu-motion/skills/huashu-motion/SKILL.md` (de drie toetsen: is het dít product, heeft de energie een vorm, kun je het delen),
- `~/earshot/skills/earshot/SKILL.md` (geluid beoordelen, want jij kunt niet horen).
Ontbreekt een van die mappen of werkt een skill niet: herstel het zelf (`gh repo clone`, zie `docs/video-recept.md`).
Heb je een skill nodig die er niet is (bijvoorbeeld voor een stijl, een 3D-model, echt geluid, ondertiteling,
videoknip), zoek hem, en lukt dat niet of kost het geld: zet het als actiepunt voor Daniel. Verzwijg dat nooit.

## Schedchie-sleutel: terugkomen (Daniel, 13-11-2026)
Daniel zit nog in de gratis proef van Schedchie; API-sleutels bestaan pas na zijn eerste betaalde factuur (verwacht rond 17-11 tot 24-11). Tot die tijd: Chrome-route, en vraag er niet over door. Controleer bij elke run of `~/.omnivaleur/schedchie-key.txt` bestaat; zo niet, zet dan in het rapport één actiepunt: "Schedchie-sleutel aanmaken (AI assistants, API keys, alleen lezen), zodra de eerste betaling erdoor is". Staat het bestand er, test dan `GET /v1/me`, daarna analytics, en schrap dit stukje uit de routine zodra het werkt.

## Stap 1: meten wat vorige week deed
Alleen lezen. Daniel is in Chrome ingelogd (Claude in Chrome); voer nooit wachtwoorden in.
0. Daniel plaatst alles via Schedchie (13-11-2026). Gebruik eerst de API: `https://api.schedchie.com/v1`, sleutel (alleen lezen: posts en analytics) in `~/.omnivaleur/schedchie-key.txt` (Daniel maakt hem aan in het dashboard onder AI assistants, API keys; hij verschijnt maar één keer; sleutels bestaan pas na de eerste betaalde factuur). Header `Authorization: Bearer <sleutel>`, `GET /v1/me` om te testen, `GET /v1/posts` (status en cursor) voor plaatsdatums, het analytics-pad staat in `https://www.schedchie.com/developers/openapi.v1.json`. Limieten: 120 per minuut, 60 ongecachte leesvragen per uur, antwoorden 5 minuten gecachet; geen webhooks, dus pollen. Alleen lezen; nooit posts aanmaken zonder dat Daniel erom vraagt. Zonder sleutel of bij een fout: de webinterface in Daniels Chrome (Schedchie, Daniels planner, alle accounts op één plek, hij is er in Chrome ingelogd): Analytics geeft per platform en per
   post volgers, weergaven, betrokkenheid, betrokkenheidspercentage en top posts, met vergelijking met de vorige periode.
   Ook het tabblad Competitors (beta) is bruikbaar voor stap 2. Daniel plant de video's daar zelf in (Scheduling): zo
   weet je de plaatsdatum per platform. Kijktijd en percentage bekeken staan er niet in: haal die uit stap 1 hieronder.
   Geteld op 10-11-2026: 6 accounts (Instagram 179 volgers, YouTube 32, Threads 13, Bluesky 7, Pinterest 0, Facebook nog niet bevestigd).
1. Per platform, per video van vorige week (en de weken ervoor, voor het verloop):
   - YouTube Studio (studio.youtube.com): weergaven, gemiddelde kijkduur, percentage bekeken, "bekeken versus weggeswiped", likes, reacties, nieuwe abonnees.
   - Instagram Insights (Professional dashboard): bereik, weergaven, gemiddelde kijktijd, likes, reacties, opgeslagen, gedeeld, volgers erbij.
   - TikTok Studio/analytics, als het lukt: weergaven, kijktijd, volledig bekeken, delen, volgers.
   - Threads en Pinterest: alleen weergaven en opslagen, lage prioriteit.
2. Verkeer en aanmeldingen per platform via de vaste korte links (`/ig`, `/tt`, `/yt`, `/pin`, `/th` plus `-nl`):
   `backend/services/ga4.py` (`traffic_sources`, `by_day`, `keyEvents:sign_up`) geeft sessies en aanmeldingen per
   bron en dag. Betalende klanten per `utm_source` staan bij de aanmeldingen in Supabase (register.html stuurt de
   tags mee). Een lege of nul-uitkomst is eerst verdacht: controleer of de meting zelf klopt (CLAUDE.md, punt 6).
3. Koppel per video: plaatsdatum, platform, hoek, hypothese (uit het leerlog) aan de cijfers van die dagen.
   Eerlijkheid: de link zit in de bio, dus je meet verkeer per platform en per dag, niet per video. Schrijf een video
   alleen toe aan aanmeldingen als de data dat dragen (sprong op de dag na plaatsen, niet bij andere video's op dat
   platform tegelijk). Anders staat er "niet te bewijzen" en noem je de dichtstbijzijnde indicatie.

## Stap 2: voorbeelden uit de niche
renno.app plus 5 tot 8 andere accounts die dit soort video's maken (3D of cartoon uitleg, reseller en software,
korte uitleg met voice-over). Zoek ze zelf op via Instagram, YouTube Shorts en TikTok in Daniels Chrome. Alleen lezen.
Noteer per account de laatste 10 video's: weergaven, likes, reacties, lengte, openingszin, tempo (sneden per
seconde), type omgeving, wat het meeste engagement had. Zoek patronen, geen losse uitschieters. Bewaar de tabel in
het leerlog.

## Stap 2b: trends van nu (Daniel, 12-11-2026: uiterst creatief, inspelen op trends)
Kijk elke week wat er nu leeft en kies er één tot twee die echt bij een reseller-pijn passen: TikTok Creative Center (trending hashtags, formats, in NL), Instagram Reels en YouTube Shorts in Daniels Chrome, Google Trends (Vinted, Marktplaats, reselling, thrift). Alleen lezen. Regels: de trend moet natuurlijk aan de pijn of belofte vast kunnen, geen geforceerde meme; niets over echte personen, politiek of gevoelige onderwerpen; niets wat Omnivaleur iets laat beloven wat niet klopt. Trendgeluiden uit de bibliotheek van een platform kan alleen Daniel in de app onder de video zetten: noem in het .txt-bestand welk geluid en waarom, en lever de video ook met een eigen passende muziekstijl zodat hij zonder trendgeluid ook klopt. Noteer in het leerlog welke trend je gebruikte en wat er gebeurde.

## Stap 3: leren
Werk `docs/social-video-leerlog.md` bij: per video de hypothese, wat er gebeurde, en wat je daaruit als regel haalt.
Regel pas als regel opnemen als hij in minstens twee video's of bij een duidelijk voorbeeldaccount terugkomt.
Wat je niet kon meten schrijf je op als openstaand punt. Optimaliseer op deze volgorde: aanmeldingen en betalende
klanten, dan bewaard en gedeeld, dan kijktijd en percentage bekeken, dan reacties, dan pas weergaven.

## Stap 3b: meetdata vastleggen en kiezen
Zet elke gemeten plaatsing (video, platform, cijfers uit stap 1) in `docs/social-video-metingen.csv` (format, hooktype, stem, lengte staan al bij het maken ingevuld). Instagram, TikTok, YouTube en Facebook zijn leidend (Schedchie eerst). Draai daarna `python3 scripts/video/format_scores.py`: het geeft per format, hooktype en stem een score (per platform genormaliseerd, aanmeldingen en betalend het zwaarst) en het advies voor deze week (ongeveer 60% winnaars met een andere hook of stem, 40% proberen). Minder dan 3 plaatsingen per format is 'onzeker': trek dan geen conclusie. Maak ook elke week één video in een format dat nog nooit is gemaakt.

## Stap 4: 4 tot 5 nieuwe video's maken (grote variatie)
Elke video heeft een eigen hypothese (andere haak, andere hoek, ander tempo, andere situatie) en een creatieve,
vreemde situatie waarin het probleem terugkomt, zoals renno dat ook doet (bijvoorbeeld de ruimte, een
rechtszaal, een kookshow, een sportcommentator). Niet steeds hetzelfde kamertje. Het product moet er wel steeds
echt in zitten: echt dashboard, echte platformlogo's, de belofte "list once, sell everywhere".
- Pijplijn: `scripts/video/` (three.js scenes, headless renderen, stem, woordtiming, muziek, mixen). Het recept en
  de valkuilen staan in `docs/video-recept.md`. Kopieer `scripts/video` naar `~/omnivaleur-videos/week-JJJJ-WW/videoN`,
  link `node_modules` en `.venv` naar `~/claude-animation-skills/kit`.
- Dashboardbeelden: elke week vers uit het ingelogde dashboard (geen "Coming soon", geen waarschuwingen, geen
  proefbanner; verberg een banner alleen lokaal met JS, wijzig niets in het account).
- Taal: Engels voor de EN accounts. Maak per week hooguit één video ook in het Nederlands voor de NL accounts
  (`omnivaleurnl`, `omni.valeur`, `@OmnivaleurNL`), tenzij het leerlog zegt dat het niet werkt.
- Lengte 15 tot 25 seconden, 9:16, 1080x1920, haak in de eerste 2 seconden, afsluiter met omnivaleur.com.
- Tekst volgens de huisregels: geen schuld aantrekken, Omnivaleur nooit als werkwoord ("crosslisten" is de actie).

## Menselijkheidspoort (nieuw, 12-11-2026; eerst deze, dan de kwaliteitspoort)
Als het als 'weer een AI-video' voelt is het fout, ook als alles technisch klopt.
1. Script: `python3 scripts/video/slop_check.py <script.json>` groen. Casual, gesproken taal met samentrekkingen, korte zinnen, geen reclamewoorden, een echte inzet of herkenbare pijn in de eerste zin.
2. Stem: Chatterbox (zie `docs/video-recept.md`, 'Menselijker maken'), eigen stem per video via een referentieclip, `intonatie.py` toonspreiding minstens 4,5 halve tonen, pauzes verschillend lang. Liever Daniels eigen stem als hij die aanlevert (format ECHT).
3. Beeld: handheld wiebel, filmkorrel, minstens één hard cut, dikke duidelijke bijschriften, echt dashboard, geen eindkaart met bijschrift eroverheen.
4. Wat je niet kunt beoordelen (hoe de stem klinkt) schrijf je als openstaand punt; Daniel luistert eerst. Platforms kunnen een label vragen voor synthetische stemmen: noem dat als Daniel plaatst.
5. Mac met 8 GB: voor Chatterbox eerst Spotify en andere zware programma's sluiten en niets anders draaien (anders uren), dan pas renderen.

## Muziek (Daniel, 12-11-2026: mag per video anders, passend bij de setting)
Kies per video een stijl die bij de situatie past en wissel af: `sound3.py <werkmap> vN <omslagtijd> <stijl>` met stijl `warm` (vriendelijk), `lofi` (rustig verhaal, avond), `spanning` (alarm, rechtszaal), `speels` (komedie, kookshow), `rustig` (bijna alleen kamertoon, voor uitleg of eigen stem). Maak gerust een nieuwe stijl in `STIJLEN` voor een nieuwe setting. Muziek is in code gemaakt (geen rechten nodig). Geen gedownloade muziek of bibliotheekmuziek zonder duidelijke vrije licentie. Bed blijft ver onder de stem.

## Kwaliteitspoort (alles moet groen voor je aanlevert)
1. Doorsteken: `node clip.mjs` geeft 0 frames (poppetje door laptop of meubel is een fout).
2. Beeld: kijk minstens 5 stills per video (haak, drie midden, afsluiter), geen afgekapte tekst, geen lege plekken.
3. Geluid met earshot beoordelen (niet raden): verstaanbaarheid van de voice-over, geluidjes duidelijk zachter dan de
   stem, totale luidheid rond -14 LUFS, geen kloppen of ruis. Citeer de getallen in je rapport.
4. Zijn er cijfers of namen in beeld van een klant die niet Daniel is? Dan niet gebruiken.
5. Opnieuw gerenderd na elke wijziging; nooit een eerdere versie opsturen.

## Aanleveren
Daniel, 12-11-2026 en 13-11-2026: de eindbestanden komen ALLEEN in `~/Downloads` en in Drive in `Omnivaleur/Social media video's Claude/Week WW` (één hoofdmap, daarbinnen per week een submap, bijvoorbeeld `Week 47`; voorbeelden of varianten in een submap daarbinnen) (Mac: `~/Library/CloudStorage/GoogleDrive-*/Mijn Drive/Omnivaleur/`; maak de weekmap aan als hij er niet is); op alle andere plekken wis je de mp4's (werkmappen, tussenbestanden, mix- en silent-bestanden) zodra de levering klaar is. Daniel wist ze uit Downloads nadat hij ze heeft ingepland. Bestandsnamen: `omnivaleur-weekWW-<nr>-<naam>.mp4` plus `.txt`.
Werkmap `~/omnivaleur-videos/week-JJJJ-WW/`: per video `videoN.mp4` en `videoN.txt` met bijschrift, hashtags, titel voor
YouTube, beste plaatsmoment per platform, hypothese en wat je ermee wilt leren. Stuur de mp4's met SendUserFile en
meld dat Daniel ze kan plaatsen. Zet een korte regel in `docs/team-notes.md`.

## Rapport aan Daniel
Vier blokjes uit CLAUDE.md, op één scherm: wat vorige week werkte (cijfers met aanmeldingen vooraan), wat dat
verandert voor deze week, zekerheid, en actiepunten die alleen hij kan (plaatsen, ontbrekende skills of toegang,
een beslissing). Staat er niets open, schrijf "Niets, klaar."


## 3D-stijlen (sinds 25-11-2026, Daniel)
Maak video's zoals de goed scorende Instagram-animaties (semigenius, Dale, renno): 3D-poppetjes, ca. 1 shot per seconde, steeds een andere kamer en camerahoek, absurd of spannend verhaal met een duidelijke storyline, Engels tot Daniel anders zegt. Levert elke run minstens drie video's in drie stijlen (A lowpoly blokpoppetjes, B zacht cartoon, C realistischer thriller), recept in `docs/video-recept.md` onder "3D-pijplijn". Meet per stijl welke wint en bouw de volgende ronde zwaarder in de winnaar, met nieuwe verhalen en hooks op alle pijnpunten van klanten. Lever in `~/Downloads/omnivaleur-week-<nr>/` met een txt per video (haak, voice-over, caption, vastgepinde reactie, hashtags, titel, plaatstijd, hypothese).


## Meting van de 3D-ronde en wekelijkse trendronde (Daniel, 25-11-2026)
Daniel plant en plaatst alles via Schedchie; de 3D-ronde van week 48 (3d-A-blocky-hoodie, 3d-B-toon-midnight, 3d-C-real-kevin, elk als -v2) staat ingepland voor deze week.
Smaakvolgorde van Daniel (alleen een eerste indruk, geen data): 1) C real-kevin, 2) B toon-midnight, 3) A blocky-hoodie. Leg de uitkomst naast deze volgorde: klopt zijn smaak met de cijfers of niet?
Dinsdag 01-12-2026 (en elke dinsdag daarna):
1. Haal de resultaten van de vorige week op via Schedchie (connector of API, zie Stap 1): per video en per platform weergaven, kijktijd/percentage bekeken waar beschikbaar, likes, reacties, opgeslagen, gedeeld, volgers erbij. TikTok is niet gekoppeld aan de connector: haal die uit de web-analytics in Daniels Chrome. Zet de rijen in `docs/social-video-metingen.csv` en draai `format_scores.py`. Zet de uitkomst in de tabel in het leerlog (stijl A, B, C) en schrijf per stijl een conclusie: wat werkte, wat niet, wat probeer je nu.
2. Wees eerlijk over kleine aantallen (ca. 180 volgers op Instagram): een video met 300 weergaven bewijst weinig. Zeg dat in het rapport en trek geen harde conclusie uit n=1.
3. Trendronde, elke week: bekijk in Daniels Chrome (Instagram, TikTok, YouTube Shorts) wat deze week scoort in animatie en storytime-video's, ook buiten de niche (semigenius, renno, Dale-achtige accounts, nieuwe accounts die opduiken), en welke onderwerpen en haken populair zijn. Noteer 5 tot 8 concrete voorbeelden met wat ze doen (tempo, haak, camera, stem, onderwerp) in het leerlog.
4. Afwisseling: maak elke week bewust een mix. Ongeveer de helft in de stijl die het best scoorde, de rest nieuwe varianten (ander verhaalformat, andere stijl, aangesloten op een trend van die week) zodat er blijft worden geleerd. Zet in het rapport welke video een test is en welke een herhaling van een winnaar.
5. Menselijk, niet AI-slop (Daniel): geen verzonnen resultaten of getuigenissen, echte pijnpunten van klanten, humor en een duidelijke storyline, wisselende stemintonatie (ElevenLabs v3 met emotietags, `genvoice_ts.py` plus `tempo.py`), en loop elke video na op botsende beelden (poppetjes of kleding door elkaar, uitgerekte schermen of logo's) met `chk.sh` voor je rendert.
6. Rapporteer in de vier blokken en noem hoeveel de ElevenLabs-tekens kostten (tekens per video, rond 450 tot 650).


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

Bijwerking 26-11-2026: TikTok (`Omnivaleur`) staat nu wel in Schedchie en in de connector; de zin hierboven dat TikTok niet gekoppeld is, is achterhaald. Facebook blijft platform_blocked (fb_checkpoint_368).


## Leerpunten uit de NL-routine die ook hier gelden (26-11-2026)
Lees de sectie "Leerpunten van Daniel, ronde 2" in `docs/routines/social-videos-nl.md`: dialoog met meerdere stemmen (`genvoice_multi.py`), tempo (19 tot 26 s, een shot per seconde), geen vertalingen maar eigen verhalen, meer diversiteit en realisme, en Drive-upload via de connector met 720p-voorbeelden (limiet 7 MB). Pas dat ook op de Engelse video's toe.

## Gouden standaard (Daniel, 27-11-2026)
Lees `docs/social-video-renno-ontleding.md` voor je een script schrijft: een analogie, een spiegel, het product als echte geanimeerde UI, een kleurboog van probleem naar oplossing, rekwisieten die het verhaal dragen, een eindkaart met een zin en een knop.
