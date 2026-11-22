---
name: egbert-verlengingen-meten
description: Eenmalig 05-10-2026: meten of de 2dehands-verlengingen van Egbert (Papa's Plectrums) gelukt zijn
---

Je werkt aan Omnivaleur in /Users/Danie/Documents/omnivaleur. Antwoord in het Nederlands, gewone taal, in de vier blokjes uit CLAUDE.md (wat er aan de hand was, wat veranderd is, zekerheid in %, actiepunten met urgentielabel). Nooit een gedachtestreepje als leesteken.

Opdracht: meet of de 2dehands-verlengingen van Egbert Brouwer (Papa's Plectrums, user_id bcdf9aa4-314d-49a2-9573-8818ad61073d, 1.508 actieve 2dehands-zoekertjes, de oudste geplaatst 11-09-2026) gelukt zijn. Alleen meten, niets wijzigen, geen mail sturen.

Werkwijze:
1. Lees eerst de laatste toevoegingen onderaan docs/team-notes.md en `git log --since="7 days ago" --oneline`, zodat je weet wat er sinds 30-09 aan verlengen of de extensie veranderd is.
2. Draai met /usr/local/bin/python3 (die heeft httpx en supabase; de systeem-python niet) vanuit de repomap een script in de scratchpad. Laad .env zelf (geen dotenv beschikbaar), importeer `from backend.database import get_db`. Meet per klant, nooit jobs.result over meerdere klanten. De kolom jobs.error bestaat niet.
3. Meet voor zijn user_id: (a) jobs met platform='2dehands' en action='extend' sinds 01-10, per status (done/error/pending/claimed) met de resultaattekst van de fouten; (b) hoeveel van zijn actieve 2dehands-listings een listed_at hebben die na een geslaagde extend is opgeschoven (een geslaagde extend schuift listed_at vooruit); (c) hoeveel listings nu ouder dan 22 dagen zijn en nog geen extend kregen; (d) welke extensieversie hij draait, als dat uit heartbeat of jobs te halen is (extension_heartbeat).
4. Wantrouw een lege uitkomst: controleer eerst of de meting zelf klopt (bijvoorbeeld dat er 1.508 listings gevonden worden).
5. Vergelijk met de bekende oorzaak: extensies onder 1.0.358 lazen bij verlengen maar 200 zoekertjes ("200 listings read"), dus bij een klant met 1.500 zoekertjes kan verlengen mislukken. Zeg expliciet of dat bij hem speelt.
6. Rapporteer eerlijk: gelukt / deels / mislukt, met aantallen. Wat je niet kon meten, schrijf op als openstaand punt. Voeg een korte, veilige tekst voor Egbert toe die alleen bewezen dingen zegt, klaar voor Daniel om te versturen. Schrijf een korte dagboekregel onderaan docs/team-notes.md met de meting en commit en push die (auto-push-hook kan al pushen; controleer met git status).