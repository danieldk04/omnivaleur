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
const WORTEL = path.join(__dirname, "..");
// De auto-push-hook commit tussendoor, dus "HEAD" is niet de versie van vóór de
// reparatie. Zoek de commit die de beurtverdeling invoerde en neem zijn ouder.
const voorReparatie = () => {
  const eerste = execSync(
    'git log -S"platformsOpBeurt" --reverse --format=%h -- extension/background.js',
    { cwd: WORTEL }).toString().trim().split("\n")[0];
  if (!eerste) throw new Error("kan de commit met de beurtverdeling niet vinden");
  return `${eerste}^`;
};
const BG = OUD
  ? execSync(`git show ${voorReparatie()}:extension/background.js`, { cwd: WORTEL, maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension", "background.js"), "utf8");

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

// Eén ronde draaien en zien of ze afloopt. "hangt" betekent: deze versie staat
// te wachten tot de lopende publicatie klaar is (`await processJob`).
const eenRonde = (omgeving) => Promise.race([
  omgeving.pollJobsEenRonde().then(() => "klaar"),
  new Promise((r) => setTimeout(() => r("hangt"), 50)),
]);

// Een nagebootste wachtrij plus de echte pollronde eromheen.
//
// `blijftHangen` laat de publicaties NIET vanzelf afronden, zodat zichtbaar is
// hoeveel er tegelijk lopen. Dat is wat sinds 19-09-2026 de vraag is: kanalen
// mogen naast elkaar publiceren, maar nooit twee op hetzelfde kanaal.
async function draai({ mp, tweedehands, vinted = 0, facebook = 0, rondes,
                       calm = true, blijftHangen = false }) {
  const wachtrij = [];
  for (let i = 0; i < mp; i++) wachtrij.push({ id: `mp${i}`, platform: "marktplaats", action: "create" });
  for (let i = 0; i < tweedehands; i++) wachtrij.push({ id: `td${i}`, platform: "2dehands", action: "create" });
  for (let i = 0; i < vinted; i++) wachtrij.push({ id: `vi${i}`, platform: "vinted", action: "create" });
  for (let i = 0; i < facebook; i++) wachtrij.push({ id: `fb${i}`, platform: "facebook", action: "create" });

  const gedaan = [];            // volgorde waarin er echt begonnen is
  const lopend = [];            // publicaties die nu een tabblad open hebben
  let nu = 1_000_000;           // virtuele klok
  const opslag = {};            // chrome.storage.local

  const omgeving = {
    console: { log() {}, error() {}, warn() {} },
    EXTENSION_PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook"],
    SCHRIJVENDE_ACTIES: new Set(["create", "delete", "content_refresh"]),
    MIN_GAP_MS: 0,
    _lopendeScans: new Set(),
    _lopendePublicaties: new Set(),
    MAX_PARALLELLE_PUBLICATIES: 3,
    wakkerHouden: () => {},
    pollJobs: async () => {},          // wordt na afloop van een klus aangeroepen
    PLATFORM_BEURT_SLEUTEL: "platformBeurt",
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
    // De server, met dezelfde regels als de echte uitgifte (get_pending_jobs):
    // een opdracht die al is uitgegeven komt niet nog een keer langs, op een
    // kanaal waar een formulier openstaat gaat er niets uit, en er lopen er
    // nooit meer dan drie tegelijk. Zonder die regels zou deze proef een
    // extensie goedkeuren die in het echt tegen een dichte deur loopt.
    fetch: async (url) => {
      const platform = decodeURIComponent(String(url).split("platform=")[1] || "");
      const bezet = new Set(wachtrij.filter((j) => j.uitgegeven && !j.klaar)
                                    .map((j) => j.platform));
      if (bezet.has(platform) || bezet.size >= 3) {
        return { ok: true, json: async () => [] };
      }
      const rij = wachtrij.filter((j) => j.platform === platform && !j.uitgegeven).slice(0, 25);
      return { ok: true, json: async () => rij.map((j) => ({ ...j })) };
    },
    // Publiceren duurt tijd; daarna staat de opdracht af.
    processJob: (job) => {
      const rij = wachtrij.find((j) => j.id === job.id);
      if (rij) rij.uitgegeven = true;          // de server claimt hem bij het oppakken
      gedaan.push(job.platform);
      if (blijftHangen) {
        // Het tabblad blijft open staan tot de proef hem zelf afrondt.
        return new Promise((klaar) => lopend.push({
          job, afronden: () => { if (rij) rij.klaar = true; klaar(); },
        }));
      }
      if (rij) rij.klaar = true;
      nu += 30 * 1000;
      return Promise.resolve();
    },
    // Calm mode: sinds 19-09-2026 één klok PER KANAAL. Marktplaats ziet niet wat
    // er op Vinted gebeurt, en één klok voor alles zou het naast elkaar
    // publiceren meteen weer ongedaan maken.
    calmMagNu: async (platform) => (calm ? nu >= (opslag[`calmNa_${platform}`] || 0) : true),
    calmVolgendeInplannen: async (platform) => {
      if (calm) opslag[`calmNa_${platform}`] = nu + CALM_MS;
    },
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
    // Met blijftHangen ronden de publicaties niet vanzelf af. De OUDE versie
    // wacht die afronding af (`await processJob`) en komt dus nooit terug uit
    // deze ronde. Dat is geen testfoutje maar precies het gedrag: zolang die
    // ronde hangt begint er bij haar niets nieuws, want `_pollLoopt` laat er in
    // het echt maar één ronde tegelijk lopen. Blijft ze hangen, dan stoppen we
    // hier — verder tellen zou de oude versie rondes geven die ze nooit krijgt.
    if (blijftHangen) {
      if (await eenRonde(omgeving) === "hangt") break;
    } else {
      await omgeving.pollJobsEenRonde();
    }
    // De klok loopt door tot calm mode de volgende publicatie toestaat; dat is
    // wat er in het echt gebeurt terwijl het alarm elke 15 seconden opnieuw kijkt.
    if (calm) {
      const klokken = Object.entries(opslag)
        .filter(([k, v]) => k.startsWith("calmNa_") && v > nu).map(([, v]) => v);
      if (klokken.length && !lopend.length) nu = Math.min(...klokken);
    }
  }
  return { gedaan, wachtrij, lopend, omgeving };
}

(async () => {
  console.log(OUD ? "\nOUDE versie (HEAD)\n" : "\nNIEUWE versie (werkmap)\n");

  // 1. Het echte geval: een volle Marktplaats-rij en één 2dehands-opdracht.
  const a = await draai({ mp: 20, tweedehands: 1, rondes: 4 });
  ok("2dehands komt binnen vier rondes aan de beurt", a.gedaan.includes("2dehands"),
     { volgorde: a.gedaan });
  ok("Marktplaats blijft gewoon doorlopen", a.gedaan.filter((p) => p === "marktplaats").length >= 3,
     { volgorde: a.gedaan });

  // 2. Zonder calm mode geldt hetzelfde. Hier telt niet het aantal rondes maar
  //    hoeveel Marktplaats-advertenties er eerst nog doorheen moeten: elke
  //    publicatie kost in het echt ongeveer een minuut.
  const b = await draai({ mp: 20, tweedehands: 1, rondes: 3, calm: false });
  const ervoor = b.gedaan.indexOf("2dehands");
  ok("2dehands hoeft niet achter de hele Marktplaats-rij aan te sluiten",
     ervoor >= 0 && ervoor <= 2, { plek: ervoor, volgorde: b.gedaan.slice(0, 6) });

  // 3. Niemand wordt overgeslagen: de hele rij gaat er uiteindelijk doorheen.
  const c = await draai({ mp: 5, tweedehands: 2, rondes: 30 });
  ok("alle opdrachten zijn uiteindelijk gedaan", c.wachtrij.every((j) => j.klaar),
     { open: c.wachtrij.filter((j) => !j.klaar).map((j) => j.id) });

  // 4. Een kanaal zonder werk houdt niemand op.
  const d = await draai({ mp: 3, tweedehands: 0, rondes: 3 });
  ok("een leeg kanaal kost geen beurt", d.gedaan.length === 3, { volgorde: d.gedaan });

  // ── 19-09-2026: kanalen naast elkaar ───────────────────────────────────────
  //
  // Daniel, over een 2dehands-zoekertje dat op Marktplaats stond te wachten:
  // "hij doet heel lang over 2dehands openen, ik denk dat ie vastgelopen is."
  // Gemeten over tien dagen: 289 seconden wachten (mediaan) op een publicatie
  // op een ánder kanaal, bovenop de 108 tot 354 seconden die het invullen zelf
  // kost.

  // 5. Vier kanalen met werk: er gaan er drie tegelijk van start, elk op een
  //    eigen kanaal, en het vierde wacht op een vrije plek.
  const e = await draai({ mp: 3, tweedehands: 3, vinted: 3, facebook: 3,
                          rondes: 3, calm: false, blijftHangen: true });
  const kanalen = e.lopend.map((l) => l.job.platform);
  ok("drie kanalen publiceren tegelijk", e.lopend.length === 3, { kanalen });
  ok("elk op zijn eigen kanaal", new Set(kanalen).size === kanalen.length, { kanalen });
  ok("het vierde kanaal wacht op een plek", !kanalen.includes(kanalen[3]), { kanalen });

  // 6. Twintig Marktplaats-opdrachten en verder niets: er mag er precies ÉÉN
  //    tegelijk lopen. Twee formulieren van dezelfde site is exact wat er nooit
  //    mag gebeuren.
  const f = await draai({ mp: 20, tweedehands: 0, rondes: 5, calm: false,
                          blijftHangen: true });
  ok("nooit twee tabbladen op hetzelfde kanaal", f.lopend.length === 1,
     { lopend: f.lopend.map((l) => l.job.id) });

  // 7. Zodra een kanaal klaar is, komt de volgende opdracht van DAT kanaal
  //    aan de beurt en niet pas over een ronde.
  if (!f.lopend.length) { ok("na afronden gaat hetzelfde kanaal meteen door", false, "niets liep"); }
  else {
  f.lopend[0].afronden();
  await new Promise((r) => setImmediate(r));
  await eenRonde(f.omgeving);
  ok("na afronden gaat hetzelfde kanaal meteen door", f.lopend.length === 2,
     { lopend: f.lopend.map((l) => l.job.id) });
  }

  // 8. Calm mode remt per kanaal, niet het hele huis. Anders zou de eerste
  //    publicatie alle andere kanalen drie tot acht minuten stilzetten.
  const g = await draai({ mp: 2, tweedehands: 2, vinted: 2, rondes: 1,
                          calm: true, blijftHangen: true });
  ok("calm mode houdt de andere kanalen niet tegen", g.lopend.length === 3,
     { kanalen: g.lopend.map((l) => l.job.platform) });

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
  process.exit(mislukt ? 1 : 0);
})();
