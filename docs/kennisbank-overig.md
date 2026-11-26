# Kennisbank overig: geheugen uit Daniels andere mappen

Automatisch gemaakt door `scripts/export_kennisbank.py`. Per kopje staat de map waaruit de les komt. Bevat Downloads (hier schrijft de nachtelijke Dreaming-taak), Documents, crosslist-eu en de andere projecten.

---

## -Users-danieldekoning-Downloads / social-video-feedback-storytime

*25-11-2026*

Daniel (24-11-2026): de "buyer door video" is goed. Wil meer storytime, meer spanning en meer invalshoeken (hooks op alle bekende klantpijnpunten), kijken naar voorbeelden van andere accounts op Instagram (ingelogd) en optimaliseren voor conversie, plus een realistischere flow tussen stem en beeld.

**Why:** de eerdere video's haalden nauwelijks weergaven.

**How to apply:** bij nieuwe video's: haak in de eerste seconde per pijnpunt, verhaalopbouw, stemtiming strak op beeld. Aanvulling op [[social-videos-animatie]].

---

## -Users-danieldekoning-Downloads / nieuwe-mac-routines-herstellen

*25-11-2026*

Sinds 24-11-2026 werkt Daniel op een nieuwe Mac. Wat hij van de oude terug wil, in exact dezelfde vorm: de rechterbalk in de chat met lopende routines, de vastgezette chat die 3 tot 4 keer per dag reageert/engaget op Indie Hackers en Bluesky (X hoeft niet), en alle LaunchAgents/geplande taken. Hij wil dat Claude de volgende dag controleert of alles gedraaid heeft. Bekende hapering: reactieronde faalde 24-11 14:56 met "Chrome niet verbonden"; Chrome moet ingelogd en verbonden zijn.

**Why:** de migratie liet stil dingen wegvallen die hij niet zelf merkt.

**How to apply:** check na elke nieuwe-Mac-vraag of taken, LaunchAgents en Chrome-verbinding draaien en meld faalrondes. Zie [[feedback-maximale-autonomie]].

---

## -Users-danieldekoning-Downloads / feedback-maximale-autonomie

*25-11-2026*

Daniel (24-11-2026, meerdere sessies): "doe alles maximaal wat je voor mij kan doen, alleen de essentiële dingen voor mij", "je mag alles testen, ook op mijn PC", doel is zekerheid richting 100% en geen actiepunten meer voor hem. Bij een voorgesteld actiepunt dat Claude zelf kon uitvoeren zei hij gewoon "doe dit voor me".

**Why:** zijn tijd is de schaarse resource; een actiepunt dat Claude zelf kan doen is verspilde tijd.

**How to apply:** voer zelf uit, test en meet na (ook lokaal, ook via Chrome), en zet alleen in actiepunten wat echt alleen Daniel kan. Zie ook [[nieuwe-mac-routines-herstellen]].

---

## -Users-danieldekoning-Projects-omnivaleur / feedback-klant-niet-afraden

*25-11-2026*

Daniel, 25-11-2026: zinnen als "Voor jou is er dan weinig extra ten opzichte van GoedGeplaatst, dus als dat goed werkt zou ik daarbij blijven" wil hij niet meer in klant- of leadmails.

**Why:** het praat een warme lead weg van de proef; eerlijk zijn gaat over feiten (wat kan niet), niet over een oordeel of de klant het nodig heeft.
**How to apply:** zeg wat Omnivaleur doet, kost en niet kan, nodig uit tot de gratis proef (ook naast een concurrent), en zet twijfel over geschiktheid alleen in het rapport aan Daniel. Staat ook in docs/schrijfstijl-daniel.md. Zie [[reference-elevenlabs-sleutel]] niet nodig; gerelateerd aan stijlregels in dat bestand.

---

## -Users-danieldekoning-Projects-omnivaleur / social-videos-3d

*25-11-2026*

