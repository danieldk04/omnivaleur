/**
 * De gele balk met "Annuleren" (04-09-2026, Egbert Brouwer).
 *
 * Chrome zet tijdens het plaatsen een balk boven de browser: "'Omnivaleur' is
 * begonnen met foutopsporing voor deze browser", met een knop Annuleren.
 * Egbert stuurde er een foto van met een pijl naar precies die knop.
 *
 * Die koppeling is geen luxe: Marktplaats en 2dehands negeren een muisklik die
 * van een script komt, dus zonder koppeling wordt er nooit op "Plaats je
 * advertentie" gedrukt. Wie op Annuleren drukt breekt dus het plaatsen af — en
 * tot nu toe merkte de extensie dat niet eens: de lijst met gekoppelde
 * tabbladen bleef staan, dus klikEcht stuurde zijn klik het niets in en gaf het
 * daarna op. Het formulier bleef ingevuld en ongeplaatst achter.
 *
 * Deze proef draait de échte functie uit background.js.
 *
 * Draaien: node tests/extensie-annuleerknop-test.js
 *          node tests/extensie-annuleerknop-test.js /tmp/oude-background.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const bestand = process.argv[2] || path.join(__dirname, "..", "extension", "background.js");
const BG = fs.readFileSync(bestand, "utf8");

let mislukt = 0;
function ok(v, wat, uitleg) {
  if (v) { console.log("  ✓", wat); return; }
  console.log("  ✗", wat + (uitleg ? " — " + uitleg : "")); mislukt++;
}

function stukVanaf(zoek) {
  const i = BG.indexOf(zoek);
  if (i < 0) return null;
  let diepte = 0, j = BG.indexOf("{", i);
  for (; j < BG.length; j++) {
    if (BG[j] === "{") diepte++;
    else if (BG[j] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(i, j + 1);
}

const luisteraars = { onDetach: [] };
const gekoppeld = new Set();     // wat Chrome zélf denkt
let attachPogingen = 0;

const chrome = {
  debugger: {
    onDetach: { addListener: (f) => luisteraars.onDetach.push(f) },
    attach: (waar, v, cb) => { attachPogingen++; gekoppeld.add(waar.tabId); cb(); },
    detach: () => {},
    getTargets: (cb) => cb([]),
    sendCommand: (doel, m, p, cb) => {
      if (!gekoppeld.has(doel.tabId)) {
        chrome.runtime.lastError = { message: "Debugger is not attached to the tab with id: " + doel.tabId };
        cb(); chrome.runtime.lastError = null; return;
      }
      cb({});
    },
  },
  runtime: { lastError: null },
  tabs: {
    onRemoved: { addListener: () => {} },
    get: async (id) => ({ id, windowId: 9, url: "https://www.marktplaats.nl/plaats/12345" }),
  },
  windows: { get: async () => ({ id: 9, state: "normal" }), update: async () => {} },
  storage: { sync: { get: async () => ({}) } },
  scripting: {
    executeScript: async () => ([{ result: {
      x: 100, y: 200, raakt: true, binnenBeeld: true, hoogte: 800, breedte: 1200,
      erop: "BUTTON.plaats", zichtbaar: "visible+focus",
    } }]),
  },
};

const ctx = { chrome, console, setTimeout, Promise, Set, Math, String, Number };
ctx.globalThis = ctx;
vm.createContext(ctx);

// Alleen de stukken die hierover gaan, uit het echte bestand.
vm.runInContext("var _vroegGekoppeld = new Set();", ctx);
vm.runInContext(`var HEEFT_TOETSEN_NODIG = ${
  BG.match(/const HEEFT_TOETSEN_NODIG = (.+);/)[1]};`, ctx);
vm.runInContext(stukVanaf("async function koppelVroeg("), ctx);
vm.runInContext("async function heeftDebugger() { return true; }", ctx);
const detachStuk = BG.match(/chrome\.debugger\.onDetach\.addListener\([\s\S]*?\n\}\);/);
ok(!!detachStuk, "de extensie luistert of Chrome de koppeling verbreekt",
   "een druk op Annuleren gaat ongemerkt voorbij");
if (detachStuk) vm.runInContext(detachStuk[0], ctx);
vm.runInContext(stukVanaf("async function klikEcht("), ctx);

(async () => {
  // Zo begint het: het werktabblad wordt geopend en gekoppeld.
  await ctx.koppelVroeg(77, "https://www.marktplaats.nl/plaats/12345");
  ok(ctx._vroegGekoppeld.has(77), "tabblad gekoppeld bij het openen");

  // Egbert drukt op Annuleren. Chrome verbreekt de koppeling en meldt het.
  gekoppeld.delete(77);
  for (const f of luisteraars.onDetach) f({ tabId: 77 }, "canceled_by_user");

  attachPogingen = 0;
  const uit = await ctx.klikEcht(77, '[data-testid="place-listing-submit-button"]');
  ok(attachPogingen === 1, "de extensie koppelt opnieuw in plaats van op te geven",
     `pogingen: ${attachPogingen}, uitkomst: ${uit}`);
  ok(/geklikt op 100,200/.test(uit), "en er wordt alsnog op Plaatsen geklikt",
     `uitkomst: ${uit}`);

  // Lukt herkoppelen niet (Chrome weigert het op een volle pagina), dan hoort
  // er een duidelijke uitkomst te staan en geen stille klik in het niets.
  ctx._vroegGekoppeld.delete(77);
  gekoppeld.delete(77);
  chrome.debugger.attach = (waar, v, cb) => {
    attachPogingen++; chrome.runtime.lastError = { message: "Cannot access a chrome-extension:// URL" };
    cb(); chrome.runtime.lastError = null;
  };
  const uit2 = await ctx.klikEcht(77, '[data-testid="place-listing-submit-button"]');
  ok(uit2 === "niet gekoppeld", "mislukt herkoppelen wordt gemeld, niet verzwegen", uit2);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
  process.exit(mislukt ? 1 : 0);
})();
