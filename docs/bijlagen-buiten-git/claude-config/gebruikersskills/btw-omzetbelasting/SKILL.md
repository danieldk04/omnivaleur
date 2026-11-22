---
name: btw-omzetbelasting
description: Bereidt Daniels kwartaal BTW-aangifte (omzetbelasting) voor uit de Google Spreadsheet "Profitsheet Right" en een Gekko voorbelasting-export. Tweedehands kledinghandel onder de margeregeling (globalisatiemethode), geen OSS. Activeer deze skill zodra Daniel het heeft over: btw, omzetbelasting, btw-aangifte, kwartaalaangifte, voorbelasting, margeregeling, "mijn belasting doen", Profitsheet, of een specifiek kwartaal (Q1/Q2/Q3/Q4). Ook activeren wanneer de geplande kwartaalmelding afgaat.
version: 1.0.0
triggers:
  - btw
  - omzetbelasting
  - btw-aangifte
  - kwartaalaangifte
  - voorbelasting
  - margeregeling
  - profitsheet
  - belastingaangifte
---

# BTW / Omzetbelasting kwartaalaangifte — Daniel

Je bereidt de Nederlandse BTW-aangifte (omzetbelasting) voor van **D M DE KONING** (btw-nr **253036975**), een handel in tweedehands kleding.

## Vaste uitgangspunten (bevestigd door Daniel)

- **Regeling:** margeregeling, **globalisatiemethode**. BTW alleen over de winstmarge, niet over de volledige verkoopprijs.
- **Geen OSS.** Margegoederen die aan EU-consumenten worden verkocht blijven in NL belast → alles in **rubriek 1a**. Niks in 3b/3c.
- **Alle BTW-tarief = 21%.**
- Dit is een uitwerking van Daniels eigen data, **geen formeel belastingadvies** — zijn boekhouder blijft leidend voor de definitieve indeling. Wees eerlijk over onzekerheid, claim nooit 100% correctheid.

## Bronnen

1. **Verkopen:** Google Spreadsheet **"Profitsheet Right"** — fileId `13tHt7SWYqYdPKwyZaj5kkAcZt3G_IJCzksZYSL-zxgI` (eigenaar [adres van Daniels eigen winkel]), tab **P&L**.
2. **Voorbelasting:** een **Gekko-export** (`.xls`, sheet "Tablib Dataset") die Daniel aanlevert. Vraag hierom als hij die nog niet heeft gegeven.

⚠️ **Negeer** de eigen BTW-kolommen in de Profitsheet (BTW-Regeling toegepast, Marge BTW, Regulier BTW, OSS Btw, BTW Terug Inkoop) — die kloppen niet. Alles zelf herberekenen uit de marges.

## Stappenplan

### A. Verkopen → rubriek 1a
1. Download de P&L als **CSV** via Drive `download_file_content` (exportMimeType `text/csv`). Gebruik NIET `read_file_content`, die kapt de rijen af. Decodeer de base64 naar een CSV-bestand.
2. Filter op kolom **`Date Sold`** binnen het kwartaal (formaat `DD-MM-YYYY`).
   - Q1 = 1 jan–31 mrt · Q2 = 1 apr–30 jun · Q3 = 1 jul–30 sep · Q4 = 1 okt–31 dec.
3. Per verkocht item: **marge = `Price Sold` − inkoop**, waarbij inkoop = `Net Price Bought` (val terug op `Price Bought` als leeg).
4. **Netto marge kwartaal** = som van álle marges, **inclusief negatieve** (globalisatie saldeert positief en negatief).
5. Vraag Daniel of het **vorige kwartaal een negatief margesaldo** had; zo ja, trek dat er eerst af.
6. **BTW = 21/121 × netto marge.** Omzet excl. = netto marge − BTW. Afronden op hele euro's.
7. → **Rubriek 1a:** Omzet (excl.) en Btw.

### B. Voorbelasting → rubriek 5b + verlegde BTW → rubriek 4
8. Lees de Gekko-export (`.xls`, sheet "Tablib Dataset"; kolommen o.a. `BTW 21%`, `BTW verlegd`, `Geen BTW`, `Leverancier`, `Totaal (ex BTW)`, `Datum`). Gebruik `xlrd` in Python.
9. **Voorbelasting (5b)** = som van kolom **`BTW 21%`**. Posten met `Geen BTW = Ja` en de kledinginkoop (bv. Fleek Commerce / Riaaj Vintage) geven **geen** aftrek.
10. **Verlegde BTW** (`BTW verlegd = Ja`): buitenlandse leveranciers (bv. Namecheap, Anthropic = VS). Bereken **21% × `Totaal (ex BTW)`** per post.
    - Buiten EU (VS e.d.) → **rubriek 4a**; binnen EU → **rubriek 4b**. Vul Omzet (grondslag) én Btw in.
    - Dezelfde verlegde BTW is óók aftrekbaar → tel op bij voorbelasting (5b). Per saldo € 0, maar moet formeel in rubriek 4 staan. **Rubriek 4 is dus niet altijd leeg.**

### C. Presenteren
11. Geef een overzichtstabel met de exacte in te vullen velden:
    - Rubriek 1a: Omzet / Btw
    - Rubriek 4a of 4b (indien verlegde posten): Omzet / Btw
    - Rubriek 5b: voorbelasting
    - **Te betalen ≈ 1a-btw + 4-btw − 5b.**
    - Alle overige rubrieken (1b–1e, 2a, 3a, 3b, 3c) leeg/€0.
12. Benoem expliciet welke aannames Daniel nog moet bevestigen (negatief saldo vorig kwartaal; of verlegde posten terecht als zodanig staan).
13. Bied aan een **Excel-totaaloverzicht** te exporteren naar `~/Downloads` (samenvattingsblad + detailregels met marge per item, negatieve marges rood).

## Referentie: Q2 2026 (ijkpunt)
150 verkopen, netto marge € 2.026,80 → **1a: omzet € 1.675 / btw € 352**. Voorbelasting **5b € 33** (€ 29,40 direct + € 3,40 verlegd). **4a:** Namecheap € 6,19 + Anthropic € 10,00 → omzet € 16 / btw € 3. **Te betalen ≈ € 322.**
