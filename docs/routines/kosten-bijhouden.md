# Kosten bijhouden (maandelijks)

Bestand: Google Sheet "Omnivaleur kosten" in Drive, map Omnivaleur.
Id: 1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U
Link: https://docs.google.com/spreadsheets/d/1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U/edit

Afspraak (Daniel, 04-10-2026, op 01-11-2026 vervangen): Anthropic API en extra tegoed tellen sinds 01-11-2026 WEL mee voor Omnivaleur (bunq-post ANTHROPIC, gemiddelde van de laatste drie maanden), naast Claude Pro (EUR 18). Niet dubbel tellen. Het project crosslist-eu bij Supabase
buiten beschouwing laten.

## Opdracht

1. Lees de sheet (tab 1: rijen 5 tot 23, kolommen A tot I; tab "Revaleur": rijen 5 tot 10) met de Sheets-klasse uit scripts/leadgen_sheets.py
   (python 3.13: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3, sleutel in
   ~/.omnivaleur/sheets-sleutel.json). De sleutel (omnivaleur-leadmachine@...) heeft schrijfrecht op dit ene bestand.
2. Open in Daniels Chrome (Claude in Chrome, hij is daar ingelogd) de factuurpagina's en lees de echte bedragen:
   - Railway: railway.com/workspace/billing en /workspace/usage
   - Supabase: supabase.com/dashboard/org/_/billing, klik de organisatie aan (upcoming invoice en past invoices)
   - Claude.ai: claude.ai/settings/billing (alleen het Pro abonnement, nu EUR 18)
   - Cloudflare: dash.cloudflare.com, Billing, Billable usage
   - Apify: console.apify.com/billing, Resend: resend.com/settings/billing
   - Stripe: dashboard.stripe.com/balance/overview (uitbetaling tegen 19,99 = kosten per betaling)
   - Hostinger: hpanel.hostinger.com/billing/subscriptions
   Serper, GitHub en Notion zijn gratis (Daniel, 04-10-2026), staan op 0. Domeinen zijn ±EUR 1 per maand (schatting Daniel);
   lees het echte bedrag zodra Daniel zegt waar ze geregistreerd staan. Voer nooit wachtwoorden in.
3. Schrijf per dienst kolom E (tekst met het gemeten bedrag), F (maandbedrag in euro, als getal), G (datum van meting,
   JJJJ-MM-DD) en I (opmerking) bij. Schrijf met de Sheets-klasse via schrijf(), die schrijft RAW:
   dus alleen rijen 5 tot 23 (Wisselend is rijen 16 tot 19, de rest is Vast), NOOIT de totaalrijen 25 tot 28, daar staan formules. Lees de rijen altijd eerst uit en ga niet af op deze nummers: er zijn rijen ingevoegd.
   Dollars omrekenen tegen de koers van die dag, zet de gebruikte koers in B2.
4. Nieuwe kostenpost gevonden (nieuwe dienst, plan veranderd, tegoed bijgekocht)? Zet hem in de juiste groep
   (Vast of Wisselend, zie kolom D). Een nieuwe rij tussen de groepen invoegen via wijzig() zodat
   de SUM-formules meegroeien.
5. Controleer na het schrijven met lees() dat F25 tot F28 kloppen en niet leeg of 0 zijn.
6. Meld in de chat: totaal per maand, wat er sinds vorige maand veranderde, en wat Daniel moet doen
   (bijvoorbeeld tegoed laag, gratis limiet bereikt, factuur gestegen). Houd je aan de vier blokjes uit CLAUDE.md.
7. Zet een korte regel in docs/team-notes.md met datum en totaal.

## Bunq-afschrift (vanaf 01-11-2026, vaste stap)

De bunq-export is de echte bron voor wat er werkelijk wegloopt. Zoek in ~/Downloads de nieuwste
`*_exporteren.csv` (bunq, kolommen Date, Amount, Name, Description). Is het bestand ouder dan de 1e van deze maand,
meld dan als actiepunt voor Daniel [NU, 2 min]: "Exporteer het bunq-afschrift tot en met gisteren naar Downloads", en
ga door met de bedragen van de diensten zelf. Loop per dienst in de sheet na of de bedragen kloppen met bunq
(Anthropic, ElevenLabs, CapCut, Google One, Supabase, Railway, Google Cloud) en zoek nieuwe terugkerende posten
die nog niet in de sheet staan (zelfde naam in minstens twee maanden). Posten van Revaleur (Metricool, Shopify,
Whop Fyndit) horen niet in deze sheet. Daniel bepaalt bij een onbekende post of hij bij Omnivaleur, Revaleur of privé hoort: vraag, raad niet.
Deze routine draait om 09:00. De maandcheck en kwartaalcheck van de doelen draaien om 14:00 en lezen deze sheet; zorg dat de totaalrijen dus klaar zijn voor 14:00.

