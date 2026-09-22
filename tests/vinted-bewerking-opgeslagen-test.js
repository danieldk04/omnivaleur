/**
 * Een Vinted-prijswijziging die gewoon doorging mag geen "timed out" worden.
 *
 * Aanleiding (22-09-2026, klant d25f18a2, extensie 1.0.345). Negen
 * content_refresh-opdrachten met een nieuwe prijs eindigden alle negen als
 * "Extension timed out ... no response after 3 minutes", laatste stap "prijs
 * gezet via de pagina zelf". Op de openbare Vinted-pagina stonden daarna alle
 * negen nieuwe prijzen (18,00 / 17,99 / 8,99 / 11,99), terwijl de scan van
 * 21-09 15:30 nog de oude (20 / 13 / 10) liet zien. De opslag lukte dus; de
 * opslagklik stuurde het tabblad weg en het invulscript stierf voor JOB_DONE.
 * De achtergrond negeerde elke adreswissel van een content_refresh.
 *
 * Draaien:  node tests/vinted-bewerking-opgeslagen-test.js
 *           node tests/vinted-bewerking-opgeslagen-test.js --oud   (hoort te falen)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

// Vast commit-nummer, geen HEAD (zie kennisbank: voor-en-na-proef-mag-geen-head-gebruiken).
const VOOR = "0714b412";
const OUD = process.argv.includes("--oud");
const lees = (f) => OUD
  ? execSync(`git show ${VOOR}:${f}`, { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", f), "utf8");
const BG = lees("extension/background.js");
const VT = lees("extension/content/vinted.js");

const a = BG.indexOf("// ── Auto-detect manual publish");
const s = BG.indexOf("chrome.tabs.onUpdated.addListener(", a);
const e = BG.indexOf("\n});\n", s) + 4;
const bron = BG.slice(s, e);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

async function ronde(meta, url) {
  let luisteraar;
  const afgemeld = [];
  const opslag = { "jobtab_7": meta };
  const ctx = {
    console: { log() {}, warn() {} },
    URL,
    chrome: {
      tabs: { onUpdated: { addListener: (f) => { luisteraar = f; } } },
      storage: { local: {
        get: async (k) => ({ [k]: opslag[k] }),
        remove: async (ks) => { for (const k of [].concat(ks)) delete opslag[k]; },
      } },
    },
    MP_LOGINPAGINA: /\/identity\/v2\/login/, MP_BETAALPAGINA: /\/payments\//,
    SITE_NAAM: {}, betaalmuurRaaktDezeOpdracht: () => false,
    clearJobWatchdog() {}, sluitWerkTabblad() {},
    finaliseJob: async (_s, id, kind, body) => { afgemeld.push({ id, kind, body }); return true; },
    bgVintedEigenAdvertentie: async () => true,
    bgVindVintedAdvertentie: async () => null,
  };
  vm.createContext(ctx);
  vm.runInContext(bron, ctx);
  await luisteraar(7, { url });
  return afgemeld;
}

const basis = { jobId: "j1", serverUrl: "s", platform: "vinted", action: "content_refresh",
  payload: { platform_listing_id: "9310934248", platform_listing_url: "https://www.vinted.nl/items/9310934248" } };

(async () => {
  console.log(OUD ? `Oude code (${VOOR}):` : "Nieuwe code:");
  let r = await ronde({ ...basis, submitClicked: true }, "https://www.vinted.nl/items/9310934248-polo-ralph-lauren-rood");
  ok("na Opslaan op de eigen advertentie geland → afgemeld als gelukt", r.length === 1 && r[0].kind === "complete", r);
  r = await ronde({ ...basis, submitClicked: true }, "https://www.vinted.nl/items/9310934248");
  ok("ook op het kale adres zonder naam", r.length === 1 && r[0].kind === "complete", r);
  r = await ronde({ ...basis }, "https://www.vinted.nl/items/9310934248-polo");
  ok("zonder klik op Opslaan niets afmelden", r.length === 0, r);
  r = await ronde({ ...basis, submitClicked: true }, "https://www.vinted.nl/items/9310934248/edit");
  ok("het bewerkformulier zelf telt niet", r.length === 0, r);
  r = await ronde({ ...basis, submitClicked: true }, "https://www.vinted.nl/items/1111111111-iets-anders");
  ok("een andere advertentie telt niet", r.length === 0, r);

  const f = VT.slice(VT.indexOf("async function refreshListingVinted("));
  const klik = f.indexOf("saveBtn.click()");
  const vlag = f.lastIndexOf('type: "SUBMIT_CLICKED"', klik);
  ok("invulscript meldt de klik op Opslaan vóór het klikken", vlag > 0 && vlag < klik);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles groen");
  process.exit(mislukt ? 1 : 0);
})();
