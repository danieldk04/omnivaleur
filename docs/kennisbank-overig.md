# Kennisbank overig: geheugen uit Daniels andere mappen

Automatisch gemaakt door `scripts/export_kennisbank.py`. Per kopje staat de map waaruit de les komt. Bevat Downloads (hier schrijft de nachtelijke Dreaming-taak), Documents, crosslist-eu en de andere projecten.

---

## -Users-Danie / project_zenbtw

*03-06-2026*

ZENbtw (voorheen Kortax) is een BTW-dashboard voor marketplace-verkopers (Vinted, Etsy, Shopify).

**Live site:** https://github.com/danieldk04/zenbtw — GitHub Pages, statische HTML-app in `app/index.html`

**Lokale Next.js versie:** `/Users/Danie/Sites/kortax-dashboard` — DDD-architectuur met React/Next.js, aparte `main` branch, NIET verbonden met de live site

**Why:** De live site is een standalone HTML/JS app. De lokale Next.js versie is een refactor-project. Fiscale fixes worden op beide codebases toegepast.

**How to apply:** Wijzigingen aan de live site: checkout branch van `origin/main` → edit `app/index.html` → push naar `origin/main`. Wijzigingen aan de Next.js versie: werk direct op lokale `main` branch.

**Cruciale fiscale logica (toegepast juni 2026):**
1. BTW-berekening: marktplaatsprijzen zijn BRUTO (consumentenprijzen). Formule: `bruto × (tarief / (100 + tarief))` — NIET `netto × tarief`
2. KOR-basis splitsing: EU-afstandsverkopen ≤ €10.000 tellen mee voor NL KOR-teller (€20k); daarboven niet (OSS-regime)
3. KOR-grens: €20.000 (NL), OSS-drempel: €10.000 (EU-breed), EU-KOR: €100.000

---

## -Users-Danie / feedback_push_to_live

*03-06-2026*

After every code change, push to the live site via git.

**Why:** User explicitly requested "push gelijk naar de live site altijd vanaf nu."

**How to apply:**
- Live site is at https://github.com/danieldk04/zenbtw (GitHub Pages)
- The live HTML app lives in `app/index.html` on the `main` branch of that repo
- After editing `app/index.html`, commit and push: `git push origin <branch>:main`
- The local Next.js project (`/Users/Danie/Sites/kortax-dashboard`) is a separate codebase on the `main` branch — changes there do NOT auto-sync to the live GitHub repo
- To push live: work on a branch from `origin/main`, apply changes, then `git push origin <branch>:main`

---

## -Users-Danie-Documents / nexus-signal-db

*15-07-2026*

Project: "Prediction Market Trading bot" (Nexus Pro) in ~/Documents. De "Bot" is een aandelen-scorer (evolution_engine.py + tier1_scanner.py + nexus_scoring.py), draait via GitHub Actions → data.json → pro.html dashboard. GEEN Alpaca/multi-asset ondanks een eerdere briefing daarover; Daniel koos expliciet voor uitbreiden van de bestaande structuur.

Doel van Daniel: bot die op basis van technische + fundamentele indicatoren + social sentiment (Twitter/Reddit/Bluesky) uiteindelijk gekalibreerde "hoge confidence" entry-signalen geeft om echt op te traden, met een database van backtests die hij onthoudt.

Gebouwd (juli 2026): src/signal_store.py (SQLite data/nexus_signals.db), src/backfill_signals.py, src/signal_cli.py. Kalibratie = empirische beat-benchmark-rate van vergelijkbaar cohort + Wilson-ondergrens als eerlijke confidence. "90%-signaal" = Wilson-ondergrens ≥0.90 én n≥100.

**Belangrijke bevinding:** backfill (11k rijen, 6jr) toont dat technisch momentum ALLEEN geen edge heeft tegen SPY (44-51% beat-rate = muntworp). Edge moet komen uit combineren met fundamentals + sentiment + regime. Backfill kan alleen technische features historisch reconstrueren; fundamentele/sentiment-lagen vullen zich met live signalen.

**Why:** Daniel vroeg om "90%+ zekerheid" — als quant heb ik dat herkaderd naar gekalibreerde Wilson-confidence, want geen eerlijk systeem belooft 90% winkans per trade. Hij ging akkoord met die framing.

Stap 2 gedaan: Bluesky toegevoegd aan social_sentiment.py (+ combined_bull_ratio), signal_logger.py schrijft live kandidaten weg met fundamentals+sentiment, update_outcomes.py realiseert uitkomsten, beide ingehaakt in tier1_scan.yml (Tier 3.5/3.6) + nexus_signals.db meegecommit. LET OP: StockTwits+Bluesky zijn 403 in de sandbox (egress-block), werken in CI.

Stap 4 gedaan: calibration.py met confidence_for_signal() (multi-factor cohort + auto-verruiming) en discover_edges() (combinaties, Bonferroni-drempel). CLI: signal_cli.py discover/confidence.

**Bevinding stap 4:** op technische+regime features ALLEEN (backfill) haalt GEEN combinatie de multiple-testing-lat. Milde suggestieve edges op 63d-horizon: mom_mid+high_rvol 57%, vcp-setups 53-56% beat-rate (z~2, niet significant na Bonferroni z-lat 3.32). Plafond ~54-57%, ver van 90%. Bevestigt: rijke laag (fundamenteel+sentiment, alleen in live-data) is nodig om edges over de streep te duwen. 63d-horizon veelbelovender dan 21d.

Stap 5 gedaan: signal_logger.py schrijft confidence per kandidaat naar data.json (horizon 63d); pro.html Bot-tab toont confidence-badge (_confBadge) op elke cand-card met Wilson%, beat-rate, n, gem. rendement. Visueel geverifieerd in browser.

Stap 6 gedaan: confidence-gating in evolution_engine.py, STANDAARD UIT. Env-schakelaars: CONFIDENCE_GATING=1 (aan), MIN_CONFIDENCE (default 0.55), CONFIDENCE_SIZE_SCALING=1, CONFIDENCE_HORIZON=63. Gate blokkeert trades onder drempel (fail-open bij geen historie); size-scaling 0.6x→1.0x tussen drempel en 0.75 confidence. confidence_at_entry opgeslagen in trade-record.

**Alle 6 roadmap-stappen af.** Nu wachten tot live fundamenteel+sentiment-laag rijpt (weken/maanden) voordat gating aangezet moet worden — op technisch-only data haalt niets de 45-55% lat (bewust). Toekomst: gating aanzetten zodra rijke data genoeg gerijpte waarnemingen heeft; evt. confidence_at_entry tonen in open-posities tabel (bot-body in pro.html).

**Why:** Daniel wilde traden op de bot; gating is de veiligheidsklep maar mag pas aan als de data betrouwbaar is. Zie [[nexus-scoring-recalibration]].

---

## -Users-Danie-Documents-Claude-AXONGEARShopify-Editor / shopify_workflow

*23-06-2026*

## Auto-push workflow for Shopify theme

**Rule:** After every edit to files in the Shopify theme directory (`/Users/Danie/Documents/Claude AXONGEARShopify Editor`), automatically run the push command to push changes live immediately.

**Why:** User wants all changes to go live instantly without manual intervention.

**How to apply:**
- After using Edit tool on any `.liquid`, `.css`, `.js` files in the theme
- Store details: store = `axongear-2.myshopify.com`, theme_id = `199013728598`
- Command: `cd "/Users/Danie/Documents/Claude AXONGEARShopify Editor" && shopify theme push --store axongear-2.myshopify.com --theme 199013728598 --allow-live`

## BELANGRIJK: Nooit content overschrijven

**Rule:** ALTIJD eerst het bestand lezen met Read tool voordat je iets aanpast. Gebruik ALTIJD de Edit tool (gerichte aanpassing) en NOOIT de Write tool op bestaande `.liquid` bestanden — Write overschrijft het hele bestand inclusief alle video-URLs en content die de gebruiker zelf heeft ingevuld via de Shopify admin.

**Why:** De gebruiker voegt zelf video-URLs en content toe via de Shopify admin. Als ik een bestand volledig herschrijf met Write, verdwijnen alle ingevulde URLs en data. Dat is onacceptabel.

**How to apply:**
- Gebruik Read → daarna Edit (alleen het gedeelte dat moet veranderen)
- Gebruik NOOIT Write op bestaande theme bestanden
- Schema-wijzigingen (settings/blocks) zijn veilig via Edit, want die overschrijven geen admin-data
- Bij twijfel: vraag de gebruiker wat er nu live staat voordat je iets aanpast

---

## -Users-Danie-Documents-Handige-Scripts-Mac / videoknipper-draait-als-launchagent

*01-09-2026*

`dashboard.py` in `~/Documents/Handige Scripts Mac` draait sinds 01-09-2026
permanent als LaunchAgent `com.danie.videoknipper` (RunAtLoad en KeepAlive, gestart
met `--stil`). Er is dus geen Terminal-venster dat je kunt sluiten.

**Why:** ik zei Daniel op 01-09-2026 eerst dat hij het venster moest sluiten en het
`.command`-bestand opnieuw moest dubbelklikken. Dat klopte niet, en het is de reden
dat wijzigingen in `videoknipper.py` anders pas werken na een herstart van de Mac.

**How to apply:** na elke wijziging aan `videoknipper.py` of `dashboard.py`:

```
launchctl kickstart -k gui/$(id -u)/com.danie.videoknipper
```

Daarna even wachten en controleren dat http://127.0.0.1:8777/ weer antwoordt; het
opstarten duurt een paar seconden omdat hij eerst Downloads, Bureaublad en Films
doorzoekt. Kijk vooraf of er geen ffmpeg draait, want een herstart breekt een
lopende montage af.

De volledige beschrijving van hoe de knipper werkt staat onder de kop `videoknipper`
in de kennisbank, zie [[kennisbank-en-team-notes]].

---

## -Users-Danie-Documents-Handige-Scripts-Mac / geen-gedachtestreepjes

*01-09-2026*

Geen gedachtestreepje of los streepje als leesteken, niet in rapportage aan Daniel
en niet in teksten die hij naar buiten stuurt. Gevraagd op 09-08-2026, staat in de
omnivaleur-kennisbank.

**Why:** het valt hem op en het leest voor hem als machinetekst. Hij wil dat zijn
mails als mensenwerk overkomen.

**How to apply:** splits de zin, of gebruik een komma, dubbele punt of punt.
Streepjes bínnen woorden en in bestandsnamen mogen gewoon. Geldt ook voor de vier
rapportageblokjes uit `/Users/Danie/CLAUDE.md`. In mail nooit opmaaktekens zoals
sterretjes voor vet, want die mail gaat als platte tekst de deur uit.

Zie ook [[kennisbank-en-team-notes]].

---

## -Users-Danie-Documents-Handige-Scripts-Mac / bewijzen-niet-aannemen

*01-09-2026*

Daniel wil nooit meer hoeven vragen of iets naar 100% zekerheid kan. De standaard
is: elke reparatie is aantoonbaar, niet aannemelijk. Komt uit de
omnivaleur-kennisbank (01-09-2026) en geldt op zijn verzoek ook hier.

**Why:** hij verkoopt zekerheid door aan zijn klanten. Zegt hij "het is opgelost"
en het is het niet, dan kost dat hem de klant, niet mij. Een percentage in mijn
rapportage is voor hem geen nuance maar een risico dat hij doorgeeft.

**How to apply**, vóór ik een reparatie meld:

1. Bewijs de oorzaak, stop niet bij een plausibele. Vind ik iets wat de klacht zou
   kúnnen verklaren, dan zoek ik door tot ik het mechanisme kan aanwijzen.
2. Meet wat het echte systeem doet in plaats van erover te redeneren. Op 01-09-2026
   bleek de videoknipper vijf keer trager dan de notitie beweerde, puur omdat die
   schatting was doorgerekend vanaf een korte testvideo.
3. Draai de echte code, niet mijn beschrijving ervan.
4. Doe de voor-en-na-proef. De oude versie erbij halen en onder dezelfde
   omstandigheden laten falen, anders weet ik alleen dat de nieuwe code werkt en
   niet dat ze iets repareert.
5. Wat ik niet kon meten staat er met zoveel woorden bij, als openstaand punt, niet
   verstopt in een percentage.

Let ook op stille meetfouten in mijn eigen gereedschap. Op 01-09-2026 concludeerde
ik dat al zijn geheugenmappen leeg waren, terwijl `ls -la` in werkelijkheid de
mapnaam als optie las omdat die met een streepje begint. De conclusie was fout, niet
de map. Een uitkomst die "leeg" of "nul" zegt is een reden om te controleren of de
meting zelf klopte.

Zie ook [[lean-tokengebruik]] en [[kennisbank-en-team-notes]].

---

## -Users-Danie-Documents-Handige-Scripts-Mac / lean-tokengebruik

*01-09-2026*

Daniel wil dat ik zo lean en efficiënt mogelijk met tokens en zijn limiet omga.
Vastgelegd in de omnivaleur-kennisbank op 01-09-2026, en door hem op diezelfde dag
ook voor deze map van toepassing verklaard.

**Why:** elke API-ronde stuurt het hele gesprek opnieuw mee, dus het aantal beurten
bepaalt de kosten, niet de moeilijkheid van de taak. Een verspilde beurt kost hem
net zoveel als een nuttige. Zijn limiet is de rem op wat we samen af krijgen.

**How to apply:**

1. Batch alles wat niet van elkaar afhangt in één bericht. Meerdere lees-, zoek- en
   bewerkacties tegelijk. Dat is de grootste besparing die er is.
2. Lees gericht, niet ruim. Eerst `grep -n` of `sed -n 'x,yp'`, niet een heel
   bestand openen omdat het antwoord er ergens in staat.
3. Nooit twee keer hetzelfde lezen. Een bestand dat ik net bewerkte niet opnieuw
   openen om te controleren; de bewerking had gefaald als het misging.
4. Geen sleepnet-zoekopdrachten over hele mappen zonder uitsluitingen.
5. Lange commando's in de achtergrond, één keer op wachten, nooit pollen met sleep.
6. Geen subagents tenzij Daniel erom vraagt. Die beginnen koud en leiden alles
   opnieuw af wat ik al weet.
7. Klaar is klaar. Geen extra controleronde, geen documentatie, changelog of
   opmaakronde die niet gevraagd is.

Dit staat náást [[bewijzen-niet-aannemen]] en gaat er niet boven. Zuinig zijn mag
nooit betekenen dat een aanname niet gemeten wordt. De zuinigheid zit in hóe ik het
uitzoek, niet in óf ik het uitzoek.

---

## -Users-Danie-Documents-Handige-Scripts-Mac / kennisbank-en-team-notes

*01-09-2026*

Daniels echte kennisbank staat in de omnivaleur-repo en reist via git mee naar
elk account en elke machine:

- `/Users/Danie/Documents/omnivaleur/docs/kennisbank.md` is de les: wat je moet
  weten om dezelfde fout niet nog eens te maken. Nieuwste bovenaan, per onderwerp
  een kop.
- `/Users/Danie/Documents/omnivaleur/docs/team-notes.md` is het dagboek: wat er
  wanneer gebeurde en waarom, inclusief afspraken over mensen en rollen.

Beide gelden ook buiten omnivaleur. Ze bevatten onder andere hoe Daniel wil dat er
gewerkt en gerapporteerd wordt, en er staat ook een hoofdstuk over de videoknipper
in deze map. Daniel verwees er zelf naar op 01-09-2026 toen hij vroeg de werkwijze
van de tweede ontwikkelaar over te nemen.

**Waarom dit ertoe doet:** de geheugenbestanden onder `~/.claude/projects/.../memory/`
hangen aan één account. De tweede ontwikkelaar ziet die niet. Wat blijvend moet
gelden hoort daarom in die repo-bestanden thuis.

**Hoe toe te passen:** heb je iets geleerd dat ook voor de andere ontwikkelaar of
een andere machine geldt, schrijf het dan als geheugenbestand in
`~/.claude/projects/-Users-Danie-Documents-omnivaleur/memory/`, draai daarna
`python3 scripts/export_kennisbank.py` in de omnivaleur-repo en laat het committen.
Alleen in deze lokale map schrijven betekent dat het verdwijnt zodra hij op een
ander account werkt.

Zie ook [[lean-tokengebruik]], [[bewijzen-niet-aannemen]] en
[[geen-gedachtestreepjes]]: die drie komen uit die kennisbank.

---

## -Users-Danie-Documents-Handige-Scripts-Mac / mac-opslag-setup

*12-08-2026*

Daniels MacBook M2 heeft 245 GB en zat op 12 augustus 2026 vol (14 GB vrij),
waardoor CapCut niet meer kon exporteren.

De structurele ruimtevreters op deze Mac:
- `~/.pm2/logs/` en `~/.openclaw/logs/` lopen ongelimiteerd vol (waren samen 10 GB).
  Deze groeien altijd terug — legen met `: > bestand`, niet verwijderen, want
  draaiende processen schrijven erin door.
- `~/.npm/_npx` (was 5 GB) en Chrome's `OptGuideOnDeviceModel` (4 GB).
- Chrome heeft 8 profielen, samen ~12 GB. **Niet opschonen** — expliciet zo gewild.
- CapCut-cache in `~/Movies/CapCut/User Data/Cache` (~2 GB): **niet aanraken**,
  projecten kunnen er media uit halen.

Het opruimscript hiervoor staat in `~/Documents/Handige Scripts Mac/` als
"💾 SCHIJFRUIMTE VRIJMAKEN - dubbelklik.command".

Cloud-archief: zakelijke Google Drive (danielsclothingshop@gmail.com), gemount op
`~/Library/CloudStorage/GoogleDrive-danielsclothingshop@gmail.com/Mijn Drive`
in streaming-modus. Daarin staat "Mac Archief" met genummerde mappen
(01 Video, 02 Studie, 03 Documenten, 04 Afbeeldingen, 05 Audio,
06 Installatiebestanden, 07 Zip, 08 Overig, 09 Persoonlijk,
10 Mappen uit Downloads). Nieuwe archivering hoort in deze structuur.

---

## -Users-Danie-Documents-Prediction-Market-Trading-bot- / project_etf_dashboard

*20-08-2026*

Sinds 20-08-2026 heeft het NEXUS-dashboard een ETF-tab. Methodiek gekozen door
Daniel: kwaliteit dominant (60/40), universum ~136 UCITS-ETF's in 23 thema's.

Kwaliteit = de negen selectiecriteria van Marc Langeveld (probeleggen /
De Aandeelhouder) toegepast op de bedrijven ÍN het fonds, gewogen naar hun
gewicht. Thema-opzet en "rendement vs. verwachte marktgroei" komen van het
De Lange Termijn-dashboard.

**Why:** Daniel wil expliciet kwaliteitsbedrijven boven momentum, management
voorop. Momentum is bij hem timing, geen koopreden.

**How to apply:** wijzigingen aan de scorelogica horen in `src/etf_quality.py`
(criteria) en `src/etf_engine.py` (weging); het universum in
`src/etf_universe.py`. Zie ook [[project-nexus]].

---

## -Users-Danie-Documents-Prediction-Market-Trading-bot- / feedback_always_push

*02-07-2026*

Always push git commits to remote for this repo without asking for confirmation first.

**Why:** User explicitly said "push zelf altijd voor mij" (always push it yourself for me) — they don't want to be asked every time before a push.

