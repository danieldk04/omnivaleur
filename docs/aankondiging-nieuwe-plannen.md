# Aankondiging nieuwe plannen en vriendenactie (concept, 11-11-2026)

Niets hiervan staat live. Dit zijn de teksten en de volgorde, klaar om te gebruiken zodra de meting
van de foto naar advertentie (19-11) uitwijst of het AI-pakket beloofd mag worden. Plekken waar dat
uitmaakt staan tussen [NA METING]. Geen streepjes als leesteken, geen opmaaktekens in mail.

## Volgorde (alles pas na jouw ja)

1. 19-11: uitkomst meting. Goed genoeg: AI-pakket mag in de trap. Niet goed: de trap belooft alleen maanden gratis.
2. Railway: REFERRAL_KORTING_AAN aan. Eerst één echte ronde nakijken (de vriendenkorting zelf).
3. Rond 1 december: mail A (vriendenactie) en het "Wat is er nieuw"-venster met rondleiding in het dashboard.
4. Uiterlijk 1 december (liefst eerder): mail B (nieuwe plannen) aan wie een prijsverhoging krijgt. De algemene
   voorwaarden (art. 5) eisen minstens 30 dagen vooraf per e-mail bij een prijsverhoging. Nagekeken 14-11.
5. 1 januari: Plus- en Ultra-prijzen en NIEUWE_PLANNEN_AAN in Railway (de prijs-id's staan in team-notes van 11-11).
   Pro en Plus krijgen hun grens pas op 15 januari (invoeringsuitstel).

## Mail A: vriendenactie (NL, platte tekst)

Onderwerp: Een vriend uitnodigen levert je nu €10 per maand op

Hoi,

Daniel hier. Tot 1 januari geef ik meer terug aan wie een andere verkoper meeneemt.

Elke vriend die een betaald abonnement neemt (vanaf Pro) haalt €10 per maand van je eigen rekening, zolang hij betaalt.
Elke vriend levert je daarnaast 2 maanden gratis op. Bij 3 vrienden krijg je het AI-pakket, elke AI-functie zodra die live
gaat. Bij 5 vrienden heb je Ultra: alle functies, Etsy zodra die er is, de nieuwste functies eerst en voorrang bij support.

Je vriend start met een gratis proef, betaalt de eerste maand de helft, en ik lees zijn voorraad in en loop de eerste artikelen met hem na tot ze online staan.

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

Zo werkt het in de praktijk. We tellen je actieve artikelen en je zit in het plan dat daarbij past. Heb je bijvoorbeeld 180 actieve artikelen, dan blijf je op Pro voor €19,99 en verandert er niets. Heb je 600, dan is Plus het plan voor €29,99. Heb je er meer dan 1.500, dan is Ultra het plan voor €49. Zit je nu al zo hoog, dan mail ik je apart over een rustige overgang. Heb je maximaal 20 artikelen, dan kun je overstappen naar Light voor €9,99.

Zit je een keer boven je grens, dan kun je gewoon doorwerken met wat er staat. Alleen nieuwe artikelen worden dan pas geblokkeerd, en de grenzen van Pro en Plus gaan pas op 15 januari gelden, zodat je rustig kunt kiezen. Bij upgraden betaal je alleen het verschil.

Nodig je daarnaast vrienden uit, dan kan je plan goedkoper worden of zelfs gratis: elke betalende vriend haalt tot 1 januari €10 per maand van je factuur, en met 5 vrienden heb je Ultra. Je link staat in je dashboard onder Vrienden uitnodigen.

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

- Het klassement en de Founding Circle zijn gebouwd (18-11) maar staan uit (vlag KLASSEMENT_AAN); noem ze pas in een mail of venster als de vlag aan staat.
- Of het AI-pakket in de mail mag staan: 20-11 gebouwd en gemeten, vlag AI_PAKKET_AAN uit. Wat er in mag zodra Daniel de vlag aanzet staat hieronder (alleen bulkopdracht en titels inkorten; foto naar advertentie en beschrijving herschrijven NIET beloven).
- Mail A noemt bewust geen aantal proefdagen: de code geeft iedereen 7 dagen (billing.py), Daniel wil 14 voor aangebrachte vrienden, nog te bouwen; pas daarna "14 dagen" in mail A en op de aanmeldpagina zetten. Mail A mag naar alle klanten.
- Mail B is nu één mail voor iedereen met voorbeelden (besluit Daniel 20-11); niets per klant invullen. Controleer de voorbeeldgrenzen voor het versturen tegen de dan geldende stand.

## AI-pakket (donker sinds 20-11-2026, vlag AI_PAKKET_AAN uit): teksten klaar

Wat het pakket nu echt kan, gemeten op echte artikelen. Beloof niets anders.

- Wijzigingen in gewone taal voor al je artikelen tegelijk: "alle prijzen 10% omhoog", "1 euro erbij op Vinted", "zet onderaan de beschrijving ...". Je ziet eerst een voorbeeld op 5 artikelen en het totaal, bevestigt zelf, en kunt het met één klik ongedaan maken.
- Te lange titels voor Marktplaats en 2dehands slim inkorten zonder merk, maat of getal te verliezen. Alleen als de titel te lang is.

Wat NIET beloofd mag worden: een advertentie maken vanaf een foto (kleur 51 tot 67% goed, merk 41 tot 52%, maat 0%), beschrijvingen per kanaal herschrijven (88,5% haalt de controle, onder de grens).

Venster (pas bij livegang, tweetalig via i18n_extract):
Titel: Nieuw: pas al je artikelen aan in gewone taal
Tekst: Typ wat je wilt, bijvoorbeeld "alle prijzen 10% omhoog". Je ziet eerst een voorbeeld, bevestigt zelf en kunt alles met één klik terugzetten.
Updatelog (data-cat automation): "Wijzigingen in bulk in gewone taal. Typ een opdracht, bekijk het voorbeeld en bevestig. Ongedaan maken kan altijd." 
Rondleiding: één stap bij het opdrachtveld, "Typ hier wat je wilt veranderen. Je ziet eerst een voorbeeld."
Het dashboardscherm (opdrachtveld, voorbeeld, knoppen Bevestigen en Ongedaan maken) is nog NIET gebouwd; de routes onder /api/ai-pakket zijn klaar.
