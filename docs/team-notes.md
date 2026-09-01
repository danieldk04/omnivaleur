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
