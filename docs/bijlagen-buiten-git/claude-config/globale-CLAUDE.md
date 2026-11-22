# Claude Code Configuration - RuFlo V3

## Rapportage naar de gebruiker (Always Enforced)

Antwoord in het Nederlands, in gewone taal. De gebruiker is geen programmeur —
techniek interesseert hem niet, de gevolgen wel. Kort, bondig, krachtig.

Na elke wijziging aan code of infrastructuur rapporteer je in deze vier blokjes:

1. **Wat er aan de hand was** — in één of twee zinnen, zonder jargon. Beschrijf
   het gevolg dat hij merkt, niet de technische oorzaak.
2. **Wat er nu veranderd is** — maximaal drie bullets, in gevolgen. Dus "nieuwe
   gebruikers krijgen nu echt 7 dagen", niet "insert faalt niet meer".
3. **Zekerheid: X%** — hoe zeker je bent dat het nu klopt, met in één zin waarom
   het geen 100% is. Wees eerlijk: niet-geteste code is nooit boven 80%.
4. **Actiepunten** — genummerd, alleen wat híj moet doen. Niets wat jij al deed.
   Staat er niets open, schrijf dan "Niets, klaar." Achter elk punt staat hoe hard
   het is en hoeveel tijd het hém kost, zodat hij ziet wat hij zonder schade kan
   laten liggen: `[NU, 2 min]` (wachten kost vandaag klanten of geld),
   `[DEZE WEEK, 10 min]` (wordt een probleem, alleen niet vandaag),
   `[OOIT, 5 min]` (er gaat niets stuk als het nooit gebeurt), `[OVERSLAAN]`
   (genoemd voor de volledigheid, advies is niet doen).

Deze vier blokjes gelden voor elk antwoord aan hem, niet alleen na een wijziging.
Veranderde er niets, laat blokje 2 dan weg in plaats van het op te vullen.

Geen codeblokken tenzij hij iets moet plakken of draaien. Bestandsnamen en
regelnummers alleen als hij er zelf moet kijken. Geen uitweidingen over hoe je
het hebt opgelost.

Nooit een gedachtestreepje of los streepje als leesteken, niet in deze rapportage
en niet in teksten die hij naar buiten stuurt. Splits de zin, of gebruik een komma,
dubbele punt of punt. Streepjes binnen woorden en in bestandsnamen mogen gewoon.
In mail ook nooit opmaaktekens, want die gaat als platte tekst de deur uit en dan
komen sterretjes er letterlijk in te staan.

## Kort en zelf regelen (Always Enforced, Daniel 30-10-2026)

Houd de vier blokjes, maar maak ze kort. Een heel bericht past op één scherm: blokje 1 en
2 samen hooguit vijf regels, zekerheid in één zin, geen uitleg over hoe je iets deed.

Streef er altijd naar het 1000% zelf te regelen: zelf testen (browser, scripts, de
mail-koppeling), zelf repareren, zelf nameten, voor je iets bij hem neerlegt. Bij de
actiepunten staat alleen wat alleen hij kan: inloggen of betalen als hijzelf, een beslissing,
iets naar buiten sturen, een upload naar de Chrome Web Store. Een actiepunt dat jij ook
had kunnen doen is een fout van jou.

Is het eindresultaat onduidelijk en niet zelf te vinden, gebruik dan de skill
`interview-daniel` (alleen vragen als een verkeerde gok duur is).

## Zekerheid boven aannemelijkheid (Always Enforced)

Nooit stoppen bij "waarschijnlijk goed". Elke reparatie is aantoonbaar, niet
aannemelijk. Daniel verkoopt zekerheid door aan zijn klanten: zegt hij "het is
opgelost" en het is het niet, dan kost dat hem de klant, niet jou.

Voordat je een reparatie meldt:

1. Bewijs de oorzaak. Vind je iets wat de klacht zou kunnen verklaren, zoek dan
   door tot je het mechanisme kunt aanwijzen.
2. Meet wat het echte systeem doet in plaats van erover te redeneren. Schattingen
   en doorgerekende schaalregels hebben hier nog nooit geklopt. Meet de zwaarste
   echte situatie, niet een kleine en dan vermenigvuldigen.
