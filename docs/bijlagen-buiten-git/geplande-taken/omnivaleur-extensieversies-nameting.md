---
name: omnivaleur-extensieversies-nameting
description: Nameting: werkt de extensie zichzelf bij sinds 1.0.304?
---

Dit is de afgesproken nameting voor Omnivaleur (afgesproken met Daniel op 05-09-2026).

ACHTERGROND. Op 05-09-2026 bleek dat vrijwel geen enkele klant de nieuwste Chrome-extensie draaide; de oudste zat 43 versies achter. Chrome werkt een extensie alleen bij terwijl hij draait. Sinds versie 1.0.304 vraagt de extensie Chrome elk uur zelf om een bijwerkcontrole en herstart hij zichzelf als er een nieuwe versie klaarstaat, maar nooit terwijl er werk loopt. 1.0.304 is op 05-09-2026 naar de Chrome Web Store geüpload. De vraag die nu beantwoord moet worden: schuiven de klanten die eerder achterliepen daadwerkelijk mee?

DOE DIT:

1. Draai in /Users/Danie/Documents/omnivaleur:
   python3 scripts/tel_extensieversies.py
   Dat script laat zien welke versie er in de Chrome Web Store staat en welke versie elke computer draait die de afgelopen week online was.

2. Beoordeel het resultaat eerlijk:
   - Staat 1.0.304 (of hoger) inmiddels in de Web Store? Zo niet, dan is de proef nog niet begonnen: Google keurt soms dagen. Meld dat dan zo, en concludeer NIETS over het bijwerken.
   - Staat hij er wel, kijk dan of computers die eerder op 1.0.294 of ouder zaten nu op de winkelversie staan.
   - "Versie onbekend" bij een actieve computer betekent een kopie van vóór 1.0.304 die nog niet is bijgewerkt; tel die mee als achterlopend, niet als onbekend.

3. Belangrijk om te wantrouwen: een computer die al dagen niet online was zegt niets over het bijwerken, want die stond gewoon uit. Het script filtert daar al op, maar noem het als er weinig actieve computers zijn, want dan is de meting te dun om iets te concluderen.

4. Rapporteer aan Daniel volgens de vaste vier blokjes (wat er aan de hand was, wat er nu veranderd is, zekerheid in procenten, actiepunten). Nederlands, gewone taal, geen jargon, geen gedachtestreepjes. Hij is geen programmeur.

5. Blijkt het bijwerken NIET te werken, zoek dan uit waarom voordat je iets meldt. De meest waarschijnlijke oorzaken op volgorde: 1.0.304 nog niet goedgekeurd door Google, klanten die de extensie met de hand hebben geladen (die mag van Chrome nooit zelf naar updates zoeken), of de herstart die steeds wordt uitgesteld omdat er werk in de wachtrij blijft hangen. Dat laatste is te zien aan opdrachten die lang op "claimed" blijven staan.

6. Leg de uitkomst vast onderaan docs/team-notes.md met de datum erbij en push het, of het nu goed of slecht nieuws is.