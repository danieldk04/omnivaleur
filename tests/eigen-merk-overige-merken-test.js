/**
 * Goudlief (5aae4954), 07-10-2026: "Crossbodytassen met stippen" met merk
 * "Goudlief" geweigerd op Marktplaats en 2dehands: "These fields were left
 * empty on the form: brand".
 *
 * Bij Tassen > Schoudertassen is Merk een keuzelijst, niet verplicht, met
 * Björn Borg, Esprit, Kipling, Oilily en Overige merken (gemeten 08-10-2026 op
 * marktplaats.nl/plaats/1826/1840?bucketId=201). Een eigen merk staat daar niet
 * in; dan hoort "Overige merken" gekozen te worden in plaats van leeg.
 *
 * Draait de ECHTE fillBrandField uit shared.js, nu en van vóór de reparatie.
 * Draaien: node tests/eigen-merk-overige-merken-test.js
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

function laadCL(bron, opties) {
  const select = {
    tagName: "SELECT", _v: "",
    options: [{ value: "", text: "Kies...", disabled: false }]
      .concat(opties.map((t) => ({ value: t, text: t, disabled: false }))),
    dispatchEvent() { return true; },
  };
  const label = {
    childNodes: [{ nodeType: 3, textContent: "Merk" }],
    textContent: "Merk", children: [],
    querySelector: () => null,
    getAttribute: (k) => (k === "for" ? "singleSelectAttribute[brand]" : null),
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
    getElementById: (id) => (id === "singleSelectAttribute[brand]" ? select : null),
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

async function kies(bron, opties, merk) {
  const { CL, select } = laadCL(bron, opties);
  await CL.fillBrandField(merk);
  return select._v;
}

const TASSEN = ["Björn Borg", "Esprit", "Kipling", "Oilily", "Overige merken"];

(async () => {
  const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
  const bronOud = execSync("git show 7fb1dabb:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

  console.log("VOOR de reparatie (1.0.372)");
  const oud = await kies(bronOud, TASSEN, "Goudlief");
  check("de oude code liet Merk leeg bij Goudlief", oud === "", `gekozen: ${oud}`);

  console.log("\nNA de reparatie");
  check("Goudlief -> Overige merken", (await kies(bronNu, TASSEN, "Goudlief")) === "Overige merken");
  check("Handgemaakt -> Overige merken", (await kies(bronNu, TASSEN, "Handgemaakt")) === "Overige merken");
  check("Kipling blijft Kipling", (await kies(bronNu, TASSEN, "Kipling")) === "Kipling");
  check("Esprit blijft Esprit", (await kies(bronNu, TASSEN, "Esprit")) === "Esprit");
  check("lijst zonder terugval blijft leeg", (await kies(bronNu, ["Kipling", "Esprit"], "Goudlief")) === "");
  check("'Overig' werkt ook", (await kies(bronNu, ["Kipling", "Overig"], "Goudlief")) === "Overig");

  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
  process.exit(mislukt ? 1 : 0);
})();
