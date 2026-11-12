# Social video's maken en bijsturen (wekelijks, dinsdag)

Opdracht van Daniel, 10-11-2026. Elke dinsdag lever je 4 tot 5 video's voor sociale media aan met een GROTE variatie in format, hook, stem en situatie
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

## Stap 1: meten wat vorige week deed
Alleen lezen. Daniel is in Chrome ingelogd (Claude in Chrome); voer nooit wachtwoorden in.
0. Eerst Schedchie (Daniels planner, alle accounts op één plek, hij is er in Chrome ingelogd): Analytics geeft per platform en per
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
Daniel, 12-11-2026: de eindbestanden komen ALLEEN in `~/Downloads` en in Drive `Omnivaleur/Social video's week WW` (Mac: `~/Library/CloudStorage/GoogleDrive-*/Mijn Drive/Omnivaleur/`); op alle andere plekken wis je de mp4's (werkmappen, tussenbestanden, mix- en silent-bestanden) zodra de levering klaar is. Daniel wist ze uit Downloads nadat hij ze heeft ingepland. Bestandsnamen: `omnivaleur-weekWW-<nr>-<naam>.mp4` plus `.txt`.
Werkmap `~/omnivaleur-videos/week-JJJJ-WW/`: per video `videoN.mp4` en `videoN.txt` met bijschrift, hashtags, titel voor
YouTube, beste plaatsmoment per platform, hypothese en wat je ermee wilt leren. Stuur de mp4's met SendUserFile en
meld dat Daniel ze kan plaatsen. Zet een korte regel in `docs/team-notes.md`.

## Rapport aan Daniel
Vier blokjes uit CLAUDE.md, op één scherm: wat vorige week werkte (cijfers met aanmeldingen vooraan), wat dat
verandert voor deze week, zekerheid, en actiepunten die alleen hij kan (plaatsen, ontbrekende skills of toegang,
een beslissing). Staat er niets open, schrijf "Niets, klaar."
