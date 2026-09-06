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
3. Sinds 06-09-2026 is de klantenservice-laag eruit (zie `docs/team-notes.md`).
   De mailmachine schrijft geen antwoorden of concepten meer en deelt geen post
   meer in met AI — dat kostte tokens en liet het API-tegoed leeglopen. Wat nog
   draait is de koude reeks mail 1/2/3 uit vaste sjablonen.

   Klanten mailen bugs rechtstreeks; Daniel leest de inbox en brengt ze bij je.
   `scripts/mail_analyse.py` bestaat nog als handmatig hulpmiddel (`bugs` toont
   de oude lijst), maar niets vult die lijst meer automatisch en `lezen` /
   `bericht_over_reparaties` falen bewust omdat de AI eruit is. De LaunchAgent
   `com.omnivaleur.devstarter` staat daarmee stil: geen buglijst, geen
   automatische sessies.

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

## De kennisbank: lessen van eerdere sessies

[docs/kennisbank.md](docs/kennisbank.md) bundelt alles wat eerdere sessies hebben
geleerd — valkuilen, werkafspraken, waarom bepaalde keuzes zo zijn. Die lessen
staan normaal in de lokale geheugenmap van één Claude-account en zijn voor een
andere ontwikkelaar onzichtbaar; hier reizen ze mee met de repo.

Sla het niet over voor je iets aanpakt dat je niet kent: het scheelt je de fout
die iemand anders al een keer heeft gemaakt. Leer je zelf iets nieuws, leg het
vast in je geheugen en draai daarna `python3 scripts/export_kennisbank.py`, en
commit het bestand.

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
