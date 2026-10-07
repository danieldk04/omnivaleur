/**
 * 2dehands verlengen via het filter "Loopt af" in plaats van het hele overzicht.
 *
 * 07-10-2026, Egbert (bcdf9aa4, 2.437 zoekertjes): "bij het verlengen begint
 * Omnivaleur iedere keer weer met het openen van alle zoekertjes". Gemeten:
 * ~5 minuten per verlenging, bijna allemaal openklappen (~49 klikken). Het
 * filter "Loopt af" (Dropdown-filterOpStatus = expiring) toont alleen de
 * zoekertjes met een verlengknop; nagemeten op account Revaleur.
 *
 * Het nagebootste overzicht: 50 rijen, 50 meer per klik op "Toon 50 volgende",
 * en het filter dat alleen de aflopende laat zien.
 *
 * Draaien:  node tests/verlengen-2dehands-filter-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "d40f5116";
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

// alle: aantal zoekertjes; aflopend: indexen die EXPIRING zijn (oudste onderaan);
// zonderFilter: de pagina heeft geen statusfilter (markup veranderd);
// filterMist: het filter laat het gezochte zoekertje weg terwijl de API hem
// aflopend noemt (vangnet).
function maakZand({ alle, aflopend, gezocht, zonderFilter = false, filterMist = false }) {
  const ids = Array.from({ length: alle }, (_, i) => `m${2400000000 + i}`);
  const afl = new Set(aflopend.map(i => ids[i]));
  const p = { filter: "", getoond: 50, klikken: 0, herladen: 0 };
  const lijst = () => p.filter === "expiring"
    ? ids.filter(id => afl.has(id) && !(filterMist && id === gezocht)) : ids;
  const zichtbaar = () => lijst().slice(0, p.getoond);
  const knop = {
    textContent: "Toon 50 volgende", disabled: false,
    click() { p.klikken++; p.getoond += 50; },
  };
  const select = {
    options: [{ value: "" }, { value: "active" }, { value: "expiring" }],
    _v: "",
    set value(v) { this._v = v; },
    get value() { return this._v; },
    dispatchEvent() { p.filter = this._v; p.getoond = 50; },
  };
  class HTMLSelectElement {}
  Object.defineProperty(HTMLSelectElement.prototype, "value", {
    set(v) { this._v = v; }, get() { return this._v; }, configurable: true,
  });
  const zand = {
    console: { log() {}, warn() {}, error() {} }, Set, Math, String,
    setTimeout: (f) => setTimeout(f, 0), HTMLSelectElement,
    Event: class { constructor(t) { this.type = t; } }, p,
  };
  zand.document = {
    getElementById(id) { return id === "Dropdown-filterOpStatus" && !zonderFilter ? select : null; },
    querySelector(sel) {
      const m = sel.match(/#verlengen"\]\[data-ad-id="([^"]+)"/);
      return m && afl.has(m[1]) && zichtbaar().includes(m[1]) ? {} : null;
    },
    querySelectorAll(sel) {
      if (sel === "button") return p.getoond < lijst().length ? [knop] : [];
      if (sel === "[data-ad-id]") return zichtbaar().map(id => ({ getAttribute: () => id }));
      return [];
    },
  };
  zand.fetch = async (url) => {
    const u = new URL(url, "https://www.2dehands.be");
    const n = Number(u.searchParams.get("batchSize")), b = Number(u.searchParams.get("batchNumber"));
    const bron = u.searchParams.get("inExpirationWindow") === "true" ? ids.filter(id => afl.has(id)) : ids;
    const ads = bron.slice((b - 1) * n, b * n).map(id => ({ itemId: id, status: afl.has(id) ? "EXPIRING" : "ACTIVE" }));
    return { ok: true, status: 200, json: async () => ({ ads, totalNumberOfResults: bron.length }) };
  };
  zand.execInTab = async (_t, fn, args = []) => fn(...args);
  zand.zetWerkStatus = async () => {};
  zand.waitForTabLoad = async () => {};
  zand.stuurWerkTabbladNaar = async () => {
    p.herladen++; p.filter = ""; select._v = ""; p.getoond = 50;
  };
  vm.createContext(zand);
  return zand;
}

async function draai(bron, opties) {
  const zand = maakZand(opties);
  vm.runInContext(functieUit(bron, "expandMp2dhOverview"), zand);
  zand.gezocht = opties.gezocht;
  await vm.runInContext("expandMp2dhOverview(1, { verlengId: gezocht })", zand);
  const knopDaar = !!zand.document.querySelector(`a[href="#verlengen"][data-ad-id="${opties.gezocht}"]`);
  return { ...zand.p, knopDaar };
}

async function proef(naam, bron) {
  console.log(`\n${naam}`);
  // Egberts formaat: 2.437 zoekertjes, de oudste 120 lopen af en staan onderaan.
  const aflopend = Array.from({ length: 120 }, (_, i) => 2317 + i);
  const id = (i) => `m${2400000000 + i}`;

  let r = await draai(bron, { alle: 2437, aflopend, gezocht: id(2436) });
  check(`laatste aflopende: knop gevonden met hooguit 2 klikken (was ${r.klikken})`,
    r.knopDaar && r.klikken <= 2, JSON.stringify(r));

  r = await draai(bron, { alle: 2437, aflopend, gezocht: id(2320) });
  check(`eerste aflopende: knop gevonden zonder klikken (was ${r.klikken})`,
    r.knopDaar && r.klikken === 0, JSON.stringify(r));

  // Al verlengd (niet meer aflopend): niets te klikken, dus ook niet het hele
  // overzicht openklappen. bgExtend2dh meet daarna "al verlengd".
  r = await draai(bron, { alle: 2437, aflopend, gezocht: id(5) });
  check(`al verlengd: hele overzicht niet opengeklapt (klikken ${r.klikken})`,
    !r.knopDaar && r.klikken <= 2 && r.herladen === 0, JSON.stringify(r));
}

async function vangnetten(bron) {
  console.log("\nVangnetten (alleen nieuwe versie)");
  const aflopend = Array.from({ length: 120 }, (_, i) => 2317 + i);
  const id = (i) => `m${2400000000 + i}`;
  let r = await draai(bron, { alle: 2437, aflopend, gezocht: id(2436), zonderFilter: true });
  check("geen filter op de pagina: oude weg, knop toch gevonden", r.knopDaar, JSON.stringify(r));
  r = await draai(bron, { alle: 2437, aflopend, gezocht: id(2436), filterMist: true });
  check("filter laat hem weg, API zegt aflopend: herladen en hele overzicht, knop gevonden",
    r.knopDaar && r.herladen === 1, JSON.stringify(r));
  r = await draai(bron, { alle: 300, aflopend: [], gezocht: id(299) });
  check("niets aflopend: geen klikken, geen herladen", r.klikken === 0 && r.herladen === 0, JSON.stringify(r));
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
  await vangnetten(nieuw);
  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
