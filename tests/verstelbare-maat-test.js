/**
 * Vagif (1ba42900), 04-10-2026 — een verstelbare ring hield 2dehands tegen.
 *
 * "These fields were left empty on the form: size. "Aanpasbaar" staat niet in
 * de lijst bij size — die biedt: Kleiner dan 17, 17 tot 18, 18 tot 19, 19 tot
 * 20, 20 of groter." Een verstelbare ring heeft geen ringmaat, en vier van zijn
 * ringen zonder maat gingen in dezelfde rubriek gewoon online: het veld is daar
 * niet verplicht. De eindcontrole moet zo'n ring dus niet tegenhouden, en een
 * echte maat die niet past nog wel.
 *
 * Draaien: node tests/verstelbare-maat-test.js
 *          node tests/verstelbare-maat-test.js --oud   (code van vóór de reparatie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "e2d78cce";
const oud = process.argv.includes("--oud");
const BRON = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// De echte lijst uit zijn foutmelding van 04-10-2026, 17:05 UTC.
const RINGMATEN = ["Kleiner dan 17", "17 tot 18", "18 tot 19", "19 tot 20", "20 of groter"];

function maakSelect(opties) {
  const options = [{ value: "", text: "Kies...", disabled: false }]
    .concat(opties.map((t) => ({ value: t, text: t, disabled: false })));
  return { tagName: "SELECT", value: "", options, dispatchEvent() { return true; } };
}

// Een formulier met alleen het label "Maat" en de keuzelijst erachter.
function laadCL(bron, maatSelect) {
  const label = {
    childNodes: [{ nodeType: 3, textContent: "Maat" }],
    textContent: "Maat", children: [],
    querySelector: () => null,
    getAttribute: (a) => (a === "for" ? "maat" : null),
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
    querySelectorAll: (sel) => (/label/.test(sel) ? [label] : []),
    querySelector: () => null,
    getElementById: (id) => (id === "maat" ? maatSelect : null),
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  zand.HTMLSelectElement = function () {};
  vm.createContext(zand);
  vm.runInContext(bron, zand, { filename: "shared.js" });
  return zand.window.CL;
}

function eindcontrole(maat) {
  const CL = laadCL(BRON, maakSelect(RINGMATEN));
  try { CL.verifyMpGroupFields({ size: maat }); return ""; }
  catch (e) { return e.message; }
}

console.log("2dehands-ringmaten:", RINGMATEN.join(" | "), "\n");

const verstelbaar = eindcontrole("Aanpasbaar");
check('"Aanpasbaar" houdt de ring niet meer tegen', verstelbaar === "", verstelbaar);
check('"Verstelbaar" ook niet', eindcontrole("Verstelbaar") === "");
check("een ring zonder maat ging al door", eindcontrole("") === "");
const echt = eindcontrole("M");
check("een echte maat die niet in de lijst staat houdt hem nog wel tegen",
      /left empty on the form: size/.test(echt), echt || "(niet tegengehouden)");

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
