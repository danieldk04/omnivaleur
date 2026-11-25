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
