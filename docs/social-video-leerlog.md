# Leerlog social video's

Bijgehouden door de wekelijkse routine `docs/routines/social-videos.md`. Nieuwste bovenaan.

## Week 48, vervolg 24-11-2026: koppeling gecontroleerd, eerste inspiratie
- Schedchie-connector werkt (whoami, list_accounts, list_posts, get_analytics_overview gedraaid). Accounts: Instagram, Facebook (geblokkeerd: Page-eigenaar moet identiteit bevestigen, fb_checkpoint_368 sinds 3-11), YouTube, Pinterest, Threads, Bluesky. TikTok is NIET gekoppeld in Schedchie, dus TikTok-cijfers komen er niet via de connector.
- Meting van de enige 2 video-posts (3-11 en 10-11, oude stijl): YouTube 1 weergave, Pinterest 1 impressie, Threads 9 weergaven, Instagram 7 likes en 1 reactie op de reel van 10-11. Volgers 30 dagen: +2 totaal. Niet toe te schrijven aan aanmeldingen. Conclusie: de oude stijl haalde niets; aanleiding om naar het renno-niveau te gaan.
- renno.app (Instagram, 6.644 volgers, gemeten via Daniels Chrome, niet ingelogd): reels met 2,6 mln, 650K, 506K, 110K weergaven; de rest tussen 100 en 2.200. Dus een paar uitschieters dragen het account: patroon voor de volgende stap is veel varianten testen en de winnaars herhalen. Nog te doen: openingszinnen, lengte en tempo van de uitschieters noteren.
- Geblokkeerd: `bash kit/setup.sh --voice` (kit, Playwright, 1 GB stemmodellen) werd door de rechtenfilter geweigerd, dus er is nog niet gerenderd.

## Week 48, dinsdag 24-11-2026 (automatische run): nog steeds geen plaatsingen, geen nieuwe video's
Schedchie (Daniels Chrome) toont nog dezelfde 2 geplaatste posts en niets ingepland: geen enkele video uit week 46 of 47 is geplaatst, dus niets te meten en alle formats 'onzeker'. Schedchie-sleutel bestaat nog niet. Besluit: geen vijf video's erbij op een stapel ongeplaatste; leren begint zodra er plaatsingen zijn. De video's van week 46 en 47 stonden op de oude Mac en zijn niet meegekomen (`~/omnivaleur-videos` en Downloads zijn leeg op deze Mac); de code staat wel in `scripts/video/` en de scripts in `week47-scripts.json`.
Omgeving hersteld op de nieuwe Mac (32 GB): `~/claude-animation-skills`, `~/huashu-art-motion`, `~/huashu-motion`, `~/earshot` opnieuw geklooid. Nog niet gedaan: `install.sh --voice` (kit, venv, modellen ongeveer 1 GB), earshot-venv, Chatterbox-venv. Spotify draait.

