# Build in public: ideeënlijst (Daniel, 17-11-2026)

Daniel houdt elke dag een build-in-public bij op Indie Hackers (17-11-2026 staat hij op dag 163).
Dit bestand bewaart alles wat uit de reacties komt, zodat hij er later een update over kan schrijven.
Het reist mee met de repo, dus beide ontwikkelaars en beide accounts vullen het aan. Nieuwste bovenaan.

## Wat hier in hoort
1. **Beloften en aankondigingen van Daniel** waar mensen op wachten. Zegt iemand "ik ben benieuwd wat het
   effect van X wordt" of staat er in zijn post "ik meld me terug als ik cijfers heb", dan komt dat hier als
   open belofte, met de datum en de postlink. Zodra de meting er is: cijfer erbij, status "klaar voor update".
2. **Vragen en ideeën van reageerders** die we kunnen bouwen, meten of uitleggen.
3. **Eigen meetpunten** die een goede update opleveren (voor en na, in cijfers die we zelf maten).

Niets verzinnen: een cijfer staat hier alleen als het gemeten is, met datum en bron. Beweert een reageerder iets
(bijvoorbeeld over een platform), zet er dan "claim van reageerder, niet gecontroleerd" bij.

## Wie vult dit aan
- Elke sessie die Indie Hackers leest of beantwoordt (Daniel plakt reacties, of de routine in
  `docs/routines/social-reageren.md` leest ze): voeg regels toe voor je afrondt.
- De kennisoverdracht (`docs/routines/kennisoverdracht.md`, stap 5b) kijkt dit bestand elke keer na:
  is een belofte inmiddels meetbaar, zet dat bovenaan overdracht.md bij "Wat nu open staat".
- Gebruik dit bestand ook als Daniel vraagt "waar kan ik over schrijven", nog voor je zelf zoekt.

## Hoe de routine hiermee werkt (Daniel, 17-11-2026)
- **Reacties beantwoorden.** De reageerronde (`data/social/ronde-prompt.txt`, blok BUILD IN PUBLIC) leest elke ronde
  de reacties onder Daniels laatste posts op X, Indie Hackers en Bluesky en beantwoordt wat nog geen antwoord heeft,
  in zijn stijl. Wat al afgehandeld is staat in `data/social/bip-gezien.json` (beheerd door `scripts/bip_reacties.py`).
- **Vastleggen.** Elke vraag, elk idee en elke toezegging uit zo'n reactie komt hier, met de postlink.
- **Terugkomdatum.** Belooft Daniel of de routine iets ("ik kijk over 3 dagen") dan komt er een rij in de tabel
  hieronder met de datum in de kolom "Terugkom op". `python3 scripts/bip_reacties.py due` toont wat aan de beurt is.
- **Ochtendrapport.** De eerste keer dat de ronde-cron per dag in het gesprek afgaat (vanaf 08:00) staat bovenaan
  een rapport: nieuwe reacties en vragen, wat beantwoord is, beloften die vandaag aan de beurt zijn (met de meting),
  en een paar ideeën voor zijn post van vandaag uit deze lijst.
- Na het melden zet je bij de belofte de status op "Gemeld op <datum>" en zo nodig een nieuwe terugkomdatum.

## Open beloften aan de lezers

