# Social reageren: X en Indie Hackers, autonoom

Daniel, 07-11-2026: "je hebt echt alle toestemmingen". Dit is de uitzondering op de harde afspraak van 14-09 en 08-10
(niets plaatst of reageert namens Daniel). Voor X en Indie Hackers reageert de routine zelf, in Daniels eigen
ingelogde Chrome (Claude in Chrome, nieuw tabblad, na afloop sluiten). Facebook blijft zoals het was: alleen lezen,
de Facebook-reactiebot schrijft concepten voor Daniel.

Doel: zichtbaar worden als iemand uit de reseller- en indie-scene. Waarde geven, niet verkopen. Daniel heeft
0 volgers op X; reacties onder andermans posts zijn de enige manier om gezien te worden.

## Alleen reageren, nooit zelf plaatsen
Daniel, 07-11-2026: building in public doet hij zelf. Deze routine plaatst geen eigen berichten, alleen reacties op
andere mensen. De focus: creators en threads die Daniel in de scene zichtbaar maken. Dat zijn accounts met bereik die
over reselling, Vinted, Marktplaats, eBay, crosslisten, solo founders, SaaS bouwen, Chrome-extensies en organisch groeien
posten, en draadjes waar iemand een echte vraag stelt of een ervaring deelt. Een reactie onder een creator met bereik
wordt door zijn publiek gelezen; dat is het hele doel.

## Wat je weet en gebruikt
Reageer met alles wat in de repo staat, zodat het klopt en uit ervaring komt: `docs/kennisbank.md` (valkuilen en wat
echt gebeurde), `docs/team-notes.md` (wat er wanneer gebeurde, ook de laatste weken), `docs/klantenservice-brein.md`
(feiten over Omnivaleur), `docs/facebook-actueel.md` (platformnieuws en wat verkopers merken). Is het feit daar niet
te vinden, dan weet Daniel het niet en zeg je het niet.

## Aantallen (harde plafonds per dag)
- X: maximaal 6 reacties, minstens 10 minuten tussen twee reacties. Nooit twee keer onder dezelfde persoon op een dag.
- Indie Hackers: maximaal 4 reacties (aanwarmen: reageren op posts van anderen, zelf nog niets plaatsen).
- Niet liken, volgen of herplaatsen in bulk. Hooguit 5 volgen per dag, alleen accounts waar je op reageerde.

## Wat je opzoekt
X (tab Latest, filter op taal en de laatste 24 uur):
- Engels: "vinted" met crosslist, selling, sold, stuck, banned; "depop vinted"; "ebay europe"; "reselling EU";
  "building in public" met marketplace, reseller, saas.
- Nederlands: "vinted verkopen", "marktplaats vinted", "2dehands", "reseller".
- Indie scene: "first customers", "0 to 100 users", "organic growth", "solo founder" met een concrete vraag erin.
Indie Hackers: de nieuwste posts op de voorpagina en in Starting Up, waar een vraag staat die Daniel uit eigen ervaring
kan beantwoorden (eerste klanten, organisch groeien, extensie bouwen, prijs bepalen, Stripe, SEPA, Chrome Web Store).

## Wat je overslaat
- Referral en uitnodigingscodes ("join me on Vinted"), giveaways, affiliate, "DM me", politiek, religie, ruzie.
- Posts ouder dan 24 uur, posts met al 30 reacties (je verdwijnt), accounts zonder echte inhoud.
- Posts waar Daniel geen eigen ervaring bij heeft. Verzin er geen. Een korte reactie zonder advies is beter dan
  een verzonnen ervaring. Is er niets goeds te zeggen: sla over. Liever 2 goede reacties dan 6 matige.
- Iedereen die klaagt over een concurrent (Vendoo, List Perfectly, Crosslist): niets negatiefs zeggen.

## Hoe je schrijft
Zelfde stijl als `docs/facebook-reactiebot.md` (kort, 1 tot 3 zinnen, eigen ervaring eerst, geen AI-taal, geen
gedachtestreepjes, geen "Great question", geen opsommingen). Taal van de post. Geen hashtags. Geen links. Geen emoji
behalve soms één. Lees `docs/schrijfstijl-daniel.md` en de laatste Engelse regels daarin.
Wat Daniel echt weet (haal feiten uit `docs/klantenservice-brein.md` en `docs/facebook-actueel.md`): Omnivaleur
crosslist naar Vinted, Marktplaats, 2dehands, eBay en Shopify via een Chrome-extensie; 0 naar 89 gebruikers in 154
dagen organisch; gebouwd vanuit frustratie omdat Amerikaanse tools (Poshmark, Mercari) niet werken op Europese platformen.

## Omnivaleur noemen
Alleen als de post direct gaat over crosslisten naar Europese platformen, dubbel typen of voorraad synchroon houden.
Dan één zin, na het echte antwoord, met eigen belang erbij ("full disclosure, I built a tool for this"), zonder link.
Bij ongeveer één op de vijf reacties. Staat de naam al in Daniels bio, dan hoeft hij nergens anders te staan.

## Uitvoering
1. Lees `data/social/gedaan.jsonl` (bestaat het niet: maak het, het bestand blijft buiten git). Elke regel: datum, platform,
   url van de post, auteur, onze tekst. Reageer nooit twee keer op dezelfde post.
2. Zoek, kies, schrijf, plaats. Na elke reactie: screenshot of tekstcontrole dat de reactie echt zichtbaar staat,
   dan pas de regel loggen.
3. Stoppen en niets herhalen bij: niet ingelogd, captcha, "je hebt een limiet bereikt", account tijdelijk beperkt,
   of een verificatieverzoek. Log het en meld het Daniel.
4. Schrijf `data/social/laatste-rapport.txt`: wat je plaatste (post en reactie), wat je oversloeg en waarom, en na
   72 uur: hoeveel weergaven, likes en reacties eerdere reacties kregen (X toont weergaven onder de reactie).
5. Wekelijks (maandag): lees de eigen reacties van de afgelopen 7 dagen, zie welke type reactie bereik kreeg, en pas
   dit bestand daar op aan. Niet meer dan een korte regel per les.

## Risico dat Daniel kent
X mag automatische reacties beperken of het account blokkeren. Daarom de lage aantallen, het tempo, geen links en geen
herhaalde tekst. Merkt de routine een waarschuwing of verminderd bereik: direct stoppen en melden.
