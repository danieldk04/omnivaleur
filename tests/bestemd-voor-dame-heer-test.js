/**
 * Vagif (sieraden), 29-09-2026: twee ringen op 2dehands geweigerd met "These
 * fields were left empty on the form: intended for". Kettingen, armbanden en
 * oorbellen gingen dezelfde middag wel online.
 *
 * Ringen hebben op Marktplaats en 2dehands een "Bestemd voor"-lijst met "Dame",
 * "Heer" en "Dame of Heer" (gemeten 29-09-2026 in de zoekfilters van beide
 * sites, l1 1826 / l2 22). selectIntendedFor kende alleen jongen/meisje en
 * instrumenten, liet het veld leeg, en verifyMpGroupFields hield het plaatsen
 * terecht tegen.
 *
 * Deze test draait de ECHTE code uit shared.js, nu en van vóór de reparatie.
 * Draaien: node tests/bestemd-voor-dame-heer-test.js
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

// Een formulier met één label "Bestemd voor" dat naar één <select> wijst.
function laadCL(bron, opties) {
  const select = {
    tagName: "SELECT", _v: "",
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

function kies(bron, opties, item) {
  const { CL, select } = laadCL(bron, opties);
  CL.selectIntendedFor(item);
  return select._v;
}

const RING = ["Dame", "Heer", "Dame of Heer"];
const VAGIF = [
  { title: "Zilveren ring met turkoois en zilver 925, maat 25", category: "sieraden ringen", color: "zilveren" },
  { title: "Zilveren ring met turkoois en marcasiet maat 19,5", category: "sieraden ringen", color: "zilveren" },
];

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
const bronOud = execSync("git show 1fc27664:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

console.log("VOOR de reparatie (1.0.360)");
const oud = VAGIF.map((it) => kies(bronOud, RING, it));
check("de oude code liet het veld aantoonbaar leeg bij Vagifs ringen", oud.every((v) => v === ""),
  `gekozen: ${oud.join(", ")}`);

console.log("\nNA de reparatie");
for (const it of VAGIF) {
  check(`"${it.title}" -> Dame of Heer`, kies(bronNu, RING, it) === "Dame of Heer");
}
for (const [item, verwacht] of [
  [{ title: "Herenring zilver 925", category: "sieraden ringen" }, "Heer"],
  [{ title: "Zegelring heren", category: "sieraden ringen" }, "Heer"],
  [{ title: "Damesring met parel", category: "sieraden ringen" }, "Dame"],
  [{ title: "Ring", category: "sieraden ringen", gender: "women" }, "Dame"],
  [{ title: "Ring", category: "sieraden ringen", gender: "men" }, "Heer"],
  [{ title: "Ring voor dames en heren", category: "sieraden ringen" }, "Dame of Heer"],
]) {
  check(`"${item.title}"${item.gender ? ` (${item.gender})` : ""} -> ${verwacht}`,
    kies(bronNu, RING, item) === verwacht, `kreeg: ${kies(bronNu, RING, item)}`);
}

console.log("\nBestaande lijsten ongewijzigd");
check("kinderkleding: Jongen of Meisje", kies(bronNu, ["Jongen", "Meisje", "Jongen of Meisje"],
  { title: "Jurkje", category: "kinderkleding" }) === "Jongen of Meisje");
check("muziek: Elektrische gitaar", kies(bronNu, ["Akoestische gitaar", "Elektrische gitaar", "Overige instrumenten"],
  { title: "Fender elektrische gitaar", category: "muziek" }) === "Elektrische gitaar");

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