## Altijd bijwerken, ook buiten de maandronde (Daniel, 01-11-2026)

De sheet wordt ook door een andere routine gelezen en moet op elk moment kloppen. Verandert er iets
aan kosten (nieuwe dienst, opgezegd, ander plan, ander tegoed, een gemeten bedrag), werk de sheet dan
in dezelfde beurt bij, ook als de maandronde niet draait. Wat bij Omnivaleur hoort staat op tab 1,
wat bij Revaleur hoort op tab "Revaleur" (Metricool, Shopify, Whop Fyndit, Anthropic-sleutel
revaleur-blog). Een bedrag nooit op twee tabs tellen. Bron voor volledigheid: bunq-export (Daniel
levert die aan); de Anthropic-kosten komen per API-sleutel uit platform.claude.com/cost (groeperen op
API-sleutel). Nexus-trading-bot en blogs-zenbtw zijn andere projecten en staan er niet in.

## De bunq-export is leidend voor het totaal (Daniel, 01-11-2026)

Wat daadwerkelijk van de bunq-rekening gaat is de waarheid; de sheet moet daarmee kloppen, niet met wat een dienstpagina belooft.

1. Zoek bij elke ronde de nieuwste `*_exporteren.csv` in ~/Downloads (bunq, rekening NL85BUNQ2157496785). Is de nieuwste ouder dan 35 dagen of ontbreekt hij, zet dan in je rapport als actiepunt voor Daniel: "bunq-export van afgelopen maand downloaden". Verzin dan geen cijfers.
2. Tel per afgelopen volle maand alle uitgaven bij Omnivaleur-diensten (indeling hieronder) en leg ze naast het totaal van de sheet. Verschil groter dan EUR 5: zoek de post en corrigeer de sheet. Een nieuwe terugkerende afschrijving die nergens in de sheet staat meld je aan Daniel en vraag bij welk project hij hoort, tenzij hij hier al is ingedeeld.
3. De CSV is privé: nooit in git zetten, nooit kopiëren naar de repo, geen privé-uitgaven noemen in rapporten of team-notes.

Indeling door Daniel: Omnivaleur = Supabase, Railway, Claude Pro, Anthropic-tegoed van de sleutels crosslisteu en omnivaleur-2, ElevenLabs, CapCut, Google One, Google Cloud (Gemini), Zoho, domeinen, Hostinger-mail, KvK. Revaleur (tab "Revaleur") = Metricool, Shopify, Whop Fyndit, Anthropic-sleutel revaleur-blog. Niet meetellen: Anthropic-sleutels nexus-trading-bot en blogs-zenbtw, Mijn host (opgezegd), en alles wat privé is (Whoop, Decathlon, Vinted, Lime enzovoort).

Anthropic-tegoed loopt achter op het verbruik: een bijlading van USD 24,20 betaalt weken aan verbruik. Zet in de sheet het verbruikstempo per maand (Console, groeperen op API-sleutel, plus 21% btw) en gebruik de bunq-som alleen om te controleren over meerdere maanden. Automatisch bijladen blijft uit (Daniel, 01-11-2026): meld alleen als het saldo onder USD 3 komt, bijladen doet Daniel zelf.

## Samengevoegd met de doelencheck (Daniel, 01-11-2026)

Kosten en doelen zijn één routine: de geplande taak `omnivaleur-kosten-bijhouden` (1e van de maand, 09:00) doet eerst deze opdracht en daarna de skill `kwartaalcheck` (kwartaalmodus in jan/apr/jul/okt, anders maandmodus). De taken `kwartaalcheck-doelen-2027` en `maandcheck-doelen-2027` staan uit. De doelen staan nu als tabs "Doelen meetlog" en "Uitgangspunten" in deze sheet; de oude losse sheet "Doelen meetlog" is weg. Tab 1 heet nu "Omnivaleur". Formules in deze sheet gebruiken puntkomma's. Schrijf in tab "Doelen meetlog" alleen kolom B, C en D van de rij van de maand; de rest rekent mee.
