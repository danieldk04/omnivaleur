---
name: kwartaalcheck
description: Kwartaalcheck van Daniels doelen tot eind 2027. Meet de actuele status van elk doel tegen vloer, stretch en kwartaalmijlpaal, haalt zelf op wat te halen is en vraagt alleen wat niet te meten valt. Activeer bij "kwartaalcheck", "check-up doelen", "hoe sta ik ervoor", "status doelen", "loop ik op schema", of wanneer de geplande kwartaalmelding afgaat.
---

# Kwartaalcheck: de thermometer in Daniels doelen

Dit is een meting, geen coachingsgesprek. Doel: eerlijk laten zien of Daniels jaar als ondernemer op schema ligt, zodat hij aan het eind van 2027 weet of het geslaagd is.

## Bron van de doelen (nooit hier kopieren)

De doelen staan in het Google Doc "Omnivaleur en Revaleur: strategie tot eind 2027":
https://docs.google.com/document/d/1vqKmbQmbwgM_PCCa9C7Eo3_XZU_D_Hnz6ZoaE9x9Pp4/edit
(Drive-map "Omnivaleur"). Lees dat document elke keer opnieuw met de Drive-tool (read_file_content). Zet geen getallen in deze skill: het document is de enige waarheid. Heeft Daniel het document verplaatst of vervangen, zoek dan in Drive op "strategie tot eind 2027" en gebruik de nieuwste.

Staat er in het document nog "concept", "nog niet definitief" of zijn de getallen kennelijk in beweging, meld dat bovenaan en vraag of Daniel de huidige getallen als meetlat wil gebruiken voordat je meet.

Lees ook het meetlog: `~/.claude/skills/kwartaalcheck/meetlog.md` (kan nog niet bestaan). Begin elke check bij de vorige uitslag, zodat de lijn door het jaar zichtbaar wordt.

## Werkwijze

1. Lees het document. Haal er elk doel uit: metric, vloer, stretch en de tussenmijlpaal van het afgelopen kwartaal.
2. Meet elk doel zo ver mogelijk zelf, in deze volgorde van betrouwbaarheid:
   - **Omnivaleur, betalende klanten:** tabel `subscriptions` in de productiedatabase (58 rijen op 04-10-2026, een lichte meting). Draai vanuit `~/Documents/omnivaleur` met `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` en `from backend.database import get_db`. Tel `status` per `plan`; "betalend" is `active` met `stripe_subscription_id`. Noem `trialing` (met en zonder kaart), `payment_processing`, `canceled` en `trial_expired` apart. Sluit eigen accounts uit: e-mail op omnivaleur.com, crosslisteu.com of revaleur.com (e-mail via `scripts/nieuwe_klanten.py` functie `accounts(get_admin_db())`). Meet nooit zwaardere tabellen (jobs, items): de productiedatabase viel eerder om (kennisbank, "meten-op-de-productiedatabase"). Stand 04-10-2026 als nulmeting: 6 actief Pro, 0 actief Light.
   - **Omnivaleur, omzet:** Pro is EUR 19,99 per maand, Light EUR 9,99. Neem de echte bedragen uit Stripe als je erbij kunt; anders klanten maal prijs en noem dat een schatting. Reken btw eraf (21%) en Stripe-kosten (ongeveer EUR 0,57 per betaling van 19,99).
   - **Omnivaleur, kosten:** Google Sheet "Kosten en doelen (Omnivaleur en Revaleur)" (id `1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U`, map Omnivaleur), bijgewerkt op de 1e van elke maand door de taak `omnivaleur-kosten-bijhouden`. Lees de totaalrijen (vast, wisselend, totaal per maand). Is `Gemeten op` ouder dan 40 dagen, meld dat de kosten verouderd zijn. Stand 04-10-2026: ongeveer EUR 60,76 per maand.
   - **Revaleur, winst:** Google Sheet "Profitsheet Right" (id `13tHt7SWYqYdPKwyZaj5kkAcZt3G_IJCzksZYSL-zxgI`, tab P&L). Download als CSV met Drive `download_file_content` (exportMimeType `text/csv`), niet `read_file_content` (kapt rijen af). Het resultaat wordt in een bestand opgeslagen: lees het met python. Groepeer op kolom `Date Sold` (formaat d-m-jjjj), som kolom `Profit` en `Price Sold` per maand, en tel de rijen zonder `Date Sold` maar met `Date Bought` als voorraad. Getallen zijn in Nederlandse notatie ("€ 70,00"). Gebruik het gemiddelde van de laatste drie volle maanden en laat de lopende maand buiten beschouwing. Controleer dat er geen verkopen zonder winstwaarde zijn. Nulmeting 04-10-2026: juli 176, augustus 255, september 286 (ongeveer EUR 240 per maand), 358 items op voorraad.
   - **Eindcijfer:** winst vóór belasting per maand = Revaleur-winst plus Omnivaleur (omzet ex btw min Stripe-kosten min kosten uit de sheet), plus eventuele andere ondernemingen die Daniel noemt. Vloer EUR 4.000 per maand, gemiddeld over het laatste kwartaal van 2027. Reken ook uit hoeveel klanten er bij de huidige prijs voor nodig zijn.
   - **Omnivaleur, bezoekers en aanmeldingen:** uit de wekelijkse GA4/Search Console-cijfers in `docs/team-notes.md` en de productielogboeken.
   - **Revaleur, omzet, marge, voorraad:** uit de Google Spreadsheet "Profitsheet Right" via de Drive-tool.
   - **Alles wat nergens in een systeem staat:** niet raden. Verzamel het als vraag voor Daniel.

