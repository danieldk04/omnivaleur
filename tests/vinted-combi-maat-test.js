/**
 * ((269) Blue Ralph Lauren Cardigan, 23-09-2026 — een samengestelde maat matcht nooit.
 *
 * Item.size stond in de database als "S / 36 / 8" (letter/EU/UK, uit de import).
 * Op het Vinted-formulier bleef "Select a size" staan met "Fill in size to
 * continue" eronder: de maat werd nooit gekozen. Van deze klant staan 61 van
 * zijn items met precies zo'n samengestelde maat.
 *
 * Oorzaak, aangetoond met de echte code uit extension/content/vinted.js: de
 * zoeker bouwt een `wants`-set van "hoe deze maat op Vinted zou kunnen heten".
 * Bij een simpele maat als "s" werkt dat, maar bij "s / 36 / 8" bleef de HELE
 * string in `wants` staan — die is nooit gelijk aan een los Vinted-label als
 * "S". De code splitste wél het Vinted-label zelf op "/" (voor het geval
 * Vinted een combi-label toont), maar nooit onze eigen waarde. Dus zelfs een
 * simpele losse "S"-tegel op Vinted werd nooit gevonden.
 *
 * Deze test draait de ECHTE matchfunctie uit vinted.js, geknipt op tekst, twee
 * keer: de versie in de map (moet slagen) en de versie van vóór de reparatie
 * uit git (moet FALEN, ter bevestiging dat dit de storing verklaart).
 *
 * Draaien: node tests/vinted-combi-maat-test.js
 *          node tests/vinted-combi-maat-test.js --oud   (moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "d6debad0";
const oud = process.argv.includes("--oud");
const BRON = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/vinted.js`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Het exacte stuk uit vinted.js dat de maat kiest, tussen deze twee regels.
const START = "      // Everything this size could reasonably be called on Vinted:";
const EIND = "      if (!match && /^\\d+$/.test(norm)) {";
const start = BRON.indexOf(START);
const eind = BRON.indexOf(EIND);
if (start === -1 || eind === -1) {
  console.log("FOUT — kon het maat-matchblok niet vinden in vinted.js (markers verschoven?)");
  process.exit(1);
}
const blok = BRON.slice(start, eind);

// Vinted's echte cardigan-maten (dames): losse letters, geen combi-label.
const VINTED_CARDIGAN_MATEN = ["XS", "S", "M", "L", "XL", "XXL"];

function maakOptie(tekst) {
  return { textContent: tekst };
}

function vindMatch(value, optieTeksten) {
  const opts = optieTeksten.map(maakOptie);
  const lv = value.toLowerCase();
  const sandbox = { opts, lv, value, console: { log() {}, warn() {} }, RegExp, Set };
  vm.createContext(sandbox);
  // `sizeOptEls` en `label`/`match` leven al in het blok zelf; wij hoeven alleen
  // `opts` en `lv` aan te bieden en te lezen wat er na afloop in `match` staat.
  const script = `
    ${blok}
    __resultaat__ = match ? match.textContent : null;
  `;
  vm.runInContext(script, sandbox);
  return sandbox.__resultaat__;
}

console.log(oud ? "OUDE code (vóór de reparatie):" : "NIEUWE code:");

check(
  "combi-maat \"S / 36 / 8\" vindt de losse tegel \"S\"",
  vindMatch("S / 36 / 8", VINTED_CARDIGAN_MATEN) === "S",
);
check(
  "combi-maat \"M / 38 / 10\" vindt de losse tegel \"M\"",
  vindMatch("M / 38 / 10", VINTED_CARDIGAN_MATEN) === "M",
);
check(
  "een gewone maat \"S\" blijft gewoon werken",
  vindMatch("S", VINTED_CARDIGAN_MATEN) === "S",
);

console.log(mislukt === 0 ? "\nAlles gaat goed." : `\n${mislukt} controle(s) mislukt.`);
process.exit(mislukt === 0 ? 0 : 1);