## Week 47, dinsdag 17-11-2026 (automatische run): geen nieuwe video's, geen cijfers
Schedchie (Daniels Chrome) toont maar 2 geplaatste posts, van 3-11 en 10-11 (tekstposts, geen van onze video's). Geen enkele video uit week 46 of 47 is ingepland of geplaatst, dus er is niets te meten en geen conclusie per format mogelijk (alles 'onzeker', minder dan 3 plaatsingen). Schedchie-sleutel bestaat nog niet. Besluit: niet nog vijf video's erbij op een stapel van acht ongeplaatste; leren begint pas zodra er plaatsingen zijn. Machine ook ongeschikt voor een render nu: vrijwel geen vrij geheugen, Spotify draait, 6,4 GB schijf vrij.

## Week 47, 13-11-2026: vijf nieuwe video's (Daniel vroeg om meer)
Eerste run besloot niets te maken; Daniel zei daarna: maak ze, meer video's. Gemaakt in `~/omnivaleur-videos/week-2026-47/` (code `src/week47.js` plus `v1.js` tot `v5.js`, tijden volgen de stem via `montage()`; geluid via `sound4.py`).
| Video | Format | Hook | Stem | Lengte | Luidheid |
|---|---|---|---|---|---|
| 1 stop-4x | MYTHE | BEWERING | man (ref_A) | 20,9 s | -13,5 LUFS |
| 2 3-manieren | LIJST (nieuw) | GETAL | vrouw (ref_B) | 20,4 s | -13,0 |
| 3 diner | ANALOGIE | ABSURD | Adam | 21,3 s | -14,6 |
| 4 hoodie-twee-keer | UITLEG | VRAAG | Puck (ref_C) | 20,3 s | -13,4 |
| 5 zelfde-avond | VOORNA | INZET | George | 21,1 s | -12,5 |
Alle vijf: doorsteken 0, piek onder -3,2 dBFS. Slop-check groen op alle scripts (twee eerst rood: te lange zin, geen samentrekking; herschreven). Geen cijfers: niets uit week 46 is geplaatst, geen Schedchie-sleutel. Dashboardbeelden zijn die van 10-11 (niet vers vastgelegd). Beeld is tekstgedreven (geen poppetje) zodat het in uren kon op een Mac van 8 GB; Chatterbox kostte 1,5 tot 90 minuten per regel door geheugendruk. Openstaand: stem niet beluisterd, trendstap en voorbeeldaccounts niet gedaan, earshot-meting niet gedraaid, geen Nederlandse versie.

## Regels die Daniel zelf gaf (10-11-2026)
- Stijl: renno.app. Een 3D blokpoppetje in uiteenlopende, creatieve situaties, schreefletters cursief in één zin, voice-over, zeer snelle sneden, echte dashboardbeelden.
- Het poppetje mag nooit door spullen heen lopen.
- Voice-over (Kokoro am_michael) is goed. Achtergrondmuziek mag blijven. Geluidjes zacht houden.
- Meetdoel: aanmeldingen en betalende klanten, daarna betrokkenheid en kijktijd, pas daarna weergaven.

## Week 46 (10-11-2026): start
Nog geen cijfers: proefvideo's 1 tot 3 zijn niet geplaatst. Eerste echte meting op dinsdag 17-11-2026 voor wat Daniel plaatst.

| Video | Hypothese | Uitkomst | Regel |
|---|---|---|---|
| proef3 (18 s, "You sell on Vinted") | Snel, veel omgevingen, echt dashboard | nog niet geplaatst | n.v.t. |

## Week 46, tweede levering (10-11-2026): drie nieuwe video's
Gemaakt in `~/omnivaleur-videos/week-2026-46/` (code `scripts/video/src/v1.js` tot `v3.js`, scenes in `week46.js`). Nog niet geplaatst, dus nog geen cijfers.

| Video | Situatie | Hypothese | Uitkomst |
|---|---|---|---|
| video1 (17,3 s) | Rechtszaal | Een aanklacht als haak houdt langer vast dan een uitspraak | nog niet geplaatst |
| video2 (18,9 s) | Kookshow | Receptformaat met stappen wordt bewaard en uitgekeken | nog niet geplaatst |
| video3 (16,5 s) | Ruimte-alarm | Drama en tempo verslaat rustige uitleg | nog niet geplaatst |

Technisch geleerd: een poppetje achter een toonbank heeft zijn handen standaard in het blad (schouder -0,9 geeft hand op 0,79 m, blad op 0,95 m); `clip.mjs` ving dat (269 frames) en nu staan de armen boven het blad. Lees clip.mjs altijd per video, niet alleen voor de eerste.
Eerste week: plaatstijden zijn een aanname (geen eigen data). Elke video heeft een ander tijdstip zodat de meting van 17-11 iets kan vergelijken.

## Voorbeeldaccounts
(Nog niet gevuld op 10-11-2026: de run ging naar de bouw van de video's. Eerstvolgende dinsdag 17-11: renno.app en 5 tot 8 andere via Daniels Chrome, plus Schedchie.)

## Openstaande punten
- Geluid van proef3 gemeten met earshot op 10-11-2026 (zie recept). De zwaardere meting (herkenning of het als echte opname klinkt) vraagt een download van ongeveer 1,1 GB modellen en is nog niet gedaan.
- Aanmeldingen per video zijn niet te bewijzen met bio-links; alleen per platform en dag.
