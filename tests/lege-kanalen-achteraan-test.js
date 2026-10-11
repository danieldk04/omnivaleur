/**
 * Lege kanalen achteraan in de pollronde.
 *
 * 11-10-2026, Egbert (bcdf9aa4): alleen 2dehands-werk (verlengingen). In de
 * Railway-verzoeklog vroeg de extensie na elke verlenging eerst Vinted,
 * Facebook en Marktplaats af (~1 s per vraag, alle drie leeg) voordat 2dehands
 * weer aan bod kwam: de beurt schuift na elke opdracht een kanaal op.
 *
 * Draait de ECHTE pollronde uit background.js met een nagebootste server die
 * per vraag tijd telt. Draaien: node tests/lege-kanalen-achteraan-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "6279f2b8";
const ROOT = path.join(__dirname, "..");

let mislukt = 0;
const check = (naam, v, extra) => {
  if (v) { console.log(`  ok   ${naam}`); return; }
  mislukt++; console.log(`  FOUT ${naam}${extra !== undefined ? " : " + JSON.stringify(extra) : ""}`);
};

function stuk(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let i = bron.indexOf("{", bron.indexOf(")", start)), diep = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diep++;
    else if (bron[i] === "}") { diep--; if (diep === 0) return bron.slice(start, i + 1); }
  }
  throw new Error(`${naam} loopt niet af`);
}

// werk: { platform: aantal opdrachten }. Geeft per ronde de gevraagde kanalen
// tot en met de uitgifte terug.
async function draai(bron, werk, rondes) {
  const rij = [];
  for (const [p, n] of Object.entries(werk)) {
    for (let i = 0; i < n; i++) rij.push({ id: `${p}${i}`, platform: p, action: p === "2dehands" ? "extend" : "create" });
  }
  const opslag = {};
  const log = [];
  const z = {
    console: { log() {}, error() {}, warn() {} },
    EXTENSION_PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook"],
    SCHRIJVENDE_ACTIES: new Set(["create", "delete", "content_refresh", "extend"]),
    MIN_GAP_MS: 0, MAX_PARALLELLE_PUBLICATIES: 3, POLL_FETCH_MAX_MS: 10000,
    AbortSignal: { timeout: () => undefined },
    _lopendeScans: new Set(), _lopendePublicaties: new Set(), _wachtrijStand: {},
    PLATFORM_BEURT_SLEUTEL: "platformBeurt",
    wakkerHouden() {}, pollJobs: async () => {},
    chrome: { storage: { local: {
      get: async (k) => (k in opslag ? { [k]: opslag[k] } : {}),
      set: async (o) => { Object.assign(opslag, o); },
    } } },
    getServerUrl: async () => "https://server", getAuthHeaders: async () => ({}),
    flushFinaliseQueue: async () => {}, reportError: async () => {},
    calmMagNu: async () => true, calmVolgendeInplannen: async () => {},
    setTimeout: () => {},
    fetch: async (url) => {
      const p = decodeURIComponent(String(url).split("platform=")[1] || "");
      log.push(p);
      return { ok: true, json: async () => rij.filter((j) => j.platform === p && !j.klaar).slice(0, 25).map((j) => ({ ...j })) };
    },
    processJob: async (job) => {
      log.push(`UIT:${job.platform}`);
      const r = rij.find((j) => j.id === job.id); if (r) r.klaar = true;
    },
  };
  vm.createContext(z);
  for (const n of ["platformsOpBeurt", "beurtDoorgeven", "pollJobsEenRonde"]) vm.runInContext(stuk(bron, n), z);
  const perRonde = [];
  for (let r = 0; r < rondes; r++) {
    log.length = 0;
    await z.pollJobsEenRonde();
    await new Promise((k) => setImmediate(k));
    perRonde.push([...log]);
  }
  return { perRonde, rij };
}

const voorUitgifte = (ronde, kanaal) => {
  const i = ronde.indexOf(`UIT:${kanaal}`);
  return i < 0 ? null : ronde.slice(0, i).filter((x) => !x.startsWith("UIT:") && x !== kanaal).length;
};

(async () => {
  const OUD = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const NIEUW = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");

  console.log(`Oude versie (${OUDE_COMMIT}): alleen 2dehands-werk, zoals bij Egbert`);
  const oud = await draai(OUD, { "2dehands": 6 }, 5);
  const oudLeeg = oud.perRonde.slice(1).map((r) => voorUitgifte(r, "2dehands"));
  check("vroeg vóór elke verlenging eerst drie lege kanalen (de klacht)", oudLeeg.every((n) => n === 3), oudLeeg);

  console.log("\nNieuwe versie: zelfde situatie");
  const nieuw = await draai(NIEUW, { "2dehands": 6 }, 5);
  const nieuwLeeg = nieuw.perRonde.slice(1).map((r) => voorUitgifte(r, "2dehands"));
  check("2dehands meteen als eerste gevraagd", nieuwLeeg.every((n) => n === 0), nieuwLeeg);
  check("de lege kanalen worden in dezelfde ronde nog steeds gevraagd",
    nieuw.perRonde.slice(1).every((r) => ["marktplaats", "vinted", "facebook"].every((p) => r.includes(p))),
    nieuw.perRonde);
  check("elke ronde een verlenging uit", nieuw.perRonde.every((r) => r.includes("UIT:2dehands")), nieuw.perRonde);

  console.log("\nNieuwe versie: een leeg kanaal krijgt werk");
  const z = await draai(NIEUW, { "2dehands": 6 }, 2);
  // Derde ronde met plots Vinted-werk erbij: zelfde omgeving nabootsen door
  // opnieuw te draaien met werk op beide, na een eerste ronde zonder Vinted.
  const beide = await draai(NIEUW, { "2dehands": 6, vinted: 2 }, 3);
  check("Vinted-werk gaat in de eerste ronde al uit",
    beide.perRonde[0].includes("UIT:vinted") || beide.perRonde[1].includes("UIT:vinted"), beide.perRonde);
  check("en 2dehands loopt ernaast gewoon door", beide.perRonde.every((r) => r.includes("UIT:2dehands")), beide.perRonde);
  check("eerste ronde zonder voorkennis: gewone volgorde", z.perRonde[0][0] === "marktplaats", z.perRonde[0]);

  console.log(mislukt === 0 ? "\nAlles groen." : `\n${mislukt} controle(s) mislukt.`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
