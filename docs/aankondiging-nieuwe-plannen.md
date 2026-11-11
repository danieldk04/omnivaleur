# Aankondiging nieuwe plannen en vriendenactie (concept, 11-11-2026)

Niets hiervan staat live. Dit zijn de teksten en de volgorde, klaar om te gebruiken zodra de meting
van de foto naar advertentie (19-11) uitwijst of het AI-pakket beloofd mag worden. Plekken waar dat
uitmaakt staan tussen [NA METING]. Geen streepjes als leesteken, geen opmaaktekens in mail.

## Volgorde (alles pas na jouw ja)

1. 19-11: uitkomst meting. Goed genoeg: AI-pakket mag in de trap. Niet goed: de trap belooft alleen maanden gratis.
2. Railway: REFERRAL_KORTING_AAN aan. Eerst één echte ronde nakijken (de vriendenkorting zelf).
3. Rond 1 december: mail A (vriendenactie) en het "Wat is er nieuw"-venster met rondleiding in het dashboard.
4. Ruim voor 1 januari: mail B (nieuwe plannen) aan wie het raakt. Controleer eerst de algemene voorwaarden op de
   aanzegtermijn voor een prijswijziging, dat heb ik niet kunnen nazien.
5. 1 januari: Plus- en Ultra-prijzen en NIEUWE_PLANNEN_AAN in Railway (de prijs-id's staan in team-notes van 11-11).
   Pro en Plus krijgen hun grens pas op 15 januari (invoeringsuitstel).

## Mail A: vriendenactie (NL, platte tekst)

Onderwerp: Een vriend uitnodigen levert je nu €10 per maand op

Hoi,

Daniel hier. Tot 1 januari geef ik meer terug aan wie een andere verkoper meeneemt.

Elke vriend die een betaald abonnement neemt (vanaf Pro) haalt €10 per maand van je eigen rekening, zolang hij betaalt.
Je eerste vriend levert je daarnaast 2 maanden gratis op. Bij 3 vrienden [NA METING: krijg je er het AI-pakket bij, foto
naar advertentie en AI-titels]. Bij 5 vrienden heb je alles.

Je vriend start met 30 dagen proef, betaalt de eerste maand de helft, en ik zet zijn eerste 100 artikelen voor hem in.

Je persoonlijke link staat in je dashboard onder Uitnodigen. Wie voor 1 januari begint houdt de €10 ook daarna.

Groetjes,

Daniel

## Mail B: nieuwe plannen per 1 januari (NL, platte tekst)

Onderwerp: Wat er per 1 januari verandert in je abonnement

Hoi,

Daniel hier. Per 1 januari rekent Omnivaleur niet meer op alles of niets, maar op het aantal actieve artikelen per factuur.

Light: tot 20 artikelen, €9,99 per maand incl. btw. Pro: tot 250, €19,99. Plus: tot 1.500, €29,99. Ultra: onbeperkt,
€49, met Etsy zodra die er is, de nieuwste functies eerst, het AI-pakket en voorrang bij support. Kies je jaarlijks, dan
betaal je 10 maanden in plaats van 12.

Voor jou betekent dat: [PER KLANT INVULLEN: blijft €19,99, of de gefaseerde stap]. Zit je een keer boven je grens, dan
kun je gewoon doorwerken met wat er staat. Alleen nieuwe artikelen worden dan pas geblokkeerd, en je hebt tot 15
januari om rustig te kiezen. Bij upgraden betaal je alleen het verschil.

Vragen? Reageer gewoon op deze mail.

Groetjes,

Daniel

## "Wat is er nieuw" venster (frontend/app.html, #nieuws-venster)

Titel: Nieuw: meer verdienen aan uitnodigen, en plannen die meegroeien
Tekst: Tot 1 januari krijg je €10 per maand per betalende vriend en 2 maanden gratis bij je eerste vriend. Per 1 januari
kies je het plan dat bij je voorraad past: Light, Pro, Plus of Ultra, maandelijks of per jaar.
Instellen: NIEUWS_ID '2026-12-uitnodigen', NIEUWS_SINDS de datum van livegang. Beide talen via i18n_extract.

## Updatelog bericht (bovenaan #view-nieuw, data-cat plans)

Titel: Plannen die meegroeien met je voorraad
Twee zinnen: Kies Light, Pro, Plus of Ultra op basis van je actieve artikelen. Betaal je jaarlijks, dan krijg je 2 maanden gratis en upgraden betaalt alleen het verschil.

## Rondleiding (stappen in #rondleiding-stappen)

1. view uitnodigen, doel de voortgangskaart met 1, 3 en 5 vrienden: "Hier zie je hoeveel vrienden je al hebt en wat de volgende trede geeft."
2. view abonnement, doel "Meer ruimte nodig?": "Hier upgrade je en betaal je alleen het verschil."
Loop beide stappen zelf af in de browser voor de livegang, zoals in CLAUDE.md staat.

## Nog open voor dit pakket

- Het klassement en de Founding Circle bestaan nog niet; noem ze dus nog niet in een mail of venster.
- Of het AI-pakket in de mail mag staan: wacht op 19-11.
- Per klant bepalen wat mail B zegt voor de grote drie (gefaseerd 29,99, 39, 49).
