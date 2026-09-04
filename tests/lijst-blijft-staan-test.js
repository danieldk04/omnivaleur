/**
 * Toon (dejuistetoon), 02-09-2026:
 *   "kan niet naar volgende pagina scrollen. Springt elke keer terug naar
 *    pagina 1. Ook bij advertenties die ik invoer daarna springt hij wederom
 *    naar 1ste artikel. Regelmatig valt het beeldscherm totaal weg."
 *
 * Eén oorzaak onder alle drie. De achtergrondronde in loadAll() draait elke
 * vijftien seconden (en nog eens zodra het tabblad naar voren komt) en riep
 * applyFilters() aan zónder argument. Die zet de lijst dan terug op bladzijde 1.
 * Bij 1.024 artikelen zijn dat 21 bladzijden, dus wie verder bladerde had steeds
 * vijftien seconden voordat hij weer bovenaan stond.
 *
 * Dezelfde ronde bouwde ook elke keer de hele tabel opnieuw op, inclusief vijftig
 * foto's van gemiddeld 450 kB (gemeten aan Toons eigen artikelen). Hij werkt op
 * een Chromebook (CrOS x86_64, Chrome 151, afgelezen aan zijn eigen verbinding);
 * daar loopt het geheugen op leeg en zet Chrome het tabblad weg — een leeg scherm.
 *
 * Deze test draait de échte renderItemsTable uit app.html.
 *
 * Draaien: node tests/lijst-blijft-staan-test.js
 */
const fs = require("fs");
const path = require("path");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(naam) {
  let start = APP.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  const eind = APP.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(start, eind + 2);
}

// ── 1. De bladzijde blijft staan bij een achtergrondronde ────────────────
console.log("De achtergrondronde laat de bladzijde met rust");
const loadAll = APP.slice(APP.indexOf("async function loadAll("));
const staart = loadAll.slice(0, loadAll.indexOf("\n}\n") + 2);
check("loadAll roept applyFilters(false) aan",
  /view-items'\)\.classList\.contains\('active'\)\)\s*applyFilters\(false\)/.test(staart),
  "hij zet de lijst nog steeds terug op bladzijde 1");
check("de oude regel staat er niet meer",
  !/view-items'\)\.classList\.contains\('active'\)\)\s*applyFilters\(\);/.test(staart));
check("bladeren zelf houdt de bladzijde vast",
  /function goToItemsPage\(page\)\s*\{\s*itemsCurrentPage = page;\s*applyFilters\(false\);/.test(APP));
check("alleen een echte keuze van de verkoper zet hem terug op 1",
  /function applyFilters\(resetPage\)\s*\{\s*if \(resetPage !== false\) itemsCurrentPage = 1;/.test(APP));

// ── 2. Niets herbouwen als er niets veranderd is ─────────────────────────
console.log("\nDe tabel wordt alleen opnieuw getekend als er iets veranderd is");

const zand = {
  console: { log() {}, warn() {} },
  schrijfbeurten: 0,
};
zand.window = zand;
let laatsteHtml = "";
const body = {
  set innerHTML(v) { laatsteHtml = v; zand.schrijfbeurten++; },
  get innerHTML() { return laatsteHtml; },
};
zand.document = {
  getElementById: (id) => (id === "items-body" ? body : null),
  querySelectorAll: () => [],
};

// Alles wat renderItemsTable aanroept en wat hier niet ter zake doet.
const stubs = `
  function renderSoldConfirmBar() {}
  function renderDuplicateBar() {}
  function renderPublishErrorBar() {}
  function updateBulkBar() {}
  function publishedAt() { return ""; }
  function smartMissingBadge() { return ""; }
  function publishErrorBadge() { return ""; }
  function renderListingBadges() { return ""; }
  function itemActions() { return ""; }
  function priceCell(i) { return String(i.price); }
  function conditionLabel() { return "Goed"; }
  function fmtDate() { return "1 sep"; }
  function lastHandledAt(i) { return i.handled || 0; }
  function handledBucket() { return ""; }
  function esc(s) { return String(s == null ? "" : s); }
  const selectedIds = new Set();
  const publishingItemIds = new Set();
  const state = { listings: [], items: [], listingsLoaded: true };
  const itemsTab = "live";
  const itemsGroepeerOpDatum = false;
  const EMPTY_TAB = { live: { h: "", p: "" } };
`;

const vm = require("vm");
vm.createContext(zand);
vm.runInContext(stubs + functieUit("itemPhotoThumb") + "\nlet _itemsTabelStempel = null;\n" +
  functieUit("renderItemsTable"), zand, { filename: "app.html" });

const items = [];
for (let n = 1; n <= 50; n++) {
  items.push({ id: "i" + n, title: "Vloerkleed " + n, brand: "Handgemaakt",
               price: 25, condition: "good", created_at: "2026-09-01",
               photo_urls: ["https://img.omnivaleur.com/foto" + n + ".jpg"] });
}

zand.renderItemsTable(items);
const naEerste = zand.schrijfbeurten;
zand.renderItemsTable(items);
zand.renderItemsTable(items);
zand.renderItemsTable(items);
check("de eerste keer wordt de tabel getekend", naEerste === 1, `${naEerste} schrijfbeurten`);
check("drie identieke rondes daarna raken de tabel niet aan",
  zand.schrijfbeurten === 1,
  `${zand.schrijfbeurten} schrijfbeurten in plaats van 1 — de foto's worden dus opnieuw geladen`);

items[7].price = 30;
zand.renderItemsTable(items);
check("een echte wijziging wordt wél getekend", zand.schrijfbeurten === 2,
  `${zand.schrijfbeurten} schrijfbeurten`);

// De voor-proef: zonder de stempel schrijft dezelfde ronde elke keer opnieuw.
const zonderStempel = functieUit("renderItemsTable")
  .replace(/if \(_itemsTabelStempel !== html\) \{[\s\S]*?\n  \}/,
           "document.getElementById('items-body').innerHTML = html;");
const zand2 = Object.assign(Object.create(null), { console: zand.console, schrijfbeurten: 0 });
zand2.window = zand2;
let h2 = "";
zand2.document = { getElementById: () => ({ set innerHTML(v) { h2 = v; zand2.schrijfbeurten++; }, get innerHTML() { return h2; } }), querySelectorAll: () => [] };
vm.createContext(zand2);
vm.runInContext(stubs + functieUit("itemPhotoThumb") + "\nlet _itemsTabelStempel = null;\n" + zonderStempel, zand2, { filename: "oud" });
for (let n = 0; n < 4; n++) zand2.renderItemsTable(items);
check("de oude opzet schreef aantoonbaar elke ronde opnieuw", zand2.schrijfbeurten === 4,
  `${zand2.schrijfbeurten} schrijfbeurten — dan bewijst deze test niets`);

// ── 3. Foto's pas ophalen als ze in beeld komen ──────────────────────────
console.log("\nDe foto's in de lijst");
const thumb = zand.itemPhotoThumb({ photo_urls: ["https://img.omnivaleur.com/x.jpg"] });
check('de miniatuur staat op loading="lazy"', /loading="lazy"/.test(thumb));
check('de miniatuur pakt de foto los uit (decoding="async")', /decoding="async"/.test(thumb));
check("de miniatuur zegt vooraf hoe groot hij wordt", /width="40" height="40"/.test(thumb),
  "zonder maat verspringt de lijst tijdens het laden");

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
