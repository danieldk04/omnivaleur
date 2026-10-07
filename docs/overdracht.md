# Overdracht: lees dit als eerste

Bijgewerkt 05-10-2026 door de sessie op Daniels account, op zijn verzoek, voordat de
tweede ontwikkelaar een tijd het werk overneemt. Doel: jij hebt direct het huidige beeld,
doet geen dubbel werk en zet de vaste routines zelf aan zonder dat Daniel erom hoeft te
vragen.

## Wat je in je EERSTE sessie zelf doet, zonder te vragen

1. `git pull`. Lees daarna deze pagina, de onderkant van `docs/team-notes.md` (laatste
   ~150 regels) en zoek in `docs/kennisbank.md` gericht op het onderwerp van je opdracht
   (`grep -n "^## " docs/kennisbank.md` geeft alle lessen; nooit het hele bestand lezen).
2. Controleer je geplande taken (`list_scheduled_tasks`). Maak ontbrekende zelf aan,
   lokale tijd, met de tekst "Je werkt aan Omnivaleur in <jouw repomap>. Lees <bestand>
   in die repo en volg het precies. Rondenaam: <naam>.":
   - `omnivaleur-onboarding-nieuwe-klanten-middag`, dagelijks 10:00,
     bestand `docs/routines/onboarding-nieuwe-klanten.md`, rondenaam `onboarding-middag`.
   - `omnivaleur-klantfouten-middagronde`, dagelijks 14:00,
     bestand `docs/routines/klantfouten.md`, rondenaam `middagronde`.
   Staat er al een met een ander tijdstip, zet hem op bovenstaand tijdstip. Schrijf in
   `docs/team-notes.md` dat ze staan, en push.
3. Draai meteen een eerste keer wat vandaag nog niet gedraaid is (het gedeelde slot
   `python3 scripts/klantfouten.py ronde begin <rondenaam>` zegt of een andere ronde bezig
   is of net klaar was; bij exit 3 niet forceren). Zo ben je niet tot 10:00 of 14:00 blind.
4. Controleer of je lokale `.env` de Supabase-service-sleutel heeft en dat
   `python3 -c "from backend.database import get_db"` werkt. Zo niet: zie kennisbank
   "env-extra-sleutel-blokkeert-scripts" en "railway-blokkeert-smtp". Vraag Daniel pas
   als het echt niet lukt.
5. Noem in je eerste antwoord kort wat je gezien hebt (CLAUDE.md eist dat).

## De vaste routines (alles staat als bestand in de repo)

| Routine | Wie / wanneer | Bestand |
|---|---|---|
| Klantfouten: waar liepen klanten de laatste 24 uur tegenaan, repareren, vastleggen | Daniels Mac 08:00 (`ochtendronde`), jouw account 14:00 (`middagronde`) | `docs/routines/klantfouten.md` |
| Onboarding: elke klant in zijn eerste week nalopen, repareren, mailtje klaarzetten dat Daniel verstuurt | Daniels Mac 06:30 (`onboarding-ochtend`), jouw account 10:00 (`onboarding-middag`) | `docs/routines/onboarding-nieuwe-klanten.md` |
| Kosten bijhouden (Drive-sheet "Omnivaleur kosten") | Daniels Mac, 1e van de maand | `docs/routines/kosten-bijhouden.md` |
| Schrijfstijl leren uit Daniels verzonden mail | Alleen Daniels Mac (heeft de Zoho-toegang), dagelijks 07:21 | `docs/schrijfstijl-daniel.md` |

Allebei de dagelijkse routines delen één slot, dus twee rondes doen nooit tegelijk
hetzelfde. Wat een vorige ronde als gerepareerd noteerde, repareer je niet opnieuw: je
meet alleen of het weg is. Elke ronde sluit je altijd af met `ronde klaar`, ook bij
afbreken.

Eenmalige taken op Daniels account (jij hoeft ze niet te doen): Egbert-verlengingen meten
(05-10), Egbert-stiltes beoordelen (06-10), Watchero-follow-up (07-10), mp-video
weekmeting (11-10).

## Werkafspraken die overal gelden

- Antwoord Nederlands, gewone taal, de vier blokjes (wat er aan de hand was, wat er nu
  veranderd is, zekerheid in %, actiepunten met `[NU/DEZE WEEK/OOIT/OVERSLAAN, tijd]`).
  Nooit een gedachtestreepje als leesteken. In mail die Daniel verstuurt geen opmaak.
- "Waarschijnlijk goed" bestaat niet: oorzaak bewijzen, echte code draaien, voor-en-na-proef
  (oude versie laten falen). Een lege meting eerst wantrouwen.
- Elke wijziging aan klanttekst: ook in het Nederlands (`python3 scripts/i18n_extract.py`,
  zie CLAUDE.md). De GitHub-proef kleurt anders rood.
