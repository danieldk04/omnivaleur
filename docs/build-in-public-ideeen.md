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
| 16-11-2026 | Dag 163, "quick win voor nieuwe gebruikers" | Terugkomen met wat het doet in de komende weken (inventaris start vanzelf, 1 klik plaatsen van het beste artikel, helpknop na 10 minuten, gemailde link naar de computer) | Mediane tijd van aanmelding tot eerste live advertentie, voor en na 16-11 (zie `docs/routines/onboarding-nieuwe-klanten.md`, onboarding-tempo). Daarnaast: hoe vaak de helpknop wordt aangeklikt | 30-11-2026 | Open. Vanaf ~30-11 meetbaar |
| 15-11-2026 | Dag 162, Search Console van /nl | Daniel liet de /nl-titel voorlopig staan en zei dat hij terugkomt zodra echte taakzoekopdrachten (zoals 'tegelijk plaatsen op Marktplaats en Vinted') in Search Console verschijnen (Five Hands Studio, 16-11: 'Worth a re-check once you start seeing task-style queries') | Search Console /nl: aantal klikken van zoekopdrachten die niet 'omnivaleur' bevatten, voor en na | 24-11-2026 | Open (voorlopige datum, eerste herkijk) |

## Ideeën uit reacties

| Datum | Van | Idee of vraag | Wat we ermee kunnen | Status |
|---|---|---|---|---|
| 16-11-2026 | Polymetis | Voortgang die al is gestart: checklist opent met "Account created" afgevinkt, zodat de verkoper op stap 3 van 5 landt (autowas-onderzoek: 19% tegen 34% afgerond) | Staat al live: poort met "Account created" afgevinkt, stap 2 van 5 (commit 2d15495d). Update schrijven met het effect op de tijd tot eerste advertentie | Gebouwd, effect nog te meten |
| 16-11-2026 | Polymetis | eBay zou voor particuliere verkopers in Frankrijk en Italië de kosten naar de koper verschuiven, dus meer losse verkopers | Frankrijk en Italië als onboarding-push overwegen. Claim van reageerder, niet gecontroleerd. Daniel zit vooral in NL en BE | Idee, eerst controleren |
| 16-11-2026 | LiranBlumenberg | Eerste taak duidelijker maken: kies één bestaande advertentie, bekijk hoe hij op de tweede markt eruit ziet, publiceer. Verkoper mag het voorgestelde artikel wisselen, ziet ontbrekende velden en kan voortgang bewaren | Test voorstellen voor de "Place now"-stap. Niet gebouwd | Idee |
| 16-11-2026 | LiranBlumenberg | De gemailde link van telefoon naar computer moet terugkomen op dezelfde stap, niet op het begin | Nameten of dat zo werkt, en zo nee repareren. Daniel heeft dit half toegezegd | Te controleren |
| 16-11-2026 | LiranBlumenberg | Kies één land en één marktplaatsenpaar, zoek handmatig verkopers die vragen hoe ze niet dubbel hoeven te plaatsen; verkeerscijfers van dag 162 bewijzen niet welke bezoekers bots zijn | Content-onderwerp: wat bots en echte bezoekers uit het verkeer scheidt. Volg apart: gesprek, aanmelding, eerste crosslist | Idee |
| 16-11-2026 | dgknght | Benieuwd hoe de helpknop uitpakt | Update schrijven met hoe vaak hij wordt geklikt en of die klikkers blijven | Wacht op meting |
| 16-11-2026 | (afgekapt, auteur onbekend) | Meet de mediane tijd van aanmelding tot eerste live advertentie, voor en na de wijziging | Zelfde meting als de open belofte hierboven | Wacht op volledige tekst |

## Gezien in reacties, geen actie nodig (17-11-2026)
- Gabriel Lora (Dag 162): benieuwd wat het evenement oplevert, vooral uit Duitsland. Sluitopmerking, niet beantwoord. Als er een evenement in de planning staat: update schrijven met de cijfers uit Duitsland.

## Ideeën voor eigen updates (nog niet aangekondigd)
- Voor-en-na van de eerste-minuten-loop met een vers account (zie overdracht.md, onboarding-tempo).
- Wat de helpknop na 10 minuten daadwerkelijk doet bij echte nieuwe klanten, in aantallen.