| Datum | Post | Wat is beloofd | Meting die nodig is | Terugkom op | Status |
|---|---|---|---|---|---|
| 26-11-2026 | Dag 171, testen op het hoofdpad | Aan Hamilton_Neuta: een uitkomstalarm bouwen (plaatspogingen per uur boven nul maar geen succes, of succespercentage ver onder hetzelfde uur vorige week) naast de foutmeldingen | Nagaan of plaatspogingen en successen per uur al in de data staan | 03-12-2026 | Open |
| 25-11-2026 | Dag 170, foutafhandeling | Aan Censtar en Irshad Khan: per account kijken naar extensie-uit (gesloten browser of uitgezet) en een waarschuwing na 1 tot 2 dagen overwegen | Per account nagaan wanneer de extensie voor het laatst incheckte | 28-11-2026 | Open |
| 24-11-2026 | Dag 170, foutafhandeling | Aan ipweb3: uitzoeken of uitval bij nieuwe klanten vooral bij de installatie zit of bij verkopers die nooit beginnen, per aanmelding, en daarop terugkomen | Per aanmelding nagaan waar het stopt (python3 scripts/onboarding_tempo.py) | 27-11-2026 | Open |
| 23-11-2026 | Facebook Vinted BE/NL, Daniels post 21-11 | Aan Ani Ta: uitzoeken wat Vinted precies toestaat aan tools (voorwaarden verbieden externe softwaretools zoals bots 'tenzij Vinted het toestaat') en daarop terugkomen | Vinted-voorwaarden en help-pagina's over tools lezen; plaatsklaar-stand (nog niet live) noemen zodra die voor klanten aan staat | 30-11-2026 | Open |
| 22-11-2026 | Dag 168, prijswijziging | Aan Nino: kijken naar de nieuwsbrief The Weekly Reseller (Vinted Survival Guide) en proberen op de ResaleOS-lijst 'Best Cross-Listing Software 2026' te komen | Nieuwsbrief en lijst nalopen, contact zoeken | 29-11-2026 | Open |
| 22-11-2026 | Dag 168, prijswijziging | Aan listdraft: bij de prijswijziging per 1 januari seizoensuitval en prijsgedreven opzeggingen apart houden | Opzeggingen rond 1 januari splitsen | 15-01-2027 | Open |
| 21-11-2026 | Facebook Startende Ondernemers, Etsy-post | Aan Gert Pellin: uitzoeken of Etsy API-toegang via de klant zelf kan lopen (wij bouwen met mocks, klanten vragen zelf toegang aan) | Etsy-documentatie en voorwaarden lezen, kijken of onze afwijzing daarmee samenhangt | 28-11-2026 | Open |
| 20-11-2026 | Dag 166, antwoord aan Dmytro Katyukha | Toegezegd: alle 88 reacties op de koude mail doorlopen en tellen hoeveel er een advertentie meestuurden met de vraag die op een ander kanaal te zetten, en erop terugkomen | Mail-antwoorden (88) doorlezen en tellen | 23-11-2026 | Open |
| 16-11-2026 | Dag 163, "quick win voor nieuwe gebruikers" | Terugkomen met wat het doet in de komende weken (inventaris start vanzelf, 1 klik plaatsen van het beste artikel, helpknop na 10 minuten, gemailde link naar de computer) | Mediane tijd van aanmelding tot eerste live advertentie, voor en na 16-11 (zie `docs/routines/onboarding-nieuwe-klanten.md`, onboarding-tempo). Daarnaast: hoe vaak de helpknop wordt aangeklikt | 30-11-2026 | Open. Vanaf ~30-11 meetbaar |
| 15-11-2026 | Dag 162, Search Console van /nl | Daniel liet de /nl-titel voorlopig staan en zei dat hij terugkomt zodra echte taakzoekopdrachten (zoals 'tegelijk plaatsen op Marktplaats en Vinted') in Search Console verschijnen (Five Hands Studio, 16-11: 'Worth a re-check once you start seeing task-style queries') | Search Console /nl: aantal klikken van zoekopdrachten die niet 'omnivaleur' bevatten, voor en na | 24-11-2026 | Open (voorlopige datum, eerste herkijk) |
| 17-11-2026 | Dag 164, Etsy afgewezen | Aan Gabriel Lora toegezegd: uitzoeken wat de mensen die om Etsy vroegen verkopen en of dat vintage (20+ jaar), handmade of craft is, en daarop terugkomen | Per Etsy-vrager nagaan wat de voorraad is (klantmails, sheet Omnivaleur te bouwen) | 20-11-2026 | Open |
| 19-11-2026 | Dag 165, referralprogramma | Aan hiredov toegezegd: tellen hoeveel gebruikers via de Facebook-groepen of informele uitnodigingen binnenkwamen en daarop terugkomen | Aanmeldbron per klant (mail, groep, doorverwijzing) uit de klantdata | 23-11-2026 | Open |
| 19-11-2026 | Dag 162, bezoekers per land | Aan ruslann3s toegezegd: aanmeldingen per land uitsplitsen (NL, BE, buiten de EU) en daarop terugkomen | Aanmeldingen per land uit de klantdata (land van de verkoper) | 23-11-2026 | Open |
| 25-11-2026 | Dag 170, antwoord aan GautamTalksDev | Toegezegd: per account nagaan hoeveel verkopers een uitgeschakelde extensie zelf na een dag zouden opmerken, en daarop terugkomen | extension_heartbeat per account | 28-11-2026 | Open |
| 27-11-2026 | Dag 172, Etsy werkt | Aan partstown: de vertraging meten tussen een verkoop op het ene kanaal en het verdwijnen van het artikel op Etsy, zodra de eerste Etsy-verkoop terugkomt | Meting zodra Mienekes eerste Etsy-verkoop binnenkomt (verkoop-tijd tegen verwijder-tijd) | 04-12-2026 | Open |
| 27-11-2026 | Dag 172, Etsy werkt | Aan founderdive: per aanmelding nagaan hoeveel artikelen een verkoper heeft en of het bijverdienste of hoofdinkomen is, en terugkomen | Per aanmelding aantal artikelen uit de klantdata; bijverdienste of hoofdinkomen bij klantmails | 01-12-2026 | Open |