Daniel (25-11-2026): video's zoals goed scorende Instagram-animaties (1 shot per seconde, wisselende kamers, bewegende camera, stem met intonatie). Taal voorlopig Engels, absurd/grappig mag, duidelijke storyline, nooit AI-slop. Drie stijlen (A blocky, B toon, C real) naast elkaar zodat hij kan kiezen en de routine op meting naar de winnaar groeit.

Week 48: alle drie (-v2) door Daniel ingepland via Schedchie. Zijn rangorde: 1 C real-kevin, 2 B toon-midnight, 3 A blocky-hoodie. Hij is nog niet tevreden en verwacht stapsgewijze verbetering. Meting op dinsdag 01-12-2026 via Schedchie (TikTok niet gekoppeld, via Chrome), plus wekelijkse trendronde en bewuste afwisseling (helft winnaar, helft test).

**Why:** de 2D-video's scoorden visueel niet mee; de referenties hebben 3D, camerabeweging en tempo.
**How to apply:** gebruik `scripts/video/motion3d/` (recept in docs/video-recept.md, sectie 3D-pijplijn; voice via `genvoice_ts.py` met eleven_v3 en `tempo.py`; botsingen controleren met `chk.sh`). Python met audio-libs: `~/claude-animation-skills/kit/.venv/bin/python`. Bij moeilijke ontwerpvragen mag een adviseur (Opus of Fable) via Agent worden gevraagd; Daniel heeft dat toegestaan. Zie [[social-videos-animatie]].

---

## -Users-danieldekoning-Projects-omnivaleur / social-videos-animatie

*24-11-2026*

Daniel (24-11-2026): de video's hoeven niet hyperrealistisch, wel mooie, logische, pakkende animaties die de pijnpunten van Omnivaleur tonen en hoe die opgelost worden. Hij plaatst zelf wekelijks via Schedchie (TikTok erbij; TikTok is niet gekoppeld aan de connector, Facebook geblokkeerd).

**Why:** de oude 3D-poppetjes en tekstvideo's haalden bijna niets (2 oude posts, 1 tot 9 weergaven) en lieten zich als AI herkennen.

**How to apply:**
- Pijplijn staat in `scripts/video/motion/` (engine.js, kit.js, videos/<naam>.js), renderen met `V=<naam> node render2.mjs video out/<naam>.silent.mp4 30` (DOM-animatie, ±0,17 s per frame, 20 s ≈ 2 min). Elke video is een pure functie van de tijd; scènetijden komen uit de woordtiming van de stem (`at('woord')`).
- Stem: ElevenLabs TTS, model `eleven_multilingual_v2`, alleen de TTS-endpoint werkt met de sleutel (zie [[reference-elevenlabs-sleutel]]). Premade stem-id's werken: George JBFqnCBsd6RMkjVDRZzb, Rachel 21m00Tcm4TlvDq8ikWAM, Adam pNInz6obpgDQGcFmaJgB, Bella EXAVITQu4vr4xnSDxMaL, Josh TxGEqnHWrfWFTfGW9XjX. Kosten: ±240 tekens per video (gratis tegoed volstaat).
- Woordtiming via `kit/words.py <mp3> <script.txt>` met de kit-venv; geluid via `audio2.py` (bed + zachte effecten uit de scenecues) en `mix2.sh` (twee-pass loudnorm naar -14 LUFS, piek onder -1,5 dBTP).
- Gebruik echte logo's (assets/) en het echte dashboard (crop uit `frontend/assets/dashboard/*.webp`, oud maar echt).
- Slop-check blijft: een Nederlands script geeft altijd rood op 'geen samentrekking' (Engelse regel), dat is een vals alarm.

---

## -Users-danieldekoning-Projects-omnivaleur / reference-elevenlabs-sleutel

*24-11-2026*

Daniel gaf de sleutel op 24-11-2026; opgeslagen buiten de repo. Alleen recht text_to_speech (voices_read en user_read geven 401), TTS getest: werkt. Gebruik voor social video's (zie [[social-videos-animatie]]). Nooit in chat, git of logs herhalen.

---
