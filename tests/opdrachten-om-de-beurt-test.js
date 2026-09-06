/**
 * Komt 2dehands aan de beurt terwijl er een Marktplaats-rij staat?
 *
 * WAAROM DEZE TEST ER IS (05-09-2026, Lynn van De Juiste Toon)
 *
 * "Marktplaats ging vandaag helemaal super, niks op aan te merken. Naar
 * tweedehands pakt ie nog niet." Gemeten in haar eigen opdrachten: op 04-09
 * stond er om 14:08:09 één 2dehands-publicatie klaar, die nooit is opgepakt en
 * om 18:23 met de hand is geannuleerd. In diezelfde vier uur gingen er negen
 * Marktplaats-publicaties wél doorheen (14:09:55, 14:14:30, 14:17:51, 14:25:01,
 * 14:31:32, 14:35:02, 14:42:33, 14:46:02, 14:54:03).
 *
 * De pollronde liep de platforms in een vaste volgorde af met marktplaats
 * altijd voorop, terwijl calm mode één klok heeft voor de hele extensie. Het
 * eerste platform in de rij pakte dus elke vrijgekomen plek.
 *
 * Deze test draait de ECHTE pollronde uit background.js in een gesloten
 * omgeving, met een nagebootste server, calm mode aan en een Marktplaats-rij
 * van twintig opdrachten tegen één voor 2dehands.
 *
 * Draaien:  node tests/opdrachten-om-de-beurt-test.js
 *           node tests/opdrachten-om-de-beurt-test.js --oud   (vorige commit)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const stuk = (naam) => {
  const start = BG.indexOf(`async function ${naam}(`) >= 0
    ? BG.indexOf(`async function ${naam}(`) : BG.indexOf(`function ${naam}(`);
  if (start < 0) return null;
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

const CALM_MS = 5 * 60 * 1000;

// Een nagebootste wachtrij plus de echte pollronde eromheen.
async function draai({ mp, tweedehands, rondes, calm = true }) {
  const wachtrij = [];
  for (let i = 0; i < mp; i++) wachtrij.push({ id: `mp${i}`, platform: "marktplaats", action: "create" });
  for (let i = 0; i < tweedehands; i++) wachtrij.push({ id: `td${i}`, platform: "2dehands", action: "create" });

  const gedaan = [];            // volgorde waarin er echt gepubliceerd is
  let nu = 1_000_000;           // virtuele klok
  const opslag = {};            // chrome.storage.local

  const omgeving = {
    console: { log() {}, error() {}, warn() {} },
    EXTENSION_PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook"],
    SCHRIJVENDE_ACTIES: new Set(["create", "delete", "content_refresh"]),
    MIN_GAP_MS: 0,
    _lopendeScans: new Set(),
    chrome: {
      storage: {
        local: {
          get: async (k) => (k in opslag ? { [k]: opslag[k] } : {}),
          set: async (o) => { Object.assign(opslag, o); },
        },
      },
    },
    getServerUrl: async () => "https://server",
    getAuthHeaders: async () => ({}),
    flushFinaliseQueue: async () => {},
    reportError: async () => {},
    gaEvent: () => {},
    // De server: alleen de openstaande opdrachten van het gevraagde platform.
    fetch: async (url) => {
      const platform = decodeURIComponent(String(url).split("platform=")[1] || "");
      const rij = wachtrij.filter((j) => j.platform === platform && !j.klaar).slice(0, 25);
      return { ok: true, json: async () => rij.map((j) => ({ ...j })) };
    },
    // Publiceren duurt tijd; daarna staat de opdracht af.
    processJob: async (job) => {
      const rij = wachtrij.find((j) => j.id === job.id);
      if (rij) rij.klaar = true;
      gedaan.push(job.platform);
      nu += 30 * 1000;
    },
    // Calm mode: één klok voor de hele extensie, precies als in het echt.
    calmMagNu: async () => (calm ? nu >= (opslag.calmNa || 0) : true),
    calmVolgendeInplannen: async () => { if (calm) opslag.calmNa = nu + CALM_MS; },
    setTimeout: (f) => f(),
  };
  omgeving.Date = { now: () => nu };
  vm.createContext(omgeving);

  // De echte code. Ontbreken de beurt-functies (de oude versie), dan draait de
  // ronde zoals hij toen draaide: altijd in dezelfde volgorde.
  for (const naam of ["platformsOpBeurt", "beurtDoorgeven", "pollJobsEenRonde"]) {
    const code = stuk(naam);
    if (code) vm.runInContext(code, omgeving);
  }
  if (!omgeving.platformsOpBeurt) {
    vm.runInContext("async function platformsOpBeurt() { return EXTENSION_PLATFORMS; }", omgeving);
    vm.runInContext("async function beurtDoorgeven() {}", omgeving);
  }

  for (let r = 0; r < rondes; r++) {
    await omgeving.pollJobsEenRonde();
    // De klok loopt door tot calm mode de volgende publicatie toestaat; dat is
    // wat er in het echt gebeurt terwijl het alarm elke 15 seconden opnieuw kijkt.
    if (calm && opslag.calmNa && opslag.calmNa > nu) nu = opslag.calmNa;
  }
  return { gedaan, wachtrij };
}

(async () => {
  console.log(OUD ? "\nOUDE versie (HEAD)\n" : "\nNIEUWE versie (werkmap)\n");

  // 1. Het echte geval: een volle Marktplaats-rij en één 2dehands-opdracht.
  const a = await draai({ mp: 20, tweedehands: 1, rondes: 4 });
  ok("2dehands komt binnen vier rondes aan de beurt", a.gedaan.includes("2dehands"),
     { volgorde: a.gedaan });
  ok("Marktplaats blijft gewoon doorlopen", a.gedaan.filter((p) => p === "marktplaats").length >= 3,
     { volgorde: a.gedaan });

  // 2. Zonder calm mode geldt hetzelfde: de server geeft één publicatie tegelijk
  //    uit, dus wie vooraan staat pakt anders alles.
  const b = await draai({ mp: 20, tweedehands: 1, rondes: 3, calm: false });
  ok("ook zonder calm mode komt 2dehands snel aan bod", b.gedaan.includes("2dehands"),
     { volgorde: b.gedaan });

  // 3. Niemand wordt overgeslagen: de hele rij gaat er uiteindelijk doorheen.
  const c = await draai({ mp: 5, tweedehands: 2, rondes: 30 });
  ok("alle opdrachten zijn uiteindelijk gedaan", c.wachtrij.every((j) => j.klaar),
     { open: c.wachtrij.filter((j) => !j.klaar).map((j) => j.id) });

  // 4. Een kanaal zonder werk houdt niemand op.
  const d = await draai({ mp: 3, tweedehands: 0, rondes: 3 });
  ok("een leeg kanaal kost geen beurt", d.gedaan.length === 3, { volgorde: d.gedaan });

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
  process.exit(mislukt ? 1 : 0);
})();
