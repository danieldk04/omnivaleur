---
name: omnivaleur-taken
description: >-
  Zet openstaande Omnivaleur-taken die alleen Daniel zelf kan doen in zijn Google
  Tasks lijst "Omnivaleur". Activeer deze skill wanneer Daniel vraagt wat er nog
  voor hem openstaat, wat hij moet doen, "mijn taken", "actiepunten", "check mijn
  Omnivaleur taken", "zet in mijn taken", of aan het eind van een sessie waarin
  iets is opgeleverd dat Daniel nog moet afmaken (Chrome Web Store,
  Supabase-dashboard, Stripe/Railway, DNS, een beslissing, iets naar buiten
  sturen). Ook activeren bij "check mijn agenda" in Omnivaleur-context.
---

# Omnivaleur-taken naar Google Tasks

Doel: Daniel hoeft niet in code of mail te graven om te weten wat er van hém
ligt. Alles wat hij zelf moet doen komt als taak in zijn Google Tasks lijst
"Omnivaleur", kort en concreet, met precies wat hij moet doen en waarom.

## 1. Verzamel de openstaande taken

Kijk in deze bronnen. Neem alleen op wat **Daniel zelf** moet doen en wat een
Claude-sessie **niet** kan (zie de filter in stap 2).

1. **Klantmeldingen:** `python3 scripts/mail_analyse.py bugs`
   Meestal is dit werk voor de developer, niet voor Daniel. Alleen als er een
   melding tussen zit die een dashboard-actie van Daniel vereist telt hij mee.
2. **Team-notes:** lees de laatste ~80 regels van `docs/team-notes.md`. Zoek op
   `Openstaand`, `Actiepunt`, `moet Daniel`, `met de hand in Supabase`,
   `Web Store`. Elke regel die aan Daniel is gericht is een kandidaat.
3. **Terugkerende Daniel-acties, altijd controleren:**
   - **Chrome Web Store:** vergelijk het hoogste `dist/omnivaleur-extension-*.zip`
     met de versie die live staat (zie `tweede-extensiekopie` memory: de
     poll-header `X-Extension-Version` of de Web Store-pagina). Staat de nieuwste
     zip nog niet in de Store en wachten er klanten op een fix, dan is uploaden
     een taak.
   - **Handmatige Supabase-migraties:**
     `grep -rn "ALTER TABLE\|CREATE TABLE" docs/team-notes.md | tail -20` en
     `grep -rn "handmatige Supabase" ~/.claude/projects/-Users-Danie-Documents-omnivaleur/memory/*.md`.
     Controleer per stuk of hij al gedraaid is (latere team-notes zeggen vaak
     "als eerder bij ..."). Alleen wat aantoonbaar nog niet gedraaid is telt.
4. **Deze sessie:** alles wat je vandaag hebt opgeleverd waar Daniel nog een
   handmatige stap voor moet zetten.

## 2. Filter: alleen wat Claude niet kan

Wél een Daniel-taak:
- Chrome Web Store upload (duurt weken, alleen Daniel heeft het account)
- SQL in het Supabase-dashboard (ALTER/CREATE TABLE, kolommen toevoegen)
- Stripe-, Railway-, Namecheap/DNS-, Notion-instellingen achter een login
- Een e-mail of bericht dat als Daniel de deur uit moet
- Een beslissing die aan Daniel is (prijs, positionering, partner)

Géén Daniel-taak (dat doet de developer-sessie zelf): code schrijven, tests
draaien, pushen, klantmail-concepten, bugs in de extensie of de backend.

## 3. Lees de bestaande taken (dubbel voorkomen)

Gereedschap: de `workspacemcp` server. Alle aanroepen hebben
`user_google_email: "danieldekoning66@gmail.com"` nodig.

1. `mcp__workspacemcp__list_task_lists` → zoek de lijst met titel "Omnivaleur",
   pak zijn ID (nu `UnlxRk9OVzFYdlBuYVpsbw`, maar controleer op naam, kan wijzigen).
2. `mcp__workspacemcp__list_tasks` met dat `task_list_id`, `show_completed: false`,
   `max_results: 100`.

Voor elke kandidaat-taak: staat er al een open taak met dezelfde kern (bijv.
"Web Store", "1.0.289", "offline_mail_sent_at")? → overslaan en dat melden.
Anders toevoegen.

Werkt de server niet (geen `workspacemcp` tools, of een auth-fout die niet
vanzelf oplost), val dan terug op hele-dag-items in de agenda
`danieldekoning66@gmail.com` (`create_event`, `allDay`, `colorId: "5"`,
`availability: "AVAILABILITY_FREE"`, titel met "Omnivaleur:" ervoor) en zeg dat
het in de agenda staat en niet in Tasks.

## 4. Zet de taak erin

`mcp__workspacemcp__manage_task` met `action: "create"`, `task_list_id` = de
Omnivaleur-lijst:
- `title`: kort, max 10 woorden, wat Daniel moet doen. Geen "Omnivaleur:" ervoor,
  de lijst zegt dat al.
- `notes`: 1 tot 3 regels: de exacte handeling (pad, SQL, knop) en waarom het nu
  moet (welke klant wacht). Geen opmaaktekens, geen gedachtestreepjes.
- `due`: altijd op vandaag zetten (RFC 3339 middernacht UTC, bijv.
  `2026-09-04T00:00:00.000Z`), zodat de taak onder "Vandaag" valt en niet onder
  "Geen datum". Is er een echte, latere deadline, gebruik die.

## 4b. Klaar is weg

Zegt Daniel dat een taak gedaan is, of blijkt uit code of team-notes dat het
geregeld is: `manage_task` met `action: "update"`, `status: "completed"` (of
`action: "delete"`). Laat geen afgehandelde taken open staan.

## 5. Meld terug aan Daniel

In de vier blokjes uit de hoofd-CLAUDE.md. Onder "wat er nu veranderd is": welke
taken je hebt toegevoegd. Onder "actiepunten": alleen de taken zelf, genummerd,
elk met de concrete handeling. Noem apart wat je oversloeg omdat het al in de
lijst stond.

## Voorbeeld-taak (vorm, niet inhoud)

- title: `Extensie 1.0.289 naar Chrome Web Store uploaden`
  notes: Upload dist/omnivaleur-extension-1.0.289.zip in de Chrome Web Store. Tot
  de Store hem doorlaat werkt de fix alleen op een handmatig geladen kopie.
