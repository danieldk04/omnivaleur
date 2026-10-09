# Omnivaleur — project instructions

This file is repo-local and checked into git, so it loads for every Claude
Code session opened against this repo — on any of Daniel's machines or
Anthropic accounts. That makes it the right place for anything that must
never depend on which account happens to be running.

## EERSTE STAP op een ander account dan Daniels: docs/overdracht.md

Lees [docs/overdracht.md](docs/overdracht.md) als allereerste, nog voor je de opdracht
uitvoert (Daniel, 05-10-2026). Daar staat de actuele stand, wat open staat, en wat je in je
eerste sessie zelf en zonder te vragen doet: de geplande routines aanmaken (onboarding
10:00, klantfouten 14:00), een eerste ronde draaien, en je omgeving controleren. De
opdrachten van de routines staan in `docs/routines/`. Daniel hoeft er niet om te vragen.

## Elk bericht: vier blokjes plus urgentie

Daniel, 19-09-2026. Elk antwoord aan hem krijgt dezelfde vorm, ook als er geen
code veranderde: wat er aan de hand was, wat er nu veranderd is, zekerheid in
procenten met in een zin waarom het geen 100% is, en daaronder de actiepunten.
Zo kort als het kan. Veranderde er niets, dan laat je dat blokje weg in plaats
van het op te vullen.

Nieuw is de urgentie. Achter elk actiepunt staat een label en hoeveel tijd het
hem kost, zodat hij in een oogopslag ziet waar zijn uur het meeste oplevert:

    1. [NU, 2 min]         er gaat vandaag iets mis; wachten kost klanten of geld
    2. [DEZE WEEK, 10 min] het wordt een probleem, alleen niet vandaag
    3. [OOIT, 5 min]       verbetering; er gaat niets stuk als het nooit gebeurt
    4. [OVERSLAAN]         genoemd voor de volledigheid, mijn advies is niet doen

De tijd die je noemt is zijn tijd, niet de jouwe. Wat jij zelf al deed of zelf
oppakt hoort niet in de lijst. Staat er niets open, dan schrijf je "Niets, klaar."

Waarom dit erbij moest: een lijstje waarin alles even zwaar oogt zette hem twee
keer aan het werk voor iets wat niets opleverde. Hij moet kunnen zien wat hij
zonder schade kan laten liggen.

Zo ziet een volledig bericht eruit (door Daniel goedgekeurd op 19-09-2026):

> **Wat er aan de hand was**
> Lynn keek een uur naar "nog even laden" terwijl de database plat lag, en Try
> again deed zichtbaar niets.
>
> **Wat er nu veranderd is**
> - Een storing heet een storing, met erbij dat het aan ons ligt en dat er niets kwijt is.
> - Try again springt meteen op "Checking…" en zet het tijdstip van de laatste poging op het scherm.
> - Een foutmelding telt niet meer als antwoord, dus haar kanalen en voorkeuren blijven staan.
>
> **Zekerheid: 93%**, getest tegen de oude versie, maar nog nooit bij een echte
> klant in een echte storing gezien.
>
> **Actiepunten**
> 1. [NU, 1 min] Mail Lynn de tekst, met erbij dat ze de pagina een keer moet verversen.
> 2. [OOIT, 2 min] Logs van 15:00 exporteren, alleen als je wilt weten waarom de database omviel.
> 3. [OVERSLAAN] De tests die de echte database aanspreken. Doe ik zelf.

## Vaste routines (dagelijks, op twee accounts)

- Klantfouten: ochtend ±08:00 (Daniels Mac), middag 14:00 (tweede account).
- Onboarding nieuwe klanten (sinds 29-09-2026): elke klant in zijn eerste week wordt
  dagelijks nagelopen, gerepareerd waar het kan, en krijgt een mailtje dat Daniel
  verstuurt. De opdracht staat in `docs/routines/onboarding-nieuwe-klanten.md`; de
  geplande taken zeggen alleen "volg dat bestand". Daniels Mac: taak
  `omnivaleur-onboarding-nieuwe-klanten`, 06:30, rondenaam `onboarding-ochtend`.

- Kosten (sinds 04-10-2026): alle maandelijkse kosten van Omnivaleur staan in de Drive-sheet "Omnivaleur kosten" (map Omnivaleur),
  elke 1e van de maand bijgewerkt door taak `omnivaleur-kosten-bijhouden`; opdracht in `docs/routines/kosten-bijhouden.md`.

