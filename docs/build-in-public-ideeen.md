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
| 21-11-2026 | Facebook Startende Ondernemers, Etsy-post | Aan Gert Pellin: uitzoeken of Etsy API-toegang via de klant zelf kan lopen (wij bouwen met mocks, klanten vragen zelf toegang aan) | Etsy-documentatie en voorwaarden lezen, kijken of onze afwijzing daarmee samenhangt | 28-11-2026 | Open |
| 20-11-2026 | Dag 166, antwoord aan Dmytro Katyukha | Toegezegd: alle 88 reacties op de koude mail doorlopen en tellen hoeveel er een advertentie meestuurden met de vraag die op een ander kanaal te zetten, en erop terugkomen | Mail-antwoorden (88) doorlezen en tellen | 23-11-2026 | Open |
| 16-11-2026 | Dag 163, "quick win voor nieuwe gebruikers" | Terugkomen met wat het doet in de komende weken (inventaris start vanzelf, 1 klik plaatsen van het beste artikel, helpknop na 10 minuten, gemailde link naar de computer) | Mediane tijd van aanmelding tot eerste live advertentie, voor en na 16-11 (zie `docs/routines/onboarding-nieuwe-klanten.md`, onboarding-tempo). Daarnaast: hoe vaak de helpknop wordt aangeklikt | 30-11-2026 | Open. Vanaf ~30-11 meetbaar |
| 15-11-2026 | Dag 162, Search Console van /nl | Daniel liet de /nl-titel voorlopig staan en zei dat hij terugkomt zodra echte taakzoekopdrachten (zoals 'tegelijk plaatsen op Marktplaats en Vinted') in Search Console verschijnen (Five Hands Studio, 16-11: 'Worth a re-check once you start seeing task-style queries') | Search Console /nl: aantal klikken van zoekopdrachten die niet 'omnivaleur' bevatten, voor en na | 24-11-2026 | Open (voorlopige datum, eerste herkijk) |
| 17-11-2026 | Dag 164, Etsy afgewezen | Aan Gabriel Lora toegezegd: uitzoeken wat de mensen die om Etsy vroegen verkopen en of dat vintage (20+ jaar), handmade of craft is, en daarop terugkomen | Per Etsy-vrager nagaan wat de voorraad is (klantmails, sheet Omnivaleur te bouwen) | 20-11-2026 | Open |
| 19-11-2026 | Dag 165, referralprogramma | Aan hiredov toegezegd: tellen hoeveel gebruikers via de Facebook-groepen of informele uitnodigingen binnenkwamen en daarop terugkomen | Aanmeldbron per klant (mail, groep, doorverwijzing) uit de klantdata | 23-11-2026 | Open |
| 19-11-2026 | Dag 162, bezoekers per land | Aan ruslann3s toegezegd: aanmeldingen per land uitsplitsen (NL, BE, buiten de EU) en daarop terugkomen | Aanmeldingen per land uit de klantdata (land van de verkoper) | 23-11-2026 | Open |

## Ideeën uit reacties

| Datum | Van | Idee of vraag | Wat we ermee kunnen | Status |
|---|---|---|---|---|
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

## Gezien in reacties, geen actie nodig (17-11-2026)
- Gabriel Lora (Dag 162): benieuwd wat het evenement oplevert, vooral uit Duitsland. Sluitopmerking, niet beantwoord. Als er een evenement in de planning staat: update schrijven met de cijfers uit Duitsland.

## Ideeën voor eigen updates (nog niet aangekondigd)
- Voor-en-na van de eerste-minuten-loop met een vers account (zie overdracht.md, onboarding-tempo).
- Wat de helpknop na 10 minuten daadwerkelijk doet bij echte nieuwe klanten, in aantallen.
