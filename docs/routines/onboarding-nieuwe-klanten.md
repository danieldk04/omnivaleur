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
fouten met tekst en job-id, vastgelopen werk, en signalen. Bij `[volgen, ronde N]` staat
wat de vorige ronde deed. `--klant <user_id>` voor één klant, `--json` voor alles.

Nul klanten in het venster: meld dat in twee zinnen en ga naar stap 6. Het script weigert
zelf bij nul accounts, dus nul nieuwe klanten is echt nul.

Extra meten doe je per user_id, nooit over meerdere klanten, nooit `jobs.result` over
een bereik (kennisbank: meten-op-de-productiedatabase). Na een zware meting: /health.

## Stap 3: per klant begrijpen

Voor elke klant, eerst de rode:
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
`nl.json` (zie CLAUDE.md, vertaallaag). Twijfel je of iets de oorzaak is: niet
repareren, open punt.

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

## Stap 5: mailtje per klant klaarzetten

Daniel verstuurt zelf; jij verstuurt niets. Een mailtje voor:
- elke klant die voor het eerst in de routine zit (welkom binnen de eerste dag),
- een klant bij wie iets gerepareerd is, of die iets moet doen,
- niet voor een klant bij wie niets veranderde en de vorige ronde al een mailtje had.

Vorm (kennisbank: klantmail-kort-en-menselijk): 120 tot 200 woorden, platte tekst zonder
opmaaktekens en zonder streepjes als leesteken, goed nieuws vooraan, eerst erkennen wat
misging. Inhoud: wat we zien dat hij verkoopt en wat al werkt (met zijn eigen getallen),
wat we voor hem rechtzetten, het ene ding dat hij zelf moet doen (als dat er is), en wat
hij de komende dagen kan verwachten voor zijn soort artikelen. Nederlands, tenzij zijn
voorraad of adres duidelijk Engelstalig is. Ondertekend met Daniel. Schrijf nooit iets
wat je niet gemeten hebt ("alles werkt" alleen als er een geslaagde plaatsing is).

## Stap 6: vastleggen

- Per bekeken klant: `PY scripts/nieuwe_klanten.py gezien <user_id> "één zin: stand, wat
  gedaan, mailtje ja/nee"`. Dat ziet de volgende ronde als "vorige ronde".
- Onderaan `docs/team-notes.md`: `## DD-MM-JJJJ: Onboarding nieuwe klanten (ochtend|middag)`
  met per klant één of twee regels, wat gerepareerd is (commit), wat open blijft.
  Commit en push.
- Iets nieuws geleerd: geheugenbestand plus `python3 scripts/export_kennisbank.py`, commit.

## Stap 7: rapport aan Daniel

De vier blokjes. In "Wat er aan de hand was" per klant één regel: e-mailadres, wat hij
verkoopt, stand (loopt / let op / vast). Zet de mailtjes kant-en-klaar onder de
actiepunten, met per mailtje het adres, zodat hij ze kan kopiëren. Rustige dag zonder
nieuwe klanten of problemen: twee zinnen.

Meld eerlijk wat je niet kon zien: fouten die alleen in de browser van de klant staan en
nooit naar de server gaan, en alles wat de Web Store nog niet heeft uitgeleverd.
