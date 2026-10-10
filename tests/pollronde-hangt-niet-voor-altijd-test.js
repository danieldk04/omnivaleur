/**
 * Janneke, 10-10-2026: "Er is een wachtrij, maar gebeurt niks." Haar extensie
 * (1.0.376) had zich 19 uur niet gemeld terwijl Chrome openstond. De hartslag
 * komt alleen uit pollJobs; bleef één await in een ronde hangen, dan stond
 * _pollLoopt voor altijd op true en deed elke volgende tik niets.
 *
 * Deze proef draait de echte pollJobs uit background.js met een ronde die nooit
 * terugkomt, zet de klok zes minuten vooruit en kijkt of er dan weer gevraagd
 * wordt. Op de code van vóór de reparatie (1.0.377) faalt de tweede check.
 *
 * Draaien: node tests/pollronde-hangt-niet-voor-altijd-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

function stuk(begin, eind) {
  const i = BG.indexOf(begin);
  if (i < 0) throw new Error(`${begin} niet gevonden`);
  return BG.slice(i, BG.indexOf(eind, i) + eind.length);
}

const bron = [
  stuk("let _pollLoopt = false;", "const _lopendeScans = new Set();"),
  stuk("async function pollJobs() {", "\n}\n"),
  "return { pollJobs };",
].join("\n");

let nu = 1_000_000;
let vragen = 0;
let eersteHangt = true;
const nepDate = { now: () => nu };
const fn = new Function("Date", "reconcileOrphanJobTabs", "pollJobsEenRonde", "console", bron);
const { pollJobs } = fn(nepDate, async () => {}, () => {
  vragen++;
  if (eersteHangt) { eersteHangt = false; return new Promise(() => {}); }  // komt nooit terug
  return Promise.resolve(false);
}, { warn() {}, log() {}, error() {} });

let mislukt = 0;
function check(naam, ok) { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}`); if (!ok) mislukt++; }

(async () => {
  pollJobs();                       // deze ronde blijft hangen
  await new Promise(r => setImmediate(r));
  await pollJobs();                 // meteen erna: moet nog wachten
  check("een ronde die net loopt wordt niet ingehaald", vragen === 1);
  nu += 6 * 60 * 1000;              // zes minuten later
  await pollJobs();
  check("na zes minuten hangen vraagt de extensie weer om werk (hartslag)", vragen === 2);
  await pollJobs();
  check("en daarna gewoon elke tik", vragen === 3);
  process.exit(mislukt ? 1 : 0);
})();
