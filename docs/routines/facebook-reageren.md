# Facebook reageren in groepen, autonoom (Engels en Nederlands)

Daniel, 08-11-2026: precies hetzelfde als `docs/routines/social-reageren.md`, maar dan in zijn Facebookgroepen. Dit
heft de oude afspraak "niets plaatst namens Daniel" op voor reacties in groepen. Lees eerst `social-reageren.md`: de
regels over stijl, wat je weet, wat je overslaat en het noemen van Omnivaleur gelden hier gewoon. Alleen REAGEREN op
andere mensen, nooit een eigen post of een eigen bericht in een groep plaatsen. Building in public doet Daniel zelf.

## Werkwijze
In Daniels ingelogde Chrome (Claude in Chrome, nieuw tabblad, na afloop sluiten). Facebook vraagt niet naar AI, maar
reageer alleen waar Daniel dit zelf verantwoordt: hij controleert achteraf.

## Waar (Daniel is lid van 44 groepen; dit is de selectie)
Reseller en Vinted, Engels en internationaal: EU Resellers: Vinted, eBay & Crosslisting Community; Resellers Community;
Reseller Community: Tips & BOLOs; Ebay Resellers & Thrifters Group; UK and EU Buy and Sell; Resellers Connected;
VINTED INTERNATIONAL.
Reseller en Vinted, Nederlands en Belgisch: Vinted NL & BE; Vinted NL/BE; Vinted PRO; Vinted Pro Verkopers (NL);
Vinted Tips&Tricks Promoties BE/NL; De Resale Club | Vinted & tweedehands verkopen.
Bouwers en ondernemers (reageren op vragen over eerste klanten, organisch groeien, een product bouwen):
VibeCoders BuildInPublic Group; #BuildInPublic | Saas Founders | Solo Developers (Engels); Beginnende Ondernemers;
Startende Ondernemers; Ambitieuze ondernemers (Nederlands).
Overslaan: groepen met "promotie", "promoten", "reclame" of "geen regels" in de naam: daar staan alleen advertenties.

## Aantallen (harde plafonds per dag)
- Maximaal 4 reacties per dag in totaal (Facebook is strenger dan X), 2 per ronde, minstens 10 minuten tussen twee reacties.
- Maximaal 1 reactie per groep per dag, nooit twee keer onder dezelfde persoon op een dag.
- Niet liken, geen vriendschapsverzoeken, geen lidmaatschapsaanvragen, geen berichten (pb). Wil iemand een pb, dan
  schrijft Daniel dat zelf.

## Wat je opzoekt
Per groep het tabblad "Nieuwste activiteit" of de groepsfeed, posts van de laatste 24 uur met een echte vraag of
ervaring: blokkades en accountproblemen op Vinted, Marktplaats of eBay, dubbel typen, voorraad synchroon houden,
crosslisten, verzendproblemen, prijs bepalen, eerste klanten, organisch groeien. Taal van de post: Nederlandse post
Nederlandse reactie, Engelse post Engelse reactie, nooit mengen.

## Overslaan
- Posts met al meer dan 15 reacties, advertenties, "volg mij", ruzie, politiek, vragen over iemands privésituatie.
- Alles waar Daniel geen eigen ervaring bij heeft, juridische of belastingvragen (hooguit "check de bron of je boekhouder").
- Groepen waarvan de regels (bij het eerste bezoek: "Over" of "Groepsregels") AI-reacties, bots of reageren door
  tools verbieden: sla die groep over, noteer het in `data/social/groepen.json` en kom er niet terug.
- Elke groep waar Facebook een melding of controle laat zien.

## Stijl
`docs/facebook-reactiebot.md` is de bron voor toon, lengte en wat Daniel nooit doet. Voorbeelden van zijn echte reacties
staan in `docs/facebook-actueel.md`. Omnivaleur noem je alleen volgens de regels daarin (één zin, eigen belang erbij,
pb in plaats van link), hooguit bij 1 op de 5 reacties.

## Uitvoering
1. Lees `data/social/gedaan.jsonl` en tel wat er vandaag al staat (alle platforms apart). Platform "facebook". Nooit
   twee keer op dezelfde post. Controleer `data/social/groepen.json` op overgeslagen groepen.
2. Kies, schrijf, plaats. Controleer na elke reactie dat hij zichtbaar staat (herlaad de post), dan loggen: datum,
   platform, groep, url van de post, onze tekst.
3. Stoppen en niets herhalen bij: niet ingelogd, een controle of checkpoint, "je kunt even niet reageren", een melding
   van een groepsbeheerder of een verwijderde reactie. Log het, meld het Daniel en blijf die dag van Facebook af.
4. Schrijf `data/social/laatste-rapport.txt` bij (kop "Facebook"): geplaatst, overgeslagen, meldingen.
5. Wekelijks, maandag: bekijk wat de eerdere reacties kregen (likes, antwoorden, verwijderd?) en pas dit bestand aan.
6. De leren-routine van de Facebook-reactiebot (`docs/routines/facebook-reactiebot.md`) leest Daniels eigen
   activiteitenlogboek. Reacties van deze routine staan daar ook in. Sla ze over bij het leren: haal de teksten uit
   `data/social/gedaan.jsonl` (platform facebook) uit `data/facebook-leren/reacties.jsonl` of neem ze niet op.

## Risico dat Daniel kent
Facebook kan een account tijdelijk beperken of blokkeren voor automatisch gedrag, en het gaat om Daniels eigen profiel
met zijn echte naam. Daarom de lage aantallen, geen links, één per groep en stoppen bij elke melding. Een groepsbeheerder
kan hem verwijderen als reacties als reclame lezen: Omnivaleur dus zelden en alleen als het echt past.
