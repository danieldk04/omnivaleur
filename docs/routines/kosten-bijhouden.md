# Kosten bijhouden (maandelijks)

Bestand: Google Sheet "Omnivaleur kosten" in Drive, map Omnivaleur.
Id: 1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U
Link: https://docs.google.com/spreadsheets/d/1BQ5bwdMXPEd-bAipoROaqSaEU0bThdvwBx5GdYYs43U/edit

Let op: crosslist-eu bij Supabase is de oude naam van Omnivaleur. Dat project is dus de
productiedatabase en mag nooit gepauzeerd of verwijderd worden. Het andere Supabase-project
("danieldekoning66@gmail.com's Project") is nog niet uitgezocht.

## Opdracht

1. Lees de sheet (rijen 5 tot 20, kolommen A tot I) met de Sheets-klasse uit scripts/leadgen_sheets.py
   (python 3.13: /Library/Frameworks/Python.framework/Versions/3.13/bin/python3, sleutel in
   ~/.omnivaleur/sheets-sleutel.json). De sleutel (omnivaleur-leadmachine@...) heeft schrijfrecht op dit ene bestand.
2. Open in Daniels Chrome (Claude in Chrome, hij is daar ingelogd) de factuurpagina's en lees de echte bedragen:
   - Railway: railway.com/workspace/billing en /workspace/usage
   - Supabase: supabase.com/dashboard/org/_/billing, klik de organisatie aan (upcoming invoice en past invoices)
   - Anthropic API: platform.claude.com/settings/billing (tegoed gekocht afgelopen maand, saldo, auto-reload)
   - Claude.ai: claude.ai/settings/billing (abonnement, extra tegoed, saldo)
   - Cloudflare: dash.cloudflare.com, Billing, Billable usage
   - Apify: console.apify.com/billing, Resend: resend.com/settings/billing
   - Stripe: dashboard.stripe.com/balance/overview (uitbetaling tegen 19,99 = kosten per betaling)
   - Hostinger: hpanel.hostinger.com/billing/subscriptions
   Serper vraagt inloggen: sla over en laat de rij op "Niet gemeten" staan. Voer nooit wachtwoorden in.
3. Schrijf per dienst kolom E (tekst met het gemeten bedrag), F (maandbedrag in euro, als getal), G (datum van meting,
   JJJJ-MM-DD) en I (opmerking) bij. Schrijf met de Sheets-klasse via schrijf(), die schrijft RAW:
   dus alleen rijen 5 tot 20, NOOIT de totaalrijen 22 tot 25, daar staan formules.
   Dollars omrekenen tegen de koers van die dag, zet de gebruikte koers in B2.
4. Nieuwe kostenpost gevonden (nieuwe dienst, plan veranderd, tegoed bijgekocht)? Zet hem in de juiste groep
   (Vast rijen 5 tot 12, Wisselend rijen 13 tot 16). Een nieuwe rij tussen de groepen invoegen via wijzig() zodat
   de SUM-formules meegroeien.
5. Controleer na het schrijven met lees() dat F22 tot F25 kloppen en niet leeg of 0 zijn.
6. Meld in de chat: totaal per maand, wat er sinds vorige maand veranderde, en wat Daniel moet doen
   (bijvoorbeeld tegoed laag, gratis limiet bereikt, factuur gestegen). Houd je aan de vier blokjes uit CLAUDE.md.
7. Zet een korte regel in docs/team-notes.md met datum en totaal.