**Tweede ontwikkelaar, eenmalig bij je eerstvolgende sessie:** staat er op jouw account
nog geen geplande taak `omnivaleur-onboarding-nieuwe-klanten-middag`, maak hem dan aan
(dagelijks 10:00, lokale tijd; staat hij er al op 15:00, zet hem dan op 10:00, Daniel
02-10-2026) met als opdracht: "Je werkt aan Omnivaleur in <jouw
repomap>. Lees docs/routines/onboarding-nieuwe-klanten.md in die repo en volg het
precies. Rondenaam: onboarding-middag." Zet daarna in team-notes dat hij staat. De
tweede ronde om 10:00 vangt de aanmeldingen van die nacht en ochtend; het gedeelde slot
(`scripts/klantfouten.py ronde`) voorkomt dat twee rondes hetzelfde doen.

## Begin elke sessie met kijken wat er veranderd is

Voordat je aan wat dan ook begint — een codetaak, een vraag, een mail, een
controle — zoek je eerst uit wat er is veranderd sinds jouw vorige sessie:

1. `git log --since="30 hours ago" --name-only`, en lees de diff van alles wat je
   onderwerp raakt. Bij een langere pauze: sinds je laatste sessie.
2. De laatste toevoegingen onder aan `docs/team-notes.md`.
3. Sinds 06-09-2026 is de klantenservice-laag eruit (zie `docs/team-notes.md`).
   De mailmachine schrijft geen antwoorden of concepten meer en deelt geen post
   meer in met AI — dat kostte tokens en liet het API-tegoed leeglopen. Wat nog
   draait is de koude reeks mail 1/2/3 uit vaste sjablonen.

   Klanten mailen bugs rechtstreeks; Daniel leest de inbox en brengt ze bij je.
   `scripts/mail_analyse.py` bestaat nog als handmatig hulpmiddel (`bugs` toont
   de oude lijst), maar niets vult die lijst meer automatisch en `lezen` /
   `bericht_over_reparaties` falen bewust omdat de AI eruit is. De LaunchAgent
   `com.omnivaleur.devstarter` staat daarmee stil: geen buglijst, geen
   automatische sessies.

Let op de commits met de tekst "auto: update ...": die komen van de auto-push-hook
en bevatten echt werk achter een nietszeggende titel. De auteursnaam zegt niets
over wie het deed.

**Waarom dit hier staat en niet alleen in lokale memory:** aan dit project werken
drie partijen die elkaar niet zien — Daniel op zijn eigen account, een tweede
ontwikkelaar, en meerdere Claude-sessies naast elkaar. Zonder deze stap bouw je
iets wat er al is, repareer je iets wat net gewijzigd is, of mis je juist de
wijziging die het probleem veroorzaakte. Dat is op 27-08-2026 aantoonbaar
gebeurd: een eerdere sessie voegde `output_config` toe aan de Claude-aanroepen van
de mailagent, de gepinde SDK op de server kende die parameter niet, de fout werd
stil opgevangen en elke lead kreeg wekenlang de standaardmail.

Noem in je eerste antwoord kort wat je hebt gezien, zodat duidelijk is dat je het
huidige beeld hebt.

## De kennisbank: lessen van eerdere sessies

[docs/kennisbank.md](docs/kennisbank.md) bundelt alles wat eerdere sessies hebben
geleerd — valkuilen, werkafspraken, waarom bepaalde keuzes zo zijn. Die lessen
staan normaal in de lokale geheugenmap van één Claude-account en zijn voor een
andere ontwikkelaar onzichtbaar; hier reizen ze mee met de repo.

Sla het niet over voor je iets aanpakt dat je niet kent: het scheelt je de fout
die iemand anders al een keer heeft gemaakt. Leer je zelf iets nieuws, leg het
vast in je geheugen en draai daarna `python3 scripts/export_kennisbank.py`, en
commit het bestand.

## Mails voor Daniel opstellen: stijl lezen, concept bewaren

Brengt Daniel je een klantmail om te beantwoorden (sinds 02-10-2026):

1. Lees eerst [docs/schrijfstijl-daniel.md](docs/schrijfstijl-daniel.md) en schrijf het
   concept in die stijl: aanhef, afsluiting, lengte, toon.
