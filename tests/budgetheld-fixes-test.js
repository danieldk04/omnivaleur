/**
 * De drie punten uit het gesprek met Budgetheld (01-09-2026).
 *
 * 1. "Extension not detected" bleef staan bij mensen die de extensie wél
 *    hadden. Er ging één ping uit met 2,5 seconde wachttijd; een koud
 *    opgestarte service worker haalt dat lang niet altijd.
 * 2. De gekozen categorie sprong terug naar "Clothing & Shoes". Er stonden 68
 *    audio-, tv- en fotocategorieën in de lijst zonder bijbehorend item-type,
 *    dus viel de terugweg altijd op kleding.
 * 3. Vinted zette een groen vinkje bij een advertentie die er niet stond,
 *    omdat de klant niet op Vinted was ingelogd.
 *
 * Draaien:  node tests/budgetheld-fixes-test.js
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const APP = fs.readFileSync(path.join(ROOT, "frontend", "app.html"), "utf8");
const BG = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");
const VINTED = fs.readFileSync(path.join(ROOT, "extension", "content", "vinted.js"), "utf8");

let mislukt = 0;
function ok(naam, voorwaarde, toelichting) {
  if (voorwaarde) { console.log(`  ✓ ${naam}`); return; }
  mislukt++;
  console.log(`  ✗ ${naam}${toelichting ? " — " + toelichting : ""}`);
}

// ── 1. Categorieën: elke groep moet heen én terug kunnen ────────────────────
console.log("\nCategorie springt niet meer terug naar Clothing & Shoes");

const catStart = APP.indexOf("const CATEGORIES = {");
const CATEGORIES = eval("(" + APP.slice(catStart + "const CATEGORIES = ".length,
                                       APP.indexOf("\n};", catStart) + 2) + ")");

const labelStart = APP.indexOf("const CATEGORIE_TAK_LABEL = {");
const CATEGORIE_TAK_LABEL = eval("(" + APP.slice(
  labelStart + "const CATEGORIE_TAK_LABEL = ".length,
  APP.indexOf("\n};", labelStart) + 2) + ")");
const CATEGORIE_TAK_VOLGORDE = eval(
  APP.match(/const CATEGORIE_TAK_VOLGORDE = (\[[^\]]*\])/)[1]);

const prefixRegel = APP.match(/const NON_CLOTHING_PREFIXES = (\{[^;]*\});/);
const NON_CLOTHING_PREFIXES = eval("(" + prefixRegel[1] + ")");

function itemTypeForCategory(category) {
  const cat = String(category || "").trim().toLowerCase();
  for (const [prefix, type] of Object.entries(NON_CLOTHING_PREFIXES)) {
    if (cat.startsWith(prefix)) return type;
  }
  return "clothing";
}

// De <option>-waarden van #f-item-type, letterlijk uit het scherm.
const typeBlok = APP.slice(APP.indexOf('<select id="f-item-type"'),
                           APP.indexOf("</select>", APP.indexOf('<select id="f-item-type"')));
const ITEM_TYPES = [...typeBlok.matchAll(/<option value="([^"]+)"/g)].map(m => m[1]);
const KLEDING = ["dames", "heren", "kinderen", "unisex"];

ok("audio staat in de item-type keuzelijst", ITEM_TYPES.includes("audio"),
   `keuzelijst is nu: ${ITEM_TYPES.join(", ")}`);

const groepenZonderOptie = Object.keys(CATEGORIES)
  .filter(k => !KLEDING.includes(k) && !ITEM_TYPES.includes(k));
ok("elke CATEGORIES-groep heeft een item-type", groepenZonderOptie.length === 0,
   `zonder optie: ${groepenZonderOptie.join(", ")}`);

const heenTerug = [];
for (const [groep, lijst] of Object.entries(CATEGORIES)) {
  const verwacht = KLEDING.includes(groep) ? "clothing" : groep;
  for (const [waarde] of lijst) {
    if (itemTypeForCategory(waarde) !== verwacht) heenTerug.push(`${waarde} → ${itemTypeForCategory(waarde)}`);
  }
}
ok("elke categorie levert zijn eigen item-type weer op", heenTerug.length === 0,
   `${heenTerug.length} fout, bv. ${heenTerug.slice(0, 3).join(" | ")}`);

// Dit is het gedrag dat Budgetheld zag: een audiocategorie opslaan en het
// scherm zet de verkoper terug op kleding.
ok('"audio luidsprekers" opent niet meer als Clothing & Shoes',
   itemTypeForCategory("audio luidsprekers") === "audio");
ok('"electronics telefoon samsung" blijft Electronics',
   itemTypeForCategory("electronics telefoon samsung") === "electronics");
ok("een gewone kledingcategorie blijft kleding",
   itemTypeForCategory("dames jassen") === "clothing");

// ── 2. Onbekende categorie wordt niet stilletjes weggegooid ─────────────────
console.log("\nEen categorie die wij niet kennen blijft staan");

const opties = [];
const nepSelect = {
  set innerHTML(_) { opties.length = 0; },
  get options() { return opties; },
  appendChild(o) { opties.push(o); },
};
const document = {
  getElementById: (id) => (id === "f-category" ? nepSelect
    : id === "f-item-type" ? { value: _itemType }
    : id === "f-gender" ? { value: _gender } : null),
  createElement: () => ({ value: "", textContent: "", selected: false }),
};
let _itemType = "clothing", _gender = "";

function functieUit(naam) {
  const start = APP.indexOf(`function ${naam}(`);
  const eind = APP.indexOf("\n}\n", start);
  return APP.slice(start, eind + 2);
}
eval(functieUit("currentItemType") + functieUit("_bewaarOnbekendeCategorie") + functieUit("updateCategoryOptions"));

_itemType = "audio"; _gender = "";
updateCategoryOptions("audio luidsprekers");
ok("een bekende audiocategorie wordt geselecteerd",
   opties.some(o => o.value === "audio luidsprekers" && o.selected));

_itemType = "clothing"; _gender = "dames";
updateCategoryOptions("iets wat wij niet kennen");
ok("een onbekende categorie blijft bewaard en geselecteerd",
   opties.some(o => o.value === "iets wat wij niet kennen" && o.selected),
   "de categorie van de verkoper werd weggegooid");

_itemType = "clothing"; _gender = "";
updateCategoryOptions("dames jassen");
ok("ook zonder gekozen doelgroep blijft de opgeslagen categorie staan",
   opties.some(o => o.value === "dames jassen" && o.selected));

// ── 2b. Zonder doelgroep is de keuzelijst geen doodlopende straat ───────────
// De Juiste Toon (07-09-2026): kleden, vachten, tapijten en kussens waren niet
// te kiezen omdat de lijst om een doelgroep vroeg en verder alleen kleding gaf.
console.log("\nZonder doelgroep staat de hele taxonomie in de lijst");

_itemType = "clothing"; _gender = "";
updateCategoryOptions();
ok("elke tak heeft een leesbare naam",
   Object.keys(CATEGORIES).every(k => CATEGORIE_TAK_LABEL[k]),
   `zonder naam: ${Object.keys(CATEGORIES).filter(k => !CATEGORIE_TAK_LABEL[k]).join(", ")}`);
const alleWaarden = opties.map(o => o.value);
const alleCategorieen = Object.values(CATEGORIES).flat().map(([v]) => v);
ok("alle rubrieken staan erin, niet alleen kleding",
   alleCategorieen.every(v => alleWaarden.includes(v)),
   `${alleCategorieen.filter(v => !alleWaarden.includes(v)).length} ontbreken`);
ok("woontextiel is bereikbaar zonder eerst een doelgroep te kiezen",
   ["wonen tapijten en kleden", "wonen vachten", "wonen kussens"]
     .every(v => alleWaarden.includes(v)));
ok("de tak staat voor de rubriek zodat de lijst leesbaar blijft",
   opties.some(o => o.value === "wonen tapijten en kleden"
                 && o.textContent.startsWith("Home & garden · ")),
   opties.find(o => o.value === "wonen tapijten en kleden")?.textContent);
ok("kleding staat vooraan",
   CATEGORIE_TAK_VOLGORDE.every(k => Object.keys(CATEGORIES).includes(k))
     && alleWaarden.indexOf(CATEGORIES.dames[0][0]) < alleWaarden.indexOf(CATEGORIES.wonen[0][0]));
ok("de oude doodlopende keuzelijst is weg",
   !APP.includes(">— choose gender first —<"));
ok("een rubriek uit een andere tak trekt het soort mee",
   /function onCategoryPicked\(\)/.test(APP)
   && /onchange="onCategoryPicked\(\)"/.test(APP));

// En dat ook echt uitvoeren: een vloerkleed kiezen terwijl het soort nog op
// kleding staat, en kijken of het scherm zichzelf goed zet.
const velden = { "fg-gender": {}, "fg-size": {}, "fg-material": {} };
for (const v of Object.values(velden)) v.style = { display: "" };
const waarden = { "f-gender": "", "f-size": "", "f-material": "", "f-category": "" };
const opties2 = [];
const nepSelect2 = {
  set innerHTML(_) { opties2.length = 0; },
  get options() { return opties2; },
  appendChild(o) { opties2.push(o); },
  get value() { return waarden["f-category"]; },
  set value(v) { waarden["f-category"] = v; },
};
const document2 = {
  getElementById: (id) => (id === "f-category" ? nepSelect2
    : id === "f-item-type" ? { get value() { return _itemType; }, set value(v) { _itemType = v; } }
    : velden[id] ? velden[id]
    : id in waarden ? { get value() { return waarden[id]; }, set value(v) { waarden[id] = v; } }
    : null),
  createElement: () => ({ value: "", textContent: "", selected: false }),
};
(function () {
  const document = document2;                       // schaduwt de stub hierboven
  const onContextInputForEbay = () => {};
  eval(functieUit("currentItemType") + functieUit("_bewaarOnbekendeCategorie")
       + functieUit("updateCategoryOptions") + functieUit("onItemTypeChange")
       + functieUit("onCategoryPicked"));
  _itemType = "clothing"; waarden["f-gender"] = "";
  waarden["f-category"] = "wonen tapijten en kleden";
  onCategoryPicked();
  ok("een vloerkleed zet het soort op Home, Garden & Christmas", _itemType === "wonen",
     `soort is nu ${_itemType}`);
  ok("doelgroep, maat en materiaal verdwijnen daarbij",
     velden["fg-gender"].style.display === "none" && velden["fg-size"].style.display === "none");
  ok("en de gekozen rubriek blijft geselecteerd staan",
     opties2.some(o => o.value === "wonen tapijten en kleden" && o.selected));

  _itemType = "clothing"; waarden["f-gender"] = "";
  waarden["f-category"] = "heren jassen";
  onCategoryPicked();
  ok("een herenjas vult de doelgroep zelf in", waarden["f-gender"] === "heren",
     `doelgroep is nu ${waarden["f-gender"]}`);
  ok("en blijft geselecteerd", opties2.some(o => o.value === "heren jassen" && o.selected));
})();

// ── 3. Extensie-detectie geeft niet op na één poging ────────────────────────
console.log("\nExtensie-detectie blijft het proberen");

ok("er is een schema met meerdere pogingen", /EXT_PING_SCHEMA_MS = \[[^\]]*,[^\]]*\]/.test(APP));
const schema = eval(APP.match(/const EXT_PING_SCHEMA_MS = (\[[^\]]*\])/)[1]);
ok("minstens vier pogingen", schema.length >= 4, `nu ${schema.length}`);
const totaal = schema.reduce((a, b) => a + b, 0);
ok("samen ruim boven de oude 2,5 seconde", totaal >= 6000, `${totaal} ms`);
ok("en niet zo lang dat een echte nieuwkomer blijft wachten", totaal <= 15000, `${totaal} ms`);
ok("na 'missing' blijft er een stille controle lopen",
   /setInterval\(\(\) => \{\s*if \(extState\.status === 'ready'\) return;/.test(APP));
ok("opnieuw controleren zet de status terug op 'checking'",
   /if \(extState\.status !== 'ready'\) extState = \{ status: 'checking'/.test(APP));

// ── 4. Vinted meldt niets af als er niet is ingelogd ────────────────────────
console.log("\nVinted: geen groen vinkje zonder inlog");

ok("er is een inlogcontrole tegen Vinted's eigen endpoint",
   /async function vintedIngelogd\(origin\)/.test(BG) && /users\/current/.test(BG));
// Sinds 04-09-2026 kijkt die controle niet meer op één gegokt domein maar zoekt
// hij op waar de verkoper is ingelogd (vintedOriginKlaarzetten). De garantie is
// dezelfde: hij draait vóór het tabblad opengaat, en uitgelogd betekent stoppen.
ok("die wordt vóór het openen van het tabblad gedraaid",
   BG.indexOf("const klaar = await vintedOriginKlaarzetten(job)") <
   BG.indexOf("openWorkerTab(url, (tab) =>"));
ok("uitgelogd = de opdracht mislukt, er gaat geen tabblad open",
   /if \(!klaar\.ok\) \{ await reportError\(job\.id, serverUrl, klaar\.melding\); return; \}/.test(BG)
   && /gevonden === false/.test(BG));
ok("twijfel houdt het werk niet tegen (null gaat door)",
   /return null;\s*\/\/ geen netwerk: laat het werk door/.test(BG));
ok("het invulscript stopt als het plaatsformulier er niet is",
   /if \(!qs\('input\[data-testid="title--input"\]'\)\) \{/.test(VINTED));
ok("die controle staat vóór fillForm",
   VINTED.indexOf('if (!qs(\'input[data-testid="title--input"]\')) {') <
   VINTED.indexOf("await fillForm(item);"));

// ── 5. De audiocategorieën zijn ook echt te publiceren ─────────────────────
// Ze in het scherm zetten heeft geen zin als de rest van de keten ze niet kent.
// Gemeten op 01-09-2026: alle 68 staan compleet in MP_CATEGORIES, ebay.py en
// CAT_HINTS. Deze test bewaakt dat een nieuwe categorie niet half wordt gekoppeld.
console.log("\nElke audiocategorie is over de hele keten bekend");

const MP_START = BG.indexOf("const MP_CATEGORIES");
const MP = eval("(" + BG.slice(BG.indexOf("{", MP_START), BG.indexOf("\n};", MP_START) + 2)
                      .replace(/sizeMap: [A-Z_]+/g, "sizeMap: null") + ")");
const EBAY = fs.readFileSync(path.join(ROOT, "backend", "platforms", "ebay.py"), "utf8");
const audioSleutels = CATEGORIES.audio.map(a => a[0]);

const zonderMp = audioSleutels.filter(k => !MP[k] || MP[k].cat1 == null || MP[k].cat3 == null);
ok("alle audiocategorieën hebben Marktplaats-nummers", zonderMp.length === 0, zonderMp.join(", "));
ok("alle audiocategorieën hebben een eBay-vertaling",
   audioSleutels.every(k => EBAY.includes(`"${k}"`)));
ok("alle audiocategorieën hebben een Vinted-hint",
   audioSleutels.every(k => VINTED.includes(`"${k}"`)));

// ── 6. Alleen een advertentie van de verkoper zelf wordt afgemeld ───────────
// De echte oorzaak van het groene vinkje: de automatische herkenning nam ELK
// advertentie-adres in het werk-tabblad voor "de onze". Uitgelogd stuurt Vinted
// /items/new door naar /member/register/select_type (gemeten: HTTP 200, geen
// formulier), de verkoper gaat klikken, en de eerste advertentie die hij opent
// werd afgemeld als de zijne.
console.log("\nGeen afmelding op andermans advertentie");

ok("er is een eigendomscontrole", /async function bgVintedEigenAdvertentie\(origin, listingId, item\)/.test(BG));
ok("uitgelogd telt als 'niet van hem'",
   /if \(ingelogd === false\) return false;   \/\/ uitgelogd: nooit van hem/.test(BG));
ok("'nog niet in de kast' levert nooit false op (een echte publicatie sneuvelt niet)",
   /if \(!gevonden\) return null;\s*\/\/ nog niet geregistreerd: laat door/.test(BG));
ok("een advertentie van hemzelf maar van het verkeerde artikel wordt tegengehouden",
   /return vintedTitelHoortBij\(gevonden\.title, item\) \? true : false;/.test(BG));
ok("de controle staat vóór de afmelding",
   BG.indexOf("const vanHem = await bgVintedEigenAdvertentie(") <
   BG.indexOf('await finaliseJob(meta.serverUrl, meta.jobId, "complete", {\n    platform_listing_id: listingId'));
ok("bewezen 'niet van hem' houdt de afmelding tegen",
   /if \(vanHem === false\) \{[\s\S]{0,220}?return;/.test(BG));
ok("twijfel (null) laat een echte publicatie gewoon door",
   !/if \(vanHem !== true\)/.test(BG));

console.log(mislukt ? `\n${mislukt} test(s) mislukt\n` : "\nAlles groen\n");
process.exit(mislukt ? 1 : 0);
