/**
 * Janneke, 12-10-2026: "in marktplaats staat overal bestemd voor jongen bij.
 * Ook bij de meidenjassen."
 *
 * Gemeten op haar echte advertenties: babyjassen zonder jongen of meisje in de
 * tekst stonden online als "Jongetje". Het babyformulier van Marktplaats
 * (/plaats/565/573) heeft de opties "Jongetje", "Meisje" en "Jongetje of
 * Meisje", en zet zelf al "Jongetje" klaar. selectIntendedFor zocht letterlijk
 * "Jongen of Meisje", vond niets, en liet de voorselectie staan.
 *
 * Deze test draait de ECHTE code uit shared.js, nu en van vóór de reparatie.
 * Draaien: node tests/bestemd-voor-baby-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Een formulier met één label "Bestemd voor" dat naar één <select> wijst, met
// de voorselectie die Marktplaats zelf zet.
function laadCL(bron, opties, voorgekozen) {
  const select = {
    tagName: "SELECT", _v: voorgekozen || "",
    options: [{ value: "", text: "Kies...", disabled: false }]
      .concat(opties.map((t) => ({ value: t, text: t, disabled: false }))),
    dispatchEvent() { return true; },
  };
  const label = {
    childNodes: [{ nodeType: 3, textContent: "Bestemd voor" }],
    textContent: "Bestemd voor", children: [],
    querySelector: () => null,
    getAttribute: (k) => (k === "for" ? "bestemd" : null),
  };
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout, clearTimeout, Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false },
    querySelectorAll: (q) => (q.startsWith("label") ? [label] : q.includes("singleSelectAttribute") ? [select] : []),
    querySelector: () => null,
    getElementById: (id) => (id === "bestemd" ? select : null),
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  zand.HTMLSelectElement = function () {};
  Object.defineProperty(zand.HTMLSelectElement.prototype, "value", {
    configurable: true,
    get() { return this._v || ""; },
    set(v) { this._v = v; },
  });
  vm.createContext(zand);
  vm.runInContext(bron, zand, { filename: "shared.js" });
  return { CL: zand.window.CL, select };
}

function kies(bron, opties, item, voorgekozen) {
  const { CL, select } = laadCL(bron, opties, voorgekozen);
  CL.selectIntendedFor(item);
  return select._v;
}

const BABY = ["Jongetje", "Meisje", "Jongetje of Meisje"];
const KIND = ["Jongen", "Meisje", "Jongen of Meisje"];
// Echte artikelen van Janneke (31d28378), titel en rubriek uit de database.
const BABYJAS = { title: "Jas Babyface maat 80*", category: "babykleding", description: "Nieuw met labels." };

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
const bronOud = execSync("git show 418249e8:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

console.log("VOOR de reparatie");
check("de oude code liet 'Jongetje' staan bij een babyjas zonder geslacht",
  kies(bronOud, BABY, BABYJAS, "Jongetje") === "Jongetje");

console.log("\nNA de reparatie");
check("babyjas zonder geslacht -> Jongetje of Meisje",
  kies(bronNu, BABY, BABYJAS, "Jongetje") === "Jongetje of Meisje", `kreeg: ${kies(bronNu, BABY, BABYJAS, "Jongetje")}`);
check("babyjas 'meisje' -> Meisje",
  kies(bronNu, BABY, { title: "Jasje meisje maat 74", category: "babykleding" }, "Jongetje") === "Meisje");
check("babyjas 'jongetje' -> Jongetje",
  kies(bronNu, BABY, { title: "Jasje jongetje maat 74", category: "babykleding" }, "Jongetje") === "Jongetje");
check("babyjas 'jongens' -> Jongetje",
  kies(bronNu, BABY, { title: "Jas", category: "jongens kleding" }, "Jongetje") === "Jongetje");

console.log("\nKinderkleding ongewijzigd");
check("kind zonder geslacht -> Jongen of Meisje", kies(bronNu, KIND, { title: "Jas Dirkje maat 110", category: "peuterkleding" }) === "Jongen of Meisje");
check("kind meisjes kleding -> Meisje", kies(bronNu, KIND, { title: "Winterjas Noppies maat 128", category: "meisjes kleding" }) === "Meisje");
check("kind jongens kleding -> Jongen", kies(bronNu, KIND, { title: "Tussenjas Name it maat 128", category: "jongens kleding" }) === "Jongen");

// Janneke 18-10-2026: het geslacht komt uit haar Shopify-label en staat in de
// rubriek. Een omschrijving die beide noemt mag dat niet terugdraaien.
console.log("\nRubriek met geslacht beslist (18-10-2026)");
const BEIDE = { title: "Jasje maat 74", category: "babykleding meisjes", description: "Leuk voor jongens en meisjes." };
const bronVoor = execSync("git show 735ee620:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();
check("voor: omschrijving met beide gaf 'Jongetje of Meisje'", kies(bronVoor, BABY, BEIDE, "Jongetje") === "Jongetje of Meisje");
check("na: babykleding meisjes -> Meisje", kies(bronNu, BABY, BEIDE, "Jongetje") === "Meisje");
check("na: peuterkleding jongens -> Jongen", kies(bronNu, KIND, { title: "Trui maat 92", category: "peuterkleding jongens", description: "voor meisjes en jongens" }) === "Jongen");

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
