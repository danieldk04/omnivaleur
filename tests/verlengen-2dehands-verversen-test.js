/**
 * 2dehands verlengen terwijl het overzicht onder ons ververst.
 *
 * 04-10-2026, klant bcdf9aa4 (2.437 zoekertjes): zijn computer werd wakker,
 * een verlengopdracht meldde "Error: Frame with ID 0 was removed." en een
 * andere "Couldn't read your 2dehands listings overview (Failed to fetch)".
 * Chrome breekt executeScript af zodra het tabblad ververst; de oude code gaf
 * dan meteen op, ook als de klik op "Verlengen" al gelukt was.
 *
 * Draaien:  node tests/verlengen-2dehands-verversen-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "9a363988";
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

// storing: "na-klik"  = klik werkt, daarna ververst de pagina (frame weg)
//          "voor-klik" = pagina ververst tijdens het lezen, nog niets geklikt
//          "fetch"     = eerste lezing geeft Failed to fetch (net wakker)
function maakZand(bron, ads, storing) {
  const db = JSON.parse(JSON.stringify(ads));
  let storingen = 1, fetchStoring = storing === "fetch" ? 1 : 0;
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    Date, URL, JSON, setTimeout: (f) => setTimeout(f, 0),
    finalise: [], fouten: [],
  };
  zand.fetch = async (url) => {
    if (String(url).includes("/my-account/sell/api/listings")) {
      if (fetchStoring) { fetchStoring--; throw new TypeError("Failed to fetch"); }
      return { ok: true, status: 200, json: async () => ({ ads: JSON.parse(JSON.stringify(db)) }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };
  zand.document = {
    querySelector(sel) {
      const m = sel.match(/data-ad-id="([^"]+)"/);
      const ad = m && db.find((a) => a.itemId === m[1]);
      if (!ad || ad.status !== "EXPIRING") return null;
      return { scrollIntoView() {}, click() {
        const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28);
        ad.closeDate = d.toISOString(); ad.status = "ACTIVE";
        if (storing === "na-klik" && storingen) { storingen--; throw new Error("__frame__"); }
      } };
    },
    querySelectorAll() { return []; },
  };
  zand.openWorkerTab = (url, cb) => cb({ id: 7 });
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.zetWerkStatus = async () => {};
  zand.wachtendAantal = () => 0;
  zand.sluitWerkTabblad = () => {};
  zand.stuurWerkTabbladNaar = async () => {};
  zand.execInTab = async (_t, fn, args = []) => {
    if (storing === "voor-klik" && storingen) { storingen--; throw new Error("Frame with ID 0 was removed."); }
    try { return await fn(...args); }
    catch (e) { if (e.message === "__frame__") throw new Error("Frame with ID 0 was removed."); throw e; }
  };
  zand.finaliseJob = async (_s, _i, kind, body) => { zand.finalise.push({ kind, body }); };
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "bgExtend2dh"), zand);
  return zand;
}

async function draai(bron, ads, storing) {
  const zand = maakZand(bron, ads, storing);
  try {
    await zand.bgExtend2dh({ id: "j", platform: "2dehands", action: "extend",
      payload: { platform_listing_id: "m2441357963" } }, "https://omnivaleur.com");
  } catch (e) { zand.fouten.push(String(e.message || e)); }
  return zand;
}

async function proef(naam, bron) {
  console.log(`\n${naam}`);
  const ads = [{ itemId: "m2441357963", status: "EXPIRING", closeDate: overNdagen(4), reserved: false }];
  for (const [storing, label] of [
    ["na-klik", "pagina ververst vlak na de klik"],
    ["voor-klik", "pagina ververst tijdens het lezen"],
    ["fetch", "eerste lezing Failed to fetch"],
  ]) {
    const z = await draai(bron, ads, storing);
    const klaar = z.finalise.find((f) => f.kind === "complete");
    check(`${label}: als verlengd gemeld, geen fout`,
      !z.fouten.length && klaar && klaar.body.verlengd === true && klaar.body.new_close,
      z.fouten.join(" | ") || JSON.stringify(z.finalise));
  }
  // Wat niet mag veranderen: een zoekertje dat nog niet in het venster zit
  // (20 dagen te gaan) wordt nooit als verlengd gemeld.
  const z = await draai(bron, [{ itemId: "m2441357963", status: "ACTIVE", closeDate: overNdagen(20) }], null);
  const k = z.finalise.find((f) => f.kind === "complete");
  check("20 dagen te gaan: niet in het venster, niet verlengd",
    k && !k.body.verlengd && k.body.note === "not_in_extend_window", JSON.stringify(z.finalise));
}

(async () => {
  const nieuw = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");
  const oud = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const voor = mislukt;
  await proef(`OUDE versie (${OUDE_COMMIT}), hoort te falen`, oud);
  const oudFaalt = mislukt > voor;
  mislukt = voor;
  console.log(oudFaalt ? "  (oude versie faalt zoals verwacht)" : "  LET OP: oude versie faalt niet");
  if (!oudFaalt) mislukt++;
  await proef("NIEUWE versie", nieuw);
  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
