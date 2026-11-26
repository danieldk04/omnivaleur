# Leerlog social video's NL

Bijgehouden door de wekelijkse donderdagroutine `docs/routines/social-videos-nl.md`. Nieuwste bovenaan.
Metingen: `docs/social-video-metingen-nl.csv`. Het Engelse leerlog (`docs/social-video-leerlog.md`) is startvermoeden, geen bewijs voor NL.

## Week 48, donderdag 26-11-2026 (ronde 2): echt nieuwe verhalen, snellere video's, menselijkere stem
Daniel over de vertaalde ronde: Kevin (C) beviel, maar te langzaam en de stem klonk te veel AI; en het waren vertalingen. Nu drie nieuwe NL-verhalen, elk een nieuw format: sollicitatie (dialoog, A), Sven en de elf dagen (tijdsprong met droge verteller, B), eten staat klaar (relatiesketch, kruisgesneden, C).
Stem: alleen premade stemmen beschikbaar (sleutel kan geen bibliotheek lezen); acht stemmen en twee instellingen gemeten op toonspreiding. Josh (de stem van de eerste ronde) was het vlakst (sd 3,9 halve tonen); Liam, Charlie, Callum, Jessica waren expressiever (sd 5 tot 7). Nu per personage een eigen stem (`genvoice_multi.py`), korte zinnen met herstarts en aarzelingen, stabiliteit 0,25 tot 0,5, tempo 1,18 tot 1,22 en stiltes ingekort. Gemeten: sd 4,9 / 5,6 / 7,1 halve tonen. Ik kan niet horen of het Nederlands natuurlijk klinkt: Engelse premade stemmen kunnen een accent hebben. Echte oplossing: Daniels eigen stem, of een Nederlandse stem uit de ElevenLabs-bibliotheek (vraagt een sleutel met voices_read).
Snelheid: lengte nu 24 / 26 / 19 s (was 33 tot 45), ca. 1 shot per seconde, snijden op het woord, kruissneden tussen twee kamers. Lengte per video is de testvariabele naast het format.
Open: de beweging van de poppetjes bij dialoog is beperkt (profielshots); gesproken tekst beweegt de mond, geen gebaren per zin. Baard van Sven is een grijs blok. Zelf geen voorbeeldaccounts bekeken in deze ronde.
Eerlijke afweging: hypothese is dat dialoog en herkenbare humor beter scoort dan voice-over; zonder NL-data blijft dat een hypothese.

## Week 48, donderdag 26-11-2026: eerste NL-ronde (3 video's, 3 stijlen)
Meting: er is nog niets op het NL-subaccount geplaatst (alleen EN-posts van 25 en 26-11 in Schedchie), dus geen cijfers en alle formats 'onzeker'. Trendronde, voorbeeldaccounts en GSC/GA4-hoeken niet gedaan in deze run (alleen de bouw); eerste echte NL-onderzoek volgt op 03-12.
Gemaakt met de 3D-pijplijn, NL-versies van de drie EN-verhalen (zelfde shotlijst, woordindex automatisch omgezet per zin): hoodie-stad (A lowpoly, 36 s, 626 tekens ElevenLabs), vannacht-twaalf-uur-veertig (B toon, 33 s, 501 tekens), kevin-twee-kopers (C realistisch, 45 s, 769 tekens). Luidheid -14,1/-14,0/-14,0 LUFS, piek -1,7/-1,0/-1,2 dBFS. Stills en tegelsheet per video bekeken. Stem niet beluisterd.
Eigen fout onderweg: eerst drie 2D-tekstvideo's gemaakt (757 tekens verspild) terwijl de EN-routine sinds 25-11 poppetjes in 3D gebruikt; door Daniel gecorrigeerd en weggegooid. Les: lees bij een NL-routine eerst wat de EN-routine DEZE week levert, niet het oudere recept.
Open: lengte 33 tot 45 s ligt boven de 15 tot 25 s uit de routine (EN is ook ~35 s); dashboard in beeld is Engels; Drive-upload niet gedaan (geen lokale Drive-map, connector kan geen grote video's).

## Start, 26-11-2026
Daniel startte een NL-lijn: eigen Schedchie-subaccount "Omnivaleur NL", alleen Instagram, TikTok en YouTube, plaatsing elke donderdag.
Nog geen NL-data en geen NL-voorbeeldaccounts bekeken. Eerste run: donderdag 03-12-2026.
