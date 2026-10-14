/**
 * Janneke, 14-10-2026: elke Vinted-plaatsing stopte met "Vul je staat in om
 * verder te gaan". CONDITION_MAP geeft de ENGELSE naam ("New without tags"),
 * haar Vinted staat in het Nederlands ("Nieuw zonder prijskaartje"). De oude
 * woordvergelijking vond niets en de stap meldde toch "ok".
 *
 * Deze proef draait de ECHTE fillAttributeVinted (nu en van vóór de reparatie)
 * tegen een nagebouwd staatlijstje: Nederlands, Duits, Engels, en een
 * onbekende taal (dan telt de vaste volgorde van de vijf staten).
 * Draaien: node tests/vinted-staat-in-elke-taal-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, ok, uitleg) {
  if (ok) { console.log(`  ok   ${naam}`); return; }
  mislukt++; console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function functieUit(bron, naam) {
  const begin = bron.indexOf(`async function ${naam}(`);
  if (begin < 0) throw new Error(naam + " niet gevonden");
  let i = bron.indexOf("{", begin), diepte = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diepte++;
    else if (bron[i] === "}" && --diepte === 0) break;
  }
  return bron.slice(begin, i + 1);
}

// Een staatveld met vijf opties. Klik op het rondje zet de naam in het veld.
function wereld(namen) {
  const veld = { value: "", offsetParent: {}, scrollIntoView() {}, matches: () => false };
  const titels = namen.map((naam) => {
    const rondje = { click() { veld.value = naam; } };
    const cel = { querySelector: () => rondje };
    return { textContent: naam, offsetParent: {}, closest: () => cel };
  });
  const document = {
    querySelector: (sel) => (sel.includes("category-condition-single-list-input") ? veld : null),
    querySelectorAll: (sel) => (sel.includes("Cell__title") ? titels : []),
    dispatchEvent() {},
  };
  const zand = {
    document, veld, console: { log() {}, warn() {} }, KeyboardEvent: function () {},
    waitUntil: async (f) => { f(); return true; }, sleep: async () => {}, realClickEl() {},
    qs: () => null, fillInput() {}, openDropdownVinted: async () => false,
  };
  vm.createContext(zand);
  return zand;
}

async function kies(bron, namen, waarde) {
  const zand = wereld(namen);
  vm.runInContext(functieUit(bron, "fillAttributeVinted"), zand);
  const ok = await zand.fillAttributeVinted(["condition", "status"], waarde);
  return { ok, gekozen: zand.veld.value };
}

const NL = ["Nieuw met prijskaartje", "Nieuw zonder prijskaartje", "Heel goed", "Goed", "Redelijk"];
const DE = ["Neu, mit Etikett", "Neu, ohne Etikett", "Sehr gut", "Gut", "Zufriedenstellend"];
const EN = ["New with tags", "New without tags", "Very good", "Good", "Satisfactory"];
const ONBEKEND = ["Nuovo con cartellino", "Nuovo senza cartellino", "Ottime", "Buone", "Discrete"];

(async () => {
  const nu = fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8");
  const oud = execSync("git show b86a6fb5:extension/content/vinted.js", { cwd: WORTEL, maxBuffer: 1 << 26 }).toString();

  console.log("VOOR de reparatie");
  const o = await kies(oud, NL, "New without tags");
  check("Nederlands Vinted: de oude code kiest geen staat", o.gekozen === "", JSON.stringify(o));

  console.log("\nNA de reparatie");
  for (const [taal, namen] of [["Nederlands", NL], ["Duits", DE], ["Engels", EN], ["onbekende taal", ONBEKEND]]) {
    for (const [i, waarde] of EN.entries()) {
      const r = await kies(nu, namen, waarde);
      check(`${taal}: ${waarde} → ${namen[i]}`, r.ok === true && r.gekozen === namen[i], JSON.stringify(r));
    }
  }
  // "Goed" mag nooit bij "Heel goed" terechtkomen en andersom.
  const g = await kies(nu, NL, "Good");
  check("Good kiest Goed, niet Heel goed", g.gekozen === "Goed", g.gekozen);

  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
  process.exit(mislukt ? 1 : 0);
})();
