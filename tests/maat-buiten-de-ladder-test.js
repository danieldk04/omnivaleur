/**
 * De Juiste Toon, 12-09-2026 — een maat die onder of boven de lijst valt.
 *
 * Zijn advertentie "Lederhosen dames bruin roze" strandde met: These fields
 * were left empty on the form: size. "XXS / 32 / 4" staat niet in de lijst bij
 * size — die biedt: Maat 34 (XS) of kleiner, Maat 36 (S), Maat 38/40 (M),
 * Maat 42/44 (L), Maat 46/48 (XL) of groter.
 *
 * Die vijf regels zijn de echte lijst van Marktplaats, letterlijk uit zijn eigen
 * foutmelding overgenomen, niet verzonnen. Zijn maat stond gewoon ingevuld; hij
 * viel alleen onder de kleinste keuze. En de kleinste keuze heet nota bene "of
 * kleiner", dus het goede antwoord stond er al.
 *
 * Geteld in zijn opdrachten sinds 25-08-2026: 17 publicaties die op een maat
 * buiten de ladder strandden (XXS onderaan, XXL / XXXL / 4XL bovenaan).
 *
 * Draaien: node tests/maat-buiten-de-ladder-test.js
 *          node tests/... --oud   (tegen de commit van vóór de reparatie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "3db24936";
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

// De echte lijst uit zijn foutmelding van 12-09-2026, 18:18 UTC.
const MP_DAMES = ["Maat 34 (XS) of kleiner", "Maat 36 (S)", "Maat 38/40 (M)",
                  "Maat 42/44 (L)", "Maat 46/48 (XL) of groter"];
// Een lijst zonder uitersten: hier hoort de extensie NIETS te kiezen.
const ZONDER_UITERSTEN = ["Maat 36", "Maat 38", "Maat 40", "Maat 42"];

function maakSelect(opties) {
  const options = [{ value: "", text: "Kies...", disabled: false }]
    .concat(opties.map((t) => ({ value: t, text: t, disabled: false })));
  return { tagName: "SELECT", value: "", options, dispatchEvent() { return true; } };
}

function laadCL(bron) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout, clearTimeout, Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false },
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
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
  return zand.window.CL;
}

const CL = laadCL(BRON);

/** Wat komt er in het maatveld te staan? Zoals repairOnce het doet. */
function vulMaat(maat, opties) {
  const el = maakSelect(opties);
  const proxy = new Proxy(el, {
    get(t, k) { return k === "value" ? (t._v || "") : t[k]; },
    set(t, k, v) { if (k === "value") t._v = v; else t[k] = v; return true; },
  });
  CL.kiesMetTerugval(proxy, "Maat", maat);
  return el._v || "";
}

console.log("Marktplaats-maatlijst (dames):", MP_DAMES.join(" | "), "\n");

check('XXS / 32 / 4 komt bij "of kleiner" uit',
      vulMaat("XXS / 32 / 4", MP_DAMES) === "Maat 34 (XS) of kleiner",
      `gekozen: "${vulMaat("XXS / 32 / 4", MP_DAMES)}"`);

check('XXL komt bij "of groter" uit',
      vulMaat("XXL", MP_DAMES) === "Maat 46/48 (XL) of groter",
      `gekozen: "${vulMaat("XXL", MP_DAMES)}"`);

check('4XL komt ook bij "of groter" uit',
      vulMaat("4XL", MP_DAMES) === "Maat 46/48 (XL) of groter",
      `gekozen: "${vulMaat("4XL", MP_DAMES)}"`);

check("een maat die er gewoon in staat verandert niet",
      vulMaat("S / 36 / 8", MP_DAMES) === "Maat 36 (S)",
      `gekozen: "${vulMaat("S / 36 / 8", MP_DAMES)}"`);

check("M / 38 / 10 blijft op de M-regel",
      vulMaat("M / 38 / 10", MP_DAMES) === "Maat 38/40 (M)",
      `gekozen: "${vulMaat("M / 38 / 10", MP_DAMES)}"`);

check("zonder 'of kleiner' en 'of groter' wordt er niets gegokt",
      vulMaat("XXS / 32 / 4", ZONDER_UITERSTEN) === "",
      `gekozen: "${vulMaat("XXS / 32 / 4", ZONDER_UITERSTEN)}"`);

check("een maat middenin een lijst zonder uitersten blijft gewoon werken",
      vulMaat("M / 38 / 10", ZONDER_UITERSTEN) === "Maat 38",
      `gekozen: "${vulMaat("M / 38 / 10", ZONDER_UITERSTEN)}"`);

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
