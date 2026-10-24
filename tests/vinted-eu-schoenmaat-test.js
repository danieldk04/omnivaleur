/**
 * Kinderschoenen op Vinted: maat "EU 25" in plaats van "25" (23-10-2026).
 *
 * Sinds ~19:40 UTC op 23-10 faalde elke Vinted-plaatsing in "kinderen schoenen"
 * met "Vul je maat in om verder te gaan" (31d28378 twaalf keer, 45f9caba twee
 * keer); om 19:11 lukte hetzelfde artikel in maat 25 nog. Gemeten op
 * vinted.nl/items/new (24-10, Kinderen > Meisjeskleding > Schoenen > Laarsjes >
 * Enkellaarzen): het maatveld heet nu category-size-single-grid_chips-input en
 * de tegels lezen "EU 15", "EU 15,5" … "EU 40" (size-group-93). Onze maat "25"
 * stond nooit gelijk aan "eu 25", dus werd er niets aangeklikt.
 *
 * Draait het ECHTE matchblok uit vinted.js, zoals vinted-combi-maat-test.js.
 * Draaien: node tests/vinted-eu-schoenmaat-test.js
 *          node tests/vinted-eu-schoenmaat-test.js --voor   (moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "1e701f6e";
const voor = process.argv.includes("--voor");
const BRON = voor
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/vinted.js`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde) {
  console.log(`  ${voorwaarde ? "ok  " : "FOUT"} ${naam}`);
  if (!voorwaarde) mislukt++;
}

const START = "      // Everything this size could reasonably be called on Vinted:";
const EIND = "      if (!match && /^\\d+$/.test(norm)) {";
const start = BRON.indexOf(START);
const eind = BRON.indexOf(EIND);
if (start === -1 || eind === -1) {
  console.log("FOUT: kon het maat-matchblok niet vinden in vinted.js");
  process.exit(1);
}
const blok = BRON.slice(start, eind);

// Precies de tegels van het formulier op 24-10-2026.
const EU_KINDERSCHOEN = [];
for (let m = 15; m <= 40; m++) {
  EU_KINDERSCHOEN.push(`EU ${m}`);
  if (m < 40) EU_KINDERSCHOEN.push(`EU ${m},5`);
}

function vindMatch(value, teksten) {
  const sandbox = { opts: teksten.map((t) => ({ textContent: t })), lv: value.toLowerCase(), value,
    console: { log() {}, warn() {} }, RegExp, Set };
  vm.createContext(sandbox);
  vm.runInContext(`${blok}\n__r__ = match ? match.textContent : null;`, sandbox);
  return sandbox.__r__;
}

console.log(voor ? "Code van vóór de reparatie:" : "Huidige code:");
check('maat "25" kiest "EU 25"', vindMatch("25", EU_KINDERSCHOEN) === "EU 25");
check('maat "20" kiest "EU 20", niet "EU 20,5"', vindMatch("20", EU_KINDERSCHOEN) === "EU 20");
check('maat "25.5" kiest "EU 25,5"', vindMatch("25.5", EU_KINDERSCHOEN) === "EU 25,5");
check('maat "37" kiest "EU 37"', vindMatch("37", EU_KINDERSCHOEN) === "EU 37");
// Wat al werkte moet blijven werken.
check('oude labels: "25" kiest "25"', vindMatch("25", ["24", "25", "26"]) === "25");
check('letters: "M" kiest "M"', vindMatch("M", ["S", "M", "L"]) === "M");
check('geen verzonnen maat: "41" vindt niets', vindMatch("41", EU_KINDERSCHOEN) === null);

console.log(mislukt ? `${mislukt} fout` : "alles goed");
process.exit(mislukt ? 1 : 0);
