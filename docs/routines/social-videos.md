# Social video's maken en bijsturen (wekelijks, dinsdag)

Opdracht van Daniel, 10-11-2026. Elke dinsdag lever je 3 tot 4 geanimeerde video's voor sociale media aan,
in de stijl van het Instagramaccount renno.app, en je leert elke week van de cijfers van de week ervoor.
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

## Stap 3: leren
Werk `docs/social-video-leerlog.md` bij: per video de hypothese, wat er gebeurde, en wat je daaruit als regel haalt.
Regel pas als regel opnemen als hij in minstens twee video's of bij een duidelijk voorbeeldaccount terugkomt.
Wat je niet kon meten schrijf je op als openstaand punt. Optimaliseer op deze volgorde: aanmeldingen en betalende
klanten, dan bewaard en gedeeld, dan kijktijd en percentage bekeken, dan reacties, dan pas weergaven.

## Stap 4: 3 tot 4 nieuwe video's maken
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

## Kwaliteitspoort (alles moet groen voor je aanlevert)
1. Doorsteken: `node clip.mjs` geeft 0 frames (poppetje door laptop of meubel is een fout).
2. Beeld: kijk minstens 5 stills per video (haak, drie midden, afsluiter), geen afgekapte tekst, geen lege plekken.
3. Geluid met earshot beoordelen (niet raden): verstaanbaarheid van de voice-over, geluidjes duidelijk zachter dan de
   stem, totale luidheid rond -14 LUFS, geen kloppen of ruis. Citeer de getallen in je rapport.
4. Zijn er cijfers of namen in beeld van een klant die niet Daniel is? Dan niet gebruiken.
5. Opnieuw gerenderd na elke wijziging; nooit een eerdere versie opsturen.

## Aanleveren
Map `~/omnivaleur-videos/week-JJJJ-WW/`: per video `videoN.mp4` en `videoN.txt` met bijschrift, hashtags, titel voor
YouTube, beste plaatsmoment per platform, hypothese en wat je ermee wilt leren. Stuur de mp4's met SendUserFile en
meld dat Daniel ze kan plaatsen. Zet een korte regel in `docs/team-notes.md`.

## Rapport aan Daniel
Vier blokjes uit CLAUDE.md, op één scherm: wat vorige week werkte (cijfers met aanmeldingen vooraan), wat dat
verandert voor deze week, zekerheid, en actiepunten die alleen hij kan (plaatsen, ontbrekende skills of toegang,
een beslissing). Staat er niets open, schrijf "Niets, klaar."
