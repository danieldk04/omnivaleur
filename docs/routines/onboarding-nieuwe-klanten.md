# Routine: onboarding nieuwe klanten

De vaste opdracht voor de ochtendronde (Daniels Mac, 06:30) en de middagronde (account
van de tweede ontwikkelaar, 15:00). Beide geplande taken zeggen alleen "volg dit bestand",
zodat er één versie is. Wijzig je de routine, wijzig dan dit bestand en push.

Waarom (Daniel, 29-09-2026): de eerste uren beslissen of een nieuwe klant blijft. Wie
meteen vastloopt sluit het af en komt niet terug. Gemeten 27-09: wie onder de 30
artikelen inlas betaalde nooit, en de afhakers met voorraad vertrokken vaak na een
publicatiefout. Doel: elke nieuwe klant ziet bij de volgende keer opstarten dat alles
loopt, en weet wat hij kan verwachten.

Werk volgens CLAUDE.md (repo en ~). Antwoord Nederlands, gewone taal, vier blokjes,
geen gedachtestreepjes, geen subagents, batch je opdrachten, lees gericht.

## Houding (Daniel, 29-09-2026: "streef altijd naar 1000% zekerheid en pak alles aan")

- Elk signaal eindigt in deze ronde als: gerepareerd met bewijs, of iets wat alleen de
  klant kan (dan staat het in zijn mailtje of in de briefing), of een beslissing die
  echt van Daniel is. Nooit als "wil je dat ik dit bouw?" of een OOIT-punt voor iets wat
  binnen deze routine past.
- Zit er achter het probleem van één klant een oorzaak die ook de volgende klant raakt
  (voorbeeld 29-09: scan gedaan, nooit op Alles importeren geklikt, een week nul
  artikelen), repareer dan die oorzaak in het product, in dezelfde ronde. Alleen
  automatische berichten aan klanten, prijs en proeftermijnen, en geld uitgeven zijn
  Daniels beslissing: vraag die met jouw advies erbij.
- "Kan ik niet zien" is geen eindpunt. Probeer eerst elke route: de flow van de klant
  nadoen in de ingebouwde browser (live dashboard of lokale server, met een testaccount),
  het codepad lezen, de serverlogs. Pas als alles geprobeerd is, schrijf je op wat je
  precies probeerde en wat open blijft.
- Geef Daniel geen actiepunt dat al gedaan of onderweg is. Kijk eerst in de laatste drie
  dagen van team-notes, en meet waar het kan in plaats van het hem te vragen (de Web
  Store-versie staat bovenaan de uitvoer van het script).

Python: gebruik er een die `supabase` kan importeren. Op Daniels Mac is dat
`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` (homebrew-python mist
supabase). Hieronder staat `PY` voor die python.

## Stap 0: één ronde tegelijk

`PY scripts/klantfouten.py ronde begin <rondenaam>` met rondenaam `onboarding-ochtend` of
`onboarding-middag` (staat in de geplande taak). Dit is hetzelfde slot als de
klantfoutenrondes: nooit twee sessies die in dezelfde map of aan dezelfde fouten werken.
- Exit 3: een andere ronde is bezig. Stop meteen, meld in twee zinnen wie en sinds wanneer.
- Exit 0: lees wat de vorige ronde deed. Wat daar gerepareerd heet repareer je niet
  opnieuw, je meet alleen of het weg is.

Aan het eind ALTIJD, ook bij afbreken:
`PY scripts/klantfouten.py ronde klaar <rondenaam> "samenvatting in één zin met commitnummers"`.

## Stap 1: huidig beeld

`git log --since="30 hours ago" --name-only` en de onderkant van `docs/team-notes.md`.
Zoek het laatste kopje "Onboarding nieuwe klanten" en lees wat toen per klant speelde.

## Stap 2: meten

`PY scripts/nieuwe_klanten.py`. Dat geeft per klant in zijn eerste 7 dagen: abonnement,
extensie en versie, wat hij inlas en waaruit, wat hij verkoopt (groepen, rubrieken,
merken, prijzen), advertenties per kanaal, opdrachten, eerste geslaagde plaatsing,
fouten met tekst en job-id, vastgelopen werk, signalen, en wat Daniel al met hem had
(koude mail, postvak, vermeldingen in team-notes, kennisbank en geheugen). Bij `[volgen, ronde N]` staat
wat de vorige ronde deed. `--klant <user_id>` voor één klant, `--json` voor alles.

Nul klanten in het venster: meld dat in twee zinnen en ga naar stap 6. Het script weigert
zelf bij nul accounts, dus nul nieuwe klanten is echt nul.

Extra meten doe je per user_id, nooit over meerdere klanten, nooit `jobs.result` over
een bereik (kennisbank: meten-op-de-productiedatabase). Na een zware meting: /health.

## Stap 3: per klant begrijpen

