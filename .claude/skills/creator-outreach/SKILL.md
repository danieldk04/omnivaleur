---
name: creator-outreach
description: Mail aan Nederlandse creators die Omnivaleur op hun eigen Instagram willen bespreken. Activeer als Daniel een screenshot of tekst van een Instagram-profiel deelt (ook zonder tekst erbij), of zegt "creator", "check reacties", "stand creators", "creator mail". Maakt de persoonlijke mail klaar, legt verstuurd vast, zoekt reacties op in Zoho en leert van de uitkomsten.
---

# Creator-outreach (sinds 24-10-2026)

Daniel deelt een profiel (screenshot of geplakte tekst). Jij zet de mail klaar. Hij verstuurt zelf
vanuit Zoho (daniel@omnivaleur.nl), nooit via Resend. Je stuurt niets zelf.

Bestanden, niet dupliceren:
- Mailtekst en regels: `docs/creator-mail-instagram.md` (lees die, kopieer hem niet hierheen)
- Stijl: `docs/schrijfstijl-daniel.md`
- Logboek en meting: `scripts/creator_outreach_meting.py` (python3.13, vanuit de repo-root). Het logboek
  `data/creator_outreach/instagram.csv` staat buiten git en bevat e-mailadressen.

## Per profiel

1. Lees het profiel. Staat de handle al in het logboek (`stand`)? Dan is het dezelfde persoon, ook
   bij een Engels of tweede account met hetzelfde e-mailadres. Zeg dat, mail niet nog een keer.
2. Schrijf de mail uit `docs/creator-mail-instagram.md`. De openingszin gebruikt alleen wat je echt
   op het scherm ziet (bio, highlight, reeltitel). Nooit iets verzinnen (Hermes-tas, team-notes
   11-09-2026). Weet je een highlightnaam niet helemaal, noem dan alleen het zichtbare deel.
   Taal: Nederlands, Engels alleen als het account of Daniel dat aangeeft ("Best," als afsluiting).
   Onderwerp: `Ik voorzie een samenwerking, VOORNAAM`. Geen gedachtestreepjes, geen opmaaktekens.
3. Beoordeel eerlijk in de zekerheid: verkoopt ze zelf tweedehands (past), is ze een gewone
   brand-UGC creator (verwacht vaak een vast bedrag), zit ze bij een bureau of heeft ze een groot
   account (bijna zeker vast bedrag). Staat er geen e-mailadres, zeg dat en vraag het.
4. Antwoord in de vier blokjes uit CLAUDE.md. Actiepunt 1 is altijd "mail versturen".
5. Pas als Daniel zegt "verstuurd": loggen, met type en ruwe volgers:
   `python3.13 scripts/creator_outreach_meting.py log --handle H --naam N --email E --type verkoper|ugc|bureau --volgers 1500`
   Nooit loggen voor hij het bevestigt, ook niet als hij de mail plakt.

## Reacties en leren

Zegt Daniel "check reacties", of draait de wekelijkse taak `omnivaleur-creator-outreach-status`:
1. `stand` draaien. Per open handle in Zoho zoeken (`mcp__zoho-mail__mail_zoek` op het adres,
   ook in Verzonden voor de datum). Eerste reactie vastleggen: `reactie HANDLE ja|nee|geen`.
   "geen" pas na 7 dagen zonder antwoord.
2. Bij een ja: link aanmaken met `log --handle H --naam N --link` en Daniel vragen welke
   afspraak hij maakt (commissie 25%, of een vast bedrag). Commissie is gebouwd (27-10-2026):
   de link krijgt automatisch 25%, de server legt elk uur de betaalde facturen vast, en
   `python3.13 scripts/creator_commissie.py stand` toont wat Daniel verschuldigd is (uitbetaalbaar
   pas 60 dagen na de betaling). Een vast bedrag is niet gebouwd: zeg dat als hij dat kiest.
3. Leren: `stand` toont per type hoeveel er reageerden en ja zeiden. Trek pas conclusies bij
   ongeveer 30 mails; zeg dat de steekproef klein is zolang dat zo is. Zie je een patroon
   (bijvoorbeeld bureaus zeggen altijd nee, verkopers ja), zet het dan als voorstel aan Daniel:
   welk type moet hij vaker of minder benaderen, of moet de aanbieding veranderen (vast bedrag).
   Pas de mailtekst nooit zelf aan op basis hiervan, alleen als Daniel het goedkeurt.
4. Zet een duidelijke uitkomst (bijvoorbeeld "bureaus: 0 van 5") als dagboekregel in
   `docs/team-notes.md`.

## Wat Daniel hoort (ook zonder dat hij ernaar vraagt)

Eindig elk bericht over dit onderwerp met de stand in één regel: verstuurd, gereageerd, ja, nog
open, en of er mails 5+ dagen wachten (`stand` print "Opvolging nodig"). Een creator die na een
week niet reageerde krijgt hooguit één korte opvolging, alleen als Daniel dat wil.