## Ideeën uit reacties

| Datum | Van | Idee of vraag | Wat we ermee kunnen | Status |
|---|---|---|---|---|
| 26-11-2026 | Hamilton_Neuta (IH, dag 171) | Alarm op uitkomsten in plaats van fouten: pogingen per uur boven nul met nul successen, of succespercentage ver onder hetzelfde uur vorige week | Bouwen naast foutalarm | Beantwoord 26-11 (toegezegd, zie Open beloften) |
| 25-11-2026 | Censtar (IH, dag 170) | Vraag: krijgt de verkoper een waarschuwing als de extensie een dag of twee uit staat, vóór de taken geannuleerd worden? | Overwegen: waarschuwing na 1 tot 2 dagen uit | Beantwoord 25-11 (nog niet, alleen Daniel ziet het; per account kijken) |
| 24-11-2026 | ipab (IH, dag 170) | Vraag: welke marktplaats was het moeilijkst te ondersteunen, de API of de plaatsingsregels? | Content-onderwerp | Beantwoord 24-11 (regels, Etsy-toegang als uitzondering) |
| 24-11-2026 | Irshad Khan (IH, dag 170) | 'Extensie uit' heeft drie oorzaken (gebruiker zet uit, browser dicht, MV3 service worker wordt niet wakker); een heartbeat naar de backend scheidt 'geen check-in' van 'check-in maar taak mislukt'; 60 verlengverzoeken van één account samenvouwen tot één statusregel | Overwegen voor de storingsmelding van de extensie. | Beantwoord 25-11 (nog niet gesplitst, gaat per account kijken) |
| 24-11-2026 | mochawang, duranlautaro (IH, dag 170) | Foutenlijst als dagelijkse wachtrij van beslissingen; 60 verlengverzoeken van één account als één verbindtaak; elke oorzaak een benoemde foutcode met een uitleg in gewone taal voor de verkoper | Overwegen voor de storingsmelding | Idee |
| 24-11-2026 | Krishna Anubhav (IH, dag 170) | Vraag: houd je fouten per klant bij of alleen het totaal? | Content-onderwerp | Beantwoord 24-11 (eerst totaal, dan per account) |
| 24-11-2026 | mochawang (IH, dag 170) | Korte dagelijkse wachtrij met beslissingen: 60 verlengverzoeken van één account als één 'opnieuw koppelen'-taak, prioriteit voor taken waar de live advertentie kan ontbreken, bewuste overslag labelen met wat nog live staat | Overwegen. Niet beantwoord (plafond) | Idee |
| 23-11-2026 | Ani Ta (Facebook) | Waarschuwing: software om tegelijk te plaatsen zou verboden zijn op Vinted en je account kosten | Zelfde zorg als de Vinted-voorwaarden (externe tools). Argument voor de plaatsklaar-stand; content-onderwerp zodra dat helder is | Beantwoord, terugkomen 30-11 |
| 22-11-2026 | listdraft (IH) | Bij prijsverhoging: directe mail met wat verandert in euro, optie om met jaarabonnement de huidige prijs vast te zetten vóór 1 januari | Overwegen voor de aankondiging aan bestaande klanten | Nieuw |
| 22-11-2026 | Nino (IH) | Geef elk plan een paar AI-aanbiedingen per maand en kijk wie de limiet haalt | Test voor AI-functies op alle plannen | Nieuw |
| 21-11-2026 | Gert Pellin (Facebook) | Etsy weigerde omdat wij een third party app zijn, geen eindklant. Bouw mocks op basis van hun documentatie, laat klanten zelf toegang aanvragen met hun eigen gebruiksreden | Mogelijke route rond de Etsy-afwijzing, eerst bij Etsy navragen of dat past bij ons beroep | Nieuw |
| 16-11-2026 | Polymetis | Voortgang die al is gestart: checklist opent met "Account created" afgevinkt, zodat de verkoper op stap 3 van 5 landt (autowas-onderzoek: 19% tegen 34% afgerond) | Staat al live: poort met "Account created" afgevinkt, stap 2 van 5 (commit 2d15495d). Update schrijven met het effect op de tijd tot eerste advertentie | Gebouwd, effect nog te meten |
| 16-11-2026 | Polymetis | eBay zou voor particuliere verkopers in Frankrijk en Italië de kosten naar de koper verschuiven, dus meer losse verkopers | Frankrijk en Italië als onboarding-push overwegen. Claim van reageerder, niet gecontroleerd. Daniel zit vooral in NL en BE | Idee, eerst controleren |
| 16-11-2026 | LiranBlumenberg | Eerste taak duidelijker maken: kies één bestaande advertentie, bekijk hoe hij op de tweede markt eruit ziet, publiceer. Verkoper mag het voorgestelde artikel wisselen, ziet ontbrekende velden en kan voortgang bewaren | Test voorstellen voor de "Place now"-stap. Niet gebouwd | Idee |
| 16-11-2026 | LiranBlumenberg | De gemailde link van telefoon naar computer moet terugkomen op dezelfde stap, niet op het begin | Nameten of dat zo werkt, en zo nee repareren. Daniel heeft dit half toegezegd | Te controleren |
| 16-11-2026 | LiranBlumenberg | Kies één land en één marktplaatsenpaar, zoek handmatig verkopers die vragen hoe ze niet dubbel hoeven te plaatsen; verkeerscijfers van dag 162 bewijzen niet welke bezoekers bots zijn | Content-onderwerp: wat bots en echte bezoekers uit het verkeer scheidt. Volg apart: gesprek, aanmelding, eerste crosslist | Idee |
| 16-11-2026 | dgknght | Benieuwd hoe de helpknop uitpakt | Update schrijven met hoe vaak hij wordt geklikt en of die klikkers blijven | Wacht op meting |
| 16-11-2026 | (afgekapt, auteur onbekend) | Meet de mediane tijd van aanmelding tot eerste live advertentie, voor en na de wijziging | Zelfde meting als de open belofte hierboven | Wacht op volledige tekst |
| 17-11-2026 | hiredov | Etsy-risico afdekken: bewaar de artikeldata (SKU, foto's, varianten, voorraad, tekst) in een exporteerbaar, marktplaatsneutraal formaat, zodat een nieuwe koppeling geen catalogusmigratie wordt | Beantwoord op Dag 164: data staat op één plek, kanalen zijn een vertaling erbovenop. Content-onderwerp mogelijk | Beantwoord |
| 17-11-2026 | Gabriel Lora | Etsy staat alleen vintage (20+ jaar), handmade en craft supplies toe: vraag de Etsy-vragers hoeveel van hun voorraad zou kwalificeren; is het weinig, dan hindert wachten minder; is het veel, dan een sterk punt voor het beroep | Nagaan wat de Etsy-vragers verkopen; zie belofte Dag 164 | Beantwoord op Dag 164, terugkomen 20-11 |
| 17-11-2026 | listdraft | Handmatige tussenoplossing voor Etsy-vragers: Etsy-klare versie per artikel (titel max 140 tekens, 13 tags van max 20 tekens, vintage/handmade-vlag) om zelf te plakken | Overwegen, alleen als Etsy-vragers echt voorraad hebben die mag; niet beantwoord | Open |
| 17-11-2026 | Bullpicks, Gregory Scott Henson | Houd bij wie echt geblokkeerd is door Etsy (aanmelding of opzegging) tegenover alleen willen; vraag wat mensen het vaakst noemen bij Etsy | Telling uit klantmails/te-bouwen-sheet | Niet beantwoord, zelfde meting als Gabriel |
| 17-11-2026 | AndersonTech | Vraag: draait de synchronisatie al hands-off of moet je mislukte taken nog babysitten? | Eerlijk cijfer nodig (aantal handmatig herstelde taken), niet verzonnen | Niet beantwoord, vraag staat open |
| 18-11-2026 | zeuxoai (IH, dag 164) | Zet een status op de Etsy-rij zelf (bijv. 'appeal filed 17 Nov, no date') zodat de wekelijkse vraag een antwoord heeft zonder belofte; schrijf de appeal als smalle aanvraag (listing maken, voorraad dalen na verkoop elders) | Statusregel Etsy in dashboard/te-bouwen overwegen. Claim van reageerder, niet gecontroleerd | Idee, niet opgepakt |
| 20-11-2026 | listdraft (Dag 164) | Brug zolang Etsy wacht: per artikel een Etsy-klare versie genereren (titel max 140 tekens, 13 tags van max 20 tekens, vintage-vlag) die de verkoper zelf plakt; laat ook zien hoeveel mensen dat gebruiken | Bruikbaar als tussenstap voor Etsy-vragers. Niet gebouwd | Idee |
| 20-11-2026 | KeepBatch (Dag 164) | Overselling van een uniek stuk bij verkoop op de ene markt voordat de andere bijwerkt: korte voorraadslot of snelle verwijderwachtrij | Bestaat al deels (verwijdering voorop in de wachtrij sinds 06-11). Niet beantwoord | Gebouwd, niet beantwoord |
| 20-11-2026 | Gregory Scott Henson (Dag 164) | Onderscheid wie niet kan starten zonder Etsy van wie al betaalt en een extra kanaal wil; tel geblokkeerde aanmeldingen en verloren verlengingen naast het aantal verzoeken | Meting voorstellen voor het Etsy-besluit. Niet beantwoord | Idee |
| 20-11-2026 | Mistermember (Dag 164) | Zelfde Etsy-afwijzing zonder reden; hij leest dat beroepen een maand duren en meestal worden afgewezen, dus de roadmap niet erop laten wachten | Zelfde les: Etsy niet in de planning zetten. Niet beantwoord | Info |

| 19-11-2026 | hiredov | Referralbeloning laten afhangen van de eerste mijlpaal van de vriend (account koppelen en eerste 10 artikelen plaatsen) in plaats van alleen betalen; voor de vriend liever extra proefperiode dan geld | Past bij het referralprogramma uit Dag 165: mijlpaalregel overwegen, filtert nepaanmeldingen | Nog te overwegen |

| 21-11-2026 | Gabriel Lora (Dag 168) | Geef elk plan een paar AI-listings per maand en kijk wie de limiet raakt, in plaats van AI alleen op het hoogste plan; vraag: zijn Ultra-gebruikers vooral high-volume resellers? | Meting later: wie raakt de AI-limiet. Nog niet gemeten wie Ultra neemt | Beantwoord 21-11: weet het nog niet, geen cijfer genoemd |

| 21-11-2026 | Jos Vervoorn (Facebook, Startende Ondernemers) | Is een headless browser geen tijdelijke oplossing voor Etsy? (Wesley Stoep stelt ook een eigen browser voor die Claude toegang geeft tot platforms zonder API) | Niets omzeilen, eerst terugvragen bij Etsy (team-notes 17-11) | Beantwoord 21-11 |
| 27-11-2026 | Alameddin (IH, dag 172) | Toon eerst een voorbeeld van de exacte Etsy-advertentie (titel, tags, categorie, prijs) met één Publiceren-knop voor de eerste 10 tot 20 artikelen, daarna pas automatisch; plus een gewoon activiteitenlogboek met pauzeknop; en Mienekes eerste verkoop als zin voor de Ultra-pagina | Voorbeeldstap voor een nieuw kanaal overwegen; zou de haakjes-titelfout hebben gevangen | Idee, niet opgepakt; Daniel gaf aan het te noteren |
| 27-11-2026 | BestAppify (IH, dag 172) | Vraag: zit de meeste tijd in de regels en categorieën per marktplaats, of ergens anders | Niet beantwoord (plafond bereikt); eerder antwoord aan ipab op dag 170 noemt de plaatsingsregels | Open |
| 27-11-2026 | Muhammad Ammad Umer (Facebook #BuildInPublic, dag 172) | Voor vertrouwen in een crosslister: een duidelijk activiteitenlogboek dat per artikel toont wat is aangemaakt, gewijzigd of verwijderd en waarom, vooral bij een artikel dat op twee kanalen tegelijk verkoopt | Zelfde idee als Alameddin op IH; logboek voor de verkoper zelf overwegen | Idee, niet opgepakt; beantwoord 27-11 |

## Gezien in reacties, geen actie nodig (17-11-2026)
- Gabriel Lora (Dag 162): benieuwd wat het evenement oplevert, vooral uit Duitsland. Sluitopmerking, niet beantwoord. Als er een evenement in de planning staat: update schrijven met de cijfers uit Duitsland.

## Ideeën voor eigen updates (nog niet aangekondigd)
- Voor-en-na van de eerste-minuten-loop met een vers account (zie overdracht.md, onboarding-tempo).
- Wat de helpknop na 10 minuten daadwerkelijk doet bij echte nieuwe klanten, in aantallen.
| 25-11-2026 | GautamTalksDev, Censtar (IH, dag 170) | Vraag: een waarschuwing aan verkopers als de extensie een dag of twee uit staat, voor de taken worden geannuleerd | Overweeg in-app melding | Beantwoord 25-11 aan Gautam (nog niet gemeten, kom erop terug) |
| 25-11-2026 | Zane Berg (IH, dag 170) | Fouten taggen op wie moet handelen (verkoper, niemand, ik); dagelijks overzicht voor verkopers | Idee voor foutenlijst | Gezien 25-11, niet beantwoord |
| 25-11-2026 | Nat Sortor (IH, dag 170) | Ontbrekend Vinted-kleurveld vangen voor de taak in de wachtrij komt | Idee | Gezien 25-11, niet beantwoord |