Voor elke klant, eerst de rode:
0. Wie is hij voor Daniel? Het script geeft per klant `koude mail` (wat de mailmachine
   stuurde, wat hij terugschreef, of Daniel antwoordde), `postvak` (mail heen en weer)
   en `genoemd in` (kopjes in team-notes en kennisbank, geheugenbestanden). Lees elk
   genoemd team-notes-kopje en geheugenbestand echt. Zijn de agenda-tools er, zoek dan
   zijn naam en adres in Daniels agenda voor vandaag en de komende twee dagen. Staat er
   een gesprek, of had Daniel de laatste 48 uur persoonlijk contact, dan krijgt hij geen
   mailtje maar een briefing (stap 5). Zegt het script "niet gelezen", dan weet je niet
   of er contact was: zeg dat erbij, schrijf nooit alsof het de eerste keer is.
1. Hoe ver is hij? Extensie geïnstalleerd, voorraad ingelezen, eerste plaatsing gelukt,
   op welke kanalen. Een klant die na een dag nog nul artikelen of nul geslaagde
   plaatsingen heeft is de belangrijkste van de dag.
2. Wat verkoopt hij? Zoek in `docs/kennisbank.md` gericht op zijn rubrieken, merken en
   kanalen (bijvoorbeeld sieraden, kleding, vloerkleden, gitaren, zakelijk account,
   2dehands, Vinted). Dat is "wat kan hij verwachten": de valkuilen die andere klanten
   met hetzelfde assortiment al tegenkwamen.
3. Vooruitkijken: loop zijn nog niet geplaatste artikelen na op wat bekend is dat
   weigert (maat Overige, geen kleur voor Vinted, betaalde rubrieken, prijs die als
   duizendtal verkeerd gelezen wordt, geen foto, geen prijs). Gebruik waar het kan de
   echte code die de kanaalvelden bepaalt, niet je eigen inschatting.
4. Elke fout: onderscheid (a) onze code of een kanaal dat zijn pagina veranderde,
   (b) iets wat alleen de klant kan (computer uit, uitgelogd, maat kiezen, extensie
   installeren), (c) de Web Store die achterloopt. Bewijs het mechanisme voor je iets
   een oorzaak noemt.

## Stap 4: repareren

Daniel koos op 29-09-2026: code én klantdata mag rechtgezet worden.

Code (a): bewijs de oorzaak, repareer in de echte code, draai de bestaande tests, doe de
voor-en-na-proef (oude code laten falen), commit en push naar main (Railway deployt).
Extensiewijziging: manifest ophogen en `build-extension.sh` volgens de kennisbank; de
upload naar de Web Store is een actiepunt voor Daniel. Klanttekst gewijzigd: ook
`nl.json` (zie CLAUDE.md, vertaallaag). Twijfel je of iets de oorzaak is: zoek door
tot je het weet (zie Houding). Lukt dat niet, dan niet repareren en opschrijven wat je probeerde.

Klantdata: toegestaan, onder deze voorwaarden.
- Alleen na een bewezen oorzaak, en met een meting ervoor en erna die je in team-notes zet.
- Opnieuw klaarzetten van mislukt of vastgelopen werk mag pas als de oorzaak weg is.
  Let op herkansen zonder dubbele opdracht (kennisbank: herkansen-mag-geen-dubbele-opdracht)
  en op een verse plek in de rij (terugzetten-is-een-verse-plek-in-de-rij).
- Een veld vul je alleen met een waarde die aantoonbaar klopt, uit een bron: de
  advertentie op het kanaal of de importkandidaat. Nooit een standaard verzinnen
  (kennisbank: verzonnen-standaard-is-erger-dan-leeg). Kan alleen de klant het weten,
  dan hoort het in het mailtje.
- Nooit verwijderen: geen artikelen, geen advertenties, geen wachtrij leeghalen, geen
  opdrachten annuleren.

Meld elke foutsoort die je behandelde terug met
`PY scripts/klantfouten.py oordeel <soort> gerepareerd|klant|onbekend "zin"` (de soort
staat tussen haken achter de fout), zodat de klantfoutenronde hetzelfde niet opnieuw doet.

## Stap 5: mailtje of briefing per klant klaarzetten

Daniel verstuurt zelf; jij verstuurt niets. Wat hij krijgt hangt af van stap 3.0:
- Gesprek gepland of de laatste 48 uur persoonlijk contact: geen mailtje. Een briefing
  van hooguit vijf regels: wat hij verkoopt, waar hij staat, wat we rechtzetten, het ene
  ding om hem te zeggen, en een open vraag van hem als die er is.
- Eerder contact (koude mail, antwoord, mail heen en weer): sluit daarop aan, geen
  nieuwe introductie. Stond er een vraag van hem open, beantwoord die als Daniel dat nog
  niet deed.