Alleen ondernemersdoelen horen in deze check. Gewicht en Bergweg zijn bewust geschrapt (04-10-2026): meet ze niet, ook niet als het oude document ze nog noemt.
3. Wantrouw lege uitkomsten. Een meting die 0 of leeg zegt: eerst controleren of de meting zelf klopte (juiste tabel, juiste periode, juiste statussen), pas dan melden.
4. Vergelijk elke meting met vloer, stretch en de mijlpaal van dit kwartaal. Geef per doel een duidelijk oordeel: VOOR op schema, OP schema, ACHTER, of NIET TE MEETEN. Reken een lineair pad naar de eindvloer door als er geen mijlpaal is.
5. Wat je niet kon meten schrijf je met zoveel woorden als openstaand punt op, niet verstopt in een percentage.

## Vragen aan Daniel

Stel pas vragen na je eigen meting, en dan alleen over wat je echt niet kon vinden. Bundel ze in een genummerde lijst, in een keer. Wacht niet op antwoorden om het deel dat wel gemeten is te rapporteren.

Draait de check automatisch (geplande taak) en Daniel is er niet: zet de vragen bovenaan het rapport en sla het rapport op in het meetlog met de vragen als "open". Pas het log aan zodra hij antwoordt.

## De som achter het eindcijfer

Reken elke check het eindcijfer uit als: winst = betalende klanten × netto prijs per klant (zonder btw en Stripe-kosten) min alle kosten, plus Revaleur-winst en eventuele andere ondernemingen. Zet de drie onderdelen naast elkaar en benoem waar het gat zit: te weinig klanten, een te lage prijs of te hoge kosten. Reken ook uit hoeveel klanten nodig zijn bij de huidige prijs en bij het grote reseller-plan van EUR 50 zodra dat bestaat.

## Voorlopers (naast de uitslag)

- **Activatie:** aandeel nieuwe accounts (sinds de vorige check) dat 30 of meer artikelen inleest. Nulmeting 27-09-2026: niemand onder 100 artikelen betaalde, en 5 van de 13 accounts met 30 of meer betaalden. Tel `items` alleen per user_id met `count`, licht en in kleine brokken.
- **Doorverwijzing:** aandeel nieuwe betalende klanten via een verwijscode (tabel `referral_codes`) of vanzelf. Dit is de toets of de sneeuwbal op gang komt.
- **Weekcijfers (mails, gesprekken, 24-uursstart):** er bestaat nog geen norm. Meet eerst vier weken en stel dan samen met Daniel de norm vast. Verzin er geen.

