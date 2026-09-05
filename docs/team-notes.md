# Team & Partnership Notes

Append-only log, newest entry on top. Read this before starting anything that
touches people, roles, deals, or business decisions — it's the one record
that travels with the repo across every Claude Code session and every
Anthropic account, unlike `~/.claude` memory, which is per-account and does
not follow Daniel between machines/logins.

## Working practice — read this first

Any Claude Code session opened in this repo must treat this file (and its
history via `git log docs/team-notes.md`) as authoritative for
team/partnership/business context. When you make or learn a decision of this
kind — roles, access, deals, non-obvious business context — append a dated
entry below and push it, exactly like a code change. Per-account `~/.claude`
memory can still be written on top for fast recall, but never as the only
record: anything here has to survive a switch to a different Claude account
without Daniel repeating himself.

## 2026-08-31 — Storing "niet ingelogd bij Marktplaats" was al gerepareerd

MOET ZEKER-storing van de klantenservice: Dennis (retrogameking) en Egbert
(papas-plectrums) meldden allebei "je bent niet ingelogd bij Marktplaats"
tijdens het scannen. Onderzoek in het opdrachtenlogboek (tabel `jobs`) wees uit
dat dit dezelfde storing is die op 29/30-08-2026 al gerepareerd is in
`backend/api/jobs.py` (`_rechtgezette_foutmelding`, commit 9967b9e, live op
main): beide klanten draaiden extensieversies ruim onder de ondergrens
(1.0.200/1.0.202/1.0.207/1.0.217/1.0.218 tegen een vereiste van 1.0.244), en
Egbert heeft bovendien een zakelijk account waarbij zijn persoonlijke overzicht
altijd leeg hoort te zijn (advertenties staan in Admarkt).

Bewijs dat de fix werkt: Egberts scan kreeg op 28-08 de gecorrigeerde melding
("zet Admarkt aan") en slaagde diezelfde dag. Dennis heeft sinds 22-08 geen
scan meer geprobeerd (extensie voor het laatst gezien 23-08) — voor hem staat
de oude foutmelding dus nog "on the shelf" totdat hij het nog eens probeert met
een bijgewerkte kopie van de extensie.

Niets aan de code gewijzigd; teruggemeld via `mail_analyse.py opgelost`. Les:
altijd eerst het opdrachtenlogboek raadplegen voordat je een MOET ZEKER-storing
gaat repareren — deze was al klaar en had zonder die stap dubbel werk
opgeleverd.

## 2026-08-26 — Monaim joins as 50/50 partner

- Monaim is coming on as a 50/50 partner on **Omnivaleur** specifically —
  not Somnia (his own e-commerce brand, unrelated) and not Revaleur.
  **Revaleur is Daniel's own vintage clothing brand; Omnivaleur is the
  software Daniel originally built to run Revaleur's own cross-listing,**
  later spun out into a standalone SaaS product.
- Structure is deliberately informal for now: no equity/contract yet. Legal
  vastlegging of the 50/50 is postponed on purpose until both sides are happy
  with how the working relationship actually plays out.
- Focus at the start: organic content for Omnivaleur's **Dutch-language**
  socials (TikTok/Instagram) — schema + ideation, editing gets outsourced.
  Also owns exploring a social-DM outreach system (parallel idea to the
  existing cold-email leadgen — see the `leadgen` skill for how that one is
  structured: find → first contact → log). **But right now (pre-50-users),
  the real company-wide priority is dashboard improvements, debugging, and
  gathering user feedback** — Monaim's content/outreach work runs alongside
  that, not instead of it, and doesn't compete with it for resources.
- Suggested role/tasks: **Growth & Content Partner.**
  1. Weekly Dutch content schema for TikTok + Instagram — he floated 3 posts
     + 1 video/week as a first test cadence.
  2. Design + test a social-DM outreach flow for finding NL tweedehands
     sellers on IG/TikTok (VA-run vs. extension vs. manual — undecided).
  3. Track weekly content performance (views, follows, signups attributed)
     — this is what tells us when organic has enough signal to justify ad
     spend, not a fixed date.
- **When to start paid ads: at 50 users** (concrete threshold, set by
  Daniel — not "once conversion is validated" in the abstract anymore).
  - **First phase targets clothing/shoe sellers specifically** — that's what
    the dashboard is built for and where it performs best; don't broaden the
    ad targeting past that niche in phase one.
  - **Creatives:** organic content can double as ad creatives if the quality
    is good enough — no separate production required by default. Monaim may
    also build dedicated landing pages for ad traffic.
  - **Geography: Europe only.** Deliberately stay out of US/UK — competition
    among cross-listing tools is by far the fiercest there.
  - **Competitive positioning:** Channable is the dominant tool most
    marketplace sellers currently use — large, but very poorly rated. Its
    focus is broad marketplace selling in general (including bol.com etc.).
    Omnivaleur's differentiation is staying narrow: **secondhand
    (tweedehands) platforms only**, for now. Don't pitch Omnivaleur as a
    general marketplace tool — that's Channable's ground, and it's already
    lost on reviews.
  - Blogs are **fully automated** already (see `backend/content/quality.py`
    and the daily auto-publish job) — not part of Monaim's remit, mentioned
    only so he doesn't assume it's an open task.
- **Free account:** `backend/services/billing.py` now recognizes a
  `complimentary` subscription status — unlimited access, no
  `stripe_subscription_id` required (see `evaluate_access`). To activate for
  Monaim: he signs up normally at omnivaleur.com with his own email (creates
  the usual 7-day `trialing` row), then Daniel sets that row's `status` to
  `complimentary` in Supabase. **Do not** use `status = active` without a
  `stripe_subscription_id` — that path is intentionally blocked (guards
  against a past bug where it silently granted free access).
- **Notion:** Daniel is giving Monaim full workspace access. No further
  restriction recommended given the 50/50 framing — gate by task assignment,
  not by permissions.
- The original onboarding document (product overview, brand colors/type,
  cijfers) was published as a Claude Artifact on 2026-08-26 and handed to
  Daniel directly in chat — not duplicated here since artifacts aren't repo
  files.

## 2026-08-27 — Egbert Brouwer (Papa's Plectrums): waarom zijn account vastliep

Eerste zakelijke klant met een grote voorraad (2.135 items, 5.534 Marktplaats-
advertenties). Hij dreigde af te haken ("ik begin er moedeloos van te worden").
Hieronder wat er écht misging, zodat dit niet nog eens ongemerkt gebeurt.

**De hoofdoorzaak: een te lange URL.** PostgREST zet een `.in_("item_id", [...])`
als tekst in de URL. Gemeten met echte item-id's: vanaf **640 id's** weigert
httpx het verzoek (`InvalidURL: URL component 'query' too long`). Elke klant met
meer dan ~639 items liep daarop stuk — zonder nette foutmelding, midden in de
verwerking. Gevolgen die we bij Egbert konden aanwijzen:

- **Scans werden opgehaald maar nooit opgeslagen.** De extensie leverde drie
  keer op rij 2.000 nieuwe advertenties aan; het opslaan knalde stuk, maar de
  opdracht stond toen al op "klaar". Het scherm meldde dus "niets nieuws" en de
  volgende scan sloeg diezelfde advertenties over. 2.000 advertenties zijn
  op 27-08-2026 alsnog teruggezet uit het bewaarde scanresultaat.
- **Verkoopcontrole (polling) lag stil voor iedereen**, niet alleen voor hem:
  die draait over álle actieve advertenties samen (4.751 gemeten).
- Ook opnieuw-plaatsen en de Vinted-verkoopcontrole raakten dit.

**Tweede oorzaak: het stille 1.000-rijenplafond.** PostgREST negeert een
`.limit(10000)` en geeft er gewoon 1.000 terug, zonder iets te zeggen.
"Fill from Marktplaats" zag daardoor alleen zijn eerste 1.000 items, vond daarin
5 lege, zocht op díe 5 titels naar zijn verkopersnummer, vond niets, en meldde
"could not find your adverts on Marktplaats" — terwijl zijn 4.754 advertenties
er gewoon stonden.

**Les voor volgende keer:** grote accounts breken op andere plekken dan kleine.
Een testaccount met 50 items bewijst niets. Bij elke query over items/listings
geldt: `fetch_all` in plaats van `.limit(...)`, en `fetch_all_in` /
`update_in` (backend/database.py) in plaats van een kale `.in_(...)`.

### 2026-08-27, aanvulling — nog twee showstoppers bij dezelfde klant

Na de fixes hierboven bleken er nóg twee dingen kapot die los stonden van de
te lange URL.

**"Import all → Items" was sinds 25-08 voor iedereen dood.** In één regel zaten
twee fouten: `db.table("items").eq(...)` zonder `select()` ervoor (bestaat niet,
gooide meteen `AttributeError`), en een "snellere" parallelle lezer die acht
verzoeken tegelijk over de gedeelde Supabase-verbinding stuurde. Gemeten op
Egberts account: **45 van de 55 gelijktijdige verzoeken mislukten**; na elkaar 0
mislukt en 4,4 seconden voor alles. De parallellisatie was zelf de storing.

**Hij draaide de extensie twee keer.** Naast een bijgewerkte kopie liep er een
met de hand geladen kopie van 16 augustus (1.0.207), die nooit meebeweegt met de
Chrome Web Store. Beide halen werk uit dezelfde wachtrij; wie het eerst pakte
bepaalde de uitslag — 13 scans geslaagd, 18 mislukt, en die 18 meldden allemaal
"je bent niet ingelogd bij Marktplaats" terwijl hij ingelogd was. De Web Store
stond al die tijd gewoon op 1.0.248; het lag dus niet aan het publiceren.

Wat er nu tegen beschermt: de server zet een scan die door een extensie ouder
dan `MINIMALE_SCANVERSIE` wordt afgekeurd terug in de wachtrij in plaats van op
"mislukt", en het dashboard meldt welke verouderde versie er meedraait. Dat is
af te lezen uit het versiestempel dat de extensie zelf in haar foutmeldingen
zet — geen extra tabel, geen migratie.

**Les:** de gepubliceerde Web Store-versie is zonder inloggen te controleren via
de CRX-updatecheck. Bij "hij doet het soms wel en soms niet" is dat de eerste
vraag: draait er ergens nog een tweede kopie?

### 2026-08-27 — tweede ontwikkelaar ingehuurd (eigen Claude-abonnement)

Daniel heeft een tweede ontwikkelaar ingehuurd die aan Omnivaleur meewerkt via
een **eigen, apart Claude Code-abonnement**. Die persoon springt in wanneer
Daniels gebruikslimiet op is. **Daniel houdt de leiding**: scope, prioriteiten
en beslissingen liggen bij hem; de tweede ontwikkelaar is aanvullend.

Praktisch:
- Werken vanaf een ander account of een andere pc kan gewoon — de code staat op
  GitHub (`danieldk04/crosslisteu`), `git clone` + `claude` in die map volstaat.
  Alleen het `.env`-bestand met sleutels staat niet in git en moet apart en
  veilig overgezet worden.
- **De git-auteursnaam bewijst niets.** Alle commits verschijnen als
  "Daniel de Koning" omdat de lokale git-config dat zo instelt, ongeacht welk
  Claude-account de sessie draait. Wie een wijziging maakte, is dus niet uit
  `git log` af te lezen — navragen bij twijfel.
- **Rechten:** de ingehuurde ontwikkelaar heeft exact dezelfde rechten als
  Daniel. Geen beperkingen op live-server, mailbox of betaalcode.

**Werkafspraak voor elke sessie (Daniel, 27-08-2026).** Begin nooit met bouwen
voordat je hebt gelezen wat er in de afgelopen dag in de code is veranderd:

```bash
git log --since="30 hours ago" --name-only
```

Let daarbij op de commits met de tekst "auto: update ..." — die komen van de
auto-push-hook en bevatten het echte werk van eerdere sessies onder een
nietszeggende titel. Dit is geen formaliteit: op 27-08-2026 voegde een eerdere
sessie om 14:04 een API-parameter toe die de op de server gepinde SDK niet kende,
waarna de mailagent een halve dag lang stilletjes standaardmails uitstuurde in
plaats van echte antwoorden. Dat was alleen te vinden door die commits te lezen.

### 2026-08-27, avond — de mailagent stuurde weer standaardmail

Rob Kruizinga van Borstelbeer antwoordde op de koude mail met één inhoudelijke
zin: de productvariabelen uit zijn webshop zijn niet op Marktplaats te zetten.
Het concept dat klaarstond ging over de demovideo, de prijs en de lijst met
kanalen. Over zijn vraag stond er niets.

**De oorzaak lag in een pin, niet in de tekst.** De server draaide op
`anthropic==0.34.2` uit september 2024. Toen de code er diezelfde middag
`output_config` bij ging sturen, gooide die SDK een `TypeError` die netjes werd
opgevangen — waarna élk conceptantwoord terugviel op het sjabloon. Een opgevangen
fout ziet er precies zo uit als "even geen antwoord", dus niemand zag het.
Bewezen door 0.34.2 in een schone venv te installeren en de aanroep te herhalen.

**Daarnaast las het sjabloon onze eigen mail.** Het bepaalde waar iemand "naar
vroeg" door de hele mail te lezen, inclusief het citaat van onze eigen koude mail
eronder — en die noemt zelf de platformen en de prijs. Iedereen die antwoordde
"vroeg" dus automatisch naar allebei. Dat is precies hoe Rob aan een
platformlijst en een maandbedrag kwam.

**En er bleek een derde gat.** `check` kijkt alleen naar nieuwe post. Wie daar
één keer doorheen glipt, komt nooit meer aan de beurt: zijn bericht is dan al
verwerkt en verhuisd naar Beantwoord. Vier mensen stonden zo te wachten zonder
dat iets het merkte, Borstelbeer incluis.

Wat er nu geldt: **geen vangnet meer.** Lukt het echte antwoord niet, dan komt er
geen concept, blijft het bericht in het postvak staan en meldt het avondbericht
mét reden welke mails op Daniel wachten. Drie nieuwe commando's: `wachtenden`
(wie wacht er zonder concept — draait vanzelf één keer per dag), `herstel`
(vervolgconcept voor wie de sjabloonmail al verstuurd kreeg) en `sjablonen-weg`.

**Les:** alles rond de Anthropic-koppeling in dit project faalt stil — een lege
creditkaart, een ontbrekend pakket, een te oude pin. Bouw daarom nooit op één
slot. En als iets "soms goed en soms generiek" is, kijk dan eerst naar de
gepinde versies, niet naar de prompt.

### 2026-08-27, avond — zes stilstaande tests, waarvan twee echte fouten

Zes tests faalden al langer zonder dat iemand keek. Drie soorten:

**Een echte fout in het publiceren naar Vinted.** `BLAD_VOORKEUR` en `enkelvoud`
stonden rond regel 1431 van `extension/content/vinted.js`, dus ná het punt waar
het formulier al wordt ingevuld (`await fillForm(item)`, regel 566). Een `const`
bestaat pas zodra zijn eigen regel gedraaid is, dus de categoriestap viel om op
een waarde die nog niet bestond. Omdat `step()` fouten opvangt en doorgaat, ging
de advertentie zónder categorie naar Vinted — geen crash, geen melding, alleen
een advertentie die niet klopt. Geraakt werden juist de items waar die lijst voor
bedoeld is: cardigans, zip-vesten, geruite overhemden. Verplaatst naar boven.
Dit is de vierde keer dat deze val toeslaat (eerder: kleurstap, V_KLEDING,
PRICE_ERR_RE).

**137 categorieën zonder bestemming.** De groepen wonen, antiek/kunst en muziek
kwamen in augustus in het dashboard, maar kregen nooit een Vinted-hint, een
eBay-hint of een Shopify-producttype. Vinted is in dit project bewust geen
kleding-only platform (zie `backend/services/platformregels.py`), dus die items
zijn echt te plaatsen — ze kwamen alleen nergens goed terecht. Alle 137 zijn nu
ingevuld vanuit één vertaaltabel; Shopify leest de eBay-hints in plaats van een
vierde kopie bij te houden. Belangrijk om te weten: deze hints zijn ZOEKWOORDEN
die in Vinted's eigen categoriezoekvak worden getypt, geen vaste categorie-ID's.

**Twee verouderde tests.** De bescherming tegen "gave spijkerbroek verkocht als
kapotte spijkerbroek" en de uitsluiting van verkochte/concept-advertenties op
Vinted bestaan allebei nog, maar waren hernoemd en verplaatst. De tests zochten
op letterlijke tekst en braken op de vorm. Ze toetsen nu de garantie zelf.

**Les:** een test die al weken rood staat, wordt genegeerd. Dat kostte hier een
maand lang stille fouten in het publiceren. Een rode suite is een storing, geen
achtergrondruis.

### 2026-08-27 — Wat leads terugvragen, en het gecontroleerde antwoord

Bijhouden wat er in de koude-mailantwoorden steeds terugkomt, mét het antwoord
zoals het écht in de code staat. Elk antwoord hieronder is geverifieerd, niet
gegokt. Vul deze lijst aan bij elke nieuwe vraag; verstuur nooit een concept met
een claim die hier niet in staat of niet in de code is nagekeken.

**1. "Koppelen jullie met WooCommerce?"** (Rob/Borstelbeer, Vianen Telecom —
2x in één dag, dus de meest gestelde vraag)
Nee. Van webshops alleen Shopify. WooCommerce komt in de hele codebase alleen
voor als herkenningsregel in `scripts/leadgen_marktplaats.py` (om te zien dát een
lead een webshop heeft), nergens als koppeling. Staat ook niet op de roadmap.

**2. "Is het een AI-agent? Foto maken en hij vult de rest in."** (Vianen Telecom)
Half. Wat er wél is: automatisch vertalen (NL/EN) en Claude die bij een import
categorie/gender/kleur/maat raadt uit titel + omschrijving
(`_classify_with_claude` in `backend/api/imports.py`). Wat er NIET is: foto →
kant-en-klare advertentie. De code bestaat wel
(`backend/services/ai_listing.py`, endpoint `POST /api/platforms/ai-listing`),
maar geen enkele knop in `frontend/app.html` roept hem aan, en de prompt is
kleding-only. Beloof dit dus niet. Openstaand: afbouwen of afmaken.

**3. "Kunnen mijn productvarianten mee?"** (Rob/Borstelbeer)
Nee, en dat is fundamenteel. Eén artikel = één stuk, één prijs, voorraad 1
(zie `_ensure_stock_of_one` en `"inventory_management": "shopify"` in
`backend/platforms/`). Bij een Shopify-product met meerdere varianten leest
`_convert()` alleen `variants[0]`. Er is geen aantal-veld in het datamodel.

**4. "Past mijn assortiment?"** — de scherpste filter, en hij wordt te vaak
gemist. Publiceren naar Marktplaats/2dehands kan alleen binnen de 322 vaste
sleutels van `MP_CATEGORIES` in `extension/background.js`: kleding, schoenen,
sieraden/tassen/horloges, wonen & tuin, antiek/kunst, muziek, games en
`electronics` — en die laatste is **uitsluitend telefoons** (10 sleutels,
cat1 820). Geen persoonlijke verzorging, geen huishoudelijke apparaten, geen
gereedschap, geen audio/tv/computers. Valt een item erbuiten, dan stopt de
extensie met `CategoryUnresolvedError` en komt de advertentie er niet.

**Werkafspraak:** controleer bij elke lead eerst wat hij écht verkoopt vóór je
antwoordt. Op 27-08-2026 ging er bijna een concept uit waarin Borstelbeer werd
afgeschreven als "borstelfabrikant met nieuwe producten in bulk". Borstelbeer
repareert elektrische tandenborstels en verkoopt daarnaast refurbished Oral-B
IO's — precies onze conditie-doelgroep. De afwijzing klopte alsnog (geen
categorie voor tandenborstels), maar op de verkeerde gronden, en dat was in de
mail te zien geweest. Eén minuut op de site van de lead voorkomt dat.

### 2026-08-27 — Audio, tv en foto erbij, en wat er nog niet aan bewezen is

**Waarom deze tak en niet een andere.** Gemeten op de 324 leads met e-mailadres:
36% verkocht iets dat wij niet konden publiceren. Audio/tv/foto was de grootste
losse groep (51), daarna computers (41), boeken (20) en sport (6). Daniel koos
audio; computers en boeken zijn bewust nog niet gebouwd.

**Wat er nieuw aan de methode is.** De 68 cat3-nummers komen niet uit de
SYI-picker maar uit `searchCategoryOptions` van `/l/audio-tv-en-foto/` — publiek,
geen login. Dat is aantoonbaar veiliger dan raden: id en naam staan daar in
hetzelfde JSON-record, dus een nummer kan niet bij de verkeerde naam belanden.
Bij telefoons en games bleek dat cat3 exact het L2-zoekcategorie-id is.

**Wat nog NIET bewezen is, en dat is belangrijk.** Dat de SYI-URL
`/plaats/31/{cat3}` het formulier ook echt in die categorie opent. `/plaats/` geeft
zonder login HTTP 401, dus dat is met een script niet te controleren. De muziek-
en antiektak zijn destijds wél in een ingelogde browser nagelopen tegen de
gerenderde categorienaam. Deze 68 nog niet. Het risico is beperkt — de vorm is
identiek aan muziek en antiek, en de tak is net als die twee twee niveaus diep,
dus zonder bucketId — maar het is een aanname en geen meting. Zolang die niet
gedaan is, is dit de zwakste schakel in de tak.

**De extensieversieondergrens is bewust NIET verhoogd.** Een oude kopie die deze
categorieën niet kent geeft `CategoryUnresolvedError` met de versie in de melding
— zichtbaar falen, geen stil half werk. De ondergrens is er voor dat tweede
geval; hem hiervoor optrekken zou iedereen buitensluiten voor een categorie die
de meesten nooit gebruiken.

**Aanvulling 27-08-2026, avond.** De audio-ids zijn alsnog langs een tweede,
onafhankelijke bron gelegd: `/lrp/api/search?l1CategoryId=31&l2CategoryId={cat3}`
gaf voor alle 68 echte advertenties terug die zelf datzelfde `categoryId` dragen,
met titels die bij de categorienaam passen. 68 van 68, geen leeg, geen afwijking.
Daarmee staat de koppeling id ↔ categorie vast; alleen de vorm van de SYI-URL is
nog een aanname.

Twee dingen die daarbij vastgesteld zijn en die je moet weten voor de volgende
keer: `/plaats/` geeft zonder login HTTP 401 **vóór** enige controle van de URL —
`/plaats/99999/38` geeft precies hetzelfde antwoord als een geldige. Uit een
statuscode valt hier dus niets af te leiden, net zoals bij Admarkt een onbekend
adres HTTP 200 gaf. En de Claude-in-Chrome-extensie was niet verbonden, dus de
ingelogde controle kon deze sessie niet gedaan worden.

**Bevestigd 27-08-2026, ingelogd.** `/plaats/31/38` opent op "Audio, Tv en Foto >
Luidsprekers". De URL-vorm klopt dus, zonder bucketId, en alle 68 delen die vorm.
De audio-tak is af.

Eén ding dat we bij het bouwen niet wisten: de aanname in `crosslist.py` dat
niet-kledingtakken géén kenmerkvelden hebben, klopt niet voor audio. Luidsprekers
vraagt om Type, Wattage, Merk en Handelsnaam fabrikant. Verplicht zijn ze niet —
alleen titel, beschrijving en foto's zijn dat — en Merk en Conditie vullen we al,
want die twee functies zijn algemeen en niet kleding-only. Type en Wattage blijven
leeg. Gevolg is hetzelfde als ooit bij sportkleding: wie in de zoekfilters op
"Type" filtert, krijgt onze advertentie niet te zien. Geen storing, wel gemiste
zichtbaarheid. `mpSportType()` is het model als je dit wilt oplossen.

### 2026-08-27 — Type en Wattage bij audio

De kenmerkvelden zijn ingevuld voor de audio-tak. Twee dingen om te onthouden.

**De keuzelijsten zijn opgehaald, niet bedacht.** Marktplaats' eigen zoek-API
geeft ze gewoon weg: `/lrp/api/search?l1CategoryId=31&l2CategoryId={cat3}` levert
onder `facets` per attribuut de complete optielijst met labels — dezelfde lijst
die een koper in de filterbalk ziet. Geen login nodig. Dit is de route om te
gebruiken als er nog een tak bij komt; raden of uit het formulier overtypen is
niet meer nodig. 39 van de 68 audio-categorieën hebben een Type, en maar twee een
Wattage (luidsprekers en versterkers). De wattage-indeling verschilt per
categorie: luidsprekers kent "120 tot 150 watt", versterkers niet.

**Nederlandse meervouden kostten twee ronden.** Het label is "Vloerstaande
luidspreker", de verkoper schrijft "vloerstaande luidsprekers", en op letterlijk
zoeken viel dat terug op "Overige typen". Nu mag het laatste woord een uitgang
dragen (-e, -en, -s, -es) plus de klankwisseling s→z en f→v, want het meervoud
van "lens" is "lenzen". Alleen het láátste woord: alles vrijgeven zou van "Enkel"
ook "enkele kabels" maken.

Wattage wordt alleen ingevuld als er echt een getal met watt in de tekst staat.
Raden is hier net zo schadelijk als een verkeerd type — de koper filtert de
advertentie er juist mee weg. Alleen Marktplaats; voor 2dehands is niet nagemeten
of dezelfde labels bestaan.

### 2026-08-27, avond — controleronde: drie echte fouten

**1. Vinted-voorkeur blokkeerde groepen die niemand kon aanvinken.** De lijst met
categoriegroepen staat op drie plekken: de vinkjes in het dashboard
(`VINTED_GROEPEN` in app.html), wat er bij opslaan bewaard mag blijven
(`VINTED_GROEPEN_GELDIG` in instellingen.py) en waarop de server blokkeert
(`GROEPEN` in platformregels.py). "wonen" stond alleen in de laatste — sinds
augustus. Gevolg voor iedere verkoper mét een ingestelde voorkeur: elk
woon-artikel werd op Vinted geweigerd met "je eigen instelling laat alleen X toe",
terwijl die instelling niet bestond en in het dashboard niets aan de hand leek.
Met "audio" zou het vandaag opnieuw zijn gebeurd. Alle drie gelijkgetrokken,
`tests/test_vinted_voorkeur.py` bewaakt het.

**2. Vijf Vinted-hints werden stil overschreven.** Onderaan `CAT_HINTS` staat een
blok "legacy keys". Vijf daarvan bestaan nog gewoon: sportkleding, ondergoed en
pakken (dames en heren). JavaScript laat bij een dubbele sleutel zonder één
waarschuwing de laatste winnen, en dat blok staat onderaan — dus "ondergoed"
kreeg `["underwear"]` in plaats van `["lingerie & nightwear", "socks &
underwear"]`. Weggehaald; er staan nu vier tests op dubbele sleutels in
CAT_HINTS, MP_CATEGORIES en de keuzelijst.

**3. Het klantenslot in de koude mail viel OPEN in plaats van dicht.** `_klanten()`
haalt de accountlijst bij Supabase en ving elke fout op met een lege verzameling —
die ook nog werd onthouden. `is_klant()` zei dan voor iedereen "nee", elke
betalende klant gold weer als prospect, en één hapering vergiftigde de hele run.
Dat is letterlijk het pad waarlangs Jaap zijn afscheidsmail kreeg, en het kon
alleen omdat de server destijds op de anon-sleutel draaide (auth/admin faalt daar
altijd). Nu: bij twijfel geldt iedereen als klant, een mislukte poging wordt niet
onthouden, en een lege lijst telt als storing — er is altijd minstens één account.
De run meldt het als kop, want nul mails ziet er anders precies zo uit als een
rustige dag.

**Bijvangst, en die is niet klein: omnivaleur.nl staat geparkeerd.** Het domein
waar de koude mail vandaan komt (`daniel@omnivaleur.nl`) heeft geen werkende
HTTPS — `omnivaleur.nl` geeft een time-out en `www.omnivaleur.nl` een SSL-fout.
Over gewone http komt er een Namecheap-parkeerpagina met "has been recently
registered... Want a domain name like this?". Iedere ontvanger die de afzender
natrekt komt daar terecht. Dit is DNS-werk bij Namecheap, geen code.

**Ook vastgesteld:** Railway draait nu op de `service_role`-sleutel (`/health`
toont `supabase_key_role`). De oude notitie dat alles met auth.admin stil faalt,
is daarmee achterhaald.

### 2026-08-27, laat — audio 68/68 bevestigd, en drie dingen rechtgezet

**De audio-tak is volledig geverifieerd.** Niet met een steekproef: in een
ingelogde browser alle 68 opgehaald via `/plaats/31/{cat3}` en de `categoryName`
uit het antwoord vergeleken met de naam die Marktplaats zelf aan dat id hangt.
68 van 68 gelijk. Dit is meteen de snelste route voor een volgende tak — vanuit
een ingelogd tabblad met `fetch()` en die ene regex, geen 68 keer klikken.

**De Notion-markering is gedraaid.** De Fase-optie "0. Kan (nog) niet" bestond
niet en is aangemaakt (let op: Notion vervangt bij zo'n PATCH de héle optielijst,
dus de bestaande 18 moesten meegestuurd worden). Daarna alle 75 onbedienbare
leads gemarkeerd, fase gezet en reden op de pagina.

**Twee dingen die ik verkeerd had en die niemand moet overnemen:**

1. De Claude-extensie leek op een ander account te draaien (`heidi.cumbre@gmail.com`
   stond in het instellingenscherm). Dat was niet de oorzaak — de koppeling kwam
   even later gewoon tot stand. Een lege browserlijst betekent "nog niet
   verbonden", niet "verkeerd account".
2. Ik dacht dat de koude mail SPF zou falen omdat de SPF van omnivaleur.nl alleen
   Zoho noemt. Onjuist: Resend gebruikt `send.omnivaleur.nl` als Return-Path, en
   dáár staan MX (feedback-smtp.eu-west-1.amazonses.com), SPF
   (`include:amazonses.com`) en de DKIM-sleutel keurig. De mailauthenticatie is
   in orde; DMARC staat op `p=none`, wat voor een jong domein normaal is.

**Wat er van omnivaleur.nl wél stukstaat is alleen de website**, en dat blijft
staan: geen werkende HTTPS, en over http een Namecheap-parkeerpagina. De
nameservers staan nog op `dns1/dns2.registrar-servers.com`. De .com draait al via
Cloudflare; het domein daar onderbrengen en een doorverwijzing naar omnivaleur.com
zetten lost het in één keer op, inclusief geldig certificaat. Vereist een login bij
Namecheap, dus dat blijft handwerk.

### 2026-08-27 — omnivaleur.nl klaargezet bij Cloudflare

Het domein stond al in Cloudflare, in het account op **danieldekoning66@gmail.com
(inlog via GitHub)** — niet in dat op dkresellacademy, waar nul zones staan. Zone
stond op "pending": ooit toegevoegd, nameservers nooit omgezet. Daarom serveerde
het al die tijd de Namecheap-parkeerpagina zonder HTTPS.

Wat er nu klaarstaat (alles in de zone, nog niet live):
- Wortel-A wees naar de parkeerpagina (162.255.119.233) en staat nu op 192.0.2.1,
  een adres uit de documentatiereeks RFC 5737 dat nergens bestaat. Bewust: het
  verkeer komt daar nooit, de doorverwijzing grijpt eerder in. `www` wees als
  CNAME naar `parkingpage.namecheap.com` en wijst nu naar het domein zelf.
- Eén redirect rule: `omnivaleur.nl` en `www` → `https://omnivaleur.com`, 301, pad
  en querystring blijven behouden.
- "Always Use HTTPS" aan, SSL op flexible (de doorverwijzing gebeurt aan de rand,
  dus er is geen origin waar een certificaat toe doet).

**Alle acht mailrecords stonden er al en zijn geverifieerd** vóór er iets werd
aangeraakt: MX naar Zoho (3×), MX `send` naar Amazon SES, SPF op de wortel en op
`send`, DMARC, Zoho-verificatie en twee DKIM-sleutels (resend én zmail). De
zmail-DKIM staat zelfs alleen in Cloudflare en niet in de huidige live DNS, dus de
mailopzet wordt met de omzetting eerder beter dan slechter. Er is een volledige
inventaris van de live DNS gemaakt vóór de wijziging.

**Nog te doen, en alleen met de hand:** bij Namecheap de nameservers omzetten van
`dns1/dns2.registrar-servers.com` naar `ariadne.ns.cloudflare.com` en
`keenan.ns.cloudflare.com`. Daar kan geen sessie bij — inloggen bij een registrar
is handwerk. Pas ná die omzetting wordt alles hierboven actief.

**Stand 28-08-2026, einde van de avond.** De nameserverwijziging bij Namecheap was
de eerste keer níet opgeslagen (dropdown stond nog op "Namecheap BasicDNS", velden
leeg). Alsnog gezet: Custom DNS met `ariadne`/`keenan.ns.cloudflare.com`. SIDN heeft
het verwerkt — whois toont beide Cloudflare-nameservers met `Updated Date:
2026-08-28` — maar na ~50 minuten serveren `ns1/ns3/ns4.dns.nl` nog steeds de oude
delegatie. Cloudflare antwoordt gezaghebbend (aa-vlag, geldige SOA) en er is geen
DNSSEC, dus er is geen technische blokkade; het is puur SIDN's publicatieschema.

Controleer bij de volgende sessie eerst of het inmiddels live is:

    dig +norecurse NS omnivaleur.nl @ns1.dns.nl

Staat daar Cloudflare, controleer dan in deze volgorde: MX (moet Zoho blijven),
SPF op de wortel én op `send`, DMARC, de twee DKIM-sleutels, en pas daarna de
doorverwijzing naar omnivaleur.com inclusief een pad zoals `/pricing`. Blijft het
na een dag hangen, dan is het een vraag aan Namecheap of ze de EPP-update echt
hebben doorgestuurd — de registratie zegt van wel.

### 2026-08-28 — Jaap: 60 advertenties weg zonder vervanger, en het plaatsen ligt nog stil

Jaap (info@zilverwebsite.nl, gebruiker `26cf5471`, ~1.222 advertenties) meldde dat
alles keurig verwijderd werd maar dat er bij het plaatsen alleen een kop en een
prijs verschenen — geen foto's, geen tekst, geen kenmerken. Er stonden ~50 halve
Marktplaats-tabbladen open.

**Wat er in zijn eigen gegevens stond.** Op 28-08 't ochtends: 60 geslaagde
verwijderingen, 61 mislukte plaatsingen, waarvan **58 met "This item has no
description"**. Van zijn 1.222 items hadden er **532 geen omschrijving** — die zijn
geïmporteerd uit de zoeklijst van Marktplaats, en die geeft alleen titel, prijs en
één omslagfoto. Het plaatsformulier eist een tekst, dus de extensie brak af nog vóór
de foto's; daarom bleven ook de kenmerken leeg. Marktplaats zet een verwijderde
advertentie meteen op **410**, dus die 60 teksten waren daarmee ook weg (Wayback had
niets). Vanaf 22-08 t/m 27-08 mislukten zijn herplaatsingen al, maar toen op de
verwijderstap — dan blijft de advertentie staan en gaat er niets verloren. Pas toen
verwijderen op 28-08 wél werkte, werd het schadelijk.

**Wat er is veranderd (commits f7090b6, a041057, en de 1.0.258-bump).**
1. `refresh_listing` weigert een relist als het item geen omschrijving of foto's
   heeft (`ontbreekt_voor_herplaatsen`) — er wordt dan niets verwijderd.
2. Vlak vóór het herplaatsen wordt ontbrekende tekst/foto's/merk/maat alsnog van de
   eigen, nog live advertentiepagina gehaald (`mp_enrich.vul_item_aan_uit_advertentie`).
3. De extensie maakt het formulier af vóór hij over de tekst klaagt, en wacht op de
   tekst-editor in plaats van hem meteen "niet gevonden" te noemen.
4. De dagteller van de handmatige verversknop telde élke verwijderopdracht mee, ook
   die van de nachtronde — daardoor stond die knop bij hem altijd op "3 per dag
   bereikt". Telt nu alleen nog geslaagde, handmatige verversingen
   (`payload->>_handmatige_verversing`).

**Data-reparatie (eenmalig, al gedraaid).** 474 van de 532 lege omschrijvingen
gevuld: 338 vanaf de nog live MP-advertentiepagina's, 50 uit zijn eigen webshop
(`scripts/backfill_beschrijving_uit_webshop.py`). Zijn webshop **zilverwebsite.nl is
een Shopify-winkel** met dezelfde titels; `/products.json` staat achter Cloudflare
en weigert httpx (429, `cf-mitigated: challenge`) maar komt er via **curl met
browser-headers** wél doorheen. Er blijven **58 items zonder tekst** over; fuzzy
matchen op titel gaf te veel bijna-treffers ("ring met bloedkoraal" → "ring met
granaat", "knipslot 1875" → "1881") en is bij een antiekhandelaar erger dan niets.

**Nog niet opgelost — hier verder oppakken.** Van de 34 advertenties die terug
konden (`scripts/herstel_verwijderde_advertenties.py`) is er **geen enkele
geplaatst**: 7× "Not published — complete the fields marked in red" met een compleet
formulier (tekst 205–1936 tekens, prijs gevuld, gratis-keuze aangeklikt, géén rood
veld), 1× een time-out. De overige 26 opdrachten zijn **gepauzeerd tot 28-08 15:49
UTC** via `scheduled_for`, zodat hij er niet nog 26 vastgelopen tabbladen bij krijgt.

Wat we wél weten: op 21-08 plaatste hij nog 60 advertenties foutloos, en toen
draaide hij **1.0.218**; sindsdien nul geslaagde plaatsingen. Bij een andere klant
(`3bfbed2c`) lukt plaatsen op Marktplaats gewoon (22 geplaatst sinds 24-08). Het zit
dus in zijn situatie, niet in de code als geheel. Sterkste verdachte: zijn ~50
openstaande Marktplaats-tabbladen — één "Site verlaten?"-venster daarin zet álle
tabbladen van dezelfde site stil, óók het tabblad dat op dat moment publiceert. Dat
is precies de fix uit 1.0.256, en hij draait 1.0.251. **1.0.258 meldt nu ook hoeveel
foto's het formulier vasthoudt bij een mislukte plaatsing** — dat was het enige gat
in de bewijsvoering, want Marktplaats weigert zonder foto net zo geruisloos.

Openstaand handwerk: `dist/omnivaleur-extension-1.0.258.zip` uploaden in de Chrome
Web Store, en Jaap eerst alle Marktplaats-tabbladen laten sluiten. Zijn categorie
klopt op één na: "Miniatuur varken op ladder, W. van Strant, Amsterdam, 1732" staat
in "Beelden en houtsnijwerken" in plaats van "Goud en zilver" — dat is de
"spaarvarken" die hij meldde. Hooguit 15 van zijn 1.222 staan zo scheef.

### 2026-08-28 — De aanhef van de koude mail: winkelnaam en HTML-code

Albert Kok kreeg als eerste mail "Hi kok modelauto&#x27;s,". Twee fouten in de
eerste regel die iemand leest: zijn Marktplaats-verkopersnaam gebruikt als
voornaam, en de HTML-codering waarin Marktplaats die naam teruggeeft onvertaald
meegenomen. Hij reageerde alsnog positief ("Heel graag"), maar het is precies het
soort regel waarop de rest afhaakt.

Wat er is veranderd:
- Namen worden ontcodeerd zodra ze binnenkomen (`unescape` in
  `leadgen_marktplaats.py`), en `_schoon()` in `leadgen_mail.py` vangt af wat er
  al in de administratie stond. Zeven bestaande gevallen zijn rechtgezet.
- De aanhef gebruikt alleen nog een voornaam die letterlijk als voornaam in het
  veld staat (`voornaam`/`contactpersoon`). Er is een regel geprobeerd die er een
  voornaam uit een verkopersnaam afleidde — twee woorden, hoofdletters, geen
  handelswoord — maar tegen de echte lijst gehouden gaf die "Hi Boutique,",
  "Hi Trimsalon," en "Hi Partytenten,". Van de 1.447 leads was er geen enkele bij
  wie het klopte, dus staat er nu overal gewoon "Hi,". Vastgelegd in
  `tests/test_leadgen_concepten.py`.

Het antwoord aan Albert staat als concept klaar in Concept, met de link naar
/mp-video.

## 28-08-2026 — Egbert kon niet meer inloggen: twee fouten in de auth-laag

Egbert Brouwer (info@papas-plectrums.nl, `bcdf9aa4`) meldde: eerst een paar keer
uitgegooid vlak na het inloggen, daarna helemaal niet meer binnenkomen, met
"Invalid email or password" op een ingevuld (autofill-)wachtwoord.

**Wat er in zijn accountgegevens staat.** Laatste geslaagde inlog 28-08 07:50:57
UTC; zijn auth-rij werd 07:51:07 nog één keer bijgewerkt (= een
tokenvernieuwing, tien seconden na het inloggen — dus er ging tien seconden na
zijn inlog een verzoek mis dat het dashboard als "sessie verlopen" las). Niet
geblokkeerd, e-mail bevestigd, `recovery_sent_at` leeg (hij heeft dus nooit zelf
een herstelmail aangevraagd). Inloggen via de live server werkt op dit moment
gewoon: getest met een tijdelijk diagnose-account, en weer verwijderd.

**Fout 1 — een weggevallen verbinding zag eruit als een verkeerd wachtwoord.**
`database.py` documenteert al jaren dat Supabase geregeld een hergebruikte
verbinding verbreekt; voor gegevens ving `execute_with_retry` dat op. De
auth-laag had niets: `login` vertaalde élke uitzondering naar "Invalid email or
password", en `get_current_user_full` (draait op zo goed als elk verzoek) élke
uitzondering naar 401 "sessie verlopen". Het dashboard gooit je bij een 401 naar
het inlogscherm en de extensie wist bij 401/403 haar inlogbewijs. Eén hik =
eruit gegooid; hik tijdens het opnieuw inloggen = "verkeerd wachtwoord". Nu:
`auth_met_herkansing()` probeert het drie keer opnieuw bij verbindingsfouten en
5xx, en levert daarna `AuthTijdelijkOnbereikbaar` → **503**, niet 401. Een echt
4xx-antwoord van Supabase gaat ongemoeid door. Inloggen onderscheidt nu ook
"te veel pogingen" (429) en "e-mail niet bevestigd" (403).

**Fout 2 — het wachtwoord van de een kon op het account van de ander landen.**
`auth.update_user({"password": ...})` schrijft naar de sessie die IN DE CLIENT
staat (`self.get_session()`), niet naar de aanvrager. Alles liep over één
gedeelde client, waarop élke inlog en élke tokenvernieuwing van welke klant dan
ook een sessie neerzette — en inloggen/verversen draaien via `asyncio.to_thread`,
dus die schuiven écht tussen `set_session` en `update_user` door. Klikte er
iemand een herstellink af op het verkeerde moment, dan kreeg een willekeurige
andere klant dat wachtwoord en kon die er niet meer in. Nu pakt elk
auth-endpoint een `verse_auth_client()`: eigen verbinding, lege sessie, na het
verzoek weg. `tests/test_auth_sessies_gescheiden.py` bootst de race na en faalt
aantoonbaar op de oude opzet.

Van fout 2 is niet bewezen dat hij Egbert getroffen heeft (niemand vroeg in dat
uur een herstelmail aan), maar het is een echt gat en het staat nu dicht.
Openstaand: Egbert één keer laten inloggen; lukt dat nog steeds niet, dan
"Wachtwoord vergeten" — dat pad werkt en is nu ook race-vrij.

## 28-08-2026 — Herplaatsen kon een advertentie kosten bij een verbindingshik

Jaap (zilverwebsite.nl) draaide eindelijk 1.0.258, verving één advertentie en
kreeg op zijn scherm: `Refresh failed unexpectedly: EOF occurred in violation of
protocol (_ssl.c:2417)`. Dat is een weggevallen verbinding met Supabase, geen
fout in zijn gegevens.

Twee dingen zaten fout:

1. **De hik werd niet opgevangen.** `execute_with_retry` herhaalde zulke fouten
   al, maar het hele herplaats-, plaats- en verwijderpad loopt via
   `naast_de_lus`, en die herhaalde niets. Bovendien stond de kale
   `ssl.SSLEOFError` niet in `_HERSTELBAAR`, dus zelfs `execute_with_retry` zou
   hem hebben doorgelaten. Nu tellen `ssl.SSLError` plus een tekstherkenning
   ("EOF occurred in violation of protocol", "Server disconnected", "connection
   reset/aborted") als herstelbaar, en kan `naast_de_lus` herkansen.

   **Maar `herkans` staat standaard UIT, en dat is met opzet.** Valt de
   verbinding weg terwijl het *antwoord* onderweg is, dan staat de rij er
   misschien al en maakt een tweede poging er nog een. Bij een opdracht in de
   wachtrij is dat een tweede advertentie. Blind herhalen zou het probleem dus
   alleen verplaatsen. Zet `herkans=True` alleen op aanroepen die je twee keer
   mag doen; voor een insert hoort het patroon uit `crosslist._exec`: zelf een
   uuid bepalen en `dubbel_is_ok=True`, zodat een dubbele sleutel "stond er al"
   betekent. De twee opdrachten van een herplaatsing gaan nu zo.

2. **De volgorde in `refresh_listing` was onveilig.** De verwijderopdracht werd
   als eerste weggeschreven; pas dáárna werden de prijs, de vertaling
   (Anthropic, over het net) en de verzend-/fabrikantinstellingen opgehaald om
   de herplaatsing te bouwen. Viel de verbinding op één van die stappen weg, dan
   stond de verwijdering er wél en de herplaatsing niet. De extensie haalde de
   advertentie dus keurig weg en er kwam nooit iets terug. Erger: de status ging
   pas ná de tweede insert op `relisting`, dus `herstel_vastgelopen_werk` zag hem
   niet eens — de advertentie was stil en definitief weg.

   Nu gebeurt álle voorbereiding vóór de eerste insert. De twee inserts staan
   direct achter elkaar en lukt de tweede alsnog niet, dan wordt de
   verwijderopdracht weer verwijderd (of anders op `cancelled` gezet). Uitkomst:
   twee opdrachten of geen enkele — nooit alleen een verwijdering.

   De verwijdering moet wél als eerste in de database blijven staan: het
   dispatch-filter in `jobs.py` zoekt de bijbehorende verwijdering op
   `created_at <= die van de herplaatsing`. Draai je dat om, dan vindt hij hem
   niet en plaatst hij een tweede advertentie naast de nog levende oude.

Verder krijgt de verkoper bij zo'n hik nu een 503 met leesbare tekst ("nothing
was changed and your listing is still live") in plaats van Python-jargon.

Vastgelegd in `tests/test_herplaatsen_verbindingshik.py`.

## 28-08-2026 — Twee Marktplaats-rubrieken erbij voor woontextiel

Voor De Juiste Toon (Etten-Leur, 237 advertenties) vielen 21 advertenties buiten
de rubrieken die we aankonden. Toegevoegd:

- `wonen vachten` → Marktplaats 504/536 (Woonaccessoires | Overige) — schapen-,
  rendier- en koeienvachten; Marktplaats heeft er geen eigen rubriek voor en
  verkopers zetten ze daar zelf ook neer.
- `wonen beddengoed` → Marktplaats 504/525 (Slaapkamer | Beddengoed) — spreien.

Beide id's en hun ouder (504) zijn nagekeken in de openbare categorieboom van
Marktplaats zelf (`lrp/api/search`, facet RelevantCategories), niet geraden. De
SYI-pagina zelf geeft 401 zonder ingelogde sessie, dus die weg was hier niet
beschikbaar.

Toegevoegd in alle vijf de plaatsen die `test_category_taxonomy.py` bewaakt:
`frontend/app.html`, `extension/background.js`, `extension/content/vinted.js`,
`backend/platforms/ebay.py`, `backend/api/imports.py`.

Daarmee dekken we 234 van Toons 237 advertenties. **Let op:** de bewering in de
koude mail aan Toon ("290 stuks in kleding") klopte niet — het zijn 237
advertenties en het is woontextiel, geen kleding.

Zijn webshop (dejuistetoon.eu, ~1.000 producten) draait op WooCommerce, en dat
ondersteunen we niet. Alleen Shopify.

## 28-08-2026 — Egbert: "je bent niet ingelogd bij Marktplaats" was twintig keer een verkeerde diagnose

Egbert Brouwer (info@papas-plectrums.nl, zakelijk, 4.250 advertenties binnen)
kreeg vanaf 22-08 twintig mislukte scans met exact dezelfde zin: "You don't
appear to be signed in to Marktplaats". Hij heeft elke keer zijn login
gecontroleerd. Uit de opdrachtenlijst op de server (tabel `jobs`) blijkt:

- 27-08 11:09 nog 2.000 nieuwe Admarkt-advertenties binnengehaald.
- 27-08 20:35 en daarna: mislukt in 5-6 seconden.

Uit de code volgt dwingend dat in al die mislukte rondes de Admarkt-stap NIET
is gedraaid: was hij wel gedraaid en mislukt, dan had de melding met "Admarkt:"
begonnen. De optionele toestemming voor admarkt.marktplaats.nl was dus weg,
zonder dat Egbert iets heeft aangeraakt. En met die toestemming weg viel de
scan door naar de tak "niet ingelogd", die voor een zakelijk account per
definitie onjuist is: zijn persoonlijke overzicht op www hoort leeg te zijn.

Wat er is veranderd:
1. De Admarkt-toegang hangt niet langer aan een optionele toestemming die kan
   verdwijnen — die staat vast in het manifest (https://*.marktplaats.nl/*,
   toegevoegd in 1.0.258).
2. Is het persoonlijke overzicht leeg, dan wordt Admarkt sowieso bekeken, ook
   als de schakelaar uitstaat. De schakelaar is nu een gewone voorkeur in
   chrome.storage, die een update overleeft.
3. Elke mislukte scan noemt voortaan de waargenomen feiten (API-status, aantal,
   ingelogd ja/nee, Admarkt aan/uit). Twintig identieke meldingen zonder cijfers
   hebben een week gekost.
4. Zolang oude extensies rondlopen (Egbert draait 1.0.251, de Web Store loopt
   achter) zet de server de melding zelf recht in backend/api/jobs.py:fail_job.


## 28-08-2026 — Shopify weigert de app; koppelen gaat nu met een eigen sleutel

Shopify heeft de app-aanvraag op **paused** gezet (ref 131213). Reden, letterlijk:
"Shopify is not currently accepting apps that connect to a marketplace system
outside of Shopify. This applies to all apps." Dat is beleid, geen defect: er is
geen versie van Omnivaleur die daar doorheen komt zolang ze naar Marktplaats,
Vinted en eBay publiceert. Bezwaar maken heeft daarom geen zin.

De app stond op "limited visibility" — hij stond nog niet in de App Store. Wat
gepauzeerd is, is de aanvraag; de twee bestaande koppelingen bleven werken.

**De nieuwe weg.** Nagekeken in Shopifys eigen documentatie: een app die de
winkelier zelf in zijn beheerscherm maakt (Settings → Apps and sales channels →
Develop apps) heeft géén review nodig, en levert een Admin API access token
(`shpat_…`) dat via exact dezelfde `X-Shopify-Access-Token`-kopregel werkt.
"Custom distribution" via een Partner-app is géén alternatief: die is beperkt tot
één winkel per app.

Gebouwd:
- `POST /api/platforms/shopify/connect-token` — controleert de sleutel eerst bij
  Shopify (`/admin/oauth/access_scopes.json` + `shop.json`) en slaat pas daarna
  op. `read_products` en `write_products` zijn hard vereist; de rest wordt
  gemeld, niet geblokkeerd. `extra_data.koppeling = "eigen_sleutel"`.
- Een venster in het dashboard met de drie stappen en alle benodigde rechten
  eronder, inclusief waarschuwing wat er stukgaat als er eentje ontbreekt.
- `backend/services/shopify_orders.py` — **dit is het belangrijke deel.** De
  verkoopmelding liep over de webhook `orders/paid`, en die hoort bij ÓNZE app.
  Bij een zelfgemaakte app komt hij nooit binnen, dus zou een winkelier stil zijn
  belangrijkste functie kwijtraken: iets dat in de eigen winkel verkocht is bleef
  dan op Marktplaats, Vinted en eBay te koop staan. Deze ronde haalt elke 5
  minuten de betaalde bestellingen op en draait dezelfde afhandeling. Draait voor
  álle winkels, ook de OAuth-koppelingen — daar is de webhook dan de snelle
  melding en dit het vangnet.

Nagekeken tegen de echte winkels, niet alleen tegen tests:
- `ywqad3-xb.myshopify.com` (Revaleur) antwoordt 200 en heeft alleen
  `read_products, write_products` — dus **geen `read_orders`**, waardoor de
  verkoopcontrole daar 403 geeft en overslaat. Wil je dat werkend hebben, dan
  moet die winkel opnieuw gekoppeld worden met meer rechten.
- `1xhfjx-a0.myshopify.com` (gekoppeld 27-08) geeft **401 — die sleutel is
  ongeldig**. Die klant heeft op dit moment een kapotte Shopify-koppeling.

Vastgelegd in `tests/test_shopify_eigen_sleutel.py` (29 tests).

### Correctie, later op 28-08-2026: de "eigen sleutel"-route bestaat niet meer voor nieuwe apps

De instructies die hierboven staan (Settings → Develop apps → Reveal token once)
zijn achterhaald. Shopifys eigen documentatie zegt nu letterlijk: *"You can no
longer create new admin-created custom apps. Existing apps are unaffected and
continue to work."* Wie zo'n app al had, houdt hem en houdt zijn sleutel. Wie er
nu een wil, kan die weg niet meer inslaan.

Wat er nog wél is:

- **Client credentials grant** — werkt, maar **alleen als de winkel en de app in
  dezelfde Shopify-organisatie zitten**. Dat geldt voor Daniels eigen
  Revaleur-winkel (app "Omnivaleur" in de Dev Dashboard, 1 install), maar per
  definitie niet voor klanten. Tokens verlopen na 24 uur en moeten dus telkens
  opnieuw worden opgehaald met client id + secret.
- **Authorization code grant (OAuth)** — de weg die we al hebben. De vraag is of
  een public-distribution app die (nog) niet is goedgekeurd, door winkeliers
  búiten onze organisatie geïnstalleerd kan worden via een directe installatielink.
  Shopifys openbare documentatie zegt daar niets over. **Dit is de beslissende
  vraag en die moet bij Shopify Partner Support gesteld worden.**

Wat blijft staan van wat er gebouwd is:
- `POST /api/platforms/shopify/connect-token` en de controle erachter zijn
  correct: ze accepteren elk geldig Admin API-token, dus zowel dat van een
  bestaande custom app als een OAuth-token.
- `backend/services/shopify_orders.py` is correct en nodig ongeacht welke route
  het wordt.
- Het venster in het dashboard beweerde de oude stappen; dat is gecorrigeerd naar
  een eerlijke uitleg plus de vereiste rechten.

Bronnen:
- https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/generate-app-access-tokens-admin
- https://shopify.dev/docs/apps/build/dev-dashboard/get-api-access-tokens

## 28-08-2026 — Jaap (Zilverwebsite): drie klachten, drie aantoonbare oorzaken

1. **"Site verlaten?" bevroor het publiceren.** De plaatsknop navigeert de
   pagina weg en het Marktplaats-formulier hangt daar een beforeunload aan.
   content/unload_guard.js bestond al, maar werd alleen aangeroepen als WIJ een
   tabblad sloten of wegstuurden — niet bij de navigatie die de plaatsknop zelf
   veroorzaakt. Nu ontwapenen we vlak vóór de klik (ONTWAPEN_AFSLUITVRAAG).
2. **Eén foto per advertentie.** Gemeten: alle 14 items in zijn publicatiewachtrij
   hadden precies één foto. Een import uit de Marktplaats-zoeklijst levert alleen
   het omslagplaatje; de hele reeks staat op de advertentiepagina. Publiceren
   vult dat nu zelf aan (crosslist.publish_to_platforms) in plaats van te wachten
   op de knop "Fill from Marktplaats".
3. **De onderkant van de tekst ontbrak.** Twee zelfverzonnen grenzen:
   `slice(0, 2000)` bij het invullen van het formulier en `DESC_MAX = 4000` bij
   het binnenhalen. Zijn 1.222 items hadden een mediaan van 2.044 tekens en een
   maximum van exact 4.000 — het bewijs. Beide staan nu op 20.000. Zijn eigen
   advertenties bewijzen dat Marktplaats langere tekst aanneemt; die tekst kwam
   daarvandaan. Het is NIET de Shopify-tekst, zoals hij vermoedde.

Aanvullen vervangt voortaan ook een afgekapte omschrijving, maar alleen als wat
wij hebben letterlijk het begin is van wat er op de pagina staat (_is_afgekapt).
Een tekst die de verkoper zelf heeft aangepast blijft staan.

Extensie 1.0.260.

### De weg die wél voor iedere klant werkt (28-08-2026, definitief)

De oplossing zat in een detail van de client credentials grant. Die eist dat de
app en de winkel in **dezelfde Shopify-organisatie** zitten. Dat leek een
blokkade voor klanten — tot je omdraait wie de app maakt: laat de **winkelier
zelf** de app in zíjn eigen organisatie aanmaken voor zíjn eigen winkel. Dan is
aan die voorwaarde per definitie voldaan, en werkt het voor iedereen. Geen
beoordeling, geen App Store, geen afhankelijkheid van Shopify's goedkeuring.

De winkelier maakt de app via Settings → Apps → Develop apps → "Build apps in Dev
Dashboard", zet de scopes, klikt Release, installeert hem op zijn winkel, en
geeft ons **client ID + client secret**. Wij wisselen die in voor een sleutel:

    POST https://{shop}/admin/oauth/access_token
    grant_type=client_credentials&client_id=…&client_secret=…
    → {"access_token": …, "scope": …, "expires_in": 86399}

Gebouwd:
- `vraag_token()` en `controleer_app_gegevens()` in `backend/platforms/shopify.py`.
- `POST /api/platforms/shopify/connect-app` — haalt éérst echt een sleutel op en
  slaat pas daarna iets op. Alleen zo weten we dat het werkt; precies dat
  ontbrak toen het venster stappen beschreef die Shopify had geschrapt.
- `_shop_creds()` is nu async en ververst de sleutel automatisch, met tien
  minuten speling. **Die sleutel leeft 24 uur** — zonder verversing zou álles
  elke dag stilvallen op een 401 die niemand ziet.
- Koppelingen zonder client_id/secret (OAuth, oude custom apps) blijven werken.

Let op bij wijzigen: de verkoopronde mag `extra_data` nooit terugschrijven vanuit
een kopie van vóór de verversing — dan wist hij de nieuwe vervaldatum weer. Hij
leest de rij daarom opnieuw vlak voor het wegschrijven.

Vastgelegd in `tests/test_shopify_eigen_sleutel.py` (37 tests).

### Naslag 28-08-2026 — bewijs uit de live Marktplaats-pagina's (Jaap)

Getoetst in plaats van beredeneerd:

- 41 van zijn advertenties die nog online stonden gaven allemaal **5 foto's** in
  plaats van de ene die wij hadden, en teksten van 1.756 tot **5.936** tekens.
  Daarmee is bewezen dat (a) de advertentiepagina de hele reeks foto's bevat en
  (b) Marktplaats teksten ver boven onze oude grenzen van 2.000 en 4.000 aanneemt.
  Die 41 zijn meteen bijgewerkt: <=1 foto ging van 108 naar 67 items, lege tekst
  van 58 naar 34, langste tekst van 4.000 naar 5.936.
- 4 advertenties gaven **HTTP 410**: al verwijderd voor een herplaatsing. Hun
  foto's zijn onherroepelijk weg. De 14 items in zijn publicatiewachtrij zitten
  in diezelfde toestand.
- 6 gaven 401 (Marktplaats wil daar een inlog voor); die kan alleen de extensie
  in zijn eigen browser ophalen.

Let op: een 410-pagina bevat 51 foto's van ÁNDERE advertenties van dezelfde
verkoper. `volledige_advertentie` weigert een niet-200 en pakt ze dus niet — dat
moet zo blijven, anders krijgt een item de foto's van zijn buurman.

Daarom oogst het herplaatsen nu vóór het verwijderen, ook als het item niet leeg
is maar alleen dun (één foto).

## 29-08-2026 — Jaap: de ontbrekende lap tekst is NIET afgekapt, hij bestond nooit

Jaap zag het scherper dan wij: "alle advertenties zijn exact op hetzelfde plekje
afgeknipt, onder het gewicht en de afmetingen, ongeacht hoeveel tekens ervoor
stonden." Dat sluit een tekenlimiet uit, en dus ook mijn eigen diagnose van
28-08.

Nagemeten op zijn echte gegevens: de omschrijving in `items` is TEKEN VOOR TEKEN
gelijk aan de omschrijving van hetzelfde product in zijn webshop
(www.zilverwebsite.nl/products.json), en die eindigt daar ook — bij gewicht en
afmetingen. Drie voorbeelden gecontroleerd: 242/242, 599/599, 192/192 tekens.

Zijn artikelnummer, winkeluitleg, verzendkosten en zoekwoorden stonden dus nooit
in de producttekst. Die tikte hij per advertentie zelf op Marktplaats erbij. Er
viel niets af te knippen en niets terug te halen: dit moest gebouwd worden.

**Nieuw:** instelling "Standard text under every listing" (Preferences →
Shipping-blok). Wat daar staat komt onder de omschrijving van elke advertentie op
elk kanaal, en nooit twee keer (een scan leest zijn eigen advertentie weer in).
Zie `instellingen.SLOTTEKST_MAX` en `crosslist._met_slot`.

Verder deze ronde, alles gemeten:
- Zijn extensie meldde zich 13 uur niet terwijl er 105 opdrachten klaarstonden.
  Sinds 07:13 draait hij weer; 8 van 8 publicaties geslaagd, nul fouten.
- 32 advertenties zijn vannacht en gisteren dun geplaatst (1 foto). De 47 die nog
  in de wachtrij staan dragen allemaal meerdere foto's en ~1.800 tekens.
- Foto's uit zijn webshop teruggezet: items met hooguit één foto van 108 → 67 → 34.
  De webshop levert 5 tot 11 foto's per product; het `products.json` van Shopify
  is openbaar. Zie scripts/backfill_beschrijving_uit_webshop.py (haalt nu ook foto's).
- De waarschuwing "er staat werk klaar maar je extensie meldt zich niet" is in een
  echte browser op bureaubladbreedte getoetst: display flex, zichtbaar, juiste tekst.

### 29-08-2026 — Publiceren zonder Shopify-koppeling ging naar Daniels eigen winkel

Bij het narekenen of de nieuwe koppeling voor iederéén werkt (en niet alleen
voor het eigen account) bleek er een terugval in te zitten die met klanten erbij
niet meer klopte.

`ShopifyPlatform.create_listing`, `delete_listing` en `update_listing_price`
vielen bij een verkoper zónder eigen koppeling terug op de winkel uit de
serverinstellingen (`SHOPIFY_STORE`, = `ywqad3-xb.myshopify.com`, Revaleur).
Ooit logisch — er was één account en dat was de eigenaar — maar met klanten erbij
betekende het: publiceren zonder koppeling zette het artikel van de een in de
wínkel van de ander, en verwijderen haalde daar iets weg.

Bereikbaar was het ook: `crosslist._publish_one` krijgt `creds_by_platform.get(p, {})`,
dus een lege dict voor wie niets gekoppeld heeft. Het dashboard verbergt de knop
wel, maar de server mag daar niet op vertrouwen.

Nu weigert `_eis_winkel()` dat met een leesbare uitleg. Vastgelegd in vier tests.

**Terzijde, over Jaap (zilverwebsite.nl):** hij heeft nooit een Shopify-koppeling
gehad — alleen `_settings`. Zijn 1.222 artikelen kwamen via de
Marktplaats-import binnen, en zijn advertenties staan op Marktplaats (600),
Vinted (5) en 2dehands (1). De zin "platgeslagen vanuit Shopify" in de mail van
28-08 klopte dus niet.

Er is op dit moment nog maar één Shopify-koppeling in de database: Revaleur, via
de nieuwe eigen-app-weg. Na het omdraaien van het clientgeheim nagemeten: sleutel
ophalen en producten lezen werkt.

### 29-08-2026 — extensie 1.0.260 ingediend bij de Chrome Web Store

Daniel heeft geüpload. Daarin zit: het "Site verlaten?"-venster dat vlak voor de
plaatsklik wordt uitgezet, de Admarkt-scan die niet meer aan een intrekbare
toestemming hangt, de foto's die bij het publiceren worden aangevuld, en de
diagnostiek bij een mislukt verwijderen (welke knoppen er op de pagina stonden).

Openstaand daarna: de 32 dun geplaatste advertenties van Jaap één keer
herplaatsen (hun foto's staan er weer bij), en zijn vaste tekst instellen zodra
hij ja zegt — die staat klaar in de conceptmail.

### 29-08-2026 — Dubbele en achterhaalde conceptmails: het slot zit nu in de postbus

Daniel meldde dat er steeds vaker twee concepten voor dezelfde persoon lagen,
dat concepten niet op het laatste bericht van een gesprek reageerden, en dat
mensen terugkwamen die hij al had beantwoord.

**Gemeten, niet geraden.** In de conceptenmap lagen drie voorstellen voor
frenky@autodokumentatie.nl — 08:49, 09:09 en 09:28 — alle drie een antwoord op
hetzelfde bericht (dezelfde In-Reply-To), alle drie met een andere tekst. Zijn
laatste bericht dateert van 20-08; Daniel had hem toen al beantwoord. Ook lagen
er nog concepten voor spacecartoonsafari en recycleland terwijl er ná dat concept
al een mail naar ze uit was gegaan.

**Waarom.** Elke controle daartegen leunde op de administratie in Supabase
(`warm_opvolg`, `laatste_inkomend`), en die wordt pas aan het EIND van een stap
weggeschreven. De ronde draait op de server met een harde grens van 25 minuten en
leest honderden berichten één voor één; wordt hij afgekapt, dan ligt het concept
er wel en weet de administratie het niet. De volgende ronde begint met het oude
beeld en doet het nog eens. `_ruim_concepten_op` stond onderaan de ronde en werd
dan óók niet meer bereikt.

**Wat er nu staat:**

1. `_waarom_geen_concept()` in `scripts/leadgen_mail.py`, aangeroepen vanuit
   `_zet_concept_klaar` — de enige doorgang waar alle vier de wegen naar een
   concept langskomen (gewone ronde, warme opvolging, vangnetronde, herstel).
   Vier vragen, alle vier aan de postbus zelf: ligt er al een concept voor deze
   persoon; ligt er al een concept op precies dit bericht; hebben wij hierna al
   iets gestuurd; heeft hij hierna nog iets geschreven. Bij twijfel of een
   onbereikbare postbus: geen concept.
2. De administratie wordt meteen na het neerleggen weggeschreven, niet aan het
   eind van de ronde.
3. Opruimen gebeurt nu vóór het schrijven, niet erna — anders houdt een
   achterhaald concept een nieuw en wél nodig antwoord voorgoed tegen.
4. Een afgekapte ronde wordt als waarschuwing gelogd (`backend/scheduler.py`) in
   plaats van stil te verdwijnen.

Vastgelegd in `tests/test_leadgen_dubbele_concepten.py` (15 tests).

**Nog open:** de ronde is echt te traag — hij haalt de map Verzonden (381
berichten) volledig op, bericht voor bericht, en doet dat meerdere keren per
beurt. De ticks liepen daardoor ~20 minuten uit elkaar in plaats van 10. Het slot
maakt de uitkomst goed, maar de traagheid zelf staat nog. De support-mailagent
(`scripts/support_mail_agent.py`) draait nergens ingepland en is buiten beschouwing
gebleven.

### 29-08-2026 — Jaaps vaste tekst staat aan

Hij zei ja. `slottekst` (1.604 tekens) staat op zijn account; de overige
instellingen zijn ongemoeid gebleven. 378 items bevatten het blok al compleet
(inclusief artikelnummer) en worden overgeslagen door de dubbelcontrole; 844
krijgen het er voortaan bij, zonder artikelnummer — dat verschilt per item en is
nergens meer vandaan te halen (de SKU komt maar bij 1 op de 40 overeen).

De 23 publicatieopdrachten die al in zijn wachtrij stonden zijn bijgewerkt, zodat
ook die compleet de deur uit gaan. Hij draait sinds vanochtend 1.0.260 en heeft
de foto's van de eerste tien dun geplaatste advertenties zelf rechtgezet.

### 29-08-2026 (later) — De mailronde was te traag; nu in bulk

De onderliggende oorzaak van de dubbele concepten (zie de vorige notitie) was de
duur van een ronde. De postbus werd bericht voor bericht bevraagd: één
IMAP-aanroep per mail, en voor de map Verzonden zelfs de volledige mail inclusief
bijlagen. Gemeten op de echte postbus: 635 kopteksten één voor één = 28,5 s, in
bulk 2,5 s. Dezelfde mappen werden per beurt drie tot vijf keer doorlopen.

Wat er veranderd is in `scripts/leadgen_mail.py`:

- `_fetch_in_bulk` / `_koppen_in_bulk` / `_berichten_in_bulk` /
  `_uid_berichten_in_bulk`: één IMAP-aanroep per groep in plaats van per bericht
  (koppen 200 tegelijk, volledige mails 20 — die dragen bijlagen).
  Omgezet: `_beantwoorde_berichten`, `_check_inbox`, `_eigen_mail_meenemen`,
  `_warme_opvolging`, `_verzonden_lezen`, `_ruim_concepten_op`,
  `_antwoorden_van_daniel`, beide lussen in `_opruimen`, en `_waarom_geen_concept`.
- `LAATST_DAGEN = 60`: de "wie sprak het laatst"-vragen liepen over ALLE post in
  Verzonden/INBOX/Beantwoord/Afval zonder enige grens.
- `_waarom_geen_concept` laat de mailserver zelf filteren
  (`SEARCH ... TO "<bedrijfsnaam>"`). Gemeten: 637 treffers → 3. Het slot kost nu
  0,3–1,0 s per concept in plaats van seconden.

Alles gemeten tegen de échte postbus, één voor één versus bulk, met vergelijking
van de uitkomst: identiek (635/635, 165/165, 151/151 volledige mails, 151/151 op
UID). `_verzonden_lezen` doet 637 mails nu in 10 s.

**Handmatig opgeruimd:** de vier achtergebleven concepten (twee dubbele van
Frenky, plus spacecartoonsafari en recycleland waar allang een mail naartoe was)
via `leadgen_mail.py concepten`. Frenky's `warm_opvolg` is op 2 gezet, zodat hij
geen derde zetje meer krijgt.

### 29-08-2026 — Vaste rolverdeling: CEO, klantenservice, developer

Door Daniel vastgesteld, expliciet als iets dat níet verandert. Dit staat hier en
niet alleen in lokale memory, omdat het voor elke sessie op elk account moet
gelden.

- **Daniel = CEO.** Hij schrijft geen conceptmails meer en controleert geen
  dubbelingen. Hij opent Concepten en ziet daar alleen juiste, volledige mails
  die hij hooguit verstuurt. Elke minuut die hij aan mailbeheer kwijt is, is een
  bug in dit systeem — geen normaal werk.
- **De mailagent = klantenservicemedewerker.** Analyseert álle mail, in- én
  uitgaand. Houdt de marketingvoortgang bij in het beheerdashboard. Escaleert
  naar Daniel alleen wanneer het echt nodig is.
- **Claude Code = developer.** Krijgt van de mailagent door welke bugs
  terugkomen, welk patroon erin zit en wie ze meldt; koppelt terug wanneer iets
  gerepareerd is, zodat de klant daar bericht over kan krijgen.

De mailagent en Claude Code horen ONDERLING te communiceren, niet allebei apart
via Daniel. Escalatie naar hem is de uitzondering, geen route.

### 29-08-2026 — De losse support-mailagent is opgeheven

`scripts/support_mail_agent.py` stond nergens ingepland en deed dus niets, maar
zag eruit alsof het meedeed. Eén klantenservicemedewerker, niet twee: alles loopt
via `scripts/leadgen_mail.py`. Verwijderd (staat in de geschiedenis als er ooit
iets uit terug moet).

Eén ding is eerst overgezet, want dat deed hij aantoonbaar beter: **antwoorden op
de code in plaats van op gevoel.** De leadgen-agent gaf het model alleen de mail
te lezen; bij een technische vraag levert dat een zelfverzekerde bewering op die
nergens op steunt. Dat is geen theorie — in de mail aan Jaap van 28-08 stond dat
zijn advertentietekst "platgeslagen vanuit Shopify" was, terwijl hij nooit een
Shopify-koppeling heeft gehad.

Nu zoekt `_grondslag()` op trefwoorden uit het bericht de bijbehorende broncode op
en gaat die als bewijsmateriaal mee, met de harde regel dat er geen technische
bewering mag staan die daar niet in terug te vinden is. Zie
`GRONDSLAG_BESTANDEN` — nieuwe onderwerpen vragen om een regel daarbij, niet om
het model zelf te laten raden waar het moet kijken.

### 29-08-2026 — De klantenservice houdt zelf bij wat er speelt, en praat met de developer

Uitwerking van de rolverdeling hierboven. Nieuw: `scripts/mail_analyse.py`,
aangehaakt in de tien-minutenronde van `leadgen_mail.py tick`.

**Alle post wordt gelezen, in- én uitgaand.** Per bericht: thema, stemming, is
het een storing, is het een klant, en één zin samenvatting. Opgeslagen in
`leadgen_opslag` onder `mail_analyse` — bewust géén nieuwe tabel, want dat zou
een handmatige migratie in Supabase vragen en Daniels tijd is juist wat dit moet
besparen. Laatste 600 berichten, 25 per beurt.

**Wat bij Daniel hoort, en niet meer dan dat.** Door hem zelf gekozen op
29-08-2026: geld, een klant die dreigt te stoppen, een storing bij meerdere
mensen, en iets wat de agent niet kan onderbouwen. Dat staat als lijst bovenaan
Marketing → Klantenservice in het beheerdashboard (`GET /api/beheer/klantenservice`).
Alleen geld en vertrek zijn spoed en krijgen ook een mailtje; de rest niet, want
daar wil hij geen post voor. Ook gekozen: **alles blijft concept**, er gaat nooit
iets automatisch de deur uit.

**De lijn klantenservice → developer.** Storingen worden gebundeld op een vaste
sleutel. `python3 scripts/mail_analyse.py bugs` is het postvak van de developer;
dit staat nu als vaste stap 3 in `CLAUDE.md`, naast de commits en deze notities.
Staat er `⚠ MOET ZEKER` bij, dan is dat het seintje dat het met zekerheid
gerepareerd moet worden — een klant is er boos over, dreigt te stoppen, of het
overkomt meerdere mensen.

**De lijn developer → klantenservice → klant.** Na een reparatie:

```
python3 scripts/mail_analyse.py opgelost <sleutel> "wat er nu anders is"
```

Twee dingen gebeuren dan. Iedereen die het meldde krijgt een concept met die
uitleg (via `_zet_concept_klaar`, dus langs het slot — nooit een tweede concept
voor wie er al een heeft liggen). En `stand_van_de_storingen()` legt vanaf dat
moment aan élk nieuw concept over dat onderwerp op wat er echt is vastgelegd:
bekend / met voorrang / gerepareerd-met-uitleg. Zonder die laatste stap schrijft
de klantenservice "ik kijk ernaar" terwijl het gisteren gerepareerd is, of
belooft hij iets wat niemand aan het bouwen is.

Vastgelegd in `tests/test_mail_klantenservice.py` (18 tests).

**Nagemeten:** 14 controles over 21 minuten na de reparatie van vanochtend, nul
dubbele concepten.

### 29-08-2026 — De developer wordt nu vanzelf aan het werk gezet

De lijn klantenservice → developer bestond, maar werd pas gelezen wanneer Daniel
toevallig een sessie opende. Een klant die woensdag boos meldt dat het niet
werkt, wachtte dus op de CEO. Nieuw: `scripts/dev_starter.py`, gestart door de
LaunchAgent `com.omnivaleur.devstarter` (plist in `config/`, wrapper in
`scripts/dev_starter.sh`, elke tien minuten).

Zet `mail_analyse` een storing op `moet_zeker`, dan begint de starter zelf een
Claude Code-sessie met de opdracht om die ene storing uit te zoeken, te
repareren, de tests te draaien, te pushen en daarna zelf
`mail_analyse.py opgelost <sleutel> "..."` te draaien. Door Daniel gekozen op
29-08-2026: **volledig autonoom**, inclusief pushen, want alleen dan is de klant
echt eerder geholpen.

De remmen staan in `tests/test_dev_starter.py`: één sessie tegelijk, nooit twee
voor dezelfde sleutel, een sleutel komt pas terug als hij is opgelost of
afgewezen, hooguit drie starts per dag, en niet beginnen in een werkmap waar het
werk van iemand anders klaarstaat. Nieuw commando daarvoor:
`mail_analyse.py afgewezen <sleutel> "reden"` — een besluit om iets níet te
repareren, zodat de sleutel niet eeuwig op de lijst blijft staan.

De sessie draait op Daniels abonnement: `ANTHROPIC_API_KEY` wordt bewust uit de
omgeving van het kindproces gehaald.

### 29-08-2026 — De klantenservice zoekt een feitelijke vraag eerst zelf op

Aanleiding: de mail van Jaap (info@zilverwebsite.nl) van 29-08 met twee vragen —
"moet de computer aan blijven staan bij het verversen?" en "er is deze maand
twee keer afgeschreven". Op allebei zei het concept dat Daniel het zou nakijken.
De eerste vraag is gewoon in de code na te zoeken.

Waarom het misging: `_grondslag()` kende geen van de woorden uit zijn vraag
(verversen, computer, browser, wachtrij), dus er ging nul regel code mee. En
zelfs mét een treffer leverde het "de eerste zestig regels van het bestand" op —
dat zijn de invoerregels. Drie plekken in de schrijfregels schreven daarnaast
letterlijk voor: "weet je het niet, schrijf dan dat Daniel het nakijkt."

Wat er nu anders is (`scripts/leadgen_mail.py`):
- `GRONDSLAG_BESTANDEN` kent de woorden waarmee klanten hun vraag stellen, niet
  alleen de woorden waarmee wij onze bestanden noemen.
- `_grondslag()` levert de kop van het bestand (waarom het bestaat) plus de
  stukken rond zijn eigen woorden, met `...` waar er iets tussenuit is. Op
  Jaaps vraag komt nu onder meer de regel mee dat de service worker sterft zodra
  Chrome dichtgaat — precies het antwoord.
- Lukt het antwoord niet met zekerheid, dan komt er **geen mail**. Het model
  geeft één regel terug (`GEEN ANTWOORD: <de vraag>`) en die vraag belandt via
  `mail_analyse.vraag_voor_daniel()` op de lijst die Daniel al leest. Een
  "ik kijk het na" in een verstuurde mail verdwijnt daarna nergens meer heen.
- Geld blijft bij Daniel. Jaaps tweede vraag is gecontroleerd: de escalatie
  `geld | info@zilverwebsite.nl | 29-08` staat op zijn lijst, dus die route
  werkte. Wel gerepareerd: het spoedbericht eiste `MAIL_HOST`, en dat is op
  Railway leeg (SMTP is daar dicht, alles gaat via Resend) — daar viel het
  seintje dus juist stil. Nu gaat het langs Resend, en kán het niet, dan zégt hij dat.

Vastgelegd in `tests/test_antwoord_uit_de_code.py`.

### 29-08-2026 — De twee storingen met voorrang, uitgezocht

**`marktplaats-niet-ingelogd-melding` — zelfde oorzaak, en al gerepareerd.**
Eerst gecontroleerd of het de bekende Admarkt-toestemming was, zoals gevraagd.
Nagemeten in het opdrachtenlogboek: het is de verouderde-kopie-oorzaak.
Dennis (info@retrogameking.com) draaide 1.0.217/1.0.218 en kreeg 14 mislukte
scans — óók op 2dehands en Vinted, die geen Admarkt hebben, dus Admarkt kan het
niet zijn. Bij hem was het na zestien minuten over ("denkt dat het nu lukt").
Egbert (info@papas-plectrums.nl) draaide 1.0.200/202/207 naast een nieuwere
kopie: geslaagde en mislukte scans op dezelfde dag, het patroon van twee kopieën
uit dezelfde wachtrij.

Wat er nog wél stuk was, en nu gerepareerd is: de server wist uit het
versiestempel dát de kopie te oud was, maar gooide die wetenschap weg zodra de
twee herkansingen op waren. Daarna kreeg de verkoper alsnog "je bent niet
ingelogd", en sinds 28-08 "zet Admarkt aan" — terwijl Admarkt bij Egbert gewoon
aanstond. Nu wint de versie: is de kopie aantoonbaar te oud, dan noemt de melding
die versie en de stap om de handmatig geladen kopie te verwijderen, voor elk
platform en elke soort opdracht. Zie `_rechtgezette_foutmelding` in
`backend/api/jobs.py` en de tests in `tests/test_extensieversie.py`.

**`import-wordt-steeds-trager` — terechte rem, aangezet door een echte storing.**
Egbert zag "eerst vijf tegelijk, nu één per keer". Dat is de ladder in
`bulkImportAllCandidates`: bij een 500/502 halveert de lading (10 → 5 → 2 → 1) om
een gateway-time-out te vermijden. De rem is terecht. De storing zat eronder:
elke aanroep las zijn hele voorraad opnieuw in, dus kleiner happen hielp niets —
precies wat hij merkte. Dat is op 27-08 gerepareerd (`_BULK_IMPORT_CACHE`, plus
alle databasewerk naar een werkdraad zodat het de server niet meer bevriest), en
de ladder klimt sindsdien ook weer terug omhoog na drie goede ladingen.
Nagemeten op zijn account op 29-08: **4.227 geïmporteerd, 23 gekoppeld, 1.284 nog
te gaan, 0 mislukt.** Geen wijziging nodig; via `opgelost` teruggemeld.

### 29-08-2026 (aanvulling) — De starter kan niet stil stilvallen

Bij het aanzetten liep hij meteen tegen de bekende macOS-val: launchd krijgt geen
toegang tot `~/Documents`. Gemeten, niet vermoed — `launchctl kickstart` gaf
`can't open input file`. Twee dingen daaruit:

1. **`[[ -r bestand ]]` is hier een nutteloze test.** macOS staat het opvragen
   van de bestandsgegevens gewoon toe en weigert pas het openen, dus die test
   slaagt terwijl de volgende regel alsnog stukloopt. De stub
   (`config/dev_starter_stub.sh`) leest daarom echt een byte, en zegt anders in
   gewone taal wat Daniel moet doen.
2. **Het dashboard merkt het nu zelf.** De starter schrijft bij elke ronde een
   hartslag weg (`dev_starter_hartslag`). Blijft die langer dan een uur uit
   terwijl er MOET ZEKER-werk klaarstaat, dan staat er een waarschuwing boven in
   Marketing → Klantenservice met de oplossing erbij. Zonder dat had hij dagen
   stil kunnen liggen zonder één signaal — precies wat de koude-mailmachine op
   11-08-2026 overkwam.

**Openstaand handwerk voor Daniel:** Volledige schijftoegang geven aan `/bin/zsh`
(Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang → +,
cmd+shift+G, `/bin/zsh`). Tot dat gebeurt start de LaunchAgent niets en meldt het
dashboard dat.

### 29-08-2026 — Tabblad Systeem is Werkplaats geworden

Door Daniel gevraagd: hij wil kunnen zien wat de mailagent en de developer met
elkaar doen zonder het te vragen. Het oude tabblad Systeem liet alleen losse
tellers zien. Nieuw: `GET /api/beheer/werkplaats`, met per storing dezelfde vorm
of hij nu wacht of klaar is — wie het meldde, waarom het voorrang kreeg, wat
eruit gekomen is en of de melders bericht hebben gehad. Bovenaan waar ik nu aan
werk, onderaan de machinetellers die er al stonden.

### 29-08-2026 — De eerste drie autonome sessies leverden niets op

Meteen goed om te weten hoe dit stukgaat. Alle drie stopten binnen enkele
seconden op **"You've hit your monthly spend limit"**. Ze telden als "afgerond",
vraten het dagmaximum van drie op, en de drie storingen stonden daarna als
opgepakt te verstoffen — terwijl er niets was gebeurd. De reden stond alleen in
een logboek dat niemand opent.

Wat er nu tegen beschermt (`scripts/dev_starter.py`):
- `_waarom_niets_geworden()` leest het logboek van een afgelopen sessie. Bekende
  zinnen (maandlimiet, gebruikslimiet, niet ingelogd) én "minder dan twaalf
  regels" gelden als: er is niets gebeurd. Let op: "not found" mag hier NIET in —
  dat staat ook in de hookmeldingen van een sessie die zijn werk gewoon deed.
- Zo'n sessie krijgt status `mislukt`. De sleutel komt daardoor gewoon weer in de
  wachtrij (hij is nooit aangeraakt) en telt niet mee voor het dagmaximum.
- Na een mislukking wacht de volgende ronde een uur (`HERSTELPAUZE_MINUTEN`) en
  probeert het dan gewoon opnieuw. NIET voorgoed stoppen: nagemeten op 29-08-2026
  was diezelfde limiet een uur later vanzelf weg, en een starter die daarna blijft
  liggen tot iemand hem aanschopt is precies wat hij moest voorkomen.
- De reden staat boven in Werkplaats, met wat Daniel eraan moet doen.
- Ook een sessie die al op "afgerond" stond wordt alsnog nagekeken, want de
  eerste ronde deed dat nog niet — anders bleven die drie eeuwig op slot.

Verder: launchd geeft een kaal PATH mee zonder node, waardoor de eigen hooks van
elke sessie omvielen met "node: command not found". `scripts/dev_starter.sh` zet
/opt/homebrew/bin en /usr/local/bin er nu bij.

**Les:** een test met een vaste starttijd in de toekomst-of-verleden faalt vanzelf
zodra de klok voorbij de drempel loopt. `tests/test_dev_starter.py` gebruikt nu
`datetime.now()`.

**Nagemeten, want de eerste conclusie was te snel.** "Verhoog je maandlimiet" was
niet het goede advies. Losse controle op 29-08 om 14:26, via exact dezelfde weg
als de starter (LaunchAgent → stub → repo → `claude -p`): dat werkt gewoon, met
afsluitcode 0. Er zit dus geen probleem in de omgeving van launchd — geen
sleutelhanger, geen HOME, geen PATH. De limiet van 12:20–13:10 was een tijdelijke
gebruikslimiet die vanzelf weer openging. Vandaar de herstelpauze hierboven in
plaats van definitief stoppen.

### 29-08-2026 — `marktplaats-import-foutmelding` was hetzelfde als `marktplaats-niet-ingelogd-melding`

Egbert (info@papas-plectrums.nl, `bcdf9aa4`) meldde op 28-08: steeds dezelfde
foutcode bij importeren, hoewel hij is ingelogd. Nagemeten in het
opdrachtenlogboek (tabel `jobs`) in plaats van aangenomen: zijn scans van
27-08 20:35 tot 28-08 10:38 kregen stuk voor stuk "You don't appear to be
signed in" en daarna "zet Admarkt aan" — exact de reeks die hierboven onder
`marktplaats-niet-ingelogd-melding` al is uitgezocht en om 12:06 vandaag
gerepareerd (`_rechtgezette_foutmelding` in `backend/api/jobs.py`, commit
`089d506`). Sinds zijn geslaagde scan op 28-08 14:25:37 is er geen nieuwe
mislukking meer bij hem geweest. Twee mailtjes, één storing, één fix — niets
aan de code gewijzigd, teruggemeld met `opgelost`.

### 29-08-2026 — `import-onvolledig-geen-nieuwe-items` was ook al bekend en gerepareerd

Egbert (info@papas-plectrums.nl, `bcdf9aa4`) meldde 26-08 t/m 27-08 09:34:
het systeem zei dat er niets meer op te halen viel, terwijl er advertenties
ontbraken. Nagemeten in het opdrachtenlogboek in plaats van aangenomen: zijn
scans van 25-08 tot 27-08 lieten precies het patroon zien dat hierboven (entry
27-08 "waarom zijn account vastliep") al is beschreven — elke ronde leverde
2.000 "nieuwe" advertenties, maar het bekende-aantal (`bekende_ids` dat de
server meestuurt) bleef vier scans lang op 2.250 steken, dus de volgende ronde
vond telkens dezelfde advertenties opnieuw en er kwam niets bij. Oorzaak: de
opslag liep stuk op de te-lange-URL-bug (vanaf ~640 item-id's) en de opdracht
stond toen al op "klaar" — precies "niets nieuws" terwijl er duizenden open
stonden. Die fix, plus de twee showstoppers erna (foute inlogstatus-melding,
dubbele extensiekopie), zijn diezelfde week al opgelost.

Nagemeten vandaag in de database: zijn account staat compleet, **5.534 van
5.534** Marktplaats-advertenties bekend (4.227 geïmporteerd, 23 gekoppeld,
1.284 nog te beoordelen, 0 ontbrekend). Niets aan de code gewijzigd — dit was
dezelfde storing als 27-08, alleen nog niet apart teruggemeld — en nu wel,
met `opgelost`.

### 29-08-2026 — Werkplaats als operationeel scherm, en het dagmaximum gerepareerd

**Het dagmaximum lekte.** Het maximum van drie sessies per dag werd afgeleid uit
`dev_sessies`, maar zodra een storing is opgelost verdwijnt hij daaruit — en dan
kwam zijn plek weer vrij. Juist een geslaagde sessie, de duurste, raakte je dus
kwijt uit de telling. Nu een eigen dagteller (`dev_starter_dagteller`); een
sessie die meteen afsloeg geeft zijn plek netjes terug.

**Het scherm.** Opgezet volgens wat voor een operationeel scherm geldt: eerst de
huidige toestand, groot en zichtbaar levend, dan expliciet eigenaarschap, dan de
gebeurtenissen — en niets meer dan dat, want elke extra teller kost aandacht.

- **Nu** — wie er aan het werk is, sinds wanneer, met een meelopende teller in de
  browser (anders staat "18 min" twintig seconden stil en lijkt het vast te zitten).
- **Wat er van jou wordt gevraagd** — alleen dat: escalaties, en wie nog geen
  bericht kon krijgen omdat er al post voor hem klaarligt. Wat de klantenservice
  en de developer onderling afhandelen staat hier niet.
- **Wat er precies gebeurd is** — een tijdlijn van de post tussen klantenservice
  en developer: gemeld → met voorrang doorgegeven → sessie gestart → teruggemeld
  → concept naar de klant. Afgeleid uit de bestaande administratie, geen nieuwe
  opslag. Gebeurtenissen van het laatste uur krijgen een groene stip.
- Verversen elke 20 seconden in plaats van elke twee minuten.
- De machinetellers zeggen er nu bij waaróm ze streepjes tonen (de server leest
  ze met de publieke sleutel niet), met de oplossing erbij.

Bewegende onderdelen respecteren `prefers-reduced-motion`.

### 2026-08-29 — `import-server-timeout` was al gerepareerd onder een andere sleutel

Egbert (info@papas-plectrums.nl) meldde op 25-08 tweemaal (11:29 en 13:20): de
server geeft time-outs, waardoor er maar een paar items tegelijk importeren.
Nagemeten in plaats van aangenomen: dit is dezelfde storing als
`import-wordt-steeds-trager`, vanochtend 10:05 al gerepareerd via de
importcache in `backend/api/imports.py` (`_BULK_IMPORT_CACHE`, rond regel
1452-1500) — de code daar noemt Egberts 25-08-melding zelfs letterlijk als
aanleiding. Oorzaak was dat elke aanroep van "Import all" éérst zijn hele
voorraad + advertenties opnieuw uit de database las, ongeacht hoe klein de
lading werd gezet; dat werd nu gecachet voor de duur van een import-sessie.
Er is nu ook een harde grens van 20 seconden per aanroep, zodat een verzoek
nooit meer op de gateway-tijdslimiet vastloopt.

Niets aan de code gewijzigd — de fix stond al op main en is al drie uur live.
Teruggemeld met `opgelost` onder de sleutel `import-server-timeout`, zodat
Egbert ook onder díe melding bericht krijgt.

### 29-08-2026 — Vier dingen op de werkplaats die niet waar waren

Bij het nalezen van het scherm met de echte gegevens. Alle vier hetzelfde soort
fout: het scherm bewéérde iets dat op dat moment niet klopte.

1. **"Aan het werk" boven een reparatie die al klaar was.** De starter zet een
   sessie pas bij zijn volgende ronde op afgerond — tien minuten later. Tot die
   tijd stond er "aan het werk sinds 15:02" boven een kaart die de terugmelding
   van 15:09 al toonde. Nu telt de storing zelf: is die teruggemeld, dan is er
   niemand meer mee bezig.
2. **Vier van de twaalf actiepunten waren al opgelost.** Escalaties bleven op
   Daniels lijst staan terwijl de bijbehorende storing gerepareerd was. Een lijst
   met vier dode punten leer je overslaan. Escalaties met een `bug_sleutel` die
   op opgelost of afgewezen staat, vallen er nu af.
3. **De lijst werd stil afgekapt op twaalf terwijl er vijftien punten waren.**
   Drie punten waren dus onzichtbaar. Nu compleet, gesorteerd op de volgorde die
   Daniel zelf koos (geld, vertrek, dan de rest), met de eerste acht open en de
   rest achter één regel.
4. **"Klant bericht: concept staat nog klaar"** terwijl er juist géén concept
   stond — het bericht was tegengehouden omdat er al post voor die persoon lag.
   Nu: "nog geen bericht; volgt zodra er geen andere post voor hem klaarligt",
   en bij een deel-bericht "1 van de 2 melders". De tegel zei om dezelfde reden
   "klant heeft bericht" voor vijf terugmeldingen waarvan er twee bericht hadden.

Ook: wachtende berichten worden per PERSOON gebundeld, niet per storing. Egbert
had er vier openstaan met dezelfde oorzaak; dat waren vier identieke regels.

### 2026-08-29 — `tabbladen-flitsen-op-voorgrond` was hetzelfde bekende verhaal, alleen bij een andere klant

Zilverwebsite (info@zilverwebsite.nl) meldde op 24-08: openende Marktplaats-
tabbladen flitsen over zijn scherm. Nagemeten in het opdrachtenlogboek in
plaats van aangenomen: zijn herplaats-jobs van die dag liepen op extensie
**1.0.218** — exact de verouderde kopie die hierboven al bij Jaap is
beschreven (`extension-version-floor`), en die het werkvenster nog niet
geminimaliseerd hield. Sinds de ondergrens van 1.0.244 (27-08-2026, jobs.py +
app.html) krijgt zo'n oude kopie vanaf 1.0.250 geen werk meer, en waarschuwt
het dashboard eronder. Zilverwebsite draait sindsdien op 1.0.251: zijn
delete+create-jobs van vandaag (29-08) liepen tientallen keren achter elkaar
foutloos af, zonder gemeld probleem. Niets aan de code gewijzigd — teruggemeld
met `opgelost`.

### 29-08-2026 — De terugkoppeling naar de klant ging per storing in plaats van per persoon

Gevonden bij het nameten van de mailagent, op verzoek van Daniel. Twee fouten in
`bericht_over_reparaties()`, allebei met dezelfde oorzaak: de lus liep over
storingen terwijl het slot per persoon werkt.

1. **Iemand met vier gerepareerde meldingen kreeg er één.** Er ligt nooit meer
   dan één concept tegelijk voor dezelfde persoon (`_waarom_geen_concept`). Egbert
   (info@papas-plectrums.nl) had er vandaag vier klaarstaan — import server
   timeout, marktplaats import foutmelding, import onvolledig, en de eerdere —
   en hoorde niets, terwijl hij juist de klant is die dreigde te stoppen. Nu gaat
   er één mail per persoon uit die alle reparaties behandelt.
2. **Elke ronde werden er vier mailteksten geschreven die meteen werden
   weggegooid.** Het slot werd pas ná `_herstelbericht()` geraadpleegd, dus elke
   tien minuten vier modelaanroepen voor niets. Het slot komt nu eerst.

Vastgelegd in `tests/test_mail_klantenservice.py`.

**Nagemeten dat de agent zelf gewoon draait:** het nieuwste beoordeelde bericht
was van 15:12, en `tabbladen-flitsen-op-voorgrond` kreeg om 15:19 netjes zijn
concept naar zilverwebsite.nl. De machine liep dus wel; de terugweg naar één
klant liep vast.

### 2026-08-29 — `advertenties-verwijderen-mislukt` was dezelfde 1.0.218-storing, nu bevestigd op verwijderen zelf

Met voorrang binnengekomen (klant dreigde te stoppen), gemeld door
zilverwebsite.nl op 22-08, laatst 24-08: "advertenties worden niet verwijderd
en daardoor ook geen nieuwe geplaatst." Nagemeten in het opdrachtenlogboek in
plaats van aangenomen: 22 t/m 24-08 gaven bij dit account **179 mislukte
verwijderopdrachten en 178 mislukte plaatsingen**, allemaal op extensie
**1.0.218** met dezelfde foutmelding ("cannot be found in your marktplaats
listings overview") — exact dezelfde verouderde-extensiekopie als
`tabbladen-flitsen-op-voorgrond` hierboven, ditmaal op de verwijderstap zelf in
plaats van het werkvenster.

Vandaag (29-08) draait dit account op 1.0.251: **47 van de 47**
verwijderopdrachten en 55 van de 58 plaatsingen liepen foutloos, geen
achterstallige opdrachten meer in de wachtrij. De drie resterende
plaatsingsfouten zijn bekende, andere gevallen (ontbrekend kenmerk,
onderbroken Chrome-sessie) en horen niet bij deze melding. Niets aan de code
gewijzigd — dit was al gerepareerd door de ondergrens van 1.0.244
(27-08-2026) en de `refresh_listing`-volgordefix (28-08-2026, zie
"Herplaatsen kon een advertentie kosten bij een verbindingshik" hierboven).
Teruggemeld met `opgelost`.

### 29-08-2026 — Vaste UTM-afspraak: waar komt het bezoek vandaan

Daniel wilde kunnen zien welk kanaal bezoek oplevert. Er stond nog geen enkele
getagde link; bezoek uit een bio in een telefoon-app komt bij Google Analytics
(G-VJ5BVD3GCH) binnen als "direct", dus dat was tot nu toe onmeetbaar.

**De afspraak — drie velden, verder niets:**

| veld | wat erin staat |
|---|---|
| `utm_source` | het kanaal, kleine letters: `tiktok`, `instagram`, `youtube`, `pinterest`, `threads`, `koude-mail` |
| `utm_medium` | alleen `social` of `email` — dit zijn de woorden die Analytics zelf in zijn kanaalgroepering herkent |
| `utm_campaign` | waar de link staat: `bio-en`, `bio-nl`, `marktplaats-nl` |

`utm_content` blijft vrij voor losse posts (linkbouwer onder aan het
analytics-dashboard). De tabel met vaste links staat als `KANAAL_LINKS` in
`backend/api/content.py` en wordt op datzelfde dashboard getoond met een
kopieerknop per kanaal.

Nederlands en Engels delen dezelfde bron (twee Instagram-accounts, twee
TikToks, twee YouTubes). Ze zijn uit elkaar te houden aan de campagne, niet aan
de bron — vandaar `bio-nl` naast `bio-en`. Een test bewaakt dat elk kanaal per
bron zijn eigen campagne houdt.

**Drie dingen die hierbij fout kunnen gaan, en waarom ze nu vastliggen in
`tests/test_utm_links.py`:**

1. **Hoofdletters.** Analytics is hoofdlettergevoelig: `TikTok` en `tiktok` zijn
   twee kanalen en dan klopt geen enkel totaal meer.
2. **Een zelfbedacht medium.** Op `/mp-video` stond `utm_medium=cold_email`.
   Dat woord kent Analytics niet, dus dat verkeer belandde in de bak "niet
   toegewezen".
3. **Getagde links binnen de eigen site.** De vier knoppen op `/mp-video` naar
   `/register` droegen zelf UTM's. Analytics bepaalt de herkomst bij binnenkomst;
   komt er halverwege een andere `utm_source` langs, dan start er een nieuwe
   sessie met een nieuwe bron — één bezoeker werd twee bezoeken en de echte
   herkomst was weg. Die tags zijn eraf; welke knop geklikt is, meten we al met
   het `cta_click`-event. Een test scant alle frontend-pagina's hierop.

**De maillink is kort met opzet.** `https://omnivaleur.com/mp` stuurt met een
307 door naar `/mp-video` mét de tags (`KORTE_LINKS` in `backend/main.py`).
Twee redenen: de koude mail wordt per lead door een taalmodel geschreven en dat
kan een lange URL met parameters verhaspelen, en een zichtbare parameterslinger
in een persoonlijke eerste mail leest als massapost — precies wat de opbouw in
`leadgen_mail.py` vermijdt (mail1 draagt daarom ook geen pixel). Bijkomend: de
campagnenaam is later te wijzigen zonder dat verstuurde links breken. Bewust 307
en geen 301, want een blijvende omleiding onthoudt de browser.

**Aanvulling dezelfde dag — wat je plakt is kort, wat Analytics meet is getagd.**
Daniel zag op zijn Instagram-profiel `omnivaleur.com/?utm_source=instagram&u…`
staan: Instagram, TikTok en Threads tonen de link letterlijk onder je naam, en
een afgekapte parameterslinger leest daar als reclame in plaats van als merk.
Elk kanaal heeft daarom nu een korte link op het eigen domein die met een 307
doorstuurt naar de getagde URL:

    /ig  /tt  /yt  /pin  /th        (Engels, bio-en)
    /ig-nl  /tt-nl  /yt-nl          (Nederlands, bio-nl)
    /mp                             (koude mail)

Ze worden in `backend/main.py` gegenereerd uit dezelfde tabel, dus een kanaal
erbij is één regel in `KANAAL_LINKS`. Een test loopt ze alle negen langs met een
echte aanroep en controleert dat er een 307 komt met precies de drie tags, dat
geen twee kanalen dezelfde code hebben, en dat een korte code geen bestaande
pagina overschaduwt (`/th` naast een `frontend/th.html` zou die pagina stil
onbereikbaar maken).

Openstaand voor Daniel: de acht bio-links moeten nog in de profielen geplakt
worden. Dat kan niemand namens hem doen zonder in te loggen; de Chrome-extensie
die dat zou toestaan was niet verbonden.

### 30-08-2026 — De extensie stond als "kanaal" in de marketingrapporten

Nagemeten in Verkeersacquisitie (23–29 aug): de rij `(not set)` telde 33 sessies
met **1.511 gebeurtenissen — 49,7% van alles in de property** — bij 0%
betrokkenheid en 45,8 gebeurtenissen per sessie. Dat zijn geen bezoekers.

Oorzaak: `extension/analytics.js` stuurt `job_started`, `job_error`,
`popup_opened` en `extension_installed/updated` via het Measurement Protocol
rechtstreeks naar GA4. Zulke meldingen komen niet van een pagina, dus er is geen
bron, geen medium en geen referrer — Google plaatst ze onder `(not set)`. Daarmee
stond er een kanaal in de lijst dat geen kanaal is, precies in het rapport waar
Daniel wil zien wat zijn kanalen opleveren, en het slokte de helft van de
gebeurtenissen op.

Elke melding draagt nu drie extra velden (extensie 1.0.266):

* `traffic_type: "internal"` — het haakje waar GA's ingebouwde filter voor intern
  verkeer op aangrijpt. Staat dat filter aan, dan komt dit de property niet meer in.
* `campaign_source: "omnivaleur-extensie"` en `campaign_medium: "app"` — het
  vangnet als dat filter uit blijft: dan staat er een leesbare naam in plaats van
  `(not set)`.

Kan dit het verkeer van een echte bezoeker vervuilen? Nee: de `client_id` van de
extensie is een eigen UUID per installatie (chrome.storage) en staat volledig los
van de cookie van de website.

Werkt pas zodra 1.0.266 in de Web Store staat en is uitgerold. Geen haast — mag
met de volgende release mee.

**Losse vondst in hetzelfde rapport: Instagram staat onder twee namen.**
`ig / social` had 19 sessies, `instagram / social` 8. Er loopt dus ergens nog een
link met `?utm_source=ig` — niet uit deze repo, want daar staat hij nergens; dat
is dus met de hand ergens geplaatst (post, oudere bio, of via Monaim). Precies de
splitsing waar `tests/test_utm_links.py` voor waarschuwt. Ook `email / cold_email`
(25 sessies) staat er nog: dat zijn de interne knoppen op /mp-video die op
29-08 zijn ontdaan van hun tags, die rij dooft vanzelf uit.

---

## 30-08-2026 — Merkkoppeling: waarom "omnivaleur" de socials gaf en niet de site

Daniel zag dat een zoektocht op "omnivaleur" zijn Instagram-accounts, de
YouTube-shorts en de Chrome Web Store bovenaan gaf, maar de site zelf nergens —
mét de vraag "bedoelde je: omnivore", en bij doorklikken zette Google de
zoekopdracht zelfs om naar dát woord.

**Nagemeten, niet gegokt** (Search Console, week 23 t/m 29 augustus):

- 275 vertoningen, 8 klikken over de hele site.
- De homepage: 5 klikken, 19 vertoningen, gemiddelde positie 3,5.
- Zoekterm "omnivaleur": 2 klikken, gemiddelde positie 1,8.
- In een privévenster staat de site wél bovenaan — maar pas ná "zoek in plaats
  daarvan naar omnivaleur".

De site is dus niet geblokkeerd en niet ongeïndexeerd. Het domein bestaat sinds
11-07-2026 (zeven weken) en Google kent "Omnivaleur" nog niet als merknaam, dus
corrigeert hij naar een woord dat hij wél kent. Instagram, YouTube en de Chrome
Web Store lenen intussen het vertrouwen van hun eigen domein.

Twee bijvangsten die het beeld verklaren:

- Bing en DuckDuckGo hebben de hele site wél compleet staan. Dat komt door de
  IndexNow-melding bij elke publicatie (`backend/services/indexnow.py`); Google
  doet niet mee aan IndexNow en moet alles zelf komen ophalen.
- De homepage noemde de eigen profielen nergens — niet in een link en niet in de
  merkgegevens. Er was letterlijk geen enkele uitspraak dat die accounts bij dit
  domein horen.

**Wat er is toegevoegd.** De organisatie op de homepage draagt nu `sameAs` met
alle acht profielen plus de Web Store-vermelding, en er staan echte links met
`rel="me"` onder aan de pagina. Dezelfde uitspraak staat via `_footer.html` op
alle blogpagina's, en de uitgever van elk artikel deelt nu hetzelfde
`@id` (`/#organization`) — één entiteit in plaats van honderd naamloze
bedrijfjes die toevallig ook Omnivaleur heten. De profiellijst is afgeleid van
`KANAAL_LINKS`, dezelfde tabel als de bio-links, zodat een kanaal erbij vanzelf
meeloopt. `tests/test_merkkoppeling.py` bewaakt dat de statische homepage niet
uit de pas gaat lopen met die tabel.

Dit is een versneller, geen schakelaar: merkherkenning bij Google komt van
herhaling en leeftijd. Verwachting is weken, niet dagen.

### 30-08-2026 — Marketing-dashboard uitgedund en gedrag toegevoegd

Daniel las het dashboard voor het eerst helemaal door en vroeg om minder, met
alleen wat telt, plus zicht op wat bezoekers op de site doen. Negen secties zijn
zes geworden.

**Weg of samengevoegd:** "Blog-prestaties per categorie", "Best presterende
blogposts" en "Stijgende zoektermen" waren drie tabellen over hetzelfde. Nu één
sectie "Zoekverkeer" met de clicks in de kop en twee smalle tabellen naast
elkaar. De categorietabel verschijnt alleen nog bij minstens drie categorieën én
twintig clicks samen — bij drie categorieën en acht clicks is het ruis die de
rest verdringt. De postniveau-tabel zit onder een uitklapper in de social-sectie
in plaats van als eigen kop.

**Nieuw: "Wat ze op de site doen".** Links waar iemand binnenkomt (met
betrokkenheidspercentage per pagina — een landingspagina die veel trekt en waar
iedereen meteen weg is, is geen succes maar een lek), rechts wat er daarna
bekeken wordt. Daarvoor is `ga4.top_pages()` bijgekomen (pagePath +
screenPageViews) en draagt `top_landing_pages` nu `engagementRate`.

**Tegels bovenaan** zijn nu bezoekers / aanmeldingen / van bezoek naar account /
blijven ze hangen. "Impressies" is eruit (staat in de zoekkop) en "GA4-verkeer
· 0 conversies" is vervangen door het aanmeldpercentage, wat het cijfer is waar
een beslissing aan hangt. `totals` levert daarvoor nu ook
`averageSessionDuration`.

De kolom "Conversies" heet overal "Aanmeldingen". Die stond op nul omdat
`sign_up` pas op 30-08 als belangrijke gebeurtenis is aangezet; vanaf nu vult
hij zich.

**`tests/test_analytics_dashboard_render.py`** is nieuw en rendert het sjabloon
met een vol én een volledig leeg rapport. Dat tweede geval is het gevaarlijkste:
zo ziet het eruit zodra een koppeling wegvalt, en juist dan moet de pagina blijven
staan in plaats van een foutmelding te tonen.

**Drie dingen die in het rapport van 23–29 aug niet klopten en geen bug zijn:**

1. `Unassigned` (33 sessies) is de extensie — zie de notitie hierboven; dooft uit
   zodra 1.0.266 is uitgerold.
2. `Email / cold_email` met campagne `marktplaats_video` (25 sessies) zijn de
   interne knoppen op /mp-video die op 29-08 van hun tags zijn ontdaan.
3. `Organic Shopping` (46 sessies, maar 2 nieuwe gebruikers) is geen marketing:
   dat zijn bestaande klanten die vanaf Shopify en de marktplaatsen terugkomen.
   Stripe is inmiddels als ongewenste verwijzing uitgesloten; hetzelfde zou voor
   shopify.com en de marktplaatsdomeinen kunnen, maar dat is Daniels keuze.

Ook gevonden: de losse link met `?utm_source=ig` draagt campagne `link_in_bio`
(18 sessies). Handmatig geplaatst, staat nergens in de repo.

### 30-08-2026 — Overdracht: sessie op het tweede account stopt hier

Wie hierna op Daniels eigen account verdergaat, begint met dit.

**Wat er vandaag is gerepareerd en live staat** (commits `c434e60` t/m de laatste
push van vandaag, extensie **1.0.265**, door Daniel geüpload naar de Web Store):

- Verkocht is verkocht. Een publicatieopdracht wordt getoetst op het moment van
  UITDELEN (`backend/api/jobs.py`, `/pending`) — het enige punt waar elke
  publicatie langskomt. Staat er ergens een verkoop, dan wordt de opdracht
  geannuleerd. Kan de controle niet worden gedaan, dan gaat er die ronde geen
  enkele publicatie uit.
- Tweelingen. Dezelfde trui staat meerdere keren in de voorraad (vertaalde
  importrijen). `backend/services/tweelingen.py` bepaalt de familie op het nummer
  in de TITEL (niet op het SKU-veld: dat is per importbron verschillend) plus
  hetzelfde merk. Verkocht op één rij geldt nu voor de hele familie.
  Gemeten bij Daniel: 440 items, 13 producten met dubbele rijen, tot acht rijen
  voor dezelfde trui.
- Op het platform van de verkoop halen we bewust NIETS weg: een tweede
  advertentie daar kan een tweede exemplaar zijn.
- Verkoopdetectie: eBay en Etsy worden nu server-side via hun eigen API
  nagekeken (`POLL_PLATFORMS` in `backend/services/polling.py`). Vinted hangt op
  de uurlijkse garderobescan, MP/2dehands op de tienminutencontrole in de
  extensie — beide vereisen dus een draaiende browser.
- Ontbrekende advertentieteksten worden elk kwartier vanzelf opgehaald
  (`vul_ontbrekende_teksten_aan`, één verkoper per ronde).
- Elk klaargezet conceptantwoord stuurt nu een mailtje naar Daniel. Dat werkte
  eerder niet: berichten aan hemzelf gaan naar twee adressen en die gingen als
  één tekstveld naar Resend, wat een 422 gaf.
- Dubbele Stripe-abonnementen zijn geblokkeerd (zilverwebsite.nl had er twee).

**Wat er nog openstaat**

1. Er lopen verwijderopdrachten op Daniels account: 12 producten waren verkocht
   en stonden nog live elders. Vanochtend 09:42 stonden er 16 op klaar, 14 in de
   rij, 3 mislukt (die advertenties bestonden al niet meer op Marktplaats).
   Nakijken of de rest is afgerond — ze lopen alleen met zijn browser open.
2. Het werkvenster van de extensie klapte op macOS steeds open. Het wordt nu op
   drie momenten expliciet geminimaliseerd (aanmaken, tabblad openen, tabblad
   sluiten). Nog niet bevestigd door Daniel. Blijft het gebeuren, dan is de
   volgende stap het venster helemaal laten vallen en in een verborgen tabblad
   werken — met als bekende prijs dat Chrome korte pauzes daar tot een seconde
   oprekt.
3. Toon & Lynn (De Juiste Toon) wachten op antwoord over de nieuwe categorie
   Verkleedkleding en over "kleed" = vloerkleed. Storing staat teruggemeld als
   `categorie-verkeerd-vanuit-vinted`.

### 30-08-2026 — Een extensie-update zette bij iedereen stilletjes de motor af

Egbert (Papa's Plectrums) vroeg om te bellen: "ik krijg het gewoon niet rond, en
ik zag een nieuwe banner die meer vragen oplevert dan antwoorden." Wat we hier
zien in zijn account:

- Zijn extensie heeft zich sinds **vrijdag 28-08 om 20:13** niet meer gemeld.
  Geen scan, geen publicatie, geen verkoopcontrole — twee dagen niets.
- Hij is zakelijk verkoper (Admarkt). 4.249 items, 5.534 advertenties gevonden,
  1.284 daarvan staan nog als `pending` te wachten om binnengehaald te worden.
- **Nul advertenties gecrosslist.** Na 17 dagen betalen staat er nog niets op
  2dehands, Vinted, eBay of Shopify. Zijn hele ervaring is import geweest.

**De oorzaak van de stilte.** Versie 1.0.256 zette vier nieuwe VASTE
host-toestemmingen in het manifest, waaronder `https://*.marktplaats.nl/*` naast
de al verleende `https://www.marktplaats.nl/*`. Chrome ziet zo'n uitbreiding als
"deze extensie wil meer dan waar je ja op zei" en zet haar bij ELKE bestaande
gebruiker uit tot hij opnieuw goedkeurt. Zonder foutmelding, zonder mail. De Web
Store staat op 1.0.262, dus dat is bij alle klanten langsgekomen. Jaaps 105
wachtende opdrachten met een 13 uur stille extensie (29-08) zijn hetzelfde
verhaal.

Pijnlijk detail: het commentaar in `background.js` waarschuwde hier al letterlijk
voor als reden om Admarkt optioneel te houden. Een commentaar in een ander
bestand houdt niemand tegen; `tests/test_extensie_permissies.py` nu wel. De regel
is: `host_permissions` mag krimpen, nooit groeien. Nieuw domein →
`optional_host_permissions`. Moet het echt vast, dan is dat een besluit mét
gevolgen (iedereen ligt stil tot hij klikt) en waarschuwen we klanten vóór de
release.

**Het dashboard zei het niet.** Het blokje "extensie meldt zich niet" was op de
computer verborgen, en sinds 29-08 zichtbaar zodra er werk in de wachtrij stond.
Egbert had niets in de wachtrij — hij kwam er immers niet eens aan toe — dus zag
hij niets. Het staat er nu ook zonder wachtrij, na een uur stilte, met de
Chrome-oorzaak en de drie stappen erbij.

**De mailkoppeling had een blinde vlek.** Er lag wel een concept voor Egbert,
maar dat was de losse reparatiemelding over de trage import van 29-08 — geen
antwoord op zijn bericht van 28-08 12:46 waarin hij om een gesprek vroeg. Het
slot "er ligt al een concept voor deze persoon" keek alleen óf er iets lag, niet
waar het over ging, en blokkeerde daarmee elk echt antwoord. Nu geldt: een
concept mét In-Reply-To beantwoordt een bericht en blokkeert; een concept zonder
(reparatiemelding, opvolging) staat een antwoord niet in de weg, en het seintje
meldt dat er twee liggen.

Daarbovenop: kon de klantenservice het antwoord niet in de code vinden, dan
schreef ze niets — bewust, want een gegokt antwoord kost een lead. Voor een
BETALENDE klant is stilte erger. Die krijgt nu een tweede ronde met één harde
regel: geen enkele technische bewering, wel erkennen, de openstaande vraag
benoemen en die bij Daniel leggen. Egberts vraag om te bellen viel precies in dat
gat.

**Voor Daniel:** er ligt een concept klaar dat hem door de drie stappen loodst en
een gesprek aanbiedt; de Google Meet-link moet daar zelf in.

### 30-08-2026 — De omzet van weken stond op één dag

Daniel zag in Analytics twaalf verkopen op 30 augustus staan, met artikelen die
in mei en juni waren geplaatst. In de database staan ze inderdaad alle twaalf
gestempeld tussen 07:36:54 en 07:37:06 — één en dezelfde ronde.

**De oorzaak.** Een verkoop kreeg tot nu toe de datum waarop wij hem ONTDEKTEN,
niet de datum waarop hij plaatsvond. Bij Vinted ontdekken we verkopen door elke
tien minuten de eigen bestellingenpagina van de verkoper te lezen. Die pagina is
een geschiedenis: er staan ook bestellingen van weken terug op. Zolang elke ronde
draait valt dat niet op. Slaat er een periode over — de extensie lag stil (zie de
Chrome-storing hierboven), de verkoper is net begonnen, of een verbetering
herkent ineens oude bestellingen die eerder niet te koppelen waren — dan worden
ze in één klap geboekt met de klok van dat moment.

Dit raakte niet alleen Vinted. Ook de Shopify-inhaalronde (die bewust 24 uur
terugkijkt) en de eBay-melding gooiden de datum weg die ze wél meekregen.

**Wat er nu geldt.**

1. De extensie stuurt de datum mee die het platform zelf bij de bestelling toont
   (het machineleesbare `datetime`-veld eerst, de zichtbare tekst als vangnet).
   Shopify geeft `processed_at`, eBay het verkooptijdstip uit de melding.
2. Een datum die niet met zekerheid te lezen is, wordt niet gegokt — dezelfde
   regel als in `mp_datums.py`. Dan blijft staan wat er staat.
3. **Een verkoopdatum mag alleen naar voren in de tijd worden bijgesteld, nooit
   naar achteren.** Ontdekken kan nooit eerder dan verkopen, dus een lagere datum
   is per definitie de betere. Daardoor repareren de bestaande foute stempels
   zichzelf zodra een ronde de echte datum leest, en kan geen enkele herdetectie
   een oude verkoop opnieuw naar vandaag schuiven.
4. Boekt een ronde vier of meer verkopen tegelijk zonder één leesbare datum, dan
   staat er een waarschuwing in de serverlog: dan is de opmaak van de
   bestellingenpagina veranderd en moet de scraper bij.
5. De datum in Analytics is aanklikbaar en corrigeerbaar (`/listings/sold-date`),
   zodat een verkeerde datum nooit meer vastligt.

Extensie 1.0.267. De ondergrens is bewust niet opgehoogd: een oudere kopie stuurt
geen datum mee en valt terug op het oude gedrag, wat niet erger is dan nu.

### 30-08-2026 — Egberts 1.284 advertenties zijn binnengehaald (met toestemming)

Daniel gaf toestemming om de import voor Egbert Brouwer (Papa's Plectrums) zelf
uit te voeren, zodat het van tafel was vóór hun telefoongesprek. Gedaan: **1.284
advertenties aangemaakt, 0 mislukt, 0 geparkeerd, 0 over** — in 26 porties van 50,
850 seconden.

**Belangrijkste les: importeren heeft zijn browser niet nodig.** De kandidaten
stonden al in `import_candidates`; `/imports/bulk-import` draait volledig op de
server. Egberts extensie ligt sinds 28-08 20:13 stil door de Chrome-storing
hierboven, en dat blokkeerde dit dus níet. Wie in dezelfde situatie zit kan op
dezelfde manier geholpen worden zonder dat de klant iets hoeft te doen.

**Prijs en tekst komen niet uit Admarkt.** Admarkt levert alleen titel en foto's.
De prijs en de omschrijving zijn er daarna bijgehaald uit het openbare aanbod van
dezelfde verkoper (verkopers-id 6999351, 4.754 advertenties met een unieke
titel): 1.285 van de 1.296 items teruggevonden, **1.284 prijzen en 1.174
omschrijvingen** ingevuld.

**Er zit een verhongeringsfout in de vaste kwartierronde.** `_mist_iets()` in
`backend/services/mp_enrich.py` markeert een item ook als het geen merk, geen maat
of hooguit één foto heeft. Bij Egbert heeft géén enkel item een merk, dus die
lijst loopt nooit leeg, en de ronde pakt telkens de eerste 150 op uuid — steeds
dezelfde. Zijn nieuwe items zouden daar nooit aan de beurt zijn gekomen. Daarom is
dit met een eenmalige gerichte ronde gedaan (alleen items zónder prijs of zónder
tekst) en niet met de knop. **Die fout staat nog open in de productcode.**

**Stand nu:** 5.533 items voor Egbert. Zonder prijs 12, zonder tekst 121, zonder
foto 1, zonder categorie 119 — waarvan 33 uit de partij van vandaag. Dat laatste
zijn pins, mokken en sleutelhangers ("officiële merchandise"), die passen niet in
de taxonomie. 2% van het geheel; die kunnen niet naar Marktplaats tot er een
categorie bij komt.

**Voor het gesprek:** hij heeft **nul** gekoppelde kanalen (geen eBay, Etsy of
Shopify) en zijn abonnement staat op `pro`, status `trialing`, proef loopt tot
19-09-2026.

De zeven storingsmeldingen die hierover binnenkwamen (`items-pagina-leeg`,
`admarkt-import-fout`, `admarkt-import-mislukt`, `admarkt-import-foutmelding`,
`import-admarkt-foutmelding`, `import-timeout-marktplaats`,
`foutmelding-schermafbeelding`) staan bij de klantenservice op opgelost.
`import-teller-klopt-niet` bewust niet: dat gaat over een teller en een
berichten-badge en is hier niet mee gerepareerd.

**Valkuil bij het bijwerken van een concept (zelfde dag, meteen hersteld).** Het
concept voor Egbert is vervangen door: nieuwe versie toevoegen, oude weghalen.
Zoho behield daarbij het bestaande bericht met hetzelfde `Message-Id` niet als
nummer 6, maar hernummerde de map — waardoor het weghalen op volgnummer het
*volgende* concept trof (dat voor d.r.seubring). Dat concept is teruggezet uit de
`leerlog` in `leadgen_opslag`, waar `_onthoud_concept()` de volledige tekst mét
citaat bewaart; de draadkoppen kwamen uit het oorspronkelijke bericht in INBOX.
Beide concepten staan er weer goed in.

Regel voor de volgende keer: **verwijder een concept op UID, nooit op
volgnummer**, en controleer vóór het verwijderen de ontvanger van precies dat
bericht. Een expunge in `Concept` gaat níet naar Afval.

### 30-08-2026 — "Is dit verkocht?" voor Marktplaats en 2dehands

Daniel zag alleen Vinted-verkopen. Gemeten in zijn account: 26 verkopen, alle 26
op Vinted, terwijl er 110 Marktplaats- en 54 2dehands-advertenties actief staan.
Over alle klanten samen was `sold_unconfirmed` nog nooit één keer gezet.

**Waarom Marktplaats niet meedeed.** Marktplaats weet zelf meestal niet dat er
verkocht is: bij een verkoop met de hand komt er nooit een "verkocht" op de
advertentie — de verkoper haalt hem weg. Het enige wat wij zien is dat de
advertentie verdwenen is, en dat betekent daar óók "verlopen na 30 dagen".
Automatisch boeken op afwezigheid is uitgesloten: dat haalt een nog levend
artikel van Vinted, eBay en de webshop af. De bestaande tussenweg keek alleen
naar advertenties die er nog stónden mét een label en sloeg dus nooit aan.

**Wat er nu gebeurt.** De verkoopcontrole (elke 10 min) kijkt per advertentie die
niet in het overzicht staat op de advertentiepagina zelf, en geeft één van vier
oordelen: `verkocht` (label op de pagina), `weg` (404, of doorgestuurd naar iets
anders), `leeft`, `onbekend` (401/403/5xx/geen verbinding). Alleen `verkocht` en
`weg` leiden ergens toe, en dan nog:

- `verkocht` is bewijs → meteen als vraag doorgegeven.
- `weg` moet twee aparte rondes standhouden, minstens een half uur uit elkaar.
  Zien we hem terug, dan vervalt de verdenking meteen.
- Gaf het overzicht **nul** advertenties terug, dan wordt er die ronde niets als
  verdwenen geteld. Anders lijkt bij een uitgelogde sessie álles verdwenen.
- Vijf pagina's achter elkaar `onbekend` breekt de ronde af (uitgelogd of
  geblokkeerd), en er zit 250 ms tussen elke aanvraag.
- Elke ronde wordt een ander stuk van de lijst nagekeken; voorheen werden bij een
  groot account eeuwig dezelfde veertig bekeken.

In het dashboard staat boven de itemlijst een balk met de vraag en twee knoppen.
*Yes, sold* vraagt de prijs (mag leeg) en doet daarna de normale verkoopafhandeling.
*No* zet de advertentie in het archief — niet terug op live, anders komt dezelfde
vraag elke ronde terug. De reden staat erbij, inclusief hoe lang de advertentie
online stond, want boven de 28 dagen is "verlopen" de waarschijnlijker verklaring.

De reden wordt in `error_message` bewaard (geen migratie nodig). Die tekst mag de
woorden "relist", "delist" of "still live" niet bevatten: het herplaats-overzicht
herkent daaraan een mislukte herplaatsing. Een test bewaakt dat, en het scherm
heeft er bovendien een statusslot op.

Extensie 1.0.268. Ondergrens bewust niet opgehoogd.

## 30-08-2026 — Eén trui, zeven keer in de voorraad

Daniel meldde dat het dashboard bij een reeks items "staat niet op Vinted" zei
terwijl hij zeker wist dat ze er wél op stonden — en hetzelfde voor Shopify.

**Wat er echt aan de hand was.** Niets aan de Vinted- of Shopify-herkenning. De
import maakte van dezelfde trui meerdere items. Gemeten op zijn eigen voorraad:
440 items, waarvan 46 in werkelijkheid 13 artikelen waren. Bij één vest zeven
rijen. Elke rij kende alleen zijn eigen advertentie, dus alle andere kanalen
stonden daar op "niet geplaatst". Eén druk op Publish had er een tweede echte
advertentie van gemaakt.

Hoe de rijen ontstonden, in volgorde:
1. De koppeling op titel eist een EXACTE en UNIEKE titel. De Marktplaats-
   advertentie is Nederlands, de Vinted-advertentie Engels — geen match.
2. Zodra er twee rijen met dezelfde titel bestaan, is de titel niet meer uniek en
   koppelt er nóóit meer iets. Elke volgende importronde legde er een rij bij.
3. De tweelingdetectie met het taalmodel kon niet helpen: `_twin_pool` sluit
   items uit die al op het kanaal van de kandidaat staan, en dat was precies het
   geval.

**`familie_ids` heeft nooit gewerkt.** De tweelingafhandeling van 30-08 zocht met
`or_("sku.eq.1032,title.ilike.(1032)%")`. PostgREST leest die haakjes als zijn
eigen groepering en geeft dan géén fout maar een lege lijst terug. Gemeten: 1 van
de 8 rijen gevonden. Met aanhalingstekens om het patroon — `title.ilike."(1032)%"`
— worden het er 8. Daardoor werkt nu pas wat er stond: bij een verkoop gaan ook de
advertenties van de zusterrijen weg. Een test bewaakt die aanhalingstekens.

**Wat er nu gebeurt.**
- `backend/services/tweelingen.py` is de enige plek voor "is dit hetzelfde
  artikel". Het advertentienummer voor de titel — "(1032)" — is de sleutel, want
  dat overleeft de vertaling. Erbovenop de harde controle op kleur, maat, merk en
  prijs, zodat een hergebruikt nummer geen twee verschillende artikelen plakt.
  Het nummer moet minstens drie tekens en twee cijfers hebben: anders werd "(XL)"
  een familienummer en kregen alle XL-artikelen bij één verkoop een
  verwijderopdracht.
- De import koppelt op dat nummer (`same_code`) vóór de titelmatch. Staat er al
  een andere advertentie op dat kanaal, dan komt er een EXTRA advertentieregel
  onder hetzelfde item — geen nieuw item meer. De rem op de titelmatch blijft
  staan: tien identieke blikjes plectrums zijn tien voorwerpen.
- Publiceren slaat een kanaal over waar een zusterrij al live staat, met reden.
  Dat is de directe rem op dubbele advertenties.
- Het dashboard telt de advertenties van zusterrijen mee: paarse stip ⧉, niet
  klikbaar, met de tekst dat samenvoegen de bedoeling is en niet publiceren.
- Nieuw: `GET /api/items/duplicates` en `POST /api/items/merge`. De balk boven de
  itemlijst voegt per groep of in één keer samen. De server weigert een
  samenvoeging die kleur, maat, merk of prijs tegenspreekt.

Samenvoegen is onomkeerbaar en gebeurt daarom nooit vanzelf. Foto's blijven staan
— opruimen zou een foto kunnen weghalen die het overgebleven item zelf gebruikt.

De dubbelenlijst wordt hoogstens eens per tien minuten opgehaald (en meteen na
een import): het is een volledige voorraaduitlezing, en bij een account met 5.500
items is dat niet iets voor elke verversing.

Geen extensiewijziging, dus geen versieophoging.

## 30-08-2026 — Waarom Amanda's serverfout nergens aankwam

Daniel vroeg waarom de melding van Amanda ("Publishing failed (HTTP 500):
Internal Server Error", met een foto erbij) niet door de mailagent én niet door
de developer was opgepakt. Drie oorzaken, alle drie gerepareerd.

**1. Een 500 liet geen enkel spoor na.** Een onverwachte fout in de server ging
als kale tekst terug naar de browser en verder alleen naar de logregels van de
Railway-container — bij de volgende deploy weg. Er was dus geen plek waar iemand
kon zien wélke fout het was, bij welk artikel, of hoe vaak hij voorkwam. Haar
foto was het enige bewijs dat het ooit gebeurd is. Nu krijgt elke onverwachte
fout een korte code (`backend/main.py`, `onverwachte_fout`). Die staat op het
scherm van de klant, gaat mee in zijn mail of screenshot, en is terug te vinden
met `python3 scripts/mail_analyse.py fouten` — inclusief het spoor. Bewaard in
`leadgen_opslag` onder `server_fouten`, de laatste 60, dus geen migratie.

**2. De mailagent kon de foto niet zien.** In Amanda's mail stond alleen "ik
stuur een foto mee van de melding". De agent las uitsluitend platte tekst, dus
de storing zelf kwam nergens aan. Egbert deed twee keer hetzelfde met een
importfout. Schermafbeeldingen gaan nu mee naar het model (max 2 per bericht,
verkleind naar 1400 px), en er is een veld `foutmelding` waarin de letterlijke
tekst van zo'n melding wordt vastgelegd en in `bugs` wordt getoond.

**3. Elke mail kreeg een nieuwe bugsleutel.** Op de lijst stonden 45 sleutels
waarvan 44 met precies één melder — met vier verschillende namen voor dezelfde
Admarkt-importfout. Het model kreeg de bestaande sleutels nooit te zien en kon
ze dus niet hergebruiken. Daardoor haalde vrijwel niets de grens van twee
melders, kreeg vrijwel niets MOET ZEKER, en startte `dev_starter.py` voor
vrijwel niets een sessie. De bestaande sleutels gaan nu mee in de opdracht, en
daaronder ligt een vangnet dat een nieuwe naam met genoeg woordoverlap
(≥ 0,6) op de bestaande sleutel laat vallen. Een sleutel op *afgewezen* blijft
buiten schot: daar is een besluit over genomen.

**Toon is geen maat voor ernst.** Amanda bleef vriendelijk, dus haar melding
gold als gewone support terwijl publiceren voor haar stuk was. Een serverfout
(5xx of "internal server error" in de foutmelding) zet nu uit zichzelf MOET
ZEKER — dat is bewijs, geen inschatting.

**En de publicatie zelf.** De API-kant van publiceren (eBay, Shopify) liep op
`asyncio.gather(..., return_exceptions=False)`: één struikelend kanaal trok de
hele publicatie om, ook de kanalen die al in de wachtrij stonden, en de
gebruiker zag alleen "HTTP 500". De extensiekant had die afscherming al. Nu is
elk kanaal apart afgeschermd, en het eerste stuk van `_publish_one` (waar
`insert.data[0]` een IndexError kon worden) ook.

Nog niet vastgesteld: wélke fout Amanda precies raakte. Dat is precies wat er
niet meer kan gebeuren — de volgende keer staat er een code onder.

## 30-08-2026 — De foutcodes wezen binnen een kwartier de oorzaak aan

Daniel vroeg of de reparatie ook echt te testen was in plaats van te beloven.
Dat leverde twee dingen op die anders onopgemerkt waren gebleven.

**Proef 1: kan de server een fout überhaupt wegschrijven?** Met de PUBLIEKE
Supabase-sleutel niet: `new row violates row-level security policy for table
"leadgen_opslag"` (401). De live server draait op `service_role` (te zien op
/health), dus daar werkt het wél — maar had Railway op de publieke sleutel
gestaan, dan was de hele foutcode een dode letter geweest, stil opgevangen door
de `except` eromheen. Zoiets is hier al vaker gebeurd; nu is het nagemeten.

**Proef 2: een echte publicatie die omvalt.** Via een echt HTTP-verzoek op
`/api/items/{id}/crosslist`, met de echte database en een fout in het
publiceerpad. De klant kreeg "Something went wrong on our side (code 685B5C)",
en die code was terug te vinden met `mail_analyse.py fouten`, met pad, soort
fout en het volledige spoor. De hele keten werkt.

**En toen stonden er twee ECHTE fouten in de lijst**, allebei van die ochtend,
allebei op `GET /api/jobs/relist-status`:

    httpx.RemoteProtocolError: <ConnectionTerminated error_code:1>

Dat is Supabase dat een hergebruikte verbinding sluit. `execute_with_retry` ving
zoiets al op — maar verreweg de meeste plekken in de code roepen gewoon
`.execute()` aan, zo'n tweehonderd stuks, en die vlogen er ongevangen uit. Dat is
naar alle waarschijnlijkheid ook wat Amanda raakte: de allereerste regel van het
publiceerpad (`items.py`, het item ophalen) is zo'n kale leesactie.

**Wat er nu gebeurt.** In `backend/database.py` hangt de herhaling op de bouwer
die Supabase teruggeeft bij een SELECT. Elke leesactie in het hele project
overleeft daarmee een weggevallen verbinding, zonder tweehonderd plekken aan te
raken. Schrijfacties (insert, update, upsert, delete) geven een ándere bouwer
terug en blijven bewust onaangeraakt: een insert blind herhalen na een
weggevallen antwoord maakt een tweede rij, en dus een tweede advertentie.
`execute_with_retry` gebruikt intern de onbewerkte versie, zodat er drie
pogingen zijn en geen negen.

## 30-08-2026 — "Foutmelding, maar wel gemeld als gelukt" (Pleun Aertssen)

Daniel meldde dat het verversen bij dat account misging: een foutmelding op het
scherm, maar in het dashboard stond de advertentie als ververst. Nagezocht in de
opdrachten van dat account. Drie Vinted-verversingen, alle drie mislukt bij de
eerste stap — de extensie kreeg de advertentie niet uit de garderobe
("still in your wardrobe after confirming delete"). Daaronder lagen twee fouten.

**1. De herkansing botste op zijn eigen mislukte poging.** Een verversing hoogt
de teller op, zet de afkoelperiode van veertien dagen en snoept een dagquotum op
zodra hij in de wachtrij staat — dus vóórdat er iets gebeurd is. Mislukt hij, dan
geeft `fail_job` dat allemaal terug. Maar `relist-retry` deed dat niet: die
annuleerde de oude opdrachten, wiste de foutmelding, en liep daarna tegen
`This listing was refreshed 0d ago. Wait 14d more.` — de afkoelperiode die zijn
eigen mislukte poging net had gezet. Wat overbleef: geen opdrachten, geen
foutmelding, teller op 1. Dat is precies "gemeld als gelukt". Nu wordt eerst
teruggedraaid en pas daarna geannuleerd, en de foutmelding blijft staan tot de
nieuwe poging écht in de wachtrij staat.

**2. Een herplaatsing kon eeuwig blijven wachten.** Bij het uitdelen van werk
werd een herplaatsing alleen afgeblazen als de bijbehorende verwijdering op
`error` stond. Stond die op `cancelled` — wat gebeurt zodra iemand opnieuw
probeert of annuleert — dan viel hij in de tak "verwijdering nog niet klaar,
wachten". Die verwijdering gaat nooit meer lopen, dus bleef de herplaatsing
eeuwig `pending` en bleef het scherm melden "nieuwe advertentie over ~X min".
Bij Pleun stond zo'n herplaatsing van 12:35 uur te wachten op een verwijdering
die om 12:48 was afgebroken. `cancelled` telt nu hetzelfde als `error`.

**En in beide gevallen wordt de boekhouding nu teruggedraaid**, zodat een
verversing die aantoonbaar niet heeft plaatsgevonden niet meetelt en de verkoper
er geen veertien dagen op vastzit.

Tien tests in `tests/test_verversen_gemeld_als_gelukt.py`; zes daarvan falen
aantoonbaar op de oude code.

## 30-08-2026 — Waarom die Vinted-verversingen überhaupt mislukten

Nagemeten, niet aangenomen: de twee advertenties waarvan de verwijdering
"mislukte" staan gewoon nog online (vinted.nl/items/8587347818 en /5462539816
geven allebei HTTP 200, een verzonnen nummer geeft 404). De controle in de
extensie had dus gelijk: er was niets verwijderd. Geen enkele advertentie van
deze verkoper is kwijtgeraakt.

Twee dingen in `bgDeleteVinted` konden dat veroorzaken, allebei aangepakt in
extensie 1.0.269:

1. **De weg-knop werd alleen in het Engels gezocht** (`/^delete$/`). Op vinted.nl
   heet hij "Verwijderen", op .fr "Supprimer", op .de "Löschen". Hij werd dus
   alleen nog gevonden als Vinted er toevallig een `data-testid` met "delete" op
   had staan. Omnivaleur is een Europese app; Engels alleen is geen uitgangspunt.
2. **Bevestigen kan meer dan één stap zijn.** Vinted vraagt soms eerst een reden
   (verkocht, van gedachten veranderd, …) en pas daarna de definitieve knop. Er
   werd alleen op die eerste knop geklikt; het tweede venster bleef staan en er
   gebeurde niets. Nu worden er tot drie stappen doorlopen, inclusief het kiezen
   van de eerste reden als daarom gevraagd wordt.

**En als het tóch misgaat, staat er nu bij wát er op het scherm stond.** De
foutmelding bevat voortaan de zichtbare knoppen en hun `data-testid`. Zonder dat
is zo'n storing niet na te lopen zonder in te loggen op het account van de
verkoper — en dat kan niet. Dit is dezelfde aanpak als de foutcodes op de server:
liever een melding die de volgende keer meteen het antwoord geeft dan een
melding waar niemand iets mee kan.

Niet met zekerheid vast te stellen zonder een echt Vinted-account: welke van de
twee het bij deze verkoper was. De volgende mislukte poging zegt het zelf.

## 30-08-2026 — De Vinted-verwijderknop, nu met bewijs in plaats van een gok

Daniel vroeg of die 70% zekerheid naar 100% kon. Dat kan, zonder in te loggen op
het account van een verkoper: **Vinted stuurt zijn eigen tekstenboek mee in elke
artikelpagina.** Daar staat letterlijk in hoe elke knop heet, per land.

Opgehaald op 30-08-2026:

    domein      item.actions.delete   ...modal.actions.delete    ...delete_v2
    vinted.nl   Verwijderen           Bevestigen en verwijderen  Ja, verwijderen
    vinted.be   Supprimer             Confirmer et supprimer     Supprimer
    vinted.fr   Supprimer             Confirmer et supprimer     Supprimer
    vinted.de   Löschen               Bestätigen und löschen     Löschen
    vinted.com  Delete                Confirm and delete         Delete

Daarmee is de oorzaak géén gok meer. Twee dingen, allebei hard:

1. De knop werd alleen als `/^delete$/` gezocht. Op vinted.nl heet hij
   "Verwijderen". Er is trouwens **geen** stap waarin Vinted om een reden vraagt
   — dat vermoedde ik eerder, en dat klopt niet; het is één venster.
2. Werd dat venster niet als `role="dialog"` herkend, dan zocht de bevestiging in
   de HELE pagina en pakte de eerste treffer: de knop op de pagina zelf. Die werd
   dan twee keer aangeklikt — venster open, venster dicht, niets verwijderd, en
   daarna terecht "still in your wardrobe". Bij .fr/.be en .de is dat gegarandeerd
   mis, want daar heet de bevestigknop letterlijk hetzelfde als de knop op de
   pagina.

**Het bewijs staat in `tests/vinted-mock/vinted-delete.html`.** Die pagina bootst
acht schermen na met Vinted's echte teksten, draait de ECHTE routine uit
`background.js` (er door `build.js` uitgesneden) en zet de code van vóór vandaag
ernaast. Uitkomst in een echte browser:

    NU:  8 van de 8 goed
    OUD: 7 van de 8 stuk — waaronder het geval van deze verkoper, waar de knop
         op de pagina TWEE keer werd aangeklikt en de bevestiging nul keer

De routine staat daarom nu als losse functie `_mwVintedVerwijderen` in
background.js. Zet hem niet terug als anonieme functie binnen `bgDeleteVinted`:
dan snijdt het harnas hem niet meer uit en test die pagina stilletjes niets meer.
`tests/test_vinted_verwijderknop.py` bewaakt dat, en bewaakt de knopteksten zelf.

Extensie 1.0.270. Ondergrens niet opgehoogd.

## 30-08-2026 15:27 — Mijn eigen fout: de geïnjecteerde functie stond niet op zichzelf

Daniel probeerde 1.0.270 zelf en kreeg bij élke poging meteen:

    Delete control not found on Vinted item page for ID 8556988767 — Vinted may
    have changed its layout. [extensie 1.0.270]

Zonder de regel "Zichtbaar op het scherm: …" die daar had moeten staan. Dát was
het spoor: die tekst ontbrak omdat de hele routine al was omgevallen vóór er ook
maar iets was bekeken.

**Oorzaak.** Chrome injecteert bij `chrome.scripting.executeScript` alléén de ene
functie die je meegeeft; de rest van background.js bestaat in die pagina niet. Ik
had de hulpfunctie voor het schermbeeld ernaast gezet als losse
`_mwVintedSchermbeeld()`. In de pagina gooide dat een ReferenceError, `execInTab`
gaf `undefined` terug, en dat leest als "knop niet gevonden". De verversing was
daarmee voor iedereen stuk — erger dan de storing die ik aan het repareren was.

**Waarom het namaakscherm dit niet ving.** Daar stonden beide functies gewoon op
de pagina, dus daar wérkte het. Een harnas dat de code anders laadt dan de
werkelijkheid bewijst niet wat je denkt.

**Wat er nu staat.** De hulpfunctie is genest, en er is een test die naar de enige
vraag kijkt die telt: roept de geïnjecteerde functie iets aan dat straks niet
bestaat? Die test vindt op de kapotte versie precies `_mwVintedSchermbeeld` terug.
Verder wordt er nu eerst gewacht tot Vinted de pagina heeft opgebouwd — te vroeg
kijken levert nul knoppen op en heet dan ten onrechte "knop niet gevonden".

Extensie 1.0.271.

## 30-08-2026 17:05 — Marktplaats verversen: "verwijderd" betekende niet altijd verwijderd

Daniel vroeg de verversing van Marktplaats op dezelfde manier na te lopen als
die van Vinted. Een verversing is weghalen + opnieuw plaatsen, en de server laat
die tweede helft alleen los als de verwijderopdracht "done" meldt. Meldt het
verwijderen dus ten onrechte succes, dan komt er een tweede advertentie naast de
eerste. Dat is letterlijk de melding van zilverwebsite.nl:
"Na verversen blijven oude advertenties staan, aantal op Marktplaats is gegroeid."

Drie gaten gevonden, alle drie aangetoond in een echte browser
(tests/vinted-mock/mp-delete.html draait de ECHTE bgDeleteMp2dh tegen een
nagebouwd "Mijn advertenties", met de versie van vóór vandaag ernaast — vastgezet
op commit 0536966 zodat het tegenbewijs niet stilletjes zichzelf wordt):

1. De controle NA het verwijderen telde niet hoeveel advertenties de pagina liet
   zien. Bij het zoeken gebeurde dat al wel, juist om "hij staat er niet" te
   kunnen onderscheiden van "de pagina laadde niet / je bent uitgelogd" — maar bij
   het nakijken niet. Een leeg overzicht las de extensie daar als "verwijderd".
   Nu vergeleken met het aantal van vóór het verwijderen, want nul kan ook eerlijk
   zijn: wie zijn laatste advertentie ververst houdt een leeg overzicht over.

2. Het overzicht is bij een grote verkoper geen getuige. Het rendert vijftig
   advertenties per keer en de extensie klikt maximaal veertig keer door; boven de
   tweeduizend staat de advertentie er simpelweg niet tussen. Jaap heeft er 1.284,
   Egbert 5.540. Nu wordt met een advertentienummer eerst de advertentiepagina zelf
   opgevraagd (/seller/view/{id}) — die antwoordt wél eenduidig.

3. De verwijderknop werd gekozen op "tekst begint met verwijder". Eén woord te
   ruim: elke knop die "Verwijder <iets>" heet en hoger op de pagina staat won.
   Er werd geklikt, er kwam geen venster, en de verversing eindigde zonder dat
   iemand kon zien dat de verkeerde knop was geraakt. Nu op de hele tekst, en de
   knop met de telling ("Verwijder (1)") wint — alleen de bulk-knop krijgt die.

Uitslag van de proef: nieuw 12 van de 12 goed, oud 3 fout, waarvan twee van het
gevaarlijke soort (gemeld als gelukt terwijl de advertentie online bleef).

Daarnaast staat er nu een test die voor ALLE 25 functies die in een pagina worden
uitgevoerd nagaat of ze op zichzelf staan — de fout die ik gisteren zelf in 1.0.270
introduceerde was Vinted-specifiek bewaakt, nu geldt het voor de hele extensie.

## 30-08-2026 — "verkeerde-categorie-toegewezen": geen nieuwe reparatie, wel uitgezocht

Met voorrang doorgegeven (zilverwebsite.nl + amandahaas1979, storing sinds
17-08). Nagelopen in plaats van blind gerepareerd, want de melding bundelt
twee losse dingen onder één sleutel:

**Zilverwebsite (17-08): "zilver ontbreekt in de lijst".** Op dat moment
bestond de sieraden/antiek-taxonomie nog niet in de huidige vorm. Nagemeten in
de echte `items`-tabel: van zijn 1000 advertenties staan er nu 990 correct
onder `antiek`/`sieraden` (390 alleen al onder "antiek goud en zilver"), en
maar 8 zonder categorie — allemaal smalle randgevallen (manchetknopen,
dasklem) waarvoor inderdaad geen bladcategorie bestaat. Die 8 krijgen nu een
nette vraag om zelf een categorie te kiezen (`CategoryUnresolvedError`/422),
geen foute toewijzing en geen 500. Te klein en te specifiek om nu een nieuwe
Marktplaats-categorie-ID bij te verzinnen zonder hem in een ingelogde browser
na te lopen — dat blijft een aparte melding als het weer opduikt.

**Amanda (30-08, 14:57): "verkeerde categorie bij verversen, ook een 500".**
Haar melding valt exact in het gat 12:50–14:11 waarin de server alleen nog
`RemoteProtocolError` (weggevallen Supabase-verbinding) teruggaf — te zien in
`server_fouten`, en dat gat is dezelfde storing die twee regels hierboven al
werd gerepareerd (de leesherhaling in `backend/database.py`, commit 74ec109).
Haar eigen items (`Verzilverd beertje beeldje`, `Vintage russische matroesjka
fles hout`) staan inmiddels gewoon goed gecategoriseerd. Sinds 14:15 uur staat
er geen server_fout meer, van niemand.

Geen code gewijzigd. Teruggemeld als `opgelost` — de uitleg wijst naar de
databasefix die al onder een andere titel in dit logboek staat, niet naar een
nieuwe reparatie.

## 30-08-2026 — "advertentietekst-onjuist-overgenomen": geen code gewijzigd, geen storing

Met voorrang doorgegeven (amandahaas1979 + zilverwebsite.nl). Nagelopen via de
`analyses()`/`bugs()`-opslag van de mailagent en het opdrachtenlogboek (`jobs`),
niet blind gerepareerd.

**De bundeling zelf klopt niet.** In de opgeslagen berichtbeoordelingen draagt
maar één bericht deze exacte `bug_sleutel`: zilverwebsite.nl, 28-08 16:02,
"Klant vermoedt dat Shopify-tekst wordt gebruikt en stopt met handmatig
klikken." Amanda's bericht van 30-08 12:12:30 — waarvan de tijd toevallig het
"eerst"-veld van dit signaal vult — staat in diezelfde opslag ondertussen onder
een ANDERE sleutel: `advertentietekst-niet-geimporteerd` (die staat al apart op
de lijst). De melderslijst van dit signaal bevat haar adres dus als restant van
een eerdere, andere classificatie van hetzelfde bericht — een boekhoudkundig
mankement in `scripts/mail_analyse.py` (een sleutel die niet meebeweegt als een
bericht later anders beoordeeld wordt), niet een crosslisting-bug. Dat verdient
op een ander moment een eigen blik, maar valt buiten wat hier gemeld is.

**Zilverwebsite's eigen vermoeden klopt feitelijk niet.** Zijn advertentietekst
komt niet van Shopify: `items.description` is bij zijn spullen woordelijk zijn
eigen, live Marktplaats-advertentietekst, opgehaald via de publieke
advertentiepagina (`backend/services/mp_enrich.py`, dezelfde route als de
eerdere Admarkt-omschrijvingen-fix). Elke omschrijving eindigt met dezelfde
lange SEO/winkeltekst die hij zelf op al zijn advertenties zet — dat ziet er
op een cross-listing wat vreemd uit, maar het is precies wat hij zelf typte,
niet iets wat wij verkeerd overnamen.

**Zijn account heeft wél een echt probleem, alleen een ander.** 815 van zijn
1203 opdrachten staan op `error`, 117 hangen al sinds 03:23 uur op `pending`.
Verreweg de meeste fouten zijn al bekend en apart getrackt (ontbrekende
"verantwoordelijke partij"-velden, "niet geplaatst — velden in het rood",
Chrome die halverwege sluit). Wel gevonden: één opdracht ("description could
not be placed into the editor", 29-08 02:26) waarbij de verwijdering wél
lukte maar de herplaatsing niet — en er geen nieuwe poging op volgde, dus die
advertentie staat sindsdien nergens meer. Te smal en te zeldzaam (1 van 815)
om nu een aanpassing aan de al zwaar geharde `_mwFillDescription` in
`extension/content/shared.js` op te hangen zonder het in een ingelogde browser
te kunnen zien — dat hoort bij een herplaatsen/verliest-advertenties-melding,
niet bij deze sleutel.

Geen code gewijzigd. Teruggemeld als `afgewezen`.

## 30-08-2026 — Amanda's vier meldingen van vandaag (extensie 1.0.273)

Vier binnengekomen berichten, twee met een schermafbeelding. Alle vier nagelopen
op haar echte gegevens (477 artikelen, 486 advertenties, 9 op Vinted) en op de
echte pagina's van Marktplaats en Vinted — niet op een namaakscherm.

**1. Verversen zette de advertentie in een verkeerde categorie.** Haar woorden:
"dan gaat dat goed, tot het punt dat de advertentie is geplaatst: hij zet deze
dan in de verkeerde categorie. Dit kun je bij MP niet aanpassen, dus moet je de
advertentie weer in zijn geheel handmatig plaatsen."

Oorzaak: bij het importeren gooien we de categorie van Marktplaats wég en laten
we Haiku er een nieuwe bij raden uit `_TAXONOMY` (backend/api/imports.py). Die
lijst kent kleding, wonen, antiek, muziek en sieraden. Amanda verkoopt daarnaast
munten, bankbiljetten, postzegels en boeken — daar bestaat in onze lijst geen
goede doos voor, dus werd het altijd de dichtstbijzijnde verkeerde. Bij het
herplaatsen kwam de advertentie daar dan ook echt terecht.

`import_candidates.category` is bij al haar 477 items NULL, terwijl de scan het
veld `category_name` van Marktplaats wél meestuurt (background.js). Dat wordt
serverkant nergens gelezen. Dat gat staat nog open.

Wat er nu wél gebeurt: de oude advertentie staat op het moment van verversen nog
online, en Marktplaats zet zijn eigen categorie letterlijk op die pagina
(`"l1CategoryId":1784,"l1CategoryName":"Postzegels en Munten","l2CategoryId":1789`).
Die wordt nu gelezen — door de server in stap 1 van `relist.py`, dus VÓÓR het
verwijderen, en nog eens door de extensie in `mpAdvertentieSnapshot` (die staat
daar ingelogd; Marktplaats geeft een kale server geregeld een 403). Kennen we het
paar zelf ook, dan houdt het zijn eigen regel uit `MP_CATEGORIES` — daar hangt
het bucketId aan, en bij kinderkleding de maat-afhankelijke onderverdeling.
Kennen we het niet, dan `/plaats/{l1}/{l2}?title=`, dezelfde tweenummervorm die
de muziektak al gebruikt. Mislukt het ophalen, dan verandert er niets: een
gemiste categorie mag nooit een advertentie kosten.

**2. Vinted gooide brocante in de kinderkleding.** "Bij het plaatsen op Vinted,
wil hij alles in de categorie kinderkleding gooien :P".

De puntentelling in `fillCategoryVinted` deelt losse bonuspunten uit — "Other …"
is +1, "sneakers" +2, de juiste sekse +3 — en `best()` neemt élk blad met een
score boven nul. Die bonussen zijn bedoeld om te kiezen TUSSEN bladen die al
ergens op sloegen, maar één bonuspunt was in zijn eentje genoeg. Bij een vintage
lamp of een beeldje raakt geen enkele hint iets, en dan won het eerste blad dat
toevallig "Other children's clothing" heette.

Aangetoond, niet beredeneerd: de echte puntentelling draait nu in Node tegen een
suggestielijst zoals Vinted die rendert, met de versie van vóór vandaag ernaast
(tests/test_vinted_categories.py). Oud: de wandlamp gaat naar
"other children's clothing | kids > clothing". Nieuw: geen categorie, dus de
verkoper kiest zelf. Twee regels erbij: een blad dat geen enkele hint raakt is
geen kandidaat, en een artikel uit de takken wonen/antiek/kunst/muziek/sieraden/
games/electronics/audio kan nooit meer in een kledingblad belanden.

Haar negen bestaande Vinted-advertenties staan overigens wél goed (Home >
Wandverlichting, Home > Standbeelden en beeldjes, Dames > Kettingen — live
nagekeken). Die heeft ze zelf rechtgezet, of Vinted's eigen suggestie was daar
goed genoeg.

**3. Dezelfde foto twee keer.** De naam van een gespiegelde foto is de
vingerafdruk van de INHOUD (`photo_mirror.py`), dus twee bronfoto's die hetzelfde
plaatje zijn — een verkoper die hem twee keer op Marktplaats zette — leveren
twee identieke adressen op, en die gingen allebei naar het formulier. Gemeten
over de hele voorraad: 71 artikelen op vier accounts, waarvan 3 van Amanda.
Ontdubbeld bij het spiegelen én in `uploadPhotos` (dat dekt meteen Vinted, eBay
en Facebook), plus een nachtelijke ronde om 04:30 die de bestaande regels
opschoont.

**4. De "browserfoutmelding" was geen fout.** Op haar schermafbeelding staat
Chrome's gele balk: "'Omnivaleur' is begonnen met foutopsporing voor deze
browser", met een knop Annuleren. Die koppeling (`koppelVroeg`) stond bij ELK
werk-tabblad aan — scannen, Vinted, eBay, verwijderen — terwijl hij maar één
ding doet: een échte toetsaanslag in het verborgen omschrijvingsveld van het
plaatsformulier van Marktplaats. Nu koppelt hij alleen nog op
`/(marktplaats\.nl|2dehands\.be)/plaats/`. Die knop Annuleren verbreekt de
koppeling, dus wie hem indrukte brak zonder het te weten zijn eigen
Marktplaats-publicaties.

**Ook langsgekomen, bewust niet als storing behandeld:** de
"verantwoordelijke partij". Amanda: "hij zet bij fabrikant, adres en mailadres
de bedrijfsgegevens van mijn bedrijf neer… Dat is niet de bedoeling." Ze heeft
gelijk dat dat een keuze hoort te zijn — ze had die velden alleen ingevuld omdat
het dashboard anders wéigerde te publiceren naar Marktplaats en 2dehands. Er
staat nu een schakelaar bij (standaard aan, dus voor bestaande klanten verandert
er niets); staat hij uit, dan wordt er niets ingevuld, niets geblokkeerd, en
klaagt de extensie ook niet meer over een leeg veld dat wij niet hoefden te
vullen. Of dit blok juridisch verplicht is voor tweedehands brocante is geen
vraag die wij voor haar kunnen beantwoorden — daarom een keuze en geen standpunt.

**Nog open na vandaag:**
- `category_name` uit de Marktplaats-scan komt nog steeds niet in
  `import_candidates`. Een eerste publicatie (geen verversing) draait dus nog
  altijd op de geraden categorie.
- De sleutel `advertentietekst-onjuist-overgenomen` is vandaag door een andere
  sessie afgehandeld; zie de aantekening hierboven.

### 30-08-2026 — `marktplaats-niet-ingelogd-melding` was al gerepareerd, alleen nooit teruggemeld

Met voorrang doorgegeven (2 melders, klant dreigt te stoppen). Nagemeten in
plaats van aangenomen: dit is exact dezelfde verouderde-extensiekopie-storing
die op 29-08 hierboven al is uitgezocht en gerepareerd (`_rechtgezette_foutmelding`
in `backend/api/jobs.py`, commit `089d506`, `tests/test_extensieversie.py` —
11 tests, allemaal groen, fix staat op main). Beide melders van vandaag
(info@retrogameking.com, info@papas-plectrums.nl) zijn dezelfde Dennis en
Egbert uit die eerdere aantekening.

Wat er mis ging: de fix zelf was er, maar de terugmelding met `opgelost` voor
déze exacte sleutel is toen vergeten — de paragraaf van 29-08 meldt de
aanverwante sleutels (`marktplaats-import-foutmelding`,
`import-wordt-steeds-trager`) wel als teruggekoppeld, maar
`marktplaats-niet-ingelogd-melding` zelf niet. Daardoor bleef hij op de
bugslijst staan en kreeg hij vandaag opnieuw voorrang, met dezelfde twee
melders van weken geleden.

Geen code gewijzigd. Teruggemeld als `opgelost`. Les: bij een groep verwante
sleutels die in één ronde worden uitgezocht, elke sleutel apart afmelden —
niet alleen de sleutel waarvan de mail toevallig als eerste binnenkwam.

## 31-08-2026 — Het project stond op slot, en niemand kreeg bericht

**Wat er aan de hand was.** Supabase weigerde elk verzoek met een 402:
`exceed_cached_egress_quota, exceed_egress_quota, exceed_storage_size_quota`.
Inloggen op omnivaleur.com gaf 503, de blog 500, en de mailagent viel volledig
stil. Gemeten in het Supabase-dashboard: verkeer 21.827 MB tegen een limiet van
5 GB (437%), cache-verkeer 5.845 MB (117%), opslag 2.108 MB tegen 1 GB (211%).
Database zelf 104 MB van 500 MB, en 24 actieve gebruikers van de 50.000 die het
gratis plan toestaat.

Die verhouding is het hele verhaal: 21,8 GB verkeer op 24 gebruikers is 900 MB
per persoon. Dat komt niet van bezoekers. Het kwam van onze eigen lussen.

**Wie het merkte.** Ronald van Zilverwebsite, om 07:22, met een
schermafbeelding van het inlogscherm. Onze eigen server wist het al uren en
zei niets. Dat is de verkeerde volgorde en is nu gerepareerd (zie onder).

**De drie kranen die openstonden.**

1. `poll_platform_statuses` haalde ELKE ronde alle actieve advertenties op
   (gemeten 27-08: 4.751) en liep ze daarna sequentieel langs met een
   netwerkaanroep per stuk. Elke vijf minuten. Twee gevolgen, allebei
   onzichtbaar: het verkeer, én het feit dat zo'n ronde niet áf kan — wat
   achteraan de lijst stond werd in de praktijk nooit gecontroleerd. Nu een
   wachtrij op `last_checked` (oudste eerst, nooit gecontroleerd gaat voor),
   hooguit 500 per ronde, en altijd een stempel — ook als het nakijken mislukt,
   anders blijft één kapotte advertentie eeuwig vooraan staan.
2. `vul_ontbrekende_teksten_aan` haalde elk kwartier van álle items de
   volledige `description` op om te kijken óf hij leeg was. Bij Egbert (2.135
   items) zijn dat megabytes per kwartier voor een vinkje. Nu een lichte
   id-vraag met dezelfde filter die `_verkopers_met_gaten` al gebruikt, en de
   echte tekst alleen voor de rijen die deze ronde aangepakt worden (daar is
   hij nodig voor `_is_afgekapt`).
3. De mailagent haalde per beurt dezelfde lijsten vijf tot tien keer opnieuw
   op — 144 beurten per dag. Nu één keer per beurt (`_GELEZEN`).

**Wat er nog moet gebeuren zodra de database open is:** de laatste foto's van
Supabase Storage naar Cloudflare R2 (`scripts/migrate_photos_to_r2.py`, met
`--budget-mb`, want terúglezen kost zelf ook verkeer). R2 geeft 10 GB en rekent
geen verkeer, dus dat haalt de opslag van 211% naar bijna niets en de 5,8 GB
cache-verkeer naar nul.

**Besluit dat bij Daniel ligt:** de factuurperiode liep tot 1 september, dus de
blokkade gaat er vanzelf af en kost niets — maar tot dat moment ligt de site
plat voor klanten. Meteen open kan door Supabase Pro aan te zetten (€25, weer
opzegbaar). Dat is een geldbeslissing en dus zijn keuze, niet die van de
developer.

## 31-08-2026 — De mailagent maakt zijn eigen werk af

Daniel, met tien concepten in zijn map: "nu staan er veel mails klaar in
concepten die daar niet horen", "nooit meer dubbele mails of dubbele meldingen
dat een concept klaar staat", "automatische follow up automatisch verstuurd
worden (bijvoorbeeld stap 2 of 3 in de mailsequence of een follow up mail als ik
de video al gestuurd heb)".

**Waar de grens nu ligt, en waarom daar.** Van die tien concepten waren er zeven
beleefdheidsberichten zonder één belofte — "ik laat het hierbij", "was het
filmpje duidelijk?" — waarvan de oudste twee dagen lag. De drie die er wél
hoorden te liggen hadden alle drie hetzelfde kenmerk: een toezegging die alleen
Daniel kan waarmaken (een belafspraak), of een storing die nog openstaat. De
scheidslijn is dus niet "koud of warm" en niet "lead of klant", maar: staat er
iets in wat iemand moet nakomen?

Gaat vanzelf weg: opvolging op stilte (stap 2 en 3), antwoorden op een nee, en
de terugkoppeling van de developer over een gerepareerde storing — die laatste
is de enige tekst in de hele machine die vóór het schrijven aan de code is
getoetst. Blijft liggen: alles met een toezegging (bellen, geld, "kom erop
terug"), alles waar het model de vraag niet uit de code kon beantwoorden, en
alles aan een betalende klant waar geen developer aan te pas kwam.

Die rem (`_waarom_niet_zelf_versturen`) kan alleen tegenhouden, nooit
doorlaten: een mail die onterecht blijft liggen kost één klik, een mail die
onterecht weggaat is niet terug te halen. Het seintje zegt er voortaan bij
waaróm iets blijft liggen, anders is de map weer een stapel.

**Wat verstuurd wordt, komt in Verzonden te staan.** Dat is geen netheid maar
het slot: `_waarom_geen_concept` beantwoordt "hebben wij hierna al iets
gestuurd?" door in die map te kijken. Zonder die kopie ziet de volgende beurt
geen spoor en gaat hetzelfde bericht nog een keer weg. Mislukt de kopie, dan is
dat een alarm.

**Geen administratie = niets versturen.** Bij de 402 hierboven klapte de agent
om op zijn eerste regel en zweeg een etmaal, terwijl er vier klanten wachtten.
Erger was het vangnet in `_save_state`: dat schreef alleen naar schijf als er
hélemaal geen database was ingesteld, dus bij een échte storing werd er niets
bewaard. Doorwerken op een administratie die niet bijgewerkt kan worden is
precies hoe iemand twee keer dezelfde mail krijgt. Nu: lezen of schrijven
mislukt = de beurt gaat niet door, en er gaat alarm uit (hooguit eens per 6 uur).

**Meldingen over wat de twee agenten afspreken.** Op Daniels verzoek. De
klantenservice die de developer aan het werk zet (`dev_starter`), en de
developer die `opgelost` of `afgewezen` terugmeldt, sturen nu allebei een
logboekregel naar zijn postbus. Geen verzoek om actie — zodat hij kan bijsturen
voordat een sessie zelfstandig code pusht.

**Nooit twee keer hetzelfde seintje.** Elk seintje draagt een kenmerk
(`X-Omnivaleur-Melding`) en een kopie in de meldingenmap; voor het versturen
wordt op dat kenmerk gezocht. Bewust in de postbus en niet in de administratie —
die lag bij deze storing juist plat.

**Openstaand na vandaag:**
- Egbert Brouwer wil bellen; hij was 31-08 tussen 14:00 en 16:30 beschikbaar.
  Dat is een afspraak die Daniel zelf moet maken; het concept ligt klaar.
- Jordi (Budgetheld) vraagt om hulp bij een integratie. Nog geen concept.
- De tien wachtende concepten zijn geschreven vóór deze wijziging en gaan dus
  niet vanzelf alsnog weg; die keuze ligt bij Daniel.

### 31-08-2026 — Aanvulling: wannéér de blokkade begon, en een dubbele kopie in Verzonden

**De blokkade begon vanochtend, niet 's nachts.** Na te meten aan de map
Verzonden: de mailagent stuurde om 09:45 en 09:46 nog gewoon post (Twan de Haas,
TipTopLaptop) en om 00:08 nog het seintje "12 conceptmails wachten op je". Ronald
van Zilverwebsite kreeg zijn inlogfout om 09:22. Rond 10:20 gaf elke aanroep een
402. De storing zit dus in het venster 09:20–10:20 en de agent heeft daarna geen
beurt meer afgemaakt. Dat sluit aan bij het beeld: de meter liep de hele maand
vol en tikte vanochtend over.

**Zoho archiveert zelf al.** Bij het met de hand versturen van de negen wachtende
concepten bleek elke mail dáárna DUBBEL in Verzonden te staan: één kopie van Zoho
zelf (dat doet hij voor alles wat via zijn eigen SMTP gaat) en één van ons. Dat
breekt het slot tegen dubbele mail niet — dat kijkt alleen óf er iets staat —
maar het vervuilt wel de map waar `_toonprofiel` Daniels toon uit afleidt.

`_stuur_zelf` legt die kopie daarom alleen nog neer als er via Resend verstuurd
is. Dat is precies het geval op de server: Resend kent Zoho niet en zet daar dus
niets neer, en juist dáár is de kopie geen netheid maar het slot zelf. De negen
dubbele regels van vandaag blijven staan; e-mail weggooien doen we niet.

**Wat er nog open ligt bij de klanten (31-08, eind ochtend):**
- Egbert Brouwer wil bellen, vandaag tussen 14:00 en 16:30. Zijn concept ligt
  klaar maar is ingehaald door zijn eigen bericht van 23:16.
- Twan de Haas vroeg om 10:07 om de video ("Ik zie de video graag tegemoet").
  Dat is een warme lead en dus een concept voor Daniel; die kan pas gemaakt
  worden als de database weer open is.
- Jordi (Budgetheld) vroeg om hulp bij een integratie.
- Rob Michiels (Data Impact) zei netjes nee ("we hebben al een koppeling"). Die
  gaat vanaf nu vanzelf een afsluitend berichtje krijgen.

## 31-08-2026 — CORRECTIE op de aantekening van vanochtend: zelf versturen was fout

De aantekening hierboven ("De mailagent maakt zijn eigen werk af") beschrijft een
grens die niet houdbaar bleek. Binnen een uur nadat hij aan stond, ging het drie
keer mis en heeft Daniel de hele mailflow gepauzeerd.

**Wat er misging.**

1. **Een verzonnen naam.** De mail aan Zilverwebsite begon met "Hi Ronald". Zo
   iemand bestaat daar niet. Oorzaak is aantoonbaar en zat niet in het model
   maar in onze eigen instructie: `HERSTELBERICHT_REGELS` vroeg letterlijk om
   `"Hi <naam>,"` terwijl er in dat hele verzoek nergens een naam meegegeven
   werd — alleen een e-mailadres en de reparatiepunten. Het model vulde dat gat
   zelf in. Er stond al sinds 20-08 vast dat een aanhef nooit een geraden naam
   mag bevatten (`_persoonsnaam`), maar die regel gold alleen voor de koude
   mail en niet voor deze route.
2. **Een antwoord op een gesloten gesprek.** Patricia van Boutique MoDo kreeg
   op 31-08 een antwoord op een bericht dat Daniel op 27-08 zelf al had
   beantwoord. Dat kwam niet door de agent maar door mij: ik verstuurde de
   wachtende concepten rechtstreeks via SMTP en sloeg daarmee juist de controle
   over die daarvoor bestaat (`_waarom_geen_concept`). Een concept van dagen
   oud is geen concept meer maar een momentopname.
3. **Een derde bericht aan iemand die met vakantie was.** Frank de Veer kreeg op
   31-08 een opvolging, terwijl ons bericht van 20-08 al eindigde met "dan hoor
   ik het wel" — een afsluiting — en het enige wat hij ooit terugstuurde zijn
   afwezigheidsassistent was.

**Waarom de grens zelf fout was.** Ik toetste of een mail iets BELOOFDE. Maar wat
een mail schadelijk maakt is of hij nog KLOPT: de aanhef, de naam, of het gesprek
al gesloten was, of iemand er eigenlijk wel is. Geen van die drie fouten bevatte
één toezegging. Een filter op toezeggingen ziet ze geen van drieën.

**Wat er nu staat.**
- `MAILFLOW_GEPAUZEERD = True`. `tick` doet niets, vóór het controleren van de
  afzender en vóór het lezen van de administratie. Weer aanzetten is Daniels
  besluit.
- De hele zelf-verstuur-machinerie is WEGGEHAALD, niet uitgezet. Een schakelaar
  is iets wat iemand later per ongeluk omzet.
- De instructie vraagt niet meer om een naam, én er zit een slot achter dat elke
  naam uit de aanhef haalt voordat de tekst de map in gaat — een promptregel is
  een verzoek, geen garantie.
- Na een afsluiting van onze kant komt er geen opvolging meer (`_is_afsluiting`),
  en een afwezigheidsassistent telt niet als een gesprek.

**Les voor de volgende keer.** "Er valt hier niets te beslissen" is geen goede
reden om iets zelf te versturen. De vraag is niet of het bericht een besluit
bevat, maar of iemand die de klant kent er nog naar gekeken heeft. Bij een
machine die teksten schrijft is dat antwoord voorlopig altijd: nee.

**Nog recht te zetten:** in de map Verzonden staan negen berichten van 31-08
dubbel. Daar is maar één keer verstuurd — Zoho zet post die via zijn eigen SMTP
gaat zelf al in Verzonden, en ik legde er nog een kopie naast. De ontvangers
hebben elk één mail gekregen; het dubbele zit alleen in Daniels eigen map.

### 31-08-2026 — Bijstelling: koude flow weer aan, en één seintje in plaats van drie

Daniel, na de pauze van vanmiddag: "koude email flow mag wel (1, 2 en 3),
reacties in concepten ook, maar het gaat mij echt om de samenwerking mail-agent
- claude code, en dat er dan een mail naar mij gestuurd wordt met wat er dan
gedaan is door deze 2 en dat ze samen een concept voor me hebben klaargezet."

`MAILFLOW_GEPAUZEERD` staat dus weer op False. De aantekening hierboven ("weer
aanzetten is Daniels besluit") is daarmee ingehaald — dat besluit is genomen.
De schakelaar zelf blijft staan; het is de enige knop die in één keer alles
stillegt.

Wat er nu geldt: mail 1, 2 en 3 van de koude reeks gaan vanzelf (dat deden ze
altijd al en daar is nooit iets mee misgegaan). Alles wat een ANTWOORD is —
reacties, opvolgingen, terugkoppelingen van de developer — blijft een concept.
Het zelf-versturen van antwoorden blijft weg.

De drie losse seintjes rond de samenwerking zijn er weer uit (klantenservice →
developer, developer → klantenservice, concept klaar). Ze meldden hetzelfde ding
drie keer en vertelden geen van drieën het verhaal. Het staat nu in één mail:
`_samenwerking` in leadgen_mail.py zoekt bij het adres van het concept de
gerepareerde storingen op en zet in het seintje wat de klant meldde, wat de
developer eraan deed, en daaronder het concept zelf.

## 31-08-2026 — Pro aangezet, en de fotoverhuizing bleek al gedaan

**Besluit van Daniel:** Supabase Pro aangezet (€25/mnd) om het project van slot
te krijgen. Aanleiding: het project stond niet meer alleen "restricted" maar
volledig **paused**, en van de drie overtredingen resetten er maar twee met de
factuurperiode. `exceed_storage_size_quota` reset nooit — opslag is een
momentopname. Daarmee was er een klem: de opslag kon alleen omlaag door de
foto's te verhuizen, en dat kon alleen als de database open was. Wachten tot
1 september zou die klem niet hebben doorbroken.

**Wat de meting daarna liet zien.** De fotoverhuizing naar Cloudflare R2 was al
gedaan — niet vandaag door de tweede ontwikkelaar, maar al op 16-08-2026, samen
met een opruiming die de bucket van 3,71 GB naar 0,67 GB bracht. Gemeten na het
openen:

  * `items`: 36.193 foto-urls, waarvan **0** nog op Supabase en 32.668 op
    img.omnivaleur.com. De rest zijn externe CDN-urls (Marktplaats, Vinted).
  * Bucket `photos`: 507 objecten, **0,67 GB** — niet de 2,1 GB die het
    dashboard meldde. Supabase-opslagmetingen lopen achter; de 2,1 GB was
    vermoedelijk de stand van vóór die verhuizing.
  * Daarvan zijn er 33 echt wees (0,06 GB). De overige 461 worden alleen nog
    genoemd in oude rijen van `jobs`/`import_candidates`, niet in actieve
    advertenties. `cleanup_orphan_photos.py` laat die bewust staan.

**Les.** De 402-melding noemt drie overtredingen zonder te zeggen welke met de
periode meereset. Alleen verkeer en cache-verkeer doen dat. Bij een volgende
blokkade: kijk éérst of `exceed_storage_size_quota` erbij staat, want die alleen
maakt wachten zinloos.

**Ook gebleken:** de `opgelost`-terugmelding voor
`marktplaats-niet-ingelogd-melding` van eerder vandaag is nooit aangekomen — de
402 slikte de schrijfactie. De sleutel staat nog steeds als MOET ZEKER op de
bugslijst. Bij een blokkade moet elke terugmelding van die dag opnieuw.

**Open bij Daniel:** Pro weer uitzetten zodra het dashboard bevestigt dat opslag
en verkeer onder de gratis grens staan. De meting zegt van wel, het dashboard
loopt een dag achter.

### 31-08-2026 — Waar die 2,1 GB dan wél zat: nergens

Nagemeten met de service-sleutel: er is **één** bucket (`photos`), en die is
0,67 GB — precies de stand van na de opruiming van 16-08-2026. Er is dus geen
tweede bucket en geen verborgen opslag. Het dashboardcijfer van 2,108 GB liep
achter op de werkelijkheid (Supabase telt verwijderde objecten nog een tijd mee).

**Wat dat betekent.** De opslag zat al onder de gratis grens van 1 GB. Van de
drie overtredingen was `exceed_storage_size_quota` dus vermoedelijk een
naijl-effect, en had wachten tot 1 september waarschijnlijk óók gewerkt. Het
advies om Pro aan te zetten is gegeven op het enige zichtbare cijfer (211%) en
dat cijfer was verouderd. Voor de volgende keer: bij een opslagoverschrijding
éérst `cleanup_orphan_photos.py` droogdraaien — dat leest de bucket echt uit —
voordat je op het dashboard afgaat.

### 31-08-2026 — Twee dingen die vandaag boven water kwamen

**1. "Merge all" klapte op elke groep.** Daniel kreeg elf serverfouten op rij
(269E80, 0A2143, 07F3A8, 9D7E67, DFD460, 2C75C5 …). Oorzaak: `listings` heeft
een unieke sleutel op (item_id, platform), dus één item kan hoogstens één
advertentie per kanaal hebben. Acht kopieën van dezelfde trui met elk een eigen
Marktplaats-advertentie botsen daar per definitie mee. Er ging niets verloren —
de listings-update is de eerste van drie stappen, dus verwijderen werd nooit
bereikt — maar de dubbele rijen bleven staan en de klant zag alleen een code.
Nu wordt de botsing vóóraf herkend en die groep overgeslagen met een reden die
de app uitlegt. Vastgelegd in `tests/test_samenvoegen_zelfde_kanaal.py`.

**Nog open, en dit is een keuze voor Daniel:** zolang die unieke sleutel bestaat
kunnen dubbele rijen die állebei op Marktplaats staan niet samengevoegd worden —
en dat is juist het normale geval. Echt oplossen vraagt een handmatige wijziging
in Supabase: de sleutel op (item_id, platform) vervangen door één op
(item_id, platform, platform_listing_id). Dat is dezelfde soort handmatige stap
als eerder bij `listings.sold_price` en `extension_heartbeat`.

**2. Het storingsalarm kon zichzelf niet bezorgen.** `owner_email` staat op
Railway op twee adressen in één instelling. `is_owner_email` in billing.py
splitste die al op komma's; de mailverzending niet — Resend kreeg
`to: ["a@x.nl, b@y.nl"]` en wees dat af. En omdat `meld_quotastoring` een
mislukt alarm expres afvangt (een mailprobleem mag nooit iets blokkeren),
verdween de afwijzing in de containerlogs. Het alarm dat vanochtend had moeten
melden dat de site plat lag, had het dus sowieso niet gered. Gerepareerd voor
zowel Resend als SMTP, met `tests/test_alarm_bereikt_beide_adressen.py`.

**Les.** Een alarm dat zijn eigen mislukking wegslikt is geen alarm. Bij elk
vangnet dat bewust zwijgt hoort een proef die bewijst dat het pad erheen werkt.

### 31-08-2026 — De sleutel op listings is vervangen, samenvoegen kan nu echt

Uitgevoerd door Daniel in de Supabase SQL Editor. De oude
`listings_item_platform_unique` is weg, `listings_item_platform_advert_unique`
staat er. Omdat het één transactie was, is daarmee ook de definitie bewezen:
was de CREATE mislukt, dan stond de oude index er nog.

Wat de oude was (nagemeten voordat we hem aanraakten):

    CREATE UNIQUE INDEX listings_item_platform_unique
      ON public.listings USING btree (item_id, platform)
      WHERE ((status)::text = 'active'::text);

En wat er nu staat:

    CREATE UNIQUE INDEX listings_item_platform_advert_unique
      ON listings (item_id, platform, platform_listing_id)
      NULLS NOT DISTINCT
      WHERE status = 'active';

Eén item mag dus meerdere lopende advertenties op hetzelfde kanaal hebben,
zolang het echt verschillende advertenties zijn. `NULLS NOT DISTINCT` houdt de
oude bescherming overeind: twee lopende advertenties zónder advertentienummer op
hetzelfde kanaal blijven onmogelijk, en zo ziet dubbel publiceren eruit (101 van
de 11.102 rijen hebben geen nummer, dus dat geval is echt).

**Hoe dit is uitgezocht, want dat was het leerzame deel.** De eerste aanname —
een gewone constraint op (item_id, platform) — klopte niet: `pg_constraint`
toonde alleen de primaire sleutel en de verwijzing naar `items`. Een unieke
INDEX staat daar niet in, alleen in `pg_indexes`. En Postgres staat geen
constraint mét voorwaarde toe, wél een index mét voorwaarde. Dat verklaarde
meteen de zes item/kanaal-combinaties die naast elkaar bestonden en alle zes
hooguit één 'active' hadden.

**Les:** bij een unieke sleutel die niet in `pg_constraint` staat, kijk in
`pg_indexes` — en vraag de voorwaarde apart op met
`pg_get_expr(i.indpred, i.indrelid)`, want de Supabase-editor kapt `indexdef`
rechts af en juist daar staat de WHERE. De hele route staat in
`scripts/fix_listings_unique.sql`.

De code in `merge_items` weigert nu alleen wat écht botst (zelfde kanaal én
zelfde advertentienummer, bij status 'active'), met daaronder een vangnet dat
een 23505 van de database opvangt in plaats van hem als serverfout door te
laten. Dat vangnet blijft staan: het beschermt ook tegen een toekomstige
schemawijziging die niemand hier doorgeeft.

### 31-08-2026 — Vinted keurt bij opslaan de héle advertentie, niet je wijziging

Stale stock verlaagde een prijs naar €27,99, de extensie zette die netjes in het
veld, en daarna leek er niets meer te gebeuren — "hij drukt niet op opslaan".
Er wérd op Save gedrukt. Vinted weigerde, omdat de maat op die advertentie leeg
stond, en liet het formulier open staan met "Fill in size to continue".

De controle na het opslaan zocht alleen naar klachten over de prijs. Die was er
niet, dus liep de lus zeven seconden leeg en eindigde met "clicked Save but the
edit form never closed — the update could not be verified". Die zin noemt het
maatveld niet en leest daarom als een knop die nooit is ingedrukt.

**Les, breder dan Vinted:** een kanaal valideert bij het opslaan het hele
zoekertje, niet alleen het veld dat wij aanraakten. Elke bewerkroute moet dus
(a) de verplichte velden die leeg staan aanvullen vóór het opslaan, en (b) bij
een weigering de eigen tekst van het kanaal doorgeven. Een foutmelding die alleen
zegt "kon niet worden bevestigd" stuurt de diagnose gegarandeerd de verkeerde
kant op — hier naar de opslaanknop, terwijl het probleem drie velden hoger zat.

Gerepareerd in `extension/content/vinted.js` (1.0.274): `refreshListingVinted`
vult een leeg maatveld eerst uit het dashboarditem, en noemt bij een weigering
Vinted's eigen rode regel plus welk verplicht veld leeg bleef. Bewezen in
`tests/vinted-mock/opslaan-geweigerd-test.js` (de echte code tegen een
namaakscherm) en `tests/test_vinted_opslaan_geweigerd.py`.

### 31-08-2026 — Correctie: de klant bij Zilverwebsite heet Jaap, niet Ronald

Twee aantekeningen van vanochtend schrijven "Ronald van Zilverwebsite" (bij de
inlogfout van 09:22 en bij "wie het merkte"). Die naam is precies de naam die de
mailagent had verzonnen in "Hi Ronald" — en die in de correctie daaronder al werd
weggezet als iemand die daar niet bestaat. Hij is daarna alsnog twee keer als
feit overgenomen.

Nagemeten aan de 57 mails van `info@zilverwebsite.nl`: de contactpersoon heet
**Jaap**. Lees op die twee plekken dus Jaap.

**Les:** een naam die één keer als verzinsel is aangemerkt, moet ook uit de
aantekeningen die erna geschreven worden. Anders wordt de fout binnen een dag
gewassen tot bron. Bij twijfel: de naam komt uit de mails zelf, nergens anders
vandaan.

### 31-08-2026 — Het vangnet van de klantenservice hing af van de vangst

Twee mails op één dag kregen hetzelfde niet-antwoord. Een klant vroeg of er een
chatfunctie in zit; het concept zei "daar heb ik nu geen goed antwoord op, dat
zoek ik uit". Amanda meldde "hij pakt de refresh button niet"; idem. In beide
gevallen kwam er geen vraag bij Daniel terecht en geen melding bij de developer.

Twee oorzaken, allebei stil:

1. **De trefwoordenlijst is Nederlands, klanten schrijven Engels.** `_grondslag`
   zoekt op woorden als "ververs" en "herplaats". Amanda schreef "refresh", dus
   nul treffers, dus nul regels broncode — over precies het onderwerp waar de
   halve lijst over gaat.
2. **En dat is waar het echt misging:** de regel "kun je het niet uit de code
   halen, geef dan de vraag door aan Daniel" ging alléén mee als er code gevonden
   wás. Precies andersom dus. Juist bij een onderwerp waar niets over te vinden
   is verdween ook de opdracht om te escaleren, en schreef het model vrijuit.

Gerepareerd in `scripts/leadgen_mail.py`: een synoniemenlaag (`verrijk`) vertaalt
Engelse en spreektaalwoorden eerst naar het woord dat de lijst kent — aanvullend,
nooit vervangend — en `GEEN_GRONDSLAG_REGEL` gaat mee wanneer er géén code is:
geen enkele technische bewering, en bij een feitelijke vraag of storing de ene
regel `GEEN ANTWOORD:` die de vraag bij Daniel neerlegt. Voor een betalende klant
volgt daarna nog steeds de tweede ronde zonder beweringen, zodat er wel post is.
Dezelfde vertaalslag zit nu ook in `stand_van_de_storingen`, anders herkent de
klantenservice een bekende storing niet in zijn eigen woorden.

**Les, breder dan deze twee mails:** een vangnet dat pas openklapt als de vangst
lukt, is geen vangnet. Elke regel die zegt "kun je X niet, doe dan Y" hoort
onvoorwaardelijk in de opdracht te staan — het geval waarin hij nodig is, is per
definitie het geval waarin de voorwaarde niet klopt.

### 01-09-2026 — Amanda's teksten stonden één plaats achter de afkapstreep

Amanda: "Ik heb idd eentje kunnen refreshen en die zet hij dan in de juiste
categorie op MP neer! Hij haalt wel nog steeds niet alle teksten uit de
omschrijvingen in de advertenties op."

De reparatie van 29-08 (`vul_ontbrekende_teksten_aan`, elk kwartier een verkoper
bijwerken vanaf de server) draaide gewoon. Hij deed bij haar alleen niets, en dat
was met geen enkele logregel te zien: hij meldde netjes dat hij 150 items had
behandeld.

**Nagemeten aan haar echte voorraad**, niet beredeneerd: 479 items, 200 zonder
omschrijving, verkopersnummer 12058863. De ronde pakt alles wat "iets mist" en
kapt dat af op 150. Maar `_mist_iets` telt ook een leeg merk en een lege maat
mee — en Amanda verkoopt brocante, dus 459 van haar 479 items missen per
definitie iets, voor altijd. Van die lijst had geen van de eerste 150 een lege
omschrijving. Het eerste item zónder tekst stond op plek **150**: één plaats
achter de streep. Elke ronde opnieuw, sinds 29-08.

Dezelfde muur zat voor de knop "Fill from Marktplaats" — die kapt hetzelfde
lijstje op dezelfde plek af. Het scherm geeft na zes lege rondes op, dus wie de
knop wél vond kreeg "niets gevonden" te zien terwijl er 200 teksten klaarstonden.

Gerepareerd in `backend/services/mp_enrich.py` met `_deze_ronde`: wat publiceren
blokkeert gaat voor (eerst zonder tekst, dan zonder prijs, dan één foto, dan de
rest), en de startplek schuift op zodra een ronde niets oplevert.

**Bewezen op de echte gegevens, dezelfde aanroep twee keer, zonder te schrijven:**
oude selectie 20 items → 0 teksten. Nieuwe selectie 20 items → 20 teksten, en 18
kregen meteen ook de rest van hun foto's. Plus zeven tests in
`tests/test_teksten_achteraan_de_rij.py` op haar gemeten vorm, met de selectie van
vóór vandaag ernaast.

**Les, breder dan deze melding:** een wachtrij die altijd bij het begin begint is
geen wachtrij maar een vaste kop. Zodra er ook maar één reden is waarom een item
nooit "af" raakt — hier een merkveld dat bij brocante nooit gevuld wordt — houdt
die kop de rest van de rij tegen, en blijft de ronde net zo lang werk melden als
dat er niets gebeurt. Elke ronde die een lijst afkapt heeft daarom twee dingen
nodig: een volgorde die zegt wat er het meest toe doet, en een startplek die
opschuift als er niets uitkomt.

### 01-09-2026 — Een verkocht artikel werd elke dag opnieuw te koop gezet

Daniel viel op dat (1314) Suitable Half Zip en (1288) Profuomo Fleece Jacket
"super vaak gerelist" waren op Marktplaats, terwijl ze allebei verkocht zijn.
Nagemeten: (1288) had zes Marktplaats-rijen en 27 opdrachten, (1314) zes
herplaatsingen in vier dagen — bij een instelling van dertig dagen.

Twee fouten die elkaar in stand hielden:

1. **Een verwijdering raakte élke advertentierij van dat artikel.** Elke
   herplaatsing zet er een rij bij (de oude blijft als archief staan). Mislukte
   de verwijdering, dan gingen ze allemaal terug op 'actief' — inclusief de rij
   van juni, mét de datum van juni. Die was daarmee meteen weer over zijn
   termijn en werd de volgende ronde opnieuw opgepakt. Dat is de lus. Hetzelfde
   gold voor een al gestelde vraag "is dit verkocht?": die werd stilletjes
   teruggezet naar 'actief'.

2. **"De advertentie was er al niet meer" gold als een geslaagde verwijdering.**
   Stap twee plaatste dan gewoon een nieuwe. Precies wat er bij een verkoop
   gebeurt: de verkoper haalt zijn advertentie zelf weg. Wij zetten hem opnieuw
   te koop, en de verkoop werd nooit opgemerkt.

Gerepareerd in `backend/api/jobs.py`: een verwijderopdracht wijst nu zijn eigen
rij aan (via het rij-id dat de herplaatsing meedraagt, anders het
advertentienummer) en laat afgemelde en verkochte rijen met rust. En een
advertentie die al weg was terwijl hij jonger was dan 28 dagen kan niet vanzelf
verlopen zijn — dat wordt een verkoopvraag in het dashboard, met annulering van
de wachtende plaatsing. Bewezen in `tests/test_herplaatslus.py`.
`scripts/stop_herplaatslus.py` past dezelfde regel toe op wat er al in zat;
uitgevoerd voor Daniels eigen account (18 combinaties, 7 met een levende
advertentie). Bij klanten stelt de gerepareerde code de vraag vanzelf zodra hun
eerstvolgende herplaatsing erop stuit — hun dashboard is niet met terugwerkende
kracht aangepast.

**Les, breder dan het herplaatsen:** afwezigheid is geen bewijs, maar de
leeftijd van iets dat afwezig is soms wél. Een gratis Marktplaats-advertentie
verdwijnt pas na dertig dagen vanzelf; is hij eerder weg, dan heeft iemand hem
weggehaald. Dat onderscheid was gratis beschikbaar en werd niet gemaakt, en
daardoor kreeg "weg" één betekenis waar er twee nodig waren.

### 01-09-2026 — De verkocht-badge staat op het gesprek, niet op de advertentie

Daniel, kijkend naar zijn eigen berichtenlijst: "de enige manier dat ik zelf kan
controleren of iets op Marktplaats echt verkocht is, is via de verkocht badge."
Dat is precies waarom wij een handmatige verkoop nooit zagen: wij keken naar het
advertentie-overzicht en naar de advertentiepagina, en daar komt bij een
handverkoop nooit een label te staan — de verkoper haalt de advertentie gewoon
weg. Marktplaats zet het label op het GESPREK met de koper.

Sinds 1.0.279 leest de kwartaalronde die de berichten telt die badges mee
(`_mwReadNotifCounts` in `extension/background.js`, endpoint
`POST /api/listings/sold-from-messages`). Geen extra bezoek aan Marktplaats: die
pagina ging toch al open.

Dit is bewijs en geen aanwijzing, dus hier wordt geboekt in plaats van gevraagd.
Drie grenzen maken dat verantwoord: (a) alleen een LOS labeltje dat exact
"verkocht" is telt, nooit het woord uit een berichtvoorbeeld; (b) het nummer voor
de titel — "(1308)" — moet bij precies één artikel van deze verkoper horen, want
de titel staat afgekapt in de lijst; (c) het artikel moet nog ergens te koop
staan, want een gesprek houdt zijn badge voor altijd en zonder die grens zou elke
ronde de hele verkoopgeschiedenis opnieuw als omzet van vandaag boeken. Bewezen
in `tests/berichten-verkocht-badge-test.js` (de echte extensiecode tegen een
namaaklijst, nagebouwd op Daniels scherm) en `tests/test_verkocht_uit_berichten.py`.

**Wat het NIET oplost:** een verkoop buiten Marktplaats' eigen betaal- of
verzendstroom om krijgt geen badge. (1314) heeft drie gesprekken en geen badge,
(1001) staat helemaal niet in de lijst. Voor die gevallen blijft de vraag
"is dit verkocht?" in het dashboard de enige route.

**Meteen meegenomen, en het is een geldfout:** `handle_item_sold` zette élke
advertentierij van dat kanaal op 'verkocht'. Sinds elke herplaatsing er een rij
bij zet — één artikel van Daniel had er zes — telde één trui zesmaal mee in de
omzet. Dat bleef onzichtbaar zolang er op Marktplaats vrijwel nooit iets geboekt
werd; met verkopen uit de berichtenlijst zou het meteen zijn gaan tellen. Nu
draagt alleen de advertentie die op dat moment leefde de verkoop.

**Les:** als een platform iets niet zegt op de plek waar je kijkt, betekent dat
niet dat het het nergens zegt. De verkoper wist waar het stond; wij hadden het
hem nooit gevraagd.

### 01-09-2026 — Waar het Supabase-dataverkeer vandaan kwam

Daniel vroeg of Supabase Pro nog nodig was, of dat hij onder de 1 GB opslag zou
blijven. Nagemeten: opslag 0,642 GB van 1 GB, database 108,9 MB van 500 MB —
allebei ruim binnen het gratis plan. Het dataverkeer niet: 2,174 GB in
anderhalve dag, bij zeven actieve gebruikers en 320.843 API-verzoeken per etmaal.

Dat verkeer kwam niet van bezoekers maar van ons eigen dashboard. Elke 15
seconden haalde het scherm de HELE catalogus opnieuw op. Op het grootste account
(5.533 items) is dat 28 pagina's van een halve MB — 11,8 MB — plus 2,87 MB
advertenties: samen zo'n negentig opvragingen per ronde, vier rondes per minuut,
ruim 3 GB per uur dat het tabblad openstond. Van die 11,8 MB was 41% de
foto-adressen en 25% de volledige advertentieteksten van alle 5.533 artikelen,
elke 15 seconden opnieuw, terwijl het overzicht die niet toont.

Daarbovenop werd bij élk verzoek het inlogbewijs apart bij Supabase nagevraagd:
61.030 keer in een etmaal, altijd dezelfde vraag met hetzelfde antwoord.

Vier ingrepen:

1. `/api/items/sync` geeft alleen wat er sinds een tijdstempel is veranderd,
   plus het totaal aantal items. De tikkende ronde gebruikt die; elke ronde na
   een handeling haalt nog gewoon alles op.
2. `updated_at` op items wordt nu centraal gestempeld in `backend/database.py`.
   Er staat geen trigger op de tabel — de kolom stond bij vrijwel elke rij nog
   op het tijdstip van aanmaken — en tweehonderd schrijfplekken los omzetten is
   vragen om die ene vergeten plek.
3. Het inlogbewijs wordt een minuut onthouden (`backend/api/deps.py`), gehasht.
   Bij wachtwoord- of e-mailwijziging meteen vergeten.
4. De advertentielijst hoogstens één keer per minuut, de activiteitsvraag elke
   20 seconden in plaats van elke 4 zolang er niets in de rij staat, en
   `relist-status` laat de database filteren in plaats van alle create-opdrachten
   op te halen.

**Les, breder dan deze meter:** dit is de tweede keer dat de verkeersmeter vol
liep door onze eigen lussen (zie 31-08-2026, het project stond op slot bij 437%).
Beide keren was de oorzaak dezelfde vorm: een ronde die met een vaste tik draait
en élke keer de volledige waarheid ophaalt in plaats van het verschil. Een tik
die niets kost bij tien items kost bij vijfduizend het duizendvoudige — de prijs
van zo'n ronde hoort mee te groeien met wat er veranderd is, niet met wat er ís.


### 01-09-2026 — De drie dingen uit het gesprek met Egbert (Papa's Plectrums)

Daniel belde met Egbert. Drie klachten, alle drie dezelfde soort: iets dat bij
honderd artikelen niet opvalt en bij zijn 5.533 een muur wordt.

**1. Het overzicht laadde eindeloos, of gaf 502.** Nagemeten op zijn echte
gegevens, niet geschat. De aanroep die het scherm opgaf was `/api/listings/`:
17,9 seconden. Die haalde eerst alle item-id's op, hakte ze in brokken van 200,
stelde per brok een vraag — en deed die hele ronde daarna nóg eens om bij elke
advertentie de titel op te zoeken. Ruim zeventig vragen achter elkaar binnen één
verzoek. Postgres kent de band tussen advertentie en artikel al (de sleutel
`listings_item_id_fkey`), dus dat kan in één gekoppelde vraag: **14,6 → 2,0
seconden**, dezelfde rijen, dezelfde velden (gecontroleerd op zijn echte
voorraad, rij voor rij). De oude weg blijft als vangnet staan voor het geval die
sleutel ooit verdwijnt.

De catalogus komt nu ook in pagina's van 1.000 in plaats van 200 (29 → 7 vragen,
5,9 → 2,9s), en tijdens de eerste lading staat er "Loading your items… 3.000
loaded so far" in plaats van een leeg scherm.

**Correctie op wat hier eerst stond.** Ik schreef dat de catalogus
ongecomprimeerd over de lijn ging en dat de nieuwe gzip-middleware dat van
13,4 MB naar 1,53 MB bracht — negen tiende winst voor de verkoper. Dat klopt
niet, en het is nagemeten: `/health` is 437 bytes en komt van de live site
gzipped terug, terwijl onze eigen middleware pas vanaf 1.024 bytes inpakt.
**Cloudflare perst het er aan de rand al in, en deed dat dus ook vóór vandaag.**
Egberts browser kreeg de gegevens al ingepakt binnen.

De middleware blijft staan en is nuttig — hij scheelt op de weg Railway →
Cloudflare, en dus in ons eigen dataverkeer — maar hij is NIET waarom Egberts
scherm sneller opent. Dat is de gekoppelde vraag hierboven (14,6 → 2,0s) en het
aantal opvragingen (29 → 7).

**Les:** "de server stuurt het onverpakt" is een aanname over een laag die je
niet zelf beheert. Eén verzoek onder je eigen ondergrens verraadt wie het
werkelijk doet — dat had vóór de meting gemoeten, niet erna.

**2. De import meldde "alles opgehaald" terwijl prijs of tekst ontbrak.**
Marktplaats levert die bij een zakelijke (Admarkt) import niet mee; ze staan
alleen op de openbare advertentie. De server haalt ze sinds 29-08 vanzelf op,
elk kwartier één verkoper — maar die ronde selecteerde **alleen op lege
omschrijvingen**. Wie de tekst wél had en de prijs niet, kwam dus nooit aan de
beurt. Gemeten op de echte database: één account met 185 zulke artikelen die
daardoor nooit zijn aangeraakt. Prijs telt nu mee.

Verder maakt de import het nu zelf af: na afloop vier ophaalrondes, en de
slotmelding noemt wat er dan nog leeg is in plaats van "✅ Import successful" te
zeggen over een halve voorraad. Egbert zelf staat inmiddels op 12 items zonder
prijs en 11 zonder tekst van de 5.533 — zijn honderd tot tweehonderd zijn dus al
weggewerkt door de automatische ronde.

**3. Hij draaide 1.0.258 terwijl de Web Store op 1.0.279 stond.** De harde
ondergrens (1.0.244) blokkeert alleen wat aantoonbaar niet kán werken; alles
daarboven kreeg groen "Extension active", hoeveel versies achter ook. Dat is
dezelfde val als bij Jaap in augustus, één laag hoger.

Er is nu een tweede, zachte grens: wat er op dít moment in de Chrome Web Store
staat. Die vragen we op bij dezelfde bron die Chrome zelf gebruikt — de
update-doorverwijzing van Google draagt de versie in de bestandsnaam
(`..._1_0_279_0.crx`). We halen de crx niet op, alleen de kopregel; hoogstens
één keer per uur, en komt er niets terug, dan verandert er niets aan het scherm.
Loopt hij achter maar boven de ondergrens: een gele balk die hij weg kan
klikken, plus "v1.0.258 — v1.0.279 available" in de zijbalk.

**Les:** een ondergrens die met de hand meebeweegt, beweegt niet mee. De vraag
"is dit de nieuwste?" heeft maar één eerlijke bron, en dat is de winkel zelf.

### 01-09-2026 — De punten uit de call met Budgetheld

Vier storingen en één wens. Punt 2 bleek diezelfde ochtend al gerepareerd in de
Egbert-ronde; de andere drie hadden alle drie dezelfde vorm: **iets dat zwijgt
waar het had moeten klagen.**

**1. "Extension not detected" bij mensen die hem wél hadden.** Het dashboard
stuurde precies één ping naar de extensie en gaf er 2,5 seconde later een
oordeel over. Dat antwoord moet drie horden nemen die geen van alle binnen 2,5
seconde hoeven te passen: het bruggetje (`content/webapp_sync.js`) draait op
`document_idle` en is op een zwaar dashboard later dan de ping; het antwoord komt
pas na twéé heen-en-weertjes met de service worker; en die worker moet in MV3
eerst koud opstarten. Eén trage start = permanent rood, mét een blokkerend
installatievenster over het scherm van iemand die alles al goed had staan.
Nu: vijf pogingen over ~8,8 seconde vóór het oordeel valt, en daarna elke halve
minuut nog een stille controle, zodat installeren of inloggen in een ander
tabblad vanzelf wordt opgemerkt. "Re-check" zet de status ook echt terug op
"aan het kijken" — dat deed die knop eerder niet.

**2. Halve import (prijs/omschrijving leeg).** Zelfde melding als Egbert, en
dezelfde oorzaak: de automatische aanvulronde selecteerde alleen op lege
omschrijvingen, dus wie alleen de prijs miste kwam nooit aan de beurt. Gerepareerd
in commit ae3a196 (zie de vorige notitie). Niets extra's aan gedaan.

**3. De categorie sprong terug naar "Clothing & Shoes".** In `CATEGORIES` staan
68 audio-, tv- en fotocategorieën (luidsprekers, koptelefoons, platenspelers,
camera's) — compleet, mét Marktplaats-nummers in `background.js`, eBay-vertaling
in `ebay.py` en Vinted-hints in `vinted.js`. Alleen ontbrak "audio" in twee
plekken in het scherm: de keuzelijst *Item type* en `NON_CLOTHING_PREFIXES`.
Gevolg: die 68 categorieën waren met de hand niet te kiezen, en een geïmporteerd
artikel dat er wél in stond werd bij openen teruggezet op kleding — waarna
opslaan de echte categorie overschreef. Dat is precies wat zij zagen.
Toegevoegd, plus een vangnet: een opgeslagen categorie die wij niet kennen
blijft nu gewoon staan (`Current: …`) in plaats van weggegooid te worden — zelfde
aanpak als bij maat en de eBay-categorie.

**Les:** een lijst op twee plekken onderhouden gaat een keer mis. De test
(`tests/budgetheld-fixes-test.js`) loopt nu élke groep in `CATEGORIES` langs en
eist dat hij heen én terug hetzelfde item-type oplevert.

**4. Groen vinkje bij een advertentie die niet op Vinted stond.** De klant was
niet ingelogd op Vinted. Uitgelogd geeft Vinted op `/items/new` gewoon een
pagina terug — geen 401, geen doorverwijzing die wij herkennen. Het invulscript
liep dan over een formulier dat er niet was: elke stap mislukt stil (`step()`
logt en gaat door), en de eindcontrole klaagde óók niet, want die kijkt of een
veld leeg is — en een veld dat er niet ís, is niet leeg. Daarna was elk
`/items/{cijfers}` in de adresbalk genoeg om af te melden als geplaatst.
Twee sloten erop: de achtergrond vraagt vóór het openen van het tabblad aan
Vinted zelf of deze browser is ingelogd (`/api/v2/users/current`, met de eigen
cookies) en meldt de opdracht anders af als mislukt mét wat er moet gebeuren;
en het invulscript stopt als de titelbalk van het formulier er niet staat.
Kunnen we het niet vaststellen (netwerk, endpoint veranderd), dan gaat het werk
gewoon door — een onzekere controle mag geen advertentie tegenhouden.

**Les:** "geen klacht" is geen bewijs van slagen. Een controle die alleen kijkt
of een veld leeg is, keurt een leeg formulier goed.

**5. Shopify-import (wens, niet gebouwd).** Budgetheld doet voorraadbeheer in
Shopify en verkoopt op Marktplaats. Directe import vanuit Shopify staat op de
lijst voor later — er is al een Shopify-koppeling via een zelfgemaakte sleutel
(zie `shopify_orders.py`), dus de weg ernaartoe bestaat; wat ontbreekt is de
import van producten naar items. Bewust niet meegenomen in deze ronde.

Extensie 1.0.280 — moet naar de Chrome Web Store voordat punt 4 bij klanten werkt.

### 01-09-2026 — Naderhand: het groene vinkje had een andere oorzaak dan gedacht

Daniel vroeg om hogere zekerheid. Dat betekende: de aannames onder de reparatie
hierboven omzetten in metingen. Twee daarvan hielden stand, één niet.

**Gemeten, klopt:** uitgelogd geeft Vinted **401** op `/api/v2/users/current`
(zowel .nl als .com, met `invalid_authentication_token`). De inlogcontrole staat
dus op vaste grond.

**Gemeten, en dit veranderde de diagnose:** uitgelogd geeft `/items/new` géén
fout maar **HTTP 200**, met een doorverwijzing naar
`/member/register/select_type?ref_url=%2Fitems%2Fnew`. Op die pagina staat geen
enkel formulierveld (`title--input` komt nul keer voor). Ons invulscript draait
daar niet eens — de manifest-patronen dekken `/items/*`, niet `/member/*`. De
opdracht kón dus niet via het invulscript groen worden.

Waar het vinkje wél vandaan kwam: `chrome.tabs.onUpdated` neemt élk
advertentie-adres dat in het werk-tabblad verschijnt voor "onze zojuist
geplaatste advertentie". De verkoper staat op een registratiepagina waar niets te
doen is, het tabblad blijft drie minuten open, hij gaat klikken — en de eerste
advertentie die hij opent (`/items/12345-een-slug`, van een wildvreemde) werd
afgemeld als de zijne. Groen vinkje bij andermans advertentie, en een latere
verwijdering zou naar díé advertentie wijzen.

Er zit nu een eigendomscontrole voor die afmelding. **De grens ligt bewust bij
"is deze browser ingelogd", niet bij "staat hij in de kast":** Vinted zet een
nieuwe advertentie pas na een minuut of twee in de kast (daarom polst
`resolveCreatedVintedItem` 90 seconden), dus "nog niet gevonden" mag nooit "niet
van jou" betekenen — dat zou een échte publicatie weggooien en bij de verkoper
terugkomen als een mogelijk dubbele advertentie. Uitgelogd is wél beslissend: wie
niet is ingelogd kan onmogelijk zojuist iets geplaatst hebben.

**Voor-en-na in een echte browser** (extensie-detectie, punt 1 hierboven). Beide
versies van `app.html` naast elkaar gedraaid met een nagebootste extensie die
pas na 6 seconden antwoordt — het gedrag van een koud opgestarte service worker:

| | pogingen | uitkomst |
|---|---|---|
| oud (4c66972) | 0 opgevangen; één ping op 400 ms, deadline 2,5 s | "Extension not detected" + blokkerend installatievenster |
| nieuw | 4 (765, 1697, 3888, 6751 ms) | "Extension active (v1.0.280)" |

Dat de oude versie nul pings opving is geen meetfout maar de tweede storing in
dezelfde zin: die ene ping vertrok vóórdat de luisteraar er was, en er kwam er
geen tweede. Precies wat er gebeurt als `content/webapp_sync.js` (document_idle)
later klaar is dan het dashboard.

**Les:** een plausibele oorzaak die de klacht verklaart is nog geen bewezen
oorzaak. Had ik het bij de inlogcontrole gelaten, dan had de klant nog steeds een
groen vinkje bij andermans advertentie kunnen krijgen — en had ik gezegd dat het
opgelost was.

Alle 68 audiocategorieën zijn nagelopen over de hele keten: Marktplaats-nummers,
eBay-vertaling en Vinted-hints staan er alle 68 bij. Er is dus niets half
gekoppeld.

### 01-09-2026 — Nagelopen: staan er verkeerde Vinted-nummers in de database?

Ja, één. En het uitzoeken legde een gat bloot in de reparatie van vanmiddag.

**Hoe ik het heb afgebakend.** Er staan 1.721 Vinted-advertenties in de database,
1.656 met een echt nummer. Die allemaal bij Vinted opvragen liep vast: boven zo'n
veertig snelle verzoeken knijpt Vinted af (eerste poging: 1.613 van de 1.656
onleesbaar — een meetfout, geen resultaat). Belangrijker was de inzicht dat het
ook niet hóéft: een nummer dat uit een **scan** komt is uit de eigen kast van de
verkoper gelezen en kan per definitie niet van een vreemde zijn. Alleen een
**geslaagde publicatie-opdracht** kan een verkeerd nummer opleveren, en dat zijn
er ooit 51 geweest. Die 51 rustig nagelopen (één voor één, 1,2s ertussen): 43
leesbaar, 8 bestaan niet meer bij Vinted, 0 onleesbaar.

**Uitkomst.** 18 leken af te wijken, maar 17 daarvan waren gewoon de vertaling —
onze titel is Nederlands, Vinted toont de vertaalde. Eén was echt:

> artikel **(1353) Dark Green Suitsupply Cardigan** droeg het nummer van
> **(1352) Navy Suitsupply Zip Vest** (9727012245). Beide van dezelfde verkoper.
> 1353's advertentie is geregistreerd om 08:34:50, 1352's eigen advertentie om
> 08:37:55 — drie minuten later.

Gevolg als het zo blijft staan: wordt 1353 ooit verwijderd of herplaatst, dan gaat
de advertentie van 1352 eraan. 1353 staat waarschijnlijk helemaal niet op Vinted.

**Het gat in de reparatie.** Mijn eigendomscontrole van vanmiddag vraagt "staat
deze advertentie in de kast van deze verkoper". Bij 1352/1353 is het antwoord
*ja* — het is zijn eigen advertentie, alleen de verkeerde. De controle had dit
dus doorgelaten. Er wordt nu ook op titel vergeleken, ruimhartig genoeg om
vertalingen en door Vinted afgekapte titels door te laten (getest), en met het
SKU-nummer als hardste bewijs: dat vertaalt niet mee.

**Les:** ik had de reparatie gebouwd op één waargenomen scenario (uitgelogd,
klikt op andermans advertentie) en de test daarop geschreven. Het énige geval dat
in de echte data voorkomt was een ánder scenario, dat er precies doorheen viel.
De data nalopen wás de test.

Verder: 8 advertenties staan bij ons op 'active' maar geven 404 bij Vinted. Dat
is een aparte, mildere onnauwkeurigheid (verwijderd zonder dat wij het merkten)
en niet in deze ronde aangepakt.

**Naderhand rechtgezet (01-09-2026).** Gebruiker 3bfbed2c is Daniel zelf, dus er
is géén klant geraakt — de enige verkeerde koppeling stond op het eigen account.

En weghalen bleek niet de goede reparatie. Vinted's openbare zoekpagina laat zien
dat (1353) Dark Green Suitsupply Cardigan gewoon online staat, onder nummer
**9727142603** (nagelopen: HTTP 200, exacte titel, `is_closed:false`). Het record
wees dus niet naar niets maar naar de buurman. Het nummer is gecorrigeerd in
plaats van gewist; had ik de rij verwijderd, dan was er bij een volgende
publicatie een dubbele advertentie ontstaan.

Nagemeten na de correctie: 1352 houdt zijn eigen nummer, en er staat geen nummer
meer dubbel behalve drie bekende gevallen — dat zijn dubbele kopieën van hetzelfde
artikel (identieke titel, identiek tijdstempel), het bestaande dubbelen-probleem,
geen verkeerde nummers.

**Les:** "dit record klopt niet" is nog geen "dit record moet weg". Eerst kijken
wat het hóórt te zijn.

**Die 8 alsnog nagekeken (01-09-2026).** Twee keer opgevraagd, alle acht bevestigd
weg bij Vinted. Maar er waren er maar **twee** echt fout: zes stonden al goed als
verkocht of verwijderd. De twee die op 'active' stonden (9067082034 Nike polo,
9657888362 Massimo Dutti polo) staan nu op **delisted** — bewust niet op 'sold',
want we weten dat ze eraf zijn, niet dat ze verkocht zijn, en dat verschil telt
mee in de omzetcijfers. Er stond geen werk meer voor ze in de rij.

Een volledige ronde over alle 1.656 is niet nodig: `backend/services/polling.py`
doet dit al uit zichzelf — oudste eerst, en na twee keer achter elkaar
niet-gevonden gaat een advertentie op delisted. Deze twee waren simpelweg nog niet
twee keer aan de beurt geweest. De boekhouding (`not_found_count`) is gelijkgezet
met wat die ronde zelf zou hebben opgeschreven.

## 01-09-2026 — "publiceren-mislukt": met voorrang doorgegeven, maar al gerepareerd

Met voorrang doorgegeven (amandahaas1979 + zilverwebsite.nl, storing sinds
30-08, MOET ZEKER wegens de serverfout). Nagelopen in plaats van blind
gerepareerd, en de vier gebundelde klachten — bedrijfsgegevens meegestuurd,
Vinted zet alles in kinderkleding, dubbele foto's, publiceerfout 500 — bleken
letterlijk dezelfde vier dingen die al op 30-08 zijn opgelost, onder twee
andere aantekeningen hierboven: "Waarom Amanda's serverfout nergens aankwam"
(de 500, opgelost met per-kanaal afscherming + leesherhaling in
`backend/database.py`) en "Amanda's vier meldingen van vandaag (extensie
1.0.273)" (kinderkleding, dubbele foto's, bedrijfsgegevens). Deze sleutel zelf
was na die reparaties nooit met `opgelost` afgesloten — vandaar dat hij als
nieuwe MOET ZEKER-storing terugkwam, hetzelfde boekhoudkundige mankement als
bij `marktplaats-niet-ingelogd-melding` op 30-08: de fix stond er, de
afmelding niet.

**Gecontroleerd, niet aangenomen.** Beide accounts opgevraagd in de tabel
`jobs` sinds 28-08: bij Amanda 284 opdrachten, bij Zilverwebsite 500, allebei
tot en met vandaag actief blijven publiceren. Geen van de foutmeldingen sinds
30-08 bevat een serverfout, een `RemoteProtocolError` of iets anders dat op de
oude 500 lijkt — alleen bekende, aparte problemen (lege velden, Chrome die
dichtklapt). De laatste 60 vastgelegde serverfouten (`server_fouten`) gaan
allemaal over een heel andere, wél nu actieve storing (`/api/items/sync`,
zie hieronder) en bevatten geen enkele treffer voor crosslist/publish/relist.
De extensieversie staat op 1.0.280, ruim boven de 1.0.273 van de reparatie.

Geen code gewijzigd. Teruggemeld als `opgelost`, met dezelfde uitleg als de
oorspronkelijke reparaties.

**Terzijde, een nieuwe en wél nu actieve storing gevonden tijdens het
uitzoeken (nog niet gerepareerd, staat niet bij deze sleutel):** de server
gooit op dit moment continu `GET /api/items/sync` fouten op:
`SyncRequestBuilder.select() got an unexpected keyword argument 'head'`
(`backend/api/items.py:160`, `db.table("items").select("id", count="exact",
head=True)`) — tientallen per uur, nog bezig op het moment van schrijven.
Niet meegenomen in deze ronde: dit is een andere sleutel, geen van beide
melders raakte deze route, en het rook naar een lopende wijziging van een
andere sessie op `backend/database.py` (herhaalde bestandsvergrendelingen
tijdens dit onderzoek wijzen op gelijktijdig werk daar). Verdient een eigen
blik zodra het zeker is dat er niemand meer in zit.

## 02-09-2026 — Toon (dejuistetoon): "alles blijft vaag en kan niets aanklikken"

Toon mailde Daniel een foto van zijn publiceervenster: elk kanaal grijs met
"MISSING: DESCRIPTION", alleen Vinted op groen. Geen knop die iets deed. Hij is
er dagen mee bezig geweest.

**Wat er echt aan de hand was.** Van zijn 1.024 geïmporteerde artikelen hadden er
**244 geen omschrijving**. Zonder omschrijving weigert het dashboard te
publiceren naar Marktplaats, 2dehands en Facebook — terecht, want die tekst is
verplicht — maar het venster bood daarna geen enkele uitweg. 768 artikelen waren
wél publiceerklaar, 24 misten alleen een categorie.

**De keten, elke schakel gemeten en niet beredeneerd.**

1. Vinted's kastoverzicht (`/api/v2/wardrobe/{id}/items`) geeft titel, prijs,
   foto's, merk en maat, maar géén omschrijving. Gecontroleerd: nul van de vijf.
2. Het detail-endpoint dat de extensie daarvoor gebruikte, `/api/v2/items/{id}`,
   is **dood**: 404, allebei de varianten, ook zonder inloggen. Vinted heeft het
   eruit gehaald. In Toons eigen scanlogboek staat het letterlijk:
   `9739740557(api404/pg429)`.
3. De openbare advertentiepagina `/items/{id}` heeft de tekst wél. Steekproef van
   acht die bij ons leeg stonden: **alle acht** hadden op Vinted gewoon een
   omschrijving van 51 tot 313 tekens. Het was dus geen ontbrekende data.
4. Maar Vinted knijpt af. Gemeten vanaf één adres:
   26 verzoeken op rij (0,5s ertussen) → 429. Daarna 30s pauze → nog 2 pagina's.
   60s pauze → 15 pagina's. 120s pauze → ook 15. Ruwweg **vijftien per minuut**,
   en dat is alles.
5. De scan vroeg er per keer **1.017** op — driekwart daarvan voor teksten die
   allang in het dashboard stonden — en verspilde er per advertentie ook nog twee
   aan het dode endpoint. Zijn drie scans van dezelfde kast leverden
   achtereenvolgens **52, 776 en 507** advertenties zonder tekst op. Dezelfde
   kast, alleen een leger budget.
6. En dan de schakel die het blijvend maakte: `_store_scan_results` schreef
   `description = row.get("description") or None`. Een afgeknepen scan wíste dus
   de tekst die een eerdere scan wél had gevonden. Bewijs uit zijn eigen
   gegevens: **271 kandidaten stonden zonder tekst terwijl het artikel dat eruit
   geïmporteerd was er wél een had** — die tekst kan alleen uit een eerdere scan
   komen, dus die 271 zijn achteraf gewist.

**Wat er is veranderd.**

- De server stuurt bij een Vinted-scan mee van welke advertenties hij de tekst al
  heeft (`tekst_bekend`, `imports._vinted_ids_met_tekst`). Bij Toon zakt dat van
  1.017 op te halen pagina's naar 52. Alleen nummers worden gelezen, nooit de
  teksten zelf — dat was de Supabase-verkeersles van 31-08.
- De extensie slaat die over, stopt met het dode endpoint zodra het één keer 404
  geeft, wacht bij een 429 dertig seconden in plaats van 1,2 seconde, en stopt
  na drie keer afknijpen met wat ze heeft in plaats van leeg door te vragen. De
  volgende scan pakt precies de rest op.
- Een scan mag nooit meer leeghalen wat hij niet zelf kon vinden
  (`jobs._rijke_velden`, apart gezet zodat de regel te testen is zonder scan).
- Het publiceervenster is geen doodlopende straat meer. Staat de advertentie nog
  op Vinted, dan is "Missing: description" een link die de tekst daar ophaalt.
  Kan dat niet, dan brengt hij naar het invulscherm.
- Nieuw: "Fill N from Vinted" naast de bestaande Marktplaats-knop, en
  `POST /api/items/fill-from-vinted` eronder (`services/vinted_enrich.py`,
  vier seconden tussen verzoeken — precies onder de gemeten grens).

**Toons account is rechtgezet.** 240 van de 244 teksten alsnog opgehaald met
`scripts/vul_vinted_teksten.py`. Vier niet: die Vinted-advertenties bestaan niet
meer, daar valt niets te halen. Nooit iets overschreven, alleen lege velden.

**Tweede probleem bij hem, apart en ook gerepareerd.** Van zijn 37 mislukte
plaatsingen zijn er 9 hetzelfde geval: een maat of kleur die wij bewaren maar die
Marktplaats in díe categorie niet aanbiedt. "Universeel" bij heren shorts —
**zeven keer geprobeerd, zeven keer mislukt**, op beide kanalen. "bordeaux" bij
wanddecoraties. Het verplichte veld bleef leeg en dan komt de advertentie er
niet. Er is nu een terugval (dezelfde aanpak als `CONDITION_CANDIDATES`, die dit
al maanden doet): staat onze waarde niet in de lijst, dan wordt het
dichtstbijzijnde gekozen dat er wél in staat, uit de lijst zelf gelezen. En de
foutmelding noemt voortaan wélke waarde niet paste en wat het veld wél aanbiedt,
in plaats van alleen "size was left empty".

**Wat ik NIET heb opgelost, met zoveel woorden.** 17 van zijn 37 mislukkingen zijn
"Extension timed out … no response after 3 minutes", plus 4 keer een tabblad of
Chrome die dichtging. Die zijn van hier niet te herleiden: daarvoor moet je in
zijn browser meekijken terwijl het gebeurt. Ze vallen op 01-09 in twee dichte
bosjes (19:22–19:40 acht stuks), wat past bij werken in een venster dat naar de
achtergrond gaat — bekend patroon, zie de aantekening over verborgen tabbladen —
maar dat is een vermoeden en geen meting, en zo staat het hier ook. Zijn
2dehands-inlog is verlopen (2x foutcode 401); dat kan alleen hij zelf herstellen.

**Les.** "De data ontbreekt" was hier drie keer achter elkaar het verkeerde
antwoord. De tekst stond er gewoon; het adres was verhuisd, het budget was op, en
wat er wél binnenkwam werd door de volgende ronde gewist. Een scan die elke keer
alles opnieuw ophaalt lijkt grondig en is in werkelijkheid de reden dat hij niets
binnenhaalt.

## 02-09-2026 — "verkeerde-categorie-toegewezen": opnieuw uitgezocht, nog steeds al gerepareerd

Met voorrang doorgegeven (zilverwebsite.nl + amandahaas1979, ⚠ MOET ZEKER,
laatst gemeld 30-08 14:57). Dit is dezelfde sleutel die op 30-08 al werd
onderzocht (zie hierboven, "geen nieuwe reparatie, wel uitgezocht") en die dag
ook als `opgelost` is teruggemeld aan de mailagent, met bericht naar beide
melders. Vandaag stond hij toch weer als open in `mail_analyse.py bugs`.

Niet blind opnieuw gerepareerd, eerst nagelopen of de fix van 30-08 er nog
staat en of hij houdt:

- `getMpSyiUrl` in `extension/background.js` (regel 702 e.v.) leest bij een
  verversing nog steeds eerst de categorie van de bestaande advertentie zelf
  af, vóór hij hem weghaalt — de code van 30-08 staat er ongewijzigd.
- Kan er geen categorie bepaald worden, dan gooit de extensie
  `CategoryUnresolvedError` (regel 642/751) met een duidelijke tekst ("Set a
  category on the item and publish again"). Die wordt op regel 1855 opgevangen
  en als nette jobfout gemeld — nooit een gok, nooit een onbehandelde crash.
  (In de notitie van 30-08 stond dit aangeduid als "CategoryUnresolvedError/422";
  het is een foutklasse in de extensie, geen server-statuscode — vandaar dat
  zoeken in de backend-code er niets van vond.)
- Opdrachtenlogboek nagekeken voor beide accounts (Jaap `26cf5471…`, Amanda
  `0b28c1ce…`) vanaf 30-08 14:57 tot nu: geen enkele opdracht met een categorie-
  gerelateerde fout of een 500 Internal Server Error. Wat er wél misging in die
  periode zijn andere, al bekende dingen (lege kleur/maat/prijsvelden, Chrome
  die dichtging, een timeout) — niets van deze sleutel.

**Vermoedelijke oorzaak van het spontaan heropenen:** het opgeslagen signaal had
`heropend_op` gelijk aan `eerst` (allebei 17-08), terwijl de reparatie van 30-08
er logisch tussenin zit. Dat past bij een bericht dat een tweede keer als
"nieuw" wordt gezien door `mail_analyse.py` (bijvoorbeeld omdat het uit de
bewaarde `alles`-lijst is gevallen, die maar een beperkt aantal berichten
bewaart) en daardoor een al opgeloste storing met zijn oude datum heropent. Niet
verder uitgezocht binnen deze storing, want dat is een apart mankement in de
mailagent zelf, geen bug in het publiceren. Verdient een eigen blik als het
patroon zich herhaalt.

Geen code gewijzigd. Opnieuw teruggemeld als `opgelost` aan beide melders.

## 02-09-2026 — Stripe-billing gecontroleerd, dubbel product gearchiveerd

Controle op verzoek van Daniel: klopt het dat er één abonnement is en betalen de
juiste mensen.

Bevindingen: in de productcatalogus stonden twee actieve producten van 19,99 per
maand, allebei "Omnivaleur Pro". Alle abonnementen hingen aan prod_UnKYIeWID9kOrs;
prod_UnKVdJAsnrpZ4Z had nul abonnees en nul omzet. Dat tweede product is met
akkoord van Daniel gearchiveerd, zodat het nooit per ongeluk gekozen kan worden.

Betalende klanten op dit moment: albinmooi1009 (19,99 binnen), zilverwebsite
(19,99 via SEPA-incasso, valt 4 september binnen) en papas-plectrums (14,99 met
aanmeldkorting, geld kwam 2 september binnen). Daniels eigen account stopt 8
september. Zilverwebsite had 24 augustus kort twee abonnementen; het tweede is
29 augustus opgezegd en terugbetaald.

De proefperiode van papas-plectrums die op 20 augustus verlengd werd tot 19
september is door Daniel zelf gezet. Geen storing in de code.

Gebruikerslijst tegen Stripe gelegd: 41 accounts, 3 betalend, 9 in proef, 29
verlopen. Niemand heeft de gratis-voor-altijd status (trial_ends_at 2099) uit de
comp-knop. Er gebruikt dus niemand de app gratis buiten een echte proefperiode om.

## 03-09-2026 — Toon (dejuistetoon): drie klachten, twee echte oorzaken

Daniel gaf Toons WhatsApp door met de opdracht het soepel te laten lopen. Alles
hieronder is gemeten aan zijn eigen account (96e30080…), niet geredeneerd.

**1. "Springt elke keer terug naar pagina 1" en "na invoeren naar het 1ste
artikel".** Eén oorzaak: de ronde in `loadAll()` die elke 15 seconden bijwerkt
(en nog eens zodra het tabblad naar voren komt) riep `applyFilters()` aan zonder
argument, en dat zet de lijst terug op bladzijde 1. Met 1.024 artikelen zijn dat
21 bladzijden, dus wie verder bladerde had telkens vijftien seconden. Staat nu op
`applyFilters(false)`; alleen een echte keuze van hemzelf (filter, zoekterm,
sortering, tabblad) zet hem nog terug naar 1.

**2. "Regelmatig valt het beeldscherm totaal weg".** Toon werkt op een Chromebook
— afgelezen aan zijn eigen verbinding met de server: `CrOS x86_64, Chrome 151`.
Dezelfde ronde verving elke vijftien seconden de hele tabel, dus vijftig rijen met
vijftig foto's, en dat zijn de originelen uit de import: gemeten op zijn eigen
artikelen gemiddeld 450 kB per stuk. 22 MB opnieuw ophalen en uitpakken, vier keer
per minuut, op een Chromebook. Twee dingen veranderd: de tabel wordt alleen nog
hertekend als de inhoud echt anders is, en elke miniatuur staat nu op
`loading="lazy"` met `decoding="async"` en een vaste maat.

**3. Twee artikelen die bleven mislukken — veel groter dan twee.** De klacht ging
over "Vrolijke granny square" (kleur *divers*) en een 2dehands-plaatsing. In zijn
logboek staan sinds 01-09 zeven mislukkingen op een leeg Kleur- of Maat-veld. De
echte omvang bleek pas bij tellen: zijn kast bevat 59 verschillende kleurwaarden,
opgeschreven zoals een mens dat doet — "bruine" (41x), "zwarte" (20x), "rode"
(16x), "groene" (15x), "crème" (13x), "witte" (10x), "lichtblauw", "olijfgroene",
"Beige bruin", "divers". Marktplaats biedt alleen de kale grondvorm aan. De oude
vertaaltabel ging enkel van Engels naar Nederlands, dus die woorden matchten op
niets en het verplichte veld bleef leeg — en dan komt de advertentie er niet
(gemeten 21-08-2026: knop doet stil niets).

Gemeten met de échte code van 1.0.280, de versie die hij draaide toen het misging:
**31 van de 59 kleurwaarden lieten het veld leeg, goed voor 175 van zijn 1.024
artikelen.** Na de reparatie: nul. De test in `tests/kleur-en-maat-terugval-test.js`
draait beide versies tegen die 59 echte waarden, zodat de voor-en-na-proef er
staat en niet alleen de belofte.

**Wat dit vandaag nog voorkomt.** Er staan 50 opdrachten klaar: 24 herplaatsingen
(eerst weghalen, dan opnieuw plaatsen) op Marktplaats. Drie daarvan hebben een
kleur die de oude code niet kon plaatsen (*rode*, *zwarte*, *crème*). Was de
verwijdering doorgegaan en de plaatsing daarna gestrand op een leeg kleurveld, dan
was die advertentie weg geweest.

**Niet gerepareerd, met zoveel woorden.**
- Tien van zijn 23 mislukkingen sinds 01-09 zijn "Extension timed out — no
  response after 3 minutes", plus één tabblad dat dichtging. Dat past bij een
  Chromebook die het werk-tabblad wegzet, maar dat is van hier niet te bewijzen;
  daarvoor moet je meekijken terwijl het gebeurt. De twee reparaties hierboven
  halen wel druk van datzelfde geheugen.
- Zijn 2dehands-inlog is verlopen: twee keer foutcode 401 op zijn
  advertentieoverzicht, laatst 02-09 15:13. Alleen hij kan dat herstellen door op
  2dehands opnieuw in te loggen. Zijn wachtwoord staat in de WhatsApp; daar is
  niets mee gedaan en dat hoort ook niet.
- "Voor mij ook beter als de tekst in het Nederland zou kunnen." Het dashboard is
  bewust volledig Engels en dat wordt afgedwongen door
  `tests/test_meldingen_engels.py`. Nederlands maken is een productbeslissing van
  Daniel en een apart project, geen reparatie. Niet aan begonnen.
- "Vanaf onze eigen webshop doorplaatsen" is een wens, geen storing. Genoteerd.

**Wat geen storing bleek.** Toon ziet 1.128 artikelen op Vinted en 1.008 in het
dashboard. Zijn laatste Vinted-scan (31-08) vond 1.130 advertenties; daarvan
werden er 1.025 kandidaat en 1.024 artikel. Het verschil zijn de advertenties die
Vinted als gesloten (verkocht of beëindigd) markeert — die telt Vinted wel mee in
het totaal op zijn profiel en wij bewust niet. Wel staan er nog 37 Vinted-,
501 2dehands- en 286 Marktplaats-kandidaten op zijn bevestiging te wachten in het
importscherm.

Extensie op 1.0.282, zip gebouwd. Zolang die niet in de Chrome Web Store staat,
draait Toon de oude en blijft het kleurprobleem bestaan — dat is de laatste stap
en die kan alleen Daniel zetten.

## 03-09-2026 (vervolg) — doorgemeten na "is dit alles wat je kan doen?"

Daniel vroeg terecht door op de 85% van hierboven. Vijf dingen die ik nog kon
meten in plaats van aannemen, en één correctie op mezelf.

**De reparatie staat aantoonbaar live.** `omnivaleur.nl/app.html` opgehaald en
nagekeken: de vaste bladzijde, de stempel op de tabel en de trage miniaturen
zitten er alle drie in. Dat was eerder aangenomen op grond van een geslaagde push.

**Correctie op mijn eigen getal.** Ik schreef "175 van de 1.024 artikelen". Bij
narekenen zijn het er 171, en belangrijker: dat is een bovengrens, geen aantal
storingen. Marktplaats vraagt lang niet in elke categorie om een kleur. Van 35
opgehaalde live advertenties van Toon had er precies één soort een kleurveld
(`plaidsKleur`). Wat vaststaat: 692 van zijn artikelen dragen een kleur, 171
daarvan in een schrijfwijze die de oude code niet kon plaatsen, en 15 daarvan
staan in "plaids en woondekens" — de enige categorie waarvan ik bewezen heb dat
ze om een kleur vraagt. Van de andere categorieën weet ik het niet en dat zeg ik
er dan ook bij.

**Een aanname die niet klopte.** Mijn hele kleurreparatie mikte op de namen uit
onze eigen vertaaltabel, met "Multicolour" als verzamelnaam. Op zijn eigen live
advertentie in "plaids en woondekens" staat `plaidsKleur: "Meerkleurig"`. Daar
bestaat "Multicolour" dus niet, en de granny square met kleur *divers* zou ook na
mijn reparatie zijn blijven hangen. Nu gecorrigeerd: de grondvorm is
"Meerkleurig" en de extensie gaat bij een verzamelnaam meerdere schrijfwijzen
langs (Meerkleurig, Multicolour, Veelkleurig, Gemengd, Overige, Overig, Anders,
Divers) en kiest wat er in díe lijst echt in staat.

**Nu werkt het vandaag, niet pas na de Web Store.** Dit was het grootste gat: een
extensiereparatie bereikt een verkoper pas nadat Google hem heeft goedgekeurd en
Chrome hem heeft opgehaald — bij Egbert duurde dat drie weken. Daarom zet de
server de kleur nu goed op het moment dat de opdracht de deur uit gaat
(`_zet_kleur_goed` in `backend/api/jobs.py`, met `backend/services/kleur.py`).
Dat geldt ook voor de 24 herplaatsingen die nu klaarstaan, en dus ook op de kopie
die Toon vandaag draait. Alleen als we de kleur herkennen; een onbekend woord
blijft staan zoals hij het schreef. Vinted heeft een eigen lijst en blijft buiten
schot.

Omdat dezelfde logica nu op twee plekken staat (Python op de server, JavaScript in
de extensie) leest `tests/test_kleur_normalisatie.py` de tabellen uit shared.js en
legt ze naast die in Python. Lopen ze uit elkaar, dan valt de test om.

**Maten er alsnog bij.** Die had ik laten liggen. Vinted schrijft kindermaten als
"10 jaar / 140 cm", Marktplaats biedt "Maat 140" aan, en geen van beide helften
komt in die optie voor. Vijftien van Toons artikelen hebben zo'n maat. De extensie
probeert nu ook het kale getal, met opzet als laatste en alleen uit "<getal> cm"
of "<getal> jaar" — anders zou "40 x 40 cm" (een kussen) op "Maat 40" in een
kledinglijst uitkomen. Ook dat staat met een voor-en-na-proef in de test.

Suite: 803 tests groen (was 763). Extensie op 1.0.283.

**Wat nu nog buiten mijn bereik ligt, en dus als actiepunt bij Daniel:** de Web
Store-goedkeuring, Toons 2dehands-inlog, de keuze of het dashboard Nederlands
wordt, en meekijken in zijn browser tijdens een tijdsoverschrijding.

## 03-09-2026 — Dashboard blijft voorlopig Engels

Toon (dejuistetoon) vroeg om een Nederlandse interface. Besluit van Daniel: het
komt er, maar nu nog niet. Reden om het niet even snel te doen: er zit geen
taalschakelaar in. Elke zin staat hard in de pagina. Gemeten op 03-09-2026:
785 verschillende zinnen in `frontend/app.html` (ongeveer 5.800 woorden), plus
483 op de andere pagina's (index, marketplaces, login, wachtwoord), plus alle
foutteksten die de extensie doorstuurt. `tests/test_meldingen_engels.py` bewaakt
op dit moment juist het omgekeerde: alles wat de gebruiker ziet moet Engels zijn.

Wie dit oppakt: eerst de schakelaar bouwen (een tabel met sleutels, niet zoeken
en vervangen), dan pas vertalen, en die test omzetten naar "beide talen compleet".
Half vertaald is slechter dan Engels: een half-Nederlandse melding leest als een
storing. Zie ook de klantmail van 03-09-2026 aan Toon.

## 03-09-2026 — Egbert liep vast op 2dehands, en waarom dat niemand vertelde

Egbert Brouwer (papas-plectrums, 5.533 artikelen) mailde drie dingen op één dag,
eindigend met "ik loop compleet vast hier, kan niet doen wat ik wil doen".

**Wat er echt aan de hand was, gemeten in het opdrachtenlogboek.** Van zijn 305
opdrachten voor 2dehands is er nooit één geslaagd. 26 werden er afgebroken door
de bewaker van de extensie na exact drie minuten, telkens zonder één teken van
leven uit het tabblad, en 279 stonden er nog achter. Zijn Marktplaats-opdrachten
uit dezelfde ronde liepen wél door (15 geplaatst), en bij andere verkopers
slaagde 2dehands in dezelfde periode 97 keer. De categorienummers kloppen ook:
728/748 geeft via hun eigen zoek-API op allebei de sites "Muziek en Instrumenten
> Gitaren | Elektrisch". Het verschil zit dus niet in onze code, niet in de
categorie en niet in de browser, maar in de site: www.2dehands.be antwoordt op
het plaatsadres met HTTP 401 (twaalf bytes platte tekst, geen formulier) zolang
je daar niet bent ingelogd. Op zo'n pagina draait ons invulscript helemaal niet,
dus meldt niemand iets terug en loopt de bewaker af.

**Marktplaats.nl en 2dehands.be zijn twee aparte sites met twee aparte
inlogsessies.** Dat is nergens uitgelegd, en de foutmelding zei "de pagina is
misschien veranderd" — precies de verkeerde kant op. De extensie doet met opzet
één opdracht tegelijk, dus 279 wachtende opdrachten van drie en een halve minuut
zijn zestien uur waarin hij verder niets kon publiceren.

**Wat er is veranderd.** De bewaker maakt nu onderscheid tussen "het formulier
liep vast" en "het formulier is nooit opengegaan": het invulscript zet een
stempel zodra het zich meldt. Ging het formulier niet open, dan zegt de melding
dat, noemt de site, en legt uit dat het twee aparte logins zijn. Drie keer op rij
op een kanaal dat bij deze verkoper nog nooit heeft gewerkt, en de rest van de
wachtrij wordt teruggenomen in plaats van zestien uur herhaald.

Die rem staat op de SERVER en niet alleen in de extensie, om dezelfde reden als
bij de kleurreparatie van gisteren: een extensiereparatie bereikt een verkoper
pas nadat Google hem heeft goedgekeurd, en bij Egbert duurde dat eerder drie
weken. Zijn 276 vastzittende opdrachten zijn vandaag met de hand teruggenomen,
met de reden op elke advertentierij.

**Twee kleinere dingen uit dezelfde mail.**

Alles selecteren wat aan een filter voldoet kon niet. Het vinkje in de kop pakte
alleen de getekende bladzijde van vijftig rijen; zijn zoekopdracht "miniatuur"
levert er 434 op. Hij kwam niet verder dan 150 en schreef dat ook zo op. Er staat
nu een link in de balk: "Select all 434 matching". Het paginaspringen dat het
erger maakte was vanochtend al gerepareerd (zie de notitie over Toon).

De knop "Fill from Marktplaats" telde merk en maat mee als ontbrekend. Geen
enkele miniatuurgitaar heeft een maat en vrijwel geen een merk, dus stond er
eeuwig "Fill 5533 from Marktplaats" terwijl er 11 artikelen echt iets misten.
Hij las dat als ruis en schreef "ik zie geen knop". Merk en maat tellen nu alleen
mee in de takken waar Marktplaats er ook om vraagt. Zonder prijs staat er nu
overigens niets meer: 0 van 5.533.

Suite: 811 tests groen (was 803). Extensie op 1.0.284.

**Openstaand bij Daniel:** Egbert moet zelf op 2dehands.be inloggen (of besluiten
dat hij België overslaat), en 1.0.284 moet nog door de Web Store. De serverkant
werkt vandaag al, ook op de kopie die nu bij hem draait.

## 03-09-2026 — Hoe een klantmail klinkt (voor iedereen die er een schrijft)

Daniel keurde een conceptmail aan Egbert af. Die was 250 woorden, opende met een
compliment over hoe goed de klant het had opgeschreven, en legde per punt eerst
uit wat er fout was gegaan voordat er stond wat de klant er nu aan heeft.
Precies andersom dus.

Zijn correctie, letterlijk: "zo kort en compact mogelijk, trek niet teveel het
boetekleed aan, werk vanuit het perspectief van de klant: zo compact en duidelijk
mogelijk wat er gebeurd is en hoe dit zijn probleem oplost. Dat is het
belangrijkste. Niet teveel BS, niet teveel slijmen, hou het menselijk vriendelijk
en duidelijk."

De vorm die hij zelf gebruikt, en die vanaf nu geldt:

* Hooguit 200 woorden. Elke zin die niets voor de klant verandert, gaat eruit.
* Eén menselijke openingszin die erkent wat hij merkte, plus dat je hebt gekeken.
  Eén keer. Geen excuusalinea, geen complimenten.
* Per punt: onderwerp, dubbele punt, dan in een of twee zinnen het gevolg dat hij
  merkt. De oorzaak mag hooguit in een halve zin mee.
* Concreet wat hij kan doen: waar hij klikt, wat hij intypt, wat hij ziet.
* Afsluiten met een korte vraag of vervolgstap, niet met een samenvatting.
* Geen techniek, geen bestandsnamen, geen versienummers tenzij hij er zelf iets
  mee moet.

**Dit is geen richtlijn maar code.** De regels staan in
`TOON_KORT_EN_MENSELIJK` in `scripts/leadgen_mail.py` en hangen daar aan
`_KLANT_REGELS` en in `scripts/mail_analyse.py` aan `HERSTELBERICHT_REGELS`.
Elk concept dat de mailagent schrijft krijgt ze dus mee. Schrijf je met de hand
een mail namens Daniel, hou dan dezelfde vorm aan. Zie ook
`docs/kennisbank.md`, les "Klantmail: kort en menselijk".

Voor de tweede ontwikkelaar: neem dit meteen mee, ook in wat je zelf voor hem
opstelt. Het is de tweede keer dat dezelfde correctie langskomt (eerder al
"mails kort houden" en "meer empathie"), dus hij staat nu op twee plekken vast:
in de prompts en hier.

## 03-09-2026 — "automatisch-verversen-mislukt-popup": met voorrang doorgegeven, maar al gerepareerd

Met voorrang doorgegeven (info@zilverwebsite.nl, MOET ZEKER wegens dreigend
opzeggen). Melding: "Automatisch verversen loopt vast op pop-up; foto's en
omschrijving worden niet ingevuld", laatst gemeld 27-08-2026.

Nagelopen in het opdrachtenlogboek (`jobs`, user_id `26cf5471`) in plaats van
blind gerepareerd. Op 26 en 27 augustus mislukten 240 van de 245 opdrachten:
120 keer kon een advertentie niet gevonden worden in het Marktplaats-overzicht
(delete), en daardoor werden 119 bijbehorende herplaatsingen overgeslagen
("paired delist failed") nog vóór foto's of tekst aan bod kwamen — precies het
beeld dat de klant beschrijft. Dat is exact het mechanisme dat op 28-08-2026 is
gerepareerd (zie "Jaap (Zilverwebsite): drie klachten, drie aantoonbare
oorzaken" hierboven, extensie 1.0.256/1.0.260): het "Site verlaten?"-venstertje
van het Marktplaats-formulier bevroor het tabblad tijdens het verwijderen, en
werd toen alleen ontwapend bij het sluiten van een tabblad, niet vlak vóór de
klik die de pagina zelf wegnavigeert.

**Gecontroleerd, niet aangenomen.** Sinds 28-08 zijn er 868 opdrachten geweest
bij deze klant: 639 gelukt (waaronder herhaaldelijk "deleted_via_ad_page", de
fix in actie), en maar 1 mislukte verwijdering — die ene was op 28-08 03:02 uur
en droeg nog het stempel `[extensie 1.0.251]`, dus een kopie van vóór de update
had de reparatie simpelweg nog niet. Sindsdien geen enkele opdracht meer met
"cannot be found in your listings overview", "verlaten" of "unload" in de
foutmelding. De 102 create-fouten die sinds 28-08 wél voorkwamen zijn stuk voor
stuk andere, bekende datakwaliteitsproblemen (58× ontbrekende omschrijving,
lege kleur/vorm-velden) — geen van alle het popup-mechanisme.

Geen code gewijzigd. Teruggemeld als `opgelost`.

**Why dit hier staat:** derde keer dat een MOET ZEKER-melding van vóór 28-08
binnenkomt over een probleem dat die dag al is opgelost — de melding zelf is
ouder dan de reparatie. Zie ook de vergelijkbare aantekening van 01-09-2026.

## 03-09-2026 — Egbert had gelijk: hij wás ingelogd op 2dehands

Vanochtend schreef ik op dat Egbert Brouwer niet was ingelogd op 2dehands, en
die conclusie ging als tekst naar 303 van zijn artikelrijen en als advies in
een mail naar hem toe. Hij mailde terug: "Ik ben ingelogd op 2ehand.be, dus
weet niet wat er nu mis gaat?" Hij had gelijk, en de fout zat in mijn bewijs.

**Wat er niet deugde aan het bewijs.** Ik had gemeten dat www.2dehands.be op
het plaatsadres HTTP 401 geeft zolang je niet bent ingelogd: twaalf bytes
"Unauthorized". Dat klopt. Maar www.marktplaats.nl doet op precies datzelfde
adres precies hetzelfde, en dáár publiceerde hij die dag gewoon door. Een
waarneming die op het werkende én op het kapotte kanaal identiek is, verklaart
het verschil niet. Nagemeten met een kale aanvraag zonder cookies, beide 401.

**Twee metingen wijzen de andere kant op.**

1. Zijn eigen 2dehands-scan van 12:13 uur meldde `API 200, 0 advertenties`. Het
   advertentie-overzicht (`/my-account/sell/api/listings`) is afgeschermd:
   zonder geldige sessie is het antwoord 401. Een 200 krijg je alleen als de
   site je herkent. Hij was dus ingelogd, en had daar alleen nog nooit iets
   geplaatst, dus was de lijst leeg.
2. De inlogcontrole in de extensie zocht in de paginatekst naar "uitloggen",
   "log uit", "mijn marktplaats" en "my account". Die woorden staan niet op
   2dehands. Op dat kanaal was het antwoord dus altijd "niet ingelogd", hoe goed
   je ook was ingelogd. Ook bij een andere verkoper zichtbaar: die publiceerde
   op 02-09 om 13:46 met succes naar 2dehands en kreeg om 15:13 "niet ingelogd".

**Wat er nu anders is.**

* Wat de site antwoordt weegt zwaarder dan welk woord er op de pagina staat.
  Bij HTTP 200 valt het woord "niet ingelogd" niet meer; er staat dan dat hij
  ingelogd is en dat er niets te importeren valt.
* Zegt de site zelf dat er advertenties zijn en lezen wij er nul, dan noemen we
  dat onze fout en niet zijn inlog.
* Een ingelogd maar leeg account rondt de scan netjes af in plaats van rood.
* De melding bij "het formulier ging nooit open" beweert geen oorzaak meer. Ze
  beschrijft de waarneming en geeft de controle die het in één klik beslist:
  open `https://www.2dehands.be/my-account/sell/index.html`. Zie je je
  advertentiepagina, dan ligt het aan ons. Zie je "Unauthorized", dan aan de
  inlog. Beide adressen zijn nagemeten.
* 320 artikelrijen en 275 teruggenomen opdrachten dragen die nieuwe tekst nu
  ook met terugwerkende kracht (`scripts/herstel_2dehands_meldingen.py`).
  Nagemeten na afloop: nul rijen met de oude tekst.
* Een rode balk kan weg. Nieuwe knoppen "Clear this error" en "Clear all N on
  {kanaal}"; een advertentie die nooit een nummer kreeg was nooit geplaatst, dus
  verdwijnt die rij echt en staat het artikel weer op "nog plaatsen". Egbert
  keek tegen zes bladzijden rood aan zonder één knop die ergens heen leidde.

**Wat nog openstaat, en dat is het belangrijkste.** Waaróm het plaatsformulier
van 2dehands bij hem nooit iets terugmeldde weten we nog steeds niet. Zijn kopie
is 1.0.281 en de meting die dat onderscheidt (`scriptSeen`) zit pas in 1.0.284.
Zolang hij die niet heeft, kan alleen hij het zien, en daarom staat die ene
controle nu in de melding zelf. 840 pytest-tests groen, alle node-tests groen,
extensie op 1.0.286.

**Voor iedereen die hier straks werkt:** zie `docs/kennisbank.md`, les "Bewijs
moet onderscheiden". Spreekt een klant je conclusie tegen, behandel dat als de
sterkste tegenmeting die je hebt. Hij kijkt naar het echte scherm, jij naar een
logboek.

## 03-09-2026 — Amanda: bieden-advertenties lieten alles hangen

Amanda Haas (amandahaas1979@gmail.com, 479 artikelen) mailde vier dingen: bij
elke herplaatsing moet ze met de hand iets bij de extensie doen, het dashboard
zegt dan wel dan niet dat de extensie er niet is, er wordt een advertentie
gemeld die daarna nergens op Marktplaats staat, en advertenties met "geen
vraagprijs, maar bieden" laten het programma hangen: "dan moet ik de hele tijd
bij de pc in de buurt blijven".

**De hoofdoorzaak, gemeten in haar eigen gegevens.** 179 van haar 479 artikelen
hebben geen prijs. Van de 168 die op Marktplaats terug te vinden zijn staan er
**161 als "Bieden"** (`FAST_BID`), 6 als "Bieden vanaf" en 1 als "Gratis". Dat is
geen importfout: een bied-advertentie hééft geen prijs, en `_naar_advertentie`
neemt met opzet alleen een échte vraagprijs over. Maar het plaatsformulier stond
altijd op "Vraagprijs", en `mpPrijs(0)` vult dan een leeg veld in. Haar
opdrachtenlogboek geeft letterlijk terug: "Geen prijs ingevuld. | Fields marked
invalid: price.value=LEEG" en "Je hebt geen advertentievorm gekozen." Het
tabblad blijft dan open staan wachten op haar, de bewaker breekt na drie minuten
af, en de wachtrij staat stil — precies wat ze beschrijft.

**En daardoor raakte ze advertenties kwijt.** Herplaatsen is eerst weg, dan
opnieuw plaatsen. Struikelt stap twee, dan is de advertentie weg. Nagemeten:
elf artikelen zonder enige advertentie op Marktplaats, en bij de laatste ronde
nog eens één (item 6aff4466, 03-09 10:16). Erger nog: dat werd nérgens
vastgelegd. De regel die een mislukte publicatie zichtbaar maakt raakt alleen een
rij die op 'pending' staat, en dat is een eerste publicatie; bij een
herplaatsing staat de rij op 'delisted'. Geen advertentie, geen foutmelding,
geen bolletje. Dat is haar derde punt.

**Wat er is veranderd.**

1. De extensie kiest de advertentievorm zelf zodra er geen vraagprijs is
   (`mpPrijsvorm`/`kiesPrijsvorm` in `extension/content/shared.js`, gebruikt door
   Marktplaats én 2dehands) en laat het prijsveld dan leeg. Wat de oude
   advertentie was lezen we van de advertentiepagina, in dezelfde ophaalronde als
   de categorie en dus vóór het verwijderen (`advertentie_kenmerken`). Artikelen
   mét prijs veranderen niet: de keuzelijst wordt dan niet eens aangeraakt.
2. Een mislukte herplaatsing is nu zichtbaar: de weggehaalde advertentie krijgt
   status 'error' met de reden erbij, zodat het scherm er een rode melding en een
   knop bij tekent in plaats van niets.
3. En liever nog: draait er nog een kopie van vóór 1.0.285, dan gaat de
   verwijdering van een advertentie zonder vraagprijs **niet door** en blijft
   alles gewoon staan (`_herplaatsing_kansloos` in `backend/api/jobs.py`). Die rem
   staat op de server om dezelfde reden als bij Egbert en Toon: een
   extensiereparatie bereikt haar pas na goedkeuring door de Web Store.
4. "Extension not detected" terwijl hij er wel is: `content/ext_stamp.js` zet bij
   het laden van de pagina het versienummer op `<html data-omnivaleur-ext>`.
   Staat dat er, dan is de extensie er — dan blijft het scherm vragen
   ("starting up…") in plaats van een blokkerend installatievenster te tonen.

**Haar elf verdwenen advertenties zijn vandaag met de hand rechtgezet:** zeven
met een prijs staan op 'relisting' en komen vanzelf terug via de opruimronde; de
vier bied-artikelen staan op 'error' met de uitleg erbij en komen terug zodra de
bijgewerkte extensie bij haar draait. Alle elf zijn eerst nagekeken op de
openbare zoek-API van Marktplaats: ze waren echt weg, dus geen dubbele
advertenties.

**Wat ik NIET heb kunnen bewijzen:** haar eerste punt, "elke keer handmatig bij
de extensie toestemming geven, en hij schakelt elke keer uit". Er is in dit
project niets dat bij een herplaatsing om toestemming vraagt, en er is sinds
1.0.273 geen wijziging in de toestemmingen van het manifest. Twee kandidaten
passen: (a) het formulier dat op een rood veld blijft staan, waarna zij het zelf
moet afmaken — dat is precies wat punt 4 veroorzaakte en dat is nu weg; en (b) de
gele balk "'Omnivaleur' is begonnen met foutopsporing voor deze browser" met de
knop Annuleren, die sinds 1.0.273 alleen nog bij het plaatsformulier hoort — dus
bij elke herplaatsing. Klikt ze daar op Annuleren, dan mislukt de
advertentietekst. Aan haar is één vraag gesteld om dat te onderscheiden.

840 tests groen (samen met het werk van de tweede sessie van vandaag). Extensie
op 1.0.286; de code van deze reparatie ging mee in commit 02aac88, die door de
andere sessie is weggeschreven — we werkten in dezelfde werkmap.

**Openstaand bij Daniel:** het pakket 1.0.286 moet naar de Chrome Web Store
(`dist/omnivaleur-extension-1.0.286.zip`, opnieuw gebouwd ná die commit), en het
antwoord op de vraag over de gele balk.

## 03-09-2026 — Correctie: Egbert heeft nog nooit iets gepubliceerd, op geen enkel kanaal

In de notitie hierboven en in de commit van 12:12 staat dat zijn Marktplaats-
opdrachten uit dezelfde ronde wél doorliepen, "15 geplaatst". Dat klopt niet.
Nagemeten over zijn hele logboek (348 opdrachten, `fetch_all`, dus zonder de
duizendgrens van PostgREST):

* 304 create-opdrachten, allemaal voor 2dehands, nul geslaagd.
* Nul create-opdrachten voor Marktplaats. Ooit. Die 15 "done" waren SCANS.
* Zijn 5.533 actieve Marktplaats-rijen komen uit de import, niet uit publiceren.

Dat is een ander verhaal dan "2dehands is stuk bij hem". Wat er werkt en wat er
niet werkt loopt bij hem precies langs één lijn:

* Scannen gebeurt met `chrome.scripting.executeScript` vanuit de service worker.
  Dat werkt bij hem: 15 geslaagde Marktplaats-scans.
* Publiceren gebeurt met de content scripts uit het manifest
  (`content/shared.js` + `content/marktplaats.js` of `tweedehands.js`). Daarvan
  is bij hem nog nooit één keer aantoonbaar iets gedraaid.

Het versiestempel `[extensie 1.0.281]` in zijn foutmeldingen komt uit
`chrome.runtime.getManifest()` in background.js en zegt dus alleen iets over de
service worker, niet over de content scripts. Zie ook de kennisbanknotitie
"Tweede extensiekopie": een handmatig geladen kopie pikt opdrachten op en levert
half werk af.

**Wat er nu is bijgebouwd om dit te beslissen.** `content/shared.js` zet bij het
laden `data-omnivaleur-cs` met zijn versie op de pagina, en de bewaker kijkt
vanaf nu in het vastgelopen tabblad in plaats van een oorzaak aan te nemen: URL,
paginatitel, aantal invulvelden, de eerste regels tekst, en of dat stempel er
staat. Drie uitkomsten, drie verschillende meldingen:

1. stempel gevonden: ons script is geladen en het ligt aan ons, en dat zeggen we
   ook met zoveel woorden ("a fault on our side").
2. geen stempel, en de pagina toont "Unauthorized" of een wachtwoordveld: dán
   pas gaat het over inloggen.
3. iets anders: we schrijven op wat er stond en verzinnen geen oorzaak.

**De proef die vandaag al kan, zonder Web Store.** Laat hem één artikel naar
Marktplaats publiceren. Daar is hij aantoonbaar ingelogd (zijn scans lukken).
Loopt dat óók vast zonder teken van leven, dan ligt het aan zijn extensiekopie
en niet aan 2dehands. Lukt het wel, dan is 2dehands echt anders en weten we waar
we verder moeten kijken.

**Ook gedaan:** de opruimknop is op de echte database beproefd, met één rij van
Egbert. Voor 304 mislukte 2dehands-rijen, na 303, precies de bedoelde rij weg,
zijn 5.533 Marktplaats-rijen onaangeroerd.

**Let op, apart houden:** Daniel heeft tegelijk contact met Amanda over de
extensie (categorieën, `verkeerde-categorie-toegewezen`). Aan de categorietabel
in background.js is vandaag met opzet niets veranderd. De categorienummers
728/748 zijn overigens wel nagemeten en kloppen op allebei de sites
("Muziek en Instrumenten | Gitaren | Elektrisch", 2.265 advertenties op
2dehands), dus daar zit Egberts probleem niet.

## 03-09-2026 — Amanda, nagemeten op het echte plaatsformulier

Daniel vroeg wat er nog kon om van 85% naar 100% te komen. Vier dingen stonden
open; drie zijn nu gemeten, één blijft bij Amanda liggen. Dit gaat ALLEEN over
haar bieden-advertenties en het stempel van de extensie; Egberts 2dehands-inlog
staat hier los van en is niet aangeraakt.

**1. De keuzelijst voor de advertentievorm.** Ik gokte op de namen uit een
eerdere waarneming. Anoniem is dat niet te controleren: `marktplaats.nl/plaats`
geeft 401 met twaalf bytes, precies zoals `2dehands.be/plaats` bij Egbert. Via
Daniels eigen ingelogde browser wél, in twee categorieën (kleding 621/636 en
Huis en Inrichting > Servies 504/1262). Allebei exact vier keuzes en verder
geen:

    Vraagprijs = FIXED
    Bieden = FAST_BID
    Zie omschrijving = SEE_DESCRIPTION
    Gratis = FREE

Onze code kiest "Bieden" op tekst én op de waarde FAST_BID, dus die klopt. Twee
dingen kwamen er bovenop:

* Bij het kiezen van "Bieden" **verdwijnt het prijsveld** uit het formulier. De
  volgorde in `fillForm` (eerst de vorm, dan de prijs) was dus geen voorzorg maar
  noodzaak, en dat staat nu ook zo in de proef.
* React neemt de keuze aan via de eigen value-setter plus een change-gebeurtenis,
  live nagemeten: van `FIXED` met een zichtbaar prijsveld naar `FAST_BID` zonder.
* Marktplaats kent hier geen "Gereserveerd" of "Ruilen". Een advertentie die op
  het platform zo staat kon dus niet in zijn eigen vorm terugkomen en liep tegen
  een foutmelding aan. Die valt nu terug op "Bieden", want zonder vraagprijs is
  dat de enige vorm die klopt.

**2. De rem in de uitgifte.** Die was los getoetst. Nu draaien drie proeven
`get_pending_jobs` zelf, met het versiekopstuk dat de extensie echt meestuurt:
een kopie van vóór 1.0.285 krijgt de verwijdering niet te zien en beide
opdrachten gaan terug terwijl de advertentie blijft staan; 1.0.286 krijgt het
werk gewoon; een artikel mét prijs gaat ook op de oude kopie door.

**3. Het dashboard, op de live uitgerolde pagina.** De echte `app.html` van
omnivaleur.com opgehaald en zijn eigen functies gedraaid. Met stempel:
"Extension v1.0.286 — starting up…" en geen installatievenster. Zonder stempel
(iedereen die de update nog niet heeft): onveranderd "Extension not detected"
met het venster. Geen achteruitgang dus voor bestaande gebruikers.

**4. Haar eerste punt blijft open, maar één theorie is nu weg.** Ik dacht aan de
gele balk "Omnivaleur is begonnen met foutopsporing" met de knop Annuleren. In
haar 194 plaatsopdrachten staat geen enkele mislukte debugger-koppeling op
Marktplaats; er staat juist een geslaagde echte klik in ("geklikt op 871,251").
De drie treffers op "niet gekoppeld" zijn alle drie Vinted en gaan over de
gratis-keuze, niet over de balk. Wat overblijft als verklaring: het formulier dat
op een rood veld bleef staan en dat zij zelf moest afmaken — precies de storing
die nu weg is. De vraag aan haar blijft staan, maar is nu een bevestiging in
plaats van een gok.

844 tests groen. Extensie op 1.0.287 (die versie komt van de andere sessie en
bevat beide reparaties). Het pakket dat eerder als 1.0.286 is doorgestuurd is
daarmee vervangen.

## 03-09-2026 — Toon (dejuistetoon): "50 jobs, er gebeurt eigenlijk niets"

Twee WhatsApp-berichten van dezelfde dag, allebei nagemeten aan zijn eigen
account (96e30080…) en niet beredeneerd.

  12:44  "Ben al ff aan het laden 50 jobs, maar er gebeurd eigenlijk niets?"
  16:18  "Diverse item zijn geplaatst echter nog niets zichtbaar op marktplaats
          en tweedehands"

**Het tweede bericht klopt feitelijk niet, en dat is meetbaar.** Zijn
advertenties stonden er gewoon. Van de negen die er die dag op Marktplaats bij
kwamen zijn alle negen opgehaald: HTTP 200, juiste titel, juiste categorie. Ze
staan ook alle negen boven aan zijn openbare verkoperslijst
(`lrp/api/search?sellerIds[]=17981431`, "DJT De Juiste Toon", 280 advertenties),
gedateerd "Vandaag". De twee 2dehands-advertenties van die dag idem, 200 met de
juiste titel. Er valt daar dus niets te repareren; hij moet horen wáár hij moet
kijken. Let op: hij is een **zakelijk** account (seller_type TRADER), en zijn
scan loopt dan ook over `personal+admarkt`.

**Het eerste bericht klopt wel, en had twee oorzaken.**

**1. Calm mode stond aan, het scherm wist dat niet.** Gemeten aan de
tijdstippen van zijn eigen opdrachten: het werk zelf duurt 20 tot 35 seconden,
maar tussen twee opdrachten zat 192 tot 571 seconden — precies de 3 tot 8
minuten van `CALM_MIN_MS`/`CALM_MAX_MS`. Mediaan 345 s. Ter vergelijking, op
dezelfde dag: Egbert 12 s, Amanda 11 s, bcdf9aa4 10 s. Ondertussen zei de balk
op zijn scherm "50 jobs queued — the extension is about to start … within ~15
seconds". Om 12:44 was hij vier minuten in zo'n pauze. Het liep gewoon; de
belofte was vijfentwintig keer te snel.

De schakelaar zit in `chrome.storage.sync` van de extensie, dus vragen kan niet
en een nieuwe extensie is pas over weken bij hem. De server **meet** het nu uit
werk dat al gedaan is (`_gemeten_tempo`): mediaan van de gaten tussen `done_at`
en het volgende `claimed_at`, gaten boven twintig minuten weggegooid (computer
uit), minimaal drie metingen voor we iets beweren. Werkt vandaag, op de kopie
die hij nu draait. Eén minuut gecachet, want `/api/jobs/active` wordt elke vier
seconden opgevraagd en zo'n vraag kost 368 ms op een blokkerende client.

De balk zegt nu drie verschillende dingen in plaats van één: bij Calm mode het
gemeten tempo plus hoe lang de rij gaat duren plus waar de schakelaar zit, bij
een stille extensie dat er niets gaat lopen en wat hij daaraan doet, en anders
gewoon de oude tekst. Dezelfde meting zit ook in de melding vlak na een klik.

**2. Zijn eigen klik stond achter de nachtronde.** De uitgifte deed
`order(created_at).limit(20)` en gaf daar één opdracht uit. Om 02:33 zette de
verversing 50 opdrachten klaar (24 herplaatsparen); zijn publiceerklik van
13:28 stond daarmee op plek 24 en kwam niet eens in dat venster voor. De
volgorde is nu urgentie in plaats van aankomst: eerst een herplaatsing waarvan
de oude advertentie al wég is (die staat nu nergens online), dan zijn eigen
klikken, dan de nachtronde die langer dan zes uur wacht, dan de verse
nachtronde, dan scans. Voor-en-na op zijn echte wachtrij van dat moment: oud
stonden de zes oudste allemaal uit de nachtronde van 02:33, nu staat de offline
advertentie voorop en daarna zijn eigen klikken van 10:49 en verder.

De volgorde wordt over de héle wachtrij bepaald met alleen de lichte velden;
pas de kop wordt volledig ingelezen. Dataverkeer blijft dus gelijk aan de oude
limit(20), maar het zijn wel de goede twintig.

**Meegenomen omdat het uit dezelfde klacht komt:** er stonden vier identieke
Marktplaats-scans van dezelfde seconde klaar (op 02-09 zelfs dertien). Dat is
wat iemand doet als er niets lijkt te gebeuren. Er blijft er nog één over, en
wel de **nieuwste** — die draagt de meest bijgewerkte lijst van "dit hebben we
al" mee, en daar bespaart de extensie haar Vinted-verzoeken op.

**Wat NIET gerepareerd is, met zoveel woorden.**
- Zijn extensie heeft zich sinds 17:00 niet meer gemeld terwijl er 62
  opdrachten wachten. Daar kan van hier niets aan gedaan worden: Chrome moet
  openstaan met de extensie aan. De balk zegt dat nu wel.
- Tien "Extension timed out — no response after 3 minutes" op Marktplaats
  vandaag. Onveranderd niet van hier te herleiden; daarvoor moet je meekijken.
- Zijn 2dehands-advertentieoverzicht geeft 401. Alleen hij kan opnieuw
  inloggen. Publiceren op 2dehands lukt wél, dus dit raakt alleen het overzicht.
- Het gat van 11:19 tot 13:21 waarin niets werd opgepakt, past bij een
  Chromebook die in slaap gaat, maar dat is een vermoeden en geen meting.

Geen extensiewijziging, dus geen versiebump: alles hierboven werkt op de kopie
die hij vandaag draait. 854 tests groen (was 844).

## 03-09-2026 — Chrome zet de extensie stil zodra het laatste venster dicht gaat

Naar aanleiding van het gesprek met Naoufal (websitebouwer van Toon/dejuistetoon)
en Toons klacht "50 jobs, er gebeurt eigenlijk niets". Naoufal bevestigde wat al
gemeten was: Toon heeft geen technische kennis en snapt niet dat hij Chrome open
moet laten. Zijn tip was om de extensie zelf op een server te draaien met de
inloggegevens van klanten. Dat doen we bewust niet: wachtwoorden van klanten in
eigen beheer, accountdelen is tegen de voorwaarden van Marktplaats, en al die
klanten vanaf één datacenter-IP is precies het patroon dat Calm mode moet
vermijden.

**Wat wel gemeten is (Mac, Chrome 152).** Twee identieke testextensies naast
elkaar, één met de permissie `background` en één zonder, elk in een eigen Chrome
met een eigen profiel, allebei pingend op een lokale logserver via
`chrome.alarms` (30 sec):

| fase | zonder permissie | met permissie |
|---|---|---|
| venster open, 75 sec | 2 tikken | 2 tikken |
| alle vensters dicht, 155 sec | 0 tikken | 5 tikken |

Controleproef die het mechanisme aanwijst: dezelfde extensie zónder de permissie,
maar gestart met `--disable-features=DestroyProfileOnBrowserClose`, tikte met alle
vensters dicht wél door (5 tikken in 150 sec). Het is dus niet de service worker
die in slaap valt, maar Chrome die het hele profiel opruimt zodra het laatste
venster sluit. De permissie `background` houdt het profiel in leven.

Risico afgedekt: Chrome zelf (`chrome.management.getPermissionWarningsByManifest`)
geeft voor het huidige manifest en het manifest mét `background` exact dezelfde
waarschuwingenlijst. Bestaande klanten krijgen dus géén nieuwe toestemmingsvraag
en de extensie valt niet stil in afwachting van een klik.

Doorgevoerd in extensie 1.0.288. Let op: dit werkt pas als de Web Store hem heeft
goedgekeurd, dus voor Toon verandert er deze week nog niets.

**Wat het niet oplost:** een computer die uit staat of slaapt. Daar helpt geen
enkele instelling tegen.

**Daarom er ook bij:** een offline-waarschuwing per e-mail
(`backend/services/extension_offline.py`, elk uur). Staat de extensie meer dan
drie uur stil terwijl er minstens drie uur werk wacht, dan krijgt de klant één
mail per 24 uur, alleen tussen 10:00 en 20:00 NL, en alleen bij een lopende proef
of abonnement. Dat tijdvenster is er omdat de nachtelijke herplaatsronde rond
02:30 bij iedereen werk klaarzet.

**Openstaand:** de markeerkolom moet met de hand in Supabase komen:
`ALTER TABLE extension_heartbeat ADD COLUMN offline_mail_sent_at timestamptz;`
Zolang die ontbreekt onthoudt de server het zelf, en kan de mail zich na een
deploy herhalen.

**Zakelijk uit hetzelfde gesprek:** Naoufal onderhoudt websites voor meerdere
Marktplaats-verkopers en bood uit zichzelf aan Omnivaleur door te vertellen. Hij
is de logische installateur voor klanten zoals Toon. Prijs naar aantal
advertenties (Toon heeft er 280 en betaalt hetzelfde als iemand met 25) is
besproken maar bewust uitgesteld: eerst moet het dashboard echt goed werken.

## 03-09-2026 — Audit kernfuncties: de reddingsronde zette dubbele advertenties klaar

Daniel vroeg om een kritische audit van de vitale functies (publiceren, ophalen,
verversen) op basis van wat er echt in de opdrachtentabel staat. Gemeten over de
laatste drie dagen: 743 klaar, 85 fout, 86 geannuleerd. Vrijwel alle fouten
vallen vóór de reparaties van vanochtend (kleurnamen, kansloze reeks) of zijn
één verkoper die niet op 2dehands is ingelogd (304 opdrachten, terecht
tegengehouden). Eén echte fout bleef over, en die stond op scherp:

**74 advertenties stonden op 'relisting'.** De reddingsronde (elke zes uur)
zette voor elke 'relisting'-rij zonder plaatsopdracht een kale plaatsing klaar,
zonder te kijken of het weghalen ooit gelukt was. Bij Toon: drie kelims waarvan
hij de herplaatsing om 02:34 zelf annuleerde (oude advertentie dus nog online),
en om 17:44 drie kale plaatsingen in de rij. Bij twee andere verkopers via de
driedagenveger, oude advertentie nog aantoonbaar live (HTTP 200). 48 van de 74
waren demo-accounts, maar het mechanisme was hetzelfde.

Gerepareerd op drie plekken (`relist.py`, `jobs.py`):
- de reddingsronde plaatst alleen opnieuw als de laatste verwijdering 'done' is;
  anders neemt ze de herplaatsing terug (rij 'active' met uitleg, klaarstaande
  plaatsingen ingetrokken, verversbeurt terug);
- de driedagenveger neemt een verlopen herplaatsverwijdering in zijn geheel terug
  in plaats van beide banen op fout te zetten en de rij te laten hangen;
- een verwijdering die de verkoper zelf annuleert zet de rij meteen terug.

Eén keer met de hand gedraaid tegen de live database (de server draait de ronde
pas zes uur na een herstart): relisting nu 15, teruggenomen 59, via veger 0. Toons drie dubbele
plaatsingen zijn ingetrokken voordat zijn extensie ze kon oppakken.

**Niet gerepareerd, wel gezien:** Jaaps zilveren dameshorloge krijgt elke ronde
een nieuwe plaatsing die op het advertentievorm-veld sneuvelt (vier keer in twee
dagen); dat lost de extensie 1.0.285+ op zodra de Web Store hem doorlaat.
Kleurwoorden "zilverkleurig", "goudkleurig" en "multicolor" worden nog niet
herkend; of "Zilver" in de sieradencategorie bestaat als optie is niet gemeten.

## 04-09-2026 — Skill: openstaande Daniel-taken naar Google Agenda

Daniel gebruikt Google Agenda, Tasks en Drive veel en wil dat elke openstaande
Omnivaleur-taak die alleen hij zelf kan doen automatisch in zijn agenda komt.
Google Tasks is niet als koppeling beschikbaar, Google Agenda wel. Nieuwe skill
`~/.claude/skills/omnivaleur-taken/` (account-lokaal, niet in de repo): verzamelt
Daniel-only taken uit mail_analyse bugs, team-notes en terugkerende acties (Web
Store upload, handmatige Supabase-migraties), controleert op dubbelen via
list_events, en zet ze als hele-dag-item op de hoofdagenda met prefix
"Omnivaleur:". Activeert bij "wat moet ik doen / mijn taken / zet in mijn agenda"
en aan het eind van een sessie met een openstaande Daniel-stap.

Eerste ronde vandaag toegevoegd: extensie 1.0.288 naar de Chrome Web Store, en
de kolom offline_mail_sent_at in Supabase.

Correctie 04-09: de taken horen in de Google Tasks lijst "Omnivaleur" (onder
danieldekoning66@gmail.com, in Chrome authuser=2), niet in de agenda. Er is geen
Google Tasks koppeling, dus de skill doet het via de Chrome-extensie op
tasks.google.com/u/2/. Lezen van de lijst werkt; het toevoegen via automation was
op 04-09 wisselvallig (renderer bevriest, invoerveld opent niet altijd). Agenda
blijft de terugval. Betere optie: een echte Google Tasks connector aanzetten in
claude.ai als die bestaat.

Definitief 04-09: geen Google Tasks connector beschikbaar, dus de omnivaleur-taken
skill zet alles als geel hele-dag-item op de agenda danieldekoning66@gmail.com
met "Omnivaleur:" ervoor. Getest en werkt.

## 04-09-2026 — "Geen zoekertjestekst ingevuld": het formulier bewaart de tekst ergens anders

Daniel: "2dehands geeft nu weer deze melding... soms wel en soms niet, soms
schrijft ie gelijk door en publiceert ie zelf." Op zijn scherm: het zoekertje
(598) Burgundy Suitsupply Turtleneck, de beschrijving zichtbaar in de editor, en
er rood onder "Geen zoekertjestekst ingevuld." Typte hij zelf één spatie, dan
verdween de melding en ging het zoekertje eruit.

In zijn opdrachtenlijst is het verschil te zien: (598) duurde 9 minuten 20, de
twee zoekertjes erna 20 en 21 seconden. Alle drie dezelfde verkoper, dezelfde
categorie, dezelfde ochtend.

**Gemeten op het echte formulier** (ingelogd, 2dehands.be én marktplaats.nl,
categorie Heren > Truien en Vesten): het plaatsformulier is een react-hook-form
en de controle bij het plaatsen leest `control._formValues.description`. Onze
manier van invullen zet 122 tekens in de zichtbare editor en laat die waarde op
0 staan. Het verborgen veld `description_nl-BE` vullen helpt niet (React kent
die waarde niet), `execCommand` doet in deze editor helemaal niets, en ook
Lexical's eigen invoegcommando en een echte focusverplaatsing veranderen er
niets aan. Waarom een getypte spatie wél werkt: die zet de waarde indirect
alsnog in de staat van het formulier.

**Voor-en-na-proef, zonder iets te plaatsen:** het formulier zijn eigen
validatie laten draaien (handleSubmit met eigen callbacks) gaf met een gevulde
editor de fout op `description`; na alleen `_formValues.description` te vullen
viel `description` uit de foutenlijst weg. Op beide platforms.

Gerepareerd in 1.0.289: de extensie schrijft de beschrijving nu rechtstreeks in
de staat van het formulier, leest hem terug vlak vóór het plaatsen, en houdt een
bewaker draaiend tot en met de klik — want elke hertekening (foto klaar, kenmerk
gekozen, merk-venster dicht) kan hem weer leeggooien. Dat laatste is precies
waarom het "soms wel, soms niet" was. De echte toetsaanslag via chrome.debugger
blijft als achtervang bestaan, maar is niet langer de enige weg.

**Openstaand:** 1.0.289 moet naar de Chrome Web Store. Tot die tijd werkt de
reparatie alleen op een handmatig geladen kopie.

04-09 vervolg: voor echte Google Tasks komt er een losse MCP-server
(taylorwilsdon/workspace-mcp, pakket workspace-mcp via uvx). uv is geinstalleerd.
Startscript en .env-sjabloon staan in ~/Documents/Handige Scripts Mac/google-workspace-mcp/.
Daniel moet nog een Google Cloud OAuth-client (Desktop app) maken en client id +
secret in .env zetten. Daarna: start.command draaien en
`claude mcp add --transport http workspacemcp http://localhost:8000/mcp`.
De skill gebruikt Tasks zodra die tool er is, anders de agenda als terugval.

04-09 workspace-mcp draait: LaunchAgent com.omnivaleur.workspacemcp (KeepAlive,
start bij inloggen) draait `uvx workspace-mcp` op http://localhost:8000/mcp,
tool-tier complete. Toegevoegd aan Claude Code als MCP 'workspacemcp' (local
config, project omnivaleur). OAuth-client (Desktop app) hoort bij
danieldekoning66@gmail.com, id+secret in de .env naast het startscript.
Openstaand: (1) Claude-sessie herstarten zodat de workspacemcp-tools laden,
(2) bij de eerste Tasks-aanroep opent een browser voor Google-toestemming,
Daniel moet door de 'niet geverifieerde app' klikken. Daarna kan de
omnivaleur-taken skill echt in Google Tasks lijst Omnivaleur schrijven.

04-09 werkt: Google Tasks-koppeling via workspace-mcp is rond. OAuth gedaan
(Daniel als testgebruiker toegevoegd, tokens in ~/.workspace-mcp/). De
omnivaleur-taken skill schrijft nu echt in de Tasks-lijst Omnivaleur
(id UnlxRk9OVzFYdlBuYVpsbw) via mcp__workspacemcp__manage_task. Eerste ronde:
"Extensie 1.0.289 naar Chrome Web Store uploaden" toegevoegd, de rest stond er al.

04-09: geplande taak 'omnivaleur-taken-ochtend' draait elke ochtend ~08:22 en
roept de omnivaleur-taken skill aan om de Tasks-lijst Omnivaleur bij te werken.
Draait alleen als de Claude-desktop-app open staat. Eerste keer 'Run now' zodat
de tool-toestemmingen (workspacemcp, bash) blijven hangen.

04-09: de ochtendtaak draait onbewaakt. In ~/.claude/settings.json staan
allow-regels voor de tools die hij gebruikt (workspacemcp Tasks, agenda-connector,
git, mail_analyse, lees-commando's), zodat er geen toestemmingsvraag komt. Geen
globale bypass-mode aangezet; iets onverwachts vraagt nog wel.

04-09 Egbert Brouwer (Papa's Plectrums) mailde twee dingen terug, allebei
gerepareerd:

1. "Waar kan ik die knop vinden om alle rode balken weg te halen, ik zie hem
   niet maar heb al wel de laatste versie (1.0.288)?" De knop bestond sinds
   03-09, maar alleen achter een klik op een rode balk in de lijst, en die balk
   zag er niet uit als iets waarop je kunt klikken. Er staat nu een balk boven
   de artikellijst ("314 publishes failed" met per kanaal "Clear 303 on
   2dehands"), naast de sold- en duplicate-balk. De rode balk in de rij zegt
   voortaan "what now?" zodat duidelijk is dat er iets achter zit.

2. "Publiceer een enkel artikel naar Marktplaats: die mogelijkheid is er niet
   omdat MP al geselecteerd staat." Klopte. Al zijn 5.533 advertenties komen uit
   de Marktplaats-import, dus elk artikel stond in het publiceervenster op
   "✓ Listed" zonder aanvinkvakje, en Publish antwoordde met "Choose at least
   one platform". Het is nu een aanvinkbare keuze met een waarschuwing dat je er
   een tweede advertentie bij krijgt als de eerste er nog staat. Let op: de
   server houdt dit niet tegen — die kijkt alleen naar dubbele rijen van
   hetzelfde artikel, niet naar de rij zelf.

3. Zijn tweede foto ging over de gele balk "Omnivaleur is begonnen met
   foutopsporing voor deze browser", met een pijl naar de knop Annuleren. Die
   koppeling is nodig: Marktplaats en 2dehands negeren een muisklik die van een
   script komt, dus zonder koppeling wordt er nooit op "Plaats je advertentie"
   gedrukt. Wie op Annuleren drukte brak het plaatsen af zonder dat de extensie
   het merkte — gemeten op de oude code: klikEcht gaf daarna "Debugger is not
   attached to the tab". In 1.0.290 luistert de extensie naar
   chrome.debugger.onDetach en koppelt hij opnieuw.

Openstaand: 1.0.290 moet naar de Chrome Web Store (1.0.289 stond er ook nog niet
op). De dashboard-reparaties (1 en 2) werken meteen na de Railway-deploy, daar
is geen nieuwe extensie voor nodig.

Wat Egberts plaatsen zelf blokkeert is hier níét mee opgelost: 309 van zijn
foutrijen zeggen "the 2dehands listing form never opened: the page never
reported back". Dat is de bekende stille tab, en dat staat nog open.

## 04-09-2026 — Vinted meldde "niet ingelogd" bij een ingelogde verkoper

Daniel kreeg bij het publiceren naar Vinted "You are not signed in to Vinted
(vinted.com). Nothing was published", terwijl hij in dezelfde browser gewoon op
vinted.nl was ingelogd. Er werd niets geplaatst.

Oorzaak, gemeten: een Vinted-account leeft op één landdomein en de sessiecookie
reist niet mee. `https://www.vinted.com/api/v2/users/current` geeft 401 zonder
doorverwijzing naar vinted.nl. De inlogcontrole (toegevoegd 01-09 na de zaak
Budgetheld) viel terug op vinted.com zodra de opdracht geen `_create_origin`
droeg, en dat is bij élke eerste plaatsing zo: dat veld wordt alleen gezet bij
herplaatsen (backend/services/relist.py:650). Dezelfde aanname zat in het adres
van het plaatsformulier zelf, dus zonder de controle was de advertentie in de
verkeerde catalogus beland; `vinted.com/items/new` stuurt een uitgelogde
bezoeker bovendien door naar `/member/register/select_type` (HTTP 200).

Vanaf 1.0.291 zoekt de extensie het domein op in plaats van het te gokken
(`vintedIngelogdOrigin`, VINTED_ORIGINS: nl, be, de, fr, com), onthoudt het
antwoord een kwartier, geeft het gevonden domein door aan het plaatsformulier, en
meldt alleen "niet ingelogd" als élk domein dat hardop zegt. Een netwerkfout of
onderhoud geeft "onbekend" en houdt het werk niet tegen. Bewezen met
`tests/vinted-inlogdomein-test.js`, inclusief voor-en-na-proef tegen de vorige
versie van background.js.

Openstaand: 1.0.291 moet nog naar de Chrome Web Store. 1.0.289 en 1.0.290 staan
er ook nog niet op, dus tot die upload werkt dit alleen op een handmatig geladen
kopie. In de database stond op dat moment één foutregel met deze melding (van
Daniel zelf, 09:24); de 309 openstaande "the listing form never opened" op
2dehands zijn hier los van en nog niet opgelost.

## 04-09-2026 — Vinted hield het plaatsen tegen om een melding die niets over de prijs zei

Daniel, met schermafbeelding: "vinted geeft nu regelmatig deze melding. als ik
dan zelf een 9 typ of iets weghaal (random) dan verdwijnt die melding." In beeld:
prijsveld €14.99, eronder in het rood "Price must be greater than or equal to
1.0". Het plaatsen stopte daarop met "Vinted wouldn't accept these fields:
price (...)".

Die melding was geen oordeel over de prijs. Ze verdween door één teken opnieuw te
typen zónder de prijs te veranderen, dus ze bleef gewoon hangen. Toch was ze in de
code hét afkeurcriterium: elke invulroute keurde zichzelf af zolang de regel er
stond, en de eindcontrole vóór het plaatsen stopte erop. Uitkomst: het veld toonde
de juiste prijs en er werd niets geplaatst.

Gemeten in Chrome (04-09-2026), dit zijn eigenschappen van de browser, niet van
Vinted:
* `dispatchEvent(new Event("blur"))` levert géén focusout op en het veld blijft
  gefocust. React hangt zijn onBlur aan focusout, dus het formulier heeft zijn
  eigen controle na onze invulling nooit opnieuw gedraaid.
* `document.execCommand("insertText")` is de enige route uit een script die een
  invoergebeurtenis met isTrusted=true oplevert; alles wat we met dispatchEvent
  sturen is isTrusted=false.
* de oude invulroute stuurde het formulier eerst een LEGE prijs (waarde "" plus
  een input-gebeurtenis) voordat de prijs erin ging. Dat is precies de invoer waar
  "must be greater than or equal to 1.0" op slaat: we zetten de klacht zelf neer.

Vanaf 1.0.292: de prijs gaat er in één keer in zonder tussenstap via leeg, het
veld wordt echt verlaten (blur plus een focusout die bubbelt), en blijft de regel
tóch staan, dan doet de extensie na wat Daniel met de hand doet: één teken over
zichzelf heen typen met execCommand. Beslissend is niet meer de rode regel maar
de waarde die het formulier zelf vasthoudt (nieuw: READ_PRICE_MAIN /
`_mwLeesVintedPrijs`). Houdt het formulier een bruikbare prijs vast, dan gaat het
plaatsen gewoon door en beslist Vinted zelf bij Uploaden; mislukt het daarna, dan
staat de prijsmelding in de foutmelding. Bewezen met
`tests/vinted-prijsmelding-test.js`, inclusief voor-en-na-proef tegen commit
668afc8.

Let op voor de volgende sessie: de voor-en-na-proef mag niet tegen HEAD draaien.
De auto-push-hook commit werk in uitvoering onder "auto: update ...", dus HEAD
bevat de reparatie al voordat de test draait. `tests/vinted-inlogdomein-test.js`
faalde daar vandaag op en wijst nu naar een vaste commit.

Openstaand: nog niet nagemeten op het echte, ingelogde Vinted-formulier (daar is
Daniels eigen browser voor nodig). 1.0.289 tot en met 1.0.292 staan alle vier nog
niet in de Chrome Web Store.

## 04-09-2026 — Vinted zette bijna alles onder "Other ..." terwijl hij zelf iets beters voorstelde

Daniel: "hij upload heel vaak binnen een categorie op vinted naar other...
terwijl vinted iets anders voorstelt en ik ook denk dat het een andere categorie
moet zijn. gebeurt vaker." Voorbeeld: (1365) Black Uniqlo Trousers kwam onder
Men > Clothing > Trousers > Other trousers.

De tak was goed. Het niveau daaronder niet. Onder een tak zet Vinted nog een
niveau (Chinos, Cargo trousers, Skinny trousers, Other trousers) en `kiesBlad`
koos dat blad op woorden uit titel en omschrijving. Zegt de tekst daar niets
over, en dat is bij een gewone advertentie bijna altijd zo, dan viel de keuze op
het vangblad "Other ...". Kopers filteren juist op die bladen, dus dat kost
vindbaarheid bij vrijwel elk artikel.

Wat er over het hoofd werd gezien: op het moment dat de kiezer opengaat toont
Vinted bovenaan zijn eigen voorstellen, afgeleid uit de foto's, als een regel met
de bladnaam en daaronder het kruimelpad ("Chinos", "Men > Clothing > Trousers").
De extensie klikte daar dwars doorheen de boom in, en dan zijn ze weg.

Vanaf 1.0.293 leest `walkVintedCategoryPath` die voorstellen zodra de kiezer
opengaat, en gebruikt er één als de tekst van het artikel niets over het model
zegt. `kiesBlad` schrijft daarvoor in `bladReden` waaróm het koos: "voorkeur" of
"woorden" is een echte aanwijzing uit de tekst en wint altijd, "neutraal" is de
gok en die wijkt voor Vinted. Een voorstel telt alleen mee als het onder ons
eigen pad ligt: Vinted mag het blad kiezen, nooit de tak, anders belandt een
herenbroek in de damesafdeling omdat de foto daarop leek.

Bewezen met `tests/vinted-mock/categorie-voorstel-test.js` (13 controles): de
vorige versie kiest onder dezelfde omstandigheden aantoonbaar "Other trousers",
de nieuwe "Chinos"; tekst wint van voorstel; een voorstel uit een andere tak of
uit de damesafdeling verandert niets; zonder voorstellen blijft het oude gedrag.

Openstaand:
- De vorm van de voorstelregels is overgenomen uit wat er in vinted.js staat
  opgeschreven van de echte pagina, niet opnieuw gemeten op een ingelogde Vinted.
  Klopt die vorm niet, dan doet de reparatie niets en blijft het bij "Other ...";
  slechter wordt het niet.
- 1.0.289 tot en met 1.0.293 staan geen van alle in de Chrome Web Store.
- `tests/vinted-mock/prijs-hertypen-test.js` stond rood sinds de prijsreparatie
  van gisteren (FocusEvent bestaat niet in Node); die proef geeft hem nu zelf mee.
- De MOET ZEKER-melding `verkeerde-categorie-toegewezen` (zilverwebsite, Amanda)
  is hiermee NIET opgelost: die gaat over een HTTP 500 en over zilver dat in de
  lijst ontbreekt.

## 04-09-2026 — Egbert: "Ik kan nu de knop zien, maar hij werkt niet"

Hij stuurde een schermafbeelding: *"Cleared 0. These did not clear: 2dehands:
Something went wrong on our side (code F1F7E7)"*. De knop van gisteren deed dus
niets.

Die code was niet meer terug te vinden, en dat is een storing op zichzelf. Het
foutenlogboek bewaart zestig regels, nieuwste bovenaan, en alle zestig waren op
dat moment exact dezelfde fout van `/api/items/sync` — die faalde elke vijftien
seconden. Zijn code was er binnen een uur uit gedrukt. Het logboek dat er is om
te kunnen bewijzen wat er stukging, wiste het bewijs zelf.

Drie reparaties, alle drie apart gemeten:

**1. `/api/items/sync` was drie dagen stuk.** Sinds commit 8747493 (01-09) telde
die met `select(..., head=True)`. `requirements.txt` pint `supabase==2.7.4`
(postgrest 0.16.11) en die kent `head` niet; lokaal stond 2.31.0 en daar werkt
het wel. Gevolg: elke automatische verversing van elk open dashboard gaf een
interne fout, dus het scherm werkte zichzelf niet meer bij (alleen na een eigen
handeling). Dezelfde fout stond ook in `backend/api/beheer.py`, waar hij in een
`except` viel: daardoor stond er "onbekend" op het beheerscherm in plaats van de
aantallen. Nu geteld met `count="exact"` + `limit(1)`; gecontroleerd tégen de
echte database mét de gepinde client: 5.533 artikelen en 10.794 actieve
advertenties, één opgehaalde rij. De oude code loopt onder dezelfde nabootsing
aantoonbaar stuk op `TypeError: ... 'head'`.

Waarom de tests dit niet zagen: de nabootsing in `tests/test_dataverkeer_
dashboard.py` slikte `head=` gewoon. Die heeft nu exact de handtekening van de
gepinde client, plus een bewaker die `head=True` nergens in `backend/` meer
toestaat.

**2. Het foutenlogboek telt dezelfde storing nu als één regel** met `aantal` en
de laatste tien codes. Zestig plekken zijn nu zestig vérschillende storingen.
Bewezen: honderd keer dezelfde fout wegschrijven laat F1F7E7 staan; op de oude
versie is hij weg.

**3. Het opruimen zelf.** `/api/listings/clear-error` deed het nog op de oude
manier: alle item-id's ophalen, in brokken van 200 hakken, per brok een vraag.
Bij zijn 5.533 artikelen 29 vragen binnen één verzoek. Gemeten op zijn echte
gegevens: 7,8 seconden tegen 0,2 seconde via de gekoppelde vraag, met exact
dezelfde 304 rijen. Belangrijker: van die 29 vragen waren de twee deletes de
enige onbeschermde. Leesacties worden sinds 30-08 overal automatisch herkanst,
schrijfacties met opzet niet (een insert herhalen maakt een tweede advertentie),
maar een rij weggooien die tóch weg moet is veilig om nog eens te proberen.
Zonder die herkansing wordt één weggevallen Supabase-verbinding een naamloze
500. Dat is de waarschijnlijkste verklaring voor F1F7E7.

Openstaand en eerlijk: **bewezen is dat niet.** De trace was al uit het logboek
gedrukt voordat ik keek. Wat wél is gemeten: het leespad en de schrijfvorm
werken allebei tegen zijn echte gegevens mét de gepinde client, en de deletes
waren de enige stap zonder vangnet. Gaat het na deze deploy tóch nog mis, dan
staat er nu in het antwoord zelf wát er misging (502 met de fout erin) in plaats
van een code, en blijft die code voortaan in het logboek staan.

Ook nog van hem: hij biedt aan te blijven testen in ruil voor gratis gebruik van
Omnivaleur. Dat is een beslissing voor Daniel, niet voor mij; hier alleen
vastgelegd zodat het niet in een mailtje blijft hangen.

### Vervolg dezelfde dag: de klikproef op Daniels eigen account

Daniel wilde geen 80% maar zekerheid, dus is de knop echt geklikt, ingelogd als
dkresellacademy. Beginstand vooraf vastgelegd: 691 advertentierijen, waarvan 13
mislukt (8 eBay, 3 Facebook, 1 2dehands, 1 Shopify), alle 13 zonder
advertentienummer.

Uitkomst op zijn scherm: *"Cleared 4. These did not clear: eBay: The server took
too long to respond (502). Shopify: idem."* Nagemeten in de database: 4 rijen
echt weg (3 Facebook, 1 2dehands), 9 blijven staan (8 eBay, 1 Shopify), en nul
rijen geraakt die niet mislukt waren.

Daarmee lag de tweede oorzaak wél op tafel, en die is bewezen in plaats van
waarschijnlijk:

**`sync_events` blokkeert het verwijderen.** `sync_events.listing_id` wijst met
een echte sleutel naar `listings(id)` en heeft geen `on delete cascade`. Aan
precies die 9 vastzittende rijen hingen 21 gebeurtenissen; aan de 4 die wél
opruimden geen enkele. eBay en Shopify schrijven bij elke poging zo'n regel
(`_log_event` in crosslist.py), de extensiekanalen niet. Dat is de scheidslijn.
`backend/api/items.py` ruimde bij het verwijderen van een artikel die
gebeurtenissen al eerst op; clear-error deed dat niet. Nu wel.

**En waarom de reden onzichtbaar bleef.** Mijn eigen vangnet gaf een 502 met de
uitleg erin. Cloudflare vervangt een 502 of 503 door zijn eigen HTML-foutpagina,
dus die uitleg bereikte de browser nooit en werd "de server duurde te lang" bij
een fout die in een fractie van een seconde optrad. Dat staat al sinds 30-08 als
waarschuwing in `backend/api/items.py` bij `create_item`, en ik trapte er alsnog
in. Nu 500, die komt ongewijzigd door.

Openstaand: er staan nog meer 502/503-antwoorden in `shopify.py`, `content.py`,
`billing.py`, `deps.py` en `listings.py:432`. Die verbergen hun boodschap op
dezelfde manier. Niet aangeraakt, want buiten deze storing om.


## 04-09-2026 — Marktplaats kreeg de Engelse tekst en de verkeerde staat

Daniel stuurde een schermafdruk van zijn eigen advertentie: **(1357) Lilac
Profuomo Shirt - Men 45 - New With Tags**, met daaronder **Conditie: Zo goed als
nieuw**. Twee dingen fout tegelijk, met twee losse oorzaken.

### 1. De titel stond in het Engels

Omnivaleur belooft: je tikt in het Engels in, wij vertalen naar het Nederlands
voor Marktplaats en 2dehands. Die vertaling zat op élke plek die een
'create'-opdracht klaarzet apart ingebouwd — publiceren (`_build_dutch`/`_pick`),
verversen en herplaatsen (`localize_item_for_platform`) — en op één plek niet:
`herstel_vastgelopen_werk` in `backend/services/relist.py`. Dat is de
reddingsronde die elke zes uur advertenties oppikt die tussen weghalen en
terugplaatsen zijn blijven hangen. Die bouwde zijn payload uit de kale
databaserij, en dat is de Engelse tekst uit het dashboard. Dezelfde regel sloeg
ook de vaste slottekst van de verkoper over.

Er ging technisch niets mis, dus er kwam ook geen foutmelding: de advertentie
stond gewoon in het Engels online.

Gerepareerd, en daarnaast een vangnet gelegd zodat "elk pad moet er zelf aan
denken" niet nóg een keer misgaat:

- elke localisatie zet nu een taalstempel in de payload (`crosslist.TAAL_VELD`);
- `_zet_taal_goed` in `backend/api/jobs.py` zeeft daarop, op de enige plek waar
  élke opdracht langskomt: de uitgifte aan de extensie. Wat er zonder stempel
  langskomt wordt daar alsnog vertaald en teruggeschreven. Dat repareert meteen
  de opdrachten die nu al in de wachtrij staan.
- `_met_slot` en het lezen van de slottekst staan niet meer binnen
  `publish_to_platforms` maar op moduleniveau, zodat een ander pad ze niet meer
  kán missen.

Vertalen zelf is opgesplitst in `_vertaal` (synchroon, de enige kopie van de
logica) en `_translate_with_claude` (dezelfde functie in een draad). Zonder die
splitsing kon de uitgifte — een gewone `def` — er niet bij.

### 2. De staat klopte niet met wat er in Omnivaleur stond

`selectCondition` in `extension/content/shared.js` had per staat een rijtje
LETTERLIJKE opties en koos het eerste rijtje-woord dat exact in de conditielijst
van die categorie stond:

    new_with_tags: ["Nieuw met etiket", "Nieuw", "Zo goed als nieuw"]

Marktplaats spelt de "nieuw met kaartje"-optie per categorie anders — "Nieuw met
prijskaartje" (zie `mp_enrich._onze_conditie`), "Nieuw met etiket", "Nieuw met
label" (zie `vinted.js`) — en het rijtje kende er precies één van. Paste die niet
en bood de categorie ook geen kale "Nieuw", dan viel de keuze door naar het derde
woord: "Zo goed als nieuw". Precies wat er bij Daniel op het scherm stond.
Onzichtbaar, want `verifyMpGroupFields` controleert of het veld gevuld is, niet
of er het juiste in staat.

Vanaf 1.0.294 wordt er niet meer geraden hoe Marktplaats het deze week spelt,
maar gelezen wat er in de lijst staat: elke optie krijgt een trap toegekend op
grond van de woorden die erin voorkomen (`conditieTrap`), en we nemen de optie
die het dichtst bij onze eigen staat ligt. Bij gelijke afstand wint de lagere —
een artikel mooier voorstellen dan het is kost een retour. Begrijpen we geen
enkele optie, dan blijft het veld leeg en houdt `verifyMpGroupFields` het
plaatsen tegen met de lijst die er wél staat, in plaats van zomaar de eerste
optie in te vullen (dat was "pak de eerste", en de eerste is bijna altijd
"Nieuw").

Bij het meten bleek `conditionSelect` dezelfde valkuil te hebben: die zocht de
conditielijst op vier letterlijke woorden, dus een categorie met uitsluitend
samengestelde opties werd helemáál niet gevonden — leeg veld, en de eindcontrole
zweeg omdat die het veld ook niet vond. Die zoekt nu ook op betekenis.

### Bewijs

- `tests/conditie-marktplaats-test.js` — de echte code uit shared.js tegen zes
  conditielijsten × vijf staten, twee keer gedraaid: met de huidige versie en met
  die van commit 4687587. VOOR: 10 van de 30 verkeerd. NA: 0.
- `tests/test_marktplaats_vertaling.py` — 13 controles, waaronder een
  voor-en-na-proef die de oude `herstel_vastgelopen_werk` uit git laadt en
  aantoont dat die de Engelse titel wegschreef.

### Openstaand

- Welke spelling Marktplaats op Kleding | Heren > Overhemden precies gebruikt is
  van hieruit niet te meten (marktplaats.nl is vanaf de bouwomgeving niet
  bereikbaar). Dat hoeft ook niet meer: de reparatie leest de lijst in plaats van
  hem te kennen, en de proef draait alle spellingen die in deze code zijn
  vastgelegd. Ziet Daniel na 1.0.294 nog een verkeerde staat, dan staat in de
  extensielog de regel `conditie: "<staat>" -> "<keuze>" (uit: <hele lijst>)` —
  daarmee is het in één keer na te rekenen.
- 1.0.289 tot en met 1.0.294 staan geen van alle in de Chrome Web Store. De
  vertaalreparatie werkt wél meteen: die zit in de server.
- De halswijdte op diezelfde advertentie stond op "Overige halswijdtes" terwijl
  het item maat 45 heeft. Niet aangeraakt — apart onderzoek waard.

## 04-09-2026 — Toon (dejuistetoon): "de Lederhosen verschijnen niet op Marktplaats"

Zijn melding via Daniel: *"Wederom aan het plaatsen zoals gisteren komt niet echt
door op marktplaats, net aantal Lederhosen gedaan zie ze niet verschijnen?"* Met
een foto van de balk: "36 jobs queued — Calm mode is spacing them out".

Nagemeten op zijn eigen account (96e30080…), niet beredeneerd. De hele dag staat
in zijn opdrachtenlogboek en dat leest als één sluitend verhaal.

**Publiceren op Marktplaats werkt bij hem gewoon.** Twaalf advertenties zijn er
vandaag echt bij gekomen, alle twaalf met een advertentienummer, en alle twaalf
teruggevonden op zijn openbare verkoperslijst (`lrp/api/search`,
sellerId 17981431, 288 advertenties, gedateerd "Vandaag"). Daar valt niets te
repareren.

**Maar er zat geen enkele Lederhosen bij, en dat klopt.** Tussen 16:02 en 16:35
NL zette hij 51 publicaties klaar. Calm mode staat bij hem aan, dus er gaat 3 tot
8 minuten tussen twee acties: in de 52 minuten dat zijn Chromebook aan bleef zijn
de eerste elf gelopen (kleden, tafelkleden, kussens). De dertien Lederhosen
stonden verderop in de rij en waren nog niet aan de beurt.

**Om 16:58 NL viel zijn extensie stil.** Laatste hartslag 14:58:50 UTC, user
agent CrOS. Daarna geen enkele poll meer. Zonder draaiende Chrome gebeurt er
niets, dat is een gegeven van het product.

**Om 20:23 NL waren de resterende 39 in één seconde weg.** Allemaal met
`{"cancelled": "by user"}` en allemaal zonder ooit opgepakt te zijn. Dat is de
knop naast de wachtrijbalk. Diezelfde ochtend gebeurde het al een keer, om 07:31
en 07:33, samen 93 opdrachten. De dertien Lederhosen zaten in die 39.

### Wat er stuk was, en gerepareerd is

**1. De knop "Cancel" wiste de hele wachtrij achter een venster dat over één
advertentie sprak.** De tekst was: *"Cancel the current publishing action? Use
this if it got stuck… The item will show as not listed."* Enkelvoud, terwijl er
zesendertig aan hingen. En hij staat pal naast een balk die kan zeggen "nothing
is running" — wie dat leest denkt dat hij iets vastgelopens opruimt.

De knop zegt nu wat hij gaat doen: **"Stop this one"** zolang er echt iets draait
(en dan blijft de rij eromheen staan, want die is niet vastgelopen maar nog niet
aan de beurt), en **"Clear queue (36)"** als er niets loopt. In dat tweede geval
vraagt het venster met zoveel woorden of hij alle 36 wachtende publicaties wil
weggooien, zegt erbij dat de rij vanzelf loopt zodra Chrome openstaat, en dat
zijn artikelen blijven bestaan zodat hij ze opnieuw kan publiceren.

Voor-en-na bewezen met dezelfde proef op beide versies
(`tests/annuleerknop-wachtrij-test.js`, draait de échte functies uit app.html):
op de oude versie annuleert één klik bij 1 lopende + 35 wachtende alle 36; op de
nieuwe alleen die ene. Zeven van de elf controles falen op de oude versie.

**2. De offline-waarschuwing kon hem vandaag onmogelijk bereiken.** Die mail gaat
uit als de extensie drie uur stil is terwijl er drie uur werk wacht, maar alleen
tussen 10:00 en 20:00 NL. Zijn laptop ging om 16:58 uit, dus drie uur stilte was
pas om 19:58 bereikt en toen viel het venster net dicht. Gemeten op zijn echte
gegevens, uur voor uur: met de grens op 20:00 kwam er die dag op geen enkel
moment een mail uit; met de grens op 22:00 om 20:00 NL wél, over 39 wachtende
opdrachten, 23 minuten vóór hij de rij weggooide. Grens staat nu op 22:00.

**3. Massaal annuleren zette de wachtrij meteen weer vol met scans.** Elke
geannuleerde plaatsing vroeg om een scan erachteraan. Die dubbelcontrole leest en
schrijft niet in dezelfde stap, dus van de 39 tegelijk glipten er vier
doorheen: na het legen stonden er vier identieke Marktplaats-scans klaar. Een
opdracht die nooit is opgepakt heeft ook nooit een tabblad gehad, dus daar valt
niets op te halen — de scan komt er nu alleen nog achteraan als de extensie er
echt aan begonnen was.

### Wat NIET gerepareerd is, met zoveel woorden

- **Zijn 39 publicaties komen niet vanzelf terug.** Ze staan als mislukt in zijn
  overzicht ("Publishing was cancelled — the item is not listed"), geen van de 39
  heeft een advertentienummer, dus opnieuw publiceren maakt géén dubbele
  advertentie. Dat is bewust aan hem gelaten: 39 advertenties namens een klant
  online zetten is niets wat wij ongevraagd doen.
- **Een uitgezette computer blijft een uitgezette computer.** De permissie
  `background` (extensie 1.0.288) houdt het profiel in leven als het laatste
  venster dichtgaat, maar wacht nog op de Web Store. Tegen een Chromebook die in
  slaap gaat helpt niets.
- **Waaróm zijn extensie om 16:58 stilviel is niet gemeten.** Hij bediende het
  dashboard om 20:23 nog wel, dus er stond ergens een browser open. Of dat een
  ander apparaat was, of dezelfde Chromebook met een uitgeschakelde extensie, is
  van hier niet te zien.
- De MOET ZEKER-storing `verkeerde-categorie-toegewezen` staat los hiervan nog
  open. Zijn "Grand Foulard Groot 264/128 cm" staat onder "sieraden damestassen",
  wat in datzelfde straatje past.

Geen extensiewijziging, dus geen versiebump. 898 python-tests groen (was 898,
twee nieuwe erbij), alle JS-proeven groen.

## 05-09-2026 — Toon (dejuistetoon): de 39 zijn opnieuw ingediend, 29 aantoonbaar online

Zijn antwoord op de mail van gisteravond: *"Zet jij die 39 maar weer actief. Zo
schiet het wederom niets op."* Dus gedaan, en nagemeten in plaats van beloofd.

**Hoe.** Niet met een los reparatiescript maar langs `publish_to_platforms`, het
gewone publicatiepad, zodat elke bestaande controle meedeed: eigendom, ontbrekende
velden, de verantwoordelijke partij, de tweelingcontrole en de "staat er al een
levende advertentie" -controle. Vooraf droog gedraaid: 0 validatieproblemen op 39,
1 pair geblokkeerd. Uitkomst: **38 opnieuw in de wachtrij, 1 overgeslagen** omdat
"Soepele grand foulard kleed uit Thailand" om 08:21 al opnieuw live was gegaan
(m2439164517). Die overslag is het bewijs dat de dubbelbeveiliging werkt; zonder
die stap had hij daar twee advertenties gehad.

**Twee rubrieken eerst rechtgezet.** "Grand Foulard Groot 264/128 cm" stond onder
`sieraden damestassen` en "Unisex originele Lederhosen kniebroek" onder
`unisex jassen`. Alle 14 gebruikte rubrieken zijn nagelopen tegen de
Marktplaats-tabel in `extension/background.js`; deze twee waren de enige foute.

**Uitkomst, gemeten op zijn openbare verkoperslijst** (`lrp/api/search`,
sellerId 17981431), niet op onze eigen administratie:

- vóór: 288 advertenties, ná: **317**.
- **29 van de 39 gepubliceerd én teruggevonden** op die lijst, met de juiste
  rubriek-id, prijs en datum "Vandaag".
- 1 stond al live (zie boven).
- 1 mislukte op 2dehands, zie hieronder.
- 1 kreeg wél een advertentienummer (m2439189692, "Foulard plaid zeilschepen")
  maar staat niet op zijn openbare lijst en zijn pagina geeft 404, 25 minuten na
  plaatsing, terwijl advertenties van vóór én ná hetzelfde moment er wél staan.
  Geen dubbele advertentie van hemzelf gevonden. Dit is aan de kant van
  Marktplaats en alleen in zijn eigen overzicht te zien. **Openstaand.**
- 7 stonden nog te wachten toen zijn extensie om 11:29 NL opnieuw stilviel.
  Ze blijven staan en lopen vanzelf zodra Chrome weer aan is. Zijn
  offline-waarschuwing komt rond 14:29 NL als hij wegblijft (drempel 3 uur stil
  én 3 uur wachtend; beide worden gehaald).

**Foto's: geen probleem, wél gecontroleerd.** De advertentiepagina toont er 5
terwijl zijn artikelen er 6 tot 12 hebben. Tegenmeting op advertenties van juni,
die al maanden goed staan: óók 5. Het is een grens van de pagina zelf, niet van
onze upload.

### Wat er onderweg is gerepareerd

**1. 2dehands: "Geen postcode ingevuld".** De enige 2dehands-opdracht van de 39
kwam terug met `contactInformation.postCode=LEEG`. Datzelfde account publiceerde
daar al tien keer met succes met precies dezelfde code (10 done, tegen 2 keer
deze fout: 03-09 en 05-09). Het contactblok wordt dus door de site zelf uit het
account gevuld en was op die twee momenten alleen nog niet aangekomen.
`submitListing` wacht nu tot acht seconden op dat veld voordat ze klikt, en
blijft het leeg dan weigert ze te plaatsen met een zin die zegt wat de verkoper
zelf moet doen. `tests/postcode-wachten-test.js`. Extensie 1.0.295 — **staat nog
niet in de Web Store, dus dit helpt Toon vandaag niet.**

**2. Een grand foulard is geen sjaal.** De classificatieprompt zegt over de
sieraden-tak "pick it for anything worn or carried as an accessory", en een
foulard is in gewoon Nederlands een sjaal. De keyword-terugval kende de
combinatie niet en gaf niets terug, dus de foute keuze bleef staan. Nu op drie
plekken geregeld, zelfde patroon als bij schoenen: woordenlijst, prompt, en een
correctie achteraf die een keuze búiten de woontak terugzet naar
`wonen plaids en woondekens`. Binnen de woontak blijven we eraf. Een losse
"foulard" blijft een sjaal. `tests/test_grand_foulard_is_geen_sjaal.py`, mét
tegenproef.

**3. De wachtrijbalk zweeg over de looptijd zodra Calm mode uitstond.** Hij had
vandaag 38 opdrachten in de rij en Calm mode UIT, en las alleen "the extension is
about to start — within ~15 seconds". Dat is precies het beeld waar hij op 03-09
op afknapte. Bovendien rekende de schatting met het gat tussen twee opdrachten in
plaats van met de hele opdracht. Gemeten op zijn account, 39 monsters uit twaalf
uur: **gat 16 s, werk 29 s, van start tot start 46 s** — bijna een factor drie
verschil. De server meet nu ook `seconds_per_job`; de balk gebruikt dat voor de
looptijd, met en zonder Calm mode, vanaf drie opdrachten in de rij.

Het gat van 30 seconden is trouwens geen instelling van ons: `POLL_INTERVAL_SECONDS`
staat op 15, maar Chrome legt `chrome.alarms` in MV3 een ondergrens van 30 seconden
op. Eén advertentie per minuut is dus de bodem zolang we via alarms werken.

### Wat NIET is opgelost

- **Een uitgezette computer blijft een uitgezette computer.** Om 11:29 NL viel
  zijn extensie opnieuw stil, met 9 opdrachten te gaan. De `background`-permissie
  (1.0.288) wacht nog op de Web Store en helpt tegen een dichtgeklapt venster,
  niet tegen een Chromebook die slaapt.
- **m2439189692 is niet publiekelijk zichtbaar.** Zie boven.
- **De Anthropic-tegoeden zijn op.** Elke vertaalaanroep gaf vandaag
  `credit balance is too low`. Voor Toon maakte dat niets uit — Nederlands naar
  Nederlands, gecontroleerd: titels identiek, tekst identiek op de vaste
  slottekst na — maar op de server raakt het alles wat op Claude leunt:
  vertalingen naar Engels voor Vinted en eBay, de categorie-indeling bij import,
  de mailagent. Of Railway dezelfde sleutel gebruikt is van hier niet te lezen.
  **Actie voor Daniel: tegoed bijvullen en het controleren.**

898 → 915 python-tests groen, alle JS-proeven groen.

## 05-09-2026 — Amanda: waarom dezelfde advertentie elke dag terugkwam

Amanda Haas mailde drie dingen: "hij blijft dezelfde advertenties er opnieuw
opzetten", "hij importeert nieuw geplaatste advertenties niet van marktplaats",
en "bij Vinted blijft hij elke keer steken op de categorie". Plus het antwoord op
Daniels vraag: die toestemming gaf ze "elke keer als een nieuwe pagina werd
geopend, rechts van de werkbalk".

Alle vier nagemeten in haar account (0b28c1ce-b913-4431-a765-395ac1e22100, 479
artikelen).

### 1. De dubbele advertenties: een lopende band, geen toeval

Haar "AH hamster knuffel kok nieuw" stond op 05-09 met drie identieke
Marktplaats-advertenties tegelijk online: m2439045744, m2439067409 en
m2439186265, geplaatst op drie opeenvolgende dagen. Idem voor haar Jumbo
legpuzzel en haar teckelbeeldje. Zes overtollige advertenties in totaal, en er
kwam elke dag eentje bij.

Het mechanisme, bewezen op haar opdrachtenlogboek:

1. Herplaatsen zet de BESTAANDE advertentierij op 'relisting' en laat het oude
   advertentienummer erop staan.
2. Kwam de nieuwe advertentie binnen, dan zocht de afronding een rij met dát
   nieuwe nummer (bestaat niet) of een rij zónder nummer (bestaat ook niet, want
   de oude rij hééft er een). Dus zette hij er een NIEUWE rij naast en bleef de
   oude eeuwig op 'relisting' staan.
3. De reddingsronde (`herstel_vastgelopen_werk`, elke zes uur) leest 'relisting'
   als "halverwege blijven steken" en zette er weer een plaatsing voor klaar.
   Advertentie erbij. Elke ronde.

Dit is niet Amanda-specifiek: op dat moment stonden er 72 rijen op 'relisting'
verdeeld over zes verkopers. Het is ook precies het patroon waar Marktplaats
accounts voor blokkeert.

Gerepareerd op twee plekken, zodat één gemiste schakel niet meteen weer een
advertentie kost: de herplaatsopdracht draagt nu `_vervangt_listing_id` en de
afronding werkt díé rij bij, en de reddingsronde kijkt eerst of er al een andere
levende advertentie voor hetzelfde artikel op hetzelfde kanaal staat.

Haar zes overtollige advertenties staan als verwijderopdracht klaar
(`scripts/herstel_dubbele_advertenties.py`), telkens op advertentienummer. De
extensie zoekt eerst op dat nummer en weigert te gokken bij twijfel, dus er kan
nooit de verkeerde weg.

### 2. "Importeert nieuw geplaatste advertenties niet" — hij vond ze wél

Op haar te-beoordelen lijst stonden 117 Marktplaats-advertenties. Daarvan hingen
er 111 allang aan een artikel in haar overzicht: hun advertentienummer stond
gewoon in `listings`. Het waren advertenties die WIJ hadden geplaatst of
herplaatst — elke publicatie levert een nieuw nummer op, en een nummer dat de
vorige scan niet kende gold als "nieuw, de verkoper moet beslissen".

De zes advertenties die ze écht zelf op Marktplaats had gezet verdronken daarin.
Dat leest als "hij importeert mijn nieuwe advertenties niet".

Nu geldt: hangt het advertentienummer al aan een artikel, dan valt er niets te
beslissen en staat het op 'linked'. Haar lijst is teruggebracht van 122 wachtende
naar precies de 6 die van haar zijn (o.a. "Switch On koffieapparaat nieuw",
"Cougar Voetbaltafel Freestyle pro White").

### 3. Vinted: blijven steken op de categorie

Zeven van haar mislukte Vinted-plaatsingen eindigen letterlijk met "Kies een
subcategorie", bij "wonen plaids en woondekens", "wonen beddengoed" en "antiek
gereedschap en instrumenten".

Vinted heeft twee wegen naar een categorie. De boom aflopen klikt netjes door tot
er geen niveau meer onder zit, maar kent alleen KLEDINGpaden. Zoeken op een
trefwoord klikte één regel aan en stopte — en zo'n gevonden regel is bij wonen en
antiek zelden een eindpunt. Amanda verkoopt brocante, dus alles bij haar loopt via
die tweede weg.

De zoek-terugval daalt nu na de klik nog maximaal drie niveaus af, met dezelfde
keuzelogica als de boom, tot Vinted de categorie echt vastlegt.

### 4. De toestemming rechts van de werkbalk

Dat is Chrome's site-access per extensie, en die staat bij haar op "Als je erop
klikt". Dan ziet de extensie een pagina pas nadat je op het icoontje hebt geklikt
— per pagina. Onze werk-tabbladen openen zichzelf, dus er gebeurt niets: geen
invulstap, geen melding, en na drie minuten "Extension timed out". Haar logboek
staat er vol mee.

Chrome geeft die stand gewoon terug via `permissions.contains()`, ook voor
host-permissies die in het manifest staan. De extensie stopt nu meteen met een
leesbare uitleg als Chrome met zoveel woorden nee zegt, en gaat gewoon door bij
twijfel. De popup heeft een rode balk met een knop die het in één klik goedzet.

Dat laatste is het enige punt waar Amanda zelf iets moet doen: één klik in de
popup, of in Chrome zelf de site-toegang op "Op alle sites" zetten.

### Wat NIET gerepareerd is, met zoveel woorden

- **De MOET ZEKER-storing `verkeerde-categorie-toegewezen` blijft open.** Het
  Vinted-deel ervan is hierboven opgelost, maar de melding van
  info@zilverwebsite.nl gaat over iets anders (zilver ontbreekt in de lijst, met
  een HTTP 500). Die sleutel afmelden zou die klant een onwaar bericht sturen.
- **Andere verkopers hebben ook dubbele advertenties.** Gemeten op 05-09:
  3bfbed2c-e8a7-4b28-8870-f3581d48afc5 heeft 11 overtollige advertenties op
  2dehands en 5 op Marktplaats, 96e30080-ab81-47ac-8626-e8637f1e2a9e heeft er 1.
  De oorzaak staat stil, maar wat er al staat is niet opgeruimd — `scripts/
  herstel_dubbele_advertenties.py --user <uuid>` doet dat, per verkoper.
- **Of Amanda's Chrome écht op "Als je erop klikt" staat is van hier niet te
  zien.** Het past op alles wat ze beschrijft en op haar time-outs, maar het
  bewijs komt pas van haar eigen machine — vanaf 1.0.296 zegt de extensie het
  zelf in plaats van drie minuten te zwijgen.
- **De extensie 1.0.296 moet nog naar de Chrome Web Store.** Tot dan werkt de
  serverkant (dubbele advertenties, importlijst) al wel; Vinted en de
  toestemmingsmelding niet.

Voor-en-na bewezen: 4 van de 6 nieuwe python-proeven en beide JS-proeven falen op
de versie van vóór deze reparatie. 925 python-tests groen, alle JS-proeven groen.

## 05-09-2026 — Toon, vervolg: 20 advertenties stonden groen en waren weg

Na het terugzetten van de 39 zijn account doorgelicht. Drie dingen gevonden.

**1. Twintig advertenties stonden "live op Marktplaats" en bestonden niet meer.**
Zijn dashboard zei het van 274 stuks; zijn openbare verkoperspagina toonde er 317
en twintig van onze 274 zaten daar niet bij. Alle twintig apart nagelopen: 404 of
410 op hun eigen advertentiepagina. Twee onafhankelijke bewijzen per advertentie,
dus zijn ze op `delisted` gezet. Dat publiceert niets; het maakt alleen de knop
weer beschikbaar. Zeventien zijn kleine tapijtjes van 10 tot 20 euro uit één
importronde, drie zijn recent.

**Waarom geen van beide controles dit zag, aanwijsbaar:**
- `services/polling.py` vraagt een pagina op mét de cookies van de verkoper en
  slaat over wie geen koppeling heeft. Toon heeft alleen een `_settings`-rij in
  `platform_credentials`. Zijn advertenties kregen dus elke ronde netjes een
  `last_checked`-stempel (stond vandaag) zonder ooit te zijn nagekeken, en
  `not_found_count` bleef 0.
- De controle in de extensie leest zijn eigen "Mijn advertenties", en dat
  overzicht is bij een zakelijk account leeg. Juist daarom mag een lege uitkomst
  daar nooit als "weg" tellen.

Daarom `scripts/controleer_advertenties_online.py`: de openbare zoek-API heeft
geen van beide bezwaren. Het script SCHRIJFT NIETS, vastgelegd als proef.

**2. Eenentwintig artikelen zonder rubriek, dus onpubliceerbaar.** Zeven daarvan
vielen net naast de woordenlijst: die kijkt op hele woorden, dus "kleed" ving wél
"kleed" maar niet "kleedje", "wandkleed", "sprei", "tafelloper" of "kelim". Die
zeven vullen zichzelf nu bij het publiceren. De overige veertien zijn kleding
zonder geslachtssignaal in de titel; daar blijft het model voor nodig, en dat
kan pas als het Anthropic-tegoed is bijgevuld.

**3. Dubbelverkoop: gecontroleerd, geen risico.** Twee artikelen stonden verkocht
op het ene kanaal en actief op het andere. Beide advertenties zijn in
werkelijkheid al weg (Marktplaats 404, 2dehands 410). Alleen onze administratie
liep achter. Wel het noteren waard: de verwijderopdracht voor "Perzisch tapijt
Bokhara" was op 04-09 om 07:31 meegegaan met de knop die zijn hele wachtrij
wiste. Van de 31 weggegooide verwijderopdrachten van die ochtend waren de meeste
verversingsparen die vannacht om 02:42 alsnog gelopen zijn.

**Stand aan het eind:** 26 artikelen staan niet op Marktplaats terwijl er wel een
advertentieregel voor bestaat. Vijfentwintig daarvan zijn meteen te publiceren,
één mist nog een omschrijving. Bewust NIET ongevraagd gedaan: van een advertentie
die door Marktplaats of door hemzelf is weggehaald valt van hier niet te zien of
hij het artikel intussen buiten ons om heeft verkocht, en dan zetten we iets te
koop wat er niet meer is. Dat is een vraag aan Toon, geen aanname van ons.

Zijn extensie viel om 11:29 NL opnieuw stil met 9 opdrachten in de rij.

## 05-09-2026 (vervolg 2) — de 26 staan terug online, en een correctie op mijn eigen bewijs

**Correctie eerst.** Hierboven staat bij de twintig dode advertenties "404 of 410
op de eigen pagina" als tweede bewijs. Dat bewijs deugde niet. Ik vroeg die
pagina's op als `https://www.marktplaats.nl/v/a/{nummer}`, en die vorm geeft
ALTIJD 404, ook voor een advertentie die springlevend is. Dat stond al met zoveel
woorden in `extension/background.js:3106` en in de kennisbank, en ik heb het
vandaag toch gebruikt. Bewezen door de controlemeting: van 26 advertenties die
vandaag nieuw online kwamen gaven alle 26 een 404 op die url, terwijl er 25 gewoon
op zijn openbare verkoperslijst staan. De echte url zit in `vipUrl` van de zoek-API
en ziet eruit als `/v/kleding-heren/broeken-en-pantalons/m2439260097-mooie-lederhosen`.

De conclusie over die twintig blijft wel staan, want het eerste bewijs was de
volledig opgehaalde openbare verkoperslijst, en juist die meting heeft zich
vandaag bewezen. Maar het was één bewijs, geen twee.

**Daniel gaf groen licht om de 26 terug online te zetten.** Uitkomst:

- 3 van de 26 kende ons systeem al als verkocht op een ander kanaal. Die zijn
  overgeslagen: een verkocht artikel gaat er niet opnieuw op. Het waren "Kelim
  kleedje rood zwart beige 127/59", "Oosters Tapijtkussen 48/42" en "Perzisch
  tapijt Bokhara 124/72".
- De overige 23 zijn via de gewone publicatieweg in de wachtrij gezet, dus alle
  bestaande controles liepen mee. 23 in de rij, 0 mislukt bij het inplannen.
- 21 daarvan staan nu aantoonbaar op zijn openbare verkoperslijst (349 stuks,
  was 325 voor deze ronde).
- 1 mislukte tijdens het plaatsen omdat Chrome halverwege dichtging ("Kelim
  kleedje Tunesië"). Opnieuw in de rij gezet.
- 1 blijft een raadsel: "Foulard plaid zeilschepen dorp boerderij 160/98". Die
  kreeg vandaag voor de tweede keer een vers advertentienummer (m2439189692 op
  09:04, m2439215272 op 10:05) en staat allebei de keren niet op zijn openbare
  lijst. Twee keer hetzelfde artikel, twee verschillende nummers, allebei
  onzichtbaar. Dat wijst op een weigering aan de kant van Marktplaats voor dit
  specifieke artikel, niet op onze kant. Alleen Toon ziet in zijn eigen overzicht
  wat er staat.

**De rubriekreparatie van vanmorgen werkt in het echt.** Drie artikelen gingen
zonder rubriek de rij in ("Kelim loper 98/35", en twee keer "Kleedje recycle
geweven kleurrijk") en kregen bij het publiceren vanzelf "wonen tapijten en
kleden" toegewezen. Dat is de woordenlijst die vanmorgen is uitgebreid met
kleedje, kelim, wandkleed, sprei en tafelloper.

## 05-09-2026 (later die dag) — Daniels eigen account: opgeruimd, en het gat in de reparatie gevonden

Daniel gaf toestemming om de dubbele advertenties op zijn eigen verkoopaccount
(`3bfbed2c`) op te ruimen en vroeg of de zekerheid vanuit zijn account omhoog kon.
Dat kon, en het leverde meteen een tweede storing op.

**Het gat.** De reparatie van vanochtend nam de oude advertentierij alleen over
als die nog op `relisting` stond. In het echte verloop staat daar nooit meer
`relisting`: het inplannen zet hem daarop, maar de GESLAAGDE verwijdering zet
dezelfde rij meteen daarna op `delisted` (`_verwijderdoelen` pakt hem op het
rij-id uit `_refresh_rollback`). We vingen dus precies het zeldzame geval af, de
mislukte verwijdering, en lieten het normale geval door. Aanwijsbaar bij Amanda:
haar Waltherglas-schalen kregen vanochtend om 09:44 UTC alsnog een tweede
advertentie, na de deploy van de eerste reparatie.

Nu neemt het merkteken `_vervangt_listing_id` ook een rij op `delisted` over
(`active` nooit), en opdrachten die al in de wachtrij stonden vinden hun rij via
de bijbehorende verwijdering. Commit 8b50ea5, 947 tests groen.

**De live proef, op zijn eigen account.** Artikel (1275) Grey Profuomo Half Zip
had om 08:51 UTC een herplaatsing lopen: verwijdering geslaagd, plaatsing
ingepland voor 10:20. Die opdracht droeg het merkteken nog niet. Voorspelling
vooraf: met de oude code komt er een vierde rij bij, met de nieuwe wordt rij
`00c61482` hergebruikt. Ik heb de plaatsing naar 10:30 verzet zodat de deploy
er eerst was. Uitkomst om 10:30:32: advertentie m2439226665, rij `00c61482`
bijgewerkt, geen rij erbij. Precies zoals voorspeld.

**Opgeruimd.** 17 verwijderopdrachten klaargezet, 16 uitgevoerd zonder één fout,
de laatste liep nog. Zijn te-beoordelen lijst ging van 66 onterechte naar 0.
Bij Amanda stond er nog één dubbele over (Waltherglas), ook klaargezet.

**Twee dingen die dit opleverde en die nog openstaan:**

1. **De Chrome Web Store staat nog op 1.0.294.** Daniel zegt 1.0.296 zelf te
   hebben geüpload, maar het update-endpoint van Google geeft nog steeds 1.0.294,
   en zijn eigen kopie meldde diezelfde versie. Ook 1.0.295 is dus nooit
   doorgekomen. Tot Google hem doorlaat werken de Vinted-subcategoriefix en de
   melding over de site-toegang bij Amanda niet.
2. **Advertenties die wij "live" noemen maar er niet meer zijn.** Bij Daniel 21
   van 93, bij Amanda 21 van 450 (Toon had er 20; zie de vorige aantekening).
   BELANGRIJK voor wie dit oppakt: de openbare verkoperspagina alleen is geen
   bewijs. Ik heb Amanda's 21 stuk voor stuk nagekeken op
   `link.marktplaats.nl/<nummer>`: 23 gaven 404 of 410, maar 2 stonden gewoon
   online (200). Eén op de tien was vals alarm. Twee bronnen, altijd.

**Klein maar hinderlijk:** het opruimscript zette ook een verwijderopdracht klaar
voor een dubbele Shopify-advertentie. Shopify en eBay lopen via hun eigen API, dus
die opdracht werd nooit opgepakt en bleef in de wachtrij staan. Geannuleerd, en
het script slaat die kanalen nu over (commit d77de10). Die ene Shopify-dubbel
staat er dus nog.

## 05-09-2026 (avond) — Papa's Plectrums: waarom er in drie weken geen enkele advertentie is geplaatst

Egbert Brouwer (info@papas-plectrums.nl, proef tot 19-09) meldde: "Ik heb 1
artikel gepubliceerd naar MP, ik kreeg geen foutmelding of zo. Na 5 minuten was
het artikel nog niet zichtbaar." Uitgezocht, en het is groter dan die ene
advertentie.

**Gemeten aan zijn account (niet geschat):**

- 5533 artikelen, en alle 5533 hebben een advertentierij `marktplaats / active`.
  Zijn hele voorraad is ingelezen vanaf zijn eigen zakelijke Marktplaats-account,
  dus alles staat daar al.
- 351 opdrachten sinds 13-08. Daarvan 305 plaatsingen op 2dehands: 274
  geannuleerd, 31 op fout, **nul geslaagd**. Verder 40 Marktplaats-scans en 6
  2dehands-scans. Er is nooit één `marktplaats / create` geweest.
- Op de dag van zijn test is er geen enkele opdracht aangemaakt. Zijn laatste
  opdracht dateert van 04-09 08:07.

**Oorzaak van zijn klacht.** `publish_to_platforms` slaat een kanaal bewust over
als het artikel er al op staat, en gaf dat terug als `status: "active"`. Het
scherm bepaalde "gelukt" door uitsluiting (`!== 'error' && !== 'duplicate'`), dus
dat telde als succes en de melding luidde "Queued for Marktplaats, the extension
starts right away". Er is nooit iets in de wachtrij gezet. Bij hem gold dat voor
élk artikel, want ze staan er allemaal al op.

`"active"` betekende bovendien op de API-kant (eBay, Shopify) juist wél zojuist
gepubliceerd. Eén woord voor twee tegengestelde uitkomsten.

**Gerepareerd.** Nieuwe status `already_live` met een eigen tekst, op de drie
plekken waar het dashboard publiceert: het losse venster, Bulk publish en Save &
publish (die derde las het antwoord van de server voorheen helemaal niet).
Voor-en-na bewezen met `tests/publiceren-zegt-queued-terwijl-er-niets-gebeurt-test.js`:
op de vorige commit komt er "Queued for Marktplaats", op de nieuwe "Not
published: Marktplaats: Already live...". 947 pytests groen.

**Zijn echte blokkade staat nog open: 2dehands.** 276 van de 305 mislukkingen
zeggen "The 2dehands listing form never opened". De extensie heeft er op 04-09
twee keer bij gemeten: "API 200, 0 advertenties, ingelogd op 2dehands: nee" en
daarna "API 401 ... ingelogd: nee". Zijn browser heeft dus geen 2dehands-sessie.
Hij moet zelf kijken of hij daar een account heeft. Dat is de vraag in de
conceptmail.

**Correctie op de aantekening van vanmiddag.** Daar stond dat er twee kopieën van
de extensie naast elkaar draaiden (1.0.258 en 1.0.281 op 03-09). Nagemeten per
tijdstip: 1.0.258 tot 09:48, 1.0.281 vanaf 09:58. Dat is één kopie die is
bijgewerkt, geen twee. Hij draait nu 1.0.281, de Web Store staat op 1.0.294.

**Waarschuwing bij de online-controle.** `controleer_advertenties_online.py`
meldt voor hem "STAAT ER NIET MEER: 699". Dat is géén bewijs: zijn openbare
verkoperslijst is afgekapt op 4900 advertenties (de bekende grens van ~5000) en
hij heeft er 5533. De 699 zitten simpelweg niet in de steekproef. Van de 4900 die
er wel in zaten werden er 4834 teruggevonden, alleen met een `a` ervoor
(Admarkt-nummering: wij bewaren `1521375186`, Marktplaats noemt het
`a1521375186`). Daardoor geeft `link.marktplaats.nl/<nummer>` bij hem altijd 404,
ook voor advertenties die gewoon online staan.

## 05-09-2026 (avond, tweede ronde) — Egbert had gelijk: hij was ingelogd, en 2dehands liep dood op de inlogpagina

Egbert Brouwer (papas-plectrums) mailde terug dat hij wél was ingelogd op
2dehands. Dat klopt, en het is nagemeten in plaats van aangenomen.

**Wat er gemeten is**

- 305 opdrachten voor 2dehands, nul geslaagd, nul voortgangsberichten. Elke
  afgebroken opdracht duurde 195 tot 230 seconden: dat is de bewaker van drie
  minuten, niet het werk. Bij andere verkopers duurt een geslaagde plaatsing op
  2dehands 10 tot 50 seconden (68 geslaagde plaatsingen gemeten).
- Zijn categorienummers bestaan gewoon op 2dehands. 728/748 (muziek,
  elektrische gitaren) geeft daar 2259 zoekertjes, op Marktplaats 4743. De
  categorieboom is op beide sites dezelfde. Categorie was dus niet de oorzaak.
- Van de 68 geslaagde 2dehands-plaatsingen zit er geen enkele in een
  muziekcategorie, maar dat komt doordat niemand anders muziek naar 2dehands
  publiceert. Het is een toevalligheid, geen oorzaak.
- In een echte browser (die van Daniel, niet ingelogd op 2dehands) komt
  `https://www.2dehands.be/plaats/728/748` NIET uit op een foutpagina maar op
  `https://www.2dehands.be/identity/v2/login?target=...`. Ons invulscript
  luistert alleen op `/plaats/*`, dus daar draait het niet, meldt niemand zich
  terug en loopt de bewaker drie minuten leeg. Dat is precies het waargenomen
  beeld.
- `/my-account/sell/api/listings` verwijst NIET door: zonder sessie 401 met
  twaalf bytes "Unauthorized", met sessie 200. Drie keer nagemeten (kale curl,
  uitgelogde echte browser, en Egberts eigen scan). Een 200 is dus een eerlijk
  "ingelogd".

**Twee eerdere beweringen rechtgezet**

1. "www.2dehands.be antwoordt op het plaatsadres met 401 zolang je niet bent
   ingelogd" klopt alleen voor een kale aanvraag zonder cookies, en verklaart
   niets: www.marktplaats.nl doet op hetzelfde adres precies hetzelfde. In een
   browser is het geen 401 maar een doorverwijzing.
2. "Zijn Marktplaats-opdrachten uit dezelfde ronde liepen wél door (15
   geplaatst)" was fout. Die 15 waren scans. Naar Marktplaats is er nooit één
   plaatsopdracht aangemaakt.

**Wat er is gebouwd (1.0.297)**

- Voor Marktplaats en 2dehands wordt vóór het openen van een tabblad aan de
  site zelf gevraagd of deze browser een sessie heeft, precies zoals dat voor
  Vinted al gebeurde. Geen sessie: geen tabblad, meteen een melding die zegt
  waar hij moet inloggen, en de rest van de wachtrij voor dat kanaal stopt.
  Bij twijfel (5xx, geen netwerk) gaat het werk gewoon door.
- Landt een werk-tabblad tóch op de inlogpagina, dan wordt dat meteen gemeld
  mét het adres waar het uitkwam, in plaats van drie minuten stilte.
- Bewijs: `tests/2dehands-loopt-dood-op-de-inlogpagina-test.js`, met `--oud`
  tegen de vorige commit, waar hij faalt.

**Openstaand**

- Egbert draait 1.0.281. De Chrome Web Store staat op 1.0.294 (nagemeten via
  de crx-doorverwijzing). Alles wat sinds 1.0.284 aan zijn klachten is
  gerepareerd zit dus wél in de Store maar nog niet bij hem. Hij moet naar
  chrome://extensions, Ontwikkelaarsmodus aan, en op "Extensies bijwerken"
  klikken. 1.0.297 moet nog geüpload worden.
- Blijft het na 1.0.294 misgaan terwijl hij is ingelogd, dan noemt de melding
  vanaf nu zelf het adres waar het tabblad terechtkwam. Dat is het volgende
  gegeven dat we nodig hebben.
