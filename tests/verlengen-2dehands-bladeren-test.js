/**
 * Verlengen op 2dehands bij een verkoper met meer dan 200 zoekertjes.
 *
 * 28-09-2026: klant 96e30080 (625 actieve zoekertjes op 2dehands) kreeg 40 keer
 * "Listing m… is not in your 2dehands overview (200 listings read)" voor
 * zoekertjes die gewoon live stonden (openbare pagina 200). bgExtend2dh las
 * alleen batch 1 van het overzicht, 200 stuks, en bladerde nooit verder.
 *
 * Het nagebootste overzicht hieronder gedraagt zich zoals de echte API:
 * batchNumber is 1-based, batchSize wordt gehonoreerd tot 200, en
 * totalNumberOfResults geeft het totaal.
 *
 * Draaien:  node tests/verlengen-2dehands-bladeren-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "19e90b78";

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

const overNdagen = (n) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + n); return d.toISOString(); };

function maakZand(bron, ads) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    Date, URL, JSON, setTimeout: (f) => setTimeout(f, 0),
    finalise: [], fouten: [], opgevraagd: [],
  };
  const db = JSON.parse(JSON.stringify(ads));
  zand.fetch = async (url) => {
    const u = new URL(String(url), "https://www.2dehands.be");
    if (u.pathname === "/my-account/sell/api/listings") {
      const nr = Math.max(1, Number(u.searchParams.get("batchNumber") || 1));
      const grootte = Math.min(200, Number(u.searchParams.get("batchSize") || 50));
      zand.opgevraagd.push(nr);
      const stuk = db.slice((nr - 1) * grootte, nr * grootte);
      return { ok: true, status: 200,
               json: async () => JSON.parse(JSON.stringify({ ads: stuk, totalNumberOfResults: db.length })) };
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => "" };
  };
  zand.document = {
    querySelector(sel) {
      const m = sel.match(/data-ad-id="([^"]+)"/);
      const ad = m && db.find((a) => a.itemId === m[1]);
      if (!ad || ad.status !== "EXPIRING") return null;
      return { scrollIntoView() {}, click() {
        const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28);
        ad.closeDate = d.toISOString(); ad.status = "ACTIVE";
      } };
    },
    querySelectorAll() { return []; },
  };
  zand.openWorkerTab = (_u, cb) => cb({ id: 7 });
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.sluitWerkTabblad = () => {};
  zand.execInTab = async (_t, fn, args = []) => fn(...args);
  zand.finaliseJob = async (_s, _i, kind, body) => { zand.finalise.push({ kind, body }); };
  zand.reportError = async (_i, _s, msg) => { zand.fouten.push(String(msg)); };
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "bgExtend2dh"), zand);
  return zand;
}

async function draai(bron, ads, itemId) {
  const zand = maakZand(bron, ads);
  const job = { id: "j", platform: "2dehands", action: "extend", payload: { platform_listing_id: itemId } };
  try { await zand.bgExtend2dh(job, "https://omnivaleur.com"); }
  catch (e) { zand.fouten.push(String(e && e.message || e)); }
  return zand;
}

(async () => {
  // 625 zoekertjes, zoals bij de klant; het te verlengen zoekertje staat op plek 450.
  const ads = [];
  for (let i = 0; i < 625; i++) {
    ads.push({ itemId: `m24${String(10000000 + i)}`, status: "ACTIVE", closeDate: overNdagen(20), reserved: false });
  }
  const doel = ads[450].itemId;
  ads[450].status = "EXPIRING"; ads[450].closeDate = overNdagen(3);

  console.log(`Oude versie (${OUDE_COMMIT}) bij 625 zoekertjes`);
  const OUD = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const oud = await draai(OUD, ads, doel);
  check("de oude versie vindt het zoekertje niet (de fout van de klant)",
    /is not in your 2dehands overview \(200 listings read\)/.test(oud.fouten[0] || ""), oud.fouten[0]);

  console.log("\nNieuwe versie bij 625 zoekertjes");
  const NIEUW = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");
  const nieuw = await draai(NIEUW, ads, doel);
  check("geen fout", nieuw.fouten.length === 0, nieuw.fouten.join(" | "));
  const klaar = nieuw.finalise.find((f) => f.kind === "complete");
  check("verlengd met bewijs (~28 dagen)",
    klaar && klaar.body.verlengd === true && klaar.body.shift_days >= 27 && klaar.body.shift_days <= 29,
    JSON.stringify(klaar && klaar.body));
  check("bladerde verder dan de eerste bladzijde", Math.max(...nieuw.opgevraagd) >= 5,
    nieuw.opgevraagd.join(","));

  console.log("\nNieuwe versie: zoekertje echt weg, 625 gelezen");
  const weg = await draai(NIEUW, ads, "m2499999999");
  check("fout noemt alle 625 gelezen zoekertjes",
    /\(625 listings read\)/.test(weg.fouten[0] || ""), weg.fouten[0]);
  check("niets als klaar gemeld", !weg.finalise.some((f) => f.kind === "complete"));

  console.log("\nNieuwe versie: kleine verkoper, één bladzijde");
  const klein = ads.slice(0, 30).map((a) => ({ ...a }));
  klein[5].status = "EXPIRING"; klein[5].closeDate = overNdagen(2);
  const k = await draai(NIEUW, klein, klein[5].itemId);
  check("verlengd", k.finalise.some((f) => f.kind === "complete" && f.body.verlengd === true), k.fouten.join(" | "));

  console.log(mislukt === 0 ? "\nAlles groen." : `\n${mislukt} controle(s) mislukt.`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
