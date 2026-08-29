# Omnivaleur — project instructions

This file is repo-local and checked into git, so it loads for every Claude
Code session opened against this repo — on any of Daniel's machines or
Anthropic accounts. That makes it the right place for anything that must
never depend on which account happens to be running.

## Begin elke sessie met kijken wat er veranderd is

Voordat je aan wat dan ook begint — een codetaak, een vraag, een mail, een
controle — zoek je eerst uit wat er is veranderd sinds jouw vorige sessie:

1. `git log --since="30 hours ago" --name-only`, en lees de diff van alles wat je
   onderwerp raakt. Bij een langere pauze: sinds je laatste sessie.
2. De laatste toevoegingen onder aan `docs/team-notes.md`.
3. Je eigen postvak van de klantenservice:

   ```bash
   python3 scripts/mail_analyse.py bugs
   ```

   Dat is geen extraatje. De rolverdeling ligt vast (zie `docs/team-notes.md`):
   Daniel is CEO, de mailagent is de klantenservicemedewerker, jij bent de
   developer. Wat klanten melden komt via die lijst bij jou terecht en niet via
   Daniel. Staat er `MOET ZEKER` bij, dan is dat het seintje dat die storing met
   zekerheid gerepareerd moet worden — een klant is er boos over, dreigt te
   stoppen, of het overkomt meerdere mensen.

   Heb je iets gerepareerd, meld dat dan terug in dezelfde lijn:

   ```bash
   python3 scripts/mail_analyse.py opgelost <sleutel> "wat er nu anders is, in gewone taal"
   ```

   Daarmee weet de klantenservice het: iedereen die het meldde krijgt bericht,
   en elk nieuw concept over dat onderwerp zegt voortaan wat jij hebt vastgelegd
   in plaats van te gokken. Overslaan betekent dat de klant nooit hoort dat zijn
   melding iets heeft opgeleverd.

Let op de commits met de tekst "auto: update ...": die komen van de auto-push-hook
en bevatten echt werk achter een nietszeggende titel. De auteursnaam zegt niets
over wie het deed.

**Waarom dit hier staat en niet alleen in lokale memory:** aan dit project werken
drie partijen die elkaar niet zien — Daniel op zijn eigen account, een tweede
ontwikkelaar, en meerdere Claude-sessies naast elkaar. Zonder deze stap bouw je
iets wat er al is, repareer je iets wat net gewijzigd is, of mis je juist de
wijziging die het probleem veroorzaakte. Dat is op 27-08-2026 aantoonbaar
gebeurd: een eerdere sessie voegde `output_config` toe aan de Claude-aanroepen van
de mailagent, de gepinde SDK op de server kende die parameter niet, de fout werd
stil opgevangen en elke lead kreeg wekenlang de standaardmail.

Noem in je eerste antwoord kort wat je hebt gezien, zodat duidelijk is dat je het
huidige beeld hebt.

## Before touching anything people/business/decision-related

Read [docs/team-notes.md](docs/team-notes.md) first. It's an append-only log
of team, partnership, and business-decision context — who's involved, what
was agreed, why. Unlike `~/.claude` memory (which is per-account and does
not follow Daniel between logins), this file travels with the repo, so it's
the only place that guarantees a session on a *different* account isn't
missing context a session on another account already has.

When you make or learn a decision of that kind, append a dated entry to
`docs/team-notes.md` and push it — the same way a code change gets pushed.
Do not let it live only in memory or only in chat.
