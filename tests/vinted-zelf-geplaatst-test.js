/**
 * De bewaker draait hier ECHT, met een nagebootste chrome.storage/alarms.
 *
 * Daniel, 05-09-2026: hij plaatste (1071) met de hand af op Vinted en het
 * kaartje bleef "Publishing now…" zeggen. De controle "heeft hij het zelf
 * gedaan?" bestond wél, maar hing aan een eenmalige wekker die na de overdracht
 * nooit opnieuw werd gezet. Er ging dus nooit meer iemand kijken.
 *
 * Draaien:  node tests/vinted-zelf-geplaatst-test.js
 *           node tests/vinted-zelf-geplaatst-test.js --oud   (vorige commit)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const stuk = (naam) => {
  const start = BG.indexOf(`async function ${naam}(`) >= 0
    ? BG.indexOf(`async function ${naam}(`) : BG.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let i = BG.indexOf("{", BG.indexOf(")", start)), diep = 0;
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diep++;
    else if (BG[i] === "}") { diep--; if (diep === 0) return BG.slice(start, i + 1); }
  }
  throw new Error(`${naam} loopt niet af`);
};

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — " + JSON.stringify(extra) : ""}`);
};

// Eén keer de bewaker laten afgaan, met een opgeslagen opdracht.
async function bewaker({ meta, gevonden }) {
  const opslag = { jobtab_7: meta };
  const wekkers = {};
  const gemeld = [];
  const chrome = {
    storage: { local: {
      get: async (k) => ({ [k]: opslag[k] }),
      set: async (o) => Object.assign(opslag, o),
      remove: async (k) => { delete opslag[k]; },
    } },
    alarms: {
      create: (naam, opties) => { wekkers[naam] = opties; },
      clear: (naam) => { delete wekkers[naam]; },
    },
  };
  const omgeving = {
    chrome,
    console: { log() {}, warn() {}, error() {} },
    JOB_TAB_TIMEOUT_MIN: 3,
    JOB_WATCHDOG_PREFIX: "jobwd_",
    bgVindVintedAdvertentie: async () => gevonden,
    finaliseJob: async (_s, id, status, extra) => { gemeld.push({ id, status, extra }); },
    reportError: async () => {},
    meldNooitBegonnen: async () => {},
    sluitWerkTabblad: () => {},
  };
  const extra = BG.includes("function armManueleControle(")
    ? "const MANUELE_CONTROLE_MIN = 2, MANUELE_CONTROLES_MAX = 15;\n" + stuk("armManueleControle") + "\n"
    : "";
  const fn = new Function(...Object.keys(omgeving),
    `${extra}${stuk("fireJobWatchdog")}; return fireJobWatchdog;`)(...Object.values(omgeving));
  await fn(7);
  return { opslag, wekkers, gemeld };
}

const KLAAR = { platform: "vinted", action: "create", jobId: "j1", serverUrl: "https://s",
                awaitingManualFinish: true, payload: { title: "(1071) Light Blue Massimo Dutti Turtleneck" } };
const NET_MISLUKT = { platform: "vinted", action: "create", jobId: "j1", serverUrl: "https://s",
                      scriptSeen: true, payload: { title: "(1071) Light Blue Massimo Dutti Turtleneck" } };
const GEVONDEN = { id: "9999", url: "https://www.vinted.nl/items/9999" };

(async () => {
  console.log("\nHeeft de verkoper het zelf afgemaakt?");

  let r = await bewaker({ meta: NET_MISLUKT, gevonden: null });
  ok("na de overdracht gaat er een herhaalwekker lopen",
     !!r.wekkers.jobwd_7 && r.wekkers.jobwd_7.periodInMinutes > 0, r.wekkers);
  ok("de opdracht blijft staan om zelf af te maken",
     r.opslag.jobtab_7?.awaitingManualFinish === true, r.opslag);

  r = await bewaker({ meta: KLAAR, gevonden: GEVONDEN });
  ok("zelf geplaatst -> alsnog als geplaatst afgemeld",
     r.gemeld[0]?.status === "complete" && r.gemeld[0]?.extra?.platform_listing_id === "9999", r.gemeld);
  ok("en de wekker stopt", !r.wekkers.jobwd_7 && !r.opslag.jobtab_7, { w: r.wekkers, o: r.opslag });

  r = await bewaker({ meta: KLAAR, gevonden: null });
  ok("nog niets gevonden -> gewoon blijven kijken",
     r.gemeld.length === 0 && r.opslag.jobtab_7?.manueleControles === 1, r.opslag);

  r = await bewaker({ meta: { ...KLAAR, manueleControles: 14 }, gevonden: null });
  ok("na een half uur houdt het op", !r.wekkers.jobwd_7, r.wekkers);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
