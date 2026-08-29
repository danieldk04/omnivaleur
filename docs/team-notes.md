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