- Nooit contact: begin met de introductie uit het voorbeeld hieronder.
- Geen mailtje voor een klant bij wie niets veranderde en de vorige ronde er al een had.
- De server stuurt zelf één herinnering aan wie liet scannen en na 24 uur nog niets
  importeerde (sinds 29-09-2026). Staat bij de klant "automatische importherinnering"
  met een datum, herhaal die boodschap dan niet.

Stijl: zo schrijft Daniel het zelf (29-09-2026, verstuurd aan een nieuwe klant, "zo'n
stijl wil ik dus dat je aanhoudt"). Dit is een voorbeeld van de toon, geen sjabloon
("niet precies dit format, maar wel dezelfde stijl"): schrijf per klant een eigen mail
die past bij wat hij verkoopt en waar hij staat, en kopieer de zinnen niet.

```text
Hoi Anneloes,

Ik ben Daniel, de oprichter van Omnivaleur. Ik kijk zelf naar elk nieuw account om te zorgen dat er geen onduidelijkheden of problemen zijn; super leuk dat je een account hebt aangemaakt!

Goed nieuws: je voorraad is binnen en 38 artikelen staan netjes op Vinted.

Op Marktplaats is het nog niet gelukt, omdat je in Chrome niet bent ingelogd op marktplaats.nl. Als je daar wilt publiceren, log je eenmaal in en kies je daarna in je dashboard de artikelen en zet ze op Marktplaats. Dan ben je met dezelfde voorraad op twee plekken zichtbaar.

Loop je ergens tegenaan, stuur me gerust een berichtje of, als je dat liever hebt, kun je ook via het dashboard een call inplannen.

Ik kijk er naar uit om je te helpen om meer tijd te besparen :)!
Groetjes,
Daniel
```

Wat de stijl is (Daniel, 29-09-2026: "hou altijd de positieve insteek, met voordelen
voor de klant, tips etc"):
- Altijd positief. Begin met wat al goed gaat, met een concreet getal uit de meting.
  Wat nog niet lukt breng je als kans: wat hij doet en wat het hem oplevert (meer
  zichtbaar, meer verkopen, tijd die hij terugwint), niet als probleem of fout.
- Voordelen voor hem, niet functies van ons. Niet "je kunt ook op 2dehands plaatsen"
  maar "met dezelfde voorraad ben je dan ook in België zichtbaar, zonder extra werk".
- Een tip die bij zijn voorraad past, uit de kennisbank of uit zijn eigen meting (wat
  andere verkopers van kleding, sieraden of meubels hielp), met het voordeel erbij.
  Liever één sterke tip dan drie halve. Nooit een tip die je niet kunt onderbouwen.
- Warm en persoonlijk: kort voorstellen als oprichter die zelf naar elk nieuw account
  kijkt (alleen bij eerste contact, in eigen woorden), enthousiasme mag, een
  uitroepteken of smiley ook. Geen boetekleed, geen uitleg van hoe wij iets repareerden.
- Sluit af met het hulpaanbod: een berichtje terug, of een call inplannen via het
  dashboard (de Calendly-knop in het dashboard bestaat).
- Aanhef "Hoi <voornaam>,", slot "Groetjes," met op de regel eronder "Daniel".
- Rond de 120 woorden (kennisbank: klantmail-kort-en-menselijk). Platte tekst, geen
  opmaaktekens, geen streepjes als leesteken, elke alinea één doorlopende regel.
- Nederlands, tenzij hij duidelijk Engelstalig is; dan dezelfde opbouw in het Engels.
- Schrijf nooit iets wat je niet gemeten hebt ("staan netjes op Vinted" alleen als het script
  ze daar als actief telt; "komt vanzelf binnen" alleen als de Web Store die versie al
  levert).

## Stap 6: vastleggen

- Per bekeken klant: `PY scripts/nieuwe_klanten.py gezien <user_id> "één zin: stand, wat
  gedaan, mailtje ja/nee"`. Dat ziet de volgende ronde als "vorige ronde".
- Onderaan `docs/team-notes.md`: `## DD-MM-JJJJ: Onboarding nieuwe klanten (ochtend|middag)`
  met per klant één of twee regels, wat gerepareerd is (commit), wat open blijft.
  Commit en push.
- Iets nieuws geleerd: geheugenbestand plus `python3 scripts/export_kennisbank.py`, commit.

## Stap 7: rapport aan Daniel

De vier blokjes. In "Wat er aan de hand was" per klant één regel: e-mailadres, wat hij
verkoopt, stand (loopt / let op / vast), en of Daniel al contact had. Zet de mailtjes
en briefings kant-en-klaar onder de actiepunten, met per mailtje het adres, zodat hij
ze kan kopiëren. Rustige dag zonder
nieuwe klanten of problemen: twee zinnen.

Meld eerlijk wat je niet kon zien: fouten die alleen in de browser van de klant staan en
nooit naar de server gaan, en alles wat de Web Store nog niet heeft uitgeleverd.
