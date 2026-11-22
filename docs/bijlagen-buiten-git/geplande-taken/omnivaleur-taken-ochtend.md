---
name: omnivaleur-taken-ochtend
description: Werkt elke ochtend de Google Tasks lijst Omnivaleur bij met wat Daniel zelf moet doen
---

Je draait autonoom, zonder dat Daniel iets vroeg. Doel: zijn Google Tasks lijst "Omnivaleur" bijwerken met alles wat alleen hij zelf kan doen.

Stappen:
1. `cd /Users/Danie/Documents/omnivaleur` en `git pull -q`.
2. Roep de skill `omnivaleur-taken` aan (via de Skill-tool) en volg die volledig. Kort samengevat wat de skill doet: verzamelt Daniel-only openstaande taken uit `python3 scripts/mail_analyse.py bugs`, de laatste ~80 regels van `docs/team-notes.md`, en terugkerende acties (nieuwste `dist/omnivaleur-extension-*.zip` nog niet in de Chrome Web Store, handmatige Supabase-migraties). Filtert op wat een Claude-sessie niet kan. Leest eerst de bestaande taken in de Tasks-lijst Omnivaleur (`mcp__workspacemcp__list_task_lists` + `list_tasks`, `user_google_email` = danieldekoning66@gmail.com), slaat dubbele over, voegt de rest toe met `mcp__workspacemcp__manage_task` action create, en vinkt taken af die aantoonbaar klaar zijn.
3. Werkt de `workspacemcp` server niet, gebruik dan de agenda-terugval uit de skill.

Rapporteer kort in het Nederlands, in de vier blokjes uit de hoofd-CLAUDE.md: wat er open stond, wat je hebt toegevoegd of afgevinkt, zekerheid in %, en of er nog iets van Daniel wordt verwacht. Verwerk geen klantmails of code, alleen de takenlijst. Geen commits nodig tenzij de skill zelf iets aan de repo verandert.