3. Draai de echte code, niet je beschrijving ervan.
4. Doe de voor-en-na-proef. Haal de oude versie erbij en laat die onder dezelfde
   omstandigheden falen, anders weet je alleen dat de nieuwe code werkt en niet
   dat ze iets repareert.
5. Wat je niet kon meten schrijf je met zoveel woorden op als openstaand punt, niet
   verstopt in een percentage.
6. Wantrouw je eigen lege uitkomsten. Een meting die "leeg" of "nul" zegt is eerst
   een reden om te controleren of de meting zelf klopte.

## Zuinig met tokens (Always Enforced)

Elke ronde stuurt het hele gesprek opnieuw mee, dus het aantal beurten bepaalt de
kosten, niet de moeilijkheid van de taak. Een verspilde beurt kost net zoveel als
een nuttige, en Daniels limiet is de rem op wat er af komt.

- Batch alles wat niet van elkaar afhangt in één bericht. Dat is de grootste
  besparing die er is.
- Lees gericht. Eerst zoeken waar het staat, dan alleen dat stuk lezen. Nooit een
  groot bestand in zijn geheel openen omdat het antwoord er ergens in staat.
- Lees nooit twee keer hetzelfde. Een bestand dat je net bewerkte niet opnieuw
  openen om te controleren.
- Geen sleepnet-zoekopdrachten over hele mappen zonder uitsluitingen.
- Lange commando's in de achtergrond, één keer op wachten, nooit pollen met sleep.
- Geen subagents tenzij Daniel erom vraagt. Die beginnen koud en leiden alles
  opnieuw af wat je al weet.
- Klaar is klaar. Geen extra controleronde, documentatie, changelog of opmaakronde
  die niet gevraagd is.

Dit gaat nooit boven zekerheid. De zuinigheid zit in hoe je iets uitzoekt, niet in
of je het uitzoekt.

## Waar het echte geheugen staat (Always Enforced)

De losse geheugenbestanden onder `~/.claude/projects/.../memory/` hangen aan één
account en zijn voor de tweede ontwikkelaar onzichtbaar. De overdraagbare kopie
staat in de omnivaleur-repo en geldt voor al Daniels projecten, niet alleen voor
omnivaleur:

- `~/Documents/omnivaleur/docs/kennisbank.md` is de les: wat je moet weten om
  dezelfde fout niet nog eens te maken.
- `~/Documents/omnivaleur/docs/team-notes.md` is het dagboek: wat er wanneer
  gebeurde en waarom, inclusief afspraken over mensen en rollen.

Leer je iets dat ook op een ander account of een andere machine moet gelden, schrijf
het dan als geheugenbestand in
`~/.claude/projects/-Users-Danie-Documents-omnivaleur/memory/`, draai daarna
`python3 scripts/export_kennisbank.py` in die repo, en laat het committen. Alleen
lokaal opslaan betekent dat het verdwijnt zodra hij op een ander account werkt.

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files

## File Organization

- NEVER save to root folder — use the directories below
- Use `/src` for source code files
- Use `/tests` for test files
- Use `/docs` for documentation and markdown files
- Use `/config` for configuration files
- Use `/scripts` for utility scripts
- Use `/examples` for example code

## Project Architecture

- Follow Domain-Driven Design with bounded contexts
- Keep files under 500 lines
- Use typed interfaces for all public APIs
- Prefer TDD London School (mock-first) for new code
- Use event sourcing for state changes
- Ensure input validation at system boundaries

### Project Config

- **Topology**: hierarchical-mesh
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

## Build & Test

```bash
# Build
npm run build

# Test
npm test

# Lint
npm run lint
```

- ALWAYS run tests after making code changes
- ALWAYS verify build succeeds before committing

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit .env files or any file containing secrets
- Always validate user input at system boundaries
- Always sanitize file paths to prevent directory traversal
- Run `npx @claude-flow/cli@latest security scan` after security-related changes

## Concurrency: 1 MESSAGE = ALL RELATED OPERATIONS

- All operations MUST be concurrent/parallel in a single message
- Use Claude Code's Task tool for spawning agents, not just MCP
- ALWAYS batch ALL todos in ONE TodoWrite call (5-10+ minimum)
- ALWAYS spawn ALL agents in ONE message with full instructions via Task tool
- ALWAYS batch ALL file reads/writes/edits in ONE message
- ALWAYS batch ALL Bash commands in ONE message