**How to apply:** For the NEXUS Market Terminal / Prediction Market Trading bot repo, after committing changes (or when a hook auto-commits), proactively run `git push` without asking. Note: this repo has automation (GitHub Actions + local hooks) that frequently pushes auto-update commits (ticker updates, snapshots) directly to `origin/main`, so `git push` can be rejected with "fetch first" — in that case, fetch, merge (resolving conflicts by combining both sides' features when they overlap, e.g. dashboard chart logic), then push again. Don't ask the user to resolve conflicts manually unless they are substantive/ambiguous.

---

## -Users-Danie-Documents-Prediction-Market-Trading-bot- / project_nexus

*14-05-2026*

Building a two-tier investor analysis system called "NEXUS MARKET TERMINAL" (v3 investor mode).

**Architecture:**
- Tier 1 (`tier1_scanner.py`): scant 400 tickers, filtert op ROE >12%, voegt ROIC, P/FCF, 5-jaars CAGR, analistentarget toe. Top 20 naar data.json.
- Tier 2 (`tier2_analyser.py`): Claude Sonnet analyse van top 10 met nieuws-sentiment, refresh na 7 dagen.
- Stock Lookup (`stock_lookup.py`): deep dive op enkel aandeel, opgeslagen in watchlist sectie van data.json.
- Evolution Engine (`evolution_engine.py`): investor modus — 10 posities, 15% allocatie, 25% take-profit, -8% stop-loss.
- Memory layer: `memory.json` slaat lessons op per sector.

**GitHub Actions:**
- `tier1_scan.yml` — 08:00 + 19:00 UTC op werkdagen: Tier1 → Tier2 → Evolution Engine
- `live_ticker.yml` — elke 15 min: live koersen bijwerken
- `stock_lookup.yml` — handmatig: individueel aandeel zoeken (inputs.ticker)

**Data in tier1_scanner.py:**
- ROIC, P/FCF ratio, 5-jaars omzet/winst CAGR, analistendoelkoers en upside %
- Universe: S&P 500 + Nasdaq-100 + NL stocks + fallback lijst bij scraping fout

**data.json schema:**
- top_candidates[].tier2 = { analysis, last_run, model, news_used }
- watchlist[] = individuele lookups met dezelfde tier2 structuur

**Scan stopte:** bot heeft niet gedraaid van 11 april t/m 14 mei 2026. Oorzaak: waarschijnlijk Wikipedia scraping kapot (tabel index Nasdaq-100). Nu gefixed met multi-index fallback.

**Investor-modus instellingen (v3):**
- MAX_TRADES=10, ALLOC=10-15%, TAKE_PROFIT=25%, STOP_LOSS=-8%, VIX_BLOCK=40

**Why:** User wil zelf-lerende investeerder (niet trader) die individuele kansen ziet op basis van nieuws, jaarrekeningen en 5-jaar data.
**How to apply:** Volgende sessies: dashboard (pro.html) upgraden om watchlist te tonen + ROIC/P/FCF zichtbaar maken.

---

## -Users-Danie-Documents-Prediction-Market-Trading-bot- / user_profile

*03-04-2026*

Dutch-speaking user (communicates in Dutch). Building a sophisticated automated trading analysis system. Has an HTML concept/mockup for a dashboard called "NEXUS MARKET TERMINAL". Interested in:
- Python automation (yfinance, GitHub Actions)
- AI-driven market analysis (Claude as the reasoning engine)
- Self-improving systems (memory + feedback loops)
- Free/low-cost infrastructure (GitHub Actions, free APIs)

Appears to have a clear vision of the architecture; wants coaching/guidance alongside implementation.

---

## -Users-Danie-Documents-ZENbtw / project_blog_slug_growth_agent

*26-06-2026*

De `growth-agent` voegt keywords toe aan `keywords.json` (queue) **zonder `slug`-veld**. `generate-blog.js` gebruikte `item.slug` direct → blog werd opgeslagen als `blog/undefined.html` en URL werd `/blog/undefined`.

**Fix (2026-06-26):** `slugify(keyword)` helper in generate-blog.js leidt nu de slug af uit het keyword (lowercase, accenten weg, max 6 woorden) als `item.slug` ontbreekt, en persisteert die terug naar keywords.json.

Tegelijk: `max_tokens` stond op 10000 (te laag, blogs werden afgekapt) → terug naar 16000 + `stop_reason==='max_tokens'` detectie die afgekapte output opnieuw genereert. Zie [[project_anthropic_sdk_node_fetch]].

---

## -Users-Danie-Documents-ZENbtw / project_anthropic_sdk_node_fetch

*26-06-2026*

GitHub Actions workflows (auto-blog, post-to-social) faalden met `ERR_STREAM_PREMATURE_CLOSE` / "Premature close" bij Anthropic API streaming calls.

**Oorzaak:** `@anthropic-ai/sdk@0.39.0` bundelt `node-fetch@^2.6.7`, dat lange streaming-responses niet aankan op Node 24 (de workflow default via setup-node@v4 node-version '24'). Connectie valt mid-stream weg; retries lossen niets op want het is een library-incompatibiliteit, geen netwerk-hapering.

**Fix (commit 6b2e31e, 2026-06-26):** upgrade naar `@anthropic-ai/sdk@^0.106.0` — gebruikt Node's native fetch, geen node-fetch meer. Lockfile mee-committen want workflow gebruikt `npm ci`.

**Let op:** post-to-social.js heeft mogelijk dezelfde streaming-fix nodig (bestond niet lokaal). Met SDK-upgrade is de root cause hoe dan ook weg.

---

## -Users-Danie-Documents-ZENbtw / feedback_blog_factual_accuracy

*11-06-2026*

Never write incorrect KOR rules in blogs or app copy. The user caught serious factual errors that were being spread across multiple blog posts.

**Correct KOR rules (as of 2026):**
- Overschrijding heeft GEEN terugwerkende kracht. Omzet vóór de grensoverschrijding blijft vrijgesteld.
- BTW reken je per direct vanaf de transactie die €20.000 doorbreekt.
- Wachttermijn na afmelding = rest lopende kalenderjaar + volledig volgend kalenderjaar. NIET 3 jaar (verouderd).
- Vrijwillige afmelding = per eerstvolgende kwartaal. Gedwongen afmelding (overschrijding) = per direct.

**Why:** User found these errors being published as fact on zenbtw.nl, risking misinformation spread to users who rely on the tool for tax decisions. Also a reputational/legal risk.

**How to apply:** When writing or reviewing any blog post or UI copy about KOR:
1. Never say "terugwerkende kracht" in the context of KOR overschrijding
2. Never say "3 jaar uitsluiting" — it's rest-of-year + next year
3. Always link to belastingdienst.nl as source for specific legal claims
4. The generate-blog.js prompt now includes a FEITELIJKE NAUWKEURIGHEID section with these rules — keep it updated if rules change

---

## -Users-Danie-Documents-crosslist-eu / project_rebrand_crosslist

*11-07-2026*

On 2026-07-11 a trademark/name claim arrived (party behind Crosslist / crosslist.com objects to the "CrossList EU" name). Daniel asked to strip the brand name from the whole live product.

**Done:** replaced all visible brand text "CrossList EU" / "Crosslist" (234 occurrences across dashboard, frontend, blog templates, emails, extension) with the temporary placeholder **`ListHub`**. Committed + pushed to main → Railway (see [[feedback_push_railway]]).

**Deliberately left untouched** (would break the site — only the brand *name* was in scope):
- Domain `crosslisteu.com` (OAuth callbacks, canonical URLs, API) — Daniel's DNS/infra task
- Code identifiers: `CrosslistValidationError`, `openCrosslist`/`doCrosslist`/`doBulkCrosslist`, `CROSSLIST_UNIVERSAL_REQ`, `backend/services/crosslist.py`
- Filenames: `Logo Crosslist EU.png`, `author-daniel-crosslisteu.jpg`
- Generic verb "cross-list"/"crosslisting"

**Still exposes the old name (needs Daniel):**
- The logo image `Logo Crosslist EU.png` visually renders the "CrossList EU" wordmark — needs a new logo (he supplies own images, see [[feedback_manual_images]])
- The domain itself

**Custom domain crosslisteu.com was detached via DNS (cowork) on 2026-07-11.** Live site now served from the temporary Railway URL: `https://crosslisteu-production.up.railway.app/` (verified rendering clean "ListHub" branding). A new custom domain will be attached to this later. The logo image (`frontend/logo.png`) is just an infinity-loop icon, NOT a wordmark — so no old-name exposure there; the "ListHub" text next to it is a separate span.

**Still hardcoded to old domain `crosslisteu.com` in `backend/config.py`** (breaks OAuth/webhooks until the new domain is live): `shopify_redirect_uri`, `ebay_webhook_url`, `app_url`, `gsc_site_url`. Swap these to the NEW domain in one pass once Daniel picks it (also update redirect URIs in Shopify/eBay dashboards + Google Search Console).

**FINAL NAME = Omnivaleur** (chosen 2026-07-11). "Omni" (list everywhere) + "valeur", deliberately sharing the `valeur` root with Daniel's existing reseller brand **Revaleur** (shown on homepage as social proof) → coherent brand family. Placeholder `ListHub` → `Omnivaleur` applied across all 226 occurrences, committed + pushed, verified live on the Railway URL (nav, hero, meta all render "Omnivaleur"; logo icon + colour palette unchanged as instructed). Rebrand is technically complete.

**Note:** Revaleur references on the site are intentional (his other brand) — do NOT rename those.

**DONE 2026-07-11 (later):** New domain `omnivaleur.com` is live (apex serves the whole app incl. /blog, /login.html, /app.html, /analytics — there is NO app. subdomain; `app.omnivaleur.com` does not resolve). Swapped all `crosslisteu.com`/`app.crosslisteu.com` → `omnivaleur.com` in code (config OAuth redirects, webhooks, app_url, gsc_site_url, canonical/OG, sitemap, robots, indexnow). Marketing dashboard is now **https://omnivaleur.com/analytics?token=crosslist-mrktng-2026** (token is Railway env var `analytics_dashboard_token`, unchanged — still contains "crosslist"; Daniel can change it in Railway if wanted).

**Existing blog articles rebranded in the DB:** the 17 published `content_pages` rows (Supabase) had "CrossList EU" in title/body/json_ld — updated all display fields via one-off script (backup at scratchpad/content_pages_backup.json). Verified live: blog index + articles show "Omnivaleur", zero "CrossList EU". Future articles already generate as Omnivaleur (generator.py rebranded).

**Left as-is deliberately:** blog **slugs / URL paths** still contain `crosslisteu` (e.g. `/vs/crosslisteu-vs-vendoo`) — renaming breaks indexed URLs, `related_slugs` internal links and SEO; would need 301 redirects. SEO `primary_keyword` fields (lowercase) untouched. eBay RuName `ebay_redirect_uri` untouched (eBay-side token).

**Chrome extension** fully rebranded (name, host permissions, popup, webapp_sync → omnivaleur.com); fresh `extension.zip` rebuilt & committed; only leftover is the verb "crosslisten" in the manifest description (kept). JS all `node --check` clean. Daniel still must upload the zip + fix store-listing copy in the Chrome Web Store dashboard.

**Comparison slugs renamed + 301 redirects (done 2026-07-11):** 4 comparison pages renamed in DB `crosslisteu-vs-{vendoo,list-perfectly}` → `omnivaleur-vs-...` (slug + translation_of; `intent_key` is a Postgres GENERATED column so it auto-follows the slug). `scripts/content_keywords.json` queue updated (keywords, slugs, url_paths, incl. the not-yet-generated `omnivaleur-vs-zenlister`). 301 redirect map added in `backend/api/content.py` (`_COMPARISON_SLUG_REDIRECTS`) for both `/vs/{slug}` and `/{lang}/vergelijking/{slug}`. Verified live: old slugs 301 → new, new 200. Backup: scratchpad/content_slugs_backup.json.

**Analytics token:** local `.env` set to `analytics_dashboard_token=omnivaleur-mrktng-2026`. Production value is a Railway env var Claude CANNOT change — **Daniel must set `analytics_dashboard_token=omnivaleur-mrktng-2026` in Railway** → new dashboard URL `https://omnivaleur.com/analytics?token=omnivaleur-mrktng-2026`. Until then the live token stays `crosslist-mrktng-2026`.

**Metadata fixes (done 2026-07-11, final audit):** earlier passes had left damage that a full audit caught & fixed: (1) og:image / twitter:image / JSON-LD `logo` in index/register/marketplaces.html pointed to URL-encoded `Logo%20Crosslist%20EU.png` (missed because encoded) → now `logo.png`; (2) DB `article_json_ld` on all 17 pages had `Logo Omnivaleur.png` (a file that never existed — brand-replace mangled the old filename) → fixed to `logo.png`; (3) json_ld `@id`/`url` + 4 `body_html` internal links still had old comparison slugs → fixed. (4) author avatar storage object `author-daniel-crosslisteu.jpg` copied to `author-daniel-omnivaleur.jpg` (additive, old kept) + 3 template refs updated. Extension manifest description rebranded. Final live sweep: home, /blog, EN+NL articles, marketplaces, pricing all CLEAN of crosslisteu/CrossList EU; all images HTTP 200. **No damage.** Manifest & extension.zip rebuilt.

**Still on Daniel (external, no code):** set the Railway analytics token; update OAuth redirect URIs in Shopify + eBay dashboards to omnivaleur.com; add omnivaleur.com in Google Search Console; upload extension.zip + fix Chrome store listing; verify EUIPO trademark for "Omnivaleur".

---

## -Users-Danie-Documents-crosslist-eu / project_blog_model_routing

*10-07-2026*

Blog content generator (backend/content/) model routing, chosen 2026-07-10 to cut cost ~75-80% (was all Opus 4.8):
- Article generation → `claude-sonnet-5` (GEN_MODEL in generator.py)
- Translation EN→NL → `claude-haiku-4-5-20251001` (TRANSLATE_MODEL)
- Keyword planner → Haiku (keyword_planner.py)
- max_tokens stays 8000 (Daniel wants max content depth; it's a ceiling not a target)

**Gotcha (root cause of a real bug):** Sonnet 5 / the 5-family return a **thinking block as content[0]** by default. Old code read `message.content[0].text` → grabbed the thinking block → empty "Lege Claude-respons" failures. Fixed via `_extract_text()` which joins all text-type blocks. Any future model swap must keep this text-block extraction, never index content[0] blindly.

Cost: ~$0.04-0.06 per article (Opus was ~$0.25). Billing runs on API credits at console.anthropic.com (NOT claude.ai usage credits — separate wallet). See [[feedback_verify_thoroughly]], [[project_content_pipeline]].

---

## -Users-Danie-Documents-crosslist-eu / feedback_language

*08-07-2026*

All frontend copy, backend code, comments, labels, buttons, and error messages must be in **English**.

**Why:** CrossList EU targets international/EU sellers, not just Dutch speakers. Dutch in the UI feels local and unprofessional.

**Exception:** The actual listing content posted TO Marktplaats and 2dehands (titles, descriptions, categories) stays in Dutch — that's a feature, not a bug, and is a key USP to highlight.

**How to apply:** When writing any UI text, buttons, banners, nav items, pricing copy — write in English. Never translate UI to Dutch.

**Extended to the programmatic blog/content system** (added 2026-07-03, see [[project_content_pipeline]]): every blog article is generated in English by default. Every article — every pillar, every region, not just Marktplaats/2dehands — additionally gets an auto-translated Dutch companion page (broadened 2026-07-08 after Daniel flagged that comparison/other articles were missing an NL version entirely; `needs_dutch_translation()` in `backend/content/generator.py` now always returns `True`). Implemented as a second linked row, not a language swap of the primary page, with a toggle UI (`{% if language_switch %}` in content_page.html) so a reader can switch either direction. A one-off backfill (`scripts/backfill_nl_translations.py`) generated NL companions for pages published before the broadening. All non-content UI strings that render on a content page (author box, FAQ heading, CTA, "Key takeaways" label) must also be conditionally translated based on `page.language == 'nl'` — this was missed once (author box shipped English-only on a Dutch page) and had to be retrofitted. Check this whenever adding new UI text to content_page.html/blog_index.html.

---

## -Users-Danie-Documents-crosslist-eu / project_notion_documentation_logs

*08-07-2026*

Two living Notion pages under "📚 Strategic Docs" (page id `017a1b02-0432-4b23-b344-d837a4f22b7d`), created 2026-07-08:

- **🛠️ Engineering Log** — page id `397b0954-fb72-816a-9067-c7f3b91670f6`. Technical changelog, newest entry at top. Format per entry: date + short title, Probleem, Fix, Bestanden, Geverifieerd.
- **📢 Build in Public Log** — page id `397b0954-fb72-81e9-85b7-d72933ff0e30`. X/Reddit build-in-public strategy, posts, and lessons learned (e.g. the corrected "nothing handled Vinted" claim).

A daily scheduled task, `daily-notion-documentation-sync` (20:08 local, see `/Users/Danie/.claude/scheduled-tasks/daily-notion-documentation-sync/SKILL.md`), autonomously diffs recent git history and prepends new entries when there's real signal — it skips days with nothing substantive rather than writing filler.

**Why:** Daniel wants this documented automatically, without prompting each time — see [[feedback_autonomous_notion_docs]].

**How to apply:** When starting work in this repo, these are the pages to check for prior context/decisions before assuming something hasn't been tried. When ending a session with real work done, prepend to the relevant log rather than creating new pages — don't fragment the documentation across multiple similar pages.

---

## -Users-Danie-Documents-crosslist-eu / feedback_autonomous_notion_docs

*08-07-2026*

At the end of any session where real engineering work happened (code changes, bug fixes, pipeline changes) or build-in-public content/strategy was created, proactively add a dated entry to the relevant Notion log — don't wait to be asked.

- [[project_notion_documentation_logs]] for the two log pages and their format.
- A daily scheduled task ("daily-notion-documentation-sync", 20:08 local) also does this autonomously by diffing recent git history — so within-session logging and the scheduled task are belt-and-suspenders, not duplicative effort. If the scheduled task already covered something, no need to re-log it in-session.

**Why:** Daniel said "ja. ik wil dat je dit allemaal zelf autonoom en automatisch gaat documenteren" — he explicitly does not want to have to prompt for this every time. He wants a future session (or himself) to understand what was built/decided without digging through git log or chat history.

**How to apply:** Only log entries with real signal — new features, bug fixes, architecture decisions, content-pipeline changes, X/Reddit posts or strategy shifts, corrected assumptions. Skip trivial changes (typos, formatting-only, config noise). Never write a hollow "nothing happened" entry. Only ever prepend new entries — never rewrite or delete existing ones. Keep the Dutch tone/format consistent with existing entries (title, Probleem, Fix, Bestanden, Geverifieerd).

---

## -Users-Danie-Documents-crosslist-eu / project_refresh_functions

*05-07-2026*

CrossList EU has two listing-refresh strategies (extension-driven, Vinted).

**Refresh 1 = "content" (content_refresh): WORKS — verified live 2026-07-05** against Vinted's real edit DOM (member daniel0164 / 35817973, item 9318598048).
- Re-orders photos to trigger a Vinted re-index, WITHOUT changing price/title/description.
- **Never moves the first (main) photo** (user rule): moves the 2nd photo to the end; only accepts the result if order changed AND photo #1 unchanged. Needs 3+ photos, else fails honestly.
- Vinted edit-page DOM: photos live in `[data-testid="media-upload-grid"]`, each draggable tile is `.u-cursor-grab` wrapping `[data-testid="image-wrapper-N"]`. Save button = `[data-testid="upload-form-save-button"]`. Vinted uses POINTER-based sortable (not native HTML5 drag). Photo src URL hashes change per page load — verify order via stable photo `id`s from `/api/v2/wardrobe/{userId}/items`.
- On failure it throws → `/jobs/{id}/error` → cooldown+quota rolled back (see relist.py rollback_refresh). Dashboard prompt spells out exactly what happens.

**Refresh 2 = "relist"**: delete + delayed recreate (45min–4h jitter). Delete half FIXED + verified live 2026-07-05 (non-destructive check, nothing deleted):
- Real delete-listing control on the item VIEW page = exact `[data-testid="item-delete-button"]` ("Delete"), can render briefly 0x0/hidden then lay out. Opens confirm dialog with `item-delete-confirmation-button` ("Confirm and delete") + `item-delete-cancelation-button` ("Cancel"). Vinted also shows a "About Your Privacy" consent dialog that can co-exist — match delete dialog by its own testids, not a generic [role=dialog].
- CRITICAL bug that was fixed: old findDeleteEntryPoint matched Vinted's per-photo remove buttons (`media-select-grid-delete-button-N`, testid contains "delete") via the edit-page fallback → would have DELETED A PHOTO not the listing. Now excludes media-select/grid-delete/image-wrapper testids, removed the edit-page fallback, targets item-delete-button only.
- Recreate half = the existing proven fillForm/submitListing list flow.

**Refresh 2 delete VERIFIED end-to-end via the real extension flow 2026-07-05**: triggered relist from dashboard (POST /api/listings/refresh strategy=relist) on a live+tracked item (Beige Mango Trousers, Vinted 9244983899, item 9cb804ae). Extension claimed the delete job → done; CrossList listing → delisted; Vinted wardrobe confirmed the listing gone (and no collateral photo deletion). Recreate ("create") job correctly scheduled ~45min later. Note: only listings with an ACTIVE listing record in CrossList (platform_listing_id matching a live Vinted item) are dashboard-relistable — some live Vinted items (e.g. 9318598048) are not tracked/active so can't be relisted via the dashboard.

Trigger relist via authenticated `apiFetch(API+"/api/listings/refresh", {item_id, platform:"vinted", strategy:"relist"})` from the crosslisteu.com origin. Map Vinted platform_listing_id → CrossList item_id via `/api/listings/?platform=vinted`. Extension needs the user logged into the dashboard + reloaded with current code.

**Full relist recreate VERIFIED end-to-end 2026-07-05** (Beige Mango Trousers, item 9cb804ae): forced the scheduled create early via new `POST /jobs/reschedule-now {item_id,platform}`, extension republished on Vinted (new listing 9331465721, all 10 photos). Two recreate bugs found + fixed along the way:
1. `submitListing` (shared.js) only found Marktplaats's `place-listing-submit-button`; Vinted's submit is `[data-testid="upload-form-save-button"]` ("Upload"/"Save", NOT the "Save draft" = `upload-form-save-draft-button`). Fixed to fall back to it.
2. Background auto-complete (`tabs.onUpdated` in background.js) only matched m-prefixed Marktplaats/2dehands ids, so Vinted's plain-digit `/items/{id}` never matched → create/relist jobs stuck "claimed", listing never marked active (JOB_DONE also lost to Vinted's post-Upload navigation tearing down the content script). Fixed to match `/items/{digits}` for vinted.

Reconcile a stuck-claimed create job manually by POSTing the true plid to `/api/jobs/{jobId}/complete` {platform_listing_id, platform_listing_url}. Both fixes are extension code → require the user to reload the unpacked extension.

Console noise seen on Vinted pages (`chrome-extension://invalid/` ERR_FAILED, Meta Pixel currency warning) is NOT from our code — it's Vinted's own Meta Pixel + orphaned content scripts after reloading the unpacked extension. Fix = refresh open tabs after reloading the extension.

---

## -Users-Danie-Documents-crosslist-eu / feedback_manual_images

*05-07-2026*

The content pipeline (see [[project_content_pipeline]]) does **not** generate featured images automatically anymore, even though `backend/content/images.py` (Gemini + Pollinations fallback) still exists in the codebase.

**Why:** AI-generated images were inconsistent quality (one attempt showed a distorted/"stretched" person, a wrong-topic scene came from a keyword-substring matching bug) and the user prefers to design his own, same workflow as his Revaleur store.

**How to apply:** `pipeline.py`'s `_save_page_row()` leaves `featured_image_url` as whatever was already on the row (never regenerates it on update). Don't resurrect the auto-generation call in `pipeline.py` unless explicitly asked again.

**UPDATE 2026-07-05 — uniform gradient featured graphic (supersedes per-article images on the page):** Daniel asked for one clean, uniform look everywhere instead of mixed/broken custom images. Both `frontend/templates/blog_index.html` (card `.post-thumb`) and `content_page.html` (hero `.featured-image-wrap`) now render a CSS-only graphic: brand gradient (`--blue`→`--mint`) + radial light overlay + a white `∞` glyph + the category label (pillar A=Platform comparison, B=Reseller guide, C=Vs. competitor) + a small rule (hero only). `featured_image_url` is NO LONGER used for the on-page visual (still used for `og:image`). So there's nothing to upload per article — every post looks consistent automatically. `POST /api/content/set-image` still exists but only affects og:image now.

---

## -Users-Danie-Documents-crosslist-eu / project_weekly_marketing_report

*05-07-2026*

Weekly marketing report emailed every Sunday 08:00 (Europe/Amsterdam) to `owner_email`, plus a live `/analytics` dashboard. Built 2026-07-04.

**Files:** `backend/services/analytics_report.py` (assembler + `send_weekly_report` scheduler entrypoint + `render_email`), `backend/services/ga4.py` (GA4 Data API reader, soft-fails until configured), `backend/services/search_console.py` (`query_window` helper added for this-week-vs-last-week), `backend/scheduler.py` (cron job `weekly_marketing_report`), `backend/api/content.py` (`GET /analytics?token=`, `POST /api/analytics/send-report?token=`), `frontend/templates/analytics_dashboard.html`.

**Data sources:** SEO via Search Console (already connected — top pages, rising queries, week-over-week by two date windows, no storage needed). Traffic/channel attribution via GA4 (not yet connected — reuses GSC OAuth client, needs `ga4_property_id` + `ga4_refresh_token` with analytics.readonly scope). Signups via Supabase `auth.admin.list_users` (best-effort).

**Env vars (config.py):** `ga4_property_id`, `ga4_refresh_token`, `analytics_dashboard_token` (protects dashboard; empty = 401). Requires `google-analytics-data` pip package (added to requirements.txt).

**GA4 + GSC now BOTH live (2026-07-05):** GSC auth_ok=true, property `sc-domain:crosslisteu.com`; GA4 configured (property 544205472, tag G-FERDR093F7), data fills over days. Dual-scope OAuth refresh token reuses the Google Ads OAuth client (Railway has only GOOGLE_ADS_* vars). Search Console API had to be enabled in Google Cloud project 997344215790.

**Dashboard expanded (2026-07-05) — decision-worthy content analytics:** ga4.py added `traffic_sources`, `social_posts`, `platform_of` (maps sessionSource substrings → TikTok/Instagram/YouTube/Pinterest/Reddit/LinkedIn/Facebook/X/Threads). analytics_report.py added `_social_section` (per-platform sessions/newUsers/conversions/conv-rate + WoW), `_blog_categories` (`_category_of` buckets URLs into Homepage/Vergelijkingen/Reseller-tools/Crosslisting-guides/Blog-index/Overig), richer `_patterns` (best & most-valuable social platform, strongest category, high-impression-low-CTR opportunity). Dashboard has social-platform table, best-posts (UTM) table, blog-per-category table, and a **UTM-linkbouwer** (client-side JS: platform+dest+content+campaign → `?utm_source=..&utm_medium=social&utm_campaign=..&utm_content=..`). Post-level social attribution ONLY works once Daniel shares UTM-tagged links (GA4 can't guess individual TikTok/Reel/Pin; in-app browsers strip referrer).

**sign_up conversion event (2026-07-05):** register.html fires `gtag('event','sign_up', {method, utm_source, utm_campaign, utm_content})` on successful registration (backend auth.py is Supabase-only, no server GA4 hit). Verified end-to-end via browser automation: test account danieldekoning66+ga4test@gmail.com, dataLayer + GA4 Realtime showed `sign_up 1`. STILL PENDING: Daniel must mark `sign_up` as a key event in GA4 (Beheer→Gebeurtenissen, star it — only appears in that admin list a few hours after firing; there is NO "create key event by name" button in this GA4 version, only the star + the wrong "Gebeurtenis maken" synthetic-event dialog). A ScheduleWakeup was set to auto-check & star it. GA4 property 544205472 lives under account 400015242 (login dkresellacademy@gmail.com, Browser 2); NOT under the AXONGEAR/DK-Socials account (Browser 1). Conv% + valuable-platform columns need ~24-48h Data-API processing after the key event is set.

**On-platform social scraping via Apify (2026-07-05):** `backend/services/social_scrape.py` — per-platform adapters (TikTok=clockworks/tiktok-profile-scraper, Instagram=apify/instagram-profile-scraper→latestPosts, YouTube=grow_media/youtube-channel-video-scraper, Pinterest=apify/pinterest-scraper best-effort), parallel ThreadPoolExecutor, normalized schema (views/likes/comments/shares/saves/date/text/url/duration/engagement_rate), `weekly(start,end)` filters to week + `_group_by_content` aggregates the SAME post across platforms (Daniel posts identical content everywhere) + `patterns()`. Validated live on @crosslisteu (TikTok+IG returned real per-post data; account is new so views 0-3). Wired: build_report(include_social=True) for Sunday email; dashboard has on-demand button → `GET /api/analytics/social?token=` (slow scrape kept off page-load). Metricool API was the cleaner option but is gated behind a paid plan upgrade, so Apify chosen. Config: `apify_token` + `social_tiktok/instagram/youtube/pinterest` handles in config.py. STILL PENDING: Daniel must add `APIFY_TOKEN` env var in Railway (free apify.com account, ~$5/mo credit covers weekly runs); until then social section shows 'niet gekoppeld'. Optional Supabase table `analytics_snapshots` (week_start, week_end, seo_clicks, seo_impressions, signups, payload jsonb) for long-term month-over-month memory — `_store_snapshot` fails silently until it exists. No UTM capture on signup yet (auth.py register uses Supabase `sign_up`; could pass utm via options.data metadata). See [[project_content_pipeline]].

---

## -Users-Danie-Documents-crosslist-eu / reference_blog_automation_sources

*03-07-2026*

Two sibling projects on this machine were used as the model for CrossList EU's programmatic blog system (see [[project_content_pipeline]]):

- `~/Documents/axongear-ai-blog-automation/` — Gemini+Pollinations image-gen fallback pattern (`src/imageService.js`), GSC-driven keyword gaps.
- `~/Documents/revaleur-blog/` — marker-delimited Claude output parsing (`===BODY===` style, more robust than JSON for HTML-with-quotes bodies), retro-pass internal linking with blocked-ranges detection, `DRY_RUN` env-var guard pattern, GitHub Actions daily cron with queue-file commit-back.

Both run on Shopify (their CMS/hosting is free with the platform); CrossList EU has no CMS, so its version is a from-scratch FastAPI + Jinja2 SSR system instead, but keeps the same prompt-architecture and cron-automation ideas.

---

## -Users-Danie-Documents-crosslist-eu / feedback_verify_thoroughly

*03-07-2026*

When fixing bugs on crosslisteu.com (especially the content pipeline / marketing pages), Daniel explicitly said to keep going "totdat je zeker weet dat dit allemaal klopt" (until you're sure it's all correct) after multiple rounds of reported bugs that turned out to be real (missing `/marketplaces` route, wrong featured image, security hole in an admin endpoint, footer not sticky, author-box float collapsing, untranslated UI strings).

**Why:** several early "done" reports turned out to be wrong or incomplete once actually checked live — e.g. claiming a nav fix worked before the deploy had actually landed, or not noticing an admin endpoint had no auth until testing it directly.

**How to apply:**
- After any fix, do a real `httpx`/`curl` check against the live URL (or a local server render) — don't infer correctness from the diff alone.
- If a live check doesn't show the fix yet, assume deploy lag (see [[project_content_pipeline]]'s Railway gotcha) and wait/recheck rather than declaring success prematurely.
- When testing admin/write endpoints, actively check the negative case too (e.g. "does this reject without the secret?") — don't just check the happy path.
- Sweep for the same bug class elsewhere before calling a fix complete (e.g. when one page's logo gradient was missing a CSS class, check all pages using the same partial, not just the one reported).

---

## -Users-Danie-Documents-crosslist-eu / project_content_pipeline

*03-07-2026*

CrossList EU has a programmatic SEO/GEO content system (built 2026-07-03, modeled loosely on the AXONGEAR/Revaleur blog-automation projects in `~/Documents/`) that publishes comparison and niche articles automatically.

**Why:** the user wants organic-search and AI-answer-engine (ChatGPT/Perplexity/Google AI Overviews) traffic, competing directly with crosslist.com's blog. Runs as a daily GitHub Actions cron so it grows without manual work.

**Architecture:**
- `backend/content/research.py` — free DuckDuckGo-HTML scrape of the real top-3 organic results per keyword, extracts their H1/H2/H3 so the generator can find a genuine content gap instead of repeating competitors.
- `backend/content/generator.py` — Claude Opus writes the English article (quick-answer blockquote, H2-question headings, 3-5 key takeaways, FAQ), citing only from a hand-verified `AUTHORITY_SOURCES` whitelist (every URL HTTP-checked before being added — never let the model invent a citation URL, several guessed ones 404'd). `translate_to_dutch()` is a separate call that translates an already-generated article, preserving HTML/links, for the Marktplaats/2dehands Dutch companion.
- `backend/content/pipeline.py` — orchestrates research → generate → (maybe) translate → internal-linking → save. `_url_path(language, pillar, slug)` is the single source of truth for URL building (see [[feedback_language]] for the language rule, and the URL-scheme section below).
- `backend/api/content.py` — FastAPI routes, all server-side rendered via Jinja2 (`frontend/templates/`), no client JS for bots. Two admin endpoints (`/api/content/generate`, `/api/content/set-image`) require an `X-Admin-Secret` header matching `SECRET_KEY` — these were briefly unauthenticated in production and a live test call accidentally overwrote a page's image before the auth was added; always confirm auth is live before treating these as safe to call externally.
- `frontend/templates/_nav.html`, `_footer.html`, `_chrome_style.html` — shared partials so every content page and the blog index have byte-identical nav/footer/branding (a `grad-text` class was missing from these partials early on, making the logo render flat instead of the blue→mint gradient everywhere else — always diff new page-chrome against `frontend/index.html`'s actual nav/footer markup when adding a page).
- `scripts/generate_content.py` + `scripts/content_keywords.json` — CLI/queue-file that the GitHub Actions cron (`.github/workflows/content-blog.yml`, daily 08:00 UTC) runs. `backend/content/keyword_planner.py` auto-generates new keyword ideas via Claude when the queue is empty, grounded strictly in CrossList EU's real supported platforms (Marktplaats, 2dehands, Vinted, eBay, Etsy, Shopify) — never invents unsupported platform combos.
- No AI-generated featured images anymore (see [[feedback_manual_images]]).

**URL scheme (language-based, not region-based):** English is the default, no prefix — pillar A is `/crosslisting/{slug}`, pillar B is `/reseller-tools/{slug}`. A translated page gets a language prefix AND a language-appropriate folder — Dutch pillar A is `/nl/crosslisten/{slug}` (note: `crosslisting` in English, `crosslisten` in Dutch — genuinely different folder words, not just a prefix). The Dutch row's DB `slug` column carries an internal `-nl` suffix (e.g. `marktplaats-naar-vinted-nl`) to stay unique from the English row's `slug`; `_url_path()` strips that suffix for the public URL. The Dutch slug's *wording* is independent of the English slug (translated separately, e.g. English `marktplaats-to-vinted` vs Dutch `marktplaats-naar-vinted`) — `run_pipeline(..., nl_slug=...)` takes an explicit override for this, don't just suffix the English slug.

**Blog index** (`/blog`, region-neutral, `blog_index.html`) only lists primary (non-translation) rows — a Dutch companion is reachable only via the language toggle on its English page, never as its own index card, to avoid looking like duplicate content.

**Database:** `content_pages` table, see `schema.sql` — `intent_key` (region:pillar:slug, generated+unique) is the cannibalization guard; `language`/`translation_of` columns added later for the EN/NL pairing; `takeaways`/`article_json_ld` columns also added after the initial migration. RLS was on by default when the table was first created via Supabase SQL editor and had to be explicitly disabled to match every other table in this project (none of them use RLS).

**Known gotcha:** this repo has an auto-commit-and-push hook that fires on every individual file edit and triggers a Railway deploy per commit — with many rapid edits this creates a build queue, and Railway's healthcheck-retry-per-commit behavior means a single broken intermediate commit (e.g. a dependency added in one commit but used starting in an earlier one) can block the queue for 5-15+ minutes before the fix lands. Always verify a fix landed live with a fresh HTTP check rather than assuming a push = instantly live; if it's still stale after ~2 minutes, wait longer rather than assume something is broken.

---

## -Users-Danie-Documents-crosslist-eu / feedback_push_railway

*29-06-2026*

Always push changes to live (git commit + git push) after every coding session or set of changes.

**Why:** Railway is connected to the git repo and auto-deploys on push. The user expects changes to be live immediately after being made.

**How to apply:** At the end of every turn where code was changed, run git add + git commit + git push. Don't wait for the user to ask.

---

## -Users-Danie-Documents-crosslist-eu / project_competitive_gaps

*28-06-2026*

Top pain points from forums/competitor research, ranked by frequency × impact:

**P1 — Auto-delist & double selling**
Vendoo/LP miss sales on secondary channels; require browser open. CrossList EU uses server-side webhooks for API platforms and background tab scraping for consumer platforms.
**How to apply:** sold detection via `checkSoldListings()` in background.js runs every 10 min. Keep this solid.

**P2 — Vinted bot detection / instant bans**
Same photos across platforms trigger duplicate scanner. Too-fast uploads trigger rate limits.
**Why:** Vinted AI hashes images; exact match = ban.
**How to apply:** Need EXIF strip + pixel jitter on photo upload, and safe pacing queue (min 45s between Vinted uploads). Not yet implemented.

**P3 — Marktplaats silent expiry + 2dehands HTML crash**
Listings expire silently on Marktplaats. 2dehands only allows 7 HTML tags (`<u> <em> <ul> <li> <p> <strong> <br>`), crashes on rich text.
**How to apply:** Add HTML sanitizer before sending description to 2dehands. Add auto-relist job for Marktplaats expiry.

**P4 — "Million tabs" crash + no mobile**
LP opens new tab per product in bulk → browser crash. Mobile apps incomplete.
**How to apply:** CrossList EU's single-tab job queue architecture already solves this.

**P5 — Wrong category mapping, maat conversie, data truncation**
AI miscategorizes; US→EU size not converted; condition details truncated = buyer claims.
**How to apply:** Zero-truncation already fixed (removed 500-char MyMemory cap). Size conversion and category mapping still manual.

**P6 — Price margin calculator**
Platforms have different commission rates (Poshmark 20%, eBay 13.25%, Vinted 0%). Tools copy price 1:1.
**How to apply:** Dashboard feature: net profit input → auto-calculate sell price per platform based on commission %.

---

## -Users-Danie-Documents-revaleur-blog / revaleur-seo-status

*10-09-2026*

Context: Daniel wil dat Revaleur (Shopify, vintage designer kleding) zo hoog mogelijk scoort in Google, NL en EN. Aanleiding was analyse van concurrent thrifttale.com, die #1 staat op "vintage ralph lauren" puur op domeinleeftijd, exacte on-page match en zwakke concurrentie, ondanks lage voorraad.

Gedaan op 2026-09-10 (via `scripts/seo.mjs`, zie [[shopify-admin-api-access]]):

- Alle 23 collecties: Google titel, meta-omschrijving (teruggebracht van 600-930 naar ~150 tekens) en pagina-tekst herschreven, EN + NL. Streepjes eruit (huisregel), machinevertaling-artefacten opgeschoond, merknaam-mistranslation "Herwaarderen" teruggezet naar Revaleur.
- Alle 314 producten: 10 ontbrekende Google titels, 10 ontbrekende omschrijvingen, 368 alt-teksten op afbeeldingen, 19 NL meta-velden. Templated (`{titel} | Revaleur` + standaardzin).

Niet gedaan / bewust uitgesteld:
- Structurele opschoning (apart voorstel, Daniel keurt eerst goed): dubbele merkcollectie `ralph-lauren` (150) vs `ralph-lauren-for-men` (111), `sold-out` en `designer-vintage-mystery-boxes` op noindex, junk 404-collectieslugs (`ralph-lauren-1271477`, `gemini-watermark-removed` etc.), menu heeft "Ralph Lauren" + "Ralph Lauren for men" dubbel.
- Extra talen voor "breder Europa" (Duits, Frans): moet Daniel eerst aanzetten in Shopify Instellingen > Talen + app Translate & Adapt. Daarna kan `seo.mjs` vertalingen pushen.
- Blog: niet aangeraakt, draait via eigen dagelijkse automatisering.
- Prijzen, thema/ontwerp, afrekeninstellingen: afgesproken niet aanraken.

Openstaand actiepunt Daniel: Client Secret van de "Revaleur SEO" app roteren (stond meerdere keren in chat).

---

## -Users-Danie-Documents-revaleur-blog / shopify-admin-api-access

*10-09-2026*

Revaleur draait op Shopify. Winkel: `ywqad3-xb.myshopify.com` (revaleur.com), plan Basic, standaardtaal `en`, tweede taal `nl` met vertalingen.

De winkel is gemigreerd naar het nieuwe **Dev Dashboard**. De oude "custom app met shpat_ reveal-once token" bestaat niet meer in het winkelbeheer. Toegang loopt nu via een Dev Dashboard app met **client-credentials grant**:

- App: "Revaleur SEO" (los van de blog-app, die apart blijft draaien voor de dagelijkse blog).
- `.env` in de repo-root (staat onder een Read/Write deny-rule, dus alleen Daniel kan hem vullen):
  - `SHOPIFY_STORE=ywqad3-xb.myshopify.com`
  - `SHOPIFY_CLIENT_ID=...`
  - `SHOPIFY_CLIENT_SECRET=...`
- Token ophalen: `POST https://{store}/admin/oauth/access_token` met form body `grant_type=client_credentials&client_id=..&client_secret=..`. Antwoord `{access_token, scope, expires_in:86399}`. Token is 24u geldig, daarna opnieuw ophalen.
- Scopes op de app: `write_products`, `write_content`, `write_translations`, `write_online_store_pages`, `write_online_store_navigation`. Geen `read_locales`, dus `shopLocales` query geeft access-denied (gebruik `availableLocales` of vraag Daniel).

Gereedschap: `scripts/seo.mjs` (helper met token-cache in os.tmpdir, `rest()`, `gql()`, commands `audit` / `apply-collections <file>` / `apply-products`). Vertalingen via `translationsRegister` met digest uit `translatableResource.translatableContent[].digest`; collectie-keys zijn `title`, `body_html`, `meta_title`, `meta_description`.

Zie [[revaleur-seo-status]] voor wat er inhoudelijk al gedaan is.

---

## -Users-Danie-Documents-revaleur-blog / feedback_auto_push

*29-06-2026*

Always push to remote after committing changes. The user does not want to push manually.

**Why:** User prefers a fully automated flow — commit + push without extra steps.

**How to apply:** After every `git commit`, immediately run `git pull --rebase origin main && git push origin main`. Do this automatically without asking for confirmation.

---

## -Users-Danie-Downloads / omnivaleur-social-reageren-routine

*23-11-2026*

Sinds begin nov 2026 draait de geplande taak `omnivaleur-social-reageren`: autonoom reageren op relevante threads van andere creators op X en Indie Hackers (zoals de Facebook-reactiebot, maar zonder tussenkomst). Mag per dag maximaal 5 accounts volgen waar hij op reageert. Building-in-public posts (Engels, X, Bluesky, Facebook, later Indie Hackers om warm te worden) schrijft Daniel zelf, de routine doet alleen reacties.

**Why:** Daniel wil 1000% autonoom, maar de veiligheidscontrole van geplande sessies blokkeert de Reply-klik als "externe schrijfactie". Een vaste Chrome-toestemming in ~/.claude/settings.json loste dit niet aantoonbaar op; de toestemmingsmodus van de geplande taak ("Alles toestaan") kan alleen Daniel in de app zetten.

**How to apply:** Meld bij problemen met deze routine eerst of de toestemmingsmodus van de taak op bypass staat. Nooit de blokkade omzeilen door zelf te plaatsen. Zie [[omnivaleur-facebook-outreach-grens]] en [[omnivaleur-groei-pivot-creators-okt-2026]].

**Update 9-11-2026:** Daniel wil 3 rondes per dag (ook op alle platforms, Indie Hackers ging naar 3 per dag) en wil dat de routine na dichtklappen of afsluiten van de laptop zelf weer verder gaat waar hij bleef, zonder dat hij iets doet. Bouw de planning dus zo dat gemiste rondes bij opstarten worden ingehaald.

**Update 23-11-2026:** X liet Daniel blokkeren omdat de bot twijfelde of hij een mens was. Eis van Daniel: X (en daarna Indie Hackers en Facebook) moet menselijk, toegestaan gedrag volgen en "1000% veilig" zijn tegen blokkades. Zoek eerst op wat humaan gedrag is en kijk bij IH en Facebook naar eerdere posts van Daniel voor de toon.

---

## -Users-Danie-Downloads / omnivaleur-facebook-outreach-grens

*23-11-2026*

Voor leadgen via Facebook-verkopersgroepen (bijv. eBay Resellers & Thrifters) geldt: geen advertenties, geen promotieposts (worden binnen een uur verwijderd, gezien als spam, en Facebook blokkeert accounts die snel in veel groepen posten/linken, vergelijkbaar risico als de eerdere Reddit-ban). Wat wel werkt: Daniels eigen profiel (nooit een bedrijfspagina) dat twee weken alleen helpt zonder pitch, en pas een opening pakt zodra iemand er zelf om vraagt. Cold DM's aan onbekenden werken niet: die komen in de "verzoeken"-map en worden nauwelijks gezien. Volgorde die wel werkt: publiek reageren en helpen → hij reageert terug → pas dan privé, of hij voegt zelf toe.

**Harde grens, bevestigd na herhaald aandringen (14-09-2026).** Daniel vroeg drie keer achter elkaar om een cloud-agent die zelfstandig namens hem in Facebook-groepen reageert ("doe het wel", ook na uitleg geweigerd). Geweigerd, en blijft geweigerd: een bot die zich zonder dat groepsleden het weten voordoet als Daniel is precies waarvoor die groepen bannen, en dat is wat het kanaal juist laat werken (mensen praten met een verkoper, niet met reclame).

**Wat wel gebouwd is, als het juiste alternatief.** Een Gemini Gem ("Facebook-brein") helpt Daniel of Monaim (Growth & Content-partner, zie [[omnivaleur-monaim-partnership]]) bij het schrijven van menselijk klinkende reacties. Instructie staat in `docs/facebook-brein.md` in de omnivaleur-repo, met `klantenservice-brein.md` uit Drive als los kennisbestand (blijft zo actueel zonder duplicatie). Daniel/Monaim plakt de post erin en plakt het antwoord terug op Facebook zelf; geen automatisering raakt Facebook aan.
- Anti-AI-detectieregels (2026): gelijke zinslengte is de grootste verklikker (belangrijker dan gedachtestreepjes), daarna rijtjes-van-drie, opsommingen, beleefde slotzin. Staan als harde regels in de Gem, plus een verboden-woordenlijst.
- **Taal-bug gevonden en gefixt (14-09-2026):** de Gem antwoordde in het Nederlands op een Engelse post, omdat de taalregel te diep in de instructie stond. Staat nu als allereerste regel bovenaan, plus een checklist die de Gem eerst langsloopt.
- Bevat ook verkoperskennis (rubrieken die een advertentie laten verwijderen, biedfunctie staat standaard aan, Vinted heeft geen archief, kleurnamen in de basisvorm) vertaald naar verkopertaal, expliciet zonder versienummers, bestandsnamen of klantnamen.

**Sinds 08-10-2026 ook als Claude Project.** Op Daniels eigen claude.ai staat nu een Project "Facebook-reactiebot", één-op-één gelijk aan dat van de tweede ontwikkelaar (post plakken, drie antwoorden in Daniels stijl terug, met een kennisbestand met productfeiten). Opdracht staat in de omnivaleur-repo en onder 05-10 in docs/team-notes.md. Zelfde regel: Daniel plakt zelf, niets raakt Facebook automatisch aan.

**How to apply:** vraagt Daniel opnieuw om volledige Facebook-automatisering (posten of lezen namens hem), verwijs naar deze afspraak in plaats van het gesprek opnieuw te voeren. Uitbreidingen aan het antwoord-hulpmiddel zelf (Gem, hotkey/klembord-tooltje dat een post kopieert en het antwoord klaarzet) mogen wel, want daar leest en plakt Daniel of Monaim nog altijd zelf.

**Update 23-11-2026:** Daniel gebruikt de Gemini Gem ("Facebook-brein") eigenlijk niet meer, hij updatet niet meer. Het brein (`docs/facebook-brein.md`) hoeft alleen bijgewerkt te worden als het voor Claude zelf nuttig is, niet meer voor de Gem. Zie [[garmin-watchdealer-gem]] voor een andere, losse Gem.

---

## -Users-Danie-Downloads / posts-volledig-in-chat-plakken

*22-11-2026*

Als Daniel zegt "plaats dit" of om een post vraagt (langere Indie Hackers post, reseller-post, build in public), zet de complete tekst gewoon in de chat.

**Why:** Hij kan eerdere berichten in een lang gesprek niet terugvinden en verwijzingen naar "de post van eerder" of een bestand werken niet voor hem (21-11-2026).

**How to apply:** Elke keer de volledige, plakklare tekst opnieuw tonen, ook als je hem eerder al schreef. Daniel publiceert zelf. Zie [[omnivaleur-community-posts-twee-per-dag]] en [[omnivaleur-social-reageren-routine]].

---

## -Users-Danie-Downloads / omnivaleur-community-posts-twee-per-dag

*21-11-2026*

Sinds 21-11-2026: Claude schrijft elke dag 2 posts (afwisselend per community, niet 4 want dat leest als spam). Daniel publiceert zelf, de bestaande reageerronde (3x per dag) controleert daarna de reacties. Posts voor Indie Hackers, Bluesky en X blijven door Daniel zelf geschreven (eigen lessen); Claude leert daarvan en beoordeelt in de rondes of crossposten naar Facebook zin heeft.

Stijlregels: geen dubbele punt in posttekst. Alles in de EU Resellers-groep in het Engels. Intro of uitleg waarom de groep bestaat alleen in de allereerste post, daarna niet meer. Niet telkens over Omnivaleur: afwisselen met oprechte menselijke verhalen, losser mag waar het past. Daniel studeert niet meer, Finance & Control is afgerond (niet meer als "student" neerzetten).

**Why:** Spam-risico bij te veel posts, en te veel pitch werkt averechts.
**How to apply:** Bij elke postronde 2 concepten met variatie in onderwerp en community, geen pitch-herhaling. Zie [[omnivaleur-facebook-groep-community]] en [[omnivaleur-social-reageren-routine]].

---

## -Users-Danie-Downloads / omnivaleur-webshop-export-import-en-ai-pakket

*20-11-2026*

Op 19-20 nov 2026 kwamen twee lijnen naar voren:
- Webshopeigenaren op andere platforms (Magento, eigen shop) kunnen niet via Shopify/WooCommerce koppelen. Daniel wil een uniforme werkwijze: de klant stuurt een export (CSV), Daniel geeft die aan Claude, die leest hem in als extra service en bouwt daarna een betrouwbare, subtiele importroute. Eerst de export van de eerste klant afwachten, dan bouwen.
- AI-pakket voor de gratis of zeer goedkope laag: meer dan titels en beschrijvingen per kanaal, een echt "wow"-pakket dat past bij de te-bouwen-lijst en klantverzoeken. Streven: features die in 100% van de niches werken. Claude pakt dit volledig autonoom op en rapporteert wat wel en niet werkte, met zo min mogelijk acties voor Daniel.

**Why:** Leads buiten Shopify/Woo haken nu af; AI-pakket moet de gratis laag aantrekkelijk maken.
**How to apply:** Check docs/te-bouwen.md voor de stand; zie [[omnivaleur-gevraagde-koppelingen]], [[omnivaleur-te-bouwen-lijst]], [[omnivaleur-light-plan]].

---

## -Users-Danie-Downloads / omnivaleur-onboarding-twee-minuten-en-betaling-automatisch

*19-11-2026*

Op 18-19 nov 2026 corrigeerde Daniel twee keer: (1) bij onboarding wil hij dat een nieuwe klant binnen 1-2 minuten een listing ziet en ziet hoeveel tijd het bespaart, niet dat de sessie in details verdwijnt; hij vroeg om kort antwoord of het echt voor zich spreekt en gegarandeerd goed gaat. (2) Als een klant betaalt (bijv. iemand die na een geblokkeerd proefaccount wil betalen) moet het account vanzelf weer opengaan, zonder dat Daniel of Claude het handmatig doet.

**Why:** Daniel zit in support-modus en elke handmatige stap of onduidelijke eerste ervaring kost klanten. Zie [[omnivaleur-onboarding-get-started]], [[omnivaleur-huidige-fase-klachten]] en [[omnivaleur-tijdsbesparing-realistisch]].

**How to apply:** bij onboarding-werk eerst het pad "aanmelding tot eerste listing in 2 minuten" toetsen, niet losse details. Bij betaal-/Stripe-flows controleren dat toegang automatisch terugkomt na betaling. Bij klantmails over Vinted-blokkade: zo zeker mogelijk formuleren, maar zonder valse garantie (zie [[omnivaleur-platform-geen-toestemming]]).

---

## -Users-Danie-Downloads / omnivaleur-tijdsbesparing-realistisch

*18-11-2026*

In het onboarding-/resultaatscherm stond "ongeveer 15 minuten met de hand" per advertentie en "11 items = 3 uur". Daniel (18-11-2026): "te gek, pak een realistischere inschatting".

**Why:** Opgeblazen besparing komt onbetrouwbaar over bij leken-resellers en raakt het vertrouwen; past bij [[kerngetallen-altijd-met-bron]].

**How to apply:** Bij elke "tijd bespaard"-tekst een nuchtere, verdedigbare schatting per item gebruiken en de aanname benoemen. Zie ook [[omnivaleur-frontend-voor-leken]].

---

## -Users-Danie-Downloads / omnivaleur-facebook-marketplace-beta-eerlijk

*17-11-2026*

Extensie 1.0.423 (nov 2026) dekt Marktplaats, 2dehands en Facebook in één upload naar de Chrome Web Store. Daniel wil dat gebruikers in de app zelf zien dat Facebook Marketplace nog beta is (16-11-2026). Etsy: API-sleutel aangevraagd, status pending review, geen melding bij afwijzing; klanten vragen ernaar (ook US-prijzen i.v.m. tariffs).

**Why:** hij verkoopt zekerheid en wil geen klachten over iets wat nog niet betrouwbaar is.

**How to apply:** noem Facebook overal als beta (UI, Help, klantantwoorden); zeg bij Etsy "coming soon" tot de sleutel actief is. Zie [[omnivaleur-gevraagde-koppelingen]] en [[omnivaleur-platform-geen-toestemming]].

---

## -Users-Danie-Downloads / omnivaleur-metingen-en-opvolging-in-overdracht

*17-11-2026*

Daniel wisselt dagelijks met de tweede ontwikkelaar (gezien 16-11-2026). Een meting "morgen" of "later" gebeurt dan in een sessie die jij niet bedient.

**Why:** meetmomenten (bijv. tijd van aanmelding tot eerste live listing, versie 1.0.423 per kanaal, analytics-sleutelgebeurtenis) vielen anders tussen wal en schip. Hij wil dat wat Indie Hackers-reacties en metingen opleveren ook bij de andere developer terechtkomt.

**How to apply:** elke toezegging "ik meet later" meteen vastleggen in docs/overdracht.md (met datum en wat gemeten wordt), terugkerende cijfers in de zondagsmail zetten en zeggen waar hij ze kan terugzien. Voorstellen die hij uitstelt gaan als "Uitgesteld" in de lijst. Zie [[overdracht-bij-limiet-zelf-klaarzetten]] en [[omnivaleur-te-bouwen-lijst]].

---

## -Users-Danie-Downloads / omnivaleur-persoonlijke-trackinglink

*15-11-2026*

Sinds 15-11-2026 bestaat https://omnivaleur.com/r/daniel: elke klik wordt geteld, aanmelders worden aan Daniel gekoppeld en krijgen de gewone 7 dagen proef.

**How to apply:** Gebruik deze link voor Daniels persoonlijke posts (X, Indie Hackers, Facebook); niet de kale homepage, anders is de bron niet meetbaar. Zie [[omnivaleur-creator-budget-standpunt]].

---

## -Users-Danie-Downloads / omnivaleur-vinted-geen-auto-herplaatsen

*15-11-2026*

Klant Joost (nov 2026) verwachtte dat verkochte Vinted-artikelen vanzelf opnieuw geplaatst of verwijderd worden. Automatisch herplaatsen bestaat alleen voor Marktplaats; op Vinted is het per artikel handmatig.

**Why:** Terugkerende verwarring in support, en Vinted-herplaatsen heeft detectierisico ([[vinted-detectie-risico-relisten]]).
**How to apply:** Leg het in klantantwoorden direct uit en maak het zichtbaar in de Help-pagina, zodat de klant het niet pas na een tweede mail ontdekt. Zie ook [[omnivaleur-vinted-marktplaats-autodelist]].

---

## -Users-Danie-Downloads / omnivaleur-opzegger-geen-tegenargument

*14-11-2026*

Voorbeeld 11-11-2026: een klant zegde op omdat hij bijna alles op Marktplaats verkoopt en de andere kanalen hem niets opleveren. Daniel vroeg of er nog iets uit te halen viel. Antwoord: weinig. Korting lost een kanaalprobleem niet op, en zijn stijlgids zegt: bij een nee geen tegenargument.

**Why:** Eerlijkheid en rust wegen zwaarder dan een klant die half blijft. Zie [[omnivaleur-light-plan]] voor het enige logische aanbod.
**How to apply:** Eerst de echte opzegreden benoemen (prijs, fouten of kanaalfit). Alleen Light (9,99, tot 20 actieve artikelen) noemen als het echt bij zijn gebruik past, en het antwoord kort en vriendelijk houden.

Aanvulling 12-11-2026: een klant die zelf om een aanbod voor verlenging vroeg (relist-vraag over Vinted, risico sinds de voorwaarden van 5 oktober) kreeg geen korting maar een nieuwe gratis week om rustig te kijken, daarna eigen keuze tegen de normale 19,99. Dat is het patroon voor klanten die twijfelen maar zelf om een aanbod vragen.

---

## -Users-Danie-Downloads / omnivaleur-social-video-pipeline-engels

*13-11-2026*

Daniel levert ruw videomateriaal in een Google Drive-map (https://drive.google.com/drive/folders/1JRq6X2EuVNXqRXF8HibapqBohSLx5uIj). Daar staat nu vooral Revaleur-content, dus Omnivaleur-clips moeten eruit gefilterd worden. Begin alleen met Omnivaleur Engels; Facebook komt later. De scheduler is nu alleen gekoppeld aan het Omnivaleur-Engelse account. Onderzoek wat een goede social video maakt (hook, realistische content) en kijk naar zijn eigen TikTok/Instagram.

**Why:** Eigen social was in okt 2026 gepauzeerd ([[omnivaleur-groei-pivot-creators-okt-2026]]), dit is de gerichte herstart.
**How to apply:** Geen Revaleur-content op het Omnivaleur-account plaatsen; eerst testen voordat er live gepost wordt.

**Update 11-11-2026:** Daniel plant alles zelf in via de scheduler "Schedchie" op alle platformen (TikTok, Instagram, YouTube Shorts, ook Threads/Pinterest); hij plaatst, Claude levert alleen de video's aan. Analytics (vooral YouTube, Instagram, hooguit TikTok) bij voorkeur via die scheduler uitlezen. Wekelijkse dinsdagroutine gewenst: 3-4 video's per week, met cijfers van voorbeeldaccounts in de niche erbij. Videokwaliteit: snel, dynamisch, veel echte dashboardbeelden, snelle switches, voice-over was goed; het poppetje mag nooit door de laptop heen bewegen (controleer dit). Ontbreekt een skill, dan escaleren naar Daniel. Voor tools zoekt hij gratis opties (vroeg naar Azure).

**Update 13-11-2026 (voorkeuren stijl en leren):** Daniel wil meer menselijkheid (stem, beelden), een sterkere hook en een duidelijkere story. Bij een voorstel wil hij 3 totaal verschillende varianten om uit te kiezen, en op termijn grote variatie: uitleggend, storytime, analogieën, direct. De routine moet leren van de analytics op Instagram, TikTok, YouTube en Facebook en zo vanzelf bij de best werkende aanpak uitkomen. Achtergrondmuziek mag wisselen en mag een actueel trendgeluid zijn dat past bij de setting; per video noteert Claude welk geluid en waarom, Daniel zet het in de app. Inspelen op relevante trends is gewenst.

---

## -Users-Danie-Downloads / omnivaleur-klant-eigen-verantwoordelijkheid

*12-11-2026*

Bij klanten die dingen laten doen die ze zelf in Omnivaleur kunnen (bv. advertenties toevoegen, voorraad herstellen), reageert Daniel subtiel maar duidelijk: dat blijven ze zelf doen. Contact met Daniel is voor support, vragen en foutmeldingen, niet om het werk voor hen te doen.

**Why:** Voorbeeld 11-11-2026 (klant Toon, webshop dejuistetoon.eu): vroeg om advertenties "toe te voegen op omni" en wanneer verkochte items terugkomen. Daniel wil niet in de rol van uitvoerend assistent belanden, het blijft de verantwoordelijkheid van de klant.

**How to apply:** Concept eerst de vraag/fix beantwoorden (eerst checken of de fix er echt is, zie [[bewijs-voor-claims-klanten]]), en eindig met een vriendelijke zin over wie wat doet. Toon: jij, informeel ([[klantcommunicatie-jij-niet-u]]).

---

## -Users-Danie-Downloads / omnivaleur-afmelden-alleen-waar-verplicht

*10-11-2026*

Daniel wil in mails een afmeldoptie alleen op de plekken waar dat juridisch 100% nodig is, en dan heel subtiel verwerkt. Afmelden of voorkeuren aanpassen mag achter een login in Omnivaleur zitten.

**Why:** Hij vindt zelf afmeldlinks irritant en wil geen vriendelijk-doen-met-uitgang in elke mail. Gesprek van 9-10 november 2026.
**How to apply:** Bij nieuwe mailtemplates eerst vaststellen of afmelden wettelijk verplicht is (koude outreach vs. transactiemail), anders weglaten. Zie [[omnivaleur-cold-outreach-wetgeving]] en [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / omnivaleur-zoho-mcp-alleen-concepten

*03-11-2026*

Op 21-10-2026 liet Daniel een eigen Zoho-mail koppeling (MCP "zoho-mail", tools mail_lees/zoek/concept) bouwen zodat Claude de mailbox kan gebruiken zoals hij. Bij de test (concept naar een klant) was zijn regel: "je mag nooit versturen".

**Why:** Een verkeerde of ongecontroleerde mail naar een klant kost direct vertrouwen; zie [[omnivaleur-automatisering-mag-nooit-zichtbaar-fout]].
**How to apply:** Gebruik alleen mail_concept, nooit mail_verstuur. Daniel verstuurt zelf. Verwant: [[omnivaleur-mailadressen-zoho]], [[omnivaleur-mailconcepten-stijl-leren]].

Bevestigd 2-11-2026: Daniel zei "sturen doe ik altijd zelf". Lever het concept in de chat en vraag niet meer of jij het moet versturen, ook niet voor andere kanalen dan Zoho.

---

## -Users-Danie-Downloads / daniel-nieuw-businessidee-criteria

*03-11-2026*

Eind september 2026 (gesprek rond 26/27-09) liet Daniel naast Omnivaleur onderzoek doen naar een nieuw businessidee. Zijn eisen, herhaald en aangescherpt:

- Bewezen businessmodel en bewezen vraag, weinig concurrentie in NL of EU, echte mogelijkheden. Hij wil ~90% zekerheid en geen onderzoek waar hij later op terug moet komen.
- Simpel, grote markt (TAM), en een probleem dat elk normaal persoon direct herkent.
- Lage drempel: de klant wordt gratis geholpen, bespaart geld of tijd of verdient eraan, en ziet direct resultaat. Liefst iets dat geld oplevert.
- Geen preventief product ("camera ophangen als het al te laat is"): mensen betalen voor acuut, direct voordeel.

Verloop: eerst een cashback-/kortingssite op affiliateprogramma's, daarna breder, en als laatste voorstel een huurcheck (adres plus huur invullen, zien hoeveel je volgens de Wet betaalbare huur van 1-7-2024 te veel betaalt).

Aanscherping 2-3 nov 2026 (nieuwe sessie): hij wil "iets simpelers" met grotere TAM, waarvan elk normaal persoon direct weet dat het een probleem is. Zelfde eisen als hierboven, onderzoek startte vanuit "onderzoekidee 1" en eindigde weer bij de huurcheck.

**Why:** hij bepaalt zijn focus tot 2027 op wat aantoonbaar werkt, zie [[daniel-focusjaar-onderneming-2027]].

**How to apply:** toets elk nieuw idee eerst aan deze lijst en kom met een korte briefing met bronnen, niet met een lang rapport. Of de huurcheck is doorgezet is onbekend; vraag dat voordat je erop voortbouwt. Zie ook [[kerngetallen-altijd-met-bron]].

---

## -Users-Danie-Downloads / daniel-sheets-visueel-een-oogopslag

*02-11-2026*

Een kale sheet (zwarte tekst op wit, afgekapte opmerkingen, geen samenvatting) werd op 2-11-2026 afgekeurd. Daniel vroeg expliciet om visueel aantrekkelijk en overzichtelijk, en dat Claude dit zelf op zijn scherm nakijkt.

**Why:** Hij werkt visueel en wil de stand zien zonder te zoeken. Zie [[daniel-visueel-liever-dan-tekst]].
**How to apply:** Bij elke nieuwe sheet: eerst tabblad "Overzicht" met kaarten en grafiek, alle tabs opgemaakt, daarna zelf in de browser nakijken voor je klaar meldt. Voorbeeld: [[omnivaleur-kosten-en-kwartaalcheck]].

---

## -Users-Danie-Downloads / omnivaleur-kosten-en-kwartaalcheck

*02-11-2026*

Alle maandelijkse Omnivaleur-kosten staan in de Drive-sheet "Omnivaleur kosten" (map Omnivaleur), elke 1e bijgewerkt door de taak omnivaleur-kosten-bijhouden (opdracht: docs/routines/kosten-bijhouden.md). Daniel gebruikt Telegram al en wil daar meldingen: vanaf 1 november 2026 elke maand winst en voor/achter op de mijlpaal richting eind 2027 (skill kwartaalcheck, mag alleen het kopje "Stand van zaken" in het strategiedocument bijwerken). Het tweede Supabase-project ApexForge (hoort bij axongear, geen prio) is op 5-10-2026 door Daniel zelf verwijderd om 8,50 per maand te besparen. Een lege Railway-service lovely-grace mocht weg.

**Why:** Hij wil meetbare richting naar eind 2027 zonder extra ruis.
**How to apply:** Meldingen naar Telegram sturen, kosten niet opnieuw uitzoeken maar de sheet lezen.

**Update 2-11-2026:** Kosten en doelen zijn samengevoegd in één centrale Google-sheet "Kosten en doelen (Omnivaleur en Revaleur)" met eerste tabblad "Overzicht" (kaarten, kostenbalken, winstgrafiek, Omnivaleur en Revaleur gescheiden). Ook de twee routines zijn samengevoegd, zodat Daniel niets dubbel hoeft te zeggen; de doelencheck moet later op de dag lopen dan het kostenbijhouden. Kosten komen uit de bunq-export, Revaleur-kosten (ca. 77 per maand) tellen mee. Stand: winst ca. 342 per maand (Revaleur 251, Omnivaleur 91), mijlpaal 500 op schema. Daniel wil dat de sheet visueel mooi en in één oogopslag helder is.

---

## -Users-Danie-Downloads / omnivaleur-creator-budget-standpunt

*29-10-2026*

Op 24-10-2026 vroeg een creator (Janina Noetzel) 250 euro per video. Daniels standpunt: Omnivaleur is een start-up zonder middelen voor vaste videoprijzen. Hij zoekt creators voor een kleinere vergoeding plus commissie, en wil dat vriendelijk en subtiel formuleren, niet hard afwijzen.

**Why:** budget is beperkt, prijs staat vast op 19,99 en winst moet eerst bewezen worden ([[omnivaleur-prijs-nog-niet-verhogen]]).
**How to apply:** bij creator-antwoorden met prijsvraag eerst de commissie/25 euro-per-klant structuur noemen ([[omnivaleur-tiktok-creator-programma]], [[omnivaleur-creator-outreach-skill]]), geen vaste videoprijs aanbieden.

**Bijstelling 28-10-2026:** een kleine vaste vergoeding kan wel. Met creator Amanda (the_cooking_mommy) is 100 euro afgesproken voor één Reel plus Story-set, betaling na levering en goedkeuring. Haar standaard: 1 maand gebruik als Partnership Ad via haar account, langer kost extra (Daniel vroeg naar minimaal 6 maanden). Creators krijgen een persoonlijke link omnivaleur.com/r/<gebruikersnaam> voor in hun bio. Bij een budgetvraag (Naomi Felts) is het advies zelf een klein vast bedrag noemen (ca. 75 euro) in plaats van alleen een hoger percentage.

---

## -Users-Danie-Downloads / omnivaleur-creator-outreach-skill

*25-10-2026*

Per 24-10-2026 heeft Daniel een creator-outreach skill laten bouwen (gecommit en gepusht in de omnivaleur-repo). Werkwijze: hij deelt een foto of screenshot van het profiel van een (NL, Instagram) creator, Claude zet de outreachmail klaar in zijn stijl. Hij wil dat Claude hem herinnert aan dit proces, de status laat zien (verstuurd, reacties) en leert van de analytics van die mails, zodat het geen doodlopend iets wordt.

**Why:** de aanpak met screenshot en klaargezette mail bevalt hem, maar hij wil dat het niet wegzakt als hij er niets aan doet.
**How to apply:** bij vragen over creators eerst deze skill gebruiken; herinner hem actief aan status en terugkoppeling uit mailresultaten. Past bij [[omnivaleur-groei-pivot-creators-okt-2026]] en [[omnivaleur-zoho-mcp-alleen-concepten]].

---

## -Users-Danie-Downloads / omnivaleur-groei-pivot-creators-okt-2026

*23-10-2026*

Rond 22-23-10-2026: Daniel zet eigen social media voor Omnivaleur op pauze (TikTok gaf 0 views, hij wil het even puur als consument gebruiken). Organische groei is nu 5 tot 10 nieuwe gebruikers per week. Hij heeft veel vrije tijd naast ontwikkelen en wil een kickstart in gebruikersaantallen.

Nieuwe koers: het "vissen naar feedback" in Facebook-groepen werkt goed, hij zoekt dezelfde aanpak op andere kanalen (IG, TikTok, YT, Threads, Pinterest). Daarnaast wil hij creators die daadwerkelijk op hun eigen kanaal plaatsen (niet losse videomakers), ook NL-verkopers (Collabstr genoemd). Hij heeft Apify-tegoed gestort om kanalen met mailadressen te verzamelen.

**Why:** eigen contentproductie leverde niets op, bestaande bereiken lijken efficiënter.
**How to apply:** bij groeivragen geen eigen-contentplannen voorstellen; denk in creators, partnerships en feedback-vissen. Past bij [[omnivaleur-tiktok-creator-programma]] en [[omnivaleur-facebook-outreach-grens]]. Apify-kosten blijven een bewuste uitzondering op [[geen-kosten-buiten-abonnement]], betaald door Daniel zelf.

---

## -Users-Danie-Downloads / browser-tool-ander-chrome-profiel

*20-10-2026*

Bij een test op vinted.nl/vinted.com zag de browsertool alleen "Registreren | Inloggen" en een 403 op de identiteitscheck, en op omnivaleur.com ontbrak het stempeltje dat de Omnivaleur-extensie op elke pagina zet. Conclusie na meting: dit is geen storing bij Daniel, het browsertool-profiel is gewoon een ander Chrome-profiel dan het profiel waarin Daniel zelf werkt en waar zijn Vinted-sessie en de Omnivaleur-extensie wél zitten.

**Why:** zonder deze check leek het alsof Daniels Vinted-login was verlopen, terwijl de sessie in zijn eigen profiel gewoon actief was (bewezen doordat een opdracht van de avond ervoor zijn Vinted-kast wél kon uitlezen).
**How to apply:** voordat je concludeert dat een sessie/login/extensie ontbreekt op een site die Daniel normaal gebruikt, check eerst of je in hetzelfde Chrome-profiel zit als hij: open een pagina met een herkenbaar stempel (zoals de Omnivaleur-extensie-marker) en vraag Daniel in welk Chrome-venster dat verscheen. Bied aan om Claude in Chrome op dat profiel te richten voor je verder test, in plaats van te melden dat de login stuk is.

Aanvulling 19-10-2026: Claude in Chrome bleek zelfs op een andere computer te draaien dan Daniels Mac ("vgm zit jij op de verkeerde pc"). Liever dan via zijn browser live te testen: bouw op de Mac een eigen testopstelling met de echte servercode en het echte dashboard tegen zijn account, zonder achtergrondrondes, zodat er niets echt geplaatst of gemaild wordt. Daniel stelde dit zelf voor en het werkte.

---

## -Users-Danie-Downloads / kerngetallen-altijd-met-bron

*20-10-2026*

Bij financiele en juridische stukken moet elk kerngetal traceerbaar zijn naar een
betrouwbare bron, met een directe verwijzing erbij. Aannames mogen wel, maar dan
expliciet gelabeld als aanname - nooit gepresenteerd alsof ze vaststaan.

**Why:** hij pitcht deze cijfers aan familie, adviseurs en examinatoren. Een getal dat
hij niet kan onderbouwen als iemand doorvraagt, kost hem geloofwaardigheid.

**How to apply:** zet per getal de herkomst erbij (wet, Belastingdienst, Huurcommissie,
contract, eigen opgave, of aanname) met een werkende link. Verzin geen bedragen uit
geheugen - zoek de officiele tabel op. Sluit af met een lijst van wat aanname is.

Geldt ook voor getallen in klantberichten (19-10-2026): Daniel vroeg waar "bijna 500 advertenties online" vandaan kwam. Het waren afgeronde plaatsopdrachten uit de database, inclusief scans, geen geteld aantal levende advertenties. Schrijf dus "geplaatst" als het uit onze database komt en alleen "online" als het bevestigd is in het account van de klant zelf (bv. haar screenshot), en tel per soort opdracht.

Hangt samen met [[bewijs-voor-claims-klanten]] en [[bergweg-scenarios-excel]].

---

## -Users-Danie-Downloads / omnivaleur-te-bouwen-lijst

*20-10-2026*

Sinds 19-10-2026 staat alles wat klanten vragen en wat later gebouwd moet worden op één plek: `docs/te-bouwen.md` in de repo danieldk04/omnivaleur. Tabellen: Gepland (met prioriteit), Gevraagd door klanten (teller + klantnamen), Klaar, Bewust niet. Een regel in de CLAUDE.md van die repo verplicht elke sessie (ook de tweede ontwikkelaar en de dagelijkse routines) om hem te lezen voor nieuw werk en zelf bij te werken.

Plan: de tweede ontwikkelaar maakt er een Google Sheet "Omnivaleur te bouwen" van in de Drive-map Omnivaleur (staat als eerste klus in zijn overdrachtsbestand). Tot die sheet bestaat blijft het repobestand de bron.

**Why:** Daniel had alle klantwensen in zijn hoofd; hij wil dat jij en beide ontwikkelaars kunnen zeggen wat gepland staat, en dat de lijst klopt met de werkelijkheid zonder dat hij erom vraagt.
**How to apply:** vraagt een klant iets: teller omhoog. Zegt Daniel "later": als Uitgesteld erop. Is iets live: naar Klaar. Doe dit ongevraagd aan het eind van elk antwoord waarin iets gevraagd, besloten of gebouwd is. Check of de sheet inmiddels bestaat en de bron is geworden.

Zie ook [[omnivaleur-gevraagde-koppelingen]] en [[omnivaleur-huidige-fase-klachten]].

---

## -Users-Danie-Downloads / revaleur-blog-system

*17-10-2026*

`revaleur-blog` is an automated SEO blog generator for Revaleur (vintage/second-hand designer clothing), modelled on the ZenBTW blog system.

- **Repo:** `/Users/Danie/Documents/revaleur-blog` → GitHub `danieldk04/revaleur-blog` (private). An auto-commit process races git pushes — push with fetch/rebase retry.
- **Site:** Revaleur is on **Shopify**, English (`revaleur.com`); the `/nl` translation is handled manually by Daniel each Monday via Translate & Adapt. Store handle `ywqad3-xb` (`ywqad3-xb.myshopify.com`).
- **Flow:** `keywords.json` queue → Claude **Sonnet 4.6** writes an English article → published to the Shopify **News blog** (id `131155296586`, URLs `revaleur.com/blogs/news/<slug>`) via Admin API. Daily cron 09:00 CEST.
- **Auth:** Shopify uses a permanent OAuth offline token (the dev-dashboard automation `atkn_` token does NOT work for the Admin API). Secrets in the repo: `ANTHROPIC_API_KEY`, `SHOPIFY_STORE`, `SHOPIFY_ADMIN_TOKEN`, `SHOPIFY_BLOG_ID`, `GOOGLE_API_KEY`.
- **Features:** category tags (5 categories), two-layer internal linking (in-prompt + retro relinker via Admin API), featured images via Google Gemini image models (needs billing-enabled Google project — free tier returns 429).
- **Search Console koppeling (werkend sinds 23-09-2026):** apart service account met alleen leesrechten ("Beperkt") op revaleur.com, sleutel als GitHub secret. Search Console login van revaleur.com is danielsclothingshop@gmail.com (niet zijn standaardaccount). Proefdraai haalde 38 artikelen met klik/positiecijfers op; generator gebruikt die voor onderwerpkeuze en interne links.
- **Stilstand aug/sep 2026:** vanaf 15-08 liep de generator vast op een al gepubliceerd keyword (sindsdien overgeslagen), en vanaf 02-09 was het Anthropic-tegoed op. Na aanvullen loopt de 09:00-run vanzelf weer.

Test with DRY_RUN, never real publishes — see [[revaleur-blog-no-test-publishing]].

- **SEO-opschoning (10-9-2026)**: structurele schoonmaak van de Shopify-winkel gedaan en live gecontroleerd: één Ralph Lauren pagina (de dubbele stuurt door), blog samengevoegd tot één hoofdblog, dode links en lege pagina's weg. Het herbruikbare gereedschap staat in de repo als `scripts/seo.mjs` (o.a. `audit` voor een inventarisrapport). Bij een volgende SEO-ronde dat script eerst draaien in plaats van opnieuw handmatig inventariseren.

---

## -Users-Danie-Downloads / nexus-market-terminal

*17-10-2026*

Daniel's main live trading system: **NEXUS Market Terminal** (aandelen/portfolio, NIET de prediction-market-bot — dat is een apart, minder actief zij-project in dezelfde repo).

- **Locatie**: `/Users/Danie/Documents/Prediction Market Trading bot /` (let op: trailing space in mapnaam). Git remote: `github.com/danieldk04/nexus-market-terminal` (publiek).
- **Kern** in `src/`: `tier1_scanner.py` (scant ~400 tickers op fundamentals + momentum, gratis via yfinance/Wikipedia), `tier2_analyser.py` (Claude Sonnet bull/bear deep-research op top-10, 7d cache), `weekly_evaluator.py` (zelflerende loop, Claude Opus, injecteert regels terug in memory.json), `momentum_engine.py` (S_Momentum scoring), `nexus_scoring.py` (vectorized), `backtest_engine.py` (walk-forward validatie, door mij toegevoegd 2026-07).
- **Dashboard**: `pro.html` (geavanceerd, tabs, Chart.js) — het actieve dashboard; `index.html` is de oude. Served op poort 8765. Data uit `data.json` (B) + `memory.json` (M).
- **BELANGRIJK**: er draait een achtergrondproces dat elke bestandswijziging automatisch commit ÉN pusht ("auto: update..." / "Auto-update: Ticker" commits, uurlijks). Verwacht dat je edits vanzelf gecommit worden. Git-commando's kunnen traag/timeouten door repo-grootte + deze auto-committer.
- **Security fix 2026-07**: `config.json` (prediction-market-bot) bevatte een live Twitter token, stond in git → untracked + .gitignore toegevoegd. Token staat nog in oude history; Daniel zou hem intrekken.
- Toegevoegd 2026-07: gratis social sentiment (`src/social_sentiment.py`: StockTwits + Google News RSS werken zonder key; Reddit vereist gratis REDDIT_CLIENT_ID/SECRET want anoniem = 403). Zie [[prediction-market-bot-improvements]].

- **Meldingen 2026-08-20**: de daily brief over portfolio e.d. is teruggezet naar **2x per week (maandag en vrijdag)** in plaats van elke ochtend. Telegram-meldingen van de ETF-scan en aandelenscan blijven wel gewoon draaien.
- **Backtest-uitkomst aandelenscan (2026-08-20/21, uit het leerlogboek zelf)**: de losse aandelenscan (momentum-gedreven) verslaat de markt niet — historisch 50,2% raak, bij live-signalen met afgeronde uitkomst zelfs 40,8% (slechter dan de index). Hoogste momentumscores (8-10) presteerden juist het slechtst. Kanttekening: nog maar 191 live-signalen, te weinig om hard te concluderen, en de fundamentele kant (S_Growth/DCF/ROIC) is alleen bij live-signalen gelogd. De **ETF-scan** presteert wel beter: 8 sterkst stijgende ETF's maandelijks kopen gaf 5 jaar terug 17,5%/jaar vs 16,2% voor gewoon MSCI World (met diepere dip, -20% vs -14%).
- Mobiel gebruikt een eigen GitHub-toegangssleutel los van desktop (sleutels worden per-apparaat opgeslagen, niet gedeeld) — bij "koppeling nodig"-meldingen op telefoon is dit de eerste checke, niet per se een echte storing.
- **Confidence-gating systeem (afgerond 23-09-2026)**: signal_logger.py/calibration.py loggen elk live scan-signaal met uitkomst in een database, berekenen een gekalibreerde Wilson-confidence per kandidaat (meerdere assen: regime × momentum × VCP × MACD × RSI), en tonen die als badge in de Bot-tab van pro.html. Een gate in evolution_engine.py kan kandidaten onder een confidence-drempel blokkeren of de positiegrootte ermee schalen, maar staat **standaard uit** via env var `CONFIDENCE_GATING=0` — op puur technische data haalt nog niets de betrouwbaarheidslat (plafond ~54-57%, niet de 90% die veel systemen beloven). Zet pas aan als de rijke laag (fundamentals + sentiment) genoeg cohorten heeft opgebouwd.
- Zie [[claude-code-sandbox-egress-block]]: StockTwits/Bluesky testen binnen een Claude Code sessie geeft een 403 die eruitziet als een API-storing maar een sandbox-egress-block is, niet een echte bug.
- **Trade Republic (vastgesteld 8-8-2026)**: Daniel belegt elke maand bij Trade Republic. Handmatig de aankoopprijs bijwerken werkt voor hem niet. Inleg en aankoopkoers komen daarom uit de Trade Republic **transactie-export (CSV)**, niet uit een schatting. De Amundi S&P 500 staat niet op Yahoo Finance: de koers wordt afgeleid van een ander S&P-fonds met een omrekenfactor, geijkt op zijn eigen aankoopkoersen uit die export. Bij afwijkende portfoliowaarde eerst die factor en een verse export checken.

---

## -Users-Danie-Downloads / omnivaleur-server-amsterdam

*16-10-2026*

Op 15-10-2026 zette Daniel de Railway-regio van de Omnivaleur-server van Californië naar Amsterdam (EU West) en deployde opnieuw. Na de wissel: site sneller (0,17 tot 0,29 s), opdrachten liepen door, 80 Marktplaats/2dehands-opdrachten zonder blokkade door een site. De privacyverklaring zegt nu dat de server in Nederland staat. Google Analytics blijft aan, zonder cookiebanner, alleen vermeld in de policy. Daniel heeft alle verwerkersovereenkomsten op de platforms geaccepteerd.

**Why:** AVG/privacy (data in de EU) en snelheid voor Nederlandse en Belgische klanten.
**How to apply:** ga bij nieuwe infra- of privacyteksten uit van hosting in NL. Openstaand: Railway-logs zijn niet nagekeken op 403-weigeringen door Marktplaats/Vinted na het nieuwe server-IP; bij plotselinge "geweigerd"-fouten eerst daaraan denken. Zie [[railway-no-headless-browser]] en [[omnivaleur-platform-geen-toestemming]].

---

## -Users-Danie-Downloads / remote-control-altijd-aan

*16-10-2026*

Daniel wil dat werkelijk alles wat hij in Claude Code doet ook vanaf zijn telefoon werkt via Remote Control, met acties op zijn Mac. Dispatch is niet wat hij zoekt. Rond 15-10-2026 aangezet: nieuwe chats in de desktop-app koppelen zich automatisch, en ook sessies uit de terminal (`claude`). Oude chats niet, die vindt hij niet relevant.

**Why:** hij wil overal kunnen doorwerken aan Omnivaleur zonder achter de laptop te zitten, met perfecte synchronisatie tussen telefoon en desktop.
**How to apply:** nieuwe sessies, scheduled tasks of opstartmethodes die je inricht moeten Remote Control aan hebben. Meldt hij dat iets niet op zijn telefoon verschijnt, eerst controleren of de instelling nog staat (niet bevestigd dat een nieuwe terminalsessie zich echt vanzelf koppelt). Zie [[daniel-macbook-8gb-ram]].

---

## -Users-Danie-Downloads / omnivaleur-mobiel-pwa-biedingen

*15-10-2026*

Sinds ongeveer 14-10-2026 kan een klant Omnivaleur op zijn telefoon als app op het beginscherm zetten (web-app via de browser). Hij staat NIET in de App Store of Play Store; dat moet in klantantwoorden expliciet gezegd worden, want klanten vragen "hoe heet de app?". De uitleg hoe je hem installeert hoort ook in het dashboard zelf op een logische plek, niet alleen in een mail.

Daarnaast is er een berichten- en biedingenoverzicht: in één blik hoeveel berichten en biedingen openstaan op Marktplaats, 2dehands en Vinted, met een knop naar het platform. Reageren gebeurt nog op het platform zelf; namens de klant antwoorden komt later. De automatische Vinted-acties draaien nog alleen via de Chrome-extensie op de computer.

**Why:** klanten willen één handelsplek en mobiel werken; dit was het realistische antwoord daarop.

**How to apply:** beloof klanten geen app-store-app, geen antwoorden vanuit Omnivaleur en geen mobiele Vinted-automatisering tot dat echt gebouwd en getest is. Dashboardteksten in het Engels, zie [[omnivaleur-dashboard-ui-taal-engels]].

---

## -Users-Danie-Downloads / omnivaleur-shopify-app

*15-10-2026*

**STAND 15-10-2026: de App Store-route is dood.** Shopify zette de aanvraag op 28-08-2026 op paused (ref 131213): ze accepteren geen apps die naar marktplaatsen buiten Shopify publiceren. Niet opnieuw indienen. Koppelen gaat nu via een app die de winkelier zelf in zijn eigen Shopify-organisatie maakt (dev.shopify.com), waarna hij client ID en secret aan Omnivaleur geeft. Daniel loopt dat met klanten door via schermdelen in een call. Details in de omnivaleur-repo-notitie shopify-app-store-geweigerd. Onderstaande historie geldt alleen nog als achtergrond.

Naast de webapp heeft Omnivaleur een losse **Shopify-app** die begin 2026-08-21/22 is ingediend voor beoordeling bij de Shopify App Store. Op 2026-08-22/23 heeft Daniel daadwerkelijk op "Submit for review" gedrukt — de app staat nu bij Shopify in de beoordelingswachtrij (niet meer alleen "in voorbereiding").

- De app praat alleen met de **Admin API** — geen Online Store, geen POS, geen embedded App Bridge (dat vinkje is bewust uitgezet).
- Test-account voor Shopify's reviewers staat op de live server: `shopify-reviewer@omnivaleur.nl` (wachtwoord staat niet in memory — zie sessielog `ed368613` of vraag Daniel; rotate niet nodig zolang het puur een testaccount is zonder echte data).
- Facturering loopt via een losse aanvraag bij Shopify voor goedkeuring van **externe facturering** — dat vinkje in de listing mag pas aan na die goedkeuring, dat proces stond nog open na deze sessie.
- Compliance-webhooks zijn geconfigureerd via een TOML-bestand met de Shopify CLI, en tijdens de laatste automatische Shopify-check bleek de HMAC-signatuurcheck (`verify_webhook`) niet op module-niveau geïmporteerd voor de drie nieuwe endpoints — dat was de laatste rode check, is gefixt en gepusht.

Op 2026-08-24 bevestigd via Daniels eigen Partner-dashboard: listing-status **"Submitted"** (nog niet goedgekeurd, niet afgewezen), 0 installs / $0 earnings, geen fouten op de Dev Dashboard (API health OK, geen webhook-fouten). Duurt normaliter een paar dagen.

Op 2026-08-30 is de **winkelkoppeling (custom app / Admin-API token) end-to-end getest op een echte winkel** (Revaleur): token ophalen, producten en bestellingen lezen, locaties/kanalen, en de automatische token-verversing werken. Er is nog maar één live Shopify-koppeling over alle tenants. Bug die drie koppelpogingen kostte: Shopify geeft scopes soms met spaties i.p.v. komma's terug, en meldt bij `write_products` niet ook `read_products` (schrijf omvat lezen) — de scope-check hield daar geen rekening mee, nu wel. Het koppelscherm is herbouwd tot drie stappen (zie [[omnivaleur-frontend-voor-leken]]).

**Why:** eerste stap richting distributie van Omnivaleur via het Shopify-ecosysteem, los van de bestaande koude-mail-outreach.

**How to apply:** nooit meer zeggen dat de app in beoordeling is of via de App Store komt; klanten koppelen via hun eigen app (client ID + secret). Zie ook [[omnivaleur-outreach-machine]] en [[omnivaleur-notion-docs]].

**Gat in de sync (vastgesteld 07-10-2026, klant Janneke vroeg ernaar):** nieuwe Shopify-producten komen niet vanzelf binnen. Er is geen webhook of vaste ronde; de klant moet zelf op Import klikken (pakt alleen wat nieuw is). Wat wel automatisch gaat: een verkoop in de Shopify-winkel haalt het artikel van de andere kanalen af. Zeg klanten dus nooit dat nieuwe producten "vanzelf" synchroniseren tot dit gebouwd en getest is.

---

## -Users-Danie-Downloads / klant-wacht-resultaat-eerst

*14-10-2026*

Op 14-10-2026 zei Daniel, na de sessie rond klant Janneke (Vinted-plaatsing bleef hangen bij de prijs) twee keer te hebben afgekapt: "je bent al heel lang bezig en ik heb eigenlijk nog geen resultaten gezien". Hij wil dat dingen worden afgerond en dat er met zekerheid zo efficiënt mogelijk een antwoord naar de klant kan.

**Why:** een wachtende klant kost hem vertrouwen per uur; hij zat op dat moment in het buitenland en kon zelf weinig bijsturen. Lang onderzoek zonder zichtbare tussenstand voelt voor hem als niets.

**How to apply:**
- Bij een wachtende klant: eerst afbakenen wat binnen deze sessie af kan, dat afmaken en meteen een plakklaar klantbericht opleveren.
- Laat na elke grote stap een korte tussenstand zien, zodat afkappen nooit betekent dat er niets ligt.
- Zekerheid blijft eis (zie CLAUDE.md), maar beperk het onderzoek tot wat nodig is voor dit ene klantantwoord; de rest wordt een vervolgtaak.
- Daniel schrijft klantberichten vaak zelf en laat ze nakijken: controleer dan vooral of elke stap voor een leek ondubbelzinnig is.

Zie [[autonoom-uitvoeren-niet-vragen]], [[omnivaleur-huidige-fase-klachten]], [[klantvraag-eerst-helemaal-lezen]].

---

## -Users-Danie-Downloads / omnivaleur-gevraagde-koppelingen

*14-10-2026*

Rond 5 tot 7-10-2026 antwoordden twee leads op de koude mail met dezelfde soort vraag: kan mijn eigen website de bron zijn waar Omnivaleur de advertenties vandaan haalt?
- Kingsman Vintage & Design (Niels): Shopify als basis, en wil ook Etsy, Whoppah, Selency en Reliving.
- Upretro Webshop: eigen site op Lightspeed. Lightspeed heeft een openbare API; in het concept is gevraagd welk Lightspeed (eCom of Retail) en of ze zelf een API-sleutel kunnen maken.

Inlezen vanaf een eigen site kon tot 9-10-2026 alleen vanuit Shopify (plus eBay, Marktplaats, 2dehands, Vinted). Sinds 09-10-2026 is WooCommerce er ook als kanaal, zie [[woocommerce-koppeling]]; Lightspeed, Etsy, Whoppah, Selency en Reliving nog niet.

Op 13-10-2026 vroeg een gitarenhandelaar met een JouwWeb-webshop hetzelfde. JouwWeb heeft geen openbare koppeling (niets gevonden om producten te lezen of op verkocht te zetten), dus echte synchronisatie kan niet. Risico bij hem: 55 van zijn 69 webshopproducten staan ook via Omnivaleur online, dus een webshopverkoop laat de advertenties op Marktplaats, Vinted en 2dehands gewoon staan. Dat moet hij dan handmatig afhalen.

**Why:** vintage- en designhandelaren met een eigen webshop zijn een terugkerend type lead; hun vraag is een signaal voor welke koppelingen klanten opleveren.

**How to apply:** bij een vergelijkbare leadvraag eerlijk zeggen wat er nu wel en niet kan, en de gevraagde platforms bijhouden als bewijs van vraag voordat er iets gebouwd wordt. Zie [[omnivaleur-outreach-machine]] en [[omnivaleur-huidige-fase-klachten]].

---

## -Users-Danie-Downloads / omnivaleur-ai-gemini-eerst

*13-10-2026*

Rond 23/24-09-2026 zijn alle AI-onderdelen van Omnivaleur (rubriek kiezen bij import, dubbelcheck tussen talen, Shopify-collecties, eBay-rubrieknamen, vertalen, blog) omgezet naar **Gemini als eerste keus** met Daniels Google-sleutel (gratis laag). Claude springt alleen in als Google plat ligt en er tegoed is.

Aanleiding: Anthropic-tegoed was op, vijf onderdelen deden niets meer. Daniel eiste "1000% zeker" en daarna een echte vergelijking, die draaide op echte data:
- Rubrieken (199 artikelen, blind beoordeeld): Gemini 43 keer beter, Claude 7 keer.
- Dubbelcheck (120 echte paren, 3 rondes): Claude 7 tot 12 foute koppelingen per ronde, Gemini 0 tot 1.
- Vertalen (20 advertenties): Gemini 20 van 20 goed; Claude maakte van "Zeer goed" drie keer "Excellent condition".
- Blog: geen harde winnaar, Claude schrijft iets natuurlijker.

Model: gewone **Flash**, bewust niet Flash-Lite (gokte te vaak, spelfouten). Kanttekening: gratis laag heeft daglimiet en Google mag teksten gebruiken voor training.

**Bijgewerkt 24-09-2026:** het eerste Google-project stond op vooraf betalen; toen dat tegoed op was gaf Google 402 en viel het niet vanzelf terug op de gratis laag. Daniel maakte daarom een nieuwe sleutel in een project zonder betaalgegevens (gratis laag). Die geeft vaak 503 "te druk"; de server wacht dan 4 seconden, probeert het één keer opnieuw en gaat pas daarna naar Claude. De rubriekenvraag is gemeten ~8.100 tokens, niet 15.000, dus inkorten is bewust niet gedaan.

**Why:** gratis en meetbaar preciezer, zie [[geen-kosten-buiten-abonnement]].
**How to apply:** zet geen Omnivaleur-AI-functie terug naar Claude als eerste keus zonder nieuwe vergelijking op echte data. Nieuwe AI-functies standaard op Gemini Flash bouwen.

**Bijgewerkt 25-09-2026 (kostenbeeld, gemeten in logs):** de gratis sleutel haalt zo'n 200 goede antwoorden per dag, genoeg voor ongeveer 70 tot 100 nieuwe artikelen. Na het dagmaximum op Flash stapt de server vanzelf over op Flash-Lite (dus toch Lite, met zwakker Nederlands zoals "Grije" i.p.v. "Grijze"); pas daarna Claude Haiku 4.5 (blog: Sonnet 5 als reserve). Op Claude kost een artikel ongeveer 1 cent, een klant met 20 artikelen per dag zo'n 6 dollar per maand, een import van 1000 artikelen eenmalig ~10 dollar. Een betaalde Google-sleutel is grofweg drie keer goedkoper dan Claude en houdt het betere Flash. Op 25-09 middag: 20 van 20 taalvragen via Gemini, Claude 0.

**Bijgewerkt 10-10-2026:** de Claude-reserve voor vertalen is nu Haiku 5.5 in plaats van Haiku 4.5 (ongeveer tien keer goedkoper, getest voor livegang). Het Anthropic-tegoed was die ochtend op en is door Daniel aangevuld. Details in de omnivaleur-geheugenmap: [[haiku-5-5-vertalen]].

**Bijgewerkt 11-10-2026 (Anthropic-dagkosten, gemeten in de Console):** 07-10 en 08-10 kostten $6 en $18 per dag, vooral Haiku 4.5 door de rubriekvraag van ~8.900 tokens. Na de rem van 09-10 (maximaal 300 Claude-vragen per dag) zakte het naar ongeveer $1 per dag. Daniels grens is ongeveer $1 per dag. De piek van 10-10 ($4,33 Sonnet 5.5 op de sleutel "crosslisteu") kwam eenmalig van de vertaalproef, waarin Sonnet als blinde beoordelaar diende. Tip: in de Anthropic Console kun je op Usage groeperen per API-sleutel, op Cost niet. Een eenmalige controle op 14-10-2026 vergelijkt de /health-teller met de dagkosten (hoe vaak Gemini wint, of de 300 geraakt wordt).

**Bijgewerkt 12-10-2026 (kostencheck):** de app gebruikt wél Sonnet: Sonnet 4.6 in de listingfunctie voor klanten, Sonnet 5 in de bloggenerator en enkele scripts. De ~$0,28 per dag Sonnet 4.6 is dus waarschijnlijk klantverkeer. Schatting nu ongeveer $0,40 per dag in totaal; Daniel vroeg dit over een week (rond 19-10-2026) na te kijken op platform.claude.com/cost. Les: een eerste zoekopdracht gaf leeg terug en werd niet gecontroleerd, waardoor eerst ten onrechte "nergens Sonnet" werd gemeld.

---

## -Users-Danie-Downloads / omnivaleur-reseller-aantal-overal-gelijk

*10-10-2026*

Sinds 9-10-2026 is het aantal resellers dat Omnivaleur in teksten noemt **64**. Daniel liet alle plekken waar nog 34 of 38 stond aanpassen: koude mails, de videopagina omnivaleur.com/mp, website en landingspagina's. Al verstuurde mails blijven zoals ze zijn.

**Why:** een lead las 64 in de mail en 38 op de videopagina. Tegenstrijdige cijfers ondermijnen het vertrouwen, zie [[omnivaleur-automatisering-mag-nooit-zichtbaar-fout]].

**How to apply:** wordt het getal opnieuw verhoogd, zoek dan op alle plekken tegelijk (homepage EN en NL, zie [[omnivaleur-homepage-nl-en-dubbel]], videopagina, mailtemplates, landingspagina's) en pas ze in één keer aan. Noem nooit een getal dat ergens anders anders staat. Zie ook [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / daniel-visueel-liever-dan-tekst

*09-10-2026*

Bij dashboards, rapporten, analytics-schermen en artifacts: bouw visueel en lean. Grafieken, cirkeldiagrammen, meters en een heldere structuur zeggen Daniel meer dan lappen tekst.

**Why:** terugkerend (o.a. 2026-08-28): "zo lean mogelijk, plaatjes zeggen mij veel meer dan tekst" en "kan je werken met de juiste visuals en een duidelijke structuur in dit dashboard ... grafieken, cirkeldiagrammen etc." Hij is geen programmeur en wil in één oogopslag de stand zien.

**How to apply:**
- Kies bij een keuze tussen een tabel/tekst en een grafiek de grafiek.
- Houd schermen kaal: weinig kolommen, geen uitleg-alinea's, cijfers groot en de belangrijkste bovenaan.
- Dit is de deliverable-kant; voor de rapportage in de chat geldt los daarvan de vier-blokjes-stijl uit CLAUDE.md.
- Vergelijking per periode is voor hem het belangrijkste aan analytics (08-10-2026): "vooral de vergelijking per periode en de grafieken" zoals Google Analytics ze geeft. Het eigen marketingdashboard op omnivaleur.com/analytics (toegang via token in de link, die staat niet in dit geheugen) kreeg toen een keuze 7/28/90 dagen tegenover dezelfde periode ervoor, met grafieken. Bouw elk nieuw cijferscherm standaard met zo'n periodevergelijking.

---

## -Users-Danie-Downloads / omnivaleur-warme-leads-inzicht

*08-10-2026*

Op 07-10-2026 zei Daniel dat mensen die op de koude mail reageren of om de video vragen zijn warmste leads zijn, en dat hij daar te weinig inzicht in heeft en er te weinig mee gebeurt. Toen bleek: 30 reageerders zonder account, 20 nooit opgevolgd, 17 daarvan ouder dan 25 dagen. Hij liet ze alsnog mailen plus een opvolging enkele dagen later. Op het marketingdashboard staat sindsdien een compact blok: tellers, "Wacht op jou" (alleen wie op Daniels antwoord wacht) en een statustabel; de volledige lijst ingeklapt.

**Why:** een lead die al reageerde is veel meer waard dan een koude lead; laten liggen is direct gemiste omzet.

**How to apply:** bij elke wijziging aan outreach of dashboard nagaan dat iedereen die reageerde of de video kreeg in een opvolgstroom zit, en dat Daniel in één oogopslag ziet wie op hem wacht. Houd het blok kort, zie [[daniel-visueel-liever-dan-tekst]] en [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / omnivaleur-prijs-nog-niet-verhogen

*08-10-2026*

Daniel vroeg 2026-09-08 of de cijfers een prijsverhoging dragen, of staffels op aantal advertenties. Antwoord: nee, nog niet.

**Why:** de betalende basis is te klein (~5 op 2026-09-06) om er een prijssignaal uit te halen, en niemand zegt op om de prijs — de churn gaat over storingen. Een verhoging in exact het venster van de terughaalcampagne spreekt de "het lag aan ons"-mail tegen. Staffels op advertentie-aantal kunnen technisch nog niet: de import levert items zonder rubriek en dubbele items op, dus de teller waarop je zou factureren klopt niet.

**How to apply:** de prijs (nu 19,99 euro/mnd, betaald via Stripe, iDEAL-klanten lopen daarna op SEPA-incasso) pas op tafel als de terughaalgroep echt gaat betalen en het richting 20-30 stabiele betalers gaat; meet dan wat die groep echt gebruikt als onderbouwing voor staffels. Tot dan: focus op betrouwbaarheid en op conversie van de eerste sessie. Zie [[omnivaleur-huidige-fase-klachten]] en [[omnivaleur-premium-doneforyou-plan]].

**Toekomstige onderbouwing (07-10-2026):** Daniel wil een latere prijsverhoging onderbouwen met extra AI-functies (bijv. AI-titels onder 60 tekens, gevraagd door klant Goudlief). AI-titels zijn op zijn account getest maar staan op "later": niet aangesloten, gratis Gemini-limiet raakte op, en hij rolt pas uit als bewezen is dat het voor elke gebruiker werkt. Niemand pakt dit zelf op tot Daniel erop terugkomt. Zie [[omnivaleur-ai-gemini-eerst]] en [[geen-kosten-buiten-abonnement]].

---

## -Users-Danie-Downloads / omnivaleur-platform-geen-toestemming

*07-10-2026*

Een klant (Peter) las de Marktplaats-voorwaarden zelf en vroeg Daniel rechtstreeks
of Omnivaleur toestemming van Marktplaats heeft voor geautomatiseerd plaatsen.
Marktplaats' voorwaarden verbieden plaatsen anders dan via hun eigen knop, tenzij
Marktplaats daar toestemming voor gaf (bijv. API-partners). Daniel antwoordde
eerlijk: nee, geen apart contact of formele toestemming, de extensie vult alleen
het gewone formulier in via de eigen ingelogde browser van de klant, maar dat
neemt het voorwaarden-risico niet weg.

**Why:** dit gold nog niet zwart op wit vastgelegd. Op 18-09-2026 is
[terms.html](frontend/terms.html:135) uitgebreid met een nieuw hoofdstuk 3 dat
per platform (Marktplaats, 2dehands, Vinted, eBay, Facebook Marketplace) letterlijk
citeert wat hun regels zijn (rechtstreeks bij de bron opgehaald, niet uit
zoekresultaten) en expliciet vastlegt dat de klant zelf het risico draagt op een
waarschuwing, beperking of verwijdering van zijn account, met een verwijzing
vanuit hoofdstuk 10 (aansprakelijkheid). Dit is geen jurist-getoetste tekst.
Verwant: [[vinted-detectie-risico-relisten]] (Vinted's eigen bot-detectie) en
[[omnivaleur-cold-outreach-wetgeving]] (aparte juridische vraag over koude mail).

**How to apply:** als een klant weer naar toestemming/legaliteit van de
automatisering vraagt, eerlijk antwoorden zoals hierboven, niet geruststellen dat
het risicovrij is. Bij grote nieuwe platform-integraties vooraf checken of hun
voorwaarden automatisering toestaan, in plaats van er achteraf achter te komen.

**Aanvulling 7-10-2026:** Facebook Marketplace staat sinds 7-10 overal op de website (marktplaatsenpagina, meta/zoektekst, AI-info, inschrijfpagina) met het label beta. Daniels regel: een platform is beta tot het getest is en klanten het echt gebruiken, dan gaat het label eraf.

---

## -Users-Danie-Downloads / omnivaleur-automatisering-mag-nooit-zichtbaar-fout

*07-10-2026*

Second-Buy BV kreeg op 18-09-2026 een koude introductiemail terwijl Daniel hen
negen dagen eerder al persoonlijk had beantwoord. Oorzaak: twee vangnetten die
moeten voorkomen dat iemand die Daniel al zelf mailde alsnog een koude mail
krijgt, hadden allebei een gat (een "Re:"-antwoord werd genegeerd, en de kant
waarbij het bedrijf zelf als eerste mailde bestond niet). Daniel: "dit mag echt
nooit meer voorkomen, check op dit soort fouten want het is voor mensen heel erg
makkelijk om te herkennen dat dit een automatisering is die fout lag en dan ben ik
natuurlijk gelijk kwijt dus check dit een fix met 100% zekerheid dat dit nooit
meer in de toekomst kan gebeuren."

**Why:** het risico zit niet in de bug zelf maar erin dat de ontvanger meteen door
heeft dat er een bot achter zit die de eigen correspondentie van Daniel niet kent.
Dat is voor een klant een vertrouwensbreuk, niet alleen een ongemak, en kost
Daniel de klant. Dit is scherper dan de gewone eis uit
[[fixes-generiek-voor-alle-gebruikers]] en [[bewijs-voor-claims-klanten]]: daar
gaat het om of een fix klopt, hier gaat het om of de outreach-machine ooit met de
menselijke correspondentie van Daniel zelf kan botsen.

**How to apply:** bij elke wijziging aan de koude-mailmachine expliciet nagaan of
een lead die Daniel zelf al (in welke vorm dan ook, ook een kort antwoord) heeft
gemaild, hard wordt uitgesloten van de koude reeks, over alle adressen binnen
hetzelfde bedrijfsdomein en over een lang venster (nu 400 dagen, was 60). Beschouw
dit soort "de machine sprak de klant tegen wat Daniel net zei"-fouten als een
aparte, zwaardere categorie dan een gewone functionele bug.

**Tweede geval 6-10-2026:** Eddie (Antiek de Evenaar) zei op 29-9 "geen interesse" vanaf een privéadres, terwijl de mail naar het winkeladres ging. De machine koppelde zijn nee niet aan de lead en stuurde toch mail 2; hij reageerde boos. Sinds 7-10 wordt een antwoord gekoppeld via de mailketen (waarop het een antwoord is), niet via adres of bedrijfsnaam, en Daniel liet een kort excuus sturen. Les: bij elke uitsluitregel ook antwoorden vanaf een ander adres dan de lead meenemen.

---

## -Users-Danie-Downloads / vinted-detectie-risico-relisten

*07-10-2026*

Uitgezocht op verzoek van Daniel (2026-09-10) na geruchten over een Vinted-update
per 8 oktober 2026: die specifieke update gaat over betalen (Mangopay →
Vinted Pay) en kopersbescherming-naamswijziging, niet over bots. Het verbod op
externe software/bots stond al langer in de voorwaarden en verandert die datum
niet.

**Het echte, blijvende risico:** Vinted heeft de detectie in 2026 wel degelijk
aangezet: identieke foto's bij herplaatsen worden herkend, "machine-achtig"
herplaatsritme wordt gezien, en sinds juli 2026 zet Vinted verdachte accounts
24 uur op slot (duizenden bans dit jaar, deels permanent — bron: blogs van
concurrerende crosslisting-tools, dus niet hard bevestigd door Vinted zelf).

**Omnivaleurs blootstelling:**
- Publiceren/verwijderen/herplaatsen op Vinted loopt volledig via de extensie in
  de eigen browser van de klant, geen server die het account bestuurt — dit is
  de veiligste opzet en juist niet wat de detectie pakt.
- Risicopunt: bij herplaatsen wordt soms verwijderd en opnieuw geplaatst met
  dezelfde foto's, precies waar Vinted nu op traint.
- De code gaat er nog van uit dat 8x per dag opnieuw plaatsen op Vinted
  onopvallend is — die aanname is nooit tegen de nieuwe detectie gemeten.
- Oude, ongebruikte servercode (`vinted.py`) bestaat nog en draagt het
  risicoprofiel als iemand hem weer aanzet.

**Why belangrijk:** dit is geen acuut probleem maar wel een reëel risico waar
klanten hun Vinted-account door kunnen verliezen; "1000% veilig" is expliciet
weerlegd toen Daniel dat vroeg.

**How to apply:** bij werk aan Vinted-herplaatsen/relist-logica dit risico
meewegen, en niet beloven dat het risicovrij is. Overweeg bij toekomstig werk om
foto's te variëren bij herplaatsen en het relist-ritme te vertragen/spreiden.

**Aanvulling 7-10-2026:** in Instellingen staat de schakelaar "Allow relisting on Vinted", standaard uit. Eén schakelaar dekt zowel herplaatsen als de lichte verversing op Vinted. Staat hij uit, dan is de Verversen-knop bij Vinted weg (met uitleg en een knop "Zet het aan bij Voorkeuren") en weigert ook de server elke Vinted-verversing en herplaatsing, inclusief opnieuw proberen en bulk. Daniel wilde dit "10000% waterdicht", ook in de frontend. Marktplaats en 2dehands vallen er niet onder.

---

## -Users-Danie-Downloads / crosslist-referral-maand-gratis

*07-10-2026*

Begin oktober 2026 is in de repo ~/Documents/crosslist-eu een referral-systeem gebouwd: een gebruiker krijgt 1 maand gratis voor elke gebruiker die via zijn persoonlijke link betalend aanmeldt, prominent in het dashboard als "Earn 1 Month Free", met kliktracking. De oude link blijft werken. Op 7-10-2026 waren er nog geen echte externe klikken: de getelde klikken kwamen van Daniel en van de eigen controles.

**Why:** dit staat los van het affiliateprogramma (30%) en het TikTok-creatorprogramma; het is de klant-brengt-klant-route.

**How to apply:** kliktellingen niet als echte interesse rapporteren zonder eigen testklikken eruit te filteren. Zie [[omnivaleur-outreach-machine]] en [[omnivaleur-tiktok-creator-programma]].

---

## -Users-Danie-Downloads / omnivaleur-supabase-micro-belasting

*07-10-2026*

In de nacht van 6 op 7-10-2026 liep de Omnivaleur-database vast (statement timeouts, verbindingen kwijt; de alarmmail "database onbereikbaar" kwam wel aan). Oorzaak: het project draaide op een Nano-instance (0,5 GB geheugen, gedeelde CPU), geen limiet van het plan zelf. Op 7-10-2026 is overgestapt naar Micro (1 GB): volgens het Supabase-scherm kost dat niets extra (9,68 dollar bleef 9,68).

Daarnaast op 7-10 de belasting verlaagd: het "Get started"-scherm haalde per keer tot 12 MB op (nu 21 kB), en van 924 scans ouder dan 7 dagen is het opgeslagen scanresultaat (ca. 250 kB per stuk) leeggemaakt in kleine porties zonder downtime. De jobs-tabel (190 MB) had geen enkele automatische opruiming.

**Why:** Daniel vindt de lopende kosten al flink en wil een grotere server (Small en hoger) vermijden; eerst de belasting omlaag, pas opschalen als Micro na optimalisatie nog vastloopt.

**How to apply:** bij nieuwe databasestoringen eerst meten welke vragen zwaar zijn en of de jobs-tabel weer groeit (structurele opruiming van oude jobs bestaat nog niet), voordat je een duurdere compute voorstelt. Of Micro genoeg is moest na een paar nachten blijken. Zie [[geen-kosten-buiten-abonnement]] en [[omnivaleur-supabase-rls-uit]].

---

## -Users-Danie-Downloads / omnivaleur-facebook-groep-community

*05-10-2026*

Sinds begin okt 2026 zet Daniel in op community bouwen: Facebookgroep "EU Resellers: Vinted, eBay & Crosslisting Community" (id 891966746831784). Veel resellers zitten op Facebook, vooral UK en US. Focus is puur Omnivaleur en Revaleur, Monaim is niet actief, Daniel doet alles zelf en heeft er de tijd voor. Groepsteksten (welkomstbericht, vastgepinde post) in het Engels, zonder bulletpoints. Een Gem of eigen post schrijven mag, een bot die zich voordoet als Daniel niet, zie [[omnivaleur-facebook-outreach-grens]].

**Why:** Hij twijfelde hoe de groep te laten groeien en vroeg wat topfounders in dit stadium zouden doen.
**How to apply:** Groei-advies richt zich op waarde bieden in de groep, niet op directe pitches. Verwijs bij Facebook-vragen naar deze notitie.

---

## -Users-Danie-Downloads / omnivaleur-mail-openrate-pixel

*03-10-2026*

Na 0 reacties op de Light-plan-mail van 1-10-2026 wilde Daniel weten of mensen de mail wel openen. Er is een meetpixel in updatemails gezet; testmail naar een eigen adres kwam binnen (2-10-2026). Open-cijfers zijn dus pas bruikbaar vanaf mails na die datum; een uitblijvende reactie betekent niet automatisch "niet gelezen". Zie [[omnivaleur-light-plan]].

**How to apply:** noem open-rate alleen voor mails met pixel, en vermeld dat mailprogramma's pixels soms blokkeren.

---

## -Users-Danie-Downloads / omnivaleur-mailconcepten-stijl-leren

*03-10-2026*

Daniel stuurt technische klantmails door naar Claude voor een antwoord, maar past toon en woorden altijd nog aan. Daarom is op 2-10-2026 een routine gebouwd (`scripts/schrijfstijl_leren.py`, ophalen via IMAP uit Zoho daniel@omnivaleur.nl) die zijn verstuurde mails vergelijkt met de concepten en een stijlbestand bijwerkt. Eerste leerpunten: "Hoi Voornaam," als standaardaanhef in lopend gesprek, aanhef mag dan weg.

**Why:** hij wil dat concepten direct bruikbaar zijn zonder nabewerking.
**How to apply:** bij klantantwoorden eerst het stijlbestand gebruiken, kort en simpel houden ("korter en simpeler" is zijn vaste correctie). Zie [[klantcommunicatie-jij-niet-u]], [[outreach-schrijfstijl-menselijk]], [[credentials-never-in-memory-or-chat]].

---

## -Users-Danie-Downloads / credentials-never-in-memory-or-chat

*03-10-2026*

Never save API tokens/credentials to memory, even if asked. Additionally: Daniel has pasted his real Apify API token in plaintext chat multiple times while troubleshooting (copy-pasting terminal output that included `export APIFY_TOKEN=...`).

**Why:** each exposure means the token should be treated as compromised — chat transcripts aren't a safe place for secrets.

**How to apply:** whenever a real-looking token/credential appears in a user message, don't just quietly proceed — explicitly tell him to rotate/regenerate it, and suggest safer alternatives (e.g. a local untracked `.env` file he edits himself outside the chat, `open -e path/to/.env`) rather than exporting/pasting in terminal commands he shares here.

**Update 2026-08-20:** opnieuw gebeurd, drie keer op één dag — een Zoho app-specifiek wachtwoord, een Notion integratietoken (`ntn_...`) en een Supabase `service_role` JWT stonden gewoon in chatberichten. Die drie moeten als gelekt beschouwd worden en vervangen.

**Update 2026-09-08:** wéér — Daniel plakte tijdens leadgen-werk zijn Notion-integratietoken (`ntn_...`) opnieuw als los chatbericht. Die token moet ververst worden in Notion.

**Update 2026-09-11/12 (garmin-coach):** een volledige Garmin OAuth-sessietoken (JWT) is drie keer in dezelfde chat geplakt tijdens het debuggen van de Render-deploy. Geadviseerd: Garmin-wachtwoord wijzigen om alle lopende sessies in één keer ongeldig te maken (niet dringend, wel iets voor op korte termijn). Zie [[garmin-coach-project]].

**Update 2026-09-21 (omnivaleur):** de echte SECRET_KEY-waarde uit Railway is in de chat geplakt om hem te vergelijken met de lokale `.env`. Deze keer werd géén rotatie-advies gegeven, alleen "probeer dit in het vervolg te vermijden" — dat is een afwijking van de eigen regel. Blijf bij elke geplakte secret expliciet aandringen op rotatie, ook als het "gewoon lokaal blijft".

**Update 2026-09-27 (omnivaleur leadgen):** een Serper.dev API-sleutel (zoekdienst voor nieuwe leadbronnen) is als los chatbericht geplakt met "zet hem erin voor mij", ook al was uitdrukkelijk gezegd hem via de terminal te zetten en niet in de chat. Die sleutel moet in het Serper-dashboard vernieuwd worden.

**Update 2026-10-02 (omnivaleur mailstijl):** het Zoho IMAP-wachtwoord van daniel@omnivaleur.nl is in de chat geplakt om het in `.env` te laten zetten. Dat wachtwoord moet in Zoho vernieuwd worden (liefst een app-specifiek wachtwoord).

---

## -Users-Danie-Downloads / daniel-rechtsvorm-eenmanszaak

*02-10-2026*

Omnivaleur valt onder Revaleur: een KvK-inschrijving, rechtsvorm eenmanszaak
(bevestigd 2-10-2026). Daniel is dus IB-ondernemer, geen BV.

Gevolgen die vaak terugkomen: winst valt in box 1 met mkb-winstvrijstelling 12,7 procent
en zelfstandigenaftrek 1.200 (2026); de box 2-route bestaat voor hem niet; ondernemings-
vermogen zoals voorraad telt niet mee in box 3, maar geld op de zakelijke rekening dat
het bedrijf niet nodig heeft wel (duurzaam overtollige liquide middelen).

Hoort bij [[bergweg-box3-leegwaarderatio]] en [[btw-aangifte-stappenplan]].

---

## -Users-Danie-Downloads / bergweg-box3-leegwaarderatio

*02-10-2026*

Stand 2-10-2026. Daniels vermogensoverzicht rekent de Bergweg voor 100% van WOZ/2
(251.500; WOZ dus 503.000, was 460.000 in het oude model). Twee correcties:

1. De woning is verhuurd met huurcontract, dus voor belastingjaar 2026 geldt de
   leegwaarderatio. Kale jaarhuur 12.938 op WOZ 503.000 = 2,57 procent, schijf 2-3
   procent, dus 84 procent. Daarmee zakt zijn box 3-vermogen van 94.728 naar 54.488,
   onder het heffingsvrij vermogen van 59.357, en betaalt hij nul in plaats van 1.607.
   OPEN PUNT: Julian woont er zelf als mede-eigenaar, dus of de ratio op Daniels hele
   helft mag, moet een belastingadviseur bevestigen.
2. De post "Inventory" (Revaleur-voorraad) hoort in box 1, niet in box 3.

Of de leegwaarderatio per 1-1-2027 helemaal vervalt is NIET zeker (gecheckt 2-10-2026).
Vaststaand is alleen wat in het aangenomen Belastingplan 2026 zit: per 1-1-2026 geen
ratio meer bij niet-marktconforme verhuur aan verbonden personen, plus codificatie van
de 10-procentregel van de Hoge Raad. De volledige afschaffing wordt breed genoemd per
2027, maar serieuze bronnen noemen het een voornemen en koppelen het aan de Wet werkelijk
rendement, die naar 2028 is uitgesteld en nog niet door de Eerste Kamer is. Niet als
feit presenteren. Valt de ratio weg, dan betaalt hij circa 1.650 per jaar. Daarom is WOZ-bezwaar nu WEL verstandig, anders dan het advies
van augustus 2026: bij kamerverhuur (WWSO) levert de WOZ maar 10 tot 14 huurpunten op in
plaats van 58, dus een lagere WOZ kost nauwelijks huurruimte. De WOZ van 503.000 staat
circa 73.000 boven de marktwaarde van circa 430.000; succesvol bezwaar scheelt circa
1.637 per jaar.

Wat niet werkt: geld verschuiven voor de peildatum, extra aflossen (verlaagt bezit en
schuld tegelijk), of groen beleggen (vrijstelling valt in 2027 terug naar 200 euro).

Per 2-10-2026 zit Daniel circa 320 euro boven de heffingsdrempel, dus hij betaalt nu
een paar euro. Zijn box 3-vermogen groeit echter met ruwweg 37.000 per jaar: 21.600
beleggingsinleg, 5.400 aflossing (lagere schuld = hoger vermogen), rendement en
WOZ-stijging. Over twee jaar zit hij circa 74.000 boven de drempel.

Wat voor hem werkt: WOZ-bezwaar, lijfrente (jaarruimte 2026 is 30 procent van inkomen
min AOW-franchise 19.172, bij 45.000 inkomen circa 7.750), en zakelijk investeren
richting box 1. Wat niet werkt: aflossen met spaargeld (spaarforfait 1,28 procent tegen
schuldforfait 2,7 procent, dus het forfaitaire rendement stijgt juist), geld verschuiven
rond de peildatum, en groen beleggen.

Hoort bij [[bergweg-scenarios-excel]] en [[kerngetallen-altijd-met-bron]].

---

## -Users-Danie-Downloads / omnivaleur-light-plan

*02-10-2026*

Daniel zei op 1-10-2026: er is nu ook een Light-plan naast het gewone plan. Gebruik dat in klantantwoorden (bijv. prospects met Shopify-webshop en kleine voorraad, maandelijks opzegbaar) waar het past. Exacte prijs/inhoud: check de live pricing-pagina, niet raden.

**Why:** prospects vragen naar kosten en opzegbaarheid.
**How to apply:** antwoorden aan klanten korter en simpeler houden (Daniel vroeg dat expliciet, 1-10-2026), zie [[klantcommunicatie-jij-niet-u]], [[omnivaleur-prijs-nog-niet-verhogen]].

---

## -Users-Danie-Downloads / omnivaleur-mailadressen-zoho

*02-10-2026*

Per 30 sep / 1 okt 2026 zijn er twee officiële adressen, beide in Zoho Mail (EU): info@omnivaleur.com (contact op de site) en daniel@omnivaleur.nl (Daniel persoonlijk, klantmails). DNS staat op Cloudflare (niet Namecheap), MX wijst naar mx.zoho.eu. Mail Lite 5GB, 1 licentie per postbus kost extra. Eerdere forward van info@revaleur naar Daniels adres is bewust niet de bedoeling: Revaleur-mail hoort niet in de Omnivaleur-inbox.

**Why:** Daniel wilde Revaleur- en Omnivaleur-mail gescheiden en alles op twee plekken.
**How to apply:** frontend/contactpagina's gebruiken info@omnivaleur.com, persoonlijke mails gaan van daniel@omnivaleur.nl. Zie [[klantcommunicatie-jij-niet-u]].

---

## -Users-Danie-Downloads / omnivaleur-verlenging-2dehands-meting

*01-10-2026*

Omnivaleur verlengt een 2dehands-zoekertje na ~3 weken gratis (advertentie loopt 4 weken), zolang Chrome en de extensie aanstaan; er wordt niets verwijderd of opnieuw geplaatst. Vereist extensie 1.0.358 of hoger. Klant Egbert Brouwer (papas-plectrums) zet honderden advertenties live en vroeg hiernaar. Daniel vroeg om rond 5-10-2026 te meten of de verlengingen gelukt zijn.

**Why:** Daniel wil geen uitspraak naar klanten doen die niet bewezen is.
**How to apply:** rond 5 oktober de verlengresultaten uit de data halen en melden. Zie [[bewijs-voor-claims-klanten]].

---

## -Users-Danie-Downloads / omnivaleur-stripe-btw-checkout

*01-10-2026*

Op 30-9-2026 (15:47 UTC) is in Stripe belastingen berekenen actief gezet voor Nederland (btw-nummer opgeslagen, type "Kleine ondernemer (EU)", dus niets met KOR). Checkouts van vóór dat moment staan op 0,00; test altijd met een nieuwe betaalpagina. Verwachte prijs op de betaalpagina bij Abonneren: 24,19 (19,99 + 21% btw). Vijf bestaande klanten zouden btw bovenop hun prijs gaan betalen.

**Why:** Daniel wilde zeker weten dat de betaalpagina klopt voordat hij klanten mailt; hij wil geen mail sturen zonder bewezen werking.
**How to apply:** vraag bij betaal- of prijsvragen eerst of de checkout echt getest is met een verse pagina. Zie [[omnivaleur-prijs-nog-niet-verhogen]].

---

## -Users-Danie-Downloads / bergweg-scenarios-excel

*30-09-2026*

De leidende versie van het financiële model is
`/Users/Danie/Documents/Bergweg/Bergweg 116A - pitch en scenarios (aug 2026).xlsx`
(op 25-08-2026 gecorrigeerd op regelgeving 2026). Het origineel staat in ~/Downloads als
"Bergweg - scenarios Daniel.xlsx"; op het bureaublad ligt nog een oud simpel overzicht
uit jan 2025 (Personal Finance/Bergweg Financiën.xlsx) - niet meer gebruiken.
Acht tabbladen: 1. Pitch (voor pap/mam en Julian), 2. Overzicht (Daniels kant),
3. Dilemma's + invulblok Julian, 4. Waarde & huur (WWS-punten), 5. Cijfers
(cashflow, box 3, vermogen), 6. Scenario's, 7. Wat als, 8. Knoppen (alle aannames).

Kerncijfers: 75 m2, bouwjaar 2024, label A+++, aangekocht aug 2024 voor 5.267/m2,
marktwaarde aangehouden 430.000 (Percelio 425.000, WOZ 460.000), lening van de
ouders was 400.000, annuïteit 1.001 p/m voor Daniel, schenking 6.600 p.p. per jaar,
huur 1.200 kaal, vaste lasten 414,85 p/m.

Op 25-08-2026 bevestigd door de ouders: de schenking van 6.600 per jaar loopt door,
ook na verkoop, en Daniel mag versneld of in een keer aflossen. Daarmee zijn twee van
de drie hoofdvragen dicht. Wat nog open staat: is het kamerverhuur (max ca. 767) of
zelfstandige verhuur (vrije sector, ca. 1.650), en hoeveel kan Daniel lenen met dit
pand erbij (ca. 240.000 koopkracht).

Uitkomst van de doorrekening (vermogen na 10 jaar, Daniels helft): blijven zitten
ca. 453k, verkopen ca. 458k (volledig liquide), Julian eruit en hele woning verhuren
voor 1.650 ca. 485k (de enige route die echt geld toevoegt), vriendin gratis erin
ca. 367k (veruit het slechtst), huur teruggezet naar 767 ca. 424k.

Gecorrigeerd t.o.v. de oude versie: box 3-forfaits 2026 (1,28 / 6,00 / 2,70 procent),
heffingsvrij vermogen 59.357, schenkingsvrijstelling 6.908 per kind, en de leegwaarderatio
volgens de officiele tabel (die per 1-1-2027 helemaal vervalt).

Hypotheekvraag doorgerekend (25-08-2026): op 45.000 bruto/4% rente is Daniels eigen
leenruimte ca. 200.000, woonbudget 956 p/m — de Bergweg-last van 1.001 p/m past daar
dus net niet in. Bij een strenge bank (huur telt niet mee) kan hij op dit moment
niets lenen; het scheelt sterk hoeveel van zijn 600 huurinkomsten de bank meetelt
(0% → 0 leenruimte, 50% → 53k, 70% → 79k, 100% → 116k, Bergweg verkocht/afgelost →
200k). Extra aflossen is inefficiënt (100k aflossen levert maar 89k leenruimte op);
verkopen is de efficiënte route. Overwaarde bij verkoop is nu nog klein (~16k in
2026, ~26k in 2027, ~46k in 2029) — zijn echte koopkracht zit vooral in eigen
beleggingsopbouw (~110k na 2 jaar bij 1.800 p/m inleg) plus de 200k hypotheek.
Zijn startersvrijstelling overdrachtsbelasting (tot 555.000) is nog ongebruikt,
want de Bergweg is geen eigen woning voor hem.

Complete pitch (voor het gesprek met ouders/Julian) staat ook gepubliceerd als
Artifact: https://claude.ai/code/artifact/cf6c9700-38b4-4fcc-b280-dccaf4151255 —
privé tot Daniel hem zelf deelt. Zeven blokken: waar je staat → wat vaststaat → de
vijf toekomstscenario's → het huurrisico → wat het kost aan een eigen huis → het
voorstel → wat je aan wie vraagt.

Het huurcontract (~/Documents/Huurcontract Bergweg 116a.pdf) maakt twee dingen hard:
de huurder huurt een privekamer met gedeelde keuken/woonkamer/badkamer en Julian staat
erin als "Resident Landlord" - dus onzelfstandige woonruimte (hospitaverhuur, altijd
gereguleerd) - en de 1.200 is ALL-IN inclusief water, elektra, verwarming en internet.
Kale huur daardoor ca. 1.078; WWSO-maximum bij geschatte 90 punten is 769,54
(Huurcommissie bijlage 2, jan 2026). Tweede risico: bij een all-in prijs kan de
Huurcommissie splitsen volgens art. 7:258 BW (55% kale huur, 25% servicekosten, 20%
vervalt) - dan blijft van 1.200 nog 960 over. Risico dus 240-310 p/m samen, niet 430.

Uitkoop door Julian is onwaarschijnlijk gezien zijn salaris en financiele positie
(opgave Daniel, 26-08-2026) - benoem dat subtiel, nooit expliciet in gedeelde stukken.
Realistisch zijn er twee routes: samen erin blijven of samen verkopen. Julian woont er
voor -54 p/m terwijl huren 900-1400 kost, dus voor hem is blijven veruit het beste.

De eigendomsovereenkomst staat niet meer in ~/Downloads; alleen nog als mailbijlage
in Apple Mail (zoek op "gemeenschappelijk bezit"). De getekende PDF noemt 395.000 als
referentiebedrag in art. 5; de docx-versie heeft daar nog een lege placeholder.
De eigendomsovereenkomst (aug 2024) regelt al een aanbiedingsplicht met termijnen
(art. 4: 2 maanden aanvaarden + 2 maanden financiering aantonen), de verdeling bij
verkoop (art. 5) en toestemmingsplicht voor medebewoners/verhuur (art. 6). LET OP:
die overeenkomst noemt abusievelijk Bergweg 106A in plaats van 116A.

De kernvraag is niet "verkopen of aanhouden" maar: groeit de woning harder dan de beurs?
Bij 7,5% beursrendement ligt het kantelpunt op circa 3,7% waardegroei per jaar. Onder die
grens wint verkopen (bij 2% groei en 7% rendement ca. 25k over 10 jaar), erboven wint
aanhouden - bij 6% groei zelfs met 48k. Optimaal verkoopjaar komt uit de cijfers op
circa 2029 (eerder stond 2031 in het advies). Bij verhuur van de hele woning aan 2
personen delen Daniel en Julian samen de huur; er zitten altijd 2 personen in.

Scenario "Julian eruit" valt uiteen in twee varianten: hele woning aan een huishouden met
een contract = zelfstandig, vrije sector, ca. 1.650 kaal; twee kamers los verhuren blijft
onzelfstandig (WWSO) en dus gemaximeerd op ca. 770 per kamer.

Pitch-dashboard: https://claude.ai/code/artifact/cf6c9700-38b4-4fcc-b280-dccaf4151255
Gedeeld rekenblad: https://docs.google.com/spreadsheets/d/1xw_WnhpG3e9i3xKsNfCgXLp5QvfKc2SNzbbtZrsZ0vk/edit

Hoort bij [[bergweg-investering-broer]] en [[bewijs-voor-claims-klanten]].

---

## -Users-Danie-Downloads / omnivaleur-outreach-machine

*29-09-2026*

De outreach-kant van Omnivaleur (`~/Documents/omnivaleur`) draait autonoom en bouwt het dagvolume voorzichtig op om niet in spam te komen.

- **Dagvolume (sinds 2026-08-21)**: groeit door naar maximaal **50 mails/dag**, maar mag t.o.v. de drukste van de laatste 3 dagen maximaal +10/dag stijgen — een sprong van 30 naar 50 in één dag zou als gekaapt account overkomen. Verzendvenster: 07:45–21:30, minimaal 6 minuten tussen mails. **Nieuwe prospects krijgen 60% van het dagbudget**, opvolgmails 40% (was eerst 40/60 andersom) — expliciete wens van Daniel om meer nieuwe mensen per dag te benaderen, niet meer opvolging.
- Verzending loopt via een apart mail-domein bij Zoho (`omnivaleur.info`), los van het hoofddomein `omnivaleur.com`, met DNS bij Cloudflare en registratie bij Namecheap. Daadwerkelijke verzending loopt via Resend, waar beide domeinen (omnivaleur.nl en omnivaleur.com) correct geverifieerd staan.
- **Sinds 14/15-09-2026 volledig verhuisd van Notion naar Google Sheets/Drive** (map "Omnivaleur" in Drive): twee losse spreadsheets, **Omnivaleur E-mail outreach** (leads, logboek, mailteksten, uitleg — vervangt de oude Notion-Leadlist) en **Omnivaleur Instagram & FB outreach**. Mailteksten komen nu live uit de sheet in plaats van uit code. Supabase (`leadgen_opslag`) blijft de bron van waarheid voor de machine zelf; de sheet is het menselijke overzicht, de tekstbron en de "Niet meer mailen"-stopknop. Notion wordt voor leadgen niet meer gebruikt, alleen nog voor de aparte build-in-public/documentatie-logs, zie [[omnivaleur-notion-docs]].
- Mailbox-indeling: automatische mails (1/2/3) apart, reacties in een eigen map, conversaties in een eigen map — weinig mappen, logische indeling.
- **Reply-workflow (sinds 6-9-2026):** de koude reeks (mail 1/2/3) draait automatisch, maar zodra een lead antwoordt schrijft de machine zelf geen antwoord meer (bewust uitgezet om kosten te besparen). Ze krijgt dan de status "⚡ Jij bent aan zet" of "bal bij hen" op basis van kale tijdstempels uit de Zoho-mailbox (laatste inkomend bericht vs. laatste uitgaand bericht van Daniel), niet op basis van wat er inhoudelijk besproken is. Bekende blinde vlek: dit loopt achter als Daniel via een ander kanaal/adres antwoordde (niet teruggesynchroniseerd naar Zoho) of binnen de laatste 10 minuten (de check draait 1x per 10 min). Het commando **wachtenden** zet voor iedereen die klaarstaat een conceptantwoord in Daniels Zoho-postvak, dat hij zelf beoordeelt en verstuurt.
- Standaardantwoorden aan leads: **€19,99 per maand, eerste 7 dagen gratis, geen opzegtermijn**. Ondersteunde platforms zijn eBay, Shopify, 2dehands, Marktplaats en Vinted (huis-en-tuin/overige categorieën nog niet ondersteund — komt pas als een lead concreet aangeeft welke rubrieken hij nodig heeft). Demovideo: **altijd de leadpagina https://omnivaleur.com/mp-video sturen, nooit de kale YouTube-link** (https://youtube.com/shorts/ymDeS37aBW4). Expliciete wens van Daniel (2026-09-01), geldt voor conceptmails en alle klant-/leadmail; herken de oude YouTube-URL en vervang hem.
- **Affiliate/referral-structuur (besloten 2026-08-20)**: nooit vooraf betalen of per volger. Aanbod is een gratis account plus **30% van wat aangebrachte klanten betalen, 12 maanden lang** (~€6/klant/maand, ~€72/jaar). Bijhouden gaat via Stripe-kortingscodes per partner (bijv. GOUDLIEF10) — Stripe telt zelf hoeveel betalende klanten per code, dat is de hele affiliate-administratie. Uitbetalen blijft handmatig, 1x/maand.
- **Apify**: alleen nodig voor Instagram-accountzoekopdrachten (stilgelegd sinds Daniels Instagram-blokkade) en het "berichten/bereik"-blokje in de zondagsmail. De Marktplaats-leadscraper (beste leadbron) praat rechtstreeks met Marktplaats en heeft Apify niet nodig — betalen voor een hoger Apify-tegoed is dus niet nodig. Concreet cijfer (14-09-2026): 171 IG-leads leverden 0 aanmeldingen op, en het IG-leadgen-commando weigert sinds 2026-09-06 zelfs te draaien — dit ligt dus hard stil, niet alleen "voorzichtig".
- Lopende lead met veel vragen: Egbert Brouwer van Papa's Plectrums — bleek een telfout in de advertentiescan te hebben blootgelegd (totaal werd 3x geteld door paginering); inmiddels gefixt.
- **Bevestigd live (15-09-2026):** de GOOGLE_SHEETS_SLEUTEL staat in Railway, de migratie is echt gedraaid en beide spreadsheets zijn gevuld vanuit Notion: **Omnivaleur E-mail outreach** (512 leads, 8.966 regels logboek, 9 mailteksten) en **Omnivaleur Instagram & FB outreach** (171 leads: 130 Instagram, 41 Facebook). Er is ook een derde tab **Proefperiode** bijgekomen in de E-mail outreach-sheet: toont wie in proef zit, wie een herinnering/laatste waarschuwing kreeg en wie gepauzeerd is (19 gebruikers op 15-09), ververst zichzelf dagelijks om 09:10, betalende klanten staan er bewust niet in en oud-gepauzeerden (>14 dagen) vallen er vanzelf weer af.
- **Video-opvolging is sinds 16-09-2026 niet meer handmatig in Notion, maar automatisch door de machine zelf** (Daniels expliciete keuze: "zonder bugs en gratis, met realtime updates in de spreadsheet"). De sheet heeft een kolom die vastlegt wanneer Daniel zelf de video (altijd https://omnivaleur.com/mp-video) heeft gestuurd; vanaf dat moment stuurt de machine zelf follow-up mail 1 en 2. **Cruciale eis van Daniel: die follow-ups moeten altijd binnen dezelfde e-mailthread/conversatie als zijn eigen video-mail gaan, nooit als losse nieuwe mail** — anders komt de reminder voor de ontvanger "uit de lucht vallen". Zie [[omnivaleur-followup-zelfde-thread]]. Er is ook een los overzicht [mail-opvolging-overzicht.md](docs/mail-opvolging-overzicht.md) dat alle drie mailsystemen (koude reeks, video-opvolging, proefperiode) naast elkaar samenvat, met eerlijk wat per systeem wel/niet bevestigd is.
- **Nieuw kanaal: groothandel-resellers (vanaf 14-09-2026).** Naast het standaard affiliateprogramma is een los, hoger-commissie aanbod verstuurd aan vintage-groothandels die zelf duizenden resellers bedienen (Vintagebulk.nl ~5100 leden + eigen WhatsApp-groep, ONEvintage Wholesale, Wildebras Vintage): eerste maand gratis + 20% doorlopende commissie per betalende klant, in plaats van de gebruikelijke 30%/12 maanden hierboven. **Twee gaten nog open, blokkeren pas als iemand ja zegt:** (1) het systeem geeft nu 7 dagen proef, niet de beloofde maand; (2) er is geen tracking van via welke partner een klant binnenkwam, dus 20%-uitbetaling kan nu niet worden toegewezen. Zie [[omnivaleur-cold-outreach-wetgeving]] voor een aanpalende juridische vraag over koude outreach.

**Leadbronnen uitgeput (18/19-09-2026):** zowel Marktplaats.nl als 2dehands.be zijn voor de huidige rubrieken nu aantoonbaar leeg (voor-en-na-meting: een diepe 2dehands.be-ronde van 656.000 advertenties over 7 rubrieken leverde netto 1 nieuwe lead op). Daardoor droogt ook de instroom van nieuwe aanmeldingen op, dat is uitputting van de bron, geen storing. Onderzochte alternatieven: eBay weigert een simpel verzoek (403) maar laat een echte browser wel door en toont bruikbare verkopersgegevens (gebruikersnaam, zakelijk/particulier, land, soms eigen merknaam als paginatitel) — nog geen proefronde met een script gedraaid, dus onbekend of eBay dat ook op schaal toelaat. Catawiki laat een echte browser ook door maar toont nergens een verkopersnaam of profiel (zij kopen zelf in en verkopen door), dus dat spoor is dood. Nog niet geprobeerd: bedrijvenregister doorzoeken op trefwoorden als vintage/tweedehands/kringloop.
**Repo verhuisd (18-09-2026):** GitHub-repo staat nu op `github.com/danieldk04/omnivaleur` (was `crosslisteu.git`); de oude naam werkte nog via een redirect maar de lokale git remote is al rechtgezet.
**Platforms staan het juridisch niet formeel toe:** zie [[omnivaleur-platform-geen-toestemming]] voor het gebrek aan formele toestemming van Marktplaats en andere platforms voor geautomatiseerd plaatsen, en de sinds 18-09-2026 aangescherpte voorwaarden die dat risico bij de klant leggen.

**Afmeldingen en timing (23-09-2026):** na boze reacties ("stoppen met mailtjes", "spamlijst, blokkeer") telt de machine zulke zinnen nu als afmelding (los woord "spam" bewust niet, "zat in mijn spam" is geen afmelding) en negeert hij geciteerde eigen tekst onder Outlook-antwoorden. Mail 2 gaat pas 7 dagen na mail 1, anders klopt "mijn mailtje van vorige week" niet en voelt het opdringerig. Een lead die "gaat al automatisch" zegt maar wel om de video vraagt of een kanaal noemt, komt onder "jij bent aan zet". Frank (FOTZ vintage) meldde dat de mails in zijn ongewenste mail belandden. De sheet werkt Claude zelf bij, zie [[leadsheet-zelf-bijwerken]].

Toon en opmaak van de mails: zie [[klantcommunicatie-jij-niet-u]]. Leadbronnen staan in de `leadgen`-skill.

**Verzending en nieuwe bronnen (26/27-09-2026):** koude mail gaat sinds 26-09 weer via Zoho (staat zichtbaar in Daniels map Verzonden), niet meer via Resend. Nieuwe leadbronnen naast Marktplaats: webshops en fysieke winkels, gevonden via Google-zoekresultaten van Serper.dev (gratis 2.500 zoekopdrachten, geen betaalkaart; Brave viel af omdat die altijd een kaart vraagt). De wachtrij wisselt webshops en winkels om en om af. Bekende beperking: de GitHub Actions-planning vraagt elk half uur een ronde, maar GitHub start er in de praktijk maar zo'n 2 à 5 per dag; elke ronde haalt de achterstand in, dus mails gaan in groepjes. Referral-idee (27-09): Daniel mailt bestaande betalende klanten persoonlijk vanaf zijn eigen adres, eerst zonder beloning, geen massamail.

**Instagram-DM's (27-09-2026):** volledig autonoom koude DM's sturen via Apify kan niet. Instagram staat koude DM's via de officiële weg niet toe (alleen antwoorden binnen 24 uur), een bot die Daniels account bestuurt wordt snel geblokkeerd, zijn eigen Instagram ligt sinds augustus 2026 al plat na een blokkade, en volgens de ACM geldt voor een DM dezelfde spamregel als voor e-mail. Zie [[omnivaleur-facebook-outreach-grens]].

**Stand 29-09-2026:** Instagram leverde weinig op: 118 accounts benaderd, 6 reacties, 0 aanmeldingen; een Apify-abonnement is het daarom niet waard. Koude mail naar winkels en webshops loopt sinds 28-09 (111 adressen verstuurd, 464 klaar), resultaat pas rond 11-10 te beoordelen. Omdat GitHub de geplande rondes te zelden startte, geeft Daniels Mac sinds 29-09 elk half uur tussen 08:00 en 21:30 GitHub een seintje om een mailronde te draaien.

---

## -Users-Danie-Downloads / klantcommunicatie-jij-niet-u

*29-09-2026*

Alles wat namens Daniel naar klanten of leads gaat — outreach-mails, antwoorden op reacties, productteksten, vertalingen — is informeel geschreven.

**Why:** hij verkoopt aan particuliere resellers en kleine handelaren; "u" en juridische disclaimers voelen daar als spam en afstandelijk. Zijn letterlijke correctie: "naar je, alles naar je. nooit u" en over de afmeld-/KvK-regel: "Dit overal altijd weghalen, dit hoeft echt niet."

**How to apply:**
- Altijd jij/je/jouw, ook in vertalingen naar andere talen (kies de informele vorm: du, tu).
- Ondertekenen met "Groetjes Daniel", niet "Met vriendelijke groet, Daniel de Koning".
- Geen afmeldzin, KvK-nummer of adresregel onder de eerste outreach-mail.
- Controleer vertalingen op blijven staan Engelse of Duitse woorden — dat is er eerder misgegaan.
- **Kort houden.** Expliciet 2026-08-28: "mails moeten sws korter zijn dan dit want dat is veel te lang, ook in de toekomst." Schrap proefperiode-alinea's en uitweidingen; kom snel ter zake.
- **Nog korter en menselijker, aangescherpt 2026-09-05:** "ik wil dat je voortaan altijd kortere en menselijkere mails stuurt." De toonregels die elk mailconcept meekrijgt staan sindsdien op: hooguit 120 woorden, schrijf zoals je praat, korte zinnen, je en jij, en goed nieuws in de eerste zin. Dit is gepusht zodat ook de mailagent zo schrijft. Een klantmail van 200+ woorden is te lang.
- **Tweetalige klantmails/meldingen: eerst Nederlands, dan Engels, gescheiden door een streep/scheidingslijn** — ook de onderwerpregel in die volgorde (bijv. "Over het betaalprobleem, van Daniel / About the checkout problem").
- **Aanhef altijd "Hoi <naam>,", afsluiting altijd "Groetjes,\nDaniel."** Aangescherpt 2026-09-07, geldt voor elke klantmail.
- **Niet het boetekleed aandragen.** 2026-09-07: "trek minder het boetekleed aan, reageer gewoon op zijn mail dat dit is opgelost (dat het niet perse aan mij lag bijv.)." Meld nuchter dat het is opgelost, zonder uitgebreide excuses of schuld naar Daniel toe te trekken. Als de oorzaak deels bij de klant of een externe partij lag, mag dat gewoon feitelijk zo staan. Op 27-09-2026 moest Daniel dit in twee losse gesprekken opnieuw corrigeren ("minder het boetekleed aan trekken", "minder als in we hebben een fout gemaakt"), dus de regel werd niet toegepast: schrijf een storingsmail vanaf de eerste versie zonder "we hebben een fout gemaakt" of "het lag aan ons". Liever één mail met alles erin, zo compact mogelijk, dan meerdere losse berichten.

- **Review- en doorverwijsverzoek aan bestaande klanten (29-09-2026):** persoonlijk, via WhatsApp of mail, eerst oprecht vragen hoe het gaat, dan de vraag of ze iemand kennen. Daniel moest twee keer corrigeren: "persoonlijker" en "korter, en minder nadruk op de problemen". Problemen die een klant had hooguit in één bijzin erkennen, de positieve insteek voorop.

Zie [[omnivaleur-outreach-machine]] en [[daniel-visueel-liever-dan-tekst]].

---

## -Users-Danie-Downloads / overdracht-bij-limiet-zelf-klaarzetten

*29-09-2026*

Als Daniel een lopende klus afbreekt omdat de Claude-limiet bijna op is, wil hij dat de tweede ontwikkelaar het werk hervat zonder dat hij erom hoeft te vragen (29-09-2026, klus voor Toon van De Juiste Toon).

**Why:** hij logt dan uit en wil niet zelf context overdragen; zonder overdracht blijft een klantklus halverwege liggen. Hij moest die dag nog apart om "de prompt voor de andere developer" vragen.

**How to apply:** zet bij zo'n afbreekmoment in één keer klaar: (1) eerst een kort bericht dat Daniel naar de klant kan sturen, (2) een overdrachtsstuk in docs/team-notes.md met oorzaak, wat al gedaan is, lijsten en genummerde stappen, gecommit, (3) meteen een plakklare prompt voor de sessie van de andere ontwikkelaar (begin met git pull, verwijs naar de exacte kopjes in team-notes en kennisbank). Zie [[omnivaleur-drie-rollen-model]] en [[team-notes-cross-account]].

---

## -Users-Danie-Downloads / omnivaleur-huidige-fase-klachten

*28-09-2026*

Stand eind augustus 2026: Omnivaleur heeft ~12 actieve betalende gebruikers en Daniel is dagelijks bezig met het beantwoorden van klachten. Zijn letterlijke woorden (2026-08-29): "ik ben namelijk de hele dag bezig met het beantwoorden van klachten, wil dat niet meer."

**Update begin september 2026:** de betalende basis is gekrompen naar ~5 (meting 2026-09-06) door de aanhoudende storingen; churn is bijna altijd "werkt niet", nooit de prijs. Daniel draait een terughaalcampagne: 26 oud-klanten kregen 2026-09-07 een "het lag aan ons"-mail met 21 dagen extra proef. Mentoradvies 2026-09-08: deze fase niet inzetten op meer leads maar op conversie — een nieuwe gebruiker moet in zijn eerste sessie één advertentie succesvol overzetten. Zie [[omnivaleur-prijs-nog-niet-verhogen]].

**Why:** de klachtenstroom komt niet uit tien hoeken maar uit één kapotte kernstroom die de rest blokkeert. Gemeten 2026-08-29: het verwijderen van een Marktplaats-advertentie mislukt in ~82% van de gevallen, en omdat herplaatsen begint met verwijderen stranden daar ook honderden publicaties. Één zware gebruiker (Jaap / Zilverwebsite.nl, honderden advertenties) veroorzaakt het leeuwendeel van de meldingen; andere terugkerende namen: Egbert Brouwer (Papa's Plectrums, info@papas-plectrums.nl, 4000+ items), Albert Kok (kok modelauto's).

**Actieve supportklanten begin september 2026 (naast bovengenoemde):**
- **Toon** (account `dejuistoon`, bedrijf "De Juiste Toon" / DJT, 5500+ items, geen IT-kennis, communiceert via WhatsApp). Hoog risico: Daniel 2026-09-04 "want anders ben ik hem kwijt". Zijn weekendhulp **Lynn** helpt digitaal mee en appt soms rechtstreeks met Daniel, maar communicatie loopt bij voorkeur via Toon zelf.
- **Amanda Haas** (Marktplaats, Bieden-advertenties zonder vraagprijs).
- Daniels eigen test-/meekijkaccount: **dkresellacademy@gmail.com** op omnivaleur.com. Gebruik dit om fixes op echte accountdata te verifieren.
- **Johan Kist** (Blackbird Guitars, account nieuw 13-09-2026, 24 gitaren van 549-4.500 euro, alleen zakelijk op Marktplaats Pro/Admarkt, verkoopt nergens anders). Kan nog niets publiceren op andere kanalen want bedrijfsgegevens (verantwoordelijke partij/handelsnaam) ontbreken. Call gepland donderdag 17-09-2026, 10:30 — daar moet hij die gegevens invullen.

**Klasse van bug die in sept 2026 meerdere klanten raakte:** een "Cancel"/afbreekknop naast de wachtrijbalk die leek over 1 advertentie te gaan maar de hele wachtrij leegde (Toon: 39 en 93 stuks; Egbert). En de Delist-knop die bij dubbel geimporteerde regels een levende advertentie van het platform haalde. Beide zijn voorzien van een bevestiging met het echte aantal.

**How to apply:**
- Bij Omnivaleur-werk: kies voor betrouwbaarheid en zichtbaarheid van de kernstromen (importeren, verrijken, publiceren, verwijderen/herplaatsen op Marktplaats/2dehands/Vinted) boven nieuwe functionaliteit.
- Zorg dat een mislukking zichzelf verklaart in de foutmelding/logs — "kon niet worden gebruikt" zonder context kostte Daniel dagen giswerk.
- Extensie-wijzigingen worden pas bij gebruikers actief nadat Daniel de nieuwe `.zip` handmatig in de Chrome Web Store uploadt. Dat is telkens het openstaande actiepunt; noem het expliciet en apart als "dit moet jij doen".
- Meet op echte accountdata (opdrachten van de laatste 7 dagen) in plaats van te schatten — dat is wat Daniel vraagt en vertrouwt.
- Bij een klant die "werkt niet / blijft mislukken" meldt: kijk éérst welke extensieversie zijn recente serverfouten dragen. De Chrome Web Store loopt geregeld ~10 versies achter, en klanten hebben vaak twee kopieën naast elkaar geladen (Web Store + handmatig uitgepakt) die allebei opdrachten oppakken en half afmaken — te herkennen aan door elkaar lopende versiestempels in de mislukte scans. Dat verklaarde meerdere meldingen (Egbert, Jaap, Daniel zelf) in aug/sep 2026.
- Marktplaats-verkoop kan Daniel zelf alleen verifiëren via de groene "Verkocht!"-badge in zijn berichtenlijst; een advertentie die daar niet in staat kan hij niet handmatig checken.

**Waar klanten weglekken (meting 27-09-2026, 56 accounts):** koude mail is de beste bron (van 7 aanmelders via koude mail betalen er 3, van ~43 andere aanmelders 2). Alle 5 betalers zetten meer dan 100 artikelen in Omnivaleur; van wie minder inzet betaalt niemand, en 30 aanmelders zetten helemaal niets in. Het lek zit dus ná de aanmelding, bij het eerste importeren, niet bij het vinden van leads.

Zie [[bewijs-voor-claims-klanten]], [[fixes-generiek-voor-alle-gebruikers]] en [[omnivaleur-frontend-voor-leken]].

---

## -Users-Danie-Downloads / geen-kosten-buiten-abonnement

*27-09-2026*

Daniel (23/24-09-2026): "in de basis wil ik sowieso dat het me niks kost", zijn Claude-abonnement mag gebruikt worden, "niks daarbuiten". Ook: steeds terugkerend Anthropic API-tegoed is "op lange termijn wel een probleem".

**Why:** het Anthropic-tegoed liep meermaals leeg (blog revaleur stil sinds 2-9-2026, vijf Omnivaleur-onderdelen stil rond 23-9-2026). Losse kosten stapelen en vallen stil zonder dat hij het merkt.

**How to apply:** kies bij nieuwe automatisering eerst een gratis route: script zonder AI voor het kijkwerk, Claude Code op het abonnement voor het denkwerk, Gemini gratis laag voor AI-functies in producten. Stel betaald API-tegoed alleen voor als er echt geen alternatief is, en zeg dan wat het per maand kost. Zie [[omnivaleur-ai-gemini-eerst]], [[omnivaleur-autonome-bugwachter]], [[token-efficiency-lean]].

**Aanscherping 2026-09-27:** ook geen diensten die een betaalkaart vragen voor een "gratis" tegoed. Daniel liet Brave Search en een betaald Brevo-account vallen; kies een dienst die echt zonder kaart werkt (bijv. Serper.dev) en controleer dat vooraf op de site van de aanbieder.

---

## -Users-Danie-Downloads / omnivaleur-blog-beeld-en-variatie

*26-09-2026*

Op 25-09-2026 klaagde Daniel dat de dagelijkse blog steeds dezelfde soort artikelen en dezelfde app-screenshots gebruikte (ook irrelevante, zoals instellingen of beveiliging). Zijn eisen:
- Beeld: gratis (geen betaalde beeldgeneratie), bij voorkeur zelf opgebouwd in HTML als informatieve kaart per onderwerp. Mag **niet als AI herkenbaar** zijn en moet op de Nederlandse én Engelse site goed werken (eigen NL-kaarten).
- Dashboardplaatje alleen waar het echt past (vergelijkingen, platformcombinaties), niet boven elke gids.
- Onderwerpen: meer variatie, kijken wat concurrenten schrijven, en bij elk artikel de top 3 Google-resultaten meenemen om erboven te komen. Sturing op Search Console-data.

Stand 25-09-2026: alle 112 blogs hebben 1 tot 3 onderwerpkaarten, kerncijferkaart alleen bij echte getallen, nieuwe blogs krijgen ze automatisch. 11 dubbele blogs zouden worden samengevoegd (Daniel zei ja).

**Why:** herhaling en generieke plaatjes ogen goedkoop en spammy; AI-uitstraling schaadt vertrouwen, zie [[omnivaleur-seo-merknaam-probleem]] en [[geen-kosten-buiten-abonnement]].
**How to apply:** bij elke wijziging aan de blogpipeline deze beeldregels en de NL-verplichting ([[omnivaleur-blog-i18n]]) aanhouden; geen stockachtige of AI-gegenereerde plaatjes introduceren.

---

## -Users-Danie-Downloads / autonoom-uitvoeren-niet-vragen

*26-09-2026*

Daniel stuurt bij voorkeur één keer aan en wil dan dat het draait: "ik wil dat je dit allemaal zelf autonoom en automatisch gaat documenteren", "ik hoef nu echt niets meer te doen?", "je mag doen wat je wilt".

**Why:** hij runt meerdere systemen tegelijk (Omnivaleur — het cross-listing product, voorheen "CrossList EU" genoemd — en NEXUS) en heeft geen tijd om per stap te bevestigen. Tussentijds terugvragen kost hem meer dan een verkeerde aanname.

**How to apply:**
- Voer tussenstappen zelf uit in plaats van keuzes voor te leggen; meld achteraf wat je deed.
- Leg resultaten zelf vast (Notion, geheugen, logs) zonder dat hij erom vraagt.
- Meld je actief zodra er iets van hém nodig is: een echte klantreactie, een crash, of een keuze die geld kost.
- Let op zijn usage-limiet: zit die tegen het maximum, dan stoppen en na de reset verdergaan in plaats van doordrammen.
- Geplande/autonome agents die hij klaarzet moeten in bypass-permissions mode draaien, zodat hij niet elke keer zelf hoeft goed te keuren (expliciet gevraagd 2026-09-05 voor de Google Tasks agent).
- Houd de rapportage van zo'n autonome agent extra kort. Daniel klaagde 2026-09-05 dat een simpele takencheck bijna 2500 tokens gebruikte: dat is te veel. Alleen de vier blokjes, geen uitweiding.

**Bijgewerkt 2026-09-24:** Daniel zei "check zelf op een later moment zonder dat ik hoef te vragen" en "check dit morgen voor mij". Iets wat later nog nagekeken moet worden plan je dus zelf in (geplande taak of wakeup) in plaats van het als actiepunt bij hem te leggen.

Er draait sinds 2026-09-05 een autonome agent die openstaande Omnivaleur-taken die alleen Daniel zelf kan doen in zijn Google Tasks lijst "Omnivaleur" zet (skill `omnivaleur-taken`), inclusief checken of hij ze al afgerond heeft en datum vandaag erbij.

**Bijgewerkt 2026-09-14:** ditzelfde geldt voor een korte handmatige stap in een externe UI (bijv. Notion: een nieuwe pagina/database aanmaken en de integratie eraan koppelen). Daniel vroeg expliciet "kan je niet mijn scherm bedienen?" toen hem alleen instructies werden gegeven voor een klusje van 30 seconden. Geef dus niet standaard de voorkeur aan "dit is voor jou sneller dan voor mij", bied liever aan het zelf via computer-use over te nemen (of vraag welke hij liever heeft) zodra dat kan. Let wel op de grens: inloggen zelf (wachtwoord invoeren) blijft altijd bij Daniel, ook als hij zegt "neem maar over" — leg dat kort uit in plaats van het te proberen.

**Bijgewerkt 2026-09-25:** Claude zette als actiepunt "kopieer de Search Console-sleutels van Railway naar GitHub"; Daniel antwoordde in hoofdletters "DIE STAAN AL IN RAILWAY". Zoek dus eerst zelf op waar een geheim of instelling al staat (Railway, GitHub, .env) en regel het overzetten zelf waar dat kan, voordat je het als actiepunt bij hem legt.

---

## -Users-Danie-Downloads / omnivaleur-vinted-marktplaats-autodelist

*26-09-2026*

Vinted geeft Omnivaleur geen signaal bij een verkoop: het systeem leidde een verkoop tot 2026-09-17 af door de kast van de verkoper uit te lezen en te zien welke advertentie was verdwenen, en boekte dat automatisch als verkoop op dat kanaal. Dat bleek een aanname met echte schade: een advertentie die de verkoper zelf ergens anders had verkocht of zelf had weggehaald (niet per se op Vinted) werd toch als "verkocht op Vinted" geboekt en meteen van Marktplaats/2dehands/Shopify afgemeld. Bij klant De Juiste Toon zijn zo op 17-09-2026 twee artikelen (een lederhose en een alpaca winterjas) hard bewijsbaar ten onrechte afgemeld terwijl ze nog gewoon op Vinted te koop stonden; een steekproef van 55 onbevestigde Vinted-"verkopen" sinds 1 september leverde 40 onbewijsbare en 2 bevestigd foute op.

**Wat er sinds 17-09-2026 staat (vervangt de aanpak van 12-13 sep hieronder):**
- Een verkoop komt alleen nog op een kanaal te staan als dat kanaal het zelf zegt (een echte bestelling of een "niet meer te koop"-signaal) óf als de verkoper het zelf bevestigt. Kan geen van beide het bewijzen, dan verschijnt bovenaan het dashboard de vraag "Is dit verkocht?" / "Did this item sell?"; bij "ja" wijst de verkoper zelf het kanaal aan en gaat het artikel pas dan overal af.
- Dit geldt nu ook voor Marktplaats/2dehands bij **zakelijke accounts**: bij die accounts gaf de pagina die Omnivaleur leest om verkopen te herkennen altijd een lege lijst terug, dus een verkoop op Marktplaats of 2dehands zelf werd bij een zakelijk account (zoals Toon) nooit opgemerkt en klanten haalden hun advertentie noodgedwongen zelf overal weg. Sinds 17-09-2026 triggert een verdwenen advertentie bij zo'n account binnen circa 12 uur dezelfde dashboardvraag. Gemeten bij Toon: 21 Marktplaats- en 72 2dehands-vragen verschenen zo in zijn dashboard, gecontroleerd tegen zijn echte lijsten.
- De oude Vinted-route (2026-09-12/13) draaide nog op automatisch afmelden zonder tussenvraag zodra de kast-uitlezing een advertentie miste, met een 10%-veiligheidsrem tegen een kapotte uitlezing (verdwijnt in één keer meer dan 10% van de kast, dan volgt alsnog een vraag in plaats van automatische verwijdering; geverifieerd op Toons kast van 1.140 advertenties). Die automatische aanname zonder tussenvraag is dus vervangen door de bevestig-eerst-aanpak hierboven; de kast wordt nog wel elke 4 uur server-side ingepland uitgelezen, dat deel is ongewijzigd.
- Beperking die blijft staan: de daadwerkelijke verwijdering op Marktplaats/2dehands loopt nog via de eigen browsersessie van de verkoper (de extensie), die moet dus aan staan.

**Why:** klant Toon en de foutieve boekingen bij De Juiste Toon zijn beide op 17-09-2026 gemeld/gevonden; Daniels instructie was weer expliciet generiek ("fix en check met 1000% zekerheid", voor alle klanten). Zie [[fixes-generiek-voor-alle-gebruikers]].

**How to apply:** bij een klantvraag over een gemiste of onterecht geboekte verkoop is het antwoord sinds 17-09-2026 altijd: het gaat via kanaalbevestiging of een dashboardvraag, nooit meer een automatische aanname uit één verdwenen advertentie. Zie ook [[omnivaleur-review-imports-vinted]] voor het spiegelbeeld (iets dat een klant zelf toevoegt), [[omnivaleur-huidige-fase-klachten]] voor de bredere context, en [[bewijs-voor-claims-klanten]] voor hoe dit extern geverifieerd moet worden voor het als bewezen wordt gemeld.

**Aanvulling 25-09-2026:** zet Marktplaats een artikel op "gereserveerd", dan wordt het ook niet automatisch overal afgehaald (reservering is geen verkoop): er komt een dashboardvraag plus een herinneringsmail. Klikt de klant niet op ja, dan blijft het op Vinted/2dehands staan en kan het dubbel verkopen. Bij Toon stonden op 25-09 86 van die vragen open. Bij een klacht "verkocht maar nog online" dus eerst de openstaande vragen van die klant tellen.

---

## -Users-Danie-Downloads / omnivaleur-autonome-bugwachter

*25-09-2026*

Daniels wens (23-09-2026): klantfouten moeten direct en autonoom gerepareerd worden, zonder dat hij een routine hoeft te starten, en zonder kosten buiten zijn abonnement.

Opzet sinds 23-09-2026: een script zonder AI kijkt elke 10 minuten naar echte klantfouten en werk dat vastzit terwijl de klant Chrome aan heeft. Ziet het iets nieuws, dan start het een Claude Code sessie op de Mac (abonnement, nooit API-tegoed) met de vaste werkwijze: oorzaak bewijzen, repareren, testen, live zetten, vastleggen. Max één sessie tegelijk, max acht per dag, wacht als er in de laatste 20 minuten aan de code gewerkt is. Klant-eigen oorzaken (Chrome uit, uitgelogd) een week met rust. De dagelijkse klantfoutenronde om 08:00 blijft als vangnet.

Eerder keek deze starter sinds begin september naar een lege buglijst en werd tegengehouden door losse bestanden in de map, dus hij deed feitelijk niets.

**Bijgewerkt 24-09-2026:** een zelf-gestarte reparatiesessie is nu wel bewezen (meerdere sessies op 24-09). Beperkingen: de wachter draait op de Mac, dus bij slaap of uit staat hij stil en haalt hij daarna het laatste etmaal in; de Claude-inlog op de Mac kan na een paar weken verlopen (gebeurde 23/24-09), dan start hij niets meer en waarschuwt het beheerdashboard. Veel "fouten" blijken klanten met een oude extensieversie (bv. Toon op 1.0.345, Daniel zelf op 1.0.351): check eerst welke versie de klant draait voor je opnieuw gaat repareren. Geplande opdrachten tellen als wachttijd pas vanaf hun geplande moment.

**Why:** Daniel zit vast in support, zie [[omnivaleur-huidige-fase-klachten]] en [[geen-kosten-buiten-abonnement]].
**How to apply:** start deze sessies alleen als de `claude` CLI op de Mac ingelogd is; valt hij stil, check eerst de login. Een echte zelf-gestarte sessie was op 23-09 nog niet bewezen, Daniel logde daarna in.

---

## -Users-Danie-Downloads / leadsheet-zelf-bijwerken

*24-09-2026*

Daniel (23-09-2026): "ik wil dat jij die in de toekomst gaat aanpassen die leadspreadsheet". Aanleiding: statuscorrecties (afgemeld, jij bent aan zet) werden steeds als actiepunt naar hem geschoven met als reden dat de sleutel alleen op de server stond. Dat was niet nodig: de sleutel is zelf van de server te halen en staat nu afgeschermd op de Mac buiten de code (werkwijze staat in de kennisbank van de omnivaleur-repo).

**Why:** hij wil geen klusjes terugkrijgen die de developer zelf kan, zie [[autonoom-uitvoeren-niet-vragen]].
**How to apply:** na een fix in de outreach-machine meteen de betrokken rijen in "Omnivaleur E-mail outreach" bijwerken en teruglezen. Zie [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / omnivaleur-supabase-rls-uit

*23-09-2026*

Op 22-09-2026 kreeg een nieuwe tabel (`platform_notifications`) row level security aan bij het aanmaken zonder policies. Gevolg: GET gaf stilletjes `{total:0}` terug (leek op "geen data" i.p.v. een fout), en de POST/write gaf een 500. Oorzaak: de hele Omnivaleur-backend gebruikt één service-sleutel zonder user-JWT-context en bewaakt toegang zelf via `user_id` in de query, dus alle bestaande tabellen draaien met RLS uit. `schema.sql` heeft nul RLS-statements. Fix was `ALTER TABLE ... DISABLE ROW LEVEL SECURITY;` (moest Daniel zelf draaien, Claude kan geen ruwe SQL op Supabase uitvoeren).

**Why:** RLS-policies toevoegen zou de backend juist blokkeren, want die heeft geen user-JWT om tegen te toetsen — precies het patroon dat de 500 veroorzaakte.

**How to apply:** bij elke nieuwe Supabase-tabel voor Omnivaleur meteen RLS uitzetten, en als een write onverklaarbaar 500 geeft terwijl de read leeg maar foutloos lijkt, eerst RLS-status van die tabel checken voordat je dieper in de applicatiecode zoekt.

---

## -Users-Danie-Downloads / omnivaleur-dashboard-ui-taal-engels

*23-09-2026*

Op 22-09-2026 corrigeerde Daniel dat een nieuw gebouwde Berichten-sectie in het dashboard volledig Nederlandse tekst had ("Berichten & biedingen", "Open op Marktplaats") terwijl de rest van het dashboard Engels is. Is toen vertaald naar Engels ("Messages & offers", "Open on Marktplaats →", "Nothing new").

**Why:** het dashboard is Engelstalig voor alle klanten (niet alleen Nederlandse), Daniel communiceert zelf in het Nederlands maar de productinterface niet.

**How to apply:** bij elk nieuw dashboard-onderdeel (menu-items, kaarten, lege-staat-teksten, tooltips, datumnotatie) standaard Engels schrijven, ook al is de opdracht en het gesprek erover Nederlands. Check voor het live zetten of er geen Nederlandse strings zijn achtergebleven. Zie ook [[omnivaleur-homepage-nl-en-dubbel]] (voor de marketing-site geldt het omgekeerde: daar juist wél beide talen bijhouden).

---

## -Users-Danie-Downloads / claude-code-sandbox-egress-block

*23-09-2026*

Bevestigd 23-09-2026 bij het testen van de NEXUS-tradingbot: StockTwits én Bluesky gaven binnen de Claude Code sessie een 403-blokpagina (herkenbaar aan bunny.net-fonts in de response), terwijl Google News en Yahoo gewoon 200 gaven. StockTwits draait al probleemloos in productie, en Bluesky gebruikt hetzelfde soort publieke endpoint, dus dit werkt wel in GitHub Actions/CI.

**Why:** dit is een netwerkbeperking van de Claude Code sandbox-omgeving zelf, niet van de code of van de externe dienst.

**How to apply:** als een externe API-call binnen een Claude Code sessie een 403/blokpagina teruggeeft terwijl dezelfde call in productie (Railway, GitHub Actions) wel werkt, eerst checken of het een egress-block is (test een bekend-werkende dienst zoals Google/Yahoo als referentie) voordat je tijd steekt in het "repareren" van de eigen code. Zie ook [[nexus-market-terminal]] en [[railway-no-headless-browser]] voor vergelijkbare omgevingsbeperkingen.

---

## -Users-Danie-Downloads / dictafoon-naar-tekst-tool

*23-09-2026*

Daniel heeft een lokale transcriptietool ("dictafoon-naar-tekst") met twee app-iconen: Dashboard.app (opent een browserscherm om transcripties te bekijken) en "Dictafoon naar tekst.app" (sleep-icoontje voor losse MP4-bestanden). De map is verhuisd naar `~/Documents/Handige Scripts Mac`; op 17-09-2026 waren beide app-iconen nog aan het oude, niet meer bestaande pad gekoppeld waardoor een klik niets deed, dat is toen hersteld.

**Why:** dit is Daniels eigen workflow om telefoongesprekken (bijvoorbeeld met klanten als Johan Kist) als tekst in Claude te kunnen gooien.

**How to apply:** bij "het dashboard/de dictafoon doet niets" eerst checken of de map recent verplaatst is en of de twee .app-iconen nog naar het juiste pad wijzen, vóór je dieper in de transcriptiecode duikt. Structuur in het transcript (titel, datum, alinea's) helpt Claude sneller de juiste passage terugvinden bij lange opnames, maar .md versus .txt maakt voor Claude zelf niets uit, dat is alleen structuur.

**Open punt (22-09-2026):** dashboard.py zelf was op enig moment helemaal uit de map verdwenen (geen pad-probleem maar een ontbrekend bestand), geen spoor in Prullenbak of Time Machine. Opnieuw aangemaakt met de werkende inhoud van daarvoor. Als het dashboard vaker "leeg" stukgaat zonder duidelijke oorzaak, eerst checken of dashboard.py nog bestaat voordat je in paden of code duikt.

---

## -Users-Danie-Downloads / omnivaleur-wekelijkse-update-screenshot-regel

*22-09-2026*

De wekelijkse automatische update-mail kan een blokje met een screenshot tonen, maar met harde regels:

- Een link die niet met `https` begint wordt genegeerd in plaats van getoond, tegen kapotte of onveilige afbeeldingen.
- De sessie mag zelf nooit een screenshot verzinnen of een AI-gegenereerd plaatje gebruiken. Alleen een link die Daniel of de developer expliciet aanlevert.
- Wanneer de maandagsessie vindt dat een blokje baat zou hebben bij een screenshot, markeert hij dat blokje met een echt veld ("heeft screenshot nodig"), niet alleen een los zinnetje. Zolang de screenshot er niet bij zit, weigert het systeem dat blokje mee te sturen naar een echte ontvangersgroep. In beheer.html is die waarschuwing al zichtbaar zodra je op "Toon huidige conceptupdate" klikt.
- Er is geen apart belletje of losse melding. De maandagsessie schrijft dit gewoon in dezelfde regel die hij al in `docs/team-notes.md` zet. Daniel of de developer leest dat, maakt de screenshot, en geeft de link door.
- Testmails gaan naar de geregistreerde eigenaar-adressen in het systeem (niet naar het adres waarmee Daniel chat).

**Why:** Daniel vroeg hoe hij weet wanneer een screenshot nodig is en wilde voorkomen dat er per ongeluk tekst-only of een onbetrouwbare AI-afbeelding uitgaat. Puur tekst presteert zwakker dan een echte screenshot, maar automatisch schieten kan niet weten welk scherm bij welke feature hoort.
**How to apply:** stel nooit voor om een screenshot te AI-genereren voor deze mail. Als je een nieuwe feature bouwt die de moeite waard is om te tonen, wijs er zelf op dat een screenshot die update sterker zou maken, in plaats van te wachten op de maandagsessie. Zie [[omnivaleur-monaim-partnership]] voor wie momenteel niet beschikbaar is om die screenshots te maken.

---

## -Users-Danie-Downloads / omnivaleur-monaim-partnership

*22-09-2026*

**Status sinds 21-09-2026: Monaim is momenteel niet actief op Omnivaleur.** Content- en growth-taken (contentschema, screenshots/video's bij de wekelijkse verbinding-update, klantverhalen) niet meer aan hem voorstellen of toewijzen totdat dit wordt teruggedraaid. Tot nader order zijn er twee mensen op het project: Daniel en de andere developer, en alles wat eerder Monaims rol was ligt bij Daniel zelf. Zie [[omnivaleur-wekelijkse-update-screenshot-regel]] voor wie nu de screenshots aanlevert.

**Why:** Daniel gaf dit expliciet aan; reden niet genoemd.
**How to apply:** stel Monaim niet meer voor als uitvoerder van content/outreach-taken totdat Daniel zegt dat hij weer actief is; check bij twijfel team-notes.md op een recentere datum dan 21-09-2026.

Onderstaande beschrijft de oorspronkelijke afspraak van 2026-08-26, nog steeds de basis zodra hij weer actief wordt.

Sinds 2026-08-26 komt **Monaim** als 50/50-partner in bij **Omnivaleur** (alleen Omnivaleur — niet Revaleur, niet zijn eigen e-commercemerk **Somnia**). Ter herinnering: Revaleur is Daniels eigen vintage-kledingmerk, Omnivaleur is de cross-listing-software die daaruit is ontstaan en later een losse SaaS werd.

- **Structuur bewust informeel**: nog geen aandelen/contract. Juridisch vastleggen van de 50/50 komt pas als beide kanten tevreden zijn over hoe de samenwerking loopt.
- **Rol: Growth & Content Partner.** (1) wekelijks Nederlandstalig contentschema TikTok + Instagram (editing uitbesteed), (2) een social-DM-outreachflow ontwerpen/testen voor NL tweedehandsverkopers (parallel aan de koude-mail-leadgen), (3) wekelijkse contentprestaties bijhouden.
- **Prioriteit nu (< 50 gebruikers)** ligt bedrijfsbreed bij dashboard verbeteren, debuggen en feedback verzamelen. Monaims content/outreach loopt daarnaast, niet in plaats daarvan.
- **Paid ads pas vanaf 50 gebruikers.** Eerste fase: alleen kleding/schoenen-verkopers, alleen Europa (bewust weg van US/UK — daar is de concurrentie het hevigst). Organische content mag dubbel als ad-creative; aparte landingspagina's mag. Positionering t.o.v. Channable (groot maar slecht beoordeeld, breed incl. bol.com): Omnivaleur blijft bewust smal — alleen tweedehandsplatforms.
- **Gratis account**: `backend/services/billing.py` kent nu status `complimentary` (onbeperkte toegang, geen stripe-id nodig). Monaim meldt zich normaal aan op omnivaleur.com met eigen e-mail (7-daagse trial-rij), daarna zet Daniel die rij in Supabase op `status = complimentary`. Nooit `status = active` zonder stripe_subscription_id — dat pad is bewust geblokkeerd.
- **Notion**: Monaim krijgt volledige workspace-toegang; sturen op taak, niet op rechten.

**Canonieke bron**: `docs/team-notes.md` in de Omnivaleur-repo (`~/Documents/omnivaleur`) — daar staat de volledige, actuele versie. Zie [[team-notes-cross-account]] voor waarom dat bestand leidend is. Zie ook [[omnivaleur-notion-docs]] en [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / omnivaleur-launch-directories

*21-09-2026*

Daniel heeft Omnivaleur (omnivaleur.com) aangemeld bij Uneed, SaaSHub en AlternativeTo als launchplatform/software-directory. Concurrenten die hij daar opgaf: Crosslist, Nifty, AI Voolist, PrimeLister. Tagline: "List once, publish everywhere."

**Why:** Backlinks en vindbaarheid, zie [[omnivaleur-seo-merknaam-probleem]] (0 backlinks). Reddit is uitgesloten omdat zijn IP daar eerder geband is.
**How to apply:** Stel bij nieuwe promotiekanalen nooit Reddit voor. Bij vragen over backlinks: eerst deze drie als gedaan beschouwen en de status controleren voordat je ze opnieuw voorstelt.

---

## -Users-Danie-Downloads / omnivaleur-notion-docs

*19-09-2026*

**Naming: sinds 2026-09-07/08 is dit niet meer onduidelijk.** Op 2026-08-21 zei Daniel "crosslisteu is voortaan omnivaleur, overal, altijd," wat begin september nog tegengesproken werd doordat de repo op `danieldk04/crosslisteu` stond. Dat is voorbij: in alle sessies van 2026-09-07/08 heet het product naar klanten en leads toe consequent **Omnivaleur** (omnivaleur.com, daniel@omnivaleur.nl, "Omnivaleur-extensie" 1.0.31x, de Gemini-Gem antwoordt met "Omnivaleur"). CrossList EU komt niet meer voor richting nieuwe leads. Ondersteunde kanalen die nu naar buiten worden genoemd: Marktplaats, 2dehands, Vinted, eBay en Shopify (Shopify-koppeling = 3 stappen in het dashboard: winkeladres, eigen mini-app in Shopify-beheer, twee codes overnemen; bij eigen verkoop haalt Omnivaleur het item op de andere kanalen weg).

**Update 2026-09-18: de repo-naam is nu ook echt `omnivaleur`.** GitHub-repo is hernoemd naar `github.com/danieldk04/omnivaleur` (was `crosslisteu.git`); de oude naam werkt nog even via een redirect maar de lokale git remote van `~/Documents/omnivaleur` is al rechtgezet en getest. De eerdere aanname hieronder ("Doe dat niet, er is niets mis met de remote") gold voor de situatie tot 2026-09-04 en is nu achterhaald: de remote wijst terecht naar de nieuwe naam.

**Bewezen 2026-09-04:** de repo-namen `crosslisteu` en `omnivaleur` zijn geen twee repo's maar dezelfde GitHub-repo onder een oude en nieuwe naam; beide wijzen naar exact identieke code. Een andere sessie adviseerde toen ten onrechte om de git-remote van `~/Documents/omnivaleur` "om te zetten" naar de andere naam. Doe dat niet, er is niets mis met de remote.

**BELANGRIJK — repo is verhuisd, maar niet volgens de veilige checklist (geconstateerd 2026-08-26).** De broncode staat niet meer op `/Users/Danie/Documents/crosslist-eu` — die map bevat alleen nog `.claude` en een `backend.log`, geen git-repo meer. De echte code (backend/frontend/extension) staat nu op **`/Users/Danie/Documents/omnivaleur`**. Gebruik dat pad voortaan als startpunt bij Omnivaleur-werk.

Gevolg: de twee geplande taken die nog het oude pad gebruiken zijn **kapot**:
- `daily-notion-documentation-sync` — draait in `/Users/Danie/Documents/crosslist-eu`, kreeg op 2026-08-25/26 `fatal: not a git repository` en liep daarna vast op een permission-prompt (niet-interactieve sessie kan die niet beantwoorden). Er is dus die dag(en) niets aan de Engineering Log toegevoegd.
- `daily-build-in-public-x-posts` — zelfde probleem, twee keer geraakt (2026-08-25 en 2026-08-26): begint met `git log` in `crosslist-eu`, vindt geen repo, en loopt vast op dezelfde permission-prompt voordat hij de X-posts kan genereren.

**How to apply:** de SKILL.md-bestanden van deze twee geplande taken (`~/.claude/scheduled-tasks/daily-notion-documentation-sync/` en `.../daily-build-in-public-x-posts/`) moeten het pad `/Users/Danie/Documents/crosslist-eu` vervangen door `/Users/Danie/Documents/omnivaleur`. Meld dit expliciet aan Daniel als het onderwerp Omnivaleur-documentatie of build-in-public-posts ter sprake komt — hij weet vermoedelijk niet dat dit al een paar dagen stilligt.

**Nog steeds niet gefixt op 2026-09-04.** Beide SKILL.md's wijzen nog naar `/Users/Danie/Documents/crosslist-eu` (dat nog altijd geen git-repo is, alleen `backend.log` + `.claude`). Op 2026-09-03 vroeg Daniel dit opnieuw en uitgebreider: "kan je in notion ook constant blijven bouwen en documenteren in een aparte map wat je en we gedaan hebben, qua code, strategie, etc. voor build in public maar ook voor documentatie. overzichtelijk en verdeeld over meerdere mappen indien nodig. dus na elke sessie wellicht of tijdens?" — hij wil het dus opgesplitst over meerdere Notion-mappen (code én strategie, documentatie én build-in-public), bijgewerkt tijdens of na elke sessie. Dat de bestaande dagtaken al ~10 dagen stilliggen is de eerste te melden actie.

Omnivaleur (FastAPI + Supabase) houdt sinds 2026-08-21 twee doorlopende Notion-pagina's bij onder "📚 Strategic Docs" (id `017a1b02-0432-4b23-b344-d837a4f22b7d`):

- **🛠️ Engineering Log** (id `397b0954-fb72-816a-9067-c7f3b91670f6`) — technisch changelog van codewerk, nieuwste bovenaan, vast format probleem/fix/bestanden/verificatie per entry.
- **📢 Build in Public Log** (id `397b0954-fb72-81e9-85b7-d72933ff0e30`) — X/Reddit build-in-public-strategie, posts, geleerde lessen, status lopende zaken (bijv. Reddit-ban appeal).

Dit gebeurt op twee manieren: een dagelijkse geplande taak (`daily-notion-documentation-sync`) die git-historie van de laatste 24-48u checkt en de logs zelf bijwerkt, én binnen actieve sessies zelf — Daniels expliciete instructie: "ja. ik wil dat je dit allemaal zelf autonoom en automatisch gaat documenteren."

**Why:** hij wil bouwwerk en build-in-public-strategie overzichtelijk vastgelegd zonder dat hij er telkens om hoeft te vragen. Zie [[autonoom-uitvoeren-niet-vragen]].

**How to apply:**
- Naam naar buiten: zie de bijgewerkte "Naming"-alinea boven — niet meer klakkeloos "Omnivaleur" aannemen, bij twijfel vragen.
- Na een sessie waarin echt aan Omnivaleur gebouwd is of een build-in-public-beslissing is genomen: voeg zelf een entry toe aan de juiste log, ook zonder dat Daniel erom vraagt.
- Er is ook een `daily-build-in-public-x-posts`-taak die concept-X-posts genereert met continuïteit via `~/.claude/buildinpublic-history.md` (chronologisch build-in-public-verhaal, geen losse snapshots).
- Er loopt daarnaast een idee om een influencer (via Instagram-DM, "juliusresell") een forever-free account te geven in ruil voor een publieke review — mechanisme: influencer registreert zelf, deelt het gekoppelde e-mailadres, en Daniel zet diens `subscriptions.status` in Supabase op `complimentary`. Sinds 2026-08-26 kent `backend/services/billing.py` die status `complimentary` (onbeperkte toegang, geen stripe-id nodig); `status = active` zonder `stripe_subscription_id` is bewust geblokkeerd. Zie [[omnivaleur-monaim-partnership]] — Monaims gratis account loopt via ditzelfde mechanisme.

Zie ook [[omnivaleur-outreach-machine]] voor de koude-mail/affiliate-kant van hetzelfde product.

---

## -Users-Danie-Downloads / omnivaleur-google-analytics-mcp

*18-09-2026*

Op 15-09-2026 is de Google Analytics MCP-server (uit een losse zip) toegevoegd, met als doel dat Claude zelf rechtstreeks GA4/Search Console-cijfers voor omnivaleur.com kan opvragen in plaats van te moeten vertrouwen op wat er toevallig in `docs/team-notes.md` is bijgeschreven.

**Correctie:** op 15-09 werd hier nog gedacht dat de site zelf geen GA4/Search Console had gekoppeld. Dat bleek onjuist (17-09-2026 gecontroleerd): beide staan al sinds eind augustus 2026 gekoppeld en leveren wekelijkse cijfers, alleen niet doorlopend opgeslagen. Zie [[daniel-focusjaar-onderneming-2027]] voor de actuele cijfers (~247 bezoekers/week, 5 klikken op 199 vertoningen/30 dagen). Dit MCP-spoor lost dus niet "geen analytics" op, maar "Claude kan er zelf niet rechtstreeks bij, moet leunen op verouderde logboek-cijfers".

- `pipx` en de Google Cloud CLI (`gcloud`) zijn op Daniels Mac geïnstalleerd; gcloud is ingesteld op Python 3.13 (de meegeleverde Python 3.14 werkt niet op dit systeem). Staat automatisch klaar via `.zshrc` in nieuwe terminals.
- **Laatste stap staat nog open (nog niet gedaan per 17-09-2026) en moet Daniel zelf doen:** in een nieuw terminalvenster `gcloud auth application-default login --scopes https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform` draaien, inloggen met het Google-account dat toegang heeft tot de omnivaleur.com Analytics-property, en het teruggegeven credentials-pad + Google Cloud project-ID doorgeven. Zie ook [[search-console-chrome-profiel]]: Search Console voor omnivaleur.com zit in een ander Google-account dan het standaard verbonden account, dus check dat bij deze login ook.

**Why:** zonder eigen queryToegang blijft elk vers cijfer voor Claude een greep uit een verouderd logboek in plaats van een live meting.

**How to apply:** zodra Daniel het credentials-pad en project-ID doorgeeft, registreer de server met `claude mcp add`. Tot die tijd heeft Claude geen live GA-queryToegang, maar dat betekent niet dat de site geen analytics heeft: gebruik voor cijfers tot dan de laatst bekende waarden uit team-notes/[[daniel-focusjaar-onderneming-2027]] en zeg erbij hoe oud ze zijn.

---

## -Users-Danie-Downloads / daniel-focusjaar-onderneming-2027

*18-09-2026*

Daniel is eind augustus 2026 afgestudeerd (zie [[daniel-studie-finance-control-cgi]] voor de opleiding zelf) en gaat vanaf 15-09-2026 een jaar volledig focussen op zijn eigen ondernemingen, tot eind 2027. Hij liet via de `daniel-mentor`-skill een strategiedocument bouwen, inmiddels samengevoegd tot één document: "[Omnivaleur en Revaleur: strategie tot eind 2027](https://docs.google.com/document/d/1vqKmbQmbwgM_PCCa9C7Eo3_XZU_D_Hnz6ZoaE9x9Pp4/edit)" in zijn Drive-map "Omnivaleur" (oudere versies/losse documenten zijn op 17-09-2026 opgeruimd, dit is de enige geldige link).

Kerninhoud (peildatum 15 t/m 17-09-2026):
- 3 betalende Omnivaleur-klanten (was 4 op 09-09-2026, dus een terugval van 1). 49 aanmeldingen in 10 weken zonder duidelijke groeilijn; een terughaalgroep van 27 die bijna volledig is weggevallen.
- Omnivaleur-bezoekers: ongeveer 247 per week via GA4, en op Search Console 5 klikken op 199 vertoningen over de laatste 30 dagen. Bijna al het verkeer komt uit koude mail, niet uit content of zoekmachines.
- Revaleur (bijgewerkt op 17-09-2026 met echte cijfers): € 1.517 omzet/mnd, 41,6% marge (€ 1.219 winst/mnd), 356 items voorraad die gemiddeld 123 dagen stilligt. Dat trekt de Revaleur-vloer naar € 15.170/jaar, hoger dan Daniels eigen € 10k-doel; dat moet hij in Q1 2027 bewust rechttrekken.
- Twee doelankers voor eind 2027 (Daniel houdt van de 10x-regel): vloer 30 klanten, stretch 120 klanten, met kwartaalmijlpalen. Persoonlijke tussenmijlpalen per kwartaal toegevoegd, waaronder gewicht in stappen: 103 → 100 → 98 → 97 kg.
- Persoonlijk: hij gaat medio oktober 2026 twee weken naar Noorwegen. Bergweg 116A (zie [[bergweg-investering-broer]]) is meegenomen als financieel obstakel: zolang die schuld op zijn naam staat zit zijn leenruimte vast, wat raakt aan samen kopen met zijn vriendin.

**Correctie op de eerdere aanname (15-09):** GA4 en Search Console staan wél al gekoppeld en leveren al sinds eind augustus 2026 wekelijkse cijfers op, in de productielogboeken (`docs/team-notes.md`). Dat was op 15-09 alleen gecheckt op de lokale ontwikkelomgeving, niet op de server. Het echte gat is dus niet "GA4 koppelen" maar "de cijfers vastleggen": er is geen tabel die ze per week opslaat, dus elk rapport overschrijft het vorige. Zie [[omnivaleur-google-analytics-mcp]] voor het aparte, nog niet afgeronde spoor waarbij Claude zelf rechtstreeks bij GA4 kan (dat is een ander doel: eigen queryToegang voor Claude, niet dezelfde vraag als "heeft de site analytics").

**Nog openstaand:** 4 accountability-vragen uit eerdere mentorsessies (08/09-09-2026) nog niet beantwoord, en er bestaat nog geen doorlopende (per-week opgeslagen) meting van de bezoekerscijfers.

**Why:** dit is de kaders waarbinnen Daniel het komende jaar beslissingen neemt — elke prioriteitsvraag ("moet ik hier tijd in steken") kan tegen deze twee doelankers en de kwartaalmijlpalen worden gelegd.

**How to apply:** bij vragen over prioriteiten, roadmap of "waar moet ik me op focussen" eerst dit document (of de actuele versie ervan in Drive) checken in plaats van from scratch te adviseren. Bij een nieuwe daniel-mentor coachingsessie is dit de lopende context, niet een eenmalig gesprek.

---

## -Users-Danie-Downloads / omnivaleur-onboarding-get-started

*18-09-2026*

Klanten begrepen het dashboard niet: bij Johan Kist stond bij elk kanaal "Auto-detected" en dacht hij dat 83 keer op een grijs kanaalicoon klikken zijn advertenties plaatste, terwijl er niets gepubliceerd werd. Naar aanleiding hiervan is op 17-09-2026 onboarding toegevoegd:

- Nieuwe klanten zien bovenaan het dashboard een "Get started"-lijst van 3 tot 7 stappen die zichzelf afvinkt.
- Een grijs kanaalicoontje opent nu een keuze in plaats van direct te schakelen: "Publish to X" (opent het publiceervenster met dat kanaal al aangevinkt), "Already on X? Paste the link", of alleen "Connect" als het kanaal (eBay/Shopify) nog niet gekoppeld is. Voorheen zette een klik daar een kanaal direct op "live" zonder dat er iets geplaatst was.
- De server weigert nu zelf een kanaal op live te zetten zonder bewijs van een echte plaatsing, ook vanuit een oud openstaand dashboardvenster.
- Uitgebreide Help-pagina met de 5 meest voorkomende vragen: wat de iconen betekenen, wanneer iets echt online staat, waar je per kanaal moet inloggen, waar een zakelijk account vastloopt, en wat Vinted en Facebook anders doen dan de rest.

**Why:** bug-voor-bug repareren loste Johans klacht niet op, het onderliggende probleem was dat niemand hem had uitgelegd hoe het dashboard werkt. Zie [[omnivaleur-frontend-voor-leken]] voor de bredere lijn (UI voor niet-technische resellers).

**How to apply:** bij een nieuwe klant die in de war is over kanaalstatus of wat een icoon betekent, eerst checken of hij de Get started-lijst en de Help-pagina al gezien heeft voordat je een technische storing vermoedt.

---

## -Users-Danie-Downloads / omnivaleur-review-imports-vinted

*18-09-2026*

Plaatst een klant een item rechtstreeks op Vinted in plaats van via Omnivaleur, dan verschijnt het niet automatisch in zijn boekhouding. Omnivaleur controleert zijn Vinted-profiel periodiek (minimaal 4 uur tussen twee controles per verkoper, en alleen als zijn browserextensie recent een "hartslag" heeft gestuurd) en zet nieuwe, onbekende items klaar als voorstel onder het tabblad "Review imports" in het dashboard. De klant moet ze daar zelf met een klik overnemen, het gaat niet vanzelf verder.

**Why:** klant Toon vroeg dit op 17-09-2026 over twee zelf geplaatste items; bevestigd in de servercode (`plan_vinted_scans`, `_store_scan_results`) en rechtstreeks in de database (de items stonden al klaar met status "pending").

**How to apply:** bij een vergelijkbare klantvraag ("ik heb iets op Vinted gezet, wanneer komt dat in Omnivaleur binnen") eerst checken of zijn extensie actief is geweest en verwijzen naar het tabblad Review imports, in plaats van een storing te vermoeden.

---

## -Users-Danie-Downloads / omnivaleur-mail-een-onderwerp

*18-09-2026*

Bij een storingsmail, een klant heeft net een probleem gemeld en het is opgelost, hoort maar één onderwerp: dat die ene storing dicht is. Ander werk dat nog loopt, ook al is het bijna klaar, blijft erbuiten, ook al voelt het transparant om het te vermelden.

**Why:** Daniel bevestigde dit expliciet toen gevraagd werd of lopend Vinted-werk in Henriettes storingsmail mocht ("nee, ik zou het niet doen"). Werk-in-uitvoering vermelden verschuift de aandacht van "dit is opgelost" naar een nieuwe belofte, en dat is precies waar vertrouwen op stukloopt als het uitloopt.

**How to apply:** Eén uitzondering: iets dat de klant sowieso binnenkort zelf ziet en anders als nieuwe storing zou melden (bijvoorbeeld een tijdelijke waarschuwingsbalk in de browser tijdens publiceren) mag je in één zin noemen, dat kost weinig en voorkomt een mailtje terug. Al het overige bewaar je voor een apart bericht met goed nieuws in plaats van een reparatie. Check ook of genoemde versienummers al echt live staan voordat je ze in de mail zet: in dit geval beloofde een conceptmail "verholpen in uitbreiding 1.0.334" terwijl die versie nog niet in de Chrome Web Store stond, dat detail is er toen uitgehaald. Zie ook [[klantcommunicatie-jij-niet-u]] voor de rest van de toon-regels.

---

## -Users-Danie-Downloads / omnivaleur-followup-zelfde-thread

*17-09-2026*

Elke automatische follow-up (bijvoorbeeld na Daniels persoonlijke video-mail, zie
[[omnivaleur-outreach-machine]]) moet in **dezelfde e-mailconversatie/thread** blijven
als het bericht waarop hij volgt, nooit als een op zichzelf staande nieuwe mail.

**Why:** Daniel zei het expliciet en met nadruk: als de follow-up als losse mail
binnenkomt, lijkt de reminder voor de ontvanger "uit de lucht te vallen" — die mist
de context van het eerdere bericht en oogt als spam of een nieuwe cold mail in plaats
van een logische opvolging.

**How to apply:** bij elk automatisch opvolgsysteem (video-opvolging, proefperiode-
herinneringen, toekomstige varianten) controleren of de implementatie reply-headers
(In-Reply-To/References) of het threading-mechanisme van de mailprovider gebruikt om
in dezelfde thread te blijven, in plaats van gewoon een nieuwe mail naar hetzelfde
adres te sturen. Dit geldt als algemeen principe voor elk toekomstig Omnivaleur
mailsysteem, niet alleen voor de video-opvolging waarbij het is uitgesproken.

---

## -Users-Danie-Downloads / daniel-studie-finance-control-cgi

*16-09-2026*

Naast zijn bedrijven (Revaleur, Omnivaleur/CrossList EU) volgt Daniel een hbo-opleiding **Finance & Control** (module POL0103). De toets bestaat uit een portfolio + motivatiebrief en een mondelinge verdediging, het **CGI (criterium gerichte interview)**, gepland op **25 augustus 2026**. Voor het GO-oordeel op zijn portfolio heeft hij al gekregen; het CGI is de laatste stap.

Voor het CGI bereidt hij een presentatie van max. 10 minuten voor over zijn persoonlijke ontwikkeling in jaar 3 en 4, gebouwd als een interactieve HTML-tijdlijn (`timeline.html` / `timeline_1.html` in zijn Downloads-map) met zes momenten: ondernemen → stage → een confrontatie → herstel → toekomst. Twee kernmomenten die assessor Frank de Poorter expliciet had gevraagd: een schaamte-moment (issues rond statuten/OR tijdens een stage bij "DKG") en een trots-moment (Bax Music, toen begeleiding wegviel en het systeem dichtging).

**Why:** dit is schoolwerk, niet zijn bedrijven — belangrijk om niet te verwarren met zakelijke content, en de deadline (25-08-2026) is hard.

**How to apply:** als Daniel het heeft over CGI, portfolio, POL0103, de tijdlijn-presentatie of "school", weet dat dit om deze opleiding gaat. Check bij vervolgvragen de actuele staat van `timeline.html`/`timeline_1.html` in Downloads in plaats van op deze memory te vertrouwen voor de exacte tekst — die was bij het laatste contact nog een concept met geschatte datums (voorjaar 2025 DKG-stage, winter 2025 start Bax Music) die Daniel zelf moest verifiëren.

**Bijgewerkt 2026-09-15:** Daniel is inmiddels afgestudeerd (eind augustus 2026) en is nu volledig overgeschakeld op een focusjaar voor zijn ondernemingen, zie [[daniel-focusjaar-onderneming-2027]].

---

## -Users-Danie-Downloads / sessiestart-context-geen-takenlijst

*16-09-2026*

Daniel vroeg op 15-09-2026 over een automatisch getoond overzicht (recente git-geschiedenis, aan het begin van een sessie): "even kort alles wat staat jij bent aan zet dat moet ik behandelen? maar daar staan al heel veel oude berichten ook in?" Hij las een intern/technisch contextblok als een to-do-lijst voor hemzelf.

**Why:** Daniel is geen programmeur ([[klantvraag-eerst-helemaal-lezen]], CLAUDE.md-rapportageregels) en de scheiding tussen "informatie voor Claude om verder te kunnen werken" en "actiepunten voor Daniel" is voor hem niet vanzelfsprekend zichtbaar, vooral als beide door elkaar op zijn scherm verschijnen.

**How to apply:** als er automatisch technische context wordt getoond (git-log, samenvatting van een vorige sessie, systeemherinnering) en Daniel reageert daarop alsof het een opdracht voor hem is, leg dan expliciet en kort uit dat dit achtergrondinformatie voor Claude is, niet een actielijst — en geef daarna, als hij dat wil, wél een echte, aparte actiepuntenlijst. Voorkom dit waar mogelijk door in eigen rapportages altijd zelf een duidelijk "Actiepunten"-blokje te geven (zie [[rapportage-kort-max-geen-invuloefening]]), zodat hij niet zelf tussen de ruis hoeft te zoeken.

---

## -Users-Danie-Downloads / omnivaleur-versienummer-conflict-concurrent-sessies

*16-09-2026*

Op 15-09-2026 gebruikten twee losse Claude Code sessies allebei versienummer 1.0.333 voor de Omnivaleur-extensie, elk met eigen werk erin. Eén sessie moest dat achteraf rechttrekken tot één eenduidige versie (1.0.334).

**Why:** er lopen structureel meerdere sessies parallel aan de Omnivaleur-repo (zie [[team-notes-cross-account]], [[omnivaleur-drie-rollen-model]]), en `manifest.json` heeft geen automatische lock op het versienummer. Twee sessies die onafhankelijk "de volgende versie" kiezen, kiezen dus soms hetzelfde nummer.

**How to apply:** voor je een nieuwe extensieversie toekent, check eerst wat er al in `dist/` staat én wat de laatst gepushte `manifest.json` op main zegt (niet alleen je eigen werkkopie) — daarna pas een vrij nummer kiezen. Zie je bewijs dat een andere sessie tegelijk aan hetzelfde bestand werkt (bijv. een niet van jou afkomstige commit die net binnenkomt), meld dat expliciet in de rapportage in plaats van het stilzwijgend te overschrijven.

---

## -Users-Danie-Downloads / workspacemcp-onbetrouwbaar

*15-09-2026*

De `workspacemcp` MCP-server (gebruikt voor Google Tasks in de skill `omnivaleur-taken`) staat niet altijd aan. Op twee opeenvolgende ochtenden (14-09 en 15-09-2026) werkte hij één keer goed en gaf hij de andere keer een verbindingsfout, waarna de sessie moest terugvallen op de agenda in plaats van de Tasks-lijst "Omnivaleur".

**Why:** de geplande taak `omnivaleur-taken-ochtend` gaat er stilzwijgend van uit dat de server bereikbaar is; als dat niet zo is komt de rapportage in de agenda terecht met "Omnivaleur:" ervoor in plaats van in Tasks, en kan Daniel op het verkeerde scherm zoeken.

**How to apply:** meld expliciet in de rapportage welke van de twee (Tasks of agenda) die dag daadwerkelijk gebruikt is, zodat Daniel weet waar hij moet kijken. Zie ook de agenda-terugval die al in de `omnivaleur-taken`-skill zelf staat beschreven.

---

## -Users-Danie-Downloads / omnivaleur-klantenservice-ai-uit

*14-09-2026*

Op het Omnivaleur-beheerdashboard stonden secties "Wat de AI je aanraadt" en "Wat ik leer van jouw aanpassingen", plus een Klantenservice-blok bovenaan de Marketing-tab. Op 14-09-2026 bleek: die AI-laag draait sinds ongeveer 6 september 2026 niet meer, en de cijfers in het Klantenservice-blok waren daardoor niet meer actueel. Daniel liet de eerste twee secties helemaal verwijderen; het Klantenservice-blok is ingeklapt onderaan de Marketing-tab gezet (net als de terughaalcampagne), met de inhoud (twaalf openstaande punten, cijfers, themalijst, terugkerende storingen) woordelijk bewaard in `docs/team-notes.md` voordat het van het dashboard verdween.

**Let op, nog niet geverifieerd:** [[omnivaleur-drie-rollen-model]] beschrijft een mailagent (`leadgen_mail.py`/`mail_analyse.py`) die de rol van klantenservicemedewerker vervult. Onduidelijk of "de klantenservice-AI die begin september uit ging" hetzelfde systeem is als die mailagent, of een los dashboard-onderdeel dat daarnaast draaide. Niet aannemen dat het rollenmodel gestopt is zonder dat te checken; wel aannemen dat de dashboard-aanbevelingssectie weg is.

**How to apply:** bouw niet voort op "Wat de AI je aanraadt" of het oude Klantenservice-blok als levende databron. Bij twijfel of de mailagent uit [[omnivaleur-drie-rollen-model]] nog actief draait: navragen of verifiëren via `python3 scripts/mail_analyse.py bugs` in plaats van aan te nemen dat die nog loopt zoals half augustus beschreven.

---

## -Users-Danie-Downloads / daniel-macbook-8gb-ram

*14-09-2026*

Gemeten (14-09-2026): Daniels MacBook M2 heeft 8GB werkgeheugen, vastgesoldeerd op de chip, dus fysiek of via software niet uit te breiden. Bij meerdere taken tegelijk comprimeert en wisselt macOS actief naar schijf, wat de vertraging verklaart die hij merkt. Op het moment van meten was er vrijwel niets "purgeable" (8-28 pagina's), dus een cache-leegmaakscript zou niets oplossen; er is in plaats daarvan een script `geheugen_check.command` gebouwd dat de 15 grootste geheugenvreters in gewone taal toont.

**Opvallend:** meerdere open Claude Code sessies plus de Claude-app zelf kostten in de meting samen zo'n 700MB, meer dan Chrome met al zijn tabbladen erbij.

**How to apply:** als Daniel klaagt dat zijn Mac traag is of vastloopt bij meerdere taken: noem niet "meer RAM erbij zetten" als optie, dat kan niet op dit model. Wel bruikbaar, in volgorde van effect: overtollige Claude Code sessies/tabs sluiten, Safari in plaats van Chrome voor gewoon browsen, opstartitems nakijken in Systeeminstellingen, en `geheugen_check.command` draaien om te zien wat er op dat moment het meeste opeet.

---

## -Users-Danie-Downloads / notion-api-nieuwe-database-beperking

*14-09-2026*

Ontdekt bij het opsplitsen van Omnivaleurs Instagram-leads uit de Leadlist (14-09-2026): de Notion-integratie "Omnivaleur Leadgen" stond gekoppeld aan de Leadlist-database zelf, niet aan de pagina waarop die database staat. Daardoor kon geen nieuwe, losse database via de API worden aangemaakt: de API heeft toegang tot de bovenliggende pagina nodig om daar iets nieuws op te zetten, en die toegang was er niet.

**How to apply:** loop je hier tegenaan bij Notion-automatisering, dan is er geen API-omweg. Vraag Daniel om zelf een nieuwe lege pagina/database aan te maken en de integratie er via Connections aan toe te voegen (30 seconden werk), en geef hem de exacte klikstappen. Pas daarna kan de rest (kolommen, migratie) geautomatiseerd worden.

---

## -Users-Danie-Downloads / notion-geen-tab-sprawl

*14-09-2026*

Bij het bouwen van een overzichtsscherm in Notion (Omnivaleur Leadlist, 14-09-2026) werd eerst een nieuwe tab "Video opvolging" met een eigen kolom toegevoegd. Daniel draaide dat terug: "dit is namelijk een beetje to much", te veel tabbladen maakt een bord onoverzichtelijk in plaats van beter. Er bleek al een tab "Vandaag doen" te zijn die precies hetzelfde deed via het bestaande datumveld "Volgende actie op".

**Why:** Daniel gebruikt een bord niet meer zodra het te veel tabs/kolommen heeft — hij wil in één keer overzicht, niet kiezen tussen schermen. Voor een taak die hij zelf maar om de paar dagen handmatig doet (bijv. leads verplaatsen na een follow-up) is een extra automatiseringslaag niet gewenst: hij sleept liever zelf een kaart of zet zelf een datumveld vooruit dan dat er iets automatisch wordt bijgehouden dat hij niet kan overzien.

**How to apply:** voordat je een nieuw tabblad, kolom of automatisering toevoegt aan een bestaand Notion-bord (of vergelijkbaar dashboard) van Daniel: zoek eerst of een bestaande weergave/kolom het al dekt en stel dat expliciet voor als alternatief in plaats van meteen iets nieuws te bouwen. Bij twijfel: vraag of hij het liever handmatig doet dan automatisch bijgehouden.

---

## -Users-Danie-Downloads / omnivaleur-cold-outreach-wetgeving

*14-09-2026*

Sinds 1 juli 2026 is koud bellen zonder voorafgaande toestemming niet meer toegestaan bij eenmanszaken en zzp'ers: die worden voor deze regels gelijkgesteld met consumenten. Dat is een groot deel van Omnivaleurs doelgroep (Marktplaats/Vinted-resellers, vaak zzp).

**Why:** koud bellen als kanaal valt hierdoor af. Onduidelijk, en nog niet uitgezocht, is of ongevraagde commerciële koude mail naar dezelfde groep juridisch in hetzelfde hoekje valt als koud bellen. Dat raakt direct [[omnivaleur-outreach-machine]], de kern van Omnivaleurs leadgeneratie.

**How to apply:** stel geen koud-bel-kanaal voor als outreach-idee. Bij een grondige juridische toets van de mailmachine: dit is het punt om eerst uit te zoeken, niet aannemen dat mail wel mag omdat bellen niet meer mag.

---

## -Users-Danie-Downloads / search-console-chrome-profiel

*13-09-2026*

Bij een poging (2026-09-13) om Search Console van omnivaleur.com te bekijken via de Claude-in-Chrome-extensie bleek het verbonden Chrome-venster op een ander Google-account/profiel te staan (zenbtw.nl), niet het account met toegang tot omnivaleur.com. De extensie kan zelf niet van Chrome-profiel wisselen en bereikt maar één venster tegelijk.

**Why:** dit kostte een hele sessie aan heen-en-weer proberen zonder resultaat, puur omdat het verkeerde profiel verbonden was.

**How to apply:** vraag bij een Search-Console-taak voor omnivaleur.com eerst welk Google-account daar toegang toe heeft, en vraag Daniel expliciet om dat specifieke Chrome-profiel te openen en op "Connect" bij de extensie te klikken vóór je site-analyse begint, in plaats van blind te proberen en pas daarna te ontdekken dat het verkeerde profiel actief is.

---

## -Users-Danie-Downloads / rapportage-kort-max-geen-invuloefening

*13-09-2026*

Het vaste rapportageformat (wat was er aan de hand / wat is er veranderd / zekerheid / actiepunten, zie CLAUDE.md) is een bovengrens, niet een verplicht in te vullen sjabloon. Bij een klein resultaat — bijvoorbeeld "er viel niets te committen, een parallelle sessie deed het al" — wordt de hele reactie één of twee zinnen, niet alle vier blokjes netjes uitgeschreven.

**Why:** Daniel, 2026-09-12, na een rapportage over een triviale git-check die toch volledig in de vier blokjes was uitgeschreven: "Sla op in je memory. Dat berichten altijd zo kort, duidelijk en compact mogelijk moeten zijn, want dit is te veel tekst voor hetgeen wat je wil zeggen, eigenlijk." Hij wil geen tekst omwille van het format.

**How to apply:** vraag jezelf bij elke rapportage af of het onderliggende resultaat de lengte rechtvaardigt. Grote/onzekere wijziging → volledige vier blokjes. Bevestiging, niets-te-doen, of een kleine controle → comprimeer tot de kern, sla lege of voor-de-hand-liggende blokjes over in plaats van ze op te vullen. Geldt naast [[bewijs-voor-claims-klanten]] en de bestaande stijlregels in CLAUDE.md.

---

## -Users-Danie-Downloads / bewijs-voor-claims-klanten

*13-09-2026*

Claim nooit richting een klant (of in een Zoho-conceptmail) dat een bug "gefixt" is
op basis van het lezen van de code alleen. Draai een echte proef (bijv. een
kunstmatige belasting-test die aantoont dat een 500/524-fout niet meer optreedt)
voordat je het als bewezen feit meldt.

**Why:** Daniel gaf expliciet aan: "ik wil niet weer een fout maken... heb je al
hun mails bekeken en de fouten 100% gefixt?" — eerder was een fix als "gefixt"
gerapporteerd puur op basis van codelezen. Bij klant Jaap bleek dat te vroeg: de
fix zat in de Chrome-extensie en was nog niet bij hem terechtgekomen (Chrome Web
Store-review moest nog door), terwijl bij klant Egbert de fix wél met een echte
test bewezen kon worden.

**How to apply:** twee stappen, altijd apart checken:
1. Is de fix technisch bewezen (test, proefdraai), niet alleen "de code ziet er
   goed uit"?
2. Heeft déze specifieke klant de fix ook echt al (juiste versienummer live,
   deploy uitgerold, Store-update goedgekeurd)? Een bewezen fix voor klant A zegt
   niets over of klant B hem al heeft.
Alleen als beide kloppen mag een conceptmail "opgelost"/"live" zeggen — anders
expliciet formuleren dat de oorzaak gevonden is en de fix onderweg is, zonder het
als voldongen feit te presenteren. Zie ook [[klantcommunicatie-jij-niet-u]].

**Eerst meten, dan pas code wijzigen.** Terugkerende frustratie van Daniel
(o.a. 2026-08-29/30): "Stop met gokken", "ik gok nu twee keer achter elkaar, dat
stopt hier". Bij een onduidelijke oorzaak niet een hypothese-fix uitrollen en
afwachten, maar eerst de échte data ophalen — de foutmelding instrumenteren zodat
hij letterlijk toont wat een externe partij (Shopify, Marktplaats) teruggeeft, of
het opdrachtenlogboek / de database van de betreffende klant uitlezen. Pas
wijzigen als je de oorzaak met echte cijfers of een echte respons hebt vastgepind.

**Daniel vraagt zelf om de sluitende proef op zijn eigen machine.** 2026-09-07:
"Kan je niet testen of dit probleem nu opgelost is met 308? Op mijn computer, dat
je 100% zekerheid hebt." Als een fix in de extensie zit en niet end-to-end te
testen was, draai dan de betreffende code letterlijk in een tabblad op de echte
site met Daniels sessie, met de voor-en-na-proef (oude logica faalt op dezelfde
invoer, nieuwe niet). Dat tilt de zekerheid van ~90% naar ~97% en dat is wat hij
verwacht voordat een klant bericht krijgt.

**Geen extra handelingen bij de klant leggen voor een onbewezen hypothese.**
2026-09-09, over klant Egbert: "Ik wil stoppen met hem valse hoop geven of hem
extra handelingen uit te laten voeren." Vraag een klant dus niet iets te
proberen, opnieuw in te loggen of iets aan te passen om een gok van jou te
testen. Bewijs de oorzaak eerst zelf (meten op Daniels account, de code in een
tabblad draaien), en meld pas iets als het hard is. Bij een echt open vraag van
de klant: kort en eerlijk antwoorden wat wél zeker is, niet doorschuiven naar
een test die de klant moet doen.

**Een diagnose uit een vorige sessie is geen eigen meting.** 2026-09-10, klant
Egbert opnieuw: een eerdere sessie had als oorzaak "Websitevermelding" (link in
advertentietekst kost €9) genoteerd in team-notes; die claim werd overgenomen
in code-commentaar en tests en zag er daardoor uit als vaststaand feit. Op
Daniels vraag "weet je dit echt zeker?" bleek de link zelf nooit gemeten te
zijn, alleen overgeschreven. Onderscheid dus altijd expliciet wat je **deze
sessie zelf hebt gemeten** van wat uit een gecomprimeerde samenvatting,
team-notes of een eerdere sessie is overgenomen — en geef dat verschil ook zo
terug als Daniel om zekerheid vraagt. Overgenomen claims tellen niet mee voor
het zekerheidspercentage totdat ze zelf zijn nagemeten.

**Je eigen database die "gelukt" zegt is geen extern bewijs.** 2026-09-12,
klant Toon: het systeem had 13 zoekertjes als "geplaatst" gelogd met een
Marktplaats-nummer erbij, en dat werd als klaar gerapporteerd. Op Daniels
vraag "weet je dit echt zeker?" bleek dat nog niet gecontroleerd — de eigen
database rapporteert over zichzelf, dat is niet hetzelfde als het artikel
zelf zien staan. Pas na het opvragen van de publieke verkoperspagina op
Marktplaats zelf (buiten de eigen database om) en het vergelijken van de
nummers kon het als bewezen (99%) gemeld worden. **How to apply:** bij een
claim dat iets "online staat" of "geplaatst is" bij een externe partij
(Marktplaats, 2dehands, Shopify, Vinted): controleer dat waar mogelijk via
de publieke/externe kant van díe partij zelf, niet alleen via het eigen
opdrachtenlogboek of de eigen database die "success" registreerde.

---

## -Users-Danie-Downloads / omnivaleur-seo-merknaam-probleem

*12-09-2026*

Diagnose van 2026-09-12: zoek je op "omnivaleur" zelf, dan komt omnivaleur.com niet in de zichtbare Google-resultaten (wel Trustpilot, Chrome Web Store, YouTube, Instagram). Geen indexeringsprobleem en geen handmatige actie in Search Console, sitemap is OK (115 pagina's). Kernoorzaak: zwakke externe merkautoriteit (0 backlinks) plus interne zelfconcurrentie tussen de homepage en `/vs/omnivaleur-vs-vendoo` op dezelfde zoekterm.

**Why:** Daniel zit al langer vast in support/betrouwbaarheid ([[omnivaleur-huidige-fase-klachten]]); dit is de eerste keer dat groei/vindbaarheid concreet is uitgezocht in plaats van alleen bugs.

**How to apply:**
- Twee tekst-edits zijn op 2026-09-12 al doorgevoerd: de titel van de vs-pagina is omgezet naar een titel gericht op de concurrent-naam (Vendoo), en op de homepage staat nu direct onder de H1 een zin die de merknaam expliciet herhaalt.
- Nog open (nog niet gedaan, wel voorgesteld): meer interne links vanuit /blog, /marketplaces, /crosslisting/* met ankertekst "Omnivaleur" naar de homepage, en vermeldingen op AlternativeTo, SaaSHub en Product Hunt om externe backlinks op te bouwen.
- De exacte cijfers uit het rapport (posities 5,7 vs 7,8, "0 backlinks", "Bedoelde je: omnivore") komen uit Google Search Console op een niet-reproduceerbaar moment — die zijn niet zelf geverifieerd, alleen de tekstuele bevindingen (paginatitels, live Google-zoekresultaat) wel.

---

## -Users-Danie-Downloads / email-tekst-per-alinea-kopieerbaar

*12-09-2026*

Wanneer een kant-en-klare mailtekst voor een klant wordt opgeleverd (in een codeblok om te kopiëren), moet elke alinea op één doorlopende regel staan, niet met losse enters halverwege de zin.

**Why:** Daniel gaf op 2026-09-11 aan: "elke keer als ik nu jouw tekst kopieer, dan staat het in soort van heel veel enters. In plaats van de volledige breedte." Tekst met interne regelafbrekingen (bijv. om binnen 80 tekens te passen) plakt in Gmail als kapotte, kort afgebroken regels in plaats van uitvloeiende alinea's.

**How to apply:** schrijf elke alinea van een klantmail als één lange string zonder eigen line-breaks; laat alleen een lege regel tussen alinea's staan. Dit geldt naast de bestaande regels in [[klantcommunicatie-jij-niet-u]] (informeel, kort, Hoi/Groetjes) — dit is puur een opmaak/plak-detail, geen inhoudsregel.

---

## -Users-Danie-Downloads / garmin-coach-project

*12-09-2026*

Daniel heeft een eigen "Garmin coach" webapp: haalt live data op uit Garmin Connect (gereedheid, HRV, slaap, Body Battery, stappen) en laat Gemini daar in een chat vragen over beantwoorden ("hoe was mijn slaap deze week"). Lokaal repo: `~/Documents/garmin-coach`. Er is ook een MCP-server `garmin-coach` (tools als `mcp__garmin-coach__dag`, `__slaap`, `__conditie`, `__trend`) die dezelfde live Garmin-data direct in een Claude-sessie ophaalt.

**Why:** dit is Daniels eigen kwantificeerde-zelf-project, los van Omnivaleur en NEXUS. Hij wil zijn cijfers overal kunnen zien zonder dat zijn Mac aan hoeft te staan.

**How to apply:**
- Sinds 2026-09-11 draait de app op Render (`https://garmin-coach-jbe3.onrender.com`), niet meer alleen lokaal op de Mac. Achter een toegangscode die Daniel zelf in Render heeft ingesteld (`TOEGANGSCODE`-env-var), die ik niet ken.
- Gratis Render-laag slaapt na 15 minuten stilte; eerste request daarna duurt ~30 seconden.
- Garmin-sessietoken staat in de env-var `GARMIN_TOKEN_JSON` op Render. Bij het verversen daarvan: nooit met de muis uit een terminal selecteren (het `%`-teken dat macOS eindregels toont breekt de JSON), altijd via het script `scripts/toon_token.py` dat rechtstreeks naar het klembord kopieert.
- Op het beginscherm draait een widget gebouwd met **Scriptable** (gratis, generieke app, geen account nodig — het enige haalbare alternatief op iOS omdat een widget altijd een app nodig heeft om te verversen). Stijl: drie ringen naast elkaar zoals de app "Bevel" — Belasting (oranje, stappendoel), Herstel (groen, gereedheidsscore), Slaap (blauw, slaapscore). Meerdere layouts ingebouwd, te kiezen via een `LAYOUT`-variabele bovenin het script: `"ringen"`, `"compact"`, `"cijfers"`.
- Zie [[credentials-never-in-memory-or-chat]] voor het OAuth-tokenlek tijdens dit werk.

---

## -Users-Danie-Downloads / klantvraag-eerst-helemaal-lezen

*11-09-2026*

2026-09-10, klant Toon: Daniel deelde een screenshot met daaronder een losse
tekstregel van de klant. Er werd gereageerd op de foto (leken er dubbele
advertenties te staan) zonder de bijschrift-tekst onder de foto te lezen. Daniel
vroeg: "is idt echt antwoord op zijn vraag?" — het antwoord bleek op de verkeerde
vraag te zijn: de klant vroeg niet of iets dubbel stond, maar wanneer net
ingeladen Vinted-advertenties doorstromen naar de andere kanalen. Er was al een
half uur gemeten op de verkeerde vraag voordat dit opviel.

**Why:** een verkeerd geïnterpreteerde vraag leidt tot een technisch correct
maar inhoudelijk nutteloos antwoord, en kost meettijd die overgedaan moet
worden. Bij screenshots zit de eigenlijke vraag soms in bijschrift-tekst onder
of naast de afbeelding, niet in de afbeelding zelf.

**How to apply:** bij elke klantvraag, zeker met een screenshot erbij:
1. Lees eerst alle tekst die erbij staat (bijschrift, losse regel, e-mailtekst),
   niet alleen de afbeelding.
2. Zeg voor jezelf (of expliciet terug) welke vraag je gaat beantwoorden, vóór
   je begint te meten.
3. Klopt het antwoord niet met de vraag zoals de klant hem stelde, geef dat
   direct en zonder omhaal toe — zie ook [[bewijs-voor-claims-klanten]] voor de
   bredere regel over zekerheid vóór claims.

---

## -Users-Danie-Downloads / outreach-schrijfstijl-menselijk

*11-09-2026*

Expliciete opdracht van Daniel (2026-09-10, bij het schrijven van DM's voor het
[[omnivaleur-tiktok-creator-programma]]): "vermenslijk, kijk hoe echte mensen
schrijven en neem dit op in je memory. zoek echt op hoe echte mensen schrijven en
hoe cold emailing het allerbeste aanslaat volgens betrouwbare bronnen en case
studies en pas toe."

**Wat er mis was met de eerste versie:** te net, te lang, te gelijkmatige
zinslengte, en het product werd gepitcht vóór het probleem werd genoemd. Volgens
Gong-onderzoek (cold email data) kost dat laatste tot 57% van de reacties.

**Hoe toe te passen, voor elke outreach-tekst (cold mail én DM's):**
1. Open met iets specifieks en persoonlijks over de ontvanger, niet met de
   afzender of het product.
2. Noem het probleem/de herkenning vóórdat het product ter sprake komt.
3. Varieer zinslengte, vermijd de nette opsomming-toon; schrijf zoals iemand
   typt, niet zoals een huisstijl-sjabloon.
4. Sluit af met een lage-drempel-vraag (bijv. "zal ik er een voor je
   klaarzetten?"), geen harde CTA.
5. Zoek bij twijfel actief naar recente cold-email/case-study-bronnen in plaats
   van op stijlgevoel te vertrouwen — dat is wat Daniel expliciet vroeg.

Geldt naast de bestaande regels in [[klantcommunicatie-jij-niet-u]] (jij niet u,
geen KvK-footer): dit gaat specifiek over de opbouw en toon van een eerste
outreach-bericht, niet over lopende klantcommunicatie.

---

## -Users-Danie-Downloads / omnivaleur-tiktok-creator-programma

*11-09-2026*

Naast de bestaande koude-mailmachine ([[omnivaleur-outreach-machine]], 30% affiliate
12 maanden) draait sinds 2026-09-10 een tweede, apart wervingskanaal: TikTok-creators.

**De afspraak:**
- Gratis account zolang de creator actief is (normaal 19,99/maand).
- **25 euro per abonnee die via de creator binnenkomt en na 60 dagen nog betaalt**
  (niet 30%/12 maanden zoals bij het koude-mail-affiliateprogramma).
- Alleen waar het moet: 50 tot 75 euro per video, voor maximaal 5 creators. Hard
  risico dus maximaal 375 euro. Uitgangspunt: start iedereen op puur
  prestatiebasis, betaal pas vooraf als iemand aantoonbaar bereik levert en er zelf
  om vraagt.

**Waar het staat:**
- Doellijst: `scripts/output/leads/creators_tiktok.csv` (219 verkopers, 98
  Nederlandstalig, gesorteerd op bereik) en `creators_tiktok.json` (alle 750
  gevonden creators inclusief afvallers).
- Notion-pagina **"Influencer Marketing"** (apart van de bestaande Leadlist onder
  "Instagram & FB Outreach", want dat kanaal gaat over koude mail, dit over
  creator-afspraken): https://app.notion.com/p/3d6b0954fb7281f2af9dd034be57cf26,
  met database **Creator Outreach (TikTok)**, kolommen Status/Benaderd
  op/Notities.
- Meetlaag: Supabase-tabellen `referral_codes`, `referrals`, `referral_clicks`.
  Link-vorm `omnivaleur.com/r/<code>`. Attributie blijft 60 dagen hangen vanaf
  eerste betaling; commissie valt automatisch terug naar €0 zodra de klant
  opzegt (elke keer opnieuw tegen de echte abonnementstatus gecheckt, niet
  eenmalig vastgelegd).
- Voor de top-10 creators (Cecile Keep, Larissa, XD Vintage, e.a.) liggen codes al
  klaar.

**Schrijfstijl voor de outreach-berichten naar creators:** zie
[[outreach-schrijfstijl-menselijk]].

**Status 2026-09-10:** alles gebouwd en op de echte database bewezen, nog niemand
benaderd. Advies was: deze week starten, in golven van vijf, en eerst het
activatielek repareren (19 van 27 proefaccounts hadden nul artikelen) voordat er
extra verkeer bij komt.

---

## -Users-Danie-Downloads / omnivaleur-support-call-link

*10-09-2026*

Boekingslink voor support- en feedbackgesprekken met klanten van Omnivaleur:
`https://calendly.com/omivaleur/supportcall-omnivaleur`

Let op: de slug is `omivaleur` (zonder de tweede "n"), niet `omnivaleur`. Daniel
gaf deze link op 2026-09-09 nadrukkelijk als de juiste door ("gebruik deze!!!"),
gebruik hem letterlijk en verzin er geen nette variant bij.

Sinds 2026-09-09 staat er in het beheerdashboard rechtsonder een prominente
founder-knop ("Talk to the founder") die deze Calendly-agenda opent. Hij ligt
bovenop het betaalscherm en het extensie-installatievenster, en verdwijnt zodra
er een echt werkvenster opengaat.

Openstaand op 2026-09-09: de klantenservice-Gem (Gemini) en de kopie van het
klantenservice-brein in Google Drive kennen deze bellink nog niet.

Sluit aan op [[omnivaleur-huidige-fase-klachten]] (Daniel wil rijkere
klantfeedback) en het toekomstplan [[omnivaleur-premium-doneforyou-plan]]; de
losse notitie over calls belonen met extra toegangsdagen staat in de
omnivaleur-repo-memory (`klantcalls-incentive-idee`).

---

## -Users-Danie-Downloads / omnivaleur-homepage-nl-en-dubbel

*07-09-2026*

De Omnivaleur-marketingsite draait op `omnivaleur.com` (Engels, `index.html`) en
`omnivaleur.com/nl` (Nederlands, `nl.html`). Het zijn twee losse bestanden, geen
gedeelde template. Er is ook een Nederlandse videopagina `/mp-video`. Taalknop
`[EN|NL]` staat in de menubalk naast Inloggen en "7 dagen gratis". Google weet via
`hreflang` en de sitemap dat `/` en `/nl` dezelfde pagina in twee talen zijn, dus
`/nl` heeft geen aparte Search Console property nodig.

**Why:** Daniel bracht deze staande afspraak expliciet aan (2026-09-07): "elke
toekomstige tekstwijziging aan de Engelse homepage moet je ook op de Nederlandse
laten doen, want het zijn twee losse bestanden ... onthoud dit in teamnotes, dat
jij dat doet wanneer ik wijzigingen aanbreng op de engelse homepage." Staat ook in
`docs/team-notes.md`.

**How to apply:** zodra Daniel een tekstwijziging aan de Engelse homepage doorgeeft
of doorvoert, breng in dezelfde sessie diezelfde wijziging vertaald aan in
`nl.html` (en `/mp-video` als het die tekst ook raakt). Hij hoeft er niet apart om
te vragen. Het dashboard blijft bewust Engels tot het stabiel is; dat wordt in één
ronde vertaald zodra er een week alleen kleine bugs zijn opgelost.

Zie [[klantcommunicatie-jij-niet-u]] en [[omnivaleur-huidige-fase-klachten]].

---

## -Users-Danie-Downloads / omnivaleur-premium-doneforyou-plan

*06-09-2026*

Idee besproken 2026-09-05 na een call met Naoufal van De Juiste Toon (bedrijf
`dejuistoon`, zie [[omnivaleur-huidige-fase-klachten]]): een betaald premium
"done-for-you" plan bovenop de standaard 19,99, richtprijs rond 59 euro per maand,
voor klanten die geen zin of kennis hebben om zelf een laptop aan te houden en de
extensie bij te werken. In de zwaarste vorm draait Omnivaleur dan een machine voor
de klant zodat er niets lokaal aan hoeft te staan.

**Besluit (Daniel, 2026-09-05):** niet nu bouwen. Eerst meten hoeveel van de
huidige supportlast puur komt door een oude extensieversie of een dichtgeklapte
laptop, want dat is met code op te lossen zonder serverkosten. Pas als die groep
weg is, blijkt hoeveel klanten echt een gehoste machine nodig hebben en of 59
euro daarvoor klopt. "dat nieuwe pricing plan komt later."

**Wat er al voor klaarstaat:**
- Kolom `ext_version` toegevoegd aan `extension_heartbeat` in Supabase (Daniel,
  2026-09-05), zodat per klant de live draaiende extensieversie meetbaar wordt.
- Meetscript `scripts/tel_extensieversies.py` in de omnivaleur-repo, ook met de
  hand te draaien.
- Geplande controle maandag 2026-09-07 19:00 die kijkt of klanten vanzelf op de
  nieuwe Web Store-versie zijn gekomen en de uitkomst vastlegt, ook bij slecht
  nieuws.

**How to apply:** komt het premium/done-for-you plan weer ter sprake, check eerst
de uitkomst van de versiemeting voor je aanneemt dat het nodig is. Zie
[[omnivaleur-outreach-machine]] voor de standaardprijs en [[omnivaleur-frontend-voor-leken]].

---

## -Users-Danie-Downloads / mac-opslag-cleanup

*02-09-2026*

Daniel gebruikt CapCut op zijn MacBook M2 voor videoprojecten; volle schijf blokkeerde export-functionaliteit. Grootste boosdoeners waren geen apps/projecten, maar drie doorgroeiende logbestanden (~10 GB) en browser/download-caches (~18 GB).

- Er staat nu een script in de map **Handige Scripts Mac**: **"💾 SCHIJFRUIMTE VRIJMAKEN - dubbelklik"**, dat logs en caches opruimt zonder apps, projecten of documenten aan te raken. Draai dit opnieuw als de schijf weer krap wordt — de logbestanden lopen vanzelf weer vol.
- Daniel gebruikt **Google Drive voor desktop in streaming-modus** (niet lokaal) voor zijn **zakelijke** Drive. Oude Downloads-bestanden (studie, video, documenten, installatiebestanden, etc.) zijn ondergebracht in **Mijn Drive → Mac Archief**, met 10 genummerde submappen; persoonlijke foto's zitten apart in een eigen map zodat ze niet tussen zakelijke bestanden staan.
- Let op: **Desktop en Documents mag met Google Drive blijven synchroniseren** (kleine mapjes, kost geen ruimte, gratis back-up). **Downloads moet júist uit die sync** — dat is zijn rommelmap en dubbel synchroniseren daarvan kost extra schijfruimte zonder voordeel.
- CapCut's eigen cache wordt bewust niet opgeruimd — kans dat projecten daar media uit halen.
- Losse grote downloads die bij een volle schijf veilig weg kunnen (bevestigd 2026-09-01): oude installatiebestanden zonder gebruik (bv. Parallels/Windows-installer ~4,9 GB, geen enkele VM draait) en de DaVinci Resolve-geluidsbibliotheek (~1,5 GB) mits die effecten niet gebruikt worden. Google-profielen niet opschonen — dat wil Daniel niet.

**Why:** dit is zijn vaste patroon voor opslagbeheer; bij een volgende "schijf is vol"-vraag hoeft niet opnieuw from scratch onderzocht te worden waar de ruimte zit.

**How to apply:** verwijs eerst naar het bestaande script en de Mac Archief-structuur in Drive voordat je opnieuw handmatig gaat opruimen of nieuwe mappen aanmaakt.

---

## -Users-Danie-Downloads / token-efficiency-lean

*02-09-2026*

Werk in elke sessie zo lean en efficiënt mogelijk met tokens en de usage-limiet.
Dit is een staande instructie, niet iets voor alleen bij een bijna-volle limiet.
Daniel gaf het expliciet (2026-09-01), onderbrak zijn eigen bericht om het te
herhalen, en zei het meermaals binnen dezelfde dag ("check even, heel lean want
heb nog maar 8% limiet", "doe de test lean", "zoek op hoe je dat kan doen en pas
dat toe dat je de meest efficiente AI bent"). Hij wil deze skills/gewoontes rond
efficiëntie én zekerheid overgenomen zien in al zijn developer-setups, niet maar
in één project.

**Why:** hij runt meerdere systemen tegelijk (Omnivaleur, NEXUS, videoknipper,
blogs, leadgen) en botst geregeld tegen zijn usage-limiet. Verspilde tokens =
minder werk dat af komt voor hij moet wachten op de reset.

**How to apply:**
- Lees gericht: alleen de regels/bestanden die je nodig hebt, geen hele grote
  bestanden "voor de zekerheid". Gebruik Grep/Glob i.p.v. brede reads.
- Batch onafhankelijke tool-calls in één bericht; geen stap-voor-stap heen en weer.
- Geen statuspolls na het starten van achtergrondwerk — wachten op het bericht.
- Zet zwaar of langlopend werk in de achtergrond i.p.v. het uit te zitten.
- Rapporteer bondig in de vier vaste blokjes; geen herhaling, geen uitweiding.
- Zit de limiet tegen het maximum: stoppen en na de reset verder, niet doordrammen.
- Zit hij hoog (bijv. 89% van de weeklimiet) en is er nog werk over: het restant
  mag naar de tweede ontwikkelaar via een gedateerde notitie onderaan
  `docs/team-notes.md` (zo escaleerde Daniel op 2026-09-01). Rond zelf alleen het
  stuk af dat echt nu moet, zet de rest daar klaar met alles wat nodig is.
- Lean gaat nooit ten koste van zekerheid: aanname meten, oorzaak bewijzen, echt
  draaien blijft staan — doe het alleen met zo min mogelijk stappen.

Zie [[autonoom-uitvoeren-niet-vragen]] en [[bewijs-voor-claims-klanten]].

---

## -Users-Danie-Downloads / videoknipper-tool

*02-09-2026*

Tool in `/Users/Danie/Documents/Handige Scripts Mac/`: `videoknipper.py` (de
knipper) + `dashboard.py` (webinterface). Knipt een lange, stille opname (Daniels
studio-/magazijnbeeld voor Revaleur-content) terug tot een korte montage van de
momenten waarop er echt iets gebeurt. Werkt volledig lokaal — alleen ffmpeg,
python, numpy; geen internet, sleutel of abonnement.

- **Interface:** dashboard draait als launchd-service `com.danie.videoknipper`
  (`~/Library/LaunchAgents/com.danie.videoknipper.plist`, RunAtLoad + KeepAlive),
  bereikbaar op `http://127.0.0.1:8777`. Video's erin via de map `Aangeleverd/`,
  resultaat in `Geknipte videos/`, logs in `logboek/`. Ook te draaien via
  `🎬 VIDEO KNIPPEN - dubbelklik.command` of `python3 videoknipper.py <bestand>`.
- **Wat het eruit filtert (stand 2026-09-01):** camerabewegingen/zwenken (met
  0,6s nasleep), wazige beeldjes (scherpte op groter raster gemeten), en
  wiebelig beeld. Grenzen zijn relatief aan de video zelf (het waziste/onrustigste
  kwart valt af), niet vaste getallen. Het dashboard meldt hoeveel % van de bron
  camerabeweging was.
- **Echte looptijd (gemeten 2026-09-01, niet geschat):** een video van 15 min /
  2,5 GB kostte ~115s analyse en ~4,5 min inclusief het knippen zelf. De eerdere
  schatting "~15s per 3 min", doorgerekend vanaf een korte testvideo, klopte niet
  en is precies de fout waar "meten, niet aannemen" tegen bedoeld is. Zwaardere
  bestanden schalen niet lineair; meet per video.
- **Openstaand idee:** filteren op *waar* de beweging zit (midden vs. rand van
  beeld), zodat een hand die het beeld in schuift niet meer als "moment" telt —
  dit trof ~4 van 21 fragmenten in de kwartiervideo.
- **Bekende valkuil:** een launchd-service krijgt een kaal PATH; ffmpeg wordt nu
  zelf opgezocht i.p.v. via PATH. Slepen naar `Aangeleverd/` checkt eerst op naam
  + grootte voor het kopieert (schijf zit vaak >95% vol).

**Let op:** de map staat NIET in git en zit in geen back-up. Wijzigingen die
Daniel wil bewaren moeten naar iCloud of een schijf. Verbeteringen gaan van zijn
abonnement af — melden in de vier vaste blokjes, en meten op eigen testmateriaal
met ingebouwde fouten, niet alleen beredeneren.

Zie [[mac-opslag-cleanup]], [[railway-no-headless-browser]] en
[[bewijs-voor-claims-klanten]].

---

## -Users-Danie-Downloads / omnivaleur-drie-rollen-model

*01-09-2026*

Sinds 2026-08-29 heeft Daniel de support-organisatie van Omnivaleur vastgezet in drie rollen. Zijn letterlijke woorden: "ik ben de ceo, de mailagent de klantenservice medewerker en claude code de developer. onthoudt dit, want dit verandert niet."

- **Daniel = CEO.** Wil geen tijd meer kwijt zijn aan het schrijven van mailtjes in Concepten of het checken van dubbelingen. Ziet in Concepten alleen nog de juiste, volledige mail — één per klant, reagerend op het laatste bericht.
- **De mailagent (`scripts/leadgen_mail.py` + `scripts/mail_analyse.py`) = klantenservicemedewerker.** Analyseert alle in- en uitgaande post, houdt marketing-/bugprogressie bij in het dashboard, zet concepten klaar (verstuurt nooit zelf), en escaleert naar Daniel alleen bij: geld, een klant die dreigt te stoppen, een storing bij meerdere klanten, of iets wat de agent niet kan onderbouwen.
- **Claude Code = developer.** Elke developer-sessie begint verplicht met `python3 scripts/mail_analyse.py bugs`. Storingen met de vlag `MOET ZEKER` (2+ melders, of iemand is boos/dreigt te stoppen) worden opgepakt.

**Why:** Daniel zat de hele dag in de klachtenafhandeling en wil dat de twee agents dat onderling oplossen zonder hem, tenzij het echt bij de CEO hoort. Zie [[omnivaleur-huidige-fase-klachten]].

**How to apply:**
- Mailagent ↔ developer communiceren rechtstreeks via twee kanalen in `mail_analyse.py`: `stand_van_de_storingen()` (developer → concept) en `bericht_over_reparaties()` (developer → klant).
- Repareert de developer een bug met zekerheid, dan meldt hij dat terug met `python3 scripts/mail_analyse.py opgelost <sleutel> "wat er nu anders is"` (of `afgewezen <sleutel> "reden"` als het geen storing bleek). Pas dán past de mailagent de concepten aan en krijgen de melders bericht.
- Er is geen automatische trigger die Claude Code wakker maakt bij een binnenkomende mail — het gat tussen mail en Daniels volgende sessie blijft bestaan tenzij hij een aparte starter-taak laat bouwen.
- Zet bevindingen als gedateerde notitie onderaan `docs/team-notes.md`.
- Vertrouw door de mailagent gegenereerde "feiten" niet blind — vooral namen.
  De agent had klant Zilverwebsite.nl "Ronald" genoemd; dat werd als feit in
  team-notes overgenomen terwijl hij Jaap heet (2026-09-01 gecorrigeerd).
  Controleer een klantnaam tegen de echte mailwisseling voor je hem gebruikt.

Zie [[bewijs-voor-claims-klanten]], [[fixes-generiek-voor-alle-gebruikers]] en [[klantcommunicatie-jij-niet-u]].

---

## -Users-Danie-Downloads / omnivaleur-frontend-voor-leken

*01-09-2026*

Alles wat een Omnivaleur-gebruiker zelf moet doen in de frontend moet kunnen zonder technische kennis.

**Why:** Daniels gebruikers zijn particuliere resellers en kleine handelaren, geen developers. Terugkerende instructie (2026-08-29): "dit kan voor sommigen nogal als een stap voelen, kan je dit versimpelen voor ze? maak ook de frontend beter hierin." Bij het Shopify-koppelscherm werkte dit: één muur tekst → drie schermpjes met voortgangsbalk, kopieerknop voor de rechten, en een knop die rechtstreeks naar de juiste pagina van de eigen winkel deeplinkt.

**How to apply:**
- Knip elke handeling van meer dan één stap op in losse schermpjes met een voortgangsindicatie; per scherm één ding vragen.
- Waarden die geplakt moeten worden: kopieerknop, niet los overtikken.
- Link rechtstreeks door naar de juiste pagina in de winkel/het account van de gebruiker in plaats van "zoek zelf naar...".
- Benoem vooraf wat de gebruiker straks ziet (bijv. "Shopify toont daarna alleen de write-rechten, dat klopt") op de plek waar mensen anders vastlopen.
- Lege verplichte velden: toon netjes waarom, en zet onderaan een "vastgelopen? mail me, dan doen we het samen".
- Test zelf door het venster in een browser en klik alle stappen, de terugknop en het telefoonformaat door.

**Terugkerende klacht: geen mobiele app.** Meerdere gebruikers (o.a. Joerp, Dave
Klaassen — jul/sep 2026) haken af omdat ze foto's steeds naar de laptop moeten
overzetten. Er komt voorlopig geen app: de Chrome-extensie is nodig om te
publiceren en die kan niet op mobiel. Standaardantwoord: open omnivaleur.nl op je
telefoon (of zet hem als app op je beginscherm) en maak daar het item met foto's
rechtstreeks vanuit je camerarol aan; alleen het publiceren op de kanalen doe je
later op de laptop. Het uploadveld pakt de camerarol technisch gewoon, maar of
het hele aanmaakscherm prettig werkt op een telefoon is niet zelf getest.

Zie [[daniel-visueel-liever-dan-tekst]] (rapportage aan Daniel) en [[omnivaleur-huidige-fase-klachten]].

---

## -Users-Danie-Downloads / fixes-generiek-voor-alle-gebruikers

*28-08-2026*

Omnivaleur is multi-tenant SaaS. Elke fix of feature moet generiek werken — voor gebruikers met Nederlandstalige listings, andere productcategorieën, andere platforms en andere data dan die van Daniel zelf.

**Why:** terugkerende controlevraag van Daniel bij vrijwel elke wijziging: "is dit nu geoptimaliseerd voor alle gebruikers en niet alleen voor mij? ook voor mensen die listings in het nederlands hebben, andere soort items verkopen etc." en "dit geldt ook voor anderen toch?" (o.a. 2026-08-28). Hij test vaak op zijn eigen voorraad, maar wil niet dat de oplossing daarop is toegespitst.

**How to apply:**
- Voordat je een wijziging afmeldt: benoem expliciet of hij tenant-onafhankelijk is, of hij afhankelijk is van taal/categorie/platform, en of er hardcoded aannames uit Daniels eigen data in zitten.
- Voordat je een klant (Jaap, Egbert, …) mailt dat iets opgelost is: check of de fix ook op hún situatie van toepassing is, niet alleen op Daniels test.

Zie [[bewijs-voor-claims-klanten]] en [[klantcommunicatie-jij-niet-u]].

---

## -Users-Danie-Downloads / sessiestart-eerst-lezen-wat-veranderd-is

*28-08-2026*

Aan het begin van elke chat/sessie — vóór je aan de slag gaat met wijzigen of bouwen — eerst kijken wat er sinds de vorige keer is veranderd: recente commits (`git log`), de changelog/Engineering Log, en `docs/team-notes.md` in de repo.

**Why:** Daniels expliciete instructie (2026-08-28): "voordat je chats gaat beginnen ... eerst even kijkt wat er in de change log gebeurt, wat er veranderd is ... zodat ik voorkom dat je dingen gaat toepassen of dingen gaat doen zonder dat je een goed beeld hebt van de huidige situatie waardoor er misschien dubbelingen ontstaan." Er wordt vanaf meerdere Claude-accounts aan hetzelfde project gewerkt; zonder deze check herhaal je werk of overschrijf je andermans wijziging.

**How to apply:**
- Bij Omnivaleur-werk: `git log --since="3 days ago" --oneline` + `git log docs/team-notes.md` lezen voordat je begint. Dit staat ook als vaste werkwijze bovenaan `team-notes.md` en is als commit in de repo vastgelegd ("Elke sessie begint met lezen wat er veranderd is").
- Bij andere projecten: minstens de laatste commits / het projectlog doornemen voor je wijzigt.
- Merk je dat iets al (deels) gedaan is op een ander account: daarop voortbouwen, niet opnieuw doen.

Zie [[team-notes-cross-account]] (dat gaat over vastleggen; dit gaat over eerst lezen) en [[autonoom-uitvoeren-niet-vragen]].

---

## -Users-Danie-Downloads / team-notes-cross-account

*27-08-2026*

Daniel werkt aan Omnivaleur vanaf meerdere Claude-accounts (zijn hoofdaccount + minstens één ander account, en later mogelijk Monaim). `~/.claude`-geheugen is per-account en reist niet mee bij een accountwissel of andere machine.

**Why:** Daniels expliciete eis (2026-08-26): "zorg ervoor dat ALLES wat je doet ook traceerbaar is voor daniel in zijn andere account, zodat zijn claude code ook direct daarmee aan de slag kan en hij geen onverwachte dingen tegenkomt of achterloopt." Hij wilde daar een skill/geheugen/gewoonte van maken.

**How to apply:**
- De canonieke, account-overstijgende plek voor team/partnership/business-context is **`docs/team-notes.md`** in de Omnivaleur-repo (`~/Documents/omnivaleur`) — append-only, nieuwste bovenaan, gepusht als een codewijziging (auto-push hook regelt dat).
- Als je in een Omnivaleur-sessie een beslissing neemt of leert over rollen, toegang, deals of niet-voor-de-hand-liggende businesscontext: voeg zelf een gedateerde entry toe onderaan die sectie en push, net als code.
- `~/.claude`-geheugen mag daar bovenop voor snelle recall, maar nooit als enige vindplaats.
- Het is eventual consistency via git, geen live-sync: een al lopende sessie ziet andermans wijziging pas na een nieuwe `git pull`/herstart in dezelfde repo.

Zie [[autonoom-uitvoeren-niet-vragen]] en [[omnivaleur-monaim-partnership]].

---

## -Users-Danie-Downloads / garmin-watchdealer-gem

*26-08-2026*

Daniel has a Gemini Gem called **"GarminWatchDealer"** at https://gemini.google.com/gem/1ZuDY6p51GaFbI2C9Uyzp9nPbphokoV_o?usp=sharing — he pastes a screenshot of a Vinted/Marktplaats listing and the Gem judges whether it's a good deal.

To keep its verdicts accurate, feed it the current market data before/with each deal screenshot: the [garmin-tracker](/Users/Danie/garmin-tracker) project generates `data/pricing_summary.md` (also served live at http://localhost:5678/summary), which lists per-model max-bid-per-condition derived from actual Vinted/Marktplaats asking prices. See [[garmin-price-tracker-project]] for the full project context.

Gemini Gems don't auto-sync a live file — the summary must be re-pasted/re-uploaded each session for freshness, it's not a one-time upload.

Since 2026-08-24 the dashboard's helper button no longer copies to clipboard — it's **"⬇️ Download actuele marktdata (.md)"**, which downloads `pricing_summary.md` straight to Downloads (clipboard access was unreliable in some browser contexts). Workflow is now: click download → upload that file into the GarminWatchDealer Gem → paste the deal screenshot.

---

## -Users-Danie-Downloads / garmin-price-tracker-project

*26-08-2026*

Daniel buys/resells secondhand Garmin watches (Vinted, Marktplaats, later eBay/Shopify). Built him a local tool at **`/Users/Danie/garmin-tracker`** (moved there from Downloads then Documents — Documents is TCC-protected and silently blocks unattended launchd processes, so the project must stay outside Desktop/Documents/Downloads).

**Architecture:**
- `config/models.json` — tracked models (Epix Gen 2, Epix Pro Gen 2, Fenix 7, Fenix 7 Pro, Forerunner 965/265/255, Instinct 2/2X) each with buyTarget/sellTargetMin/Max/priority. Fenix and Epix Pro variants were split out from base models because they sell for meaningfully more — matchModel() picks the longest alias match so "fenix 7 pro" outranks "fenix 7".
- `data/listings.csv` — all scraped/manual listings, append-only.
- `data/pricing_summary.md` — auto-regenerated AI-readable market summary, used to feed his Gemini Gem "GarminWatchDealer" (see [[garmin-watchdealer-gem]]).
- `dashboard/index.html` served by `scripts/serve.mjs` on **http://localhost:5678** (binds 127.0.0.1 only) — shows focus ranking, current buy opportunities, per-model/per-condition max-bid tables, full filterable/sortable listings table, and "Ververs Vinted/Marktplaats" buttons that trigger scraping server-side.
- Two `launchd` LaunchAgents keep it always-on: `com.danie.garmin-tracker` (dashboard, RunAtLoad+KeepAlive) and `com.danie.garmin-tracker-watch` (every 30 min: refreshes Vinted, checks for buy-target deals, pops a macOS `display dialog` alert for new ones, regenerates pricing_summary.md).

**Data sources — important limitations:**
- **Marktplaats**: via Apify actor `haketa/marktplaats-scraper` — costs Apify credits (he was down to ~$0.87 free tier at one point). Reliable when it works.
- **Vinted**: no reliable free method exists. Direct fetch, 3 different Apify actors, and Playwright (headless and headed) were all tried — Cloudflare/Turnstile blocks it, sometimes intermittently even in headed mode. Do not spend more effort chasing bypasses; CAPTCHA-solving services are explicitly out of scope (deliberate anti-bot circumvention). `scripts/fetch_vinted.mjs` fails gracefully now. Manual entry via `scripts/add_manual.mjs` is the fallback.
- **eBay**: sold-listing data (`findCompletedItems`) was deprecated/cut off Jan 2026, and the Marketplace Insights API (real sold prices) is only granted to large approved partners — not available for a hobby developer account. As of 2026-08-24, active *asking-price* listings ARE integrated via the eBay Browse API (OAuth client-credentials + `item_summary/search`), in `scripts/fetch_ebay.mjs`, same filter/dedupe pipeline as Marktplaats. Default marketplace is `EBAY_DE` (broader supply than `.nl`); override via `EBAY_MARKETPLACE` in `.env`. All 8 tracked models are pulled (~85 listings fetched initially). Dashboard has a "Ververs eBay (gratis)" button per model, and eBay rows count toward focus-score/opportunities/pricing_summary like any other source.
- No platform exposes real *sold* prices or Marktplaats bid history publicly — everything in the dashboard is asking-price data, clearly labeled as such.

**Feedback learned**: [[credentials-never-in-memory-or-chat]] type incident happened repeatedly with his Apify token pasted in plaintext — always tell him to rotate exposed tokens and never store them.

---

## -Users-Danie-Downloads / pol-cgi-tijdlijn-tool

*24-08-2026*

De tijdlijnpresentatie voor Daniels CGI (25-08-2026) staat sinds 24-08-2026 in
`~/Documents/CGI Presentatie/tijdlijn.html`. Losstaand HTML-bestand, opent via file://,
media in de submap `media/`.

Opzet:
- Data zit in `<script id="data" type="application/json">` in het bestand zelf.
- Bibliotheek zit in `<script id="lib" type="application/json">`.
- Ingebouwde editor (knop "Bewerken"): stappen slepen/toevoegen/verwijderen, alle
  tekst aanpassen, beeld slepen. Autosave naar localStorage, key `pol-tijdlijn-v1`.
  "Opslaan als bestand" exporteert een complete nieuwe tijdlijn.html.
- Foto's kan Daniel zelf in de editor slepen (worden automatisch verkleind naar
  1600px en als data-URL opgeslagen).
- Video's: hij zet ze in de submap `Nieuwe videos` en dubbelklikt op
  `Video's klaarzetten.command`. Dat script converteert met ffmpeg naar 720p mp4 +
  poster in `media/`, en herschrijft de lib-lijst in tijdlijn.html. Het script laat
  de data van Daniel ongemoeid, dus zijn eigen bewerkingen blijven staan.

Belangrijk: video's kunnen NIET rechtstreeks in de pagina worden geüpload
(file:// heeft geen IndexedDB, localStorage is te klein, en .MOV/HEVC speelt niet
af in Chrome). Vandaar het script.

Zie ook [[daniel-studie-finance-control-cgi]].

Het kader past zich aan de verhouding van elk beeld aan (geen zwarte/grijze randen).

Sinds 24-08-2026: de map `POL CGI` (met het conversiescript) en de bijbehorende
`media/`-submap zijn verplaatst (niet gekopieerd) van `~/Downloads` naar
`~/Documents/CGI Presentatie/` — dat is nu de enige, actuele plek. De ruwe
originele video's/foto's (inclusief losse bronbestanden die eerst in Downloads
stonden) zijn gekopieerd naar Google Drive:
`Mac Archief → 02 Studie en afstuderen → POL CGI - originelen`, met een losse
reservekopie van de complete presentatie in `CGI Presentatie (reservekopie)`.
Bit-voor-bit geverifieerd. `~/Downloads/POL CGI` mag pas weg zodra Google Drive
bevestigt dat de sync klaar is.

---

## -Users-Danie-Downloads / bergweg-investering-broer

*23-08-2026*

Op 28 augustus 2024 tekenden Daniel en zijn broer bij de notaris voor een woning
aan de Bergweg in Rotterdam. Verdeling 50/50. Zijn broer woont er zelf, samen met
een Griekse huurder die huur betaalt. Voor Daniel is het puur een investering, geen
woonruimte. Op 28 december 2024 was de verhuizing.

Daniel ziet dit als zijn eerste echte investering: het moment waarop financiën van
studievak naar eigen verplichting verschoven, en het eerste inkomen dat binnenkwam
zonder dat hij ervoor hoefde te werken.

Gebruikt in [[daniel-studie-finance-control-cgi]].

---

## -Users-Danie-Downloads / revaleur-toekomstplan-kwaliteit

*23-08-2026*

Daniels plan met Revaleur (stand augustus 2026):

- Fysieke winkel(s) openen op bewust gekozen, strategische locaties; de webshop
  wordt de motor achter de etalage in plaats van andersom.
- Bewuste positionering tegenover "nietszeggende vintagewinkels": streng inkopen
  op merk en staat — Ralph Lauren, Stone Island, Suitsupply, Profuomo. Hogere
  marge per stuk, minder dood voorraadkapitaal.
- Omnivaleur uitbouwen van eigen gereedschap naar product voor andere winkels en
  webshops (NL, BE, DE, FR).

Hangt samen met [[omnivaleur-outreach-machine]] en [[omnivaleur-shopify-app]].

---

## -Users-Danie-Downloads / railway-no-headless-browser

*22-08-2026*

Railway draait op Nixpacks zonder browser beschikbaar. Zelf Chromium in die build proberen te krijgen is risicovol omdat het de build van de live site (bijv. omnivaleur.com) kan breken voor iets dat er inhoudelijk niets mee te maken heeft.

**Why:** ontdekt bij het inplannen van de Omnivaleur Trendmotor (TikTok-metingen, headless browser nodig) — Railway bleek geen bruikbare optie.

**How to apply:** voor elke toekomstige taak die een headless browser nodig heeft (scraping, screenshots, TikTok/Marktplaats-metingen e.d.) bij een project dat op Railway draait: gebruik in plaats daarvan **GitHub Actions** (browser standaard aanwezig, gratis, en volledig los van de live-site-deployment) — niet de Railway-service zelf uitbreiden. Zie [[omnivaleur-trendmotor]] als voorbeeld van deze aanpak. Relevant voor andere projecten met een vergelijkbare stack, zoals [[nexus-market-terminal]], als daar ooit browser-gebaseerde scraping bij komt.

---

## -Users-Danie-Downloads / omnivaleur-trendmotor

*22-08-2026*

Omnivaleur heeft sinds 2026-08-21 een tweede autonoom systeem naast de outreach-machine: de **Trendmotor**, die TikTok-video's meet om te zien wat werkt in de niche (vintage/secondhand fashion).

- Ingepland op Daniels expliciete wens ("plan in, volledig autonoom en automatisch"): **elke dinsdag 08:30** (Nederlandse tijd) valt een mail binnen op daniel@omnivaleur.nl met vijf concrete video-opdrachten (hook, wat te filmen, lengte, sound, onderbouwend cijfer), plus het dashboard als bijlage.
- Elke opdracht moet een video-URL noemen die letterlijk in de meting voorkomt — een broncontrole verwerpt opdrachten die dat niet kunnen, dus er komt nooit een verzonnen voorbeeld in de mail.
- Draait bij **GitHub Actions, niet Railway** — zie [[railway-no-headless-browser]] voor waarom.
- Schrijft naar Notion onder de Omnivaleur-pagina ("Trendmotor — wat werkt in de niche") en heeft een los dashboard-artifact met filters (periode 7/30/90 dagen, platform, hoek, taal, min. views, sortering).
- Er staan bewust **twee cronroosters** (06:30 en 07:30 UTC) omdat GitHub geen zomertijd kent — het script zelf checkt de Nederlandse klok en slaat de verkeerde beurt over.
- Vroege bevinding (n nog klein, dus voorlopig): #y2k / #2000s / #vintagefashion scoren structureel +120-150% engagement boven gemiddeld; vraagvormen en resultaatclaims in de tekst-hook scoren juist 30-64% ónder gemiddeld op TikTok (de hook zit in beeld/spraak, niet in de bijschrift-tekst).

**Why:** Daniel wil contentideeën voor de Omnivaleur-social-kanalen zonder dat hij zelf trends hoeft te turven.

**How to apply:** bij vragen over Omnivaleur-content of TikTok-strategie eerst checken of de Trendmotor al relevante cijfers heeft (Notion-pagina/dashboard) voor je advies geeft. Zie ook [[omnivaleur-outreach-machine]].

---

## -Users-Danie-Downloads / omnivaleur-blog-i18n

*22-08-2026*

**Vaste regel (bevestigd 2026-08-21): elk nieuw artikel op de Omnivaleur-blog krijgt voortaan ook een Nederlandse versie.** Daniel expliciet: "ja, elk artikel voortaan ook in het Nederlands." Aanleiding was een SEO/GEO-audit van omnivaleur.com die liet zien dat 41 Nederlandse artikelen wel in de sitemap stonden maar nergens vanuit de site bereikbaar waren (verweesde pagina's), en dat de nieuwste artikelen geen Nederlandse tweeling hadden.

Gebouwd n.a.v. die audit:
- `omnivaleur.com/nl/blog` bestaat nu als aparte Nederlandse blogindex met alle vertaalde artikelen en een taalwissel-knop; menu/kruimelpad op NL-artikelen wijst er ook naartoe.
- Vertaling bij publiceren wordt nu **twee keer geprobeerd** (was één keer — mislukte pogingen lieten een artikel voorgoed alleen-Engels staan).
- **Elke dag 11:00** loopt een inhaalronde die Engelse artikelen zonder Nederlandse versie alsnog vertaalt (max. 3 per run), zodat een gat nooit blijft staan.
- Een echte 404-pagina staat er nu ook (voorheen kale `{"detail":"Not Found"}` tekst).

**Why:** zonder Nederlandse index-pagina en zonder retry ranken de NL-artikelen structureel slechter en vielen ze soms helemaal weg — dat kost bezoekers/omzet op de Nederlandse markt.

**How to apply:** bij elke toekomstige wijziging aan de Omnivaleur-blogpipeline (content_keywords, publicatiescript, etc.) blijft de aanname dat NL-vertaling verplicht en automatisch is — niet iets waar apart om gevraagd hoeft te worden. Zie ook [[omnivaleur-outreach-machine]] en [[omnivaleur-notion-docs]] voor de rest van het Omnivaleur-ecosysteem.

Nog open (niet in memory als taak, want operationeel): www.omnivaleur.com wees op 2026-08-21 nog naar een oude, losse kopie van de site op Cloudflare i.p.v. een 301-redirect — Daniel moest dat zelf in Cloudflare afronden.

---

## -Users-Danie-Downloads / btw-aangifte-stappenplan

*22-07-2026*

Kwartaal-stappenplan voor Daniels BTW-aangifte (tweedehands kledinghandel, D M DE KONING, btw-nr 253036975).

**Bron:** Google Spreadsheet "Profitsheet Right" (fileId `13tHt7SWYqYdPKwyZaj5kkAcZt3G_IJCzksZYSL-zxgI`, eigenaar danielsclothingshop@gmail.com), tab P&L.

**Regeling:** margeregeling (globalisatiemethode), GEEN OSS. Ook EU-consumentenverkopen blijven margegoederen → in NL belast in rubriek 1a. Niks in 3b/3c/OSS.

**Belangrijk:** de eigen BTW-kolommen in de sheet (BTW-Regeling toegepast, Marge BTW, Regulier BTW, OSS Btw, BTW Terug Inkoop) NEGEREN — die kloppen niet. Alles zelf herberekenen uit de marges.

**Stappen:**
1. Download P&L als CSV via Drive `download_file_content` (exportMimeType text/csv) — read_file_content kapt af, gebruik CSV. Base64 decoden.
2. Filter rijen op `Date Sold` binnen het kwartaal (formaat DD-MM-YYYY). Q2 = 1 apr t/m 30 jun, etc.
3. Per item: marge = `Price Sold` − inkoop, waarbij inkoop = `Net Price Bought` (val terug op `Price Bought` als leeg).
4. Netto marge kwartaal = som van alle marges INCLUSIEF negatieve (globalisatie saldeert). Indien vorig kwartaal negatief eindigde, dat negatieve saldo eerst verrekenen (vragen aan Daniel).
5. BTW = 21/121 × netto marge. Omzet excl. = netto marge − BTW. Afronden op hele euro's.
6. Invullen aangifte rubriek 1a: Omzet (excl.) en Btw.
7. Voorbelasting (5b): Daniel exporteert kostenposten uit Gekko (.xls, "Tablib Dataset"; kolommen o.a. BTW 21%, BTW verlegd, Leverancier). Voorbelasting = som kolom "BTW 21%". Kledinginkoop (Fleek/Riaaj Vintage) en posten met "Geen BTW=Ja" geven geen aftrek.
8. **Verlegde BTW (BTW verlegd = Ja):** posten van buitenlandse leveranciers (bv. Namecheap, Anthropic = VS). Bereken 21% × grondslag (Totaal ex BTW). Dit hoort in **rubriek 4a** (diensten buiten EU; 4b voor EU-leveranciers) als Omzet+Btw, ÉN is aftrekbaar als voorbelasting (5b) → per saldo € 0, maar moet formeel in 4a/4b staan. Dus rubriek 4 is NIET altijd leeg.
9. Optioneel Excel-totaaloverzicht exporteren naar ~/Downloads (samenvatting + detailregels).

Referentiekwartaal Q2 2026: 150 verkopen, netto marge € 2.026,80 → 1a omzet € 1.675 / btw € 352. Voorbelasting 5b € 33 (€ 29,40 direct + € 3,40 verlegd). Rubriek 4a: Namecheap € 6,19 + Anthropic € 10,00 → omzet € 16 / btw € 3. Te betalen ≈ € 322.

Zie ook [[revaleur-blog-system]] en [[nexus-market-terminal]] voor andere Daniel-projecten.

---

## -Users-Danie-Downloads / revaleur-blog-no-test-publishing

*17-06-2026*

When testing the `revaleur-blog` generator (`/Users/Danie/Documents/revaleur-blog`), do NOT trigger real publishes to verify changes — it burns the keyword queue and posts live to the Revaleur Shopify store.

**Why:** Daniel called this out after I repeatedly ran the workflow (publishing ~7 live posts) just to test fixes.

**How to apply:** Use the `DRY_RUN` path — `gh workflow run "Auto Blog Generator" -f dry_run=true`. It generates the article + attempts the image but writes nothing to Shopify and leaves `keywords.json` untouched. The repo also has an auto-commit process that races git pushes, so push with a fetch/rebase retry loop. See [[revaleur-blog-system]].

---