- De auto-push-hook zet elke Edit los live (kennisbank: "auto-push-zet-tussenstand-live").
  Werk dus in kleine, werkende stappen en kijk na een push of `git ls-files -u` leeg is.
- Meten op de productiedatabase: nooit een zware telling over meerdere klanten, alleen per
  user_id of in brokken (kennisbank: "meten-op-de-productiedatabase").
- Klantdata nooit destructief aanraken zonder Daniel. Mails aan klanten verstuurt hij zelf;
  jij zet ze klaar. Brengt hij je een klantmail: eerst `docs/schrijfstijl-daniel.md`
  lezen en je concept bewaren met `scripts/schrijfstijl_leren.py concept`.
- Leer je iets nieuws dat ook op Daniels account moet gelden: geheugenbestand schrijven,
  `python3 scripts/export_kennisbank.py`, committen. Beslissing of afspraak: dagboekregel
  in `docs/team-notes.md`, pushen.
- Zuinig met tokens: batchen, gericht lezen, geen subagents tenzij Daniel erom vraagt.

## Stand van zaken per 05-10-2026

Open voor Daniel (niet voor jou):
- Extensie 1.0.367, 1.0.368 en 1.0.369 staan nog niet in de Web Store
  (`dist/omnivaleur-extension-1.0.369.zip` bevat alles). Tot dan krijgen Egbert (bcdf9aa4)
  en Vagif (1ba42900, verstelbare ring) de reparaties niet.
- Tabel `extension_stiltes` moet nog met de hand in Supabase aangemaakt worden (commit 0c6e0a13).
- Daniel mailt Goudlief de uitleg "Shopify koppelen met Omnivaleur".

Lopend en relevant voor je werk:
- **Goudlief (info@goudlief.nl, user 5aae4954)**: nieuwe proef van 7 dagen tot 11-10-2026
  16:58 UTC, om Shopify te koppelen en te proberen. Ze zat sinds 13-09 op slot, las nooit
  een artikel in. De koppelknop blokkeerde het scherm-slot, de server niet.
- **Shopify-import** (gebouwd 23-09, `backend/services/shopify_scan.py`): Import > Shopify >
  Scan leest actieve producten via de server, zonder extensie. Echt gedraaid op Revaleurs
  winkel (304 producten). Een product met meerdere varianten komt binnen als één artikel.
  Lees vóór je eraan werkt in de kennisbank: `shopify-zoeken-op-sku-stopte-te-vroeg`,
  `shopify-nummer-gaat-voor-titel`, `shopify-app-store-geweigerd`,
  `lijst-en-knop-delen-een-beslissing`, `klaar-klusje-herlaadt-hele-voorraad`
  (database ging plat door herladen), `storing-mag-nooit-als-antwoord-tellen`.
- Klant-eigen, niet repareren: 96e30080 (Chromebook, vaak uit), 0b28c1ce (extensie sinds
  01-10 offline, abonnement liep 05-10 af), 26cf5471 (Vinted niet ingelogd).
- Meting loopt: Egbert (bcdf9aa4) 2dehands-verlengingen en stiltes. Zie de laatste
  kopjes in team-notes voor de uitkomst voordat je er iets aan doet.
- Koude mail aan winkels en webshops: evaluatie per bron rond 11-10.
- Open idee, geen prioriteit: als "No tab with id" in reeksen terugkomt, laat de extensie
  meesturen of het tabblad door de gebruiker of met het venster is gesloten.
- Op de planning voor later (Daniel, 07-10-2026), niet zelf oppakken: Daniel komt erop terug.
  1. Rubriekvraag bij importeren kleiner maken: nu ~9.000 tokens per product omdat alle 469
     rubrieken meegaan; alleen de passende tak meesturen scheelt ~10x. Raakt de rubriekkwaliteit,
     dus voor-en-na meten (zie kennisbank rubriekvraag-volgorde-niet-omgooien).
  2. (07-10: module `backend/services/titel_ai.py` gebouwd en getest, NIET aangesloten; zie team-notes
     07-10-2026 "AI-titels getest") AI-titels voor Marktplaats/2dehands: alleen titels boven 60 tekens, ~25 per vraag, eenmalig
     per artikel bewaren, met controle dat elk woord in de oude titel staat (anders terug naar
     _mp_titel). Metingen en voorbeelden: team-notes 07-10-2026 "AI-titels en rubriekvraag".

Prijs en product in het kort: EUR 19,99 per maand, 5 kanalen, 7 dagen proef plus 2 respijt;
Omnivaleur Light EUR 9,99 tot 20 actieve artikelen. Details in kennisbank
(`omnivaleur-demovideo-en-prijs`, `proefperiode-en-toegangsslot`, `omnivaleur-light-plan`).
