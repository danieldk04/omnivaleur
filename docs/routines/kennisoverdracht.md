# Routine: kennisoverdracht (Daniel, 16-11-2026)

Doel: twee ontwikkelaars (twee Claude-accounts) werken aan hetzelfde project en moeten
altijd exact weten waar de ander gebleven is. `docs/overdracht.md` is daarvoor de ene
pagina die klopt "op dit moment". Deze routine houdt hem 1 op 1 gelijk aan de werkelijkheid.

## Wanneer

1. **Aan het eind van elke sessie** waarin je iets bouwde, repareerde, besliste of ontdekte
   dat niet meer klopte: doe de stappen hieronder voor je afrondt. Niet wachten op een verzoek.
2. **Dagelijks als vangnet**, door een geplande taak per account:
   - `omnivaleur-kennisoverdracht-avond`, 22:30, op het account van de tweede ontwikkelaar.
   - `omnivaleur-kennisoverdracht-ochtend`, 07:45, op Daniels hoofdaccount. Staat hij daar
     nog niet, maak hem dan aan in je eerstvolgende sessie, zet in team-notes dat hij staat.
   De taaktekst: "Je werkt aan Omnivaleur in <repomap>. Lees docs/routines/kennisoverdracht.md
   in die repo en volg het precies."

## Stappen (kort, batchen, geen subagents)

1. `git pull --rebase --autostash origin main`. Een andere sessie kan net gepusht hebben.
2. Zoek wat er nieuw is sinds de datum bij "Bijgewerkt" bovenin `docs/overdracht.md`:
   - `git log --since="<die datum>" --no-merges --format='%h %ad %s' --date=short | grep -v "auto: update"`
     (maar kijk ook naar "auto: update"-commits die echt werk bevatten).
   - De kopjes in `docs/team-notes.md` sinds die datum:
     `grep -n "^## " docs/team-notes.md | tail -60`, lees alleen wat geen gewone dagronde is.
3. Leg overdracht.md naast de werkelijkheid en meet wat je kunt meten, niet overschrijven
   vanuit het geheugen:
   - Extensieversie: `grep '"version"' extension/manifest.json`, Web Store-versie staat in
     de laatste onboarding-notitie.
   - Server: `curl -s https://omnivaleur.com/health` (commit, Google-sleutel `279422aa`).
   - Geplande taken: `list_scheduled_tasks`.
   - Open punten: staat er iets als open dat inmiddels klaar is (of andersom)?
4. Werk `docs/overdracht.md` bij, op zijn plaats, geen nieuw bestand:
   - Zet "Bijgewerkt <datum> door <wie>" bovenin.
   - "Wat er sindsdien gebeurde": voeg de lijn toe (besluiten, bouwwerk, klantwerk), schrap wat
     verouderd is. Het blijft één pagina; detail hoort in team-notes of kennisbank.
   - "Wat nu open staat": haal klare punten weg, voeg nieuwe toe, met wie het oppakt
     (`Daniel` / `Mac` / `iedereen`). Alleen wat alleen Daniel kan, krijgt het label Daniel.
   - Routinetabel: klopt wie wat draait nog?
5. Beslissingen en afspraken ook als dagboekregel onderaan `docs/team-notes.md`.
   Nieuwe les: geheugenbestand, daarna `python3 scripts/export_kennisbank.py`.
6. Commit en push naar main (`git add docs/overdracht.md docs/team-notes.md docs/kennisbank.md`,
   alleen die). Verandert er niets, schrijf dan één regel in team-notes "kennisoverdracht
   <datum>: niets nieuws" en niets anders.

## Regels

- Overdracht.md bevat alleen wat je zelf gezien of gemeten hebt, met datum. Twijfel je:
  zet er "niet gecontroleerd" bij.
- Geen dubbel werk: heeft de andere ontwikkelaar vandaag al bijgewerkt (kijk naar de datum
  en het uur bovenin en `git log -3 -- docs/overdracht.md`), voeg dan alleen toe wat daarna
  gebeurde.
- Nooit een geheim, sleutel of klantadres in deze bestanden zetten dat er nog niet in staat.
- Rapport aan Daniel in de vier blokjes, kort. Actiepunten alleen wat alleen hij kan.
