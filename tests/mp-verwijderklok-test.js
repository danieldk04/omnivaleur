/**
 * Verwijderen en verlengen op Marktplaats/2dehands moeten met een vaste klok open.
 *
 * Aanleiding (16-10-2026, klant 26cf5471, extensie 1.0.388). 85 herplaatsingen
 * stonden sinds 15-10 11:56 stil terwijl de server gewoon een verwijdering
 * uitdeelde. Gemeten in zijn opdrachten: het eerste verwijderen na het wakker
 * worden van zijn computer bleef 81 minuten hangen (15-10 10:35 tot 11:56), en
 * vijf seconden nadat het eindelijk klaar was ging de volgende opdracht al uit.
 * Op 16-10 opnieuw: opgepakt na 08:35, om 09:03 door de server teruggezet omdat
 * hij na vijf minuten nog niets had gemeld. Plaatsingen in hetzelfde venster
 * liepen na het wakker worden binnen een halve minuut door; die hebben klokVast.
 *
 * bgDeleteMp2dh werkt via stukjes code ín de pagina (execInTab met fetch en
 * setTimeout). Zonder focus-emulatie staat de klok van een tabblad dat niet in
 * beeld is na anderhalve minuut op 0,0 tikken per seconde
 * (tests/klok-varianten-echt-test.mjs), en Chrome bevriest het tabblad daarna.
 * Dan wacht execInTab tot iemand het venster in beeld haalt, en zolang houdt de
 * extensie het kanaal bezet (_lopendePublicaties).
 *
 * Draaien:  node tests/mp-verwijderklok-test.js
 *           node tests/mp-verwijderklok-test.js --oud   (hoort te falen)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// Vast commit-nummer, geen HEAD: na het committen van deze reparatie zou HEAD
// de nieuwe code zijn en vergeleek de proef zich met zichzelf.
const VOOR = "e69e37da";
const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync(`git show ${VOOR}:extension/background.js`, { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

function functie(naam) {
  const start = BG.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  return BG.slice(start, BG.indexOf("\n}\n", start) + 2);
}

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

// Draai de echte functie tot vlak na het openen van het tabblad. Alles wat de
// functie zelf noemt komt uit `nep`; de rest (Promise, String, Error, ...) is
// gewoon de echte JavaScript. Het eerste wachten op het laden stopt de ronde.
async function totHetTabblad(naam, job) {
  const geopendMet = [];
  const nep = {
    openWorkerTab: (url, cb, opts) => { geopendMet.push(opts || {}); cb({ id: 7 }); },
    _klokTabbladen: new Set(),
    startOntdooiTeller: () => { nep._teller = true; },
    waitForTabLoad: async () => { throw new Error("stop"); },
    console: { log() {}, warn() {}, error() {} },
    _teller: false,
  };
  const omgeving = new Proxy(nep, { has: (t, k) => k in t });
  // `with` kan alleen buiten strict mode; new Function is dat standaard.
  const fabriek = new Function("omgeving", `with (omgeving) { ${functie(naam)}; return ${naam}; }`);
  const fn = fabriek(omgeving);
  try { await fn(job, "https://s"); } catch (_) { /* stop, of een helper die we niet nadoen */ }
  return { opts: geopendMet[0], klokTab: nep._klokTabbladen.has(7), teller: nep._teller };
}

// verzekerKlok zet na elke paginawissel de klok opnieuw. Kijkt hij ook naar een
// tabblad zonder jobtab_-gegevens?
async function verzekert() {
  const gezet = [];
  const nep = {
    chrome: { storage: { local: { get: async () => ({}) } } },
    _vroegGekoppeld: new Set([7]),
    _klokTabbladen: new Set([7]),
    heeftDebugger: async () => true,
    zetDoorlopendeKlok: async (tabId, url, altijd) => { gezet.push({ tabId, altijd }); },
  };
  const omgeving = new Proxy(nep, { has: (t, k) => k in t });
  const fabriek = new Function("omgeving", `with (omgeving) { ${functie("verzekerKlok")}; return verzekerKlok; }`);
  await fabriek(omgeving)(7);
  return gezet;
}

(async () => {
  console.log(OUD ? "OUDE CODE (hoort te falen)" : "NIEUWE CODE");

  console.log("\n1. Verwijderen op Marktplaats opent met een vaste klok");
  const a = await totHetTabblad("bgDeleteMp2dh", { id: "j1", platform: "marktplaats", payload: {
    title: "Bijbel met zilveren sloten", platform_listing_id: "m2454232919",
    platform_listing_url: "https://www.marktplaats.nl/v/antiek-en-kunst/m2454232919-bijbel",
  } });
  ok("openWorkerTab krijgt klokVast mee", a.opts && a.opts.klokVast === true, a.opts);
  ok("het tabblad staat op de lijst die na elke paginawissel de klok terugzet", a.klokTab);
  ok("de ontdooi-teller loopt", a.teller);

  console.log("\n2. Verwijderen op 2dehands ook");
  const b = await totHetTabblad("bgDeleteMp2dh", { id: "j2", platform: "2dehands", payload: {
    title: "Lamp", platform_listing_id: "m1234567890",
  } });
  ok("openWorkerTab krijgt klokVast mee", b.opts && b.opts.klokVast === true, b.opts);

  console.log("\n3. Verlengen op 2dehands ook");
  const c = await totHetTabblad("bgExtend2dh", { id: "j3", platform: "2dehands", payload: {
    platform_listing_id: "m1234567890",
  } });
  ok("openWorkerTab krijgt klokVast mee", c.opts && c.opts.klokVast === true, c.opts);
  ok("het tabblad staat op de lijst", c.klokTab);

  console.log("\n4. verzekerKlok zet de klok ook bij zo'n tabblad opnieuw");
  const d = await verzekert();
  ok("zetDoorlopendeKlok wordt aangeroepen", d.some((x) => x.tabId === 7 && x.altijd === true), d);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
  process.exit(mislukt ? 1 : 0);
})();
