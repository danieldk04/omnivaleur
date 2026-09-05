# Kennisbank — wat eerdere sessies hebben geleerd

Dit bestand staat in de repo en reist dus mee naar elk account en elke machine.
De losse geheugenbestanden onder `~/.claude/projects/.../memory/` zijn **per
account** en voor een tweede ontwikkelaar onzichtbaar; dit is de overdraagbare
kopie daarvan.

Lees dit samen met [team-notes.md](team-notes.md): team-notes is het dagboek
(wat er wanneer gebeurde), deze kennisbank is de les (wat je voortaan moet weten
om dezelfde fout niet nog eens te maken).

Nieuwste bovenaan. De datum is wanneer de les is vastgelegd of bijgewerkt.
Verwijzingen tussen lessen staan als "zie: naam-van-de-les" — zoek op die naam
in dit bestand.

Bijwerken: `python3 scripts/export_kennisbank.py` en het resultaat committen.

---

## marktplaats-advertentiepagina-url

*05-09-2026 — /v/a/{nummer} geeft ALTIJD 404, ook voor een levende advertentie; gebruik vipUrl of de openbare verkoperslijst*

Een Marktplaats-advertentie is niet op te vragen als
`https://www.marktplaats.nl/v/a/{nummer}`. Die vorm geeft altijd 404, ook voor
een advertentie die springlevend is. Hetzelfde geldt voor `/v/listing/{id}`.

De werkende url staat in het veld `vipUrl` van de zoek-API en heeft de vorm
`/v/{rubriek}/{subrubriek}/{nummer}-{slug}`, bijvoorbeeld
`/v/kleding-heren/broeken-en-pantalons/m2439260097-mooie-lederhosen`.

**Waarom:** op 05-09-2026 gebruikte ik `/v/a/{nummer}` als "tweede bewijs" dat
twintig advertenties weg waren. Later gaven alle 26 advertenties die diezelfde dag
nieuw online kwamen ook 404 op die url, terwijl 25 ervan gewoon op de openbare
verkoperslijst stonden. Het bewijs was dus geen bewijs. Het stond al in
`extension/background.js:3106` en ik heb het toch gebruikt.

**Hoe toe te passen:** wil je weten of een advertentie echt online staat, haal dan
de volledige openbare verkoperslijst op via
`https://www.marktplaats.nl/lrp/api/search?sellerIds[]={id}` en kijk of het
`itemId` erin zit. Dat is de meting die zich bewezen heeft. Zie
"scan-mag-nooit-leeghalen" en "marktplaats-publiceren-valkuilen".

---

## vinted-zoekterugval-stopt-op-tak

*05-09-2026 — Vinted's zoek-terugval klikte één regel aan en stopte, ook als daaronder nog subcategorieën zaten*

Vinted heeft twee wegen naar een categorie: de boom aflopen
(`walkVintedCategoryPath`, kent alleen KLEDINGpaden) en zoeken op een trefwoord
en de best scorende regel aanklikken. Die tweede weg stopte na één klik. Bij
wonen, antiek, kunst en muziek gaat Vinted's boom daar nog een of twee niveaus
onder door, dus het veld bleef leeg en het formulier weigerde met "Kies een
subcategorie".

Gemeten bij Amanda Haas (05-09-2026): zeven mislukte plaatsingen met precies die
melding, bij "wonen plaids en woondekens", "wonen beddengoed" en "antiek
gereedschap en instrumenten". Zij verkoopt brocante, dus alles bij haar loopt
via de zoek-terugval.

**Why:** een categorie kiezen is niet "een regel aanklikken" maar "doorklikken
tot Vinted het veld zelf invult". Dat veld is het enige bewijs.

**How to apply:** `kiesRestSubcategorie` daalt na de klik nog maximaal drie
niveaus af met dezelfde `kiesBlad`-logica als de boom, tot
`input[data-testid="catalog-select-dropdown-input"]` een waarde heeft. Let op
"extensie-const-na-await-valstrik": alles wat de invulstappen gebruiken moet
een function declaration zijn of boven `const job = await getJob()` staan.

---

## chrome-sitetoegang-op-klik

*05-09-2026 — Chrome's site-access "Als je erop klikt" laat elke opdracht stil doodlopen in een lege pagina; permissions.contains() verraadt het*

Chrome kent per extensie drie standen voor site-toegang: "Op alle sites", "Op
specifieke sites" en "Als je erop klikt". Bij die laatste ziet de extensie een
pagina pas nadat de verkoper op het icoontje rechts van de adresbalk heeft
geklikt — per pagina. Onze werk-tabbladen openen zichzelf, dus dan gebeurt er
niets: geen invulstap, geen foutmelding, en na drie minuten "Extension timed out
waiting for this job to finish".

Amanda Haas (05-09-2026): "Die toestemming geven betrof elke keer als een nieuwe
pagina werd geopend, rechts van de werkbalk" — daarom moest ze erbij blijven
zitten.

**Why:** een time-out leest als "de site is veranderd" terwijl het een
browserinstelling is. Zonder deze controle zoek je weken in de verkeerde hoek.

**How to apply:** `chrome.permissions.contains({origins:[…]})` geeft de ECHTE
stand terug, ook voor host-permissies die in het manifest staan (Chrome mag ze
inhouden). `processJob` stopt nu meteen met een leesbare uitleg als Chrome met
zoveel woorden nee zegt, en gaat gewoon door bij twijfel. De popup toont een
knop die `chrome.permissions.request` doet — en die moet uit een echt tabblad
komen, want Chrome sluit het uitklapvenster zodra hij de vraag toont (zelfde val
als bij "admarkt-toestemming-verdwijnt").

---

## herplaatsing-laat-oude-rij-staan

*05-09-2026 — Een geslaagde herplaatsing liet de oude rij op 'relisting' staan, waarna de reddingsronde elke zes uur een dubbele advertentie plaatste*

Herplaatsen zet de BESTAANDE advertentierij op `relisting` en laat het oude
advertentienummer erop staan. `_rond_publicatie_af` zocht bij binnenkomst van de
nieuwe advertentie een rij met het nieuwe nummer (bestaat niet) of een rij zonder
nummer (bestaat niet), en zette er dus een tweede rij naast. De oude bleef eeuwig
op `relisting`.

`herstel_vastgelopen_werk` leest `relisting` als "halverwege blijven steken" en
zette er elke zes uur een nieuwe plaatsing voor klaar. Gemeten bij Amanda Haas
(05-09-2026): drie artikelen met elk drie identieke Marktplaats-advertenties
tegelijk online, elke dag eentje erbij. Dat is precies het dubbel plaatsen waar
Marktplaats accounts voor blokkeert.

**Why:** een status die niemand afsluit is geen tussenstand maar een lopende
band. Elke ronde die op zo'n status reageert vermenigvuldigt zichzelf.

**How to apply:** een herplaatsingsopdracht draagt nu `_vervangt_listing_id` in
zijn payload; de afronding werkt díé rij bij. En de reddingsronde kijkt eerst of
er al een andere levende advertentie voor hetzelfde artikel op hetzelfde kanaal
staat: dan was de herplaatsing gewoon gelukt en gaat de oude rij op `delisted`.
Zie ook "herplaatslus-op-verkochte-artikelen" en
"reddingsronde-kale-plaatsing-dubbele-advertentie".

---

## waarschuwing-moet-in-het-venster-passen

*04-09-2026 — Een alarm met een drempel (3 uur stil) én een tijdvenster (10-20 uur) kan elkaar uitsluiten; reken het na op echte gegevens*

De offline-waarschuwing ging pas af na drie uur stilte en alleen tussen 10:00 en
20:00 NL. Wie om 16:58 zijn laptop dichtklapt is pas om 19:58 drie uur stil, en
dan is het venster nog twee minuten open. Gemeten op Toons echte gegevens van
04-09-2026: die hele dag kwam er op geen enkel uur een mail uit. Grens naar 22:00
en er gaat om 20:00 NL wél een mail over 39 wachtende opdrachten, 23 minuten
voordat hij de wachtrij weggooide omdat hij dacht dat het vastzat.

**Why:** twee onafhankelijke voorwaarden op tijd lijken allebei redelijk en
sluiten elkaar in de praktijk uit. Dat zie je niet door ernaar te kijken, alleen
door het uur voor uur na te rekenen op iemands echte tijdstippen.

**How to apply:** bij elk alarm met zowel een wachtdrempel als een tijdvenster:
draai de selectie op echte gegevens langs elk uur van de dag, oud én nieuw, en
kijk of er überhaupt een uur overblijft waarop hij afgaat. Zie ook
"offline-waarschuwing-per-mail" en "omnivaleur-altijd-bewijzen".

---

## annuleerknop-wist-de-hele-wachtrij

*04-09-2026 — Een knop die "Cancel" heet naast een balk met 36 wachtende opdrachten wist ze alle 36; enkelvoud in de tekst is een val*

Een afbreekknop moet in zijn bijschrift én in zijn bevestigingsvenster het aantal
noemen dat hij raakt. "Cancel the current publishing action?" naast een balk die
"36 jobs queued" zegt, leest als "ruim die ene vastgelopen actie op" en wiste er
zesendertig (Toon, 04-09-2026: 39 publicaties 's avonds, 93 diezelfde ochtend,
waaronder de dertien Lederhosen waar hij de volgende dag naar zocht).

**Why:** wachtende opdrachten zijn niet vastgelopen, ze zijn nog niet aan de
beurt. Ze op één hoop gooien met de opdracht die écht hangt, betekent dat de
oplossing van het ene probleem het andere veroorzaakt: de klant ruimt op en
concludeert daarna dat publiceren niet werkt. Extra verraderlijk als de balk
ernaast "nothing is running" zegt.

**How to apply:** splits afbreken van leegmaken. Draait er iets, dan raakt de
knop alleen dat ("Stop this one") en zeg erbij dat de rest blijft staan. Draait
er niets, dan heet de knop "Clear queue (N)" en vraagt het venster om precies die
N, met erbij wat er daarna nog mogelijk is. Zie ook
"geen-doodlopende-straat-in-de-ui" en "beloofd-tempo-moet-gemeten-tempo-zijn".

---

## sync-events-blokkeert-verwijderen

*04-09-2026 — sync_events wijst met een sleutel naar listings zonder cascade; een advertentierij met gebeurtenissen is niet te verwijderen*

`sync_events.listing_id` verwijst met een echte sleutel naar `listings(id)` en
heeft GEEN `on delete cascade` (zie `schema.sql`). Staat er nog één gebeurtenis,
dan weigert Postgres de advertentierij weg te gooien.

Gemeten op 04-09-2026 bij de klikproef op "Clear all 13": 4 rijen gingen weg
(3 Facebook, 1 2dehands, nul gebeurtenissen), 9 bleven staan (8 eBay, 1 Shopify,
samen 21 gebeurtenissen). eBay en Shopify schrijven bij elke poging een regel via
`_log_event` in `backend/services/crosslist.py`; de extensiekanalen doen dat niet.
Dat is dus de scheidslijn: **API-kanalen hebben gebeurtenissen, extensiekanalen
niet.**

**Hoe hiermee om te gaan:** verwijder je een `listings`-rij, ruim dan eerst zijn
`sync_events` op. `backend/api/items.py` deed dat bij het verwijderen van een
artikel al; `/api/listings/clear-error` deed het niet en liet daardoor negen
onwisbare rode balken achter. Dit geldt voor elke nieuwe plek die listings
verwijdert.
Zie ook "frontend-parse-json-safe" en "schrijfacties-zonder-herkansing".

---

## frontend-parse-json-safe

*04-09-2026 — "Frontend must parse API responses via parseJsonSafe, never blind r.json()"*

In frontend/app.html, never call `.json()` blindly on a fetch response. Use the `parseJsonSafe(r)` helper instead.

**Why:** When a proxy/gateway (Railway) times out or errors, it returns an HTML error page, not JSON. Blind `r.json()` then throws the cryptic `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`, which is what the user saw after a large bulk import. Daniel explicitly asked that this class of error never surface again.

**How to apply:** `parseJsonSafe` reads the body once and, on non-JSON, throws a human-readable message (e.g. 502/503/504 → "server took too long, may still be processing, refresh"). Also prefer bounding long operations into batches server-side so requests can't hit the gateway timeout at all — see the bulk-import loop (backend returns `remaining`, frontend loops batches of 25). Related: "deploy-pipeline".


## En andersom: stuur zelf nooit een 502 of 503 (04-09-2026)

Cloudflare vervangt een 502- of 503-antwoord door zijn EIGEN HTML-foutpagina.
De uitleg die wij in `detail` meesturen bereikt de browser dan nooit, en
`parseJsonSafe` maakt er terecht "de server duurde te lang" van. Zo werd bij de
klikproef op "Clear all" een sleutelfout die in een fractie van een seconde
optrad op het scherm een tijdverloop, en was de echte reden onvindbaar.

`backend/api/items.py` waarschuwde hier al voor bij `create_item`, en ik trapte
er alsnog in. **500 komt wél ongewijzigd door.** Er staan nog meer 502/503's in
`backend/api/shopify.py`, `content.py`, `billing.py`, `deps.py` en
`listings.py:432`; die verbergen hun boodschap dus net zo goed. Nog niet
aangepakt.
Zie ook "sync-events-blokkeert-verwijderen".

---

## schrijfacties-zonder-herkansing

*04-09-2026 — Leesacties worden overal automatisch herkanst, schrijfacties met opzet niet; bij delete en statuswijziging moet dat wel*

`backend/database.py` hangt sinds 30-08-2026 een herkansing op de SELECT-bouwer
van Supabase, dus élke leesactie overleeft een weggevallen verbinding, ook zonder
`execute_with_retry`. Schrijfacties zijn daar bewust buiten gelaten: een insert
blind herhalen maakt een tweede rij, en dus een tweede advertentie.

**Maar dat argument geldt niet voor alles.** Een rij weggooien die toch weg moet,
of een status van "error" naar "active" zetten, levert bij een tweede poging
precies dezelfde uitkomst op. Blijft de herkansing daar weg, dan wordt één
verbroken verbinding een naamloze 500 op het scherm van de klant.

Zo stond het in `/api/listings/clear-error`: de leesacties waren beschermd, de
twee deletes niet. Egbert kreeg "code F1F7E7" en de knop deed niets.

**Hoe hiermee om te gaan:** vraag bij elke schrijfactie of herhalen iets dubbels
maakt. Nee (delete, statuswijziging, upsert op een vaste sleutel) → in
`execute_with_retry`. Ja (insert met een nieuw id) → laten staan, of
`dubbel_is_ok=True` gebruiken. En vang de rest af met een foutmelding die zegt
wát er misging: een kale foutcode is voor de klant hetzelfde als niets.
Zie ook "geen-doodlopende-straat-in-de-ui" en "foutenlogboek-wist-zichzelf".

---

## foutenlogboek-wist-zichzelf

*04-09-2026 — Een storing die zich herhaalt duwde alle andere foutcodes uit het logboek; nu telt dezelfde fout als één regel*

De foutcodes die de klant op zijn scherm ziet ("code F1F7E7") worden bewaard in
`leadgen_opslag/server_fouten`, hooguit `FOUTEN_BEWAREN = 60` stuks, nieuwste
bovenaan. Dat was een simpele stapel.

Op 04-09-2026 klikte Egbert op "Clear all" en kreeg code F1F7E7. Toen ik ging
kijken waren alle zestig plekken gevuld met exact dezelfde fout van
`/api/items/sync` — die faalde elke vijftien seconden. Zijn code was er binnen
een uur uit gedrukt. **Het logboek dat er is om te kunnen bewijzen wat er
stukging, wiste het bewijs zelf.**

**Hoe het nu werkt:** dezelfde (methode, pad, soort, bericht) is één regel met
`aantal` en de laatste tien `codes`. Zestig plekken betekent nu zestig
verschillende storingen. `mail_analyse.py fouten` toont "(100x, codes: ...)".

**Hoe hiermee om te gaan:** vind je een klantcode niet terug, kijk dan eerst of
er een herhalende storing loopt — en repareer die eerst, anders blijf je blind.
Zie ook "omnivaleur-altijd-bewijzen" en "anthropic-sdk-pin-valstrik".

---

## anthropic-sdk-pin-valstrik

*04-09-2026 — Een te oude pin (anthropic OF supabase) laat nieuwe parameters falen; lokaal werkt het, op Railway niet*

`requirements.txt` en `requirements-content.txt` pinnen de `anthropic`-SDK. Stond
tot 27-08-2026 op `0.34.2` (september 2024). GitHub Actions installeert daarentegen
`pip install httpx anthropic` — altijd de nieuwste. **Die twee liepen dus uiteen**,
en code die lokaal en in Actions werkte, faalde op Railway.

Wat er gebeurde: de mailagent kreeg `output_config={"effort": ...}` mee. Op 0.34.2
gooide dat `TypeError: unexpected keyword argument`, die netjes werd opgevangen —
waarna elk conceptantwoord terugviel op het standaard verkoopsjabloon. Niemand zag
het, want een opgevangen fout ziet eruit als "even geen antwoord".

**Hoe hiermee om te gaan:**
- Voeg je een API-parameter toe, controleer dan of de gepinde SDK hem kent.
  Testje: `pip install anthropic==<pin>` in een venv en de parameter meesturen.
- `scripts/leadgen_mail.py` heeft nu `_claude()`: die vangt een onbekende
  parameter op, probeert opnieuw zonder, en meldt het luid.
- Bumpen kan veilig samen met de gepinde `httpx==0.27.2` (gecontroleerd met
  `pip install --dry-run -r requirements.txt`) — doe die controle wél, want een
  mislukte resolutie betekent een mislukte Railway-deploy en dus site down.
- Zie ook "anthropic-credit-silent-translation-fallback": hetzelfde patroon,
  andere oorzaak. Alles rond Anthropic in dit project faalt stil.


## Zelfde val, 04-09-2026: `supabase`

`requirements.txt` pint `supabase==2.7.4` (postgrest 0.16.11). Lokaal stond
2.31.0. Op 01-09 kwam er `select("id", count="exact", head=True)` in
`backend/api/items.py` en in `backend/api/beheer.py` — `head` bestaat pas in
nieuwere postgrest.

Gevolg: `/api/items/sync` gaf drie dagen lang bij ELKE verversing (elke 15
seconden per open dashboard) een interne fout. Het scherm ververste zichzelf
niet meer, en op het beheerscherm stond "onbekend" in plaats van de aantallen.

Tellen zonder `head`: `select("id", count="exact").eq(...).limit(1)` — het getal
komt uit de kop (Content-Range) en de `limit(1)` houdt het verkeer klein.
Gecontroleerd tegen de echte database met de gepinde client: 5.533 en 10.794,
één opgehaalde rij.

**De les die hier bovenop komt:** de nabootsing in de test slikte `head=` gewoon,
dus stonden de tests groen terwijl productie stuk was. Een nabootsing moet de
handtekening van de GEPINDE client hebben, niet die van de nieuwste.
Zie ook "schrijfacties-zonder-herkansing" en "foutenlogboek-wist-zichzelf".

---

## vinted-voorstel-verslaat-vangblad

*04-09-2026 — "Zegt de tekst van het artikel niets over het model, dan weet het platform het beter dan onze gok: Vinted's eigen voorstel uit de foto's, maar alleen binnen ons eigen pad"*

Vinted zette bijna elke advertentie onder "Other ..." (Men > Clothing > Trousers
> Other trousers voor een gewone Uniqlo-broek), terwijl Vinted zelf bovenaan de
kiezer "Chinos" voorstelde. De tak was goed, het blad daaronder niet: `kiesBlad`
koos op woorden uit titel en omschrijving, en die zeggen bijna nooit iets over
het model. De terugval was het vangblad, en juist daarop filteren kopers niet.

**Why:** wij kennen de tak (die staat in het dashboard), maar over het blad
daarbinnen weet het platform meer dan wij: het heeft de foto's gezien en wij
niet. Onze eigen gok inruilen voor zijn voorstel kost niets, want een gok is
geen aanwijzing. Andersom mag nooit: een echte aanwijzing uit de tekst
("cargo", "half zip") verslaat elk voorstel.

**How to apply:** laat de keuzefunctie opschrijven waaróm ze koos (bij Vinted:
`bladReden` = "voorkeur"/"woorden"/"neutraal"). Alleen bij "neutraal" wijkt ze
voor het voorstel van het platform. Lees de voorstellen op het moment dat de
kiezer opengaat, want ze verdwijnen zodra je de boom in klikt; ze staan er als
een regel met de naam in `Cell__title` en het kruimelpad in `Cell__body`. Neem
alleen voorstellen waarvan het kruimelpad begint met ons eigen pad: het platform
mag het blad kiezen, nooit de tak, anders belandt een herenbroek in de
damesafdeling omdat de foto daarop leek. Sla een omhulsel met meer dan één
`Cell__title` over, anders knoop je de naam van de ene regel aan het pad van de
andere. Zie "rode-regel-is-geen-oordeel" en
"omnivaleur-niet-kledingcategorieen".

---

## rode-regel-is-geen-oordeel

*04-09-2026 — "Een foutmelding onder een veld die weggaat van een teken dat niets verandert, zegt niets over de waarde; laat het formulier zelf beslissen"*

Vinted toonde "Price must be greater than or equal to 1.0" onder een keurig
ingevulde €14,99. Daniel typte één teken over zichzelf heen, de melding
verdween, en plaatsen werkte. In de code was die melding het afkeurcriterium van
elke invulroute én van de eindcontrole, dus er werd niets geplaatst terwijl de
prijs er goed in stond.

**Why:** een melding die weggaat van een handeling die de waarde niet verandert,
is blijven hangen weergave en geen oordeel. Erop afgaan is meten aan het
verkeerde ding. Wat telt is de waarde die het formulier zelf vasthoudt (React:
`__reactProps$*.value`, react-hook-form: `_formValues`), en anders het oordeel van
het platform bij het opsturen.

**How to apply:** lees de waarde van het formulier in de hoofdwereld (MAIN world)
en beslis daarop. Houdt het formulier een bruikbare waarde vast, laat het werk dan
doorgaan en laat het platform bij opsturen beslissen; onthoud de melding en zet
hem in de foutmelding als het opsturen alsnog mislukt. Gemeten in Chrome
(04-09-2026): `dispatchEvent(new Event("blur"))` geeft geen focusout, dus React's
onBlur draait nooit en het formulier herbeoordeelt niets; gebruik `el.blur()` plus
een bubbelende focusout. `document.execCommand("insertText")` is de enige route
uit een script met isTrusted=true. Zet nooit eerst "" met een input-gebeurtenis:
daarmee zet je de "waarde te laag"-klacht zelf neer. Zie
"zoekertjestekst-zit-in-react-hook-form" en "stille-tab-is-geen-formulier".

---

## vinted-sessie-per-landdomein

*04-09-2026 — Een Vinted-account leeft op één landdomein; vinted.com weet niets van een sessie op vinted.nl, dus "niet ingelogd" is meestal het verkeerde domein*

Vinted heeft per land een eigen domein (vinted.nl, .be, .de, .fr, .com) en de
sessiecookie reist niet mee. Gemeten op 04-09-2026:
`https://www.vinted.com/api/v2/users/current` geeft 401 zonder enige
doorverwijzing naar het landdomein, ook al is de verkoper op vinted.nl ingelogd.
`https://www.vinted.com/items/new` stuurt een uitgelogde bezoeker door naar
`/member/register/select_type` met HTTP 200, dus daar valt niets in te vullen.

**Why:** de extensie viel bij elke eerste plaatsing terug op vinted.com, want
`_create_origin` wordt alleen gezet bij herplaatsen (backend/services/relist.py).
De inlogcontrole kreeg daar 401 en meldde "je bent niet ingelogd op Vinted" aan
iemand die zichtbaar was ingelogd. Er werd niets geplaatst. Dezelfde aanname zou
de advertentie ook in de verkeerde catalogus hebben gezet.

**How to apply:** nooit een Vinted-domein aannemen. Zoek het op met
`vintedIngelogdOrigin()` in extension/background.js: die loopt VINTED_ORIGINS af
met de cookies van de browser, onthoudt het antwoord een kwartier, en zegt alleen
"niet ingelogd" als élk domein dat hardop zegt. Een netwerkfout geeft `null` en
laat het werk gewoon door, zoals bij "zekerheid-is-geen-stopplek" en
"bewijs-moet-onderscheiden".

---

## geen-doodlopende-straat-in-de-ui

*04-09-2026 — Elk grijs vakje en elke blokkade in het dashboard hoort een klik te zijn die je naar de oplossing brengt*

Een melding over wat er ontbreekt of geblokkeerd is, moet altijd een weg vooruit
hebben: een link naar het invulscherm, naar de instelling, of een knop die het
zelf oplost. Een uitgegrijsd vakje met alleen tekst eronder is een doodlopende
straat.

**Waarom:** Toon (dejuistetoon) stuurde op 02-09-2026 een foto van zijn
publiceervenster — elk kanaal grijs met "MISSING: DESCRIPTION" — met de zin
"Lukt niet alles blijft vaag en kan niets aanklikken". Hij was er dagen mee bezig.
De melding klopte inhoudelijk volledig; er zat alleen niets achter. De tekst die
hij miste stond gewoon nog op zijn Vinted-advertenties en was met één klik op te
halen.

**Hoe toe te passen:** in `renderPlatformCheckboxes` (app.html) hebben de andere
blokkades dit al langer — "Not connected — set up →" gaat naar Platforms, "Not
possible here" naar Preferences. Missende velden waren de uitzondering; die
wijzen nu naar `haalOmschrijvingOp()` als de bron nog leeft, en anders naar
`editItem()`. Doe hetzelfde bij elke nieuwe blokkade die je toevoegt.