## Maandmodus (1e van elke maand, ook een van de kwartaalmaanden)

Een korte check, geen volledig rapport. Lees de actuele cijfers (klanten, kosten uit de sheet, Revaleur-winst), reken de som uit en vergelijk met de tussenmijlpaal voor winst per maand: 31-12-2026 EUR 500, 31-03-2027 EUR 1.200, 30-06-2027 EUR 2.000, 30-09-2027 EUR 3.000, 31-12-2027 EUR 4.000. Tussen twee mijlpalen reken je het lineaire pad uit. Rapporteer in een regel: winst per maand, betalende klanten, VOOR/OP schema/ACHTER op de mijlpaal, en in welk onderdeel van de som het gat zit. Voeg een korte regel toe aan het meetlog. Geen vragen, geen vier blokjes: alleen de regel plus, als er iets niet te meten was, die ene reden.

## Melding

Stuur na elke check, maand of kwartaal, een PushNotification (status proactive) van een regel: winst per maand, voor of achter op de mijlpaal, en bij een kwartaalcheck het aantal vragen aan Daniel. Houd het onder 200 tekens, zonder opmaak en zonder gedachtestreepjes.

## Rapportage

Antwoord in het Nederlands, gewone taal, kort. Daniel is geen programmeur: gevolgen boven techniek. Geen gedachtestreepjes of losse streepjes als leesteken, geen codeblokken.

Gebruik de vier blokjes uit zijn CLAUDE.md:
1. **Wat er aan de hand was**: waar staat hij nu, in een of twee zinnen, als gevolg niet als techniek.
2. **Wat er nu veranderd is**: alleen wat sinds de vorige check verschoof (laat weg bij de eerste check).
3. **Zekerheid: X%**: hoe zeker de metingen zijn, met in een zin waarom niet 100%.
4. **Actiepunten**: genummerd, alleen wat Daniel zelf moet doen, met `[NU, 2 min]`, `[DEZE WEEK, 10 min]`, `[OOIT, 5 min]` of `[OVERSLAAN]`.

Tussen blok 1 en 3 hoort een compact overzicht per doel: huidige waarde, vloer, stretch, mijlpaal dit kwartaal, oordeel. Daarna de verandering ten opzichte van de vorige check.

Sluit af met een eerlijke zin over de grote lijn: ligt dit jaar op koers voor de vloer, de stretch, of geen van beide? Beschouw niets als geslaagd wat niet gemeten is.

## Meetlog bijwerken

Voeg na elke check onderaan `~/.claude/skills/kwartaalcheck/meetlog.md` een blok toe: datum, kwartaal, per doel de gemeten waarde en het oordeel, de bron per waarde, en de openstaande vragen. Overschrijf nooit eerdere blokken. Maak het bestand aan bij de eerste check.

## Stand van zaken en focus bijwerken (na elke check)

Bovenaan het strategiedocument staat het kopje "Stand van zaken" met drie regels: laatste meting, focus van het kwartaal, en een vaste regel. Werk dat kopje na elke maand- en kwartaalcheck bij, en niets anders in het document.
1. Lees het document met `read_doc` (Docs-connector) en vind het kopje "Stand van zaken" en het volgende kopje. Gebruik de Google Workspace-skill (`references/docs.md`) voor de regels over indexen.
2. Vervang alleen de twee tekstregels onder het kopje: delete het bereik tussen de kopregel en de vaste regel en voeg de nieuwe regels in, met `writeControl.requiredRevisionId`. Behoud de kopregel en de vaste regel "Deze sectie wordt na elke maand- en kwartaalcheck automatisch bijgewerkt."
3. Regel 1: datum, winst per maand, mijlpaal van dit moment, en VOOR/OP schema/ACHTER met in een bijzin waar het gat zit.
4. Regel 2, de focus: kies bij een kwartaalcheck uit het grootste gat in de som een hoofdprioriteit voor het komende kwartaal (maximaal een per onderneming) en zet "voorstel" erbij zolang Daniel hem niet bevestigde. Bij een maandcheck laat je de focus ongemoeid, tenzij de meting hem tegenspreekt: dan noem je dat in regel 1.
5. Lees het document terug en controleer dat de rest ongewijzigd is. Geen gedachtestreepjes.

