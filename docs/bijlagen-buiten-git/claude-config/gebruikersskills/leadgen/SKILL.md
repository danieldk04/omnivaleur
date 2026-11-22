---
name: leadgen
description: Draait en onderhoudt de leadgeneratie van Omnivaleur — Marktplaats-handelaren met e-mailadres (hoofdbron) en Instagram-resellers (kleine aanvulling), en schrijft ze naar de Google-spreadsheet Omnivaleur E-mail outreach (sinds 14-09-2026, was de Notion-Leadlist). Activeer deze skill zodra Daniel het heeft over leads, leadgen, nieuwe leads zoeken, prospects, outreach-lijst, verkopers zoeken, Marktplaats-handelaren, de Leadlist, "meer leads", of vraagt hoeveel leads erbij gekomen zijn. Ook activeren bij vragen over crosslisters vinden of over welke leadbron het meeste oplevert.
version: 1.0.0
triggers:
  - leads
  - leadgen
  - leadgeneratie
  - prospects
  - outreach
  - leadlist
  - marktplaats-handelaren
  - crosslisters
---

# Leadgeneratie Omnivaleur — Daniel

Doel: zoveel mogelijk **Nederlandse en Belgische handelaren in verzendbare tweedehands spullen** vinden, met een e-mailadres erbij, en ze in de spreadsheet Omnivaleur E-mail outreach zetten (tab Leads) zodat de mailmachine ze kan benaderen en Daniel ze kan volgen.

Daniel is geen programmeur. Rapporteer in gewone taal en in gevolgen: hoeveel leads erbij, hoeveel met e-mail, wat hij nu moet doen.

## De twee bronnen, met gemeten opbrengst

| Bron | Script | Opbrengst (gemeten 2026-08-10) |
|---|---|---|
| **Marktplaats** — de motor | `scripts/leadgen_marktplaats.py` | 1.662 zakelijke verkopers → 381 leads, 324 met e-mail |
| Instagram — kleine aanvulling | `scripts/leadgen_instagram.py` | 194 profielen → 15 leads, **0** e-mailadressen |

Instagram levert mooie maar weinig leads en je kunt er alleen handmatig DM'en. Zet er geen tijd in als Daniel om volume vraagt — dan is Marktplaats het antwoord.

## Standaardopdracht: nieuwe leads halen

```bash
export GOOGLE_SHEETS_SLEUTEL="$(security find-generic-password -a google-sheets -s omnivaleur-google-sheets -w)"
python3 scripts/leadgen_marktplaats.py run --dry-run   # eerst kijken
python3 scripts/leadgen_marktplaats.py run             # dan wegschrijven
```

De vijf stappen draaien achter elkaar en schrijven elk naar `scripts/output/leads/`. Elke stap leest de vorige van schijf, dus na een onderbreking pak je met het losse subcommando verder op waar het misging in plaats van opnieuw te betalen voor wat al gelukt was.

1. `discover` — sweept de rubrieken en houdt alleen verkopers met een zakelijk signaal over
2. `enrich` — bedrijfsprofiel: KvK, telefoon, e-mail, plaats, "over ons"
3. `crosslist` — verkoopt hij al op meer plekken? eigen webshop, webshopsysteem, bol.com
4. `classify` — Haiku beoordeelt op verzendbaar, winstmotief en NL/BE
5. `push` — onderaan de tab Leads van de spreadsheet, Platform "MP" of "2dehands", fase "1. Te benaderen". Alleen leads met e-mailadres; wie er al staat blijft ongemoeid.

**Alles is cachend.** Verkopers die al beoordeeld zijn gaan niet nog eens naar het model, en handles die niet bestaan worden na drie mislukte rondes definitief opgegeven. Een tweede run kost daardoor bijna niets. Verwijder `mp_sellers.json` dus NOOIT om "opnieuw te beginnen" — daarmee gooi je alle oordelen weg.

## Wat Daniel heeft besloten

- **Ondergrens 20 advertenties** (`--min-ads`, staat standaard aan). Onder die grens is crosslisten geen probleem dat je met een tool oplost. Verlaag alleen als de lijst opdroogt.
- **Alleen verzendbare rubrieken.** Huis-en-inrichting en antiek staan bewust niet in `CATEGORIES`: banken en kasten gaan niet in een doos.
- **Koude mail nooit vanaf omnivaleur.nl.** Dat domein stuurt de transactionele mail via Resend; als dat als spam wordt gemarkeerd komen wachtwoord- en factuurmails ook niet meer aan. Waarschuw hiervoor zodra hij over versturen begint.