Zelfde gedachte een laag dieper: een foutmelding hoort te zeggen wélke waarde
niet paste en wat er wél kan ("Universeel staat niet in de lijst bij size — die
biedt: S, M, L, XL"), niet alleen dat een veld leeg bleef.

Twee varianten die er op 04-09-2026 bij kwamen, allebei van Egbert Brouwer:

**Een knop die je niet vindt bestaat niet.** De knop "Clear all 303 on 2dehands"
bestond al sinds 03-09, maar zat achter een klik op een rode balk in de lijst,
en niets aan die balk zei dat je erop kon klikken. Egbert, mét de nieuwste
versie: "Waar kan ik die knop vinden om alle rode balken weg te halen, ik zie
hem niet." Zit de oplossing achter een klik, zorg dan dat het ding waarop je
moet klikken eruitziet als een knop — of zet hem ergens waar hij vanzelf in
beeld staat. Nu: een balk boven de lijst (`renderPublishErrorBar`), naast de
sold- en duplicate-balk.

**Een toestand die als mededeling wordt getoond is óók een doodlopende straat.**
Het publiceervenster liet "✓ Listed" zien als een vakje zónder aanvinkmogelijkheid.
Egbert importeerde 5.533 advertenties van Marktplaats, dus élk artikel stond zo,
en hij kon letterlijk niets naar Marktplaats publiceren: op Publish kwam alleen
"Choose at least one platform". Dat gold ook voor de echte situatie waarin de
advertentie op het platform verlopen is en je hem opnieuw wilt plaatsen. Nu is
het een keuze mét waarschuwing over de tweede advertentie. Let op: de server
houdt dit niet tegen, die kijkt alleen naar dubbele rijen van hetzelfde artikel
(`bezet` in crosslist.py), niet naar de rij zelf.

Zie ook "rapportage-in-gewone-taal" en "klantmails-meer-empathie".

---

## zoekertjestekst-zit-in-react-hook-form

*04-09-2026 — "Marktplaats/2dehands valideren de beschrijving op react-hook-form's _formValues.description, niet op de editor en niet op het verborgen veld"*

Het plaatsformulier van Marktplaats en 2dehands is een **react-hook-form**. De
controle bij het plaatsen leest `control._formValues.description`. Dat is de
enige waarheid. Gemeten op 04-09-2026, ingelogd, op zowel
`www.2dehands.be/plaats/1776/652?bucketId=169` als dezelfde URL op
`www.marktplaats.nl`:

- de zichtbare Lexical-editor vullen (onze `FILL_DESC`) zet 122 tekens in beeld
  en laat `_formValues.description` op **0** staan;
- het verborgen veld `description_nl-BE` vullen helpt niet: de DOM-waarde
  verandert wel, maar `__reactProps.value` blijft leeg en het formulier leest
  hem niet. Dat veld is uitvoer, geen invoer;
- `document.execCommand("insertText")` doet in deze editor **niets** (de tekst
  wordt niet langer). Lexical's eigen `insertText` maakt de editor wél langer
  maar `_formValues` niet. Ook `dispatchCommand(CONTROLLED_TEXT_INSERTION)` en
  een echte focusverplaatsing veranderen er niets aan;
- het formulier zijn eigen validatie laten draaien (`control.handleSubmit` met
  eigen callbacks, dus zonder te plaatsen) gaf met een gevulde editor de fout op
  `description` — dat is "Geen zoekertjestekst ingevuld" — en na alléén
  `_formValues.description` te vullen viel `description` uit de foutenlijst weg.
  Op beide platforms.

De control is te vinden door vanaf `[data-testid^="text-editor-input"]` (of het
`form`) omhoog te lopen door de React-fiberketen en in de hooks te zoeken naar
een object met `_formValues` én `_fields`. Gemeten: diepte 8, hook 17, op beide
platforms identiek. Het veld heet `description` (zonder taalachtervoegsel).

**Why:** hierdoor was "Geen zoekertjestekst ingevuld" met de tekst zichtbaar in
beeld jarenlang onverklaarbaar en "soms wel, soms niet". Een echte toetsaanslag
via `chrome.debugger` werkte omdat die de waarde indirect wél in de staat zet;
dat is een fragiele omweg met een gele balk, een koppeling die kan weigeren en
muiscoördinaten die ernaast kunnen zitten.

**How to apply:** schrijf bij elke beschrijvingswijziging rechtstreeks in
`control._formValues.description` (en `_fields.description._f.value`), lees hem
terug vóór het plaatsen, en houd een bewaker draaiend tot en met de klik — elke
hertekening (foto klaar, kenmerk gekozen, merk-venster dicht) kan hem
leeggooien. Levert de zoeker `-1` op, dan werkt dat platform niet zo (Vinted,
Facebook) en is er niets aan de hand; `0` betekent wél leeg. Zie
"mp-2dehands-hidden-description-field" en "extension-release-bump-version".

---

## reddingsronde-kale-plaatsing-dubbele-advertentie

*03-09-2026 — Een advertentie op 'relisting' mag alleen kaal opnieuw geplaatst worden als het weghalen aantoonbaar 'done' is; anders staat de oude nog online en wordt het een dubbele*

De reddingsronde (`herstel_vastgelopen_werk`, elke 6 uur) zag "rij op 'relisting'
zonder plaatsopdracht" en zette dan een kale plaatsing klaar, zonder te kijken of
het weghalen ooit gelukt was. Gemeten 03-09-2026: bij Toon drie kelims waarvan hij
de herplaatsing zelf had geannuleerd (oude advertentie nog online) met drie kale
plaatsingen in de rij; bij twee andere verkopers hetzelfde via de driedagenveger,
oude advertentie nog HTTP 200. Per-job annuleren (`cancel_job`) zette de rij ook
niet terug op 'active'.

**Why:** een 'relisting'-rij zegt alleen dat er een herplaatsing is ingepland, niet
dat de oude advertentie weg is. Alleen de status van de laatste verwijderopdracht
zegt dat.

**How to apply:** nieuw plaatsen alleen bij delete 'done'; bij error/cancelled/
afwezig de herplaatsing terugnemen (`_neem_herplaatsing_terug`: rij 'active' met
uitleg, gepaarde plaatsing geannuleerd, verversbeurt terug). Zie ook
"herplaatsen-verliest-advertenties" en "herkansen-mag-geen-dubbele-opdracht".

---

## prijs-naar-aantal-advertenties

*03-09-2026 — Prijs staffelen naar aantal advertenties is besproken en uitgesteld tot het dashboard echt goed werkt*

Daniel wil de prijs op termijn staffelen naar aantal advertenties. Nu betaalt
iedereen 19,99 per maand, terwijl Toon met 280 advertenties tien keer zoveel
serverwerk kost en tien keer zoveel tijdwinst krijgt als iemand met 25.

**Waarom nu niet:** het dashboard moet eerst echt goed werken. Meer vragen voor
iets wat nog haperende meldingen en wachtrijen heeft, kost klanten in plaats van
dat het omzet oplevert. Dit is Daniels expliciete beslissing op 03-09-2026, niet
een openstaand voorstel.

**Hoe toe te passen:** breng het pas weer ter sprake als de klachten over
publiceren en wachtrijen weg zijn. Ga er ondertussen niet vast op bouwen.

Uit hetzelfde gesprek: Naoufal (websitebouwer van Toon) is een kanaal voor
installatie en doorverwijzing, en het idee om de extensie zelf op een server met
klantwachtwoorden te draaien is bewust afgewezen. Zie docs/team-notes.md,
03-09-2026.

---

## offline-waarschuwing-per-mail

*03-09-2026 — Klant krijgt mail als zijn computer uren stil is met werk in de wachtrij; vereist één handmatige Supabase-kolom*

Sinds 03-09-2026 draait er elk uur een controle
(`backend/services/extension_offline.py`): staat de extensie van een klant meer
dan drie uur stil terwijl er minstens drie uur werk wacht, dan krijgt hij één
mail. Alleen tussen 10:00 en 20:00 NL, hoogstens één per 24 uur, en alleen bij
een lopende proef of abonnement.

Het tijdvenster is geen detail: de nachtelijke herplaatsronde zet bij iedereen
rond 02:30 werk klaar, dus zonder dat venster kreeg elke klant met een uitgezette
computer midden in de nacht een mail.

OPENSTAAND zolang niemand het doet:
`ALTER TABLE extension_heartbeat ADD COLUMN offline_mail_sent_at timestamptz;`
Ontbreekt die kolom, dan onthoudt de server zelf wie al gemaild is en kan de mail
zich na een deploy herhalen. Bewust geen stille uitschakeling zoals bij
"extension-heartbeat-migration" en "sold-price-actual", want dan blijft de
melding maanden onzichtbaar.

Aanleiding: Toon (dejuistetoon) meldde "50 jobs, er gebeurt eigenlijk niets"
terwijl zijn extensie 196 minuten stil was met 62 wachtende opdrachten. Zie ook
"chrome-ruimt-profiel-op-bij-venster-dicht".

---

## chrome-ruimt-profiel-op-bij-venster-dicht

*03-09-2026 — Zonder de background-permissie stopt de extensie zodra het laatste Chrome-venster dicht gaat; Chrome ruimt dan het profiel op*

Chrome sluit niet alleen het venster als de klant zijn laatste venster sluit: het
ruimt het hele profiel op (DestroyProfileOnBrowserClose), en daarmee stopt de
extensie onmiddellijk. Geen alarms, geen poll, niets. De permissie `background`
in het manifest houdt het profiel in leven en lost dat op. Sinds 1.0.288 staat
hij erin.

Gemeten 03-09-2026 op Chrome 152 (Mac), twee identieke testextensies naast elkaar
in eigen profielen, pingend via chrome.alarms: venster open allebei 2 tikken in
75 sec; alle vensters dicht 155 sec lang 0 tikken zonder de permissie en 5 met.
Controleproef die het mechanisme aanwijst: dezelfde extensie zonder de permissie
maar gestart met `--disable-features=DestroyProfileOnBrowserClose` tikte met alle
vensters dicht wél door.

Toevoegen was veilig omdat Chrome zelf zegt dat er geen nieuwe waarschuwing bij
komt: `chrome.management.getPermissionWarningsByManifest` geeft voor het oude en
het nieuwe manifest exact dezelfde lijst. Dat is de meting die je bij elke nieuwe
permissie moet doen voordat je hem toevoegt, want een permissie die wél een
waarschuwing oplevert zet de extensie bij iedereen stil. Zie
"extension-release-bump-version" en de bewakingstest
tests/test_extensie_permissies.py.

Let op: een uitgezette of slapende computer blijft onoplosbaar. Daarvoor is er
"offline-waarschuwing-per-mail".

Testtruc die je nodig hebt: sinds Chrome 137 wordt `--load-extension` genegeerd.
Laden gaat via CDP `Extensions.loadUnpacked` met de vlag
`--enable-unsafe-extension-debugging`. Zo geladen extensies zijn wel vluchtig:
ze staan niet in het profiel en komen na een profielopruiming niet terug.

---

## eigen-klik-gaat-voor-de-nachtronde

*03-09-2026 — De uitgifte pakte de oudste twintig, dus een verse klik stond achter de 50 opdrachten van de nachtelijke verversing*

`get_pending_jobs` haalde de wachtrij op met `order(created_at).limit(20)` en
deelde daar één opdracht uit. Bij Toon zette de nachtelijke verversing om 02:33
vijftig opdrachten klaar; zijn eigen publiceerklik van 13:28 stond daarmee op
plek 24 en kwam niet eens in dat venster van twintig voor. Met Calm mode erbij
(3 tot 8 minuten per opdracht) is dat uren wachten op een knop waar je net op
drukte.

**Why:** het venster van twintig was onzichtbaar. Van buiten lijkt het of de
knop niets doet, terwijl de wachtrij gewoon in de verkeerde volgorde stond.

**How to apply:** de volgorde is nu urgentie, niet aankomst
(`_wachtrij_volgorde` in `backend/api/jobs.py`):

0. een herplaatsing waarvan de oude advertentie al weg is (staat nú nergens
   online) — altijd eerst;
1. wat de verkoper zelf aanklikte;
2. de nachtronde die al langer dan zes uur wacht;
3. de verse nachtronde (die advertentie staat gewoon nog te koop);
4. scans.

De volgorde wordt bepaald over de HELE wachtrij met alleen de lichte velden;
pas daarna worden de payloads van de kop opgehaald. Dataverkeer blijft dus
gelijk. Zie "job-dispatch-serialisation" en
"beloofd-tempo-moet-gemeten-tempo-zijn".

---

## beloofd-tempo-moet-gemeten-tempo-zijn

*03-09-2026 — Een scherm dat "binnen 15 seconden" belooft terwijl het 6 minuten duurt, leest als een storing; meet het tempo in plaats van het te beloven*

Het dashboard beloofde op zes plekken "within ~15 seconds the extension opens a
tab". Bij Toon (dejuistetoon, 03-09-2026) zat er **345 seconden** tussen twee
publicaties omdat Calm mode aanstond. Die schakelaar zit in de extensie
(`chrome.storage.sync`), dus de server wist er niets van en het scherm dus ook
niet. Hij keek naar een balk die zei dat het zo ging beginnen, zag minutenlang
niets, en meldde "er gebeurt eigenlijk niets". Zijn werk liep gewoon.

**Why:** een belofte die het systeem niet waarmaakt is erger dan geen belofte.
De gebruiker concludeert dat het stuk is, drukt nog een keer (vier identieke
scans in dezelfde seconde), en meldt een storing die er niet is. Dat kost
Daniel klantvertrouwen én mijn tijd aan een spookbug.

**How to apply:** vraag het niet aan de extensie (een nieuwe versie is pas over
weken bij de klant, zie "rem-op-de-server-bij-een-extensiefout"), maar **meet
het aan werk dat al gedaan is**: de tussentijd tussen `done_at` van de vorige
opdracht en `claimed_at` van de volgende staat gewoon in de database. Gaten
groter dan twintig minuten weggooien (dan stond de computer uit), mediaan
nemen, en pas iets beweren vanaf drie metingen. Gemeten 03-09-2026: Toon 345 s
→ Calm mode aan; drie andere verkopers dezelfde dag 10 tot 12 s → uit. Dat
onderscheidt dus echt.

Cache zo'n meting per gebruiker: `/api/jobs/active` wordt elke vier seconden
opgevraagd en één zo'n vraag kost 368 ms op een blokkerende client. Zie
"omnivaleur-blocking-supabase-event-loop" en "lean-tokengebruik".

Zie ook "calm-mode" en "geen-doodlopende-straat-in-de-ui".

---

## geen-vraagprijs-is-bieden

*03-09-2026 — een artikel zonder prijs is op Marktplaats geen fout maar de advertentievorm "Bieden"; een lege vraagprijs laat het plaatsformulier hangen en kost bij herplaatsen de advertentie*

Prijs 0 in onze database betekent bijna nooit "vergeten in te vullen". Op
Marktplaats kies je bij elke advertentie een **advertentievorm**, en drie ervan
hebben geen bedrag: Bieden (`FAST_BID`), Gratis (`FREE`) en Zie omschrijving.
Onze import neemt met opzet alleen een échte vraagprijs over (`_naar_advertentie`
in `backend/services/mp_enrich.py`), dus komt zo'n advertentie binnen als 0.

Gemeten 03-09-2026 bij Amanda Haas: 179 van haar 479 artikelen zonder prijs,
waarvan er 168 op Marktplaats terug te vinden waren — **161 als "Bieden"**, 6 als
"Bieden vanaf" en 1 als "Gratis".

Het plaatsformulier stond altijd op "Vraagprijs" en `mpPrijs(0)` vult dan een
leeg veld in. Marktplaats weigert dat ("Geen prijs ingevuld", "Je hebt geen
advertentievorm gekozen"), laat het tabblad open staan wachten op de verkoper, en
bij een herplaatsing is de oude advertentie op dat moment al weg. Elf van haar
advertenties waren zo verdwenen, en zij moest bij elke ronde bij de computer
blijven.

Sinds 1.0.285 kiest de extensie de vorm zelf (`mpPrijsvorm` in
`extension/content/shared.js`) en laat ze het prijsveld dan leeg. Twee dingen om
te onthouden:

* **De keuzelijst heet `select#Dropdown-prijstype` en biedt precies vier vormen
  aan.** Nagemeten op het echte, ingelogde plaatsformulier op 03-09-2026, in twee
  categorieën (kleding 621/636 en Huis en Inrichting > Servies 504/1262), allebei
  identiek: `Vraagprijs = FIXED`, `Bieden = FAST_BID`,
  `Zie omschrijving = SEE_DESCRIPTION`, `Gratis = FREE`. Meer niet — een
  advertentie die op Marktplaats "Gereserveerd" of "Ruilen" is kan hier dus niet
  in zijn eigen vorm terugkomen, en valt terug op Bieden.
* **Kies je "Bieden", dan verdwijnt het prijsveld** (`input[name="price.value"]`)
  uit het formulier. Daarom eerst de vorm en dan pas de prijs: andersom is het
  ingevulde bedrag weg. React neemt de keuze aan via de eigen value-setter plus
  een change-gebeurtenis; ook dat is op het echte formulier nagemeten.
* "Bieden vanaf" (`MIN_BID`) is geen aparte vorm maar een vraagprijs met de
  schakelaar `#syi-bidding-switch-input` aan.
* **De vorm van de oude advertentie lezen we van de advertentiepagina**, in
  dezelfde ophaalronde als de categorie en dus vóór het verwijderen
  (`advertentie_kenmerken`). Daarna geeft die pagina 410.

Zie ook "verbogen-kleurnamen-matchen-niet" en
"herplaatsen-verliest-advertenties": alle drie hetzelfde patroon — een
verplicht veld dat het formulier niet aanneemt, en een verkoper die daarna zonder
advertentie zit.

---

## rem-op-de-server-bij-een-extensiefout

*03-09-2026 — een extensiereparatie bereikt een klant pas na goedkeuring door de Web Store; tot die tijd hoort de rem op de server te staan, en die kent de versie uit de poll-header*

Elke reparatie in `extension/` bereikt een verkoper pas nadat de Chrome Web Store
hem heeft goedgekeurd én Chrome hem heeft opgehaald. Bij Egbert Brouwer duurde
dat drie weken. Tot die tijd loopt de schade gewoon door, en bij herplaatsen kost
elke ronde een advertentie.

Daarom hoort er bij zo'n reparatie een tweede, die vandaag werkt: op de server.
De extensie stuurt haar versie mee in het kopstuk `x-omnivaleur-ext` bij elke
poll (sinds 1.0.250), dus `GET /api/jobs/pending` weet precies welke kopie er
draait. Voorbeelden die er al staan:

* `_zet_kleur_goed` — kleuren goedzetten vlak vóór uitgifte (1.0.282).
* `_herplaatsing_kansloos` / `_neem_herplaatsing_terug` — een verwijdering die
  niet terug kan komen gaat niet door (1.0.285, advertenties zonder vraagprijs).

De vorm die werkt: **de verwijdering tegenhouden, niet de plaatsing repareren.**
Zolang stap 1 niet loopt is er niets kwijt en staat de advertentie er gewoon nog.
Een onbekende versie telt daarbij als oud: kopieën van vóór 1.0.250 sturen niets
mee en kunnen het zeker niet.

Zie ook "extension-version-floor" en "extension-release-bump-version".

---

## aanwezigheid-niet-vragen-maar-stempelen

*03-09-2026 — "Extension not detected" kwam doordat we het aan de slapende service worker vroegen; een content script dat zijn versie op de pagina zet weet het zonder heen-en-weer*

Of de extensie geïnstalleerd is, is geen vraag die je aan haar achtergrond moet
stellen. Dat antwoord moet in MV3 twee heen-en-weertjes met een service worker
overleven die Chrome koud moet starten — en juist terwijl er gepubliceerd wordt
duurt dat het langst. Het dashboard gaf na ~8,8 seconde op en zette een
blokkerend installatievenster over het scherm van iemand die alles goed had
staan (Budgetheld 01-09-2026, Amanda 03-09-2026, allebei mét extensie).

Sinds 1.0.285 zet `extension/content/ext_stamp.js` op `document_start` het
versienummer op `<html data-omnivaleur-ext="…">`. Een content script kent zijn
eigen manifest; daar komt geen achtergrond aan te pas. Staat het stempel er, dan
IS de extensie er — dan blijft het scherm vragen ("starting up…") in plaats van
"niet gevonden" te beweren.

De regel erachter: **vraag aanwezigheid nooit aan iets dat kan slapen.** Alleen
wat de achtergrond echt als enige weet (is ze ingelogd, welke opdrachten staan
klaar) blijft een vraag met een antwoord.

---

## bewijs-moet-onderscheiden

*03-09-2026 — Een waarneming die op het werkende én het kapotte kanaal hetzelfde is, verklaart het verschil niet en is dus geen bewijs*

Een meting is pas bewijs als ze de twee gevallen uit elkaar houdt. Doet ze dat
niet, dan voelt ze als bewijs en is ze een gok met cijfers erbij.

**Waarom:** op 03-09-2026 concludeerde ik dat Egbert Brouwer niet was ingelogd
op 2dehands. Het "bewijs": www.2dehands.be antwoordt op het plaatsadres met
HTTP 401 zolang je niet bent ingelogd, twaalf bytes "Unauthorized". Dat klopt,
maar www.marktplaats.nl doet op precies datzelfde adres precies hetzelfde, en
daar publiceerde hij die dag gewoon door. De meting zei dus niets over het
verschil tussen het kanaal dat wél werkte en het kanaal dat niet werkte.

Die conclusie ging als tekst naar 303 artikelrijen en in een mail naar de klant.
Hij mailde terug: "Ik ben ingelogd op 2dehands, dus weet niet wat er nu mis
gaat?" Hij had gelijk. Twee metingen bewezen het tegendeel: zijn eigen scan
kreeg HTTP 200 op het afgeschermde advertentie-overzicht (dat kan alleen met een
geldige sessie), en onze inlogcontrole zocht in de paginatekst naar "mijn
marktplaats" en "uitloggen" en draaide óók op 2dehands, waar die woorden niet
staan. Zie "stille-tab-is-geen-formulier" en "omnivaleur-altijd-bewijzen".

**How to apply:** voor je een oorzaak opschrijft, vraag: wat zou ik hebben
gemeten in het geval dat wél werkt? Is dat hetzelfde, dan heb je niets. Zoek een
waarneming die alleen bij de storing voorkomt. Spreekt de klant je daarna tegen,
behandel dat als de sterkste tegenmeting die je hebt en meet opnieuw, want hij
kijkt naar het echte scherm en jij naar een logboek.

---

## klantmail-kort-en-menselijk

*03-09-2026 — Klantmails van Daniel: hooguit 200 woorden, één zin erkenning, per punt het gevolg voor de klant vooraan, geen boetekleed en geen slijmen*

Elke mail aan een klant is hooguit 200 woorden en staat vanuit zijn kant
geschreven: wat er nu anders is en hoe dat zijn probleem oplost. Dat is het
belangrijkste. De oorzaak mag hooguit in een halve zin mee, waar die helpt om
het te snappen.

De vorm die Daniel zelf gebruikt:

- Eén menselijke openingszin die erkent wat de klant merkte, in zijn eigen
  woorden, plus dat je hebt gekeken. Eén keer, niet meer.
- Per punt: onderwerp, dubbele punt, dan in een of twee zinnen het gevolg dat
  hij merkt. Concreet wat hij kan doen: waar hij klikt, wat hij intypt.
- Afsluiten met een korte vraag of vervolgstap, niet met een samenvatting.
- Geen techniek, geen bestandsnamen, geen versienummers tenzij hij er zelf iets
  mee moet. Geen opmaaktekens, want de mail gaat als platte tekst de deur uit.

**Why:** het concept dat hij op 03-09-2026 afkeurde was 250 woorden, opende met
een compliment over hoe goed de klant het had opgeschreven, en legde per punt
eerst uit wat er fout ging voordat het zei wat de klant eraan heeft. Zijn
correctie: "trek niet teveel het boetekleed aan... niet teveel BS, niet teveel
slijmen, hou het menselijk vriendelijk en duidelijk." Excuses en uitleg over onze
storing kosten woorden en lossen niets voor hem op.

**How to apply:** de regels staan als code in `TOON_KORT_EN_MENSELIJK` in
`scripts/leadgen_mail.py` en hangen aan `_KLANT_REGELS` daar en aan
`HERSTELBERICHT_REGELS` in `scripts/mail_analyse.py`, zodat elk concept van de
mailagent ze meekrijgt. Schrijf je met de hand een mail voor Daniel, hou je dan
aan dezelfde vorm. Zie "mails-kort-houden", "klantmails-meer-empathie" en
"rapportage-in-gewone-taal".

---

## tel-alleen-wat-er-echt-ontbreekt

*03-09-2026 — Een teller op een knop die velden meerekent die in die categorie niet bestaan, roept altijd het hele bestand en leest als ruis*

"Fill from Marktplaats" telde merk en maat mee als ontbrekend. Egbert Brouwer
verkoopt miniatuurgitaren en plectrums: geen enkele heeft een maat, vrijwel geen
een merk. De knop zei daardoor eeuwig "Fill 5533 from Marktplaats" terwijl er
11 artikelen echt iets misten. Zijn reactie: "ik zie geen knop om deze alsnog op
te halen" — de knop stond er wel, maar riep zo'n hoog getal dat hij hem niet als
zijn probleem herkende.

**Why:** Marktplaats vraagt in de takken muziek, antiek, sieraden, games, wonen
en electronics helemaal niet om merk of maat. Een verplicht veld dat daar niet
bestaat kan ook niet ontbreken. Bovendien haalde elke ronde zijn hele voorraad
opnieuw langs de openbare zoekpagina.

**How to apply:** toets elke "N moeten nog"-teller aan een echte klantvoorraad
vóór je hem live zet, en sluit velden uit die in die categorie niet bestaan
(`_is_non_clothing` in `backend/services/crosslist.py`, `isNonClothingItem` in
app.html). Let op: staat `category` niet in de `select()`, dan leest de
uitzondering altijd "leeg" en verandert er stilletjes niets. Zie
"omnivaleur-niet-kledingcategorieen" en "geen-doodlopende-straat-in-de-ui".

---

## stille-tab-is-geen-formulier

*03-09-2026 — Een opdracht die zonder één teken van leven afloopt betekent "het formulier ging nooit open", niet "de pagina is veranderd"; 2dehands en Marktplaats hebben aparte logins*

Loopt een publicatie-opdracht af op de bewaker van drie minuten **zonder dat het
invulscript zich ooit heeft gemeld**, dan is de pagina die openging niet het
plaatsformulier geweest. Dat is een andere storing dan "het formulier liep vast"
en vraagt om een ander antwoord.

Gemeten 03-09-2026 bij Egbert Brouwer (papas-plectrums): 305 opdrachten voor
2dehands, nooit één geslaagd, 26 afgebroken na exact 3m20s, 279 in de wachtrij.
Zijn Marktplaats-opdrachten uit dezelfde ronde liepen wél door, en bij andere
verkopers slaagde 2dehands in dezelfde periode 97 keer. www.2dehands.be antwoordt
op `/plaats/{l1}/{l2}` met HTTP 401 (12 bytes platte tekst) zolang je daar niet
bent ingelogd; op zo'n pagina draait ons invulscript niet.

**marktplaats.nl en 2dehands.be zijn twee aparte sites met twee aparte
inlogsessies.** Ingelogd op de een is niet ingelogd op de ander. De categorie-
nummers zijn wél identiek (nagemeten via hun eigen zoek-API: 728/748 geeft op
allebei "Muziek en Instrumenten > Gitaren | Elektrisch").

**Why:** de extensie doet met opzet één opdracht tegelijk. 279 × 3,5 minuut is
zestien uur waarin de verkoper verder niets kan publiceren, met 279 keer dezelfde
onbegrijpelijke melding. Zie ook "verborgen-tabblad-vertraagt-wachttijden".

**How to apply:** een kanaal dat bij deze verkoper nog nóóit een geslaagde
plaatsing had én drie keer op rij op de bewaker afliep, is kansloos: neem de rest
van de wachtrij terug en zeg waaróm. Bouw die rem op de server (`_kansloze_reeks`
in `backend/api/jobs.py`), niet alleen in de extensie — een extensiereparatie
bereikt de verkoper pas na goedkeuring door de Web Store, bij hem eerder drie
weken. Zie "extension-release-bump-version" en "anthropic-sdk-pin-valstrik"
voor hetzelfde patroon.

---

## lean-tokengebruik

*03-09-2026 — "Het aantal beurten bepaalt de kosten, niet de moeilijkheid; elke ronde stuurt het hele gesprek opnieuw mee, dus tel beurten voor je ze uitgeeft"*

Op 03-09-2026 was Daniel na één opgeloste klacht al op de helft van zijn
vijfuurslimiet. Het schrijven van één klantmail kostte vier tool-beurten. Zijn
oordeel: dit moet echt efficienter, altijd en overal, zonder kwaliteitsverlies.

**Why:** elke beurt stuurt het complete gesprek opnieuw mee. Een beurt die één
regel oplevert kost daardoor net zoveel als een beurt die het probleem oplost.
Bij een lang gesprek is het aantal beurten dus vrijwel de hele rekening, en de
limiet is de rem op wat er die dag af komt. Niet de moeilijkheid van de taak
kost geld, maar de manier waarop ik hem uitvoer.

**How to apply:** tel vooraf hoeveel beurten iets gaat kosten en haal daar
alles uit wat niet nodig is.

- Weet ik het antwoord al, dan schrijf ik het op zonder eerst iets op te zoeken.
  Een mail schrijven vraagt nul tool-beurten. Meten doe je alleen voor een
  bewering die anders een gok zou zijn, en dan in één beurt, niet in vier.
- Alles wat niet van elkaar afhangt gaat in één bericht. Een bestand schrijven
  plus een script draaien plus committen is één bash-aanroep met een heredoc,
  geen drie beurten.
- Geen tussenstap om het formaat van een bestand te bekijken waar ik daarna toch
  aan toevoeg: `tail` en de bewerking horen in dezelfde aanroep.
- Nooit iets nalezen wat ik zojuist zelf schreef.
- Achtergrondwerk niet pollen.

Dit botst niet met "omnivaleur-altijd-bewijzen" en
"zekerheid-is-geen-stopplek": de zuinigheid zit in hoe ik iets uitzoek, nooit
in of ik het uitzoek. Een bewijs dat een beurt kost is die beurt waard; een
beurt die alleen bevestigt wat ik al wist, niet.

---

## verbogen-kleurnamen-matchen-niet

*03-09-2026 — "bruine" en "rode" matchen op geen enkele Marktplaats-kleuroptie; verkopers schrijven verbogen en samengestelde kleuren, de lijst kent alleen de grondvorm*

Marktplaats vraagt niet in elke categorie om een kleur, en waar het veld wél
staat heet het per categorie anders (`plaidsKleur`, …) met een eigen lijst.
Gemeten 03-09-2026 aan Toons eigen live advertentie in "plaids en woondekens":
de verzamelnaam is daar **"Meerkleurig"**, niet "Multicolour" — precies de waarde
die onze tabel eerder als doel had. Nooit één vaste lijst aannemen dus; lees de
opties uit het formulier zelf en ga meerdere schrijfwijzen langs.

Waar het veld staat, biedt het alleen de kale grondvorm aan. Verkopers schrijven
iets anders op. Geteld in Toons kast
(1.024 artikelen, 03-09-2026): 59 verschillende kleurwaarden, waarvan "bruine"
41x, "zwarte" 20x, "rode" 16x, "groene" 15x, "crème" 13x, "witte" 10x, plus
"lichtblauw", "olijfgroene", "Beige bruin", "divers", "Meerkleurig".

De vertaaltabel ging alleen van Engels naar Nederlands, dus die woorden kwamen
ongewijzigd bij `matchScore` aan en scoorden nul op elke optie. Gemeten met de
echte code uit 1.0.280: 31 van de 59 waarden lieten het veld leeg. Die 31 zitten
op 171 van zijn 1.024 artikelen; hoeveel daarvan echt vastlopen hangt af van de
categorie, want alleen waar het veld bestaat blokkeert het. Voor "plaids en
woondekens" is dat bewezen: 15 artikelen. En een leeg kenmerkveld betekent bij
Marktplaats geen advertentie: de plaatsknop doet dan stil niets (gemeten
21-08-2026).

**Why:** je ziet dit niet aankomen door naar de code te kijken, alleen door de
echte waarden van een echte klant te tellen. Zeven mislukte plaatsingen in het
logboek lijken een randgeval; 171 artikelen is een heel andere orde van grootte.
En andersom: reken je die 171 door alsof ze állemaal vastlopen, dan overdrijf je,
want de helft van zijn categorieën vraagt niet eens om een kleur. Tel wat er is.

**How to apply:** normaliseer vóór het matchen, in deze volgorde: verbuiging
afhalen (bruine → bruin, rode → rood, witte → wit, grijze → grijs, gouden →
goud), samenstelling terugbrengen tot de kleur die er als laatste in zit
(lichtblauw → blauw, olijfgroen → groen), en pas dan bekende bijzondere namen
(ecru → wit, marine → blauw, divers → multicolour). Meerdere woorden leveren
meerdere kandidaten op, in geschreven volgorde. Kies altijd uit de opties die
er echt in staan, verzin nooit een waarde. Zet de kleur ook op de server goed op
het moment dat de opdracht uitgaat: een extensiereparatie bereikt de verkoper pas
na goedkeuring door de Chrome Web Store, de server bij de eerstvolgende opdracht. Zie ook
"marktplaats-publiceren-valkuilen" en "omnivaleur-altijd-bewijzen".

---

## zekerheid-is-geen-stopplek

*03-09-2026 — "Een percentage onder de 100 is geen eindverslag maar een opdracht; eerst alles doen wat het cijfer omhoog kan brengen, pas dan melden"*

Op 03-09-2026 meldde ik Toons reparaties af op "zekerheid 85%", met als reden dat
ik niet in zijn browser kon meekijken. Daniel: "kan je de zekerheid nog hoger
krijgen? is dit alles wat je kan doen?" Twee keer, want de eerste keer had ik het
nog niet door.

Er was wél meer te doen, en het was niet eens duur: nakijken of de reparatie
werkelijk live stond op omnivaleur.nl (dat kon in één opvraging), de maten net zo
grondig doormeten als de kleuren in plaats van ze te laten liggen, en de kleur al
op de server goedzetten zodat de reparatie vandaag werkt in plaats van pas nadat
de Chrome Web Store bijwerkt. Dat laatste is precies het verschil tussen "het is
gerepareerd" en "hij heeft er iets aan".

**Why:** het blokje "Zekerheid: X%" is bedoeld als eerlijke maat, niet als
uitweg. Zodra het als afsluiting wordt gebruikt, wordt eerlijkheid over een gat
een manier om het gat te laten liggen. Daniel verkoopt zekerheid door aan zijn
klanten; 85% betekent voor hem dat hij het niet met droge ogen kan beloven.

**How to apply:** voordat je een percentage opschrijft, maak je de lijst van alles
wat het omhoog zou brengen en doe je dat eerst. Wat overblijft mag alleen dat zijn
wat buiten je bereik ligt (in de browser van de klant meekijken, een Web
Store-goedkeuring, een beslissing van Daniel), en dat noem je bij naam als
actiepunt. Vraag jezelf altijd: werkt dit vandaag voor de klant, of pas na een
stap die iemand anders nog moet zetten? Kun je het vandaag laten werken, doe dat
dan ook. Zie ook "omnivaleur-altijd-bewijzen" en "rapportage-in-gewone-taal".

---

## achtergrondronde-mag-de-lijst-niet-herbouwen

*03-09-2026 — "De ronde die elke 15 seconden bijwerkt zette de lijst terug op bladzijde 1 en hertekende alle rijen met foto's; op een Chromebook viel het tabblad daardoor weg"*

Toon (dejuistetoon), 02-09-2026: "kan niet naar volgende pagina scrollen, springt
elke keer terug naar pagina 1", "na invoeren springt hij naar het 1ste artikel",
"regelmatig valt het beeldscherm totaal weg". Drie klachten, één oorzaak.

`loadAll()` in `frontend/app.html` draait elke 15 seconden en riep `applyFilters()`
aan zonder argument. Die zet `itemsCurrentPage` terug op 1. Bij 1.024 artikelen
zijn dat 21 bladzijden, dus wie verder bladerde had steeds 15 seconden.

Dezelfde ronde verving ook onvoorwaardelijk `#items-body.innerHTML`, dus vijftig
rijen met vijftig `<img>`-elementen. Die foto's zijn de originelen uit de import:
gemeten op Toons eigen artikelen gemiddeld 450 kB per stuk, dus 22 MB die de
browser elke 15 seconden opnieuw ophaalt en uitpakt. Hij werkt op een Chromebook
(afgelezen aan zijn eigen verbinding: CrOS x86_64, Chrome 151) en daar zet Chrome
het tabblad dan weg: leeg scherm.

**Why:** een achtergrondronde die "gewoon alles opnieuw tekent" is onzichtbaar op
een snelle machine met tien artikelen en slopend bij duizend op een Chromebook.
Het gedrag dat de klant beschrijft (springen, wegvallen) leest niet als een
verversingsprobleem, dus je zoekt het in de verkeerde hoek.

**How to apply:** een periodieke ronde mag nooit de keuze van de gebruiker
terugzetten (bladzijde, scrollpositie, selectie) en nooit DOM herschrijven die
niet veranderd is. Vergelijk de opgebouwde HTML met wat er staat en schrijf alleen
bij verschil. Geef elke miniatuur `loading="lazy"`, `decoding="async"` en een
vaste breedte/hoogte. Zie ook "verborgen-tabblad-vertraagt-wachttijden" en
"frontend-parse-json-safe".

---

## scan-mag-nooit-leeghalen

*02-09-2026 — "Een scan mag aanvullen en bijwerken, nooit wissen; een afgeknepen ronde schreef lege waarden over goede heen"*

Een scan die iets niet kon ophalen mag dat veld **niet leegmaken**. Alleen een
waarde die de scan echt vond wint; leegte verliest altijd van wat er al stond.

**Waarom:** in `_store_scan_results` stond
`"description": row.get("description") or None`. Platforms knijpen af, dus een
scan komt geregeld terug met niets voor advertenties waar de vorige scan wél iets
vond. Die leegte ging er keihard overheen. Bij Toon (dejuistetoon, 02-09-2026)
zijn zo 271 kandidaatteksten gewist; wie daarna importeerde kreeg artikelen zonder
tekst en kon niet meer publiceren naar Marktplaats, 2dehands en Facebook. Zijn
klacht was "alles blijft vaag en kan niets aanklikken".

**Hoe toe te passen:** lees bij het opslaan van een scan eerst de vorige waarden
op (alleen de velden die je overschrijft) en val daarop terug als de nieuwe leeg
is. De regel staat als losse, database-vrije functie `jobs._rijke_velden` zodat
hij te testen is zonder scan — met een test die de óude regel naspeelt en
aantoonbaar zakt. Zelfde reden als bij `imports._backfill_patch`.

Geldt niet alleen voor Vinted: elk platform dat throttlet (Marktplaats, 2dehands)
kan dit patroon veroorzaken.

Zie ook "vinted-tekst-alleen-op-de-pagina" en "omnivaleur-altijd-bewijzen".

---

## vinted-tekst-alleen-op-de-pagina

*02-09-2026 — "Vinted geeft omschrijvingen alleen op de openbare advertentiepagina, ~15 per minuut; het item-API-endpoint is dood (404)"*

Waar de advertentietekst van Vinted vandaan komt, gemeten op 02-09-2026:

- Het kastoverzicht `/api/v2/wardrobe/{id}/items` geeft titel, prijs, foto's,
  merk en maat, maar **nooit** de omschrijving.
- `/api/v2/items/{id}` is **dood**: 404, allebei de varianten, ook zonder
  inloggen. `/api/v2/item_upload/items/{id}` geeft 403. Er is geen enkel
  endpoint dat teksten in bulk levert.
- De openbare pagina `/items/{id}` heeft de tekst wél, ook zonder cookies. Pak
  de **langste** `"description":"…"` uit de HTML: de eerste is vaak een lege
  SEO-stomp.
- Vinted knijpt af op ~**15 pagina's per minuut**. Gemeten: 26 verzoeken op rij
  (0,5s ertussen) → 429; daarna 30s pauze → nog 2 door; 60s pauze → 15 door;
  120s pauze → ook 15. Vier seconden ertussen is dus het houdbare tempo, en dat
  staat zo in `backend/services/vinted_enrich.py`.

Gevolg voor elk ontwerp dat teksten ophaalt: **vraag nooit op wat je al hebt.**
Een scan die elke keer de hele kast opnieuw ophaalt is het budget kwijt vóór de
advertenties die het nodig hebben aan de beurt zijn. De server stuurt daarom
`tekst_bekend` mee in de scanopdracht.

Zie ook "scan-mag-nooit-leeghalen" en "omnivaleur-altijd-bewijzen".

---

## videoknipper

*01-09-2026 — Stille video's automatisch inkorten tot een montage — script + dashboard in ~/Documents/Handige Scripts Mac*

Sinds 31-08-2026 staat er een videoknipper in `~/Documents/Handige Scripts Mac/`
(buiten de omnivaleur-repo, dus niet in git): `videoknipper.py` doet het werk,
`dashboard.py` is een lokaal webdashboard op poort 8777, en
`🎬 VIDEO KNIPPEN - dubbelklik.command` start het.

Werkt op **stil beeld zonder gesproken woord** — magazijn-, studio- en
b-rollmateriaal. ffmpeg levert acht verkleinde grijze beeldjes per seconde (128x72)
aan numpy, plus één scherptegetal per beeldje van een 480px-brede versie.
De video wordt in evenveel vensters verdeeld als er fragmenten nodig zijn en uit
elk venster komt het beste fragment. Een montage mag hoogstens 40% van de bron
beslaan, anders valt er niets te kiezen.

**Het uitpakken van beeld is de hele kostenpost, niet het rekenwerk** (01-09-2026).
Een kwartier telefoonvideo in 1080p op 60 beelden per seconde bevat bijna
veertigduizend beeldjes en die moeten allemaal door de decoder, ook al houden we er
maar acht per seconde van over. Op de processor kostte dat ruim zes minuten, waarvan
de balk al die tijd op 8% bleef staan; Daniel las dat als vastgelopen. Sinds
01-09-2026 leest `_uitlezen` de video in vier stukken tegelijk en laat hij de
videochip van de Mac decoderen (`-hwaccel videotoolbox`). Gemeten op dezelfde video
van 2,4 GB: de hele klus gaat van ruim zes minuten naar 2 min 40, en de beeldjes zijn
bit voor bit dezelfde als op de processor (vergeleken met de oude versie, nul verschil
op alle zes de signalen en dezelfde gekozen momenten). Vier stukken is het optimum op
een M2; bij acht wordt het weer trager, want dan raakt de videochip verzadigd. Lukt de
chip het bestand niet, dan wordt alles opnieuw op de processor gelezen.

Twee valstrikken daarbij:

1. **De stukken moeten op hetzelfde meetrooster beginnen.** Bij een stukgrens die
   geen veelvoud van 1/8 seconde is, meet elk stuk op nét andere momenten en komt er
   een andere montage uit dan eerst. Uitlijnen op het rooster maakte de uitkomst weer
   identiek aan de oude versie. Dit was zichtbaar als tientallen afwijkende beeldjes
   ná de eerste stukgrens, terwijl het eerste stuk perfect klopte.
2. **De schatting hierboven klopte niet.** In de eerste versie van deze notitie stond
   "~75 sec voor een kwartier", doorgerekend vanaf een korte testvideo. In werkelijkheid
   was het vijf keer zoveel. Meet de zwaarste échte video, niet een schaalregel vanaf
   een korte.

**De balk beweegt nu tijdens het analyseren.** Hij telt hoeveel beeldjes er al binnen
zijn en meldt dat als 8% tot 45%, met tekst erbij ("beeld analyseren",
"camerabewegingen zoeken"). Een stap die minutenlang stilstaat leest als kapot, ook als
er niets mis is.

**De kern: verschuift het beeld, of beweegt er iets ín het beeld?** Puur op
"er verandert iets" selecteren kiest juist de cameraverzetten, want dan verandert
álles tegelijk — dat was Daniels klacht op 31-08-2026 na een video van 15 minuten.
Elk beeldje wordt daarom over het vorige gelegd en tot 3 pixels heen en weer
geschoven; past het duidelijk beter op een verschoven plek (of verandert meer dan
75% van het beeld tegelijk), dan bewoog de camera en valt het fragment af, met
0,6 sec aanloop en nasleep eromheen. Beoordeeld wordt een héél fragment, niet één
tel — anders gaat het halverwege alsnog mis. Vindt hij in een venster niets
schoons, dan zoekt hij eerst buiten het venster voordat hij water bij de wijn doet.

**Wazig en wiebelig vallen ook af.** Onrust is het gemiddelde verspringen per
achtste seconde — wiebelen geeft ~2,0 tegen ~0,0 bij een vaste camera. Scherpte
kán niet uit de verkleinde beeldjes komen: door dat verkleinen is álles wazig
(een gblur van sigma 7 gaf daar maar 15% verschil). ffmpeg rekent het daarom in
dezelfde doorloop uit op een 480px-brede versie via `convolution` + `signalstats`,
en levert één getal per beeldje — verschil wordt dan 0,8 tegen 2,5. Beide grenzen
zijn percentielen van de video zelf (waziste 25%, onrustigste 25% vallen af), want
wat "scherp" is verschilt per camera en licht. Eén ffmpeg-aanroep met `split`
levert beide signalen; de scherpte kost daarbij bijna niets, het decoderen alles.

**Gemeten op testvideo's met ingebouwde fouten** (studiobeeld met twee magazijnpans
erin geplakt): 100% van de zwenken herkend, montage ging van 5 van de 14 fragmenten
in een zwenk naar 0 van de 14. Tweede proef met 15 sec kunstmatig vervaagd en
15 sec kunstmatig wiebelig beeld: 0 van de 14 fragmenten daaruit.

**Waarom dit lean is:** ffmpeg maakt van de gekozen momenten één contactvel met
miniaturen. Claude kijkt naar dat ene plaatje in plaats van naar de video — zo'n
2.500 tokens, ongeacht of de bron 3 of 15 minuten duurt. Elke montage krijgt
automatisch zo'n contactvel naast zich, juist om die controle mogelijk te maken.

**Grens:** beweging is een proxy. Camerawiebel telt mee als "er gebeurt iets", en
of iemand met zijn rug naar de camera staat ziet de meting niet — dat zie ik pas
op het contactvel.

De map heeft een eigen naamstijl: `EMOJI NAAM - dubbelklik.command` met een
banner-echo bovenaan. Nieuwe scripts daar volgen die stijl.

Aanleveren kan op drie manieren: kiezen uit de lijst (Downloads, Bureaublad en
Films worden doorzocht, alles onder 5 seconden of 1 MB valt af), of een bestand
in het sleepvak gooien, of bladeren. Geüploade bestanden komen in `Aangeleverd/`
en worden blok voor blok naar schijf geschreven, zodat een video van een halve
gigabyte niet eerst in het geheugen moet passen. Muziek kan op dezelfde manier.

**Draait vanaf 01-09-2026 automatisch** via LaunchAgent `com.danie.videoknipper`
(RunAtLoad + KeepAlive, start met `--stil` zodat er geen tabblad opent). Daarvoor
was de bladwijzer naar 127.0.0.1:8777 de dag erna dood, want de server draaide
alleen zolang er iemand hem gestart had.

**Valstrik die dat blootlegde:** een LaunchAgent krijgt een kaal zoekpad zonder
`/opt/homebrew/bin`, dus ffmpeg en ffprobe waren onvindbaar. Het gevolg was níet
een duidelijke foutmelding maar een lege videolijst en "0 sec" bij elk bestand,
omdat `zoek_videos` de fout per bestand opslikte. Opgelost met `gereedschap()`,
dat de programma's zelf opzoekt in de bekende mappen; de PATH in de plist is
alleen een tweede vangnet. Geldt voor élke dienst die de Mac zelf start.

Slepen kopieert niet meer blind: `/api/bestaat` kijkt eerst op naam en grootte
of het bestand er al staat. Daniels schijf zat op 98% vol en er stond een kopie
van 2,4 GB in `Aangeleverd/` van een video die al in Downloads stond.

---

## omnivaleur-altijd-bewijzen

*01-09-2026 — "Bij Omnivaleur nooit stoppen bij \"waarschijnlijk goed\" — meet de aanname, bewijs de oorzaak, draai het echt, en meld pas dan"*

Daniel wil bij Omnivaleur nooit meer hoeven vragen "kan dit naar 100% zekerheid?".
De standaard is: elke reparatie is aantoonbaar, niet aannemelijk.

**Why:** hij verkoopt zekerheid door aan zijn klanten. Zegt hij "het is opgelost"
en het is het niet, dan kost dat hem de klant — niet mij. Een percentage in mijn
rapportage is voor hem geen nuance maar een risico dat hij doorgeeft.

**How to apply:** vóór ik een reparatie meld, elke aanname die eronder ligt
omgezet in een meting:

1. **Bewijs de oorzaak, stop niet bij een plausibele.** Vind ik iets wat de
   klacht zou kunnen verklaren, dan blijf ik zoeken tot ik het mechanisme kan
   aanwijzen. (01-09-2026: het "groene vinkje bij niets" op Vinted leek een
   ontbrekende inlogcontrole; het bleek de automatische herkenning die élk
   advertentie-adres in het werk-tabblad afmeldde. Zonder doorzoeken had ik het
   verkeerde gerepareerd en gezegd dat het klaar was.)
2. **Meet wat het externe systeem écht doet.** Niet redeneren over wat Vinted,
   Marktplaats of Chrome "waarschijnlijk" teruggeeft — curl het, open het,
   kijk. (Uitgelogd geeft Vinted 401 op `/api/v2/users/current` maar HTTP 200
   op `/items/new`; dat verschil wás de bug en was niet te raden.)
3. **Draai de echte code, niet mijn beschrijving ervan.** Frontend in een echte
   browser met een nagebootste trage extensie; extensiecode in node; backend via
   de tests. Een test die alleen naar de brontekst kijkt is een begin, geen bewijs.
4. **Doe de voor-en-na-proef.** De oude versie erbij halen en laten falen onder
   dezelfde omstandigheden — anders weet ik alleen dat de nieuwe code werkt, niet
   dat ze iets repareert.
5. **Wat ik niet kon meten, staat er met zoveel woorden bij** — als openstaand
   punt, niet verstopt in een percentage.

Zie ook "rapportage-in-gewone-taal" en "eerst-recente-wijzigingen-lezen".

---

## gekoppelde-vraag-ipv-brokken

*01-09-2026 — Het patroon "haal alle item-id's, hak in brokken van 200, vraag per brok" is de vaste oorzaak van 502's bij grote accounts; PostgREST kan het in één gekoppelde vraag*

Op meerdere plekken in de backend staat dezelfde vorm: eerst alle item-id's van
een verkoper ophalen, die in brokken van 200 hakken (zie "postgrest-in-filter-url-limiet")
en per brok een aparte vraag stellen. Bij 5.533 artikelen zijn dat zeventig
vragen achter elkaar binnen één verzoek — en dát is wat de gateway opgeeft, niet
de database.

PostgREST kent de sleutel tussen `listings` en `items` (`listings_item_id_fkey`)
en kan het in één vraag: `select("*,items!inner(title,sku,user_id)")` met
`.eq("items.user_id", uid)`. Gemeten op de echte voorraad: 14,6 → 2,0 seconden,
rij voor rij dezelfde uitkomst.

**Waarom dit blijft gelden:** dezelfde vorm staat óók in `/api/items/duplicates`,
in `imports.py` en in `jobs.py`. Bij honderd items valt het nergens op; het
verschil zit niet in de code maar in wie hem draait.

**Hoe toe te passen:** zie je `for ... in range(0, len(item_ids), 200)` gevolgd
door een `.in_(...)`, dan schaalt die aanroep mee met het aantal ARTIKELEN in
plaats van met wat er gevraagd wordt. Vervang hem door een gekoppelde vraag, en
laat de oude weg als vangnet staan voor het geval de sleutel ooit verdwijnt.
Meet altijd op het grootste echte account voor en na — schatten heeft hier nog
nooit geklopt.

---

## omnivaleur-niet-kledingcategorieen

*01-09-2026 — MP/2dehands publiceren kan naast kleding ook muziek, antiek, sieraden, audio-tv-foto, games, telefoons en wonen (url-vorm geverifieerd); zakelijke Admarkt-verkopers kunnen sinds 28-08-2026 wel geïmporteerd worden*

Stand op 13-08-2026. Aanleiding: lead Egbert Brouwer (Papa's Plectrums)
verkoopt plectrums, geen kleding.

**Wat er nu kan en niet kan:** importeren vanaf Marktplaats werkt voor élke
categorie (de scan leest gewoon het verkoopoverzicht). Terugplaatsen op
Marktplaats/2dehands kan alleen voor kleding: `MP_CATEGORIES` in
extension/background.js kent 90 sleutels, allemaal kleding en schoenen, en
`_TAXONOMY` in backend/api/imports.py heeft alleen dames/heren/kinderen/unisex.
Een onbekende categorie geeft bewust een `CategoryUnresolvedError` — hij gokt
niet meer (dat deed hij ooit wel: alles werd Dames Jeans). eBay en Shopify zijn
wel categorievrij.

**Hoe je de categorieboom oogst** (dit werkte, in tegenstelling tot de
api-endpoints die 404 geven): haal `https://www.marktplaats.nl/l/<key>/` op en
lees de `CategoryTreeFacet` uit de embedded state. Kinderen herken je aan
`parentId`. De muziekboom staat geoogst in
`config/marktplaats-muziek-categorieen.json`.

**De url-vorm is op 13-08-2026 geverifieerd** in Daniels ingelogde browser,
tegen de door Marktplaats zelf gerenderde categorienaam (`l1Name` /
`categoryFullName` in de embedded state — het kruimelpad wordt client-side
getekend, dus dat staat niet in de ruwe HTML). Alle 52 ids goed, 0 fout, en
2dehands.be gebruikt exact dezelfde ids.

`https://www.marktplaats.nl/plaats/728/{id}` — **zonder bucketId**. Kleding is 3
niveaus diep (`/plaats/{L1}/{L3}?bucketId={L2}`), deze boom 2, en een bucketId
geeft daar HTTP 400. Zonder login geeft /plaats/ altijd 401, dus dit kan alleen
in een ingelogde browser.

**Op 13-08-2026 end-to-end bewezen:** een plectrum-advertentie is echt online
gekomen in Instrumenten | Toebehoren, met foto, tekst en conditie, en daarna
weer verwijderd. Het invulscript blijkt categorie-onafhankelijk genoeg: elk veld
is voorwaardelijk, dus maat/kleur/merk worden simpelweg overgeslagen. Drie
dingen moesten er wel voor gerepareerd worden — zie "marktplaats-publiceren-valkuilen". Zie ook "leadgen-doelgroep-kleding" — de doelgroep wordt sowieso op
kleding/sieraden/accessoires gefilterd.

**Tweede beperking, gemeten op 13-08-2026 bij lead Egbert Brouwer:** een
Marktplaats **zakelijke** verkoper kan niet geïmporteerd worden. Bewijs, niet
vermoeden: verkopers-id 6999351 heeft `isVerified: true`, `showWebsiteUrl: true`,
een `sellerWebsiteUrl` via `admarkt.marktplaats.nl` en **5.529 live
advertenties** — terwijl onze scan tweemaal nul teruggaf.

Oorzaak: de scan leest `/my-account/sell/api/listings`, het *persoonlijke*
"mijn advertenties"-overzicht. Zakelijke verkopers beheren hun advertenties in
**Admarkt** (`admarkt.marktplaats.nl`, OAuth, eigen API/feed) en die staan daar
niet tussen. De API antwoordt dus correct met niets.

Sinds extensie 1.0.198 zegt de melding dat ook. Een eerdere poging raadde het
uit de paginatekst (`pro_hint`) en gaf een verkeerd antwoord — die gok is eruit.

Let op bij het beoordelen van zulke leads: **de hele leadlijst bestaat uit
zakelijke verkopers** (het scrape-filter selecteert op precies dat vlaggetje,
zie "leadgen-doelgroep-kleding"). Hoeveel van hen Admarkt gebruiken is niet
gemeten. Verwar dit niet met "een pro account aangemaakt" in een mail van een
lead: het Omnivaleur-abonnement heet in de database óók `plan: "pro"`.

**Antiek en Kunst toegevoegd (18-08-2026), 45 categorieën.** L1 = **1**, twee
niveaus en dus **geen bucketId** — net als muziek: `/plaats/1/{L2}`. Geverifieerd
in een ingelogde browser (HTTP 200 zegt niets): `/plaats/1/2614` toont
"Antiek en Kunst > Goud en Zilver", `/plaats/1/2` toont "Bestek". Oogsten gaat via
`https://www.marktplaats.nl/l/antiek-en-kunst/` → `CategoryTreeFacet`; de
`label`- en `key`-velden zitten in dezelfde objecten, `parentId == 1` filtert L2.

**Sieraden bestond alleen in het dashboard en de extensie, niet in `_TAXONOMY`.**
Daardoor kón de classificatie een ring of armband nooit als sieraad indelen en
belandden die in "unisex accessoires". 26 categorieën alsnog toegevoegd.

**De classificatieregel gaat over WAT iets is, niet waarvan het gemaakt is:** wat
je draagt is sieraden, wat op tafel/muur/plank staat is antiek. Zonder die regel
werd "zilveren ring" ingedeeld als `antiek goud en zilver`.

**Aanleiding:** Jaap (Zilverwebsite, 1.200 advertenties) had bij 97 van 130 items
geen categorie — daardoor uitroeptekens bij elk product, vragen om maat en merk,
en een gembercouvert onder sieraden.

**Correctie 30-08-2026 — twee dingen hierboven kloppen niet meer.**

1. *"Terugplaatsen kan alleen voor kleding"* is achterhaald: muziek (13-08),
   antiek (18-08) en sieraden zitten er sindsdien in, met geverifieerde url-vorm.
2. *"Een zakelijke verkoper kan niet geïmporteerd worden"* is achterhaald.
   Egberts **1.284** advertenties zijn op 30-08-2026 wél binnengehaald, volledig
   op de server via `/imports/bulk-import` — zonder zijn browser, terwijl zijn
   extensie stil lag. De beperking zat in de scan die het *persoonlijke*
   overzicht las; de Admarkt-weg zelf werkt.

Wat wél blijft staan: Admarkt levert **alleen titel en foto's**. Prijs en
omschrijving moeten daarna uit de openbare zoek-API van diezelfde verkoper komen
(zie "admarkt-omschrijving-via-openbaar-mp"). En let op de verhongeringsfout in
`_mist_iets()` van `backend/services/mp_enrich.py`: die markeert ook een ontbrekend
merk of maat, dus bij een verkoper zonder merken loopt de kwartierronde eeuwig op
dezelfde eerste 150 items en komen nieuwe items nooit aan de beurt.

**Aanvulling 01-09-2026 — de boom is veel breder dan hierboven staat.** In
`frontend/app.html` (`const CATEGORIES`, de bron van waarheid, bewaakt door
`tests/test_category_taxonomy.py`) staan nu ook: **audio, tv en foto** (68, L1=31,
incl. verrekijkers/telescopen/microscopen), **games** (50), **telefoons** (10),
**wonen en tuin** (42). De audio-tak is op 27-08-2026 in een ingelogde browser
geverifieerd — alle 68 via `/plaats/31/{cat3}`, categorienaam vergeleken met die
van Marktplaats zelf, 68 van 68 gelijk — plus onafhankelijk nagemeten via
`/lrp/api/search?l2CategoryId={cat3}`. Twee niveaus, dus géén bucketId.

Wat daar wél blijft liggen: die tak heeft kenmerkvelden (Type, Wattage) die wij
leeg laten. Alleen titel, tekst en foto's zijn verplicht, dus publiceren lukt —
maar wie op zo'n filter zoekt ziet de advertentie niet.

---

## verkocht-badge-in-berichtenlijst

*01-09-2026 — "Marktplaats zet \"Verkocht!\" op het gesprek, niet op de advertentie; sinds 1.0.279 leest de berichtenscan die badge"*

Bij een handverkoop komt er nooit een "verkocht" op de Marktplaats-advertentie —
de verkoper haalt hem gewoon weg. Marktplaats zet het label wél op het GESPREK
met de koper. Dat is de enige plek waar het platform een handverkoop bevestigt,
en het is hoe Daniel het zelf nakijkt.

Sinds 1.0.279 leest de kwartaalronde die berichten telt die badges mee
(`_mwReadNotifCounts` in `extension/background.js` → `POST
/api/listings/sold-from-messages`). Geen extra bezoek: die pagina ging al open.
Hier wordt geboekt, niet gevraagd, met drie grenzen: alleen een los labeltje dat
exact "verkocht" is; het nummer voor de titel moet bij precies één artikel horen
(de titel staat afgekapt in de lijst); en het artikel moet nog ergens te koop
staan, want een gesprek houdt zijn badge voor altijd.

Lost NIET op: verkopen buiten Marktplaats' betaal-/verzendstroom krijgen geen
badge. Daarvoor blijft de vraag "is dit verkocht?" in het dashboard.

Geldfout die hier bovenkwam: `handle_item_sold` zette élke advertentierij van dat
kanaal op 'verkocht'. Met meerdere rijen per artikel (zie
"herplaatslus-op-verkochte-artikelen") telde één verkoop meerdere keren mee in
de omzet. Nu draagt alleen de rij die op dat moment leefde de verkoop.

Zie ook "sold-price-actual" en "extension-release-bump-version".

---

## herplaatslus-op-verkochte-artikelen

*01-09-2026 — "Verkochte artikelen werden dagelijks opnieuw op Marktplaats gezet; twee oorzaken in jobs.py, gerepareerd 01-09-2026"*

Een artikel houdt op Marktplaats één advertentierij per herplaatsing (de oude
blijft als archief staan) — tot zes rijen op één artikel. Twee fouten in
`backend/api/jobs.py` maakten daar een eindeloze lus van, gerepareerd 01-09-2026:

1. Een verwijderopdracht werkte élke rij van dat artikel+kanaal bij. Bij een
   mislukte verwijdering gingen ze dus allemaal terug op 'actief' mét hun oude
   plaatsingsdatum, en waren daarmee meteen weer relist-kandidaat. Het wiste ook
   een al gestelde vraag "is dit verkocht?" uit.
2. `already_absent` (de advertentie was al weg toen we hem kwamen weghalen) gold
   als geslaagde verwijdering, waarna stap twee een nieuwe advertentie plaatste.
   Precies het geval bij een verkoop.

De regel die het onderscheid maakt: een gratis MP-advertentie verdwijnt pas na
30 dagen vanzelf. Is hij jonger dan 28 dagen en tóch weg, dan heeft iemand hem
weggehaald → `sold_unconfirmed` (de bestaande "mogelijk verkocht"-vraag in het
dashboard) plus annulering van de wachtende plaatsing. Ouder → gewoon
herplaatsen.

`scripts/stop_herplaatslus.py` past die regel met terugwerkende kracht toe; met
`--user` te beperken, want zonder filter verschijnt de vraag ook in het
dashboard van klanten. Gemeten bij Daniel: 18 combinaties in de lus.

Zie "herplaatsen-verliest-advertenties" en "klantenslot-valt-dicht".

---

## supabase-gratis-plan-egress

*31-08-2026 — "Supabase-gratisplan loopt steeds over: eerst egress (select(\"*\") op /blog + 5-min-polling), nu opslag — 3,71 GB foto's tegen een limiet van 1 GB; de database zelf is nooit het probleem"*

Het Supabase-gratisplan is twee keer overschreden. **Beide keren was het code,
niet bezoekers, en nooit de database** (die zit op 47 MB van 500 MB = 9%).

**31-07-2026 — egress, 149%.** Twee grootverbruikers: `/blog` deed `select("*")`
inclusief de volledige `body_html` (0,57 MB per paginabezoek, nu 0,04 MB), en de
5-minutenpolling in `backend/services/polling.py` deed losse queries per listing
en draaide óók over gebruikers zonder platformkoppeling. Blogbeelden staan sinds
toen lokaal in `frontend/assets/` (Railway-verkeer telt niet mee).

**16-08-2026 — opslag, 346%.** 3,71 GB foto's. Gemeten verdeling: 2,55 GB in
gebruik (gemiddeld 724 KB per foto, sommige 11 MB), 1,00 GB verweesd. Eén
account houdt 2,10 GB vast. Twee oorzaken, allebei opgelost in code:

* Niets verwijderde ooit een foto. `delete_item` liet de foto's staan. Nu ruimt
  `_release_photos` in `backend/api/items.py` op, maar alleen wat aantoonbaar
  nergens anders meer bij hoort — foto's zijn op inhoud geadresseerd (SHA-256)
  en kunnen dus gedeeld zijn tussen items. **Vergelijk op PAD, nooit op url:**
  oudere Supabase-clients zetten een kale `?` achter `get_public_url`, dus
  tekstvergelijking wist foto's die nog in gebruik zijn.
* Foto's gingen onverkleind de bucket in. `backend/services/image_optimize.py`
  verkleint nu naar max 1600 px (~70% winst). **Nooit naar webp** — Etsy post
  onze bytes als `image/jpeg` en de extensie geeft het bestand rechtstreeks aan
  een marktplaatsformulier. EXIF-rotatie moet vóór het hercoderen vastgelegd,
  anders liggen telefoonfoto's op elk kanaal op hun kant.

**Afloop:** op 16-08-2026 alles verhuisd naar R2 (zie "omnivaleur-r2-fotoopslag")
en de bucket opgeruimd: **3,71 GB → 0,67 GB**, 3436 objecten weg, alle 3525
foto's daarna nog bereikbaar. Wat overblijft zijn foto's van nog lopende
publicatieopdrachten en de blogmap.

**Valstrik die me een vals succes opleverde:** `storage.remove()` met de
**anon-sleutel gooit geen fout maar antwoordt 200 met een lege lijst**. Het
opruimscript meldde daardoor "3,04 GB vrijgemaakt" terwijl er niets was gewist.
Tel altijd na hoeveel objecten de API teruggeeft; `SUPABASE_SERVICE_KEY` staat nu
in `.env` voor onderhoudsscripts (de gewone lokale sleutel is anon, Railway heeft
service_role).

**31-08-2026 — het project ging van "restricted" naar PAUSED.** Drie
overtredingen tegelijk: egress 437%, cached egress 117%, storage 211%. Inloggen
lag plat, klanten klaagden. Twee lessen:

* **Alleen verkeer en cache-verkeer resetten met de factuurperiode; opslag
  niet.** Staat `exceed_storage_size_quota` in de melding, dan is wachten op de
  reset zinloos — dat lijkt een klem, want de opslag verlagen kan alleen als de
  database open is.
* **Maar het dashboardcijfer loopt achter.** Het meldde 2,108 GB terwijl de
  bucket in werkelijkheid 0,67 GB was (de stand van na de opruiming van 16-08).
  Er is maar één bucket; nagemeten met de service-sleutel. Op dat verouderde
  cijfer is Pro (€25) aangezet, wat achteraf vermoedelijk niet nodig was.

**How to apply bij de volgende blokkade:** draai éérst
`python3 scripts/cleanup_orphan_photos.py` (droogloop — leest de bucket écht
uit) en `python3 scripts/migrate_photos_to_r2.py` (droogloop — telt wat er nog
op Supabase staat), en vergelijk dát met het dashboard voordat je iemand
adviseert te betalen. De preflight van het migratiescript test alleen de
R2-kant en werkt dus óók als Supabase op slot staat — handig bewijsmateriaal
zonder een cent uit te geven.

**Why:** een quotawaarschuwing voelt als groei, maar was beide keren verspilling.
Kijk altijd eerst naar de verdeling voordat je aan upgraden denkt — en meet zelf
in plaats van het dashboard te geloven.

**How to apply:** bij een nieuwe waarschuwing eerst de Usage-pagina lezen wélke
meter rood staat. Egress → `grep -rn 'select("\*")'` over `backend/` plus
`backend/scheduler.py`. Opslag → `python3 scripts/cleanup_orphan_photos.py`
(droogloop, toont de hele verdeling) en daarna
`scripts/backfill_shrink_photos.py`. Let op: teruglezen uit de bucket kost zélf
egress (2,55 GB voor een volledige backfill), dus die heeft een `--budget-mb` en
draait bij voorkeur na het begin van een nieuwe factuurcyclus. Cloudflare R2
(10 GB gratis, geen egresskosten) blijft de structurele uitweg. Zie ook
"deploy-pipeline" en "railway-draait-op-anon-sleutel" — met de anon-sleutel
kan een storage-delete op RLS stuklopen.

---

## concept-verwijderen-op-uid

*30-08-2026 — Een concept bijwerken via append+delete raakt het verkeerde bericht als je op volgnummer verwijdert; Zoho hernummert de map. Herstel kan alleen uit de leerlog.*

Bij het bijwerken van een klaarliggend concept (nieuwe versie toevoegen, oude
weghalen) hernummerde Zoho de map `Concept` na de append, waardoor
`store(<volgnummer>, +FLAGS \Deleted)` het cóncept van de volgende klant trof in
plaats van het bedoelde. Waargenomen 30-08-2026 bij het bijwerken van Egberts
concept; het concept voor d.r.seubring verdween.

**Waarom:** een APPEND met een `Message-Id` dat al in de map staat laat Zoho het
bestaande bericht vervangen en achteraan opnieuw plaatsen. Alle volgnummers
erna schuiven één op. Een `expunge` in `Concept` gaat **niet** naar `Afval`, dus
het bericht is daarna definitief weg.

**How to apply:** verwijder een concept altijd op **UID** (`uid('STORE', ...)`),
nooit op volgnummer, en haal vlak vóór het verwijderen de `To`-kop van precies
dat bericht op ter controle. Gaat het toch mis: de volledige conceptekst mét
citaat staat in de `leerlog` in `leadgen_opslag` (`_onthoud_concept()` in
`scripts/leadgen_mail.py`), en de draadkoppen (`In-Reply-To`, `References`) haal
je uit het oorspronkelijke bericht in INBOX. Zie "mailbox-eigenaarschap".

---

## marktplaats-category-ids

*29-08-2026 — "How Marktplaats/2dehands SYI category URLs are structured, and the verified numeric IDs for the games (Spelcomputers en Games) tree"*

Marktplaats' sell-flow (`/plaats`) category URL is `/plaats/{cat1}/{cat3}?bucketId={bucketId}`. Counter-intuitively, in the games branch **bucketId = the L2 subcategory** and **cat3 = the L3 "type"** (the console generation), not a strict L1→L2→L3 nesting of the path segments. The extension's `MP_CATEGORIES` stores `{cat1, cat3, bucketId}` per category key and `getMpSyiUrl` builds that URL. 2dehands.be shares the exact same numeric IDs — only the base domain differs.

The numeric IDs are only visible in the logged-in sell flow (public `/l/...` browse pages use slugs). They must be read live from the category picker, not guessed. Read once via the browser and verified against the real URL (`/plaats/356/2952?bucketId=205` = PS5 game).

**How to harvest IDs reliably:** on `/plaats` (logged in, in the user's own Chrome — the in-app browser gets bot-blocked) the picker is three plain `<select>`s named `cat_sel_1/2/3`. Set `.value` via the native setter + dispatch a bubbling `change` event, then read `options` — that dumps the whole tree without any clicking.

**HTTP 200 is NOT proof the category is right.** A wrong-but-parseable ID combination renders a *different* real category rather than an error. Always navigate and read the rendered "Gekozen categorie" breadcrumb. Found this way (2026-07): the kids branch had been on `cat1=428` (= "Diversen", not Kinderkleding) with a non-existent `bucketId=127` — most combinations returned HTTP 400, but `meisjes kleding` returned 200 and silently resolved to *Diversen › Modeltreinen › Brommobielen en Scootmobielen*, a **paid** category.

**Kinderen en Baby's — cat1 = 565.** Marktplaats files children's clothing by **SIZE**, not by boy/girl — the L3 "type" literally is the size. Babykleding bucketId 150 (Maat 50→568, 56→569, 62→570, 68→571, 74→572, 80→573, 86→574, Overige 575); Kinderkleding bucketId 153 (Maat 92→582 … 176→596 in +6cm steps, Schoenen en Sokken 598, Overige 597); Mode-accessoires bucketId 427 (Baby 3137, Kind 3136). `MP_CATEGORIES` entries therefore carry a `sizeMap` and `getMpSyiUrl` resolves cat3 from `item.size`.

**Sieraden, Tassen en Uiterlijk — cat1 = 1826.** L2 buckets: Accessoires 197, Horloges 199, Sieraden 200, Tassen en Koffers 201, Zonnebrillen 203. A watch/ring/handbag has no home in the clothing tree, so these get their own `sieraden ` category-key prefix (in `_NON_CLOTHING_PREFIXES`) rather than being forced into an "accessoires" key, which maps to Kleding | Dames.

**Games — cat1 = 356 ("Spelcomputers en Games"):**
- PlayStation games (bucketId 205): PS5 2952, PS4 2889, PS3 1735, PS2 1734, PS1 367, PSP 1660, PS Vita 2890
- Nintendo games (bucketId 204): Switch 2942, Wii U 2888, Wii 1630, 3DS 2887, DS 1659, GameCube 1730, N64 1733, SNES 1732, NES 1731, Game Boy 363
- Xbox games (bucketId 206): Series X/S 2953, One 2891, 360 1631, Original 368
- Other games (bucketId 207): PC 365, Sega 366, Atari 1729, Overige 364
**Game consoles — hardware, cat1 = 356, L2 "Spelcomputers" buckets (distinct from games software 204-207):**
- PlayStation consoles (bucketId 209): PS5 2954, PS4 2894, PS3 1741, PS2 1740, PS1 347, PS Vita 2895, PSP 1656
- Nintendo consoles (bucketId 208): Switch 2943, Switch Lite 2946, Wii U 2893, Wii 1628, 3DS/2DS 2892, DS 1655, GameCube 1736, N64 1739, SNES 1738, NES 1737, Game Boy 346
- Xbox consoles (bucketId 210): Series X/S 2955, One 2896, 360 1629, Original 349
- Other consoles (bucketId 211): Sega 348, Atari 345, Overige 1743
- (accessories = 300-303, VR = 415 — not yet mapped in the app)

**Electronics — mobile phones, cat1 = 820 ("Telecommunicatie"), L2 bucketId 225 ("Mobiele telefoons"), cat3 = brand:**
- Apple iPhone 1953, Samsung 841, Huawei 2897, Sony 843, Nokia 836, LG 1632, Motorola 834, HTC 1685, Blackberry 1954, Overige 837
- Verified: /plaats/820/1953?bucketId=225 = Apple iPhone. Recognised app-wide by the `electronics ` category-key prefix (added to `_NON_CLOTHING_PREFIXES`).
- Other Telecommunicatie L2 buckets (not yet mapped): Hoesjes 226, Telefoon-accessoires 227, Wearables 426, Datacommunicatie 223, Vaste telefoons 228.
- Top-level cat1 IDs harvested from the SYI combobox: Audio/Tv/Foto 31, Computers en Software 322, Telecommunicatie 820, Witgoed 537, Spelcomputers en Games 356.

Non-clothing items are recognised app-wide by the `games ` category-key prefix (see "extension-release-bump-version" for the extension side; backend `crosslist.py` `_is_non_clothing`), which lets games skip the gender/maat/kleur required-field gate without any DB column.

Carnaval/verkleedkleding (geverifieerd 30-08-2026 in een ingelogde browser, broodkruimel gelezen): dames `/plaats/621/623?bucketId=162`, heren `/plaats/1776/2031?bucketId=169` → "Carnavalskleding en Feestkleding". De categorieboom is op te vragen met `GET marktplaats.nl/lrp/api/search?l1CategoryId=<id>&limit=1` → `searchCategoryOptions`.

---

## seintje-concept-klaar

*29-08-2026 — Elk klaargezet conceptantwoord stuurt direct een mailtje naar Daniel, met het label wie het schreef*

Sinds 29-08-2026 stuurt de mailagent bij élk klaargezet concept meteen een mailtje
naar ALARM_NAAR (danieldekoning66@gmail.com + info@revaleur.com): ontvanger,
onderwerp, de concepttekst, en "Geschreven: klantenservice" of "klantenservice +
developer". Dat laatste staat er zodra er voor die melder een storing op
`opgelost` staat — het teken dat het antwoord in de code is nagekeken.

**Why:** Daniel wil alleen nog op verzenden drukken en niet zelf de conceptenmap
bewaken. Zonder seintje bleef dat handwerk bestaan.

**How to apply:** Het haakje zit in `_zet_concept_klaar` in `scripts/leadgen_mail.py`
— de enige plek waar alle conceptpaden langskomen. Nieuwe conceptroutes hoeven
niets extra's te doen; wie er wél omheen bouwt, sloopt de melding.
Zie "rolverdeling-ceo-va-developer" en "mailbox-eigenaarschap".

---

## rolverdeling-ceo-va-developer

*29-08-2026 — Vaste rolverdeling — Daniel is CEO, de mailagent is klantenservice, Claude Code is developer; de twee onderste rollen praten onderling en escaleren alleen als het moet*

Vastgesteld 29-08-2026 door Daniel, expliciet als iets dat niet verandert.

- **Daniel = CEO.** Hij schrijft geen conceptmails meer en controleert geen
  dubbelingen. Hij opent Concepten en ziet daar alleen juiste, volledige mails
  die hij hooguit verstuurt. Alles wat hem tijd kost aan mailbeheer is een bug.
- **De mailagent = klantenservicemedewerker.** Analyseert álle mail, in- én
  uitgaand. Houdt de marketingvoortgang bij in het dashboard. Escaleert naar
  Daniel alleen wanneer het echt nodig is.
- **Claude Code = developer.** Krijgt van de mailagent door welke bugs
  terugkomen, welk patroon erin zit en wie ze meldt; koppelt terug wanneer iets
  gerepareerd is zodat de klant bericht kan krijgen.

De mailagent en Claude Code horen onderling te communiceren, niet allebei apart
via Daniel. Escalatie naar hem is de uitzondering, geen route.

Staat ook in `docs/team-notes.md`, want dit mag niet aan één account hangen.
Zie "mailbox-eigenaarschap", "mailagent-op-de-server",
"klanten-zijn-geen-leads" en "rapportage-in-gewone-taal".

---

## shopify-app-store-geweigerd

*28-08-2026 — Shopify accepteert geen marktplaats-apps; koppelen gaat via een sleutel die de winkelier zelf aanmaakt, en de verkoopmelding werkt daar niet met een webhook*

Shopify zette de app-aanvraag op **paused** (28-08-2026, ref 131213): "Shopify is
not currently accepting apps that connect to a marketplace system outside of
Shopify. This applies to all apps." Dat is beleid, geen defect — er is geen
versie van Omnivaleur die daar doorheen komt zolang ze naar Marktplaats, Vinted
en eBay publiceert. Niet opnieuw indienen, geen bezwaar maken.

Ook de oude uitweg is dicht: *"You can no longer create new admin-created custom
apps."* Een winkelier kan in zijn winkelbeheer dus geen app meer maken die een
`shpat_`-sleutel toont. Bestaande apps blijven wel werken.

**De weg die wél werkt, voor iedere klant.** De client credentials grant eist dat
app en winkel in dezelfde Shopify-organisatie zitten. Dat lijkt klanten uit te
sluiten — tot je omdraait wie de app maakt: laat de **winkelier zelf** de app in
zíjn organisatie maken voor zíjn winkel. Dan klopt die voorwaarde per definitie.
Hij geeft ons client ID + client secret, wij wisselen die in via
`POST https://{shop}/admin/oauth/access_token` met `grant_type=client_credentials`.
Geen review, geen App Store. "Custom distribution" via een Partner-app is géén
alternatief: beperkt tot één winkel per app.

**Die sleutel leeft 24 uur.** `_shop_creds()` ververst hem automatisch met tien
minuten speling; zonder dat zou alles elke dag stilvallen op een 401.

**De valkuil die je makkelijk mist:** de verkoopmelding liep over de webhook
`orders/paid`, en die hoort bij ÓNZE app. Bij een zelfgemaakte app komt hij nooit
binnen — verkocht in de eigen winkel bleef dan overal elders te koop staan.
Daarom kijkt `backend/services/shopify_orders.py` elke 5 minuten zelf de betaalde
bestellingen na. Dat vereist `read_orders`; zonder dat recht geeft Shopify 403 en
slaat de ronde die winkel over.

Vastgelegd in `tests/test_shopify_eigen_sleutel.py`.

---

## klantmails-meer-empathie

*28-08-2026 — Klantmails openen met erkenning van de moeite die de klant erin stak, niet meteen met de technische uitleg*

Mails aan klanten die een probleem melden moeten beginnen met erkenning: deze
mensen steken veel eigen tijd in testen, schermafbeeldingen maken en precies
opschrijven wat er misging. Benoem dat, benoem wat het hen kost (achterlopen op
planning, zorgen), en zeg dat het niet aan hen lag. Pas daarna de uitleg.

**Waarom:** Daniel gaf dit op 28-08-2026 als correctie op een concept aan Jaap
(zilverwebsite.nl) dat meteen met "Twee dingen deugden daar niet" begon. Zakelijk
correct, maar het las alsof zijn dagenlange meewerken vanzelfsprekend was.

**How to apply:** eerst danken en erkennen, dan de oorzaak in gewone taal, dan
wat er gerepareerd is, en waar mogelijk iets concreets dat je zelf al voor ze
hebt gedaan in plaats van een vraag terug. Blijf rond de 200 woorden — zie
"mails-kort-houden" en "mailbox-eigenaarschap".

---

## herkansen-mag-geen-dubbele-opdracht

*28-08-2026 — Een weggevallen verbinding opnieuw proberen is alleen veilig bij lezen/verwijderen; bij een insert maakt het een tweede advertentie*

Bij een weggevallen verbinding (28-08-2026 zag Jaap "EOF occurred in violation of
protocol") is opnieuw proberen NIET vanzelf veilig. Valt de verbinding weg
terwijl het antwoord onderweg is, dan staat de rij er al en maakt de herhaling
er nog een — bij een opdracht in de wachtrij dus een tweede advertentie.

`naast_de_lus(aanroep, herkans=False)` staat daarom standaard uit. Zet hem alleen
aan voor lezen of een update die hetzelfde resultaat geeft. Voor een insert geldt
het patroon uit `crosslist._exec`: zelf een uuid bepalen en `dubbel_is_ok=True`,
zodat een dubbele sleutel "stond er al" betekent.

Tweede, ernstiger les uit dezelfde dag: bij herplaatsen moet ALLE voorbereiding
(vertaling, prijs, instellingen) gebeuren vóór de verwijderopdracht wordt
weggeschreven. Stond die eerst, dan kon een hik de advertentie weghalen zonder
dat er ooit een herplaatsing was vastgelegd — en de status bleef op "active",
zodat zelfs de reddingsronde hem niet zag. De verwijdering moet wel als eerste in
de database staan: `jobs.py` zoekt hem op `created_at <=` die van de herplaatsing.

Vastgelegd in `tests/test_herplaatsen_verbindingshik.py`.
Zie ook "herplaatsen-verliest-advertenties" en "parallelle-supabase-leesacties".

---

## admarkt-toestemming-verdwijnt

*28-08-2026 — De optionele Admarkt-toestemming verdween uit Egberts browser; de scan viel toen door naar de onjuiste melding "je bent niet ingelogd"*

Egbert Brouwer (zakelijk, 4.250 advertenties) kreeg van 22-08 t/m 28-08-2026
twintig keer "You don't appear to be signed in to Marktplaats". Uit de tabel
`jobs` blijkt dat de Admarkt-stap in al die rondes niet gedraaid heeft (anders
had de melding met "Admarkt:" begonnen) — de optionele toestemming voor
admarkt.marktplaats.nl was weg zonder dat hij iets deed. Voor een zakelijk
account is het persoonlijke overzicht per definitie leeg, dus de scan viel door
naar een tak die nooit klopt.

**Why:** een optionele Chrome-toestemming is geen betrouwbaar fundament; hij kan
bij een update of een tweede kopie verdwijnen, en de gebruiker merkt alleen een
verkeerde foutmelding.

**How to apply:** Admarkt-toegang staat sinds 1.0.258 vast in het manifest
(`https://*.marktplaats.nl/*`), de schakelaar is een voorkeur in
chrome.storage, en een leeg persoonlijk overzicht triggert Admarkt sowieso.
Elke mislukte scan noemt nu API-status, aantal, ingelogd en Admarkt aan/uit.
Zie ook "admarkt-zakelijke-marktplaats" en "extension-release-bump-version".

---

## auth-fouten-lijken-op-verkeerd-wachtwoord

*28-08-2026 — Auth-laag vertaalde elke storing naar 401/"verkeerd wachtwoord"; gedeelde Supabase-client kon een wachtwoord op andermans account zetten*

Twee vallen in `backend/api/auth.py` + `deps.py`, beide gerepareerd op 28-08-2026
na de klacht van Egbert Brouwer (eerst uitgegooid na het inloggen, daarna
"Invalid email or password" op een goed wachtwoord).

1. Elke uitzondering werd 401 of "Invalid email or password". Het dashboard gooit
   je bij 401 naar het inlogscherm en de extensie wist haar inlogbewijs — dus één
   weggevallen Supabase-verbinding = klant buitengesloten. Nu gaat alles door
   `auth_met_herkansing()` in database.py: opnieuw proberen, daarna 503.
   **Nooit een storing als 401 naar buiten laten.**
2. `auth.update_user({"password": ...})` schrijft naar de sessie die in de
   Supabase-client staat, niet naar de aanvrager. Op een gedeelde client kan een
   wachtwoordreset dus op het account van een willekeurige andere klant landen.
   Elk auth-endpoint gebruikt nu `verse_auth_client()` — eigen verbinding per
   verzoek. Zie ook "railway-draait-op-anon-sleutel".

**Waarom:** beide fouten zijn onzichtbaar in logs en tests; ze tonen zich alleen
als een klant die zegt dat zijn wachtwoord niet meer werkt.
**Hoe toe te passen:** bij elke auth-klacht eerst `last_sign_in_at`,
`updated_at`, `banned_until` en `recovery_sent_at` van die gebruiker opvragen via
de admin-API voordat je iets aanneemt. Bewaakt door
`tests/test_auth_sessies_gescheiden.py`.

---

## koude-mail-geen-naam-in-aanhef

*28-08-2026 — De koude mail begint altijd met "Hi," — een Marktplaats-verkopersnaam is een winkelnaam, nooit een voornaam*

Daniel (28-08-2026): de verkopersnaam mag nooit meer in de aanhef van een koude
mail staan. Albert Kok kreeg "Hi kok modelauto&#x27;s," — winkelnaam als voornaam
plus onvertaalde HTML-codering.

**Why:** van een Marktplaats-lead kennen we alleen de verkopersnaam, en dat is de
naam van de winkel. Tegen de echte lijst (1.447 leads) gehouden leverde élke
poging om er een voornaam uit af te leiden "Hi Boutique," en "Hi Trimsalon," op;
nul treffers die klopten.

**How to apply:** aanhef is "Hi," tenzij er letterlijk een `voornaam`- of
`contactpersoon`-veld is. Namen die van buiten binnenkomen altijd ontcoderen
(`unescape`) vóór ze worden bewaard. Zie "mailbox-eigenaarschap" en
"mp-video-leadpage".

---

## jaap-plaatsen-ligt-stil

*28-08-2026 — "Openstaand op 28-08-2026 — bij Jaap lukt geen enkele Marktplaats-plaatsing sinds 21-08; 26 opdrachten gepauzeerd, 1.0.258 moet nog naar de Web Store"*

Stand 28-08-2026. Bij Jaap (`26cf5471`) mislukt élke plaatsing op Marktplaats met
"Not published — complete the fields marked in red" terwijl het formulier compleet
is: tekst 205–1936 tekens, prijs gevuld, gratis-keuze aangeklikt, geen rood veld.
Op 21-08 plaatste hij nog 60 advertenties foutloos, toen op extensie **1.0.218**;
sindsdien nul. Bij klant `3bfbed2c` lukt plaatsen wel. Sterkste verdachte: zijn
~50 openstaande Marktplaats-tabbladen — één "Site verlaten?"-venster daarin zet
alle tabbladen van dezelfde site stil, ook het publicerende tabblad. Dat is de fix
uit 1.0.256; hij draait 1.0.251.

Openstaand:
1. `dist/omnivaleur-extension-1.0.258.zip` uploaden in de Chrome Web Store.
2. Jaap alle Marktplaats-tabbladen laten sluiten en de versie laten controleren.
3. 26 herstelopdrachten staan via `scheduled_for` gepauzeerd tot 28-08 15:49 UTC.
4. 58 items hebben nog geen omschrijving — die tekst bestaat nergens meer.

1.0.258 meldt bij een mislukte plaatsing hoeveel foto's het formulier vasthoudt;
dat getal wijst de volgende ronde uit of het aan de foto's ligt.

**Why:** dit is niet afgerond werk, en het staat los van de tekstfix van dezelfde
dag — zonder deze aantekening lijkt het probleem opgelost.

**How to apply:** begin een volgende sessie hierover met de laatste job-fouten van
deze gebruiker, niet met de code. Zie "herplaatsen-verliest-advertenties",
"extension-release-bump-version" en "werkvenster-en-afsluitvraag".

---

## herplaatsen-verliest-advertenties

*28-08-2026 — "Herplaatsen verwijdert eerst; een item zonder omschrijving raakte daardoor de advertentie definitief kwijt (Jaap, 60 stuks, 28-08-2026)"*

Herplaatsen op Marktplaats is twee stappen: eerst weg, dan opnieuw plaatsen. Bij
Jaap (info@zilverwebsite.nl) hadden 532 van 1.222 items geen omschrijving — die
kwamen uit de zoeklijst van Marktplaats, die alleen titel, prijs en één foto
geeft. Het plaatsformulier eist een tekst, dus stap twee brak af nog vóór de
foto's. Op 28-08-2026: 60 advertenties verwijderd, 0 teruggeplaatst, en omdat
Marktplaats een verwijderde advertentie meteen op 410 zet was de tekst ook weg.

Sinds commit f7090b6 weigert `refresh_listing` te verwijderen wat niet terug kan
(`ontbreekt_voor_herplaatsen`) en wordt ontbrekende tekst eerst van de nog live
advertentiepagina gehaald.

**Why:** dit is de enige plek in het systeem waar een fout niet "mislukt" maar
"weg" betekent. Elke nieuwe strategie die eerst verwijdert heeft dezelfde rem
nodig.

**How to apply:** verwijder nooit iets van een platform zolang niet vaststaat dat
het opnieuw geplaatst kan worden. Zie ook "marktplaats-publiceren-valkuilen" en
"import-dubbele-items-over-platforms".

---

## eerst-recente-wijzigingen-lezen

*28-08-2026 — "Begin ELKE sessie met uitzoeken wat er sinds je vorige keer veranderd is, vóór je ook maar iets doet"*

Begin ELKE sessie met uitzoeken wat er veranderd is sinds jij hier voor het laatst
was. Niet alleen bij een codetaak — ook bij een vraag, een mail of een controle.
Pas daarna aan de slag. Daniel heeft dit op 27-08-2026 nadrukkelijk als vaste
gewoonte gevraagd.

**Waarom:** er werken drie partijen aan dit project zonder elkaar te zien —
Daniel op zijn eigen account, de tweede ontwikkelaar (zie
"tweede-ontwikkelaar-partner") en meerdere Claude-sessies naast elkaar. Zonder
deze stap bouw je iets wat er al is, repareer je iets wat net gewijzigd is, of
mis je juist de wijziging die het probleem veroorzaakte. Daniel wil dubbel werk
en tegenstrijdige wijzigingen voorkomen.

Bewezen op 27-08-2026: een eerdere sessie voegde om 14:04 `output_config` toe aan
de Claude-aanroepen van de mailagent; de server draaide op `anthropic==0.34.2`,
die parameter bestond daar niet, de TypeError werd stil opgevangen en vanaf dat
moment kreeg elke lead de standaard verkoopmail. Alleen te zien door de commits
van diezelfde dag te lezen.

**Hoe toe te passen — in deze volgorde, aan het begin van de sessie:**
1. `git log --since="30 hours ago" --name-only` (bij een langere pauze: sinds je
   laatste sessie) en lees de diff van alles wat je onderwerp raakt.
2. Lees de laatste toevoegingen onder aan `docs/team-notes.md`. Daar staat het
   *waarom* van beslissingen die niet uit de code blijkt, en dat bestand reist
   met de repo mee tussen accounts — zie "cross-account-traceerbaarheid".
3. Let op de "auto: update ..."-commits: die komen van de auto-push-hook en
   bevatten het echte werk van eerdere sessies achter nietszeggende teksten.
4. De auteursnaam zegt niets over wie het deed — zie
   "tweede-ontwikkelaar-partner".
5. Zeg in je eerste antwoord kort wat je hebt gezien, zodat Daniel merkt dat je
   het huidige beeld hebt en niet dat van gisteren.

**Geldt ook voor mails en concepten:** beweer nooit iets over wat het product kan
zonder het in de code te hebben gezien. Op 27-08-2026 stond er in een concept aan
een lead "dat kijk ik na" voor twee dingen die gewoon in de code staan (varianten,
WooCommerce), terwijl de echte blokkade — het vaste categoriemodel — ongenoemd
bleef.

---

## werkvenster-en-afsluitvraag

*28-08-2026 — Publiceren draait sinds 28-08-2026 altijd in een ingeklapt werkvenster, en elk werk-tabblad wordt ontwapend voordat het sluit*

Sinds 28-08-2026 (extensie 1.0.256) geldt in extension/background.js:

1. `openWorkerTabInner` gebruikt ALTIJD `state: "minimized"`. Publiceren draaide
   eerder in een gewoon venster "omdat verborgen tabbladen trager zijn"; dat
   klapte bij elke advertentie het venster open over Daniels werk heen. De
   vertraging wordt geaccepteerd — zie "verborgen-tabblad-vertraagt-wachttijden".
   Niet terugdraaien zonder dat Daniel er expliciet om vraagt.

2. Geen enkel werk-tabblad wordt nog met een kale `chrome.tabs.remove` gesloten:
   alles loopt via `sluitWerkTabblad` / `stuurWerkTabbladNaar`, die eerst
   `ontwapenAfsluitvraag` aanroepen. Reden: het "Site verlaten?"-venstertje van
   een Marktplaats-formulier bevriest ÓÓK het tabblad dat op dat moment een
   andere advertentie invult (zelfde site = zelfde proces). content/unload_guard.js
   (MAIN world, document_start) doet uit zichzelf niets — hij zet de melding pas
   uit als de extensie er zelf om vraagt.

**Why:** allebei zijn ze onzichtbaar in de code maar direct zichtbaar voor de
verkoper; een "opruimende" wijziging zou de klacht meteen terugbrengen.

**How to apply:** raakt een taak het openen of sluiten van werk-tabbladen, houd
deze twee regels aan; tests staan in tests/test_relist_foto_en_venster.py.

---

## klantenslot-valt-dicht

*27-08-2026 — "Bij twijfel geldt iedereen als klant; een lege lijst uit Supabase is een storing, geen antwoord"*

`is_klant()` in `scripts/leadgen_mail.py` is de rem die betalende klanten uit de
koude mail houdt. Sinds 27-08-2026 valt die rem DICHT in plaats van open: lukt het
niet om de accountlijst op te halen, dan geldt iedereen als klant en gaat er geen
mail uit — met een luide melding, want nul mails ziet er anders precies zo uit als
een rustige dag.

**Waarom:** hiervoor ving de functie elke fout op met een lege verzameling, die ook
nog werd onthouden. Dan zei hij voor iedereen "geen klant" en werd elke klant weer
prospect. Dat is het pad waarlangs Jaap een afscheidsmail kreeg terwijl hij betaalde
(zie "klanten-zijn-geen-leads").

**Hoe toe te passen:**
- Een lege lijst uit Supabase is nooit een antwoord: er is altijd minstens één
  account. Leeg = verkeerde sleutel (auth/admin vereist service_role, zie
  "railway-draait-op-anon-sleutel").
- Ziet Daniel "0 mails verstuurd", kijk dan eerst of de klantenlijst gelezen kon
  worden voordat je naar het rooster kijkt.
- Deze vorm — fout opvangen, lege waarde teruggeven, resultaat cachen — is in dit
  project vaker de oorzaak dan de oplossing.

---

## railway-draait-op-anon-sleutel

*27-08-2026 — De live server draait op de Supabase anon-sleutel; alles wat auth.admin gebruikt faalt daardoor stilletjes — waaronder alle proefherinneringen*

Gemeten op 13-08-2026 via `https://omnivaleur.com/health` →
`config.supabase_key_role: "anon"` (die rol staat er sindsdien in; een JWT draagt
zijn claims onversleuteld, dus dit lekt niets).

**Gevolg:** elke aanroep van `db.auth.admin.*` krijgt "User not allowed". Met de
anon-sleutel werkt de rest van de app gewoon, omdat RLS op de meeste tabellen
uit staat — daardoor viel dit nooit op.

**Wat er hierdoor stil kapot was:**
- `services/billing.py` — proefherinneringen. Bewijs: 27 abonnementen, 22
  verlopen, **0** verstuurde mails. De fout werd opgevangen met een stille
  `continue`; die logt nu hard. Zie "proefperiode-en-toegangsslot".
- `api/auth.py` — je e-mailadres wijzigen.
- `services/analytics_report.py` en `services/announcement.py` — gebruikers
  opsommen voor het weekrapport en voor aankondigingsmails.
- `api/billing.py` — dit had de checkout al een keer gesloopt; daar is het
  omzeild door het adres uit het token te halen in plaats van de oorzaak te
  verhelpen. Dat is de reden dat het elders bleef liggen.

**Fix 1 (14-08-2026 gedaan):** `SUPABASE_KEY` op Railway is nu de
**service_role**-sleutel. Controleer op `/health`. Let op: de sleutel in de
lokale `.env` is óók anon, dus lokaal testen bewijst hier niets.

**Fix 2 — en dit was de échte reden dat fix 1 niet genoeg was.** De hele app
liep over ÉÉN gedeelde `create_client`. Een Supabase-client onthoudt zijn laatste
sessie: zodra er ergens `sign_in_with_password`, `set_session` of
`refresh_session` op gebeurt, stuurt diezelfde client daarna het token van díé
gebruiker mee in plaats van de servicesleutel. Alle `auth.admin`-aanroepen kregen
daarna "User not allowed", ook met de juiste sleutel.

`backend/database.py` heeft nu drie gescheiden verbindingen: `get_db()`
(gegevens), `get_admin_db()` (alleen `auth.admin.*`, wordt nooit ingelogd) en
`get_auth_db()` (registreren/inloggen/wachtwoord — die mág vervuild raken).
Zet nooit een `auth.admin`-aanroep terug op `get_db()`.

`change_email` in api/auth.py logt de gebruiker in om zijn wachtwoord te
controleren en deed daarna direct de beheerdersactie op dezelfde client — die
kon dus per definitie nooit werken.

Controleren zonder te wachten op de dagelijkse taak: knop **"Who would get a
trial mail?"** in Owner tools (`POST /api/billing/admin/reminder-dryrun`).
Verstuurt niets.

**ACHTERHAALD sinds 27-08-2026.** `/health` op omnivaleur.com toont
`"supabase_key_role": "service_role"` — de server draait dus op de goede sleutel
en auth.admin werkt weer. Controleer die regel voordat je een storing hierop
gokt; hij staat er juist om dit te kunnen zien. Wat er van deze notitie overblijft
is het patroon: een verkeerde sleutel geeft geen foutmelding maar een leeg
antwoord, en dat leest als "er is niets". Zie "klantenslot-valt-dicht".

---

## extension-version-floor

*27-08-2026 — De ondergrens voor de extensieversie staat op twee plekken en moet samen verhoogd worden; een oude kopie levert stil half werk af*

De minimale extensieversie staat sinds 27-08-2026 op **1.0.244** en is op twee
plekken vastgelegd die gelijk moeten blijven:

- `frontend/app.html` → `EXT_MIN_VERSION` (blokkerende melding in het dashboard)
- `backend/api/jobs.py` → `MINIMALE_SCANVERSIE` (server deelt geen werk uit)

`tests/test_extensieversie.py` faalt als ze uiteenlopen.

De extensie stuurt haar versie sinds 1.0.250 bij elk verzoek mee in het kopstuk
`X-Omnivaleur-Ext`. Kopieën van vóór 1.0.250 sturen dat niet; die worden
server-side dus niet tegengehouden — alleen het dashboard blokkeert ze.

**Why:** Jaap (info@zilverwebsite.nl) draaide drie weken 1.0.218 terwijl de Web
Store op 1.0.249 stond. Die kopie nam werk wél aan: ze bleef staan op het
"verkocht via Marktplaats?"-venster en maakte daarna advertenties zonder foto's
en zonder tekst. Het dashboard toonde al die tijd een groen
"Extension active (v1.0.218)", want de ondergrens stond nog op 1.0.171. Werk dat
niet wordt opgepakt is zichtbaar; werk dat half wordt afgemaakt niet.

**How to apply:** verhoog beide grenzen tegelijk zodra een fix uitrolt waarvan
de gebruiker móet merken dat hij hem mist. Elke wijziging in `extension/` vraagt
verder een versiebump plus `scripts/build-extension.sh` — zie
"extension-release-bump-version". Let bij klachten altijd eerst op de versie:
zie ook "tweede-extensiekopie".

---

## extensie-const-na-await-valstrik

*27-08-2026 — "In de content-scripts moet elke const/let bóven `await getJob()` staan, anders valt de invulstap stil om"*

De content-scripts van de extensie (o.a. `extension/content/vinted.js`) zijn één
grote async functie. Zodra de code bij `const job = await getJob();` wacht, zijn
de regels daarónder nog niet uitgevoerd. Een `const` die verderop staat bestaat op
dat moment dus niet, en elke functie die hem gebruikt stopt met een harde fout op
het moment dat hij aangeroepen wordt.

**Dit is al vier keer misgegaan:** de kleurstap, de categoriekeuze (`V_KLEDING`),
de prijscontrole (`PRICE_ERR_RE`) en op 27-08-2026 `BLAD_VOORKEUR`/`enkelvoud`.

Wat het zo verraderlijk maakt: `step()` in `extension/content/shared.js` vangt de
fout op, logt "stap X: FOUT" en gaat gewoon door. Het publiceren stopt dus niet —
de advertentie gaat zonder categorie de deur uit. Je ziet geen crash, alleen een
advertentie die niet klopt.

**Hoe toe te passen:**
- Nieuwe hulpwaarden altijd boven `const job = await getJob();` zetten, bij de
  andere constanten. Er staat een waarschuwingsblok in vinted.js op die plek.
- `tests/test_vinted_categories.py::test_geen_hulpwaarden_na_de_hoofdstroom`
  bewaakt dit. Die test faalde maandenlang zonder dat iemand keek — zie
  "eerst-recente-wijzigingen-lezen".
- Elke wijziging in `extension/` vereist een versiebump, zie
  "extension-release-bump-version".

---

## mailagent-geen-sjabloon-vangnet

*27-08-2026 — "Mislukt het echte antwoord, dan komt er GEEN concept — nooit meer een standaardmail als vangnet"*

Beslissing van Daniel, 27-08-2026: als de mailagent geen echt antwoord kan
schrijven, komt er **geen concept**. Nooit meer een sjabloon of een sussende
plaatshoudertekst als vangnet.

**Waarom:** een verkeerd antwoord kost een lead, geen antwoord kost hooguit een
paar minuten. Erger nog: een vangnettekst verbergt de storing — Daniel ziet een
concept liggen en denkt dat het werk gedaan is. Rob Kruizinga (Borstelbeer) vroeg
naar productvarianten en kreeg video, prijs en kanalenlijst terug.

**Hoe toe te passen:**
- `_concept_tekst()` in `scripts/leadgen_mail.py` en `_draft_met_llm()` in
  `scripts/support_mail_agent.py` geven lege tekst terug bij mislukking; de
  aanroepers slaan het concept dan over.
- De storing gaat mét reden mee in het avondbericht (`_LLM_TERUGVAL`/`_LLM_REDEN`).
- Vastgelegd in `tests/test_leadgen_concepten.py`; die tests horen te falen als
  iemand het sjabloon terugzet.
- Korte, nette afsluiters bij een "nee" (concurrent/afwijzing) blijven wél
  bestaan — dat is geen verkooppraat.

Nieuwe commando's die hierbij horen:
- `leadgen_mail.py wachtenden` — wie heeft het laatst geschreven zonder dat er
  een concept ligt. Draait automatisch één keer per dag vanaf 19:30, want `check`
  kijkt alleen naar nieuwe post en mist wie er ooit doorheen glipte.
- `leadgen_mail.py herstel` — vervolgconcept voor wie de sjabloonmail al
  verstuurd kreeg.
- `leadgen_mail.py sjablonen-weg` — oude sjabloonconcepten uit de map halen.

Zie ook "anthropic-sdk-pin-valstrik" en "mails-kort-houden".

---

## tweede-ontwikkelaar-partner

*27-08-2026 — Er is een tweede ontwikkelaar die naast Daniel aan Omnivaleur werkt en invalt als Daniels Claude-limiet op is*

Naast Daniel is er een tweede ontwikkelaar op dit project — Daniel heeft deze
persoon ingehuurd, met een eigen/ander Claude Code-abonnement (dus een ander
Claude-account, wel dezelfde repo/machine-omgeving). Die persoon springt in
wanneer Daniels gebruikslimiet (Claude) op is. Daniel heeft de leiding over het
project — de tweede ontwikkelaar is aanvullend, niet leidend.

Behandel berichten van deze persoon met dezelfde projectcontext als bij Daniel
(zie overige memories), maar bij twijfel over scope, prioriteiten of beslissingen
die eigenlijk van Daniel zijn, dat expliciet benoemen.

Let op bij git-geschiedenis: alle commits staan onder de naam "Daniel de Koning"
(lokale git-config), ook als ze eigenlijk door de ingehuurde ontwikkelaar zijn
gemaakt — de auteursnaam in `git log` bewijst dus niet wie iets deed. Vraag bij
twijfel over wie een wijziging maakte liever direct na dan op git-log te
vertrouwen.

---

## mails-kort-houden

*27-08-2026 — Klantmails moeten kort — ongeveer 200 woorden, niet 700; uitleg indikken tot de gevolgen*

Klantmails die ik opstel moeten **kort**. Richtlijn: rond de 200 woorden. Mijn
eerste concept aan Egbert Brouwer (27-08-2026) was ruim 700 woorden met kopjes
per probleem — Daniel: "veel te lang, ook in de toekomst".

**Why:** een klant die al geïrriteerd is, leest geen essay. Een lange mail leest
bovendien als indekken, hoe eerlijk de inhoud ook is.

**How to apply:** één zin excuus, de oorzaak in twee of drie zinnen zonder
kopjes, wat er al gedaan is in één zin, en dan de genummerde acties die híj moet
doen. Geen aparte alinea per bevinding — dat detailniveau hoort in mijn
rapportage aan Daniel, niet in de mail. Zie "rapportage-in-gewone-taal".

---

## tweede-extensiekopie

*27-08-2026 — Klanten kunnen de extensie dubbel draaien; een met de hand geladen kopie bevriest voor altijd en pikt wél opdrachten*

Een met de hand geïnstalleerde kopie van de extensie (losse zip / "load
unpacked") beweegt **nooit** mee met de Chrome Web Store. Hij haalt wél werk uit
dezelfde wachtrij als de bijgewerkte kopie. Wie het eerst een opdracht pakt,
bepaalt de uitslag.

Egbert Brouwer draaide 1.0.207 (16-08-2026) naast een bijgewerkte kopie:
13 scans geslaagd, 18 mislukt — en die 18 meldden allemaal "je bent niet
ingelogd bij Marktplaats" terwijl hij gewoon ingelogd was. Twee weken lang
"soms doet hij het wel, soms niet".

**Why:** dit is van buitenaf onzichtbaar en niet te raden. De enige aanwijzing
is het versiestempel `[extensie X.Y.Z]` dat de extensie zelf in elke
foutmelding zet.

**How to apply:** de gepubliceerde Web Store-versie is te controleren zonder
inloggen via de CRX-updatecheck:
`https://clients2.google.com/service/update2/crx?response=updatecheck&x=id%3Dgfaogapbhaacfbpdppdcmnkjndlphleh%26uc`.
Wijkt de versie in een foutmelding daarvan af, dan draait er een tweede kopie.
De server weigert sinds 27-08-2026 scans van versies onder `MINIMALE_SCANVERSIE`
(backend/api/jobs.py) en zet ze terug in de wachtrij; het dashboard waarschuwt
erover. Zie "extension-release-bump-version".

---

## parallelle-supabase-leesacties

*27-08-2026 — Gelijktijdige Supabase-verzoeken over de gedeelde client mislukken massaal (45 van 55 gemeten); altijd na elkaar lezen*

De Supabase-client is synchroon en deelt **één** HTTP/2-verbinding. Meerdere
werkdraden die daar tegelijk overheen gaan krijgen van Cloudflare `400 Bad
Request` of van de verbinding zelf `RemoteProtocolError:
ConnectionTerminated`.

Gemeten 27-08-2026 op het account van Egbert Brouwer (2.135 items):
**8 tegelijk → 45 van de 55 verzoeken mislukt. Na elkaar → 0 mislukt, 4,4
seconden voor alles.**

**Why:** hierdoor was "Import all → Items" van 25-08 tot 27-08-2026 voor
iedereen dood, met alleen een kale "Server error (500)" op het scherm. In
dezelfde functie zat trouwens ook `db.table("items").eq(...)` zonder `select()`
ervoor — dat bestaat niet en gooide meteen `AttributeError`. Twee fouten, één
regel. Zie ook "postgrest-in-filter-url-limiet".

**How to apply:** nooit een ThreadPoolExecutor over Supabase-queries. Gebruik
`fetch_all` / `fetch_all_in` uit `backend/database.py`; die zijn sequentieel en
herkansen per pagina. Snelheid is hier nooit het probleem geweest — de
"optimalisatie" was zelf de storing. En: `db.table(x)` geeft een builder zónder
filters, dus `.select()` moet altijd eerst.

---

## postgrest-in-filter-url-limiet

*27-08-2026 — Boven ~639 id's in een .in_()-filter weigert httpx het verzoek; dat legde scans, verkoopcontrole en relist stil voor grote accounts*

PostgREST zet een `.in_("item_id", [...])` als tekst in de URL. Gemeten
27-08-2026 met echte item-id's: tot 639 id's gaat goed, **vanaf 640 gooit httpx
`InvalidURL: URL component 'query' too long`** — geen nette foutmelding, maar
een uitzondering midden in de verwerking.

Los daarvan geldt het stille 1.000-rijenplafond: `.limit(10000)` levert gewoon
1.000 rijen op, zonder enige melding.

**Why:** dit sloopte het account van Egbert Brouwer (Papa's Plectrums, 2.135
items) zonder één zichtbare foutmelding. Zijn Marktplaats-scans werden wel
opgehaald (3x 2.000 nieuwe advertenties) maar nooit opgeslagen, want de opdracht
stond al op "klaar" voordat het opslaan stukliep. Ook de verkoopcontrole
(polling) lag hierdoor voor álle klanten stil. Zie "railway-draait-op-anon-sleutel"
voor het andere soort stille storing.

**How to apply:** bij elke query over items/listings `fetch_all` gebruiken in
plaats van `.limit(...)`, en `fetch_all_in` / `update_in` uit
`backend/database.py` (brok = 200) in plaats van een kale `.in_(...)`. En:
testen met een groot account, want een testaccount met 50 items bewijst niets.

---

## omnivaleur-positionering-vs-channable

*26-08-2026 — "Channable is de grote, slecht beoordeelde marketplace-tool; Omnivaleur differentieert door alleen tweedehands-platforms en alleen Europa te bedienen"*

**Channable** is de tool die de meeste marktplaatsverkopers nu gebruiken —
groot, maar zeer slecht beoordeeld. Channable focust breed op
marketplace-verkopers in de ruimste zin (incl. bol.com etc).

**Why:** Omnivaleur kiest bewust een smallere niche om zich te onderscheiden:
uitsluitend tweedehands-platforms (Marktplaats, 2dehands, Vinted, eBay,
Shopify), niet marketplace-verkopers in het algemeen. Reden voor
Europa-only: buiten Europa (vooral US/UK) is de concurrentie tussen
cross-listing-tools veel groter, daar wil Daniel bewust niet mee concurreren.

**How to apply:** bij marketing-, positionerings- of ads-vraagstukken nooit
Omnivaleur pitchen als algemene marketplace-tool (dat is Channables terrein,
en daar staat Channable al slecht op reviews) — altijd de tweedehands-niche
en Europa-focus benadrukken. Eerste paid-ads-fase (zie
"monaim-50-50-partnership") richt zich specifiek op kleding/schoenen-
verkopers, waar het dashboard het best voor werkt.

---

## monaim-50-50-partnership

*26-08-2026 — "Monaim is 50/50-partner op Omnivaleur (Growth & Content), aparte deal van zijn eigen merk Somnia; juridische vastlegging bewust uitgesteld"*

Monaim bouwt sinds 2026-08-26 mee aan **Omnivaleur** als 50/50-partner —
losstaand van zijn eigen merk **Somnia** (paid ads/e-commerce, aparte
context, niet Omnivaleur-gerelateerd). "omnivaleur-brand-never-a-verb"

**Why:** Daniel wil eerst zien hoe de samenwerking in de praktijk loopt
voordat er iets juridisch (aandelen/contract) wordt vastgelegd. De 50/50 is
dus nu een mondelinge afspraak, bewust nog geen contract.

**Herkomst van het merk:** Revaleur is Daniels eigen vintage kledingmerk;
Omnivaleur is de software die daaruit is ontstaan (gebouwd om Revaleurs
eigen cross-listing te automatiseren) en later losgetrokken tot een eigen
SaaS-product.

**Rol & taken:** Growth & Content Partner — wekelijks Nederlandstalig
contentschema voor TikTok/Instagram (eigen suggestie: 3 posts + 1 video/week
als eerste test) en een social-DM-outreachsysteem verkennen naast de
bestaande koude-mail-leadgen "leadgen-vier-bronnen". **Maar de echte
bedrijfsbrede prioriteit ligt nu (tot 50 gebruikers) bij
dashboard-verbetering, debuggen en feedback verzamelen** — Monaims
content/outreach-werk loopt daarnaast, niet in plaats daarvan.

**Paid ads — pas vanaf 50 gebruikers (harde drempel, geen vage voorwaarde):**
- Eerste fase richt zich **alleen op kleding/schoenen-verkopers** — daar is
  het dashboard voor gebouwd en presteert het het best. Niet breder targeten
  in fase 1.
- Creatives: organische content mag hergebruikt worden als de kwaliteit goed
  genoeg is; Monaim mag ook aparte landingspagina's bouwen.
- Geografie: **alleen Europa**, bewust weg van US/UK — daar is de concurrentie
  voor cross-listing-tools het grootst.
- Concurrentie: **Channable** is de grote speler die de meeste
  marktplaatsverkopers nu gebruiken — groot, maar zeer slecht beoordeeld.
  Focust breed op marketplace-verkopers (incl. bol.com etc). Omnivaleur
  differentieert door **uitsluitend tweedehands-platforms** te bedienen, voor
  nu niet breder positioneren.

**Blogs:** volledig geautomatiseerd (backend/content/quality.py + dagelijkse
auto-publish-job) — geen taak voor Monaim, alleen ter info.

**Toegang:** volledige Notion-workspace-toegang toegekend.

**Gratis account:** `backend/services/billing.py` heeft een
`complimentary`-subscriptionstatus (onbeperkte toegang, geen
stripe_subscription_id nodig) — expliciet niet via `status = active` zonder
stripe-id, want dat pad is bewust geblokkeerd tegen een oude bug. Monaim
meldt zich zelf normaal aan met eigen e-mail en stuurt dat adres naar
Daniel; Daniel zet daarna zijn subscriptions-rij op `complimentary` in
Supabase.

**How to apply:** verwar dit niet met Somnia-gerelateerde vragen (aparte
klant/merk, geen Omnivaleur-partnerschap). Volledige, meest actuele context
staat in `docs/team-notes.md` in de repo zelf: dat bestand is leidend bij
tegenstrijdigheid, deze memory is het lokale snelle geheugen op dit account.

---

## cross-account-traceability

*26-08-2026 — "Team/business-beslissingen altijd ook naar docs/team-notes.md schrijven, niet alleen naar lokale memory — Daniel werkt met meerdere Claude-accounts"*

Schrijf elke team-, partnerschap- of bedrijfsbeslissing (rollen, toegang,
deals, niet-vanzelfsprekende context) ook naar `docs/team-notes.md` in de
omnivaleur-repo zelf, en push dat mee — niet alleen naar deze lokale memory.

**Why:** Daniel gebruikt meerdere Claude Code-sessies/accounts. Lokale
`~/.claude`-memory is per account en gaat niet mee naar een andere login of
machine; een repo-bestand wel, via git. Zonder dit loopt een andere sessie
achter of herhaalt Daniel zichzelf. `CLAUDE.md` in de repo-root verwijst
elke sessie al naar `docs/team-notes.md` als startpunt hiervoor.

**How to apply:** bij elke wijziging die niet puur code is maar impact heeft
op mensen/rollen/afspraken — schrijf eerst de repo-notitie (en push, of laat
de auto-push hook dat doen), pas daarna eventueel een lokale memory erbovenop
voor snel opzoeken. De repo-notitie is leidend bij tegenstrijdigheid.

---

## trendmotor-gesproken-hooks

*26-08-2026 — TikTok levert zelf de ondertiteling mee (gesproken hook), YouTube niet; YouTube-datums moeten uit de zoekpagina komen want de videopagina is vanaf GitHub dicht*

De trendmotor meet sinds 22-08-2026 de échte hook: wat er in de eerste drie
seconden gezégd wordt, niet het bijschrift.

- TikTok geeft in `item_list` per video `video.subtitleInfos` met een WebVTT-link
  (ASR = origineel, MT = machinevertaling — kies ASR). Ruim 60% van de video's
  heeft het. De link is ondertekend en verloopt binnen uren, dus ophalen moet
  binnen dezelfde browsersessie, via `ctx.request.get` met een TikTok-Referer.
- Er komt veel Duits en Pools door de hashtags heen; filter op `LanguageCodeName`
  (nld/eng), anders meet je een andere markt.
- YouTube-ondertiteling is dicht: `timedtext` geeft 200 met een lege body.
- YouTube's videopagina werkt lokaal maar geeft vanaf GitHub Actions een
  botpagina — dat mislukte stil (0 van 48 datums, dus YouTube telde in geen enkel
  tijdvenster mee). Datums komen nu uit `publishedTimeText` van de zoekpagina
  ("3 weken geleden"), gemarkeerd als geschat en geweerd uit de 7-dagenlaag.
  Sinds 26-08-2026 staat `YT_API_KEY` als GitHub-secret ingesteld: exacte datums,
  likes, reacties en duur (15/15 in de controle). Dat legde twee scheefheden
  bloot: YouTube's shorts-zoekfilter laat video's van 3 minuten door (nu een
  grens van 180 sec), en engagement mag geen delen/bewaren meebellen omdat
  alleen TikTok die vrijgeeft — het is nu likes plus reacties.

Zie ook "trendmotor" en "tiktok-gratis-schrapen".

---

## weekrapport-opmaak

*26-08-2026 — Zondagse marketingmail is opgemaakte HTML (backend/services/analytics_email.py); historie is retroactief uit GSC/GA4 dus geen snapshottabel nodig; Pinterest meldt géén weergaven*

Sinds 16-08-2026 is de zondagse marketingmail opgemaakt: samenvattende zin, vier
tegels, 8-wekengrafiek, hooguit drie acties, dan pas details. Meten gebeurt in
`analytics_report.py`, vertellen in `analytics_email.py`.

Wat je moet weten voordat je hem aanpast:

* **Geen opslag nodig voor trends.** Search Console en GA4 leveren met
  terugwerkende kracht; `_trend()` doet één query over acht weken en verdeelt die.
  De `analytics_snapshots`-tabel bestaat niet en is niet nodig.
* **Grafieken zijn tabelcellen met een `height` in pixels.** Gmail toont geen
  svg, blokkeert afbeeldingen en gooit `<style>`-blokken weg. Procenthoogtes
  werken evenmin. Er gaat altijd óók een platte tekstversie mee (`send_email(...,
  html=...)` is nieuw en stuurt beide).
* **Pinterest publiceert geen weergavecijfer.** Een 0 daar is een ontbrekende
  meting, geen slechte week — het rapport toont "niet gemeten" en laat Pinterest
  buiten de adviezen. TikTok meldt wél weergaven; die 0 is dus echt.
* **Een mislukte scrape mag niet lijken op 'niets gepost'.** Eerder verdween een
  kanaal geruisloos uit de mail (zo miste Instagram). Nu staat elk ingesteld
  kanaal in de tabel, met `fetched=None` als "niet opgehaald".
* De social-trend per kanaal komt uit dezelfde opgehaalde posts (laatste 25),
  dus ~4 weken diep, en elk kanaal heeft zijn eigen schaal.

Testen kan zonder te wachten op zondag:
`POST /api/analytics/send-report?token=<analytics_dashboard_token>` bouwt het
rapport mét social en mailt het naar `owner_email`. Duurt ~1 minuut (Apify).

**Why:** de oude mail was een platte lijst waarin dezelfde cijfers meerdere keren
terugkwamen en "+100%" op drie klikken stond; hij is er niets mee opgeschoten.

**How to apply:** verandert er iets aan de mail, stuur dan meteen een testmail via
dat endpoint — de opmaak is pas te beoordelen in Gmail zelf. Zie ook
"rapportage-in-gewone-taal" en "deploy-pipeline".

**Beeld in een mail:** Gmail laat plaatjes die als `data:`-URI in de HTML zitten
weg — je krijgt lege vakjes zonder enige foutmelding. De enige vorm die werkt is
een los meegestuurd onderdeel met een `cid:`-verwijzing: `add_alternative(html,
subtype="html")`, dan op dát deel `add_related(bytes, maintype="image",
subtype="jpeg", cid="<naam>")`. Bevestigd werkend in Daniels Gmail op
26-08-2026 via de trendmotor-mail (zie "trendmotor").

---

## trendmotor

*26-08-2026 — Wekelijkse social-trendmotor draait bij GitHub Actions (niet Railway) omdat de meting een echte browser nodig heeft*

De trendmotor meet elke dinsdag 08:30 wat er in de niche werkt en mailt Daniel
vijf video-opdrachten, met het dashboard als bijlage.

**Draait bij GitHub Actions, bewust niet op Railway.** De meting heeft Chromium
nodig; Railway bouwt met Nixpacks zonder browser, en die daar inbouwen zet de
bouw van de live website op het spel voor een taak die er niets mee te maken
heeft. Bij GitHub staat de browser standaard klaar en raakt een mislukte meting
de site niet.

Bestanden: `scripts/social_trends_discover.py` (meten), `_analyse.py` (patronen),
`_dashboard.py` (pagina met beeld + filters), `_rapport.py` (mail + Notion),
`.github/workflows/trendmotor.yml`.

Details die niet vanzelf spreken:
- **Dubbele cron** (06:30 en 07:30 UTC op dinsdag) plus `--alleen-uur 8`: GitHub
  roostert alleen in UTC en Nederland schuift twee keer per jaar een uur op. De
  verkeerde beurt stopt zichzelf. Nooit "opschonen" tot één cron.
- **Broncontrole op de opdrachten**: elke door Claude geschreven opdracht moet
  een URL noemen die letterlijk in de meting voorkomt, anders wordt hij
  weggegooid. Dat is de enige rem op verzonnen voorbeelden.
- **Streaming verplicht** bij de Anthropic-aanroep: zonder streaming liep de
  aanroep in een leestijd-time-out en ging de mail stil zonder opdrachten uit.
- Geheimen stonden er al (ANTHROPIC_API_KEY, NOTION_TOKEN, MAIL_PASS via Zoho).

Zie "tiktok-gratis-schrapen" en "apify-gratis-limiet-op".

**Twee stille faalvormen die het rapport wekenlang tegenhielden (gevonden 26-08-2026):**

- GitHub start een geroosterde taak vaak 30-60 min te laat. Een klokcontrole op
  precies één uur (`--alleen-uur 8`) stuurde daardoor beide dinsdagbeurten weg
  terwijl de taak "geslaagd" meldde. Nu een venster 08-11 plus een merkbriefje
  (`data/laatste-rapport.txt`) tegen dubbele mail; dat briefje en het archief
  worden vooraf vers uit main gehaald, want de tweede beurt van dezelfde dag
  draait op de code van vóór de eerste.
- Notion weigert een link met een lege url met een 400 en laat dán de hele
  pagina vallen. `DASHBOARD_URL` is nooit ingesteld, dus het archief werd elke
  week volledig geweigerd terwijl de rest klopte. Log altijd `response.text` bij
  Notion-fouten; "HTTPStatusError" alleen zegt niets.

---

## mp-video-leadpage

*22-08-2026 — "Concept-mails van de mailagent moeten naar /mp-video linken, nooit naar de kale YouTube-video"*

De tweede mail in de koude-mail-sequence (en elk concept dat de mailagent klaarzet)
moet linken naar `https://omnivaleur.com/mp-video`.

Nooit meer de kale YouTube-link versturen. Concreet vervangen:
- OUD (niet gebruiken): `https://youtube.com/shorts/ymDeS37aBW4`
- NIEUW (altijd deze):  `https://omnivaleur.com/mp-video`

**Why:** Daniel wil een eigen, trackbare leadpagina met UTM's, founder-story en
dashboardbeelden i.p.v. rechtstreeks naar YouTube sturen — geeft meer controle
over conversie en meetbaarheid.

**How to apply:** De link staat als constante `VIDEO` in
[scripts/leadgen_mail.py:82](../../scripts/leadgen_mail.py) — is al aangepast
naar de leadpagina (22-08-2026). Bij het schrijven van nieuwe mailteksten of
templates: gebruik altijd die `VIDEO`-constante, nooit een los ingetypte
YouTube-URL. Zie ook "mailagent-slimme-antwoorden" en "koude-mail-autonoom".

---

## tiktok-gratis-schrapen

*21-08-2026 — TikTok is gratis te schrapen met Playwright+stealth, maar alleen met een verse browsercontext per hashtag*

TikTok-cijfers (views, likes, shares, saves) zijn gratis te halen zonder Apify:
laad de hashtagpagina met Playwright en onderschep het `item_list`-antwoord dat
TikTok zelf ophaalt. Twee valkuilen die stille mislukking geven, geen foutmelding:

1. TikTok antwoordt bij afwijzing met **HTTP 200 en een lege body** — nooit met
   een foutcode. Wie op status controleert denkt dat het lukt.
   Wat wél nodig is: de chromium-vlag `--disable-blink-features=AutomationControlled`.
   `playwright-stealth` blijkt níet geïnstalleerd en is ook niet nodig; headless
   werkt gewoon.
2. Bij hergebruik van één browsersessie levert alleen de **eerste** hashtag data
   op; alles daarna komt leeg terug. Nodig: nieuwe browser/context per hashtag
   plus ~8 seconden pauze. Kost ~25 s per hashtag.

Gemeten 21-08-2026: 22 hashtags → 1033 video's, 806 creators.
Instagram kan dit niet (login-muur) en loopt via Apify.
YouTube heeft niets van dit alles nodig: `ytInitialData` in de zoekpagina bevat
de views, dus een gewone GET volstaat — geen API-sleutel.

Code: `scripts/social_trends_discover.py`. Zie "apify-gratis-limiet-op".

---

## apify-gratis-limiet-op

*21-08-2026 — Apify staat op het gratis tier; de maandlimiet was op 21-08-2026 uitgeput*

Het Apify-account draait op het **gratis tier**. Op 21-08-2026 gaf elke
actor-aanroep "Monthly usage hard limit exceeded" — geen enkele scrape lukte
meer tot de maandreset.

Gevolg: alles wat op Apify leunt ligt dan stil, ook de bestaande wekelijkse
social-scrape van de eigen profielen (`backend/services/social_scrape.py`).
Dat faalt zacht, dus je ziet het niet als foutmelding maar als een lege sectie
in het zondagse marketingrapport.

Instagram is het enige platform waarvoor Apify echt nodig is; TikTok en YouTube
kunnen gratis, zie "tiktok-gratis-schrapen".

---

## mailagent-op-de-server

*20-08-2026 — koude-mailmachine draait sinds 20-08-2026 op Railway, niet meer op de Mac; versturen gaat via Resend vanaf omnivaleur.nl*

De mailagent draait sinds 20-08-2026 op Railway (scheduler-taak `leadgen_tick`,
elke 10 minuten), niet meer via de LaunchAgent op de Mac. Die staat bewust uit
(`com.omnivaleur.leadgen.plist.uit`) — hij mag NOOIT op twee plekken tegelijk
draaien, anders krijgt dezelfde ontvanger twee keer dezelfde mail.

Versturen gaat over https via Resend, want Railway blokkeert SMTP. Beide domeinen
staan verified in Resend: omnivaleur.com (product) en omnivaleur.nl (koude mail,
bewust apart zodat een spamklacht nooit de klantmail raakt). DNS van omnivaleur.nl
staat bij **Namecheap**, niet bij Cloudflare — het domein staat wel in Cloudflare
maar de nameservers wijzen nog naar registrar-servers.com, dus wat je daar invult
doet niets.

Controle zonder gokken: `/health` toont `leadgen_tick`, `leadgen_resend` en
`leadgen_mailbox`; `/health/resend` toont welke domeinen geaccepteerd worden.
Zie "mailagent-slimme-antwoorden", "klanten-zijn-geen-leads",
"railway-blokkeert-smtp".

---

## klanten-zijn-geen-leads

*20-08-2026 — de mailagent mag klanten nooit als lead behandelen — geen koude mail, geen video/prijs, geen afscheidsmail*

Wie een Omnivaleur-account heeft is KLANT, geen prospect. De mailagent stuurde op
20-08-2026 aan Jaap (zilverwebsite.nl, al dagen klant, met een dringende vraag over
100 verlopende advertenties) een afscheidsmail: "veel succes met de winkel".

**Why:** Daniel heeft met deze mensen een lopende relatie die veel verder gaat dan
wat er in de leadlijst staat. Een verkoopmail of afscheidsgroet aan een betalende
klant met een probleem beschadigt dat vertrouwen direct, en Daniel moet het daarna
zelf rechtzetten — precies het werk dat de agent hoorde weg te nemen.

**How to apply:** `is_klant()` in `scripts/leadgen_mail.py` leest de accounts uit
Supabase auth. Voor een klant: geen koude mail, geen opvolger, geen afsluitmail,
geen sjabloon-vangnet (liever GEEN concept dan een verkeerd concept), en een eigen
set schrijfregels (`_KLANT_REGELS`) zonder verkoop. Dit geldt ook voor alles wat ik
zelf schrijf: check bij elk concept eerst wat de geschiedenis met die persoon is.
Zie "mailagent-slimme-antwoorden" en "mailbox-eigenaarschap".

---

## mailagent-slimme-antwoorden

*20-08-2026 — mailagent schreef sjabloonmails; nu LLM-antwoorden — draaide op stale lokale state en de LaunchAgent staat uit*

De koude-mailmachine (`scripts/leadgen_mail.py`) schrijft conceptantwoorden sinds
20-08-2026 met Claude (`_slim_concept`), met de sjablonen als vangnet. Drie dingen
die eronder lagen en niet vanzelf zichtbaar zijn:

- `tick.sh` exporteerde geen SUPABASE_URL/KEY, waardoor de machine terugviel op
  `output/leads/mail_state.json` met 6 leads terwijl er 95 in de database stonden.
  Elk antwoord van iemand buiten die zes werd genegeerd.
- `leadgen_deploy.sh` had een niet-aangehaald pad met een spatie ("Application
  Support") en kopieerde dus niets. Draai hem na elke wijziging en kijk of hij
  "mailmachine bijgewerkt" zegt.
- De LaunchAgent staat UIT (`com.omnivaleur.leadgen.plist` bestond alleen als
  `.uit`). Zolang die niet geladen is doet de machine niets, ook niet met een
  perfecte prompt. Zie "koude-mail-autonoom".

max_tokens moest naar 2000: het model denkt eerst, en op 900 was het budget op
voor er tekst stond — dan viel hij stil terug op het sjabloon.

---

## nl-blogindex-en-vertaalinhaalronde

*19-08-2026 — /nl/blog bestaat sinds 18-08-2026; mislukte NL-vertalingen worden dagelijks ingehaald; www is een APARTE site buiten Railway om*

Sinds 18-08-2026: elke taal heeft een eigen blogindex (`/blog` en `/nl/blog`,
zie `BLOG_INDEX_PATHS` in backend/api/content.py). Kruimelpad, menu en footer
van een artikel wijzen naar de index in dezelfde taal. Vergeet bij een nieuwe
taal niet ook `STATIC_SITEMAP_URLS`.

De NL-vertaling wordt bij publicatie twee keer geprobeerd, en een dagelijkse
inhaalronde om 11:00 NL-tijd (`translate_missing_pages`, 3 per ronde) vult
gaten alsnog. Draai `translate_missing_pages(limit=0)` om alleen te tellen.

**Waarom:** een mislukte vertaling liet vroeger voorgoed een Engels artikel
zonder Nederlandse tegenhanger achter, en de 41 NL-artikelen waren verweesd —
wel in de sitemap, nergens vandaan gelinkt.

**How to apply:** www.omnivaleur.com komt NIET bij de Railway-server binnen —
het is een aparte Cloudflare-site die op élke URL de homepage met status 200
teruggeeft, ook op niet-bestaande paden. Een redirect in FastAPI werkt daar dus
nooit; dat moet een Cloudflare Redirect Rule zijn. Zie ook
"blog-publicatienorm" en "blog-evaluator-and-infographics".

---

## mailbox-eigenaarschap

*18-08-2026 — Claude is volledig verantwoordelijk voor de Zoho-mailbox; Daniel leest alleen concepten. Drie sloten tegen dubbele mail.*

Daniel wil dat ik de mailbox volledig beheer: concepten opstellen, antwoorden
lezen, zijn verzonden mails lezen en daarvan leren, Notion bijhouden. Zijn enige
taak is concepten lezen en versturen. Nooit zelf versturen.

**Why:** hij had geen overzicht meer in de mailbox en miste inhoudelijke reacties
van klanten. Een dubbele mail naar een klant is het ergste wat er kan gebeuren.

**How to apply:**
- Hij gaf expliciet toestemming (18-08-2026) om de HELE verzonden map te lezen
  om toon te leren, inclusief zijn aanpassingen aan mijn concepten.
- Storen mag bij een stapel wachtende concepten (grens 5, 1x per dag), en bij
  afspraken/opzeggingen die ik niet zelf kan oplossen.
- Drie sloten tegen dubbele mail in scripts/leadgen_mail.py:
  1. `_beantwoorde_berichten()` — In-Reply-To/References uit Verzonden én Concept.
     NOOIT op e-mailadres vergelijken: mensen antwoorden vanaf een ander adres.
     Zoho codeert die koppen (=?utf-8?q?...), dus eerst `_leesbaar()`.
  2. `_lijkt_op_recent_verstuurd()` — overlap met wat er 5 dagen terug al uitging.
     Meet OVERLAP, niet gelijkenis: gelijkenis straft lengteverschil af.
  3. `_ruim_concepten_op()` — verstuurde concepten weghalen.
- Toon wordt geteld, niet door een model bedacht: `_toonprofiel()` leest Verzonden.

**De regel die er echt toe doet (18-08-2026, na 9 foute concepten):**
`_wij_spraken_het_laatst()` — heeft Daniel NA hun laatste bericht iets gestuurd,
dan geen concept. Draadkoppen zijn GEEN betrouwbare sleutel: 174 van zijn 217
verstuurde mails hebben helemaal geen In-Reply-To/References omdat hij vanuit de
webmail antwoordt. Verder: per afzender alleen het NIEUWSTE bericht behandelen,
anders krijgt iemand die drie keer schreef drie concepten.

Val bij het controleren nooit terug op de Concept-map als bewijs dat iets al
beantwoord is — een net aangemaakt fout concept 'bewijst' dan zichzelf.

Zie "koude-mail-autonoom" en "rapportage-in-gewone-taal".

---

## admarkt-omschrijving-via-openbaar-mp

*18-08-2026 — Admarkt levert geen prijs/omschrijving, maar de openbare Marktplaats-zoek-API van dezelfde verkoper wel — dat is de bron voor "Fill from Marktplaats"*

Admarkt (zakelijk Marktplaats) geeft alleen titel, foto's en categorie. Prijs en
omschrijving staan er niet in. Ze staan wél op de openbare advertentie:

- `GET /lrp/api/search?sellerIds[]=<id>&limit=100&offset=N` geeft per advertentie
  `priceInfo`, `vipUrl` en een AFGEKAPTE omschrijving.
- De volledige tekst staat server-rendered in de advertentiepagina, in
  `class="Description-module-description"`. Er is geen item-API; alle `/v/api/...`
  varianten geven 404.

Drie valkuilen die gemeten zijn (backend/services/mp_enrich.py):
1. De verkoperslijst stopt hard bij 5.000 advertenties, ook bij 5.534. De rest
   moet per titel worden opgezocht.
2. Admarkt-titels bevatten HTML-codes (`&#39;`), Marktplaats geeft platte tekst.
   Zonder `html.unescape` matcht niets.
3. Marktplaats geeft 403 bij te veel aanvragen achter elkaar. Zonder herkansing
   kwamen 52 van 240 teksten afgekapt binnen. Een afgekapte tekst NOOIT opslaan —
   die belandt middenin een zin op Vinted of eBay.

Koppelen gaat op genormaliseerde titel, binnen één verkoper. Het verkopersnummer
wordt afgeleid door op de eigen titels te zoeken, dus de klant hoeft niets te weten.

Zie "facebook-marketplace-beta" en "marktplaats-category-ids".

---

## rapportage-in-gewone-taal

*17-08-2026 — Rapporteer elke code-/backendwijziging in gewoon Nederlands met vier vaste blokjes plus een zekerheidspercentage*

Na elke wijziging aan code of infrastructuur rapporteren in vier blokjes: wat er
aan de hand was, wat er nu veranderd is (in gevolgen, niet in techniek),
zekerheid in procenten met de reden waarom het geen 100% is, en genummerde
actiepunten voor de gebruiker zelf. Kort en bondig. Vastgelegd in
/Users/Danie/CLAUDE.md zodat het elke sessie geldt.

**Why:** De gebruiker is geen programmeur. Technische uitleg kost hem tijd zonder
dat hij er een beslissing mee kan nemen; hij wil weten wat het voor zijn
gebruikers en zijn omzet betekent en wat hij zelf nog moet doen.

**How to apply:** Geen jargon, geen bestandsnamen tenzij hij er zelf moet kijken,
geen codeblokken tenzij hij iets moet plakken of draaien. Het
zekerheidspercentage eerlijk houden — ongeteste code komt niet boven de 80%.
Zie ook "always-push-to-live".

**In e-mail nooit opmaaktekens** (Daniel, 17-08-2026). Mail gaat als platte
tekst de deur uit, dus `**vet**` komt er letterlijk als sterretjes uit te zien —
midden in een zin naar een klant. Geldt voor alles wat naar buiten gaat: koude
mail, conceptantwoorden, afsluitberichten. Wil je nadruk, gebruik dan een
kopregel op een eigen regel of gewoon de zin zelf. In het gesprek met Daniel in
de terminal mag markdown wél.

---

## koude-mail-autonoom

*17-08-2026 — "De koude-mailmachine draait autonoom via een LaunchAgent; wachtwoorden in de sleutelhanger, wrapper buiten Documenten, alles gelogd in Notion"*

Sinds 11-08-2026 verstuurt `scripts/leadgen_mail.py` zelfstandig koude mail naar
de Marktplaats-leads uit "leadgen-marktplaats-beste-bron", vanaf
daniel@omnivaleur.nl (nooit vanaf omnivaleur.com, zie "railway-blokkeert-smtp").

**Sinds 12-08-2026 draait de machine in de cloud, niet meer op de Mac.** GitHub
Actions (`.github/workflows/leadgen-mail.yml`), elke 30 minuten tussen 08:00 en
21:30 NL-tijd, `concurrency: leadmachine` zodat er nooit twee beurten tegelijk
lopen. Gratis omdat de repo publiek is. `TZ: Europe/Amsterdam` in de workflow is
niet optioneel — zonder dat rekent de runner in UTC en loopt het rooster twee uur
voor. De LaunchAgent op de Mac staat uit (plist hernoemd naar `.uit`); zet die
nooit tegelijk aan, dan mailt hij dubbel want die gebruikt lokale bestanden.

**De repo is PUBLIEK.** Daarom staan de leadlijst en de verzendadministratie in
Supabase, tabel `leadgen_opslag` (naam/inhoud/bijgewerkt, RLS aan, geen policy).
Alleen de **service_role**-sleutel komt erbij; de anon-sleutel uit de frontend
krijgt leesbaar niets (200 met lege lijst) en schrijven geeft 401. Nieuwe leads
gescrapet? Dan `python3 scripts/leadgen_mail.py overzetten` draaien, anders ziet
de cloud ze niet. Zonder SUPABASE_URL/KEY valt het script terug op lokale
bestanden — handig om lokaal te testen.

**De oude Mac-opstelling (uit, maar bewaard als terugval).** LaunchAgent `com.omnivaleur.leadgen` start elke tien minuten
`~/Library/Application Support/omnivaleur/tick.sh`. **Niets wat de machine nodig
heeft staat nog in ~/Documents** — code in `.../omnivaleur/code/`, gegevens in
`.../omnivaleur/leads/`, logboek `tick.log` ernaast. De projectmap blijft de bron;
na elke wijziging aan `leadgen_mail.py` of `leadgen_notion.py` moet je
`scripts/leadgen_deploy.sh` draaien, anders draait de achtergrondtaak de oude code.

**Waarom, en dit is de belangrijkste val.** ~/Documents is bij Daniel zowel
TCC-beschermd als iCloud-gesynct. Een LaunchAgent krijgt er geen toegang
("Operation not permitted", en `brctl download` faalt met NSCocoaErrorDomain 257),
en met "Opslagruimte optimaliseren" haalt iCloud bestanden weg die even niet
gebruikt zijn — een proces dat zo'n bestand leest krijgt dan
`OSError [Errno 11] Resource deadlock avoided`. Beide fouten zijn stil: de mails
gingen gewoon niet meer weg. Van 11-08 14:30 tot 12-08 11:34 stond alles stil
zonder één signaal. Zet nooit een LaunchAgent op iets in ~/Documents.

**Wachtwoorden staan in de sleutelhanger, niet in bestanden:**
`security find-generic-password -a daniel@omnivaleur.nl -s omnivaleur-leadgen-mail -w`
en `-a notion -s omnivaleur-notion-token -w`. Daardoor kan de wrapper gewoon mee
in git.

**`tick` beslist zelf.** Eén keer per dag maakt hij een rooster met willekeurige
tijdstippen tussen 08:45 en 20:30 (minstens 9 minuten uit elkaar) en vinkt die
daarna af; alles staat in `scripts/output/leads/mail_plan.json`, dus een slapende
Mac of een herstart verstuurt niets dubbel. Opbouwschema `RAMP`: 5 op dag 1, 15 vanaf
dag 2, 25 vanaf dag 6, 40 vanaf dag 11 (Daniels wens, 11-08-2026). Hoger heeft
geen zin zolang de lijst ~320 adressen telt. `_dagnummer` telt vandaag als vandaag zodra
er al gemaild is — een eerdere versie zag vandaag als "de volgende dag" en
verstuurde daardoor 6 in plaats van 5 mails op dag 1.

**Kijk voor "draait hij nog?" NOOIT naar de Mac.** Lokale `mail_state.json`,
`tick.log` en de LaunchAgent zijn een dode schaduwkopie en zeggen niets; de
`.uit`-plist is opzet, geen storing. De enige echte bronnen zijn
`gh run list --workflow=leadgen-mail.yml` en de tabel in Supabase — en die tabel
lees je alleen met de service_role-sleutel uit de GitHub-secrets, niet met de
`SUPABASE_KEY` uit de lokale `.env` (ander project, geeft 200 met lege lijst).
Op 14-08-2026 concludeerde ik uit die drie lokale sporen dat de machine stilstond,
terwijl hij gewoon elke 30 minuten mailde.

**Opvolgritme (Daniels wens, 14-08-2026): 2 en 4 dagen**, was 5 en 12.
`STIL_NA_DAGEN = 10`: alles verstuurd en daarna tien dagen stil → Fase
`Doodgelopen` + Afgesloten reden `Geen reactie na follow-ups`.

**De Fase-kolom in Notion IS de werkvoorraad (afgesproken 17-08-2026).** Daniel
verloor het overzicht omdat "heeft geantwoord" niets zegt over wie er aan zet is.
Twee fases toegevoegd, direct achter `4. Gereageerd`: **`⚡ Jij bent aan zet`**
(zij wachten op Daniel) en **`⏳ Bal bij hen`** (wij hebben geantwoord). Samen met
`Gebruikt concurrent`, `Geen interesse`, `Klant` en `Doodgelopen` is dat de hele
levende staat. Status heeft maar 4 opties en is via de API niet uit te breiden
(zie "notion-api-beperkingen"), dus stuur op Fase, niet op Status.

**Reconciliatie postbus ↔ Notion, 17-08-2026.** 18 bedrijven hadden geantwoord;
14 stonden verkeerd in Notion. Drie stonden zelfs op **Interesse** terwijl ze
letterlijk schreven dat ze Channable al gebruiken. De postbus is de waarheid, niet
Notion: mappen `Beantwoord`/`Automatisch`/`Afval` + `Verzonden` samen geven het
hele verhaal per lead. Doe dit opnieuw als de tellingen niet meer kloppen.

**Gevonden lek: een antwoord vanaf een ander adres telde niet.** A. Dinkelaar
kreeg mail op `info@afstandsbediening-online.nl` en antwoordde vanaf
`info@afstandsbediening.nl` — voor de machine een vreemde, dus zijn "nee dank je"
werd genegeerd en de opvolging liep door. `_zelfde_bedrijf()` koppelt nu op de
kern van de domeinnaam (zonder subdomein, extensie en streepjes), **alleen** bij
precies één kandidaat en **alleen** bij namen van 8+ tekens. Twee aangeschreven
collega's bij hetzelfde bedrijf worden bewust niet gekoppeld. Inbox-terugblik van
4 naar 14 dagen.

**Wel geverifieerd:** niemand die antwoordde kreeg daarna nog een sjabloonmail.
Onderscheid machine/handmatig gaat op de tekst, niet op de onderwerpregel — die
is identiek omdat Daniel in dezelfde draad antwoordt.

**Dagbudget 30 (Daniels wens, 15-08-2026), met `NIEUW_AANDEEL = 0.4`.**
Opvolgmails gaan vóór, maar 40% van het budget blijft gereserveerd voor nieuwe
eerste mails. Zonder die reservering drukt een opvolggolf het aanboren van
nieuwe leads volledig weg: op 15-08 waren 12 van de 15 mails opvolging en werd
er die dag vrijwel niemand nieuw aangeschreven.

**Een reactie is een FEIT, interesse is een OORDEEL.** Elk antwoord zet Fase
`4. Gereageerd`; Status `Interesse` wordt alleen nog gezet bij een warm antwoord.
Daarvoor kreeg iedereen die antwoordde Interesse — inclusief "we gebruiken al
Channable". Ook het seintje naar Daniel gaat nu alleen bij een warm antwoord.

**Tussencategorie `Gebruikt concurrent`** (Fase-optie via de API toegevoegd op
15-08-2026, staat direct achter `4. Gereageerd`), met Afgesloten reden
`Gebruikt al een tool`. Dit is geen nee maar een **bezet ja**: die handelaar
crosslist al, ziet de waarde en betaalt er al voor — de kansrijkste lijst die er
is zodra die tool tegenvalt. `CONCURRENT` herkent Channable, Lengow,
ChannelEngine, EffectConnect e.a. plus losse zinnen.

**Val die dit blootlegde:** `AFMELD_WOORDEN` bevatte `geen interesse`, waardoor
"wij gebruiken al Channable, dus geen interesse" als **afmelding** werd geboekt
en het echte nieuws (ze crosslisten al) verdween. Eruit gehaald. Datzelfde
patroon ving `niet meer TE mailen` niet — nu wel. Volgorde in de inbox:
afmelding → concurrent → afwijzing → warm.

**Een nette afwijzing is geen afmelding.** `AFWIJZING` herkent "geen interesse",
"we gebruiken al zo'n tool", "niet wat wij zoeken", "not interested" → Fase
`Geen interesse` + reden `Niet geinteresseerd`, opvolging stopt. Zonder dit
landde een nee in Notion op Status `Interesse`, naast de mensen die wél wilden.
Status blijft bij een nee bewust ongemoeid: er is geen nee-status in de database.

**Daniel mailt ook zelf, buiten de machine om.** `_eigen_mail_meenemen` leest
elke beurt de map Verzonden en neemt elk leadadres dat een niet-`Re:`-mail heeft
gehad over als `met_de_hand`; die krijgen nooit meer een sjabloonmail. Dit vangt
óók het geval waarin de administratie zoek is geraakt terwijl er al gemaild was —
30 adressen zaten in die situatie. Antwoorden op een lopend gesprek (`Re:`) tellen
niet mee, anders zou elk gesprek als "koud benaderd" worden geboekt.

**Een leeggemaakte datum in Notion vraagt `date: null`**, niet `{"start": null}`.
Afgesloten leads horen geen "Volgende actie op" meer te hebben, anders blijven ze
in de takenlijst staan.

**Alles wordt vastgelegd in Notion**, tegen de LIVE kolommen van de Leadlist
(zie "notion-leadlist-kolomnamen"): Fase `2. Benaderd` → `T2. Tekst follow-up 1`
→ `T3. Tekst follow-up 2 (laatste)` → `4. Gereageerd` / `Geen interesse` /
`Doodgelopen`, plus Status, Eerste contact, Volgende actie op en Follow-ups
verstuurd. Daarnaast komt elke gebeurtenis als tekstregel onder aan de leadpagina;
blokken hebben geen kolomnamen en kunnen dus niet stukgaan door een hernoeming.

**Daniel krijgt zelf een seintje** (`_alarm`, naar `ALARM_NAAR`: zijn Gmail en
info@revaleur.com) zodra iemand écht antwoordt — getest en aangekomen op
11-08-2026. Automatische ontvangstbevestigingen tellen niet als antwoord: die
worden herkend aan de onderwerpregel én aan zinnen in de tekst ("bedankt voor je
e-mail", "in goede orde ontvangen"). BoekenBalie stuurde er een terug ónder ons
eigen onderwerp en werd eerst als reactie geteld; dat is gerepareerd. Zou je dit
missen, dan valt zo iemand stil uit de opvolging.

**Opgelost: IMAP stond uit in Zoho** ("You are yet to enable IMAP for your
account"). Let op: het vinkje op organisatieniveau (mailadmin) is NIET genoeg —
IMAP moet ook per postbus aan, in Zoho Mail zelf onder Instellingen →
E-mailaccounts → IMAP. Aangezet op 11-08-2026.

**Onzin-adressen.** Uit webshops komt af en toe iets als `-@mail.nl` mee. Dat is
een gegarandeerde bounce en bounces zijn dodelijk voor een jong domein; `_bruikbaar`
gooit alles met minder dan twee tekens voor de apenstaart eruit. Er is er één
verstuurd voordat dit erin zat.

**Toon van de mails (Daniels beslissing, 11-08-2026):** los en persoonlijk,
"Hi <naam>" en "Groetjes, Daniel". Geen adresblok en geen afmeldregel onder de
mail — hij weet dat dat wettelijk anders hoort en heeft het bewust zo gewild. De
afmeldweg zit alleen nog in de List-Unsubscribe-header.

---

## admarkt-zakelijke-marktplaats

*16-08-2026 — Zakelijke Marktplaats-verkopers beheren hun advertenties in Admarkt; het persoonlijke overzicht is dan leeg en de scan vindt nul*

Een **zakelijk** Marktplaats-account beheert zijn advertenties op
`admarkt.marktplaats.nl/advertisements`, niet op de persoonlijke
"Mijn advertenties"-pagina die de scan leest. Die pagina is dan gewoon leeg.
Gemeten bij Egbert Brouwer (Papa's Plectrums, plectrums/muziekmerchandise):
**5.540 advertenties in Admarkt tegenover 0 in het gewone overzicht.**

De Admarkt-lijst toont per rij: miniatuur, titel, datum, CPC, biedstrategie,
pagina, budget, kliks, klikratio — **geen prijs en geen omschrijving**. Die
moeten dus alsnog van de advertentiepagina zelf komen, net als bij de gewone
import.

**Twee wegen, en de dure is niet nodig gebleken.**
1. *Officieel:* de iCAS Sellside-API (`admarkt.marktplaats.nl/api/sellside/`,
   OAuth2 authorization code, kan ook namens andere verkopers werken). Klinkt
   perfect, maar: "To request a client id and secret please ask your contact at
   the respective tenant." Er is geen aanmeldknop — Marktplaats moet je die
   sleutels persoonlijk geven. Dat is een zakelijke horde, geen technische.
2. *Wat gebouwd is (extensie 1.0.201):* de pagina in een tabblad laden en lezen
   wat hij zelf ophaalt.

**Gemeten op Daniels eigen (lege) Admarkt-account, 16-08-2026** — hij heeft
Marktplaats Pro zonder advertenties, en dat is genoeg om de pagina te bestuderen:
- De site is een React-SPA met een **catch-all**: élk onbekend pad geeft
  **HTTP 200 met de gewone pagina** terug in plaats van 404. Raden naar een
  endpoint "lukt" dus altijd en levert nooit iets op. De controle op
  `content-type: json` is daarom geen nettigheid maar de énige manier om te zien
  dat er niets is. `/api/v2/{advertisements,listings,ads,campaigns,account}` gaven
  allemaal 200 text/html.
- De pagina haalt **`/csrf-token`** op → de advertentielijst kan een POST zijn,
  en die valt met een eigen GET nooit na te doen.
- Met 0 advertenties doet de pagina **geen enkel** gegevensverzoek voor de lijst.
  Een leeg account kan de aanpak dus niet bewijzen, alleen ontkrachten.
- Het datamodel is **campagne → listing** (`/campaign/{id}/listing/edit/{id}`);
  "Alle advertenties" is een samenvoeging.

**DE KOPPELING (gevonden en uitgeprobeerd op een live advertentie, 16-08-2026).**
Admarkt praat **tRPC**: `GET /api/trpc/<procedure>?batch=1&input=<urlencoded json>`
met `{"0": {…}}` als invoer, op de sessiecookie van de ingelogde verkoper.
- `campaign.getAllCampaigns` → `{campaigns:[{id,title,status,…}], total}`.
  Iedereen heeft er minstens één ("Campagne zonder titel").
- `ad.getAds` met `{campaignId, pageToken?}` → `{ads, count, nextPageToken}`.
- Advertentievelden: `id, title, images[], categoryId, status, dateCreated,
  campaignId, links`. Foto's zitten in `images[].links` op meerdere maten,
  **1024x1024** is de grootste; protocol-relatief, dus `https:` ervoor.
- **Hoe je hier zoekt:** een onbekend PAD geeft 200 + de gewone pagina (nutteloos),
  maar een onbekende PROCEDURE geeft netjes **404**. Dat is de oracle waarmee
  `ad.getAds` gevonden is. De API noemt bovendien zelf de geldige veldnamen in
  zijn foutmelding (zo bleek de dimensie `am:adID` te heten, niet `am:adId`).

**Admarkt kent GEEN prijs en GEEN omschrijving.** Het zijn advertenties die naar
de **eigen webwinkel** van de verkoper wijzen (`links.url`), niet naar een
Marktplaats-advertentie. Een import levert dus titel + foto's + categorie op; de
verkoper vult prijs en tekst zelf aan. Sla bewust **geen** `platform_listing_url`
op — dat adres is de webwinkel en zou later de verkeerde pagina openen of
verwijderen. Er valt om dezelfde reden ook niets te verrijken.

**De meekijker (1.0.205) staat er nog als vangnet.**
`content/admarkt_sniffer.js` draait op `document_start` in de **MAIN world**,
aangemeld via `chrome.scripting.registerContentScripts` zodra de toestemming er
is (executeScript is altijd te laat — dan heeft de app haar gegevens al binnen).
Hij haakt `fetch` en `XMLHttpRequest` en bewaart json-antwoorden op
`window.__omnivaleurVangst`. Methode, adres, sleutels en cookies kloppen dan per
definitie. **Antwoorden worden geKLOOND, nooit uitgelezen** — lees je het
origineel, dan is de body op voor de pagina zelf en breekt de site onder de
gebruiker. Locales, csrf-token en html worden genegeerd.

**Het API-adres wordt niet geraden maar waargenomen.** Ik heb geen zakelijk
account en kan die pagina niet zien; een geraden endpoint was een gok geweest.
`bgScanAdmarkt` leest daarom na het laden `performance.getEntriesByType("resource")`
uit, haalt de data-verzoeken die de pagina zelf deed nog eens op met
`credentials: "include"`, en zoekt in die antwoorden een array van objecten met
een id- en een titel-veld. Wat gewerkt heeft komt terug in `meta.bron` en
`meta.velden`, zodat het daarna hard vastgelegd kan worden. Mislukt het, dan
meldt de fout wélke adressen zijn geprobeerd en wat ze gaven.

**`optional_host_permissions`, nooit `host_permissions`.** Een update die een
nieuwe vaste host-toestemming toevoegt zet Chrome bij **iedere** gebruiker de
extensie stil tot hij hem accepteert. De schakelaar "Business account (Admarkt)"
in de popup levert bovendien de gebruikersklik die `permissions.request` eist —
vanuit een achtergrondscan kun je die toestemming niet vragen.

**Vraag nooit een toestemming vanuit het uitklapvenster van de extensie.**
Chrome sluit dat venster op het moment dat hij de vraag toont; de code die op
het antwoord wacht verdwijnt mee en bij heropenen staat de schakelaar
onveranderd uit. Voor de gebruiker lijkt de schakelaar dan klem te zitten — dat
gebeurde in 1.0.201. De oplossing in 1.0.202: dezelfde `popup.html` openen in een
tabblad (`?tab=1`) en `permissions.request` daar doen. **Gemeten werkend op
15-08-2026:** tabblad opent, Chrome stelt de vraag, schakelaar blijft aan staan.

**`calmModeToggle` in popup.html is een dode schakelaar** — hij schuift (pure
CSS) maar er is geen enkele code die hem uitleest of opslaat; "calmMode" komt
nergens voor in background.js. Calm mode heeft dus nooit gewerkt. Daniel weet
het sinds 15-08-2026 en heeft het bewust geparkeerd.

**BEWEZEN OP EEN ECHT ZAKELIJK ACCOUNT, 16-08-2026.** Egbert Brouwer (Papa's
Plectrums, 5.540 advertenties) meldde "Ok nu is het gelukt" met extensie 1.0.206.
Daarmee is de hele keten rond: schakelaar → toestemming → tRPC → import.
De weg ernaartoe kostte vijf versies (1.0.201 t/m 1.0.206); wat elke ronde
kostte was steeds hetzelfde soort fout — een aanname die stil faalde in plaats
van te klagen.

**Oudere aantekening, inmiddels achterhaald: de scan was ongetest op 15-08-2026** — alleen de toestemming
is bewezen. Zie "extension-release-bump-version" en
"marktplaats-category-ids".

---

## omnivaleur-r2-fotoopslag

*16-08-2026 — "Advertentiefoto's verhuizen van Supabase Storage naar Cloudflare R2 op img.omnivaleur.com; lege R2-instellingen = automatisch terug naar Supabase, dat is de terugweg"*

Sinds 16-08-2026 is Cloudflare R2 de bestemming voor advertentiefoto's
(bucket `omnivaleur-photos`, publiek via `img.omnivaleur.com`). Reden: Supabase
gaf 1 GB en rekende ook dataverkeer; R2 geeft 10 GB en verkeer is gratis. Zie
"supabase-gratis-plan-egress".

Hoe het in elkaar zit:

* `backend/services/r2_storage.py` is de enige plek die met R2 praat (boto3,
  S3-protocol). **Zijn de vijf `r2_*`-instellingen leeg, dan valt alles vanzelf
  terug op Supabase Storage** — precies zoals het daarvoor werkte. Dat is de
  terugweg zonder deploy, en ook wat er in tests gebeurt.
* `locate_object()` in `image_upload.py` bepaalt per url op welke opslag een
  foto staat. Tijdens de migratie staan beide soorten urls door elkaar.
* De bucket heeft een CORS-regel nodig (`ensure_cors()`), anders kan de extensie
  de foto niet ophalen vanaf een marktplaatspagina en publiceert een item zónder
  beeld. Dat is exact de storing waarvoor het spiegelen ooit gebouwd is.
* Nooit het `r2.dev`-adres gebruiken: Cloudflare knijpt dat af en verbiedt het
  in productie.
* `scripts/migrate_photos_to_r2.py` verhuist en verkleint in één beweging.
  Droogloop tenzij `--apply`, met `--budget-mb` omdat terúglezen uit Supabase
  nog wél egress kost (2,55 GB in totaal). Doet eerst een ketentest
  (upload → publiek ophalen → verwijderen) en stopt als die faalt.

Op 16-08-2026 afgerond: alle 3525 foto's staan op R2 (1,48 GB van 10 GB), nul
mislukt, alle 3525 daarna één voor één opgevraagd en bereikbaar. De Supabase-
bucket ging van 3,71 GB naar 0,67 GB.

Eén ding dat bijna misging: **publicatieopdrachten (`jobs.payload`) dragen hun
eigen kopie van de foto-urls mee.** Ruim je de oude bestanden op zonder daarop te
letten, dan publiceren openstaande opdrachten een advertentie zónder foto's.
`cleanup_orphan_photos.py` telt jobs die niet `done`/`cancelled` zijn nu mee als
verwijzing (errored jobs ook — die worden opnieuw geprobeerd).

**Why:** dit was de enige uitweg die zowel de opslag- als de verkeersgrens
wegneemt zonder een betaald abonnement, en zonder de database te verhuizen (die
zat maar op 9%).

**How to apply:** R2-sleutels horen zowel in de lokale `.env` als in de
Railway-variabelen — anders schrijven nieuwe imports op de server nog steeds
naar Supabase. Na de migratie de oude bestanden opruimen met
`scripts/cleanup_orphan_photos.py --apply --include-root`.

---

## calm-mode

*16-08-2026 — Calm mode was jarenlang een dode schakelaar; sinds extensie 1.0.207 vertraagt hij publicaties naar 3-8 min en de verkocht-controle naar 1x per uur*

**Tot 1.0.207 was `calmModeToggle` een dode schakelaar.** Hij schoof heen en weer
(pure CSS), maar er was geen enkele regel die hem uitlas of opsloeg — "calmMode"
kwam nergens voor in background.js. Wie dacht rustiger te publiceren deed dat
niet. Ontdekt op 15-08-2026 bij het bouwen van de Admarkt-schakelaar ernaast.

**Wat hij nu doet** (gebouwd 16-08-2026, op verzoek van Daniel omdat het
verkoopargument werd in koude mail — zie "koude-mail-autonoom"):
- publicaties **3 tot 8 minuten uit elkaar**, willekeurig gekozen — een váste
  tussenpoos is zelf ook een patroon;
- verkocht-controle van elke 10 minuten naar **1x per uur**.

**Waarom dit het juiste argument is tegen "ik word geblokt".** Wat een
geautomatiseerd account verraadt is ritme, niet aantal. Twintig advertenties in
twee minuten zien er anders uit dan twintig over een middag, met hetzelfde
eindresultaat. Handelaar Otte (2.750 advertenties) bracht dit bezwaar op
16-08-2026; het is de meest voorspelbare vraag van elke serieuze handelaar.
Beloof nooit veiligheid — het dashboard zegt zelf dat het op eigen risico is.

**Drie valkuilen die in de bouw zaten:**
1. De wachttijd staat in `storage.local`, **niet in het geheugen**. Chrome maakt
   een MV3 service worker dood zodra hij niets doet; in het geheugen zou de rem
   elke keer opnieuw op nul beginnen.
2. Het alarm van de verkocht-controle moet **opnieuw gezet** worden zodra de
   schakelaar omgaat (`chrome.storage.onChanged`) — een bestaand alarm verandert
   niet vanzelf van tempo.
3. **Alleen schrijvende opdrachten** worden geremd (`create`, `delete`,
   `content_refresh`). Een scan leest alleen en is onzichtbaar voor het platform;
   die tegenhouden laat de gebruiker wachten zonder iets veiliger te maken.

Geremde opdrachten blijven gewoon `pending` staan en zijn in het dashboard als
wachtrij zichtbaar; er gaat niets verloren.

---

## notion-techstack-pagina

*16-08-2026 — "Notion-pagina 'Techstack Omnivaleur' is Daniels vaste overzicht van alle gebruikte diensten — bijwerken bij elke toevoeging, vervanging of verwijdering van een dienst"*

**Techstack Omnivaleur** — https://app.notion.com/p/3beb0954fb728120a7c6e6509b47ccba
(losse pagina bovenaan zijn werkruimte, aangemaakt 16-08-2026)

Eén tabel-overzicht van alles wat Omnivaleur draaiend houdt, gegroepeerd in:
fundament, verkoopkanalen, chrome-extensie, geld & klantcontact, AI & content,
groei & werkproces, techniek onder de motorkap, en een sectie "staat nog in de
kast" voor ongebruikte diensten (nu: Cloudinary).

**Why:** Daniel is geen programmeur en wil één plek waar hij ziet wat er draait
en waar de valkuilen zitten, zonder in de code te hoeven kijken.

**How to apply:** werk deze pagina bij zodra we een dienst toevoegen, vervangen,
opzeggen of een belangrijke valkuil ontdekken — ongevraagd, als onderdeel van de
wijziging zelf. Kolommen zijn dienst / waarvoor / belangrijk om te weten, in
gewone taal en in gevolgen, niet in techniek (zie "rapportage-in-gewone-taal").
Ook de datumregel bovenaan meenemen. Zie "omnivaleur-r2-fotoopslag".

---

## marktplaats-publiceren-valkuilen

*13-08-2026 — "Drie fouten in de MP/2dehands-publicatie die pas bij de eerste muziektest boven water kwamen: prijsformaat, Bestemd voor, en de dode /v/listing-link"*

Gevonden op 13-08-2026 bij het end-to-end testen van de muziekcategorieën
("omnivaleur-niet-kledingcategorieen"). Geen van de drie was muziekspecifiek —
ze zaten er al voor iedereen in.

**1. Prijs met één decimaal wordt geweigerd.** Marktplaats/2dehands antwoorden
met "Ongeldige prijs." op `9,5` en `25,0`. Wél goed: `9,50`, `25`, `25,00`,
`29,99`. Wij stuurden letterlijk `String(9.5)` → `"9,5"`, dus elk item op een
halve euro ging nooit online. Bij kleding viel dat niet op omdat die bijna altijd
op ,99 eindigt. Nu altijd `toFixed(2)` (`mpPrijs` in shared.js).

**2. "Bestemd voor" betekent per categorie iets anders.** Bij kinderkleding is
het jongen/meisje, bij muziek is het WELK INSTRUMENT (28 opties, van Accordeon
tot Overige instrumenten). Blind "Jongen of Meisje" invullen liet het veld leeg
en dan weigert `verifyMpGroupFields` terecht te plaatsen. `selectIntendedFor`
leest nu eerst de opties die er écht staan.

**3. `/v/listing/{id}` bestaat niet.** Die vorm geeft ALTIJD 404, ook voor een
advertentie die gewoon online staat — en wij sloegen hem na elke publicatie op.
Drie gevolgen: de verwijderklus opende een 404-pagina en vond geen knop; de
controle "staat hij nog online?" las die 404 als bewijs van afwezigheid en
meldde een lévende advertentie als verwijderd; en de link in het dashboard was
dood. Gebruik `https://www.marktplaats.nl/seller/view/{id}` (geverifieerd 200,
mét de Verwijder-knop), of de pagina waar je na het plaatsen echt op landt.
79 opgeslagen links zijn achteraf gerepareerd.

Regel die daaruit volgt: **"waarschijnlijk weg" mag nooit als succes gemeld
worden.** Een verkoper die denkt dat zijn advertentie eraf staat terwijl hij nog
te koop staat, is de slechtste van de drie uitkomsten.

**Verwijderen met de hand** (voor als het ooit weer nodig is): open
`/seller/view/{id}`, klik Verwijder, en kies daarna "Niet verkocht via
Marktplaats" of "Verkocht via Marktplaats" — er is altijd een tweede stap.

---

## leadgen-doelgroep-kleding

*13-08-2026 — De koude-mail doelgroep moet gefilterd worden op tweedehands kleding/sieraden/accessoires; bol.com-wederverkopers moeten eruit*

Vastgesteld op 13-08-2026, te doen bij de **volgende Marktplaats-leadscrape**
(zie "leadgen-marktplaats-beste-bron" en "koude-mail-autonoom"):

De huidige lijst zit vol met bol.com-wederverkopers, dropshippers en handelaren
in nieuwe spullen. Die kopen niets: Omnivaleur is gebouwd voor tweedehands.

**Primaire doelgroep om op te filteren:**
- tweedehands **kleding**, **sieraden** en **accessoires**
- verkopers die **al op meerdere marketplaces** actief zijn (dat is het signaal
  dat crosslisten hun echte pijn is)

Waarom dit hard is en niet "nice to have": de categorie-indeling van de app is
volledig op tweedehands kleding gebouwd — zie
"omnivaleur-niet-kledingcategorieen". Een lead buiten die niche kan zijn
advertenties wel importeren, maar niet terugplaatsen op Marktplaats/2dehands in
de juiste categorie. Dat komt in maand één uit, niet in maand drie.

---

## import-dubbele-items-over-platforms

*13-08-2026 — Importeren vanaf meerdere kanalen kan hetzelfde voorwerp dubbel opleveren; de dedup mag daarom nooit automatisch samenvoegen*

Sinds 13-08-2026 staat de import voor Marktplaats en 2dehands aan (was
"Coming soon" via één vlag in `IMPORT_SCANNABLE` in frontend/app.html; de scan
zelf, `bgScanMp2dh` in extension/background.js, bestond al sinds juli).

Het gevaar zat niet in de scan maar in de dubbele voorraad: dezelfde trui staat
in het Nederlands op Marktplaats en in het Engels op Vinted. De exacte
titelmatch ziet dat niet, dus zonder ingreep krijgt de verkoper het voorwerp
twee keer — en crosslist hij dan één kopie, dan komt er een echte dubbele
advertentie op een kanaal waar het al te koop staat.

De keuze die daarbij is gemaakt, en die overeind moet blijven:

- **Nooit automatisch samenvoegen.** Twee verschillende voorwerpen samenvoegen
  is veel moeilijker terug te draaien dan een dubbele regel. De verkoper
  bevestigt altijd zelf; het voorstel staat wél bovenaan de keuzelijst.
- De tweelingdetectie (`_find_twins` in backend/api/imports.py) vergelijkt
  alleen tegen items die al op een **ánder** kanaal staan, met een
  prijs-plausibiliteitsgrens; bij twijfel geeft hij niets terug.
- Bulk-import verwerkt **één kanaal per ronde**, anders zouden twee gelijktijdig
  gescande kanalen elkaar niet kunnen zien.
- Geparkeerde regels blijven `pending`; de frontend loopt er met een `offset`
  langs, anders draait de import eeuwig op dezelfde rijen.

**Het taalmodel alleen is hier niet betrouwbaar.** Op Daniels echte voorraad
(384 items, 118 MP-advertenties) koppelde Haiku grijs aan blauw, Profuomo aan
Suitsupply en een maat M aan een XL: 14 "dubbelen" waarvan er 12 fout waren. Er
staan nu harde regels onder (`_twin_plausible`) op kleur, maat, merk en prijs,
in het Nederlands én Engels — die kan het model niet omzeilen. Daarna: 2
voorstellen, beide juist. Wie hier iets aan verandert, moet opnieuw tegen echte
data draaien; een testje met verzonnen titels laat dit soort fouten niet zien.

Twee valkuilen die al een keer zijn gemaakt:
- De poel van mogelijke tweelingen moet **per kanaal** berekend worden. Op de
  vereniging van alle kandidaat-kanalen valt elk item af en staat de detectie
  stilletjes uit.
- Marktplaats levert protocol-relatieve fotolinks ("//images.marktplaats.com/…").
  Die als pad behandelen gaf 404's en dus lege foto's; `_fix_photo_url` in
  backend/api/jobs.py repareert ze ook achteraf.

Taal is géén probleem: `localize_item_for_platform` in
backend/services/crosslist.py vertaalt bij publicatie automatisch naar de taal
van het doelkanaal.

---

## blog-publicatienorm

*13-08-2026 — De blognorm staat als code in backend/content/quality.py en wordt bij elke publicatie getoetst; verhoog daar de lat als het niveau omhoog moet*

Het blogformat is sinds 2026-07-31 vastgelegd in `backend/content/quality.py`:
minimaal 1200 woorden, 5 H2-secties, 4 interne links, 2 externe bronnen, 2
afbeeldingen, een hero/og:image, een quick answer van 35-75 woorden, 3
takeaways, 4 FAQ-vragen, titel ≤60 en meta ≤160 tekens, plus controles op
markdown-restanten en merknaam-als-werkwoord.

- De pijplijn toetst elk nieuw én herschreven artikel eraan — ná het opslaan,
  want hero en interne links worden pas in `_save_page_row` toegevoegd.
- `scripts/check_blog_quality.py` toetst de hele site en draait mee in de
  dagelijkse GitHub Action, zodat een terugval binnen een dag zichtbaar is.
- Bewust waarschuwingen, geen blokkade: een artikel dat op één punt zakt is
  beter dan geen artikel, en een blokkade zou de cron stil laten vallen.

**Why:** een norm die alleen in een prompt staat, zakt weg zodra het model iets
anders doet. In code is hij meetbaar, en meetbaar betekent dat je kunt zien of
het beter of slechter wordt.

**How to apply:** wil je het niveau omhoog, verhoog dan een drempel in
`quality.py` of voeg een check toe — dat geldt automatisch voor nieuwe én
bestaande artikelen. Draai daarna `scripts/check_blog_quality.py` om te zien
wie er onder valt, en `scripts/backfill_blog_upgrade.py` voor alles wat zonder
hergeneratie op te lossen is. Stand op 31-07-2026: 22/50 haalden de volle norm;
het restant zakt vrijwel altijd op lengte (~1100 i.p.v. 1200+ woorden).
Zie ook "blog-beeldsysteem-valkuilen" en "blog-evaluator-and-infographics".

**Afgekapte artikelen (13-08-2026).** Het model kreeg 8.000 tokens en liep daar bij
lange artikelen tegenaan; wat er stond werd gepubliceerd. Vijf van de 75 pagina's
eindigden middenin een zin en één FAQ-antwoord was het woord "It". De norm keek
naar lengte en links, niet naar of de tekst áf was. Nu drie sloten: de generator
stopt bij `stop_reason == "max_tokens"` (`_afgekapt` in generator.py, limiet naar
16.000), `check_article` meldt het met het voorvoegsel `AFGEKAPT:` (body sluit niet
op een dichtgezet blok, ongelijk aantal `<p>`, FAQ-antwoord < 40 tekens, takeaway
< 25 tekens), en `pipeline._afgekapt` weigert publicatie — als enige normpunt
blokkerend, de rest blijft waarschuwing. Herstellen van bestaande pagina's kan met
`scripts/blog_repair_afgekapt.py --repareer`: die knipt de halve zin weg en laat
het slot opnieuw schrijven, in plaats van het hele artikel opnieuw te genereren
(dan verlies je de afbeeldingen en interne links).

**Nederlandse content tutoyeert altijd (Daniel, 13-08-2026): "je", nooit "u".** Via
de NL-vertaling was "u" op zes van de 37 pagina's binnengeslopen. De vertaalprompt
in generator.py verbiedt het nu expliciet, `check_article` meldt het bij
`language == "nl"`, en `scripts/blog_repair_afgekapt.py --u-vorm --repareer` zet
bestaande pagina's om. Let op bij dat omzetten: doe het per alinea met
string-splicing en controleer daarna het aantal `<img>`, `<a>` en `<p>` — een hele
body in één keer door het model halen liep tegen de tokenlimiet aan én sleepte
opmaak mee. Tekst in infographics zit niet in `<p>`/`<li>` en wordt door de
alinea-aanpak gemist; die moet je apart nalopen.

**Vertalen gaat op Sonnet, niet op Haiku (13-08-2026).** Haiku leverde in
gepubliceerde NL-artikelen "lesenswaardig" (Duits), "hoger-eindige" en onvertaald
"throttled" op. `TRANSLATE_MODEL` staat nu op `claude-sonnet-5`. Alle Claude-calls
in generator.py lopen via `_vraag()` en **streamen**: de SDK weigert een
niet-streamende call die lang kan duren, en dat is precies de NL-vertaling van een
lang artikel (die moet het hele artikel opnieuw uitschrijven, en Nederlands is
langer dan Engels). `MAX_TOKENS` staat op 24.000.

**Infographics breken tekst af, ze kappen niet meer af (13-08-2026).** SVG kent
geen tekstterugloop, dus lange labels werden geknipt met "…" — 108 regels over 33
pagina's. `_wrap()` + `_regels()` in infographics.py verdelen de tekst over
meerdere `<tspan>`-regels en laten de rijhoogte meegroeien; past het echt niet
(stappen >3 regels, labels >3 regels), dan wordt de infographic niet getekend in
plaats van verminkt. Bestaande pagina's opnieuw tekenen:
`scripts/blog_repair_afgekapt.py --infographics --repareer` — die strippt de oude
`<figure class="infographic">`-blokken en laat ze opnieuw genereren.

---

## omnivaleur-demovideo-en-prijs

*13-08-2026 — "De demovideo (YouTube Short) en de prijs die Daniel in de outreach noemt — €19,99 per maand voor alle marketplaces"*

Wat Daniel in gesprekken met leads uit "koude-mail-autonoom" noemt, vastgesteld
op 13-08-2026:

- **Demovideo:** https://youtube.com/shorts/ymDeS37aBW4 (2 minuten, verborgen op
  YouTube — de link werkt voor iedereen, maar hij is niet te vinden via zoeken).
  Stuur altijd de link, nooit het mp4-bestand: 25 MB is de bijlagegrens bij Zoho
  en Gmail, en een videobijlage van een onbekende afzender verhoogt de kans op
  spam flink.
- **Prijs:** €19,99 per maand, alle marketplaces inbegrepen. Eerste 7 dagen
  gratis, daarna maandelijks opzegbaar (zie "proefperiode-en-toegangsslot").
- **Ondersteunde kanalen:** Marktplaats, 2dehands, Vinted, eBay en Shopify.
  Facebook Marketplace is beta en noem je niet uit jezelf, zie
  "facebook-marketplace-beta".

Gebruik deze drie ook in antwoorden op leads die om "de prijzen" of "welke
marketplaces" vragen — dat waren de eerste twee vragen die binnenkwamen.

---

## railway-blokkeert-smtp

*11-08-2026 — Railway laat geen uitgaand SMTP toe; alle mail loopt via de Resend HTTP-API met afzender Omnivaleur en Reply-To revaleur*

Railway blokkeert uitgaand SMTP-verkeer: poort 465 en 587 lopen dood in een
time-out (en over IPv6 in "Network is unreachable"). Mail kan het platform
alleen verlaten over https. Sinds 04-08-2026 gaat alle mail daarom via de
Resend HTTP-API (`RESEND_API_KEY`, `RESEND_FROM`) in `backend/services/email.py`;
de SMTP-weg staat er nog als terugval maar werkt op Railway niet.

Vaste afspraak over adressen: **uitgaand** heet alles Omnivaleur
(`info@omnivaleur.com`, domein geverifieerd bij Resend), **antwoorden** komen
binnen op `info@revaleur.com` — via Reply-To en het adres in de mailtekst
(`REPLY_TO_EMAIL`). Niet door elkaar halen: revaleur.com is de postbus die
Daniel echt leest, omnivaleur.com is het merk.

**Nooit koude outreach via Resend.** Resend verbiedt in zijn acceptable use policy uitdrukkelijk ongevraagde mail, koude acquisitie en gescrapete adreslijsten, en sluit accounts zonder waarschuwing bij een klachtpercentage boven 0,08%. Het Resend-account stuurt óók de wachtwoord- en factuurmails van de app; een schorsing legt dus het product plat. De leadgen-mailings uit "leadgen-marktplaats-beste-bron" moeten daarom over een apart domein **en** een aparte aanbieder die voor koude mail bedoeld is.

**Why:** uren kwijtgeraakt aan het debuggen van "verkeerde SMTP-instellingen"
terwijl de instellingen klopten en het platform de poort dichthield.

**How to apply:** bij een mailprobleem op Railway eerst Resend controleren, niet
SMTP-gegevens. Nieuwe mailfuncties altijd via `send_email` / `send_email_checked`.

Zie ook "deploy-pipeline" en "proefperiode-en-toegangsslot".

---

## leadgen-marktplaats-beste-bron

*10-08-2026 — "Marktplaats is gemeten de verreweg beste leadbron — de zoek-API markeert zakelijke verkopers gratis en het smb-profile geeft KvK, telefoon en vaak e-mail"*

Live gemeten op 2026-08-10, niet aangenomen. Vergelijking van leadbronnen voor Omnivaleur:

| bron | opbrengst |
|---|---|
| Instagram | 411 handles over meerdere runs → 194 profielen → 15 leads → **0 e-mailadressen** |
| Marktplaats | ~4 minuten scrapen → 263.000 advertenties → 88.000 verkopers → 978 zakelijke verkopers → ~360 met direct e-mailadres |
| eBay.nl | 82.000 NL-kledingadvertenties, maar particuliere verkopers tonen geen contactgegevens; pool veel kleiner dan MP |

**De techniek die het werkt maakt:**
- Interne zoek-API: `https://www.marktplaats.nl/lrp/api/search?l1CategoryId={id}&l2CategoryId={id}&limit=100&offset={n}`. Geeft JSON, 100 advertenties per call, ~1.360 advertenties/seconde met 8 threads. Paging is gecapt op **50 pagina's (5.000 advertenties) per categorie** — daarom moet je per subcategorie sweepen, niet per hoofdcategorie.
- Elke advertentie draagt `sellerInformation` met `sellerId`, `sellerName`, `showWebsiteUrl` en `isVerified`. Die laatste twee zijn een **gratis zakelijk-filter**: mét vlag is 72% echt zakelijk, zonder vlag 3%. Dat is een filter van 25x en het kost geen enkele extra request.
- `https://www.marktplaats.nl/smb-profile/profile/{sellerId}` geeft van zakelijke verkopers: KvK-nummer (100%), telefoon (94%), **e-mailadres (37%)**, BTW-nummer (50%), handelsnaam en adres. Particulieren hebben geen smb-profile — het bestaan ervan ís de zakelijk-toets.
- HTML-pagina's (`/l/{slug}/p/{n}/`) werken ook en bevatten dezelfde data in `__NEXT_DATA__`, maar geven 35 advertenties per request in plaats van 100. Gebruik de API.
- Categorie-ID's staan als `searchCategory` in de HTML van `/l/{slug}/`. **Niet gokken** — 1032 is Huizen en Kamers, niet kleding. Kleding dames = 621, heren = 1776, games = 356, sieraden/tassen = 1826, audio-tv-foto = 31.

De vijver is niet uitgeput: een tweede sweep over 132 subcategorieën leverde 451 nieuwe zakelijke verkopers op 497 gevonden — 90% nieuw. Zie "leadgen-vier-bronnen" voor de Instagram-pijplijn en "instagram-leadgen-bronnen".

**Ondergrens van 20 advertenties (Daniel, 2026-08-10).** `classify --min-ads` staat standaard op 20. Onder die grens is crosslisten geen probleem — met vijf advertenties zet je ze desnoods met de hand over — en op 3 kwamen er buurtwinkels en eenmansacties binnen die niets aan de tool hebben. Van 464 leads bleven er 381 over, waarvan 324 met e-mailadres; mediaan 200 advertenties per lead. Verlaag dit alleen als de lijst opdroogt.

**Crosslisten aantoonbaar maken (`crosslist`-stap, gemeten over 792 verkopers).** 61% verkoopt al op meer dan één kanaal. Wat wél te meten valt: de eigen webshop (uit de doorklik-link van Marktplaats of anders uit het e-maildomein), het webshopsysteem (WooCommerce 154, Shopify 48, Magento 34, Lightspeed 33, CCVshop 25) en bol.com (zoeken op handelsnaam, alleen een exacte match in "Verkoop door ..." telt — bol geeft ook bij onzin altijd verkopers terug; 37 treffers). Wat **niet** te meten valt: eBay (winkeladressen zijn niet uit een handelsnaam af te leiden, 40 pogingen gaven 40 lege pagina's), Vinted (Cloudflare) en 2dehands (zelfde techniek, eigen verkoper-nummers — hetzelfde nummer geeft daar nul advertenties). Facebook- en Instagram-links op de site zijn bewust niet meegeteld: bijna iedereen heeft die.

**Waarschuwing bij uitvoering:** de gemarkeerde verkopers bevatten ook niet-doelgroep (Catawiki, verhuurbedrijven, retailers van nieuwe spullen) — de bestaande Haiku-classificatie is nodig. En koude mail nooit vanaf omnivaleur.nl: dat domein stuurt de transactionele mail via Resend, zie "railway-blokkeert-smtp".

---

## notion-leadlist-kolomnamen

*10-08-2026 — Notion weigert een hele pagina bij één onbekende kolomnaam — de leadgen-push was daardoor stilletjes stuk na een hernoeming*

De Notion-API weigert een **volledige** pagina zodra er één kolomnaam in de payload staat die niet in de database bestaat. Een hernoemde kolom betekent dus niet "dat ene veld blijft leeg" maar "er komt helemaal niets binnen" — en `push_leads` vangt die fout per lead af, dus het faalt zonder alarm.

Dat is precies gebeurd: `scripts/leadgen_notion.py` schreef naar `Notes (Optional)`, `Verkoopt vooral...` en `Verkoop op...`, terwijl de Leadlist die kolommen inmiddels `Notities`, `Verkoopt` (multi_select) en `Verkoopt op` (multi_select) noemt. Hersteld op 2026-08-10.

**Controleer na elke wijziging in de Leadlist** of de kolomnamen nog kloppen — offline te doen, zonder één rij te schrijven: bouw `_properties(lead)` voor een lead en trek de sleutels af van de `properties` uit `GET /databases/{id}`. Wat overblijft zijn de kolommen die de push zullen laten mislukken.

Let ook op het type: `Verkoopt` en `Verkoopt op` zijn **multi_select**, geen select. Onbekende waarden worden bewust weggelaten in plaats van aangemaakt, anders groeit de kolom vol met varianten ("Vinted en eigen website" is één modelantwoord maar twee opties).

Zie "leadgen-marktplaats-beste-bron" en "leadgen-vier-bronnen".

---

## leadgen-vier-bronnen

*10-08-2026 — "Architectuur van de Instagram-leadgen — vier bronnen achter één uitvoervorm, met discover/enrich gesplitst om Apify's gratis-limiet te omzeilen"*

`scripts/leadgen_sources.py` bevat vier discovery-bronnen (`dork`, `hashtag`, `keyword`, `local`) die allemaal dezelfde recordvorm teruggeven, zodat `scripts/leadgen_instagram.py` de bron niet hoeft te kennen. De pijplijn is `discover → enrich → classify → push`.

**Waarom die splitsing bestaat:** Apify's gratis-plan knijpt de *keyword-discovery*-actor af tot 5 kandidaten per run. De profiel-actor heeft dat plafond niet. Door discovery (alleen handles) los te trekken van verrijking (bio/volgers/website) loopt de dure limiet alleen nog over de goedkope stap. Zie "instagram-leadgen-bronnen" voor de gemeten opbrengst per bron.

`python3 scripts/leadgen_instagram.py bench` draait alle vier apart en meet **leads na classificatie**, niet ruwe handles — een bron die 100 kopers aandraagt is slechter dan een die 12 winkels vindt.

**Doelgroep (2026-07-29, na Daniels feedback):** serieuze RESELLERS, geen kringloopwinkels. Kringloopwinkels/goede doelen werken met vrijwilligers, hebben geen winstmotief, verzenden niet en verkopen onverzendbare meubels — precies de groep die de eerste hashtaglijst (#kringloopwinkel, #brocante, #vintagemeubels) opleverde. De classificatie toetst nu op drie assen (winstmotief, verzendbaarheid, NL/BE) en `REJECT_TYPES` gooit kringloop/meubels/consument/influencer/merk eruit, ongeacht wat het model zelf van `is_lead` vindt — dat vat te veel samen en liet kringloopwinkels met keurige onderbouwing door. Beste hashtag: **#vintednederland** (12 unieke resellers uit 30 posts, helft haalde de classificatie).

`run` doet de hele trechter in één commando; `--dry-run` slaat alleen het wegschrijven naar Notion over. De Notion-laag zit apart in `scripts/leadgen_notion.py`.

**Herzien 2026-08-10 na een run van drie kwartier die nul nieuwe leads gaf.** Gemeten over 194 beoordeelde profielen: `local` haalt 19% leads, `hashtag` 6%. Bovendien is `hashtag` na een paar runs *op* — een hashtagpagina geeft ~27 posts terug hoe hoog `--per-tag` ook staat, dus dezelfde tags opnieuw scrapen levert 0-2 nieuwe handles. `local` levert elke run verse accounts (stad × term × 5). Beide staan nu standaard aan via `DEFAULT_METHODS`; `--method` accepteert meerdere waarden.

Drie dingen die de run traag en zinloos maakten, alle drie verholpen:
- Mislukte handles werden eeuwig opnieuw opgevraagd. Een handle die drie rondes "Could not retrieve profile data" geeft is verwijderd of hernoemd, niet tijdelijk druk — een derde ronde leverde 1 profiel op 198 pogingen. Nu telt `fails` per rij door over runs heen en gaat een handle op `dead` na `MAX_FAILS`; `enrich --retry-dead` maakt dat ongedaan.
- Elk profiel werd elke run opnieuw door Haiku beoordeeld. Het oordeel staat nu onder `verdict` op de rij in `handles.json` (daarom leest `classify` handles.json en niet candidates.json — dat bestand wordt bij elke enrich herschreven).
- Alles liep sequentieel terwijl het vrijwel alleen wachten is. Actor-runs en modelaanroepen gaan nu door een ThreadPoolExecutor.

- `discover` stapelt in `handles.json` in plaats van te overschrijven; `enrich` muteert diezelfde dicts, zodat `--limit` niet de rest van het bestand wegsnijdt.

Er staat geen `APIFY_TOKEN` in de lokale `.env` (alleen op Railway) — lokaal draaien vereist een `export`.

---

## verborgen-tabblad-vertraagt-wachttijden

*10-08-2026 — Chrome rekt elke wachttijd onder 1s op tot een hele seconde in het onzichtbare job-tabblad; wacht op DOM-verandering (waitUntil) i.p.v. op de klok*

De extensie vult formulieren in een tabblad in een achtergrondvenster. Chrome
behandelt dat als "hidden" en klemt élke setTimeout onder 1000 ms vast op 1
seconde (gemeten: sleep(150) → 999 ms). Honderden kleine pauzes in één
formulier werden zo minuten, waarna de 3-minuten-bewaker de opdracht afbrak
terwijl het formulier al gevuld was — het klassieke "alles ingevuld, niets
geplaatst".

**Why:** dit is onzichtbaar bij het testen in een zichtbaar tabblad, dus elke
timing-analyse die uitgaat van de opgegeven ms-waarden klopt niet voor productie.

**How to apply:** gebruik `waitUntil(voorwaarde, timeout)` uit shared.js (wacht
via MutationObserver op een echte paginaverandering) in plaats van poll-lussen
met `sleep()`. Reken bij bestaande lussen met ~1 seconde per await. Zie
"job-dispatch-serialisation"; de testopstelling in `tests/vinted-mock`
reproduceert dit (draait in een verborgen tabblad).

---

## geen-gedachtestreepjes

*09-08-2026 — Daniel wil nooit gedachtestreepjes of koppelstreepjes als leesteken in tekst die ik voor hem schrijf*

Gebruik nooit een gedachtestreepje of streepje als leesteken, niet in rapportage
aan Daniel en niet in teksten die hij naar buiten stuurt (mails, blog, DM's).
Gevraagd op 09-08-2026.

**Why:** het valt hem op en het leest voor hem als machinetekst; hij wil dat zijn
mails als mensenwerk overkomen.

**How to apply:** splits de zin, of gebruik een komma, dubbele punt of punt.
Streepjes binnen woorden en in bestandsnamen mogen gewoon. Geldt ook voor de vier
rapportageblokjes uit "rapportage-in-gewone-taal".

---

## instagram-ban-augustus-2026

*09-08-2026 — "Daniels Instagram is sinds ~09-08-2026 geband via zijn gekoppelde Facebookprofiel; bezwaar loopt, reactie verwacht rond 10-08-2026"*

Sinds ongeveer 09-08-2026 is Daniels Instagram-account geblokkeerd, veroorzaakt
door het eraan gekoppelde Facebookprofiel. Hij heeft bezwaar ingediend en
verwachtte rond 10-08-2026 een reactie.

**Why:** Instagram is een van de vier leadgen-bronnen en volgens
"instagram-leadgen-bronnen" de beste (hashtags). Zolang de ban loopt, staat die
kant van de acquisitie stil en heeft het geen zin om IG-outreach te plannen.

**How to apply:** vraag naar de uitkomst van het bezwaar voordat je
Instagram-werk voorstelt of inplant; wijk zo nodig uit naar de andere bronnen.
Zie ook "leadgen-vier-bronnen". Blijkt de ban definitief, dan is dit geheugen
verouderd en moet het herschreven worden.

---

## stripe-checkout-live-config

*08-08-2026 — "Betalen lukte nooit door drie losse live-config-fouten; /health toont nu per sleutel ja/nee, en Railway bakt env-vars bij de build"*

Tot 08-08-2026 kon niemand betalen. Drie oorzaken achter elkaar, allemaal
configuratie en niet de code: (1) iDEAL/Bancontact expliciet meegeven in
mode=subscription is verboden zolang sepa_debit uit staat, waardoor Stripe ÉLKE
checkout weigerde; (2) de Stripe-variabelen stonden helemaal niet in Railway, en
de webhook wees naar `api.omnivaleur.com` — een tweede, volledig lege Railway-
service; (3) de `STRIPE_SECRET_KEY` in Railway was een oude, ongeldige sleutel
(eindigde op `d6F$`; de geldige eindigt op `hM3o`).

**Why:** elk van deze drie gaf dezelfde vage "Could not start checkout", dus het
leek steeds op één bug. Zonder meetpunt is dit uren gokken.

**How to apply:** `GET /health` geeft nu per instelling ja/nee terug (nooit de
waarde) — check dat eerst bij elke "werkt niet live"-klacht. Railway bakt
env-vars als ENV in het image, dus een gewijzigde variabele werkt pas na een
nieuwe build, niet na een herstart. Geef fouten nooit als 502 terug: Cloudflare
vervangt de inhoud van een 502 door zijn eigen storingspagina. Zie ook
"deploy-pipeline" en "proefperiode-en-toegangsslot".

---

## proefperiode-en-toegangsslot

*04-08-2026 — "7 dagen proef + 2 dagen respijt, server-side afgedwongen met 402; twee herinneringsmails vereisen twee handmatige Supabase-kolommen"*

Sinds 04-08-2026 wordt de paywall op de server afgedwongen, niet meer alleen in
het scherm. `require_active_subscription` (backend/api/deps.py) geeft 402 op
crosslisten, publiceren, imports, listing-refresh en de jobwachtrij van de
extensie. Lezen en betalen blijft altijd open, en bij een databasestoring of een
ontbrekende abonnementsrij valt het bewust open (niemand buitensluiten).

Ritme: 7 dagen proef → `GRACE_DAYS = 2` respijt → slot. Twee mails, dagelijks om
09:00 NL vanuit `send_trial_reminders`: één als de proef binnen 2 dagen eindigt,
één op de laatste dag van het respijt.

Beide mails hangen aan een kolom die met de hand in Supabase gezet moest worden:
`trial_reminder_sent_at` en `final_reminder_sent_at`. Ontbreekt er één, dan
stuurt die taak bewust níéts (anders zou hij iedereen dagelijks mailen). Een
nieuwe mailsoort erbij betekent dus opnieuw een handmatige ALTER TABLE.

**Why:** de proefperiode was maandenlang gratis door te gebruiken, en de
markeerkolommen zijn de enige rem op dubbele mail.

**How to apply:** raak `GRACE_DAYS` of de mailmomenten niet aan zonder ook de
teksten na te lopen — die noemen het aantal dagen letterlijk.

Zie ook "railway-blokkeert-smtp" en "extension-heartbeat-migration".

---

## notion-api-beperkingen

*31-07-2026 — "Notion-MCP kan geen status-opties zetten, geen Assignee verwijderen en geen UI-snelfilters wissen; SQL-query's zijn gelimiteerd op het huidige plan"*

Bij het opschonen van de Leadlist (31-07-2026) tegen deze grenzen aangelopen:

- **Status-opties zijn niet via de API te zetten.** `ADD/ALTER COLUMN ... STATUS`
  geeft altijd de standaard Not started/In progress/Done. Wil je een eigen
  trechter, gebruik dan een `SELECT` (daar werken opties + kleuren wél).
- **`Assignee` is niet te droppen** in een database die uit een taken-template
  komt: "Cannot delete a required property from a typed collection." Verbergen
  in de views is het enige dat kan.
- **`CLEAR FILTER` wist alleen de geavanceerde filters**, niet de
  `simpleFilters` (de snelfilterchips uit de UI). Een view met oude chips is via
  de API niet schoon te krijgen — maak een nieuwe view aan.
- **`ALTER COLUMN ... SET MULTI_SELECT` werkt alleen in een losse call**, niet
  gecombineerd met een `RENAME COLUMN` in dezelfde statement-reeks (wordt dan
  stil genegeerd). Waarden blijven bij de omzetting behouden, maar opties die je
  weglaat verdwijnen — snapshot ze eerst.
- **`query-data-sources` (SQL) heeft een gebruikslimiet** op het huidige plan.
  Raak je die kwijt, dan is `fetch` op een losse pagina het alternatief om te
  verifiëren.

**Why:** stuk voor stuk stille of cryptische fouten waar je makkelijk data mee
kwijtraakt.

**How to apply:** snapshot altijd de kolomwaarden (via één SQL-select) vóór een
type-omzetting, en verifieer daarna op één pagina met `fetch`.
Zie ook "leadlist-outreach-formula".

---

## cloudflare-blocks-ai-crawlers

*31-07-2026 — "Cloudflare's managed robots.txt blokkeerde GPTBot/ClaudeBot/Google-Extended op omnivaleur.com; sinds 31-07-2026 uitgezet — controleer altijd de LIVE robots.txt, niet het repo-bestand"*

De live `https://omnivaleur.com/robots.txt` is niet per se gelijk aan
`frontend/robots.txt`: Cloudflare kan er een eigen "Managed content"-blok vóór
plakken. Tot 2026-07-31 deed het dat ook, met `Disallow: /` voor ClaudeBot,
GPTBot, Google-Extended, CCBot, Applebot-Extended, Bytespider en
meta-externalagent, plus `Content-Signal: ai-train=no`.

Dat maakte de hele GEO/AI-SEO-opzet van de blogs (quick-answer blok, FAQ-schema,
key takeaways — allemaal gebouwd om geciteerd te worden) waardeloos: de bots die
moesten citeren mochten niet binnen. Een eigen robots.txt kan dit niet
overrulen — Cloudflare's groepen staan eerst en zijn per user-agent specifieker
dan `User-agent: *`.

**Status:** Daniel heeft het blok op 2026-07-31 uitgezet. Geverifieerd: geen
Cloudflare-blok meer in de live robots.txt, en GPTBot, OAI-SearchBot, ClaudeBot,
PerplexityBot, Google-Extended en Googlebot krijgen allemaal de volledige pagina
(2045 woorden, quick-answer, FAQ- en Article-schema), identiek aan een gewone
browser en zonder challenge.

**Why:** het is een dashboard-instelling die buiten de repo om kan veranderen —
een Cloudflare-update of een collega kan hem opnieuw aanzetten zonder dat er
iets in git verandert.

**How to apply:** vertrouw nooit op `frontend/robots.txt` als bewijs. Check de
live output (`curl -s https://omnivaleur.com/robots.txt`) én of bots echte
inhoud krijgen (pagina ophalen met een GPTBot/ClaudeBot user-agent en het
woordenaantal vergelijken met een gewone browser). Uitzetten kan alleen in
Cloudflare → zone `omnivaleur.com` → AI Crawl Control / "Manage robots.txt".
Zie ook "deploy-pipeline".

---

## blog-beeldsysteem-valkuilen

*31-07-2026 — "Blogbeeld komt uit hero.py + dashboard_images.py; Vinted blokkeert screenshots, de prijs-view rendert niet los, en elke <nav> erft de sticky sitebalk-CSS"*

Het beeld in blogs komt sinds 2026-07-31 uit drie bronnen: `backend/content/hero.py`
(unieke hero per slug, ook de og:image), `backend/content/dashboard_images.py`
(app-screenshots, per onderwerp gekozen en per slug geroteerd) en
`backend/content/web_images.py` (platform-screenshots). Verversen:
`scripts/capture_dashboard_screenshots.py` (na `seed_demo_account.py`) en
`scripts/capture_marketplace_screenshots.py`. Terugwerkend toepassen:
`scripts/backfill_blog_upgrade.py` (idempotent).

Drie dingen die je anders opnieuw ontdekt:

1. **Vinted is niet te screenshotten.** Zowel screenshot-services als een
   headless browser krijgen een botcontrole ("Verifieer dat u een mens bent") of
   een "Where do you live?"-landenkiezer over de pagina. Die landenkiezer stond
   maandenlang als "Vinted-interface" in élk artikel. Niet omzeilen — Vinted
   staat daarom bewust niet in `PLATFORMS`.
2. **`showView('prijs')` valt terug op het Account-scherm.** Een screenshot van
   die view levert dus een abonnementenpagina op onder een prijsadvies-bijschrift.
   Ook Marktplaats' cookiemuur zit in een iframe (2dehands' variant is wél weg te
   klikken).
3. **`_chrome_style.html` style't élke `<nav>`** als de sticky sitebalk
   (`height:64px; display:flex; position:sticky`). Voeg je ergens een `<nav>` toe
   (inhoudsopgave!), dan moet je al die eigenschappen expliciet terugzetten,
   anders klapt het blok dicht op 64px en loopt de inhoud eronderdoor.

**Why:** alle drie zijn stil falend — er komt geen foutmelding, er staat gewoon
een verkeerd of kapot beeld live.

**How to apply:** bekijk na elke capture-run de bestanden zelf voordat je ze
promoveert; de scripts zetten nieuwe platform-shots daarom in `_review/`.
Zie ook "deploy-pipeline" en "frontend-parse-json-safe".

---

## mp-2dehands-hidden-description-field

*30-07-2026 — "Marktplaats/2dehands valideren de beschrijving op een verborgen input, niet op de zichtbare Lexical-editor"*

Het SYI-formulier van Marktplaats/2dehands valideert de advertentietekst op een
verborgen veld `input[name="description_nl-BE"]` (NL: `description_nl-NL`), niet
op de zichtbare Lexical-editor. Live gemeten op 2026-07-30: de Lexical-API vullen
zet wel de zichtbare tekst maar laat dat verborgen veld leeg, en dan blijft
"Geen zoekertjestekst ingevuld" staan en weigert het formulier te plaatsen.

Ook gemeten in diezelfde sessie:
- `document.execCommand('insertText')` doet op dit veld helemaal niets (geen DOM,
  geen editorstaat) — als terugvaloptie waardeloos.
- `chrome.debugger.attach` faalt op deze machine altijd, zowel op `{tabId}` als op
  `{targetId}`, met "Cannot access a chrome-extension:// URL of different
  extension". De trusted-keystroke route is daarmee dood.
- Het verborgen veld staat onder React-beheer (`_valueTracker`); zetten via de
  prototype-setter plus een bubbling `input`-event blijft staan.
- `input[name="images.ids"]` is de betrouwbare bron voor "zijn de foto's er?" —
  miniaturen tellen is per categorie anders.

**Why:** vier releases lang is er naar veldnamen en toetsaanslagen gezocht terwijl
de echte bron van waarheid een verborgen input was.

**How to apply:** vul bij elke beschrijvingswijziging óók het verborgen veld, en
lees het terug vlak voor het plaatsen. Zie "extension-release-bump-version".

---

## facebook-marketplace-beta

*29-07-2026 — "Facebook Marketplace is a beta best-effort extension platform; selectors unverified, account-ban risk"*

Facebook Marketplace was added (2026-07-18) as a **beta, best-effort** extension platform, wired end-to-end like Vinted:
- extension: `extension/content/facebook.js` (create happy-path + best-effort delete), `background.js` create/delete URLs + `EXTENSION_PLATFORMS`, manifest host-permission + content-script match (shipped in v1.0.102)
- backend: `crosslist.py` → `EXTENSION_PLATFORMS`, `_PLATFORM_REQUIRED["facebook"] = ["category"]`, `_EXTENSION_DELIST_PLATFORMS`
- frontend `app.html`: platform lists, labels, `📘` icon, margin calc, filter, mark-active, publish checkboxes, plus `BETA_PLATFORMS` risk warnings

**Verified live (2026-07-18, NL account, read-only inspection):**
- The create form (`/marketplace/create/item`) is fully localised. Required fields carry Dutch aria-labels: **Titel, Prijs, Categorie, Staat**; flow button is **Volgende** (not "Publish" — final step is "Publiceren"). "Staat" options: **Nieuw / Gebruikt - zo goed als nieuw / Gebruikt - in goede staat / Gebruikt - in redelijke staat**. facebook.js now matches NL+EN for all of these (v1.0.104).
- FB gates the form behind a one-time **DMA/GDPR consent** (`/privacy/consent?flow=fb_dma_marketplace`) and can show `/checkpoint`. facebook.js loads on those URLs too and reports a clear job error instead of hanging (v1.0.103).

**Selector mechanics (verified live, v1.0.105 — this is the crux):**
- Titel/Prijs `<input>` and Categorie/Staat comboboxes have **NO aria-label/placeholder**. Their accessible name comes from the **wrapping `<label>`** (`<label><span>Titel</span><input></label>`). So field-finding MUST read `el.closest('label').textContent`, not aria-label. (First symptom of getting this wrong: "only condition fills" — because Staat's own matching happened to work while title/price/category didn't.)
- Category is a **hierarchical tree of plain clickable `<div>`s (role=null), no free-text search** — not role=option. Match option nodes by exact text across a broad selector (div/span/li/a), innermost-first, then click. The flat clothing leaves **"Herenkleding en -schoenen" / "Dameskleding en -schoenen"** are directly selectable; map by gender. Generic fallback "Kleding en accessoires".
- `typeInto` via the native value setter + input/change event sticks in FB's React inputs (verified).
- **Price is INTEGER-ONLY** (verified live, NL). The field rounds whatever you type (29,50→€30, 19,95→€20, 1234,56→€1235) AND reads a "." as a thousands separator ("29.99"→2999 — the original "prijs klopt niet" bug). Fix (v1.0.106): type the rounded whole-euro amount with NO separator (`String(Math.round(price))`) — plain "30"/"1235" render as "€ 30"/"€ 1.235".
- **Beschrijving is a `<textarea>` that only mounts AFTER a category is picked** (it's a clothing-specific field, alongside Grootte/Merk). A single findField right after the condition combo could miss it → description stayed empty while everything else filled. Fix (v1.0.106): poll (`waitForField`) until it mounts.
- **Photo upload mechanism works** via DataTransfer: set the image `input[type=file]` (first of 3 — accept `image/*`, the others are video and a generic `file`), `.files`, dispatch change → FB renders a `blob:` preview `<img>`. Confirm success by waiting for a `blob:` img (NOT scontent — FB's own profile/chrome imgs are scontent). If photos were provided but no blob preview appears, throw (likely cross-origin fetch block on the image host) instead of publishing photoless. Whether real Supabase photo_urls fetch cleanly from facebook.com context is still UNconfirmed end-to-end.

**Category mapping — non-clothing gap fixed (v1.0.107, 2026-07-19):**
- FB has NO numeric category IDs; it's a flat click-list matched by exact visible text. `fbCategoryCandidates()` originally handled ONLY clothing (men/women), so every `games ...` / `electronics ...` item (Daniel's whole non-clothing catalog) fell through to "Kleding en accessoires" — wrong category + wrong (clothing) attribute fields. Fixed: non-clothing prefixes are now mapped BEFORE the gender logic.
- **VERIFIED live (NL account, read-only DOM inspection of `/marketplace/create/item`):** FB top-level leaves that are directly selectable — **games → "Videogames"**, **electronics → "Elektronica en computers"** (both mount a Beschrijving field just like the clothing leaves; Videogames also mounts optional Platform/Genre/ESRB/Merk which we leave empty). Full top-level list also includes: Huis en tuin, Gereedschap, Meubels, Huishouden, Tuin, Apparaten, Amusement, Videogames, Boeken/films/muziek, Kleding en accessoires, Dameskleding en -schoenen, Herenkleding en -schoenen, Elektronica, Elektronica en computers, Mobiele telefoons, Speelgoed en spellen, Sport en buitenleven, Muziekinstrumenten, Antiek en verzamelobjecten, Voertuigen, Overig.
- The create form loaded with NO consent gate this session (already granted on this account).

**Publish + delete flow — VERIFIED end-to-end via a real test publish (NL account, 2026-07-19, item deleted right after):**
- A full publish SUCCEEDED: photo (via canvas→File→DataTransfer, no external fetch) → Titel/Prijs(€5)/Categorie=Videogames/Staat/Beschrijving → **Volgende** advances to `/marketplace/create/item?step=audience` → **Publiceren**. So the two-step Volgende→Publiceren flow is real and works.
- **Publish redirect (BUG fixed):** after Publiceren FB redirects to **`/marketplace/you/selling`**, NOT `/marketplace/item/{id}`, and the new listing sits "in beoordeling" with NO public item URL. The old `publishAndCapture` waited only for `/item/{id}` → burned the 15s timeout and always returned null. Fixed to treat the `/you/selling` redirect as success and capture an id only if one appears (usually none). Consequence: `platform_listing_id` is normally null, so delete jobs fall back to the `/you/selling` URL (see getDeleteUrl in background.js).
- **Delete is a THREE-click flow (BUG fixed):** on `/you/selling` the card's "..." menu → **"Advertentie verwijderen"** → confirm **"Verwijderen"** → a SECOND survey **"Heb je dit artikel verkocht?"** (radio: Ja verkocht op FB / Ja ergens anders / Nee, niet verkocht / Ik geef liever geen antwoord) → **Volgende**. Old `deleteListingFb` (a) matched `/^verwijder/` which never hit "Advertentie verwijderen", (b) used the FIRST menu on the page (could delete the WRONG listing since /you/selling lists all items), and (c) skipped the survey step. Rewritten to scope to the card by exact title, match "verwijder" anywhere, and complete the survey. Delete VERIFIED to fully remove the listing (empty state after).
- Photo upload via DataTransfer CONFIRMED working (blue test image rendered in thumbnail + preview). The blob:-preview check can be too fast; FB may render the thumbnail slightly later.

**Fotobewijs — blob: bestaat NIET meer (v1.0.139, 2026-07-29, live geverifieerd):**
- De create-pagina bevat **nul `<img>`-elementen** tot er een foto gekozen is. Zodra dat gebeurt uploadt FB direct naar zijn eigen CDN en rendert `scontent-*.fbcdn.net` met `alt="Advertentiefoto"`/`"Productfoto"`. Er is **geen `blob:`-preview** — de eerdere notitie hierboven klopt niet meer.
- Dit brak alles: de Marktplaats-herschrijving van `uploadPhotos` (shared.js) gooit sinds v1.0.13x een fout als er geen thumbnail verschijnt, en zocht alleen naar `blob:`/MP/Vinted-hosts. Op Facebook wachtte hij dus 45s, gooide, en `fillForm` stierf **vóór het eerste veld** — de melding "er wordt niks ingevuld".
- Fix: `uploadPhotos(urls, { thumbSelector })` accepteert nu een platform-eigen selector; facebook.js geeft `FB_PHOTO_THUMBS` mee. Matchen op `fbcdn.net` is veilig omdat de baseline nul is en uploadPhotos voor/na vergelijkt. `waitForPhotoPreview` is verwijderd (dubbelop).
- Live bevestigd na de fix: foto + Titel + Prijs (€ 30) + Categorie (Videogames) + Staat + Beschrijving vullen allemaal. Selectors voor alle velden zijn dus nog steeds goed — het zat puur in de fotocontrole.
- **Les:** `shared.js` is gedeeld met MP/2dehands/Vinted. Elke verscherping daar (throw i.p.v. return false, hardere verificatie) kan Facebook stilletzwijgend slopen, want FB's DOM lijkt op geen van de andere. Draai na elke shared.js-wijziging de veldcontrole op het live FB-formulier.

**Key caveats / How to apply:**
- A full **dry-run of field-filling** (title/price/category/condition) passed on the live form, but an actual **publish (Volgende→Publiceren) and the post-publish URL capture + delete flow were NOT executed** — still unproven. Pin any remaining issues from `[Omnivaleur]` console output of a real publish.
- Facebook obfuscates markup (rotating class names) and detects automation — still best-effort, still account-ban risk.
- Real **account-ban risk** for the seller — this is surfaced in the UI as an explicit beta warning; keep that warning whenever touching this platform. Advise a separate FB account.
- Facebook is create-first; auto-delist on sale is wired but best-effort. No translation (uses the item's own NL text). No per-platform `price_facebook` column — falls back to base `price`.
- See "extension-release-bump-version" and "extension-version-floor" for the build/version rules, and "deploy-pipeline" for going live.

---

## instagram-leadgen-bronnen

*29-07-2026 — Welke bronnen wel/niet werken voor Instagram-leadgen; Vinted is onscrapebaar en Marktplaats heeft geen brug naar Instagram*

Voor de Instagram-outreach van Omnivaleur (`scripts/leadgen_instagram.py`) zijn in juli 2026 drie bronnen live getest:

**Vinted — onbruikbaar als serverbron.** Zit achter Cloudflare en weigert datacenter-IP's. De publieke JSON-API geeft 403 op de homepage en 401 op `/api/v2/catalog/items`; drie verschillende Apify-actors (scrape.badger, epicscrapers, kazkn) gaven allemaal nul resultaten of faalden. Werkt alleen vanuit de browser van de gebruiker zelf, zoals de extensie doet.

**Marktplaats — scrapet prima, maar geen brug naar Instagram.** `haketa/marktplaats-scraper` werkt betrouwbaar (velden: sellerName, sellerId, sellerType, location). Maar er is geen automatische weg van een MP-verkoper naar zijn Instagram: handles raden uit de winkelnaam gaf 4 treffers op 13 gokken en de enige echte match was een verzamelaar uit Tokio, en **0 van 53 advertentiebeschrijvingen** noemde een @handle of instagram-link. Als leadbron voor IG dus dood; als losse lijst NL-verkopers nog wel bruikbaar.

**Instagram-hashtags — beste bron, met afstand.** `apify/instagram-hashtag-scraper` op Nederlandse tags: 30 posts op #kringloopwinkel gaven 22 unieke NL-kringloopwinkels, 83% overleefde de Haiku-classificatie. Kies tags die een *verkoper* gebruikt en een koper niet (#kringloopwinkel wel, #thrifthaul niet). Let op: `coderx/instagram-hashtag-scraper` is goedkoper maar knijpt gratis accounts af tot **één run per dag**, en meldt dat als gewone datarij met een `error`-veld — niet als HTTP-fout.

**Instagram keyword-discovery — werkt, maar 5 per run.** `afanasenko/instagram-profile-scraper` in `keywordDiscovery`-modus met **Nederlandstalige** zoektermen. Die taal is zelf het landfilter — "kringloop" bestaat alleen in NL/BE, terwijl "thrift" de halve wereld binnenhaalt.

**De sleutel tot het omzeilen van die 5-limiet:** die zit op de *discovery*-actor, niet op Instagram-data in het algemeen. `figue/instagram-profile-scraper` haalt ongelimiteerd profielen op voor ~$0,001. Vandaar de splitsing in `discover` (alleen handles) → `enrich` (profieldata) in "leadgen-vier-bronnen". De limiet geldt bovendien *per run*, dus losse runs per stad geven 14x5 in plaats van 5.

**Bewust niet gebouwd: instaloader.** Anoniem profielen ophalen is stuk (400 "ig_business_category_subvertical" op elk testaccount); werkend krijg je het alleen met ingelogde sessie, en dan riskeer je je eigen account voor data die $0,001 kost.

Categorie-ID's van `haketa/marktplaats-scraper` zijn grotendeels dood: alleen **621 (Kleding|Dames), 504 (Huis en Inrichting), 1099 (Hobby en Vrije Tijd), 728 (Muziek), 91 (Auto's)** geven resultaten. De andere veertien in de enum accepteert hij wel maar leveren stil nul items — een geaccepteerde input is hier geen bewijs, zie ook "marktplaats-category-ids".

Koude DM's mogen niet via de officiële Instagram-API (alleen antwoorden binnen 24 uur nadat iemand jou schrijft). Het script automatiseert daarom alles tot en met de kant-en-klare tekst in de "leadlist-outreach-formula", maar verstuurt zelf niets.

---

## blog-evaluator-and-infographics

*28-07-2026 — Blog-evaluator draait op GSC-data en herschrijft op dezelfde slug; infographics zijn deterministische SVG uit de artikel-eigen tabellen*

De contentpijplijn heeft sinds 2026-07-28 een post-publicatie helft:
`backend/content/evaluator.py` scoort elke gepubliceerde pagina op Search
Console-cijfers en laat de slechtste door `run_pipeline` herschrijven op
DEZELFDE slug (intent_key is UNIQUE → update, geen duplicaat).

Twee dingen die niet uit de code blijken:

1. **De evaluator doet voorlopig niets.** Alle 46 pagina's waren op de bouwdag
   20-25 dagen oud; `MIN_AGE_DAYS = 45` houdt ze op `too_young`. Reken op
   ~half september 2026 voor de eerste echte refresh. Lokaal is GSC bovendien
   niet geconfigureerd (net als "ebay-local-sandbox-creds") — alleen op
   Railway.
2. **`content_page_performance` vereist een handmatige Supabase-migratie**
   (staat in schema.sql). Tot die draait wordt alleen de historie overgeslagen,
   niet de evaluatie — zelfde patroon als "extension-heartbeat-migration".

Infographics (`backend/content/infographics.py`) zijn bewust GEEN AI-beelden:
beeldmodellen renderen tekst onbetrouwbaar. Het zijn inline SVG's afgeleid uit
de tabellen/lijsten van het artikel zelf, ingevoegd met **string-splicing, niet
`str(soup)`** — BeautifulSoup-herserialisatie herordent attributen en is precies
het mechanisme achter "blog-linking-corrupts-img-src". De injectie is
idempotent en byte-voor-byte additief; `scripts/backfill_infographics.py` is
daarom veilig herhaalbaar en is al toegepast op 36/46 artikelen.

---

## omnivaleur-blocking-supabase-event-loop

*23-07-2026 — "Omnivaleur backend uses a synchronous Supabase client inside async routes on a single uvicorn worker, causing site-wide stalls/empty responses under load"*

`backend/database.py`'s `get_db()` returns supabase-py's synchronous `Client` (blocking httpx.Client underneath). It's called directly (no `await`/thread offload) from many `async def` route handlers across the codebase. Railway runs uvicorn with exactly 1 worker (`railway.json`), so any one blocking Supabase call freezes the ENTIRE process's event loop — including totally unrelated requests like `/health` — for as long as that call takes.

**Why this matters:** under concurrent load (dashboard tabs + extension job-polling + AI translation calls), this snowballed into Railway's Response Time metric climbing past 20s, and sometimes a request's connection got cut mid-response — surfaced to the user as "site laadt niet" and a login page showing `Unexpected end of JSON input` (empty response body). Confirmed live 2026-07-23 by hitting the raw `*.up.railway.app` domain directly (bypassing Cloudflare): `/health` sometimes hung 25s+, `/api/jobs/pending` sometimes returned the correct FastAPI 422 instantly and sometimes hung — proof it's origin-side contention, not Cloudflare/DNS.

**Why `--workers N` was rejected as the fix:** `backend/scheduler.py`'s `start_scheduler()` runs in the FastAPI lifespan, i.e. once per worker PROCESS. Multiple uvicorn workers would duplicate polling jobs, relist checks, trial expiry, and — worst — the weekly marketing email, once per worker.

**How to apply:** fixed the two hottest paths so far — `get_current_user_full` (deps.py, runs on nearly every authenticated request) and `/api/auth/login` (auth.py) — by wrapping the blocking Supabase call in `asyncio.to_thread(...)`. The SAME blocking pattern (`db.table(...).execute()`) still exists throughout items.py, jobs.py, listings.py, crosslist.py, etc. — this was NOT a full fix, just the highest-impact spots. If stalls/empty-response symptoms return, the next place to look is those other route files, following the same `asyncio.to_thread` pattern, OR migrating to `supabase-py`'s async client if one becomes available/stable.

---

## anthropic-credit-silent-translation-fallback

*23-07-2026 — Depleted Anthropic API credit makes all Omnivaleur translation silently fall back to source text*

When the Anthropic API credit runs out, every Claude translation call in the backend errors and `_translate_with_claude` (backend/services/crosslist.py) catches it and returns the ORIGINAL text unchanged. Symptoms in the dashboard: eBay category suggestions stay Dutch, and Marktplaats/2dehands listings publish in English (title + description) instead of translated Dutch, sometimes as one block. Same root cause as the eBay category language complaint.

**Why:** the fallback is silent by design (so a listing still publishes), so a billing/credit problem looks like a translation *bug*.

**How to apply:** if translation "stops working" across the board, check Anthropic API credit / billing FIRST before touching translation code. Confirmed 2026-07-23: topping up credit restored it. A static NL→EN eBay category map ("marktplaats-category-ids" area, in ebay.py `_EBAY_SEGMENT_NL_EN`) was added as a resilience vangnet so at least categories stay English even with no working LLM.

---

## nexus-learning-db-in-git

*22-07-2026 — "NEXUS trading bot's leerlogboek is een binaire SQLite in git; werd gewist door -X ours merge; nu additief unioned"*

Aparte repo `nexus-market-terminal` (lokaal in `~/Documents/Prediction Market Trading bot /`, remote github.com/danieldk04/nexus-market-terminal) — een autonome aandelen-signaalbot (NEXUS). Actieve code in `src/`; een GitHub Actions-scan ("NEXUS AUTONOMOUS INVESTMENT ENGINE", tier1_scan.yml) draait 2×/dag en commit `data/nexus_signals.db` — het leerlogboek — als binair bestand in git.

**Waarom het logboek telkens leeg raakte (opgelost 2026-07-22):** (1) `backfill_signals.py` (bouwt de technische backtest-historie) draaide nooit in de pipeline, dus de gecommitte DB had alleen live-scan-rijen; (2) `git merge origin/main -X ours` wiste bij elke scan het logboek van elke andere motor botweg omdat een binaire SQLite niet regel-voor-regel mergebaar is → last-push-wins clobber tussen de CI-bot en Daniels lokale/andere terminal.

**Fix:** `backfill_signals.py --if-empty` (bootstrap eenmalig), `signal_store.merge_from()` + `python src/signal_store.py --merge <db>` (union rijen additief, COALESCE zodat gerealiseerde uitkomsten nooit verloren gaan), en tier1_scan.yml unioneert origin's DB IN het onze vóór `-X ours` + race-veilige push-retry.

**Belangrijk:** een lokaal `backfill_signals.py`-run (5588 backtest-rijen) is NIET veilig als losse push — commit/rebase haalt de gecommitte versie op. De DB groeit nu monotoon via de union; laat de CI-bootstrap de historie opbouwen. Zie "always-push-to-live" — deze repo heeft z'n eigen auto-commit/-push-hook, dus expliciete commits worden ingepakt en direct gepusht.

---

## extension-heartbeat-migration

*22-07-2026 — "computer online?" indicator needs a manual Supabase CREATE TABLE extension_heartbeat*

The dashboard "Your computer is online / No computer online" indicator (Optie A, for mobile users) depends on a new `extension_heartbeat` table (user_id PK, last_seen, user_agent) defined in schema.sql. Supabase does NOT auto-apply schema.sql, so it must be created manually once in the SQL editor — same manual-migration gotcha as "sold-price-actual".

**Why:** Backend + frontend are self-healing — `/jobs/extension-status` returns `online:null` and the frontend hides the whole indicator until the table exists. So it silently does nothing (never errors) until the migration runs.

**How to apply:** Run the `CREATE TABLE IF NOT EXISTS extension_heartbeat (...)` block from schema.sql in Supabase. Heartbeat is stamped on the extension's existing `/jobs/pending?platform=` poll AND on claim/progress/complete/error (all extension-only). Online window = 120s.

**RLS gotcha (2026-07-22):** Verified realtime the table had ZERO rows — every upsert failed with `error 42501 new row violates row-level security policy`. Creating the table via the Supabase UI enables RLS-but-policyless, and the backend key is subject to RLS, so ALL writes were silently swallowed (`except: pass`) → indicator permanently stuck on "offline". Fix = run `ALTER TABLE extension_heartbeat DISABLE ROW LEVEL SECURITY;` in Supabase (now in schema.sql, matching platform_notifications). Same class of bug applies to any future UI-created table.

---

## ebay-listing-requirements

*21-07-2026 — "eBay Inventory API write-calls require a Content-Language header; refreshed OAuth tokens must be persisted back to platform_credentials"*

**Symptom (2026-07-17):** a customer complained eBay "asks for a verification code every time." Diagnosis via the DB: both eBay connections had a stored refresh_token and eBay *accepted* the Bearer token (returned an API error, not 401), so the koppeling worked. The real blocker: every `create_listing` failed with `Invalid value for header Content-Language`, which the customer read as a broken connection → reconnect → eBay 2SV code again. (The 2SV code itself is eBay-side two-step verification on the seller's account and cannot be disabled from Omnivaleur.)

**Fix 1 — Content-Language (the actual blocker):** eBay's Inventory API write-calls (`PUT inventory_item`, `POST offer`) *require* a `Content-Language` BCP-47 header matching the marketplace; without it eBay rejects the whole write. Added `_MARKETPLACE_LANGUAGES` (EBAY_NL→nl-NL, EBAY_US→en-US, …) and `_auth_headers(..., write=True)` in `backend/platforms/ebay.py`. The publish POST (step 3) has no body and needs no language header.

**Fix 2 — token writeback:** `_ensure_fresh_token` refreshed the access token but never persisted it, so every call re-refreshed. Now `_persist_refreshed()` writes the new access_token + token_expires_at back to `platform_credentials` (keyed on user_id+platform from the DB row). eBay's refresh response returns no new refresh_token, so the old one is preserved. Non-blocking (a write failure never fails the listing) and a no-op when creds lack user_id (unit-test safe).

**Fix 3 — category fallback (2026-07-17):** items without `ebay_category_id` used to fail (`EBAY_DEFAULT_CATEGORY_ID` is empty). `create_listing` now has a 3-step chain: 1) item's own `ebay_category_id`, 2) auto-resolve via the Taxonomy API on the title (`resolve_category_id()` → `_raw_category_suggestions()`, a slim no-translation share of `suggest_categories`), 3) `EBAY_DEFAULT_CATEGORY_ID` as last backstop. Chose auto-resolution over a hardcoded static ID because eBay category IDs can't be verified locally (401) and a wrong static ID reintroduces the failure. A title is required for a listing anyway, so step 2 covers real items. `EBAY_DEFAULT_CATEGORY_ID` on Railway remains optional — only set it with a verified leaf ID.

**Fix 4 — merchant location / Item.Country (2026-07-21):** publishing failed with `Er bestaat geen waarde voor <Item.Country>` because the offer had no `merchantLocationKey`, so eBay couldn't derive the ship-from country. `create_listing` now calls `_ensure_location()` (lazily creates a `MERCHANT_LOCATION_KEY="OMNIVALEUR_MAIN"` warehouse location under the user's own eBay account) and adds `merchantLocationKey` to the offer. Address is **per-user**: `_ship_from_address()` reads `platform_credentials.extra_data.ship_from` (postal_code/city/country), falling back to global env `EBAY_LOCATION_*`. Users set their own postcode via a form on the Platforms page → `POST /api/platforms/ebay/ship-from` → `upsert_location()` (create-or-update via `/location/{key}/update_location_details`). Also: RuName changed to `Daniel_de_Konin-Danielde-crossl-hnjbpa` (display "Omnivaleur"); the eBay auth accepted/declined URL must be set to `https://omnivaleur.com/ebay-callback.html` in the Developer Portal per environment (was still pointing at old crosslisteu.com). Next likely blocker after location: business policies (fulfillment/payment/return).

**Fix 5 — required item specifics (2026-07-21, VERIFIED WORKING):** after the location fix, clothing categories rejected publish with "De specificatie Stijl ontbreekt" (Style aspect missing) — required item specifics vary per category. Added `_get_required_aspects(category_id)` (Taxonomy API `get_item_aspects_for_category`, cached in `_required_aspects_cache`) + `_fill_required_aspects()`: maps gender→Department (Men/Women), Size Type→Regular, and for any other required aspect picks the first allowed value from eBay's closed list so publish never blocks on a missing spec. Best-effort (taxonomy failure doesn't block). After this, a real production publish to eBay SUCCEEDED — eBay is now end-to-end working (connect → location → aspects → publish).

**Testing note:** cannot be verified end-to-end locally — see "ebay-local-sandbox-creds" (local .env = sandbox, code hits production → always 401 locally). Confirm on Railway or via a real customer retry after deploy. See "deploy-pipeline".

---

## sold-price-actual

*20-07-2026 — Analytics uses actual sold_price (not asking price); requires a Supabase ALTER to add listings.sold_price*

Items rarely sell at their asking price (bids/offers, esp. Vinted/Marktplaats). Analytics now uses `listings.sold_price` (actual amount received) for revenue/profit, falling back to `item.price` (asking) as a flagged ESTIMATE when unknown.

- Column added in schema.sql via `ALTER TABLE listings ADD COLUMN IF NOT EXISTS sold_price NUMERIC(10,2)` — but schema.sql is NOT auto-run, so this **must be applied manually on Supabase** (as of 2026-07-20). Until then, writes fall back gracefully (crosslist.handle_item_sold catches the missing-column error) and the API just omits the field.
- Capture points: Shopify webhook (real line-item total), eBay webhook (best-effort), and manual `POST /api/listings/sold-price` {item_id, platform, sold_price}. Vinted sales are scan-detected with NO price → left NULL, user confirms via Analytics "Sales breakdown" (✎ / "confirm" / "Set actual price").
- Frontend: `renderAnalytics()` uses helper `saleAmt`/`isEstimate`; blue "still using the asking price" callout (`an-estimate-card`) lists sales to confirm. See "frontend-parse-json-safe".

---

## always-push-to-live

*20-07-2026 — Daniel wants code changes committed and pushed to live (origin main) by default*

Daniel's standing instruction (2026-07-20): after making code changes, **always commit and push to live** (origin/main) without asking each time — "push altijd naar live".

**Why:** He runs a continuous-deploy setup and treats main as live; he doesn't want a confirmation gate on every push.

**How to apply:** When work is done and verified, commit the relevant source files and push to origin/main. Note the repo has an auto-commit hook that often already commits changes (commits named `auto: update ...`), and origin frequently diverges — the working fix is `git stash -u` → `git pull --rebase origin main` → `git push` → `git stash pop`. `dist/` is gitignored (build zips aren't committed). See "deploy-pipeline" and "extension-release-bump-version".

---

## leadlist-outreach-formula

*19-07-2026 — "Notion Leadlist outreach column is now an LLM AI-autofill Text property; old formula hidden as backup"*

In the Notion "Leadlist" database (Instagram & FB Outreach), the main outreach column **"AI Generated Tekst"** is (as of 2026-07-19) a **Text property with Notion AI autofill ("Basic" agent)** — a real LLM that writes correct Dutch per row from a custom base prompt. The prompt references Name, Je/Jullie, Verkoopt vooral..., Verkoop op..., enforces je/jullie consistency, a natural sentence around Verkoop op (no "actief op fysieke winkel"), the Omnivaleur pitch (Marktplaats/eBay/Shopify), a demo-video CTA, "Groetjes, Daniel", and "leave empty if key fields not filled". Trigger: On page update → only when Name / Je-Jullie / Verkoopt vooral / Verkoop op change (limits credit burn, avoids overwriting manual edits).

The **old deterministic formula** that used to fill this column was renamed to **"AI formule (oud, backup)"** and hidden in the view (Σ formula, not AI). It produced grammatically-off Dutch ("actief op fysieke winkel", mixed je/jullie), which is why Daniel switched to the LLM.

**Why:** Daniel wanted real LLM-quality Dutch, generated centrally in Notion from one base prompt, for all existing and new leads.

**How to apply:** To change wording, edit the AI-autofill prompt (column header "AI Generated Tekst" → Autofill Text). AI autofill can't run on a formula, so the backup column stays formula-only. Notion AI autofill costs credits (~1 AI response per generated row); bulk-filling existing leads via "Run AI Autofill now" spends ~1 per lead. Availability: this workspace has custom AI autofill on Text props (Basic + Custom Agent); the property-type picker only pre-lists Summarise/Translate, so reach custom autofill via Edit property → AI Autofill. See "omnivaleur-brand-never-a-verb".

---

## omnivaleur-brand-never-a-verb

*17-07-2026 — "Content rule: 'Omnivaleur' is a brand name (noun) only, never a verb; the action is cross-list / crosslisten"*

"Omnivaleur" is a brand/product name — a noun, **never a verb**. The action of listing an item across marketplaces is "cross-list" / "cross-listing" (EN) or "crosslisten" / "crosslisting" (NL — that IS a valid Dutch verb). Use the brand only to refer to the product ("with Omnivaleur you can…", "Omnivaleur's refresh tool").

**Why:** the content generator turned the Dutch keyword verb "crosslisten" into the brand name in H1s, producing "How to Omnivaleur from Marktplaats to Vinted" (surfaced 2026-07-17). Reads as broken/amateurish and misuses the brand.

**How to apply:** guardrails now live in `backend/content/generator.py` — a CRITICAL BRAND RULE in the generation prompt and a note in the translation prompt (translate "cross-list" → "crosslisten", never to "Omnivaleur"). Two live pages were repaired (marktplaats-to-vinted, marktplaats-naar-vinted: H1 + article_json_ld.headline). When touching the content pipeline or reviewing generated copy, re-scan title/h1/quick_answer/body for `Omnivaleur` used as an action (patterns like "How to Omnivaleur", "to Omnivaleur from"). Brand-as-noun ("to Omnivaleur's tool") is fine. See "blog-linking-corrupts-img-src" for the content-pages DB structure.

---

## blog-linking-corrupts-img-src

*17-07-2026 — "Blog internal-link engine corrupted <img src> by linking platform names inside attribute values; fixed by blocking all tag markup + a backfill repair"*

**Symptom (surfaced 2026-07-17):** blog pages showed a broken image + literal text like `vinted.jpg" alt="..." loading="lazy" ...>`. Cause: the served HTML was `<img src="/assets/platforms/<a href="/reseller-tools/vinted-clothing-automation">vinted</a>.jpg">` — the internal-link engine had wrapped the word `vinted` **inside the img `src` attribute** in an `<a>`, shattering the tag.

**Root cause:** `backend/content/linking.py` `_blocked_ranges` only protected the *contents* of `<a>`/`<h1-3>` elements, not text inside a tag's own markup (attribute values). Platform names in `src="/assets/platforms/<name>.jpg"` were fair game. It got much more likely after the games/electronics work added many `<figure><img>` platform screenshots.

**Fix (prevention):** `_blocked_ranges` now also blocks every `<[^>]+>` span, so a term inside any attribute value is never linked. Verified: img src untouched, body-text mentions still linked, alt attributes untouched.

**Fix (repair):** added `repair_anchors_in_tags()` to linking.py — unwraps any `<a>…</a>` sitting at tag-depth >0 (idempotent). Backfill script `scripts/backfill_repair_anchors.py` (dry-run default, `--apply` to write). Ran it against production Supabase `content_pages`: 6 of 29 pages were corrupted (book-reselling-automation +nl, etsy-to-ebay-crosslisting +nl, omnivaleur-vs-list-perfectly-nl, omnivaleur-vs-vendoo-nl) — all repaired, live pages confirmed clean.

**Why it matters / how to apply:** any time you edit the content pipeline's HTML injection order or the link engine, re-run the dry-run backfill to catch regressions. Local `.env` has *production* Supabase creds (project `bgpeoaavbiaurpvybcqe`) — DB writes from local hit prod; always dry-run first. See "deploy-pipeline".

---

## extension-release-bump-version

*17-07-2026 — Any change under extension/ requires bumping manifest.json version AND building the zip with scripts/build-extension.sh — never tell Daniel to upload without doing both*

Whenever I change anything under `extension/`, I must **bump `version` in `extension/manifest.json`** in the same change, and build the package with `./scripts/build-extension.sh` (output: `dist/omnivaleur-extension-<version>.zip`). Never tell Daniel to "reload the extension" or "upload it to the Chrome Web Store" without having done both first.

**Why:** the Chrome Web Store rejects any upload whose version is not higher than the published one ("Ongeldig versienummer in manifest"). Daniel hit this repeatedly. He also zips by hand with Finder, which produces a stale archive wrapped in an `extension/` folder with `__MACOSX/` junk and an out-of-date manifest — so he was uploading old code without knowing. The build script zips the *current* folder with `manifest.json` at the archive root, excludes tooling cruft, and names the file after the manifest version so a stale build is obvious.

**How to apply:** treat "bump version + run build script" as part of the edit, not a follow-up step. Then point him at the exact `dist/…zip` path. Ignore the loose `extension*.zip` files in the repo root — they are stale Finder exports, not build output. Related: "deploy-pipeline" (backend auto-deploys via Railway; the extension never does — it always needs a Web Store upload).

---

## ebay-local-sandbox-creds

*17-07-2026 — Local .env has eBay SANDBOX credentials but the code calls production api.ebay.com — eBay lookups always 401 locally and cannot be tested end-to-end*

The local `.env` holds eBay **sandbox** credentials (`ebay_cert_id` starts with `SBX-`), while `backend/platforms/ebay.py` calls production `api.ebay.com`. Every eBay API call therefore fails locally with `401 Unauthorized` on the OAuth token request. Production (Railway) has working credentials — the dashboard returns real suggestions there.

**Why:** this is a local-environment mismatch, not a bug. Don't chase the 401 as a defect, and don't "fix" it by pointing the code at the sandbox host.

**How to apply:** anything touching eBay category suggestion (`suggest_categories`) cannot be verified end-to-end on this machine. Verify the deterministic parts instead — e.g. `_build_ebay_query` / `_clean_ebay_query` query construction — and say plainly that the live eBay response is unverified rather than implying it was tested. Related: "deploy-pipeline".

---

## job-dispatch-serialisation

*14-07-2026 — "Why extension jobs are dispatched strictly one-at-a-time, and why the content-script job is keyed per-tab — do not relax without care"*

The Chrome extension runs each job by opening a REAL browser tab and driving the marketplace inside it. Two failure modes bit hard (2026-07-14) and are now guarded — respect both before changing publishing throughput.

**1. Listing cross-contamination (data corruption).** The extension used to store the active job under one shared key per platform, `job_<platform>` in `chrome.storage.local`, and the content script read that. When two same-platform create tabs ran at once, the second `set` overwrote the first's job → listings published with each other's photos, prices, titles, descriptions. **Fix:** the background now stores the whole job per TAB (`jobtab_<tabId>`) and the content script asks for its own tab's job via a `GET_JOB` message (background uses `sender.tab.id`); it retries ~20×150ms for the tab-open race. See `extension/background.js` (processJob tab-open callback + GET_JOB handler) and `getJob()` in `content/{vinted,marktplaats,tweedehands}.js`. Extension version bumped to **1.0.11** — needs a Web Store re-upload to reach users.

**2. Tab-storm.** The create path does NOT await completion before the next job is claimed, so a bulk publish opened many tabs at once. **Fix (backend, `GET /jobs/pending`):** STRICT GLOBAL SERIALISATION — when called by the extension (`?platform=` present), if ANY job is freshly claimed (claimed within 5 min) it returns `[]`; otherwise it returns `ready[:1]`. So exactly one tab is ever in flight. The dashboard calls `/pending` WITHOUT a platform (just to count the queue) and is never throttled — it gets the full list.

Also in `/pending`: `_recover_stale_claims` rescues jobs stuck `claimed` >5 min with no recent progress (Chrome closed / SW killed mid-run) — retry-safe ones (delete, scan, content_refresh, relist recreate) reset to `pending`; an initial crosslist create is marked `error` (re-running could duplicate a listing that actually published); reclaim cap = 2.

**If you want faster publishing later:** once 1.0.11 (per-tab job) is widely installed, per-platform concurrency (1 per platform ≈ 3× faster) is safe. Until then keep it strictly serial — correctness of live listings beats speed. Related: "deploy-pipeline".

---

## deploy-pipeline

*14-07-2026 — How omnivaleur.com goes live — push to GitHub main → Railway auto-deploys; frontend served by the FastAPI backend*

Production (omnivaleur.com) is a single **Railway** service running the FastAPI backend (`railway.json` → `uvicorn backend.main:app`). The **frontend is served by that same backend** — `backend/main.py` returns `frontend/app.html` at `/app` and mounts `frontend/` as static. There is no separate Vercel/Netlify frontend deploy.

**Deploy chain:** commit → `git push origin main` (remote = `github.com/danieldk04/crosslisteu.git`) → Railway rebuilds & deploys automatically. So *nothing goes live until it's pushed to `main`.*

**Auto-commit/push** happens via a Claude Code PostToolUse hook in `/Users/Danie/.claude/settings.json` that runs `git add`+commit (`auto: update <file>`) and pushes on every file edit.

**2026-07-14 incident + fix:** the hook's push was `git push origin HEAD 2>/dev/null` — it swallowed errors and had `timeout: 30` (ms). When `origin/main` diverged (GA PRs #1–#7 + content-bot commits merged on GitHub, never pulled locally), every auto-push was silently rejected ("fetch first"), so ~20 commits piled up locally and production ran stale code for days. Fixed the hook to `git push … || { git pull --rebase --autostash origin <branch> && git push … } || git rebase --abort` and bumped timeout to 60000ms, so a diverged remote self-heals instead of blocking deploys. If deploys ever look stuck again, check `git log origin/main..HEAD` for an unpushed backlog.

---