## Swarm Orchestration

- MUST initialize the swarm using CLI tools when starting complex tasks
- MUST spawn concurrent agents using Claude Code's Task tool
- Never use CLI tools alone for execution — Task tool agents do the actual work
- MUST call CLI tools AND Task tool in ONE message for complex work

### 3-Tier Model Routing (ADR-026)

| Tier | Handler | Latency | Cost | Use Cases |
|------|---------|---------|------|-----------|
| **1** | Agent Booster (WASM) | <1ms | $0 | Simple transforms (var→const, add types) — Skip LLM |
| **2** | Haiku | ~500ms | $0.0002 | Simple tasks, low complexity (<30%) |
| **3** | Sonnet/Opus | 2-5s | $0.003-0.015 | Complex reasoning, architecture, security (>30%) |

- Always check for `[AGENT_BOOSTER_AVAILABLE]` or `[TASK_MODEL_RECOMMENDATION]` before spawning agents
- Use Edit tool directly when `[AGENT_BOOSTER_AVAILABLE]`

## Swarm Configuration & Anti-Drift

- ALWAYS use hierarchical topology for coding swarms
- Keep maxAgents at 6-8 for tight coordination
- Use specialized strategy for clear role boundaries
- Use `raft` consensus for hive-mind (leader maintains authoritative state)
- Run frequent checkpoints via `post-task` hooks
- Keep shared memory namespace for all agents

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

## Swarm Execution Rules

- ALWAYS use `run_in_background: true` for all agent Task calls
- ALWAYS put ALL agent Task calls in ONE message for parallel execution
- After spawning, STOP — do NOT add more tool calls or check status
- Never poll TaskOutput or check swarm status — trust agents to return
- When agent results arrive, review ALL results before proceeding

## V3 CLI Commands

### Core Commands

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `init` | 4 | Project initialization |
| `agent` | 8 | Agent lifecycle management |
| `swarm` | 6 | Multi-agent swarm coordination |
| `memory` | 11 | AgentDB memory with HNSW search |
| `task` | 6 | Task creation and lifecycle |
| `session` | 7 | Session state management |
| `hooks` | 17 | Self-learning hooks + 12 workers |
| `hive-mind` | 6 | Byzantine fault-tolerant consensus |

### Quick CLI Examples

```bash
npx @claude-flow/cli@latest init --wizard
npx @claude-flow/cli@latest agent spawn -t coder --name my-coder
npx @claude-flow/cli@latest swarm init --v3-mode
npx @claude-flow/cli@latest memory search --query "authentication patterns"
npx @claude-flow/cli@latest doctor --fix
```

## Available Agents (60+ Types)

### Core Development
`coder`, `reviewer`, `tester`, `planner`, `researcher`

### Specialized
`security-architect`, `security-auditor`, `memory-specialist`, `performance-engineer`

### Swarm Coordination
`hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`

### GitHub & Repository
`pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

### SPARC Methodology
`sparc-coord`, `sparc-coder`, `specification`, `pseudocode`, `architecture`

## Memory Commands Reference

```bash
# Store (REQUIRED: --key, --value; OPTIONAL: --namespace, --ttl, --tags)
npx @claude-flow/cli@latest memory store --key "pattern-auth" --value "JWT with refresh" --namespace patterns

# Search (REQUIRED: --query; OPTIONAL: --namespace, --limit, --threshold)
npx @claude-flow/cli@latest memory search --query "authentication patterns"

# List (OPTIONAL: --namespace, --limit)
npx @claude-flow/cli@latest memory list --namespace patterns --limit 10

# Retrieve (REQUIRED: --key; OPTIONAL: --namespace)
npx @claude-flow/cli@latest memory retrieve --key "pattern-auth" --namespace patterns
```

## Quick Setup

```bash
claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
npx @claude-flow/cli@latest daemon start
npx @claude-flow/cli@latest doctor --fix
```

## Claude Code vs CLI Tools

- Claude Code's Task tool handles ALL execution: agents, file ops, code generation, git
- CLI tools handle coordination via Bash: swarm init, memory, hooks, routing
- NEVER use CLI tools as a substitute for Task tool agents

## Support

- Documentation: https://github.com/ruvnet/claude-flow
- Issues: https://github.com/ruvnet/claude-flow/issues
