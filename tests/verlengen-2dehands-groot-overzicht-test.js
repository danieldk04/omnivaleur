/**
 * Het 2dehands-overzicht openklappen bij een verkoper met meer dan 2.050 zoekertjes.
 *
 * 03-10-2026: klant bcdf9aa4 (2.437 actieve zoekertjes op 2dehands) kreeg
 * "Listing m… shows as expiring on 2dehands but the "Verlengen" button could
 * not be found". De API vond het zoekertje wel (die bladert tot 5.000), maar
 * expandMp2dhOverview klikte hooguit 40 keer op "Toon 50 volgende": 50 + 40 x 50
 * = 2.050 rijen op het scherm. De vier mislukte zoekertjes horen bij zijn zes
 * oudste, en de oudste staan onderaan. Geen rij, geen knop.
 *
 * Het nagebootste overzicht toont eerst 50 rijen en 50 meer per klik, en
 * schakelt de knop na elke klik één keer uit terwijl de volgende portie laadt.
 *
 * Draaien:  node tests/verlengen-2dehands-groot-overzicht-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "ec876d31";

const ROOT = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, ok, uitleg) {
  if (ok) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " : " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const s = bron.indexOf(`async function ${naam}(`);
  const e = bron.indexOf("\n}\n", s);
  if (s < 0 || e < 0) throw new Error(`${naam} niet gevonden`);
  return bron.slice(s, e + 2);
}

function maakZand(totaal, { haperen = false } = {}) {
  const pagina = { getoond: Math.min(50, totaal), bezig: false };
  const knop = {
    get textContent() { return "Toon 50 volgende"; },
    get disabled() { return pagina.bezig; },
    click() {
      pagina.getoond = Math.min(totaal, pagina.getoond + 50);
      if (haperen) pagina.bezig = true;
    },
  };
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout: (f) => setTimeout(f, 0),
    pagina,
    document: {
      querySelectorAll(sel) {
        if (sel !== "button") return [];
        if (pagina.getoond >= totaal) return [];
        return [knop];
      },
    },
  };
  zand.execInTab = async (_tab, fn, args = []) => {
    const uit = fn(...args);
    // Na één blik is de portie geladen en is de knop weer klikbaar.
    if (!uit) pagina.bezig = false;
    return uit;
  };
  zand.zetWerkStatus = async () => {};
  vm.createContext(zand);
  return zand;
}

async function draai(bron, totaal, opties) {
  const zand = maakZand(totaal, opties);
  vm.runInContext(functieUit(bron, "expandMp2dhOverview"), zand);
  await vm.runInContext("expandMp2dhOverview(1)", zand);
  return zand.pagina.getoond;
}

async function proef(naam, bron) {
  console.log(`\n${naam}`);
  for (const [totaal, opties, label] of [
    [2437, {}, "2.437 zoekertjes (bcdf9aa4)"],
    [2437, { haperen: true }, "2.437 zoekertjes, knop even uit tijdens laden"],
    [625, {}, "625 zoekertjes (96e30080)"],
    [30, {}, "30 zoekertjes, geen knop"],
  ]) {
    const getoond = await draai(bron, totaal, opties);
    check(`${label}: alle rijen op het scherm`, getoond === totaal, `${getoond} van ${totaal}`);
  }
}

(async () => {
  const nieuw = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");
  let oud = null;
  try {
    oud = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
                       { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  } catch (_) { /* geen git-geschiedenis: alleen de nieuwe versie */ }

  if (oud) {
    const voor = mislukt;
    await proef(`OUDE versie (${OUDE_COMMIT}), hoort te falen`, oud);
    const oudFaalt = mislukt > voor;
    mislukt = voor;
    console.log(oudFaalt ? "  (oude versie faalt zoals verwacht)" : "  LET OP: oude versie faalt niet");
    if (!oudFaalt) mislukt++;
  }
  await proef("NIEUWE versie", nieuw);
  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
