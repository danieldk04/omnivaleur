# OSS-aangifte (Revaleur) en splitsing met de gewone btw-aangifte

Opgezet 25-11-2026 (Claude, opdracht Daniel). Daniel is sinds 1 juli 2026 geregistreerd voor
de Uniregeling (deelnemersnummer staat in Mijn Belastingdienst Zakelijk > E-commerce). Eerste
OSS-aangifte is Q3 2026. Dit is een uitwerking van Daniels data, geen formeel advies;
de boekhouder blijft leidend.

## Splitsing: elke verkoop staat in precies een van de twee

| Verkoop | Waar |
|---|---|
| Margeregeling, waar de koper ook woont (NL of EU) | gewone aangifte, rubriek 1a (globalisatie) |
| Regulier belast, koper in Nederland | gewone aangifte, rubriek 1a, 21/121 van de verkoopprijs |
| Regulier belast, consument in ander EU-land (vanaf 1 juli 2026) | OSS, tarief van het land van de koper |
| Voorbelasting (Gekko), verlegde btw | gewone aangifte, 5b en 4a/4b |

Voorbelasting trek je niet af in de OSS. Een OSS-verkoop mag niet ook in 1a staan (anders dubbel).

## Datums (zelfde als de gewone aangifte)
Q1 30 april, Q2 31 juli, Q3 31 oktober, Q4 31 januari. OSS ook indienen als je niets verkocht hebt.
OSS-btw apart betalen met het betaalkenmerk van de OSS-aangifte, niet samen met de gewone btw.
Herinnering in de agenda op de 20e van januari, april, juli en oktober.

## Stappen per kwartaal (binnen 5 dagen na kwartaaleinde)
1. Profitsheet P&L als CSV (Drive `download_file_content`, text/csv). Filter `Date Sold` in het kwartaal.
2. Controle: elk item met `BTW-Regeling toegepast` = Regulier en `Country Sold` buiten NL moet een
   OSS-bedrag hebben (kolom `OSS Btw` niet 0). Tarief per land: BE 21, FR 20, ES 21, IT 22, DE 19, PT 23.
3. OSS: per land netto omzet = prijs / (1 + tarief), btw = prijs - netto. Afronden per land.
4. Gewone aangifte: marge-items volgens skill btw-omzetbelasting; reguliere NL-items apart (zie open vraag).
5. Eerst gewone aangifte, dan OSS apart indienen en betalen.

## Q3 2026 (uit de sheet)
OSS: BE 94,01 incl. (netto 77,70, btw 16,31), FR 152,42 (netto 127,02, btw 25,40), ES 36,00 (netto 29,75, btw 6,25). Totaal btw 47,96.
Let op: item 598 (BE, 30-9, 55,50) heeft OSS Btw = 0 in de sheet, moet 9,63 zijn.
Q4 tot nu: IT 99,00 (22%, btw 17,85), FR 45,00 (20%, btw 7,50).

## Open
- Q3 gewone aangifte: staat de 282,43 aan reguliere EU-verkoop erin? Zo ja: suppletie.
- Reguliere NL-verkopen (Q3 drie items, 130,00 incl.): de skill rekent alles als marge. Bij een regulier item is de
  grondslag de volle prijs, niet de marge. Boekhouder laten bevestigen.

## Aangevuld 25-11-2026 na nalopen van de ingediende Q3-aangifte

**Portaal (Mijn Belastingdienst Zakelijk > Btw > E-commerce > Btw-meldingen > Openen).** Veld "Btw-bedrag" is het
btw-BEDRAG, niet de omzet (de omzet rekent het formulier zelf uit). Per land: btw-bedrag, percentage, tarief "algemeen".
De verklaring en het versturen zijn Daniels eigen klik. Betalen apart, met de gegevens die het overzicht in het portaal
toont (niet die van de gewone aangifte). Betaalgegevens staan bewust niet in de repo.

**Gewone Q3-aangifte (ingediend en betaald 20-10-2026):** 1a omzet 579 / btw 122, 4a 104/22, 4b 217/46, 5b 168, te betalen 22.
De sheet-cijfers (marge-items netto + reguliere NL-items over de volle prijs) geven 1a 559 omzet / 117,43 btw.
Verklaring van de ingediende 701 (579+122): dat is exact de som van alle POSITIEVE marges van alle 58 Q3-items
(700,82), dus ook de reguliere en OSS-items als marge en zonder saldering van negatieve marges. Overbetaling in 1a:
ongeveer 4 tot 5 euro (122 tegen 117). Voorbelasting (5b, uit Gekko) is volgens Daniel (25-11-2026) juist; niet opnieuw nalopen.
Tarieven BE 21, FR 20, ES 21 zijn gecontroleerd (europa.eu en andere bronnen, 25-11-2026).
Kleine correctie (onder 1.000 euro) mag in de volgende gewone aangifte (Q4, uiterlijk 31 januari 2027); geen aparte suppletie.

**Items met prijs maar zonder verkoopdatum (Daniel, 25-11-2026):** meld elk kwartaal items waar `Price Sold` is
ingevuld en `Date Sold` leeg is, want die vallen buiten elke berekening. Uitgezonderd, door Daniel bevestigd als
oud en niet van 2026: item 66, 67, 70, 73, 86, 105, 203, 213, 226, 277, 582, 727, 793, 814, 1270, 1298, 1299, 1300, 1314, 1316.
Elk ander nummer zonder datum melden aan Daniel.

**Sheet-controle (nieuw):** kolom AC "Binnenland verkocht?" is verborgen en moet "Nee" zijn bij elke buitenlandse
verkoop. Item 598 (rij 599) had hem leeg, daardoor stond OSS Btw op 0. Kijk elk kwartaal naar buitenlandse verkopen met lege AC.
