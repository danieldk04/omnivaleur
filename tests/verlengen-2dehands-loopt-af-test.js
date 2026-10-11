/**
 * Elke 2dehands-verlenging neemt de lijst "Loopt af" van 2dehands zelf mee.
 *
 * Lynn (96e30080), 11-10-2026: de server raadde het verlengvenster uit
 * listed_at, en dat is bij een geimporteerd zoekertje de importdatum. Het
 * venster kwam te laat; 4 van 11 oude rijen waren al verlopen en verlengen gaf
 * tien rode fouten. 2dehands weet het precies: /my-account/sell/api/listings
 * met inExpirationWindow=true geeft de zoekertjes met een verlengknop, met hun
 * closeDate. De extensie stuurt die lijst nu mee, plus het echte einde van een
 * zoekertje dat nog niet aan de beurt is.
 *
 * Draaien:  node tests/verlengen-2dehands-loopt-af-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vlak vóór deze reparatie. Nooit HEAD (auto-push-hook, zie de kennisbank).
const OUDE_COMMIT = "3f8a42c5";
const ROOT = path.join(__dirname, "..");

let mislukt = 0;
function check(naam, ok, uitleg) {
  if (ok) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const s = bron.indexOf(`async function ${naam}(`);
  const e = bron.indexOf("\n}\n", s);
  return bron.slice(s, e + 2);
}

const overNdagen = (n) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + n); return d.toISOString(); };

function maakZand(bron, ads) {
  const zand = { console: { log() {}, warn() {}, error() {} }, Date, URL, JSON, setTimeout, finalise: [] };
  zand.window = zand;
  zand.fetch = async (url) => {
    const u = String(url);
    let lijst = ads;
    if (u.includes("inExpirationWindow=true")) lijst = ads.filter((a) => a.status === "EXPIRING");
    const b = Number((/batchNumber=(\d+)/.exec(u) || [])[1] || 1);
    const n = Number((/batchSize=(\d+)/.exec(u) || [])[1] || 100);
    return { ok: true, status: 200, json: async () => ({
      ads: JSON.parse(JSON.stringify(lijst.slice((b - 1) * n, b * n))), totalNumberOfResults: lijst.length }) };
  };
  zand.document = { querySelector: () => null, querySelectorAll: () => [] };
  zand.openWorkerTab = (_u, cb) => cb({ id: 7 });
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.zetWerkStatus = async () => {};
  zand.wachtendAantal = () => 0;
  zand.sluitWerkTabblad = () => {};
  zand.stuurWerkTabbladNaar = async () => {};
  zand.execInTab = async (_t, fn, args = []) => fn(...args);
  zand.finaliseJob = async (_s, _i, kind, body) => { zand.finalise.push({ kind, body }); };
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "bgExtend2dh"), zand);
  return zand;
}

const ADS = [
  { itemId: "m2400000003", status: "ACTIVE", closeDate: overNdagen(15), reserved: false },
  { itemId: "m2229805595", status: "EXPIRING", closeDate: overNdagen(2), reserved: false },
  { itemId: "m2229790810", status: "EXPIRING", closeDate: overNdagen(5), reserved: false },
];

async function draai(bron) {
  const zand = maakZand(bron, ADS);
  await zand.bgExtend2dh({ id: "j1", platform: "2dehands", action: "extend",
    payload: { platform_listing_id: "m2400000003", _listing_row_id: "r1" } }, "https://omnivaleur.com");
  return (zand.finalise.find((f) => f.kind === "complete") || {}).body || {};
}

(async () => {
  const oud = await draai(execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }));
  console.log("Oude versie (" + OUDE_COMMIT + ")");
  check("oud: geen lijst 'Loopt af' mee (dit is de fout)", !oud.aflopend);
  check("oud: geen echt einde mee", !oud.close);

  const nieuw = await draai(fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8"));
  console.log("Nieuwe versie");
  check("nog niet aan de beurt, dus niet verlengd", nieuw.note === "not_in_extend_window", JSON.stringify(nieuw));
  check("het echte einde gaat mee", nieuw.close === ADS[0].closeDate, nieuw.close);
  const ids = (nieuw.aflopend || []).map((a) => a.id).sort();
  check("de aflopende zoekertjes gaan mee, met einddatum",
    JSON.stringify(ids) === JSON.stringify(["m2229790810", "m2229805595"])
      && (nieuw.aflopend || []).every((a) => a.close), JSON.stringify(nieuw.aflopend));

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt.` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