## Telegram

Stuur de regel van de melding ook via Telegram met `~/.claude/skills/kwartaalcheck/stuur_telegram.sh "<tekst>"`. Het script leest token en chat-id uit `~/.claude/skills/kwartaalcheck/telegram.env` (alleen door Daniel aangemaakt, nooit in de chat of in het log). Bestaat dat bestand niet of faalt het sturen: meld dat als een regel in het rapport, ga verder en laat de PushNotification dan wel gaan.

## Grenzen

Dit is een meting. Wijzig van het strategiedocument alleen het kopje "Stand van zaken", tenzij Daniel iets anders vraagt. Pas doelen nooit stilletjes aan om een meting beter te laten uitkomen: wijkt een doel af van de werkelijkheid, noem dat en laat Daniel beslissen.

## Meetlog-sheet bijwerken (na elke maand- en kwartaalcheck)

Sinds 01-11-2026 staat het meetlog in dezelfde Google Sheet als de kosten: "Kosten en doelen (Omnivaleur en Revaleur)" (id `1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U`, map Omnivaleur), tabs "Omnivaleur" (kosten Omnivaleur), "Revaleur" (kosten Revaleur), "Doelen meetlog" en "Uitgangspunten". De oude losse sheet "Doelen meetlog" (id 1OTAcG8jgp9bOuUekhJVoVOy6pPqnJj9PouebkSkrLfE, map Strategie en doelen) is niet meer de bron: schrijf daar nooit meer in.
Op tab "Doelen meetlog" staat één rij per maand (rij 5 is 04-10-2026, rij 6 is 01-11-2026, daarna de 1e van elke maand tot 01-12-2027). Vul alleen kolom B (betalende klanten), C (kosten Omnivaleur, uit F27 van tab Omnivaleur, "Totaal per maand") en D (Revaleur-winst: gemiddelde winst laatste drie volle maanden uit de Profitsheet min F14 van tab Revaleur) in de rij met de datum van deze maand, als gewone getallen. Kolommen E tot en met I (Omnivaleur winst, totaal, mijlpaal, verschil, oordeel) en de grafiek rekenen zelf mee: laat die met rust. Tab Uitgangspunten bevat prijs, btw, Stripe-kosten, marge en de mijlpalen: pas dat alleen aan als Daniel een doel wijzigt.
Schrijven kan nu rechtstreeks, zonder Chrome: gebruik de Sheets-klasse uit scripts/leadgen_sheets.py (python 3.13 in ~/Documents/omnivaleur, sleutel in ~/.omnivaleur/sheets-sleutel.json, zet die inhoud in de omgevingsvariabele GOOGLE_SHEETS_SLEUTEL) met `schrijf(bestand, [{"range": "'Doelen meetlog'!B6:D6", "values": [[11, 84, 251]]}])`. Dat schrijft RAW, dus alleen getallen, geen formules. Formules in deze sheet gebruiken puntkomma's als scheidingsteken (Nederlandse instellingen). Lees daarna `'Doelen meetlog'!A5:I19` terug en controleer dat kolom I een oordeel geeft en F25 tot F28 op tab Omnivaleur niet leeg zijn. Pas de nulmeting en eerdere rijen nooit aan. Is de rij van deze maand al ingevuld door een eerdere run, overschrijf dan alleen als de meting echt anders is en zeg dat.