2. Bewaar je concept meteen, zodat de nachtelijke routine het naast de echt verstuurde
   mail kan leggen en daarvan leert:
   `python3 scripts/schrijfstijl_leren.py concept --aan <adres van de klant> --onderwerp "<onderwerp>"`
   met de conceptekst via stdin. Het adres moet dat van de ontvanger zijn, anders
   koppelt de routine niets. De map `data/schrijfstijl/` blijft buiten git.
3. De routine `omnivaleur-schrijfstijl-leren` draait dagelijks en past het stijlbestand
   aan. Pas dat bestand niet zelf aan, tenzij Daniel een stijlregel uitspreekt: dan
   direct erin zetten.

## Het klantenservice-brein bijwerken

[docs/klantenservice-brein.md](docs/klantenservice-brein.md) is de bron die
Daniel in een Gemini Gem plakt om klantmails te beantwoorden. Verandert je
wijziging iets aan prijs, ondersteunde kanalen, proef- of betaaltermijnen, de
demolink, of ontstaat er een nieuwe veelvoorkomende klantvraag of bug, werk dan
in dezelfde beurt de betreffende regel in dat bestand bij en zet de datum
bovenaan opnieuw. Zo blijft het actueel zonder dat het Daniel iets kost.

## Grote wijziging in het dashboard: klanten krijgen een melding

Daniel, 09-10-2026: verander je iets groots in het dashboard (menu, indeling, namen van
schermen of knoppen, een nieuwe werkwijze), dan krijgen bestaande klanten in het dashboard
zelf een "Wat is er nieuw"-venster, "zodat niemand in de war raakt door nieuwe dingen".
In `frontend/app.html`: vervang de inhoud van `#nieuws-venster`, geef `NIEUWS_ID` een nieuwe
waarde en zet `NIEUWS_SINDS` op de datum van de wijziging. Tweetalig, zoals alle klanttekst.
Daarbij altijd een rondleiding op het echte dashboard (Daniel, 09-10-2026: "met animaties,
met het echte dashboard"): vervang de stappen in `#rondleiding-stappen`, één per wijziging,
met `data-view` (welk scherm) en `data-doel` (wat oplicht). Loop hem zelf af in de browser
voor je hem live zet.
Noem in je rapport aan Daniel welke melding klanten krijgen. Kleine reparaties zonder
zichtbare verandering hoeven niet.

## Tekst in het dashboard: ook in het Nederlands

Het dashboard is Engels geschreven en wordt op het scherm vertaald door
`frontend/i18n.js` met `frontend/i18n/nl.json` (sinds 24-09-2026, zie
team-notes). Schrijf of wijzig je tekst die een klant ziet (dashboard,
inlogpagina's, foutmeldingen van extensie of server), draai dan
`python3 scripts/i18n_extract.py`, zet de vertaling in `nl.json` en draai
`python3 scripts/i18n_extract.py --versie`. `tests/test_i18n_compleet.py` faalt
anders. Nooit half vertalen; waarom staat in de kennisbank bij
"vertaallaag-nooit-half".

Dit geldt ALTIJD, ook bij een kleine wijziging en ook als niemand erom vraagt
(Daniel, 24-09-2026: "als je iets wijzigt, altijd in Nederlands en Engels"). Een
wijziging aan klanttekst is pas klaar als beide talen kloppen. De GitHub-proef
`.github/workflows/vertaaltest.yml` draait dezelfde test bij elke pull request en
push naar main en kleurt rood als je het vergeet; merge nooit met die proef rood.
Tekst die bewust in beide talen gelijk is of buiten de vertaling valt (zoals de
tweetalige wijzer bij EN · NL in `frontend/i18n.js`) krijgt `translate="no"`.

## Before touching anything people/business/decision-related

Read [docs/team-notes.md](docs/team-notes.md) first. It's an append-only log
of team, partnership, and business-decision context — who's involved, what
was agreed, why. Unlike `~/.claude` memory (which is per-account and does
not follow Daniel between logins), this file travels with the repo, so it's
the only place that guarantees a session on a *different* account isn't
missing context a session on another account already has.

When you make or learn a decision of that kind, append a dated entry to
`docs/team-notes.md` and push it — the same way a code change gets pushed.
Do not let it live only in memory or only in chat.
