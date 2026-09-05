/**
 * Lynn (De Juiste Toon), 05-09-2026: "ik heb dus de meest recente advertenties
 * dubbel geimporteerd, kan ik de dubbele gewoon delisten of verdwijnt die
 * advertentie dan van vinted ook?"
 *
 * Nee. Beide rijen wijzen naar precies dezelfde advertentie, dus Delist haalt
 * de echte advertentie weg. De waarschuwing daarover bestond al, maar pas op
 * het moment dat er iets weg zou gaan. In de lijst zelf was niets te zien.
 *
 * Deze test draait de ECHTE sharedAdvertBadge uit app.html.
 *
 * Draaien: node tests/dubbele-advertentie-merkje-op-de-rij-test.js
 *          node tests/... --oud     (tegen de vorige commit; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const oud = process.argv.includes("--oud");
const html = oud
  ? execSync("git show HEAD:frontend/app.html", { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "frontend/app.html"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function pakFunctie(bron, naam) {
  const start = bron.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  let diepte = 0, i = bron.indexOf("{", start);
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diepte++;
    else if (bron[i] === "}") { diepte--; if (!diepte) break; }
  }
  return bron.slice(start, i + 1);
}

// Twee artikelrijen, een dubbele import: allebei dezelfde Vinted-advertentie.
// Het derde artikel heeft een eigen advertentie en hoort schoon te blijven.
const listings = [
  { item_id: "a", platform: "vinted", platform_listing_id: "111", status: "active" },
  { item_id: "b", platform: "vinted", platform_listing_id: "111", status: "active" },
  { item_id: "c", platform: "vinted", platform_listing_id: "222", status: "active" },
];
const items = [
  { id: "a", title: "Foulard plaid zeilschepen" },
  { id: "b", title: "Foulard plaid zeilschepen" },
  { id: "c", title: "Wollen deken" },
];

const zand = {
  state: { listings, items },
  PLATFORM_LABELS: { vinted: "Vinted" },
  esc: (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"),
  console,
};
vm.createContext(zand);

let ontbreekt = null;
try {
  for (const naam of ["advertIndex", "sharedAdverts", "sharedAdvertBadge"]) {
    vm.runInContext(pakFunctie(html, naam), zand);
  }
} catch (e) { ontbreekt = e.message; }

check("sharedAdvertBadge bestaat", !ontbreekt, ontbreekt);

if (!ontbreekt) {
  const idx = vm.runInContext("advertIndex()", zand);
  zand.__idx = idx;
  const merkA = vm.runInContext("sharedAdvertBadge(state.items[0], __idx)", zand);
  const merkC = vm.runInContext("sharedAdvertBadge(state.items[2], __idx)", zand);

  check("de dubbel geimporteerde rij krijgt een merkje", /shared advert/i.test(merkA), JSON.stringify(merkA));
  check("het merkje noemt het kanaal", /Vinted/.test(merkA));
  check("het merkje wijst Delete aan als de veilige knop", /Delete/.test(merkA));
  check("het merkje waarschuwt voor Delist", /Delist/i.test(merkA));
  check("een gewone rij krijgt geen merkje", merkC === "", JSON.stringify(merkC));
}

// De rij zelf moet het merkje ook echt tonen: een functie die niemand aanroept
// verandert niets op het scherm.
const tabel = pakFunctie(html, "renderItemsTable");
check("renderItemsTable bouwt de index een keer op", /advertIndex\(\)/.test(tabel));
check("renderItemsTable zet het merkje in de rij", /\$\{sharedBadge\}/.test(tabel));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