## De heetste leads eruit pikken

De `crosslist`-stap meet of iemand al op meer dan één kanaal verkoopt. Gemeten: **56% van de leads heeft naast Marktplaats een eigen webshop of bol.com** — die doen nu handmatig wat de tool automatiseert, en dat is het scherpste argument dat er is.

Sorteer bij twijfel op: veel advertenties × verkoopt al op meerdere kanalen × heeft e-mailadres. In de spreadsheet staat het in de kolommen Verkoopt, Advertenties en Website. Een lead met een Shopify-webshop is extra interessant, want daar heeft Omnivaleur een koppeling voor.

Wat wél te meten is: eigen webshop, webshopsysteem, bol.com. Wat **niet**: eBay, Vinted en 2dehands — de redenen staan in de code bij `crosslist`. Beloof Daniel dus nooit een compleet beeld van alle kanalen.

## De koude mail draait vanzelf

Sinds 06-09-2026 draait de machine op de Railway-scheduler (elke 10 minuten) en
sinds 14-09-2026 schrijft hij alles in de spreadsheet Omnivaleur E-mail outreach.
De mailteksten komen uit de tab Mailteksten, die Daniel zelf aanpast; het vinkje
"Niet meer mailen" haalt iemand uit de reeks. Details in de geheugenbestanden
`koude-mail-autonoom` en `leadlist-in-google-sheets`.
**Belangrijk voor deze skill:** heb je nieuwe leads binnengehaald met `run`, draai
dan ook `python3 scripts/leadgen_mail.py overzetten`, anders staan ze wel in de
spreadsheet maar ziet de mailmachine ze niet.

## Meer volume nodig?

In deze volgorde, want zo loopt de opbrengst per bestede minuut af:

0. **2dehands.be** — `python3 scripts/leadgen_marktplaats.py run --site 2dehands`.
   Zelfde zoek-API en zelfde categorie-ID's als Marktplaats, verse Belgische
   markt, €0 extra. Testrun 07-09-2026: 76% van de profielen had een e-mailadres.
   Eigen cache (`2dh_*.json`); `leadgen_mail.py overzetten` pakt de leads erbij.
1. `--depth 5000` bij `discover` — dieper per subcategorie (het plafond van de API)
2. Rubrieken toevoegen aan `CATEGORIES` in het script — ID's ophalen uit `searchCategory` in de HTML van `https://www.marktplaats.nl/l/{slug}/`, **nooit gokken** (1032 lijkt kleding maar is Huizen en Kamers)
3. `--min-ads` verlagen naar 10
4. Pas daarna Instagram: `python3 scripts/leadgen_instagram.py run`

## Vaste valkuilen

- **De machine zoekt kolommen in de tab Leads op hun kopnaam.** Hernoemt iemand een kolom, dan wordt die overgeslagen en gemeld, niet verzonnen. Staan de mailteksten of het stopvinkje niet goed, dan gaat er bewust niets uit en krijgt Daniel een seintje. Controleer de teksten met `python3 scripts/leadgen_mail.py teksten`.
- **Instagram en Facebook staan in een aparte spreadsheet** (Omnivaleur Instagram & FB outreach) en worden met de hand bijgehouden. Nooit leads van die kant in de e-maillijst zetten.
- **`APIFY_TOKEN` en `GOOGLE_SHEETS_SLEUTEL` staan niet in de lokale `.env`**; die moeten met `export` mee. Marktplaats heeft geen Apify nodig, Instagram wel.
- Draai lange stappen op de achtergrond en wacht op het resultaat; een volledige `discover` duurt ruim tien minuten.

## Verantwoording

De cijfers in dit bestand zijn gemeten, niet geschat. Voeg nooit een bron of hashtag toe "omdat het logisch lijkt" — meet eerst wat het na classificatie oplevert, en schrijf het resultaat erbij. Zo is #vinted eruit gegaan: grootste leverancier van de run, nul leads.

Achtergrond en techniek staan in de kop van `scripts/leadgen_marktplaats.py` en in de geheugenbestanden `leadgen-marktplaats-beste-bron`, `leadgen-vier-bronnen` en `leadlist-in-google-sheets`.
