/**
 * Egbert Brouwer (Papa's Plectrums), 13-09-2026: "Als ik even van de computer
 * wegloop stopt het plaatsen vrij snel daarna, en het gaat pas weer verder als
 * ik opnieuw inlog."
 *
 * Nagemeten in zijn eigen opdrachten: werk tot 08:05:58, daarna niets tot
 * 09:21:53, en precies op dat tijdstip meldde zich een opdracht klaar die om
 * 07:40:43 was begonnen. Een bevroren tabblad dat anderhalf uur later meteen
 * afmaakt is Windows dat slaapt, niet een tijdslimiet van ons.
 *
 * De reparatie: zolang de server opdrachten klaar heeft staan die NU aan de
 * beurt zijn, vraagt de extensie Chrome om de machine wakker te houden, en
 * zodra de rij leeg is laat ze dat weer los.
 *
 * Deze proef draait de echte pollJobsEenRonde uit background.js in een
 * nagebouwde Chrome.
 *
 * Draaien: node tests/wakker-houden-test.js
 *          node tests/wakker-houden-test.js --oud   (vóór de reparatie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "a0b631cb";
const oud = process.argv.includes("--oud");
const BRON = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Een nagebouwde Chrome: alles wat background.js bij het laden aanroept mag
// bestaan en niets doen. Wat we echt willen meten (power) houdt zijn eigen
// boekhouding bij.
function bouwChrome(power) {
  const opslag = () => {
    const d = {};
    return {
      // Chrome kent twee vormen: get(sleutels) met een belofte terug, en
      // get(standaarden, callback). background.js gebruikt ze allebei.
      get: (k, terug) => {
        let uit = {};
        if (k == null) uit = { ...d };
        else if (Array.isArray(k) || typeof k === "string") {
          for (const s of (Array.isArray(k) ? k : [k])) if (s in d) uit[s] = d[s];
        } else {
          uit = { ...k };
          for (const s of Object.keys(k)) if (s in d) uit[s] = d[s];
        }
        if (typeof terug === "function") { terug(uit); return; }
        return Promise.resolve(uit);
      },
      set: (o, terug) => {
        Object.assign(d, o);
        if (typeof terug === "function") { terug(); return; }
        return Promise.resolve();
      },
      remove: (k, terug) => {
        for (const s of (Array.isArray(k) ? k : [k])) delete d[s];
        if (typeof terug === "function") { terug(); return; }
        return Promise.resolve();
      },
      clear: async () => { for (const s of Object.keys(d)) delete d[s]; },
      _ruw: d,
    };
  };
  const luisteraar = { addListener() {}, removeListener() {}, hasListener() { return false; } };
  const niets = () => new Proxy(function () {}, {
    get: (doel, sleutel) => {
      if (sleutel === "addListener" || sleutel === "removeListener") return () => {};
      if (sleutel === "then") return undefined;
      if (!(sleutel in doel)) doel[sleutel] = niets();
      return doel[sleutel];
    },
    apply: () => Promise.resolve(),
  });
  return {
    storage: { local: opslag(), session: opslag(), sync: opslag(), onChanged: luisteraar },
    alarms: { create() {}, clear() {}, clearAll() {}, get: async () => null, onAlarm: luisteraar },
    runtime: {
      onInstalled: luisteraar, onMessage: luisteraar, onStartup: luisteraar,
      onConnect: luisteraar, onSuspend: luisteraar, onUpdateAvailable: luisteraar,
      getManifest: () => ({ version: "test" }), getURL: (p) => `chrome-extension://test/${p}`,
      lastError: null, id: "test", sendMessage: async () => {},
    },
    power: {
      requestKeepAwake(niveau) { power.aan.push(niveau); },
      releaseKeepAwake() { power.uit++; },
    },
    idle: { queryState: async () => "active", onStateChanged: luisteraar },
    action: niets(), tabs: niets(), windows: niets(), scripting: niets(),
    notifications: niets(), cookies: niets(), debugger: niets(),
    permissions: niets(), webRequest: niets(), downloads: niets(), management: niets(),
  };
}

async function ronde(jobsPerPlatform) {
  const power = { aan: [], uit: 0 };
  const gevraagd = [];
  const sandbox = {
    chrome: bouwChrome(power),
    console: process.argv.includes("--praat") ? console : { log() {}, warn() {}, error() {}, info() {}, debug() {} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    URL, URLSearchParams, TextEncoder, TextDecoder, Blob, FormData, AbortController,
    Date, Math, JSON, Promise, fetch: async (url) => {
      gevraagd.push(String(url));
      const m = String(url).match(/\/api\/jobs\/pending\?platform=([a-z]+)/);
      if (m) return { ok: true, status: 200, json: async () => jobsPerPlatform[m[1]] || [] };
      return { ok: true, status: 200, json: async () => ({}), text: async () => "" };
    },
    btoa: (s) => Buffer.from(s, "binary").toString("base64"),
    atob: (s) => Buffer.from(s, "base64").toString("binary"),
    crypto: { randomUUID: () => "00000000-0000-4000-8000-000000000000", getRandomValues: (a) => a },
    structuredClone: (o) => JSON.parse(JSON.stringify(o)),
    importScripts: () => {},   // analytics.js hoort niet bij deze proef
  };
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(BRON, sandbox, { filename: "background.js" });

  // Het echte publiceren doet hier niet mee: we meten alleen of de machine
  // wakker gehouden wordt zolang er werk klaarstaat.
  sandbox.processJob = async () => {};
  const verzet = await Promise.race([
    sandbox.pollJobsEenRonde(),
    new Promise((_, f) => setTimeout(() => f(new Error("pollJobsEenRonde kwam niet terug binnen 20s")), 20000)),
  ]);
  return { power, verzet, gevraagd };
}

(async () => {
  console.log(oud ? "VÓÓR de reparatie (moet falen)" : "Na de reparatie");

  console.log("\nEr staat werk klaar dat nu aan de beurt is:");
  const werk = await ronde({ marktplaats: [{ id: "j1", action: "create", platform: "marktplaats" }] });
  check("de machine wordt wakker gehouden", werk.power.aan.length > 0,
        "chrome.power.requestKeepAwake is niet aangeroepen");
  check("alleen de machine, niet het scherm", werk.power.aan.every((n) => n === "system"),
        `niveau was ${JSON.stringify(werk.power.aan)}`);
  check("de rij is echt uitgevraagd", werk.gevraagd.some((u) => u.includes("/api/jobs/pending")));

  console.log("\nDe rij is leeg:");
  const leeg = await ronde({});
  check("de machine mag weer gaan slapen", leeg.power.uit > 0,
        "chrome.power.releaseKeepAwake is niet aangeroepen");
  check("en wordt niet onnodig wakker gehouden", leeg.power.aan.length === 0,
        `requestKeepAwake werd toch aangeroepen: ${JSON.stringify(leeg.power.aan)}`);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})().catch((e) => { console.error("proef zelf stukgelopen:", e); process.exit(2); });
