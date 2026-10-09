/**
 * Janneke (31d28378), 09-10-2026 22:39: "Hij blijft deze melding geven. Ik ben
 * wel ingelogd" — bij elke Vinted-plaatsing "You are not signed in to Vinted in
 * this browser, so nothing was published."
 *
 * Twee fouten in de inlogcontrole van de extensie (tot en met 1.0.376):
 *   1. Alleen /api/v2/users/current telde. Dat geeft 401 zodra Vinteds
 *      kortlevende toegangskoekje verlopen is, ook bij iemand die ingelogd is.
 *   2. Een "nee" werd tien minuten onthouden, dus opnieuw inloggen hielp niet.
 * Nu: bij 401 het plaatsformulier zelf als tweede bron, en alleen een "ja"
 * wordt onthouden.
 *
 * Draaien: node tests/vinted-inlog-verlopen-koekje-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function functieUit(bron, naam, woord = "function") {
  const start = bron.indexOf(`${woord} ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n}\n", start);
  return bron.slice(start, eind + 2);
}

console.log("\nHet oordeel uit het tabblad");
const oordeel = new Function("return " + functieUit(BG, "vintedOordeel"))();
const api401 = { status: 401, id: null };
check("API zegt ja: ingelogd", oordeel({ api: { status: 200, id: 7 } }) === true);
check("verlopen koekje (401) maar het formulier opent: ingelogd",
  oordeel({ api: api401, formulier: { status: 200, url: "https://www.vinted.nl/items/new" } }) === true);
check("401 en het formulier stuurt naar registreren: uitgelogd",
  oordeel({ api: api401, formulier: { status: 200, url: "https://www.vinted.nl/member/register/select_type" } }) === false);
check("401 zonder antwoord van het formulier: weet niet (dus niet tegenhouden)",
  oordeel({ api: api401, formulier: null }) === null);
check("onderhoud (500): weet niet", oordeel({ api: { status: 500, id: null },
  formulier: { status: 503, url: "https://www.vinted.nl/items/new" } }) === null);

console.log("\nEen 'nee' wordt niet onthouden");
const bron = functieUit(BG, "vintedEerstepartijOrigin", "async function");
check("geen opgeslagen origin:false meer", !/_vintedEerstepartij\s*=\s*\{\s*origin:\s*false/.test(bron));
check("de bewaarde uitslag telt alleen als er een origin is",
  /_vintedEerstepartij\s*&&\s*_vintedEerstepartij\.origin/.test(bron));

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
