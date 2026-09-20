/**
 * Het venster waar de VERKOPER in werkt mag nooit ingeklapt worden.
 *
 * GEMELD 20-09-2026 (Daniel). "Iedere keer als ik een item publiceer op
 * Marktplaats minimaliseert hij het hele tabblad waarin ik bezig ben: zowel het
 * dashboard als de twee publicaties." Twee keer achter elkaar.
 *
 * Het mechanisme: staat Chrome zonder vensters (op een Mac gewoon: rode kruisje)
 * dan maakt de extensie zelf een klein werkvenster met een vast anker-tabblad.
 * Klikt de verkoper daarna op het Chrome-icoon in de Dock, dan zet macOS precies
 * dat geminimaliseerde venster terug — en werkt hij vanaf dat moment IN ons
 * werkvenster. Het nummer van dat venster staat nog steeds in ons geheugen, dus
 * elke keer dat er een werk-tabblad bijkomt klapt `houdWerkvensterGeminimaliseerd`
 * het weer in. Met zijn dashboard erin.
 *
 * Draaien: node tests/werkvenster-van-de-gebruiker-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "601765df";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function haalFunctie(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  // Eerst de haakjes van de parameters uit de weg (een standaardwaarde als
  // `extra = {}` heeft zelf ook een accolade), dan pas het lichaam aflopen.
  let haakjes = 0, i = bron.indexOf("(", start);
  for (; i < bron.length; i++) {
    if (bron[i] === "(") haakjes++;
    else if (bron[i] === ")" && --haakjes === 0) break;
  }
  let diep = 0;
  for (let j = bron.indexOf("{", i); j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}" && --diep === 0) return bron.slice(start, j + 1);
  }
  throw new Error(`${naam} loopt niet af`);
}

const NODIG = [
  "getWorkerWindowId",
  "veiligOmWerkvensterTeMinimaliseren",
  "houdWerkvensterGeminimaliseerd",
  "maakWerkTabblad",
];

// wereld = { vensters: [{id,state}], tabs: [{id,windowId,url,pinned}],
//            werkvensterId, jobtabs: [tabId], gefocust: vensterId }
function maakOmgeving(bron, wereld) {
  const updates = [];
  let volgendTabId = 900;
  const tabs = wereld.tabs.map(t => ({ ...t }));
  const vensters = wereld.vensters.map(v => ({ ...v }));
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout,
    KEEPER_URL: "chrome-extension://abc/keeper.html",
    _onzeTabbladen: new Set(),
    WORKER_WIN_KEY: "workerWindowId",
    async koppelVroeg() { return true; },
    chrome: {
      storage: {
        session: {
          async get() { return { workerWindowId: wereld.werkvensterId }; },
          async remove() {},
        },
        local: {
          async get() {
            const uit = {};
            for (const id of wereld.jobtabs) uit[`jobtab_${id}`] = { jobId: "x" };
            return uit;
          },
        },
      },
      windows: {
        async get(id) {
          const w = vensters.find(v => v.id === id);
          if (!w) throw new Error("no such window");
          return { ...w };
        },
        async getLastFocused() {
          const w = vensters.find(v => v.id === wereld.gefocust);
          if (!w) throw new Error("none");
          return { ...w };
        },
        async update(id, wat) {
          updates.push({ id, ...wat });
          const w = vensters.find(v => v.id === id);
          if (w && wat.state) w.state = wat.state;
          return { ...w };
        },
      },
      tabs: {
        async query(q) {
          return tabs.filter(t => q.windowId == null || t.windowId === q.windowId)
                     .map(t => ({ ...t }));
        },
        async create(o) {
          const t = { id: volgendTabId++, windowId: o.windowId, url: o.url, pinned: !!o.pinned };
          tabs.push(t);
          // Een nieuw tabblad zet een ingeklapt venster op macOS terug in beeld.
          const w = vensters.find(v => v.id === o.windowId);
          if (w && w.state === "minimized") w.state = "normal";
          return { ...t };
        },
        async update(id, wat) {
          const t = tabs.find(x => x.id === id);
          if (t && wat.url) t.url = wat.url;
          return t ? { ...t } : {};
        },
      },
    },
  };
  vm.createContext(zand);
  let code = "";
  for (const naam of NODIG) {
    try { code += haalFunctie(bron, naam) + "\n"; }
    catch (e) { if (naam !== "vensterIsAlleenVanOns") throw e; }
  }
  // De reparatie brengt een extra helper mee; die bestaat in de oude versie niet.
  try { code += haalFunctie(bron, "vensterIsAlleenVanOns") + "\n"; } catch (_) {}
  code += "this.maak = maakWerkTabblad;";
  vm.runInContext(code, zand);
  return { zand, updates, vensters };
}

// DANIELS SITUATIE. Eén venster (nummer 3): ons anker-tabblad, zijn dashboard,
// en twee Marktplaats-publicaties. Het staat vooraan, want hij zit erin te
// werken. In ons geheugen staat dat venster 3 "ons werkvenster" is.
const DANIEL = {
  werkvensterId: 3,
  gefocust: 3,
  vensters: [{ id: 3, state: "normal", incognito: false }],
  tabs: [
    { id: 1, windowId: 3, url: "chrome-extension://abc/keeper.html", pinned: true },
    { id: 2, windowId: 3, url: "https://omnivaleur.com/app", pinned: false },
    { id: 3, windowId: 3, url: "https://www.marktplaats.nl/plaats/", pinned: false },
    { id: 4, windowId: 3, url: "https://www.marktplaats.nl/plaats/", pinned: false },
  ],
  jobtabs: [3, 4],
};

// ONS EIGEN WERKVENSTER, waar niets van hem in staat. Dat moet ingeklapt blijven.
const ALLEEN_VAN_ONS = {
  werkvensterId: 5,
  gefocust: 5,
  vensters: [{ id: 5, state: "normal", incognito: false }],
  tabs: [
    { id: 1, windowId: 5, url: "chrome-extension://abc/keeper.html", pinned: true },
    { id: 7, windowId: 5, url: "https://www.marktplaats.nl/plaats/", pinned: false },
  ],
  jobtabs: [7],
};

const NU = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const TOEN = execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`,
                      { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

function klapte(updates, id) {
  return updates.some(u => u.id === id && u.state === "minimized");
}

(async () => {
  console.log("Het venster van de verkoper blijft staan");

  // 1. De oude versie moet hier falen, anders bewijst deze proef niets.
  const oud = maakOmgeving(TOEN, DANIEL);
  await oud.zand.maak({ windowId: 3, active: false }, "https://www.marktplaats.nl/plaats/");
  check("vroeger: zijn venster werd ingeklapt", klapte(oud.updates, 3),
        "de oude versie liet het venster met rust — dan klopt deze proef niet");

  // 2. En nu niet meer.
  const nu = maakOmgeving(NU, DANIEL);
  await nu.zand.maak({ windowId: 3, active: false }, "https://www.marktplaats.nl/plaats/");
  check("nu: zijn venster blijft staan", !klapte(nu.updates, 3),
        `er ging alsnog een windows.update overheen: ${JSON.stringify(nu.updates)}`);

  // 3. Publiceren gaat gewoon door: er komt wel degelijk een tabblad bij.
  const tabsNa = await nu.zand.chrome.tabs.query({ windowId: 3 });
  check("nu: het werk-tabblad wordt gewoon geopend", tabsNa.length === 5,
        `${tabsNa.length} tabbladen in plaats van 5`);

  // 4. Ons eigen werkvenster blijft wél uit het zicht.
  const eigen = maakOmgeving(NU, ALLEEN_VAN_ONS);
  await eigen.zand.maak({ windowId: 5, active: false }, "https://www.marktplaats.nl/plaats/");
  check("nu: ons eigen werkvenster wordt nog steeds ingeklapt", klapte(eigen.updates, 5),
        "een venster zonder werk van de verkoper hoort onzichtbaar te blijven");

  console.log(mislukt === 0 ? "\nAlles goed." : `\n${mislukt} fout(en).`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
