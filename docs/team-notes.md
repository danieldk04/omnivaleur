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
