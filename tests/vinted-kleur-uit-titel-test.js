/**
 * Vinted-kleur uit de titel (26-09-2026).
 *
 * "New Ruby Necklace with Natural Stones" (item zonder kleur) ging 25-09-2026
 * drie keer terug met "colour (empty — no colour on this item and nothing
 * usable in the title)". De Vinted-lijst kende geen robijn, terwijl shared.js
 * en kleur.py hem al als rood lazen.
 *
 * Draait de ECHTE parseColours uit vinted.js, en dezelfde functie uit de versie
 * van vóór de reparatie (vaste commit, niet HEAD), zodat vaststaat dat de oude
 * code faalt en de nieuwe niet.
 *
 * Draaien: node tests/vinted-kleur-uit-titel-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const OUD = "448c4256";

function laad(bron) {
  const kaart = bron.match(/const COLOUR_MAP = \{[\s\S]*?\n  \};/)[0];
  const functie = bron.match(/function parseColours\(item\) \{[\s\S]*?\n  \}\n/)[0];
  const ctx = {};
  vm.runInNewContext(`${kaart}\n${functie}\nthis.parseColours = parseColours;`, ctx);
  return ctx.parseColours;
}

const nieuw = laad(fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8"));
const oud = laad(execSync(`git show ${OUD}:extension/content/vinted.js`, { cwd: WORTEL }).toString());

let mislukt = 0;
function check(naam, ok) { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}`); if (!ok) mislukt++; }

const GEVALLEN = [
  ["New Ruby Necklace with Natural Stones", ["Red"]],
  ["New Ruby Necklace with Natural Gemstones", ["Red"]],
  ["Nieuwe Robijn Ketting met Natuurlijke Steentjes", ["Red"]],
];
for (const [titel, verwacht] of GEVALLEN) {
  check(`nieuw: "${titel}" -> ${verwacht}`, JSON.stringify(nieuw({ title: titel, color: null })) === JSON.stringify(verwacht));
  check(`oud faalde: "${titel}"`, oud({ title: titel, color: null }).length === 0);
}
// Een kleur die wél bij het item staat blijft winnen.
check("eigen kleur gaat voor", !nieuw({ title: "Ruby Necklace", color: "zilver" }).includes("Red"));
// "Natural" alleen levert niets op: geen verzonnen kleur.
check("natural alleen blijft leeg", nieuw({ title: "Natural Stone Bracelet", color: null }).length === 0);

if (mislukt) { console.log(`${mislukt} mislukt`); process.exit(1); }
console.log("alles goed");
