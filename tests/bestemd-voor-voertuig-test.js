/**
 * Goudlief, sinds 31-10-2026: telefoonkoorden op 2dehands geweigerd met "These
 * fields were left empty on the form: intended for" (10 van de 14). In Telefoonhouders
 * heeft "Bestemd voor" alleen Auto, Fiets en Motor, zonder voorinvulling en niet
 * verplicht (gemeten 07-11-2026 op /plaats/820/3046). Geen van de drie past op een
 * koord, dus wij hielden iets tegen wat de site gewoon aanneemt.
 *
 * Tweede reparatie: hoed Amanda met maat L op "58 of 59 cm (L, 7¼ of ⅜ inch)" (06-11).
 *
 * Draait de ECHTE shared.js, nu en van vóór de reparatie (633a861f).
 * Draaien: node tests/bestemd-voor-voertuig-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function laadCL(bron, labelTekst, opties) {
  const select = {
    tagName: "SELECT", _v: "", selectedIndex: 0,
    options: [{ value: "", text: "Kies...", disabled: false }]
      .concat(opties.map((t) => ({ value: t, text: t, disabled: false }))),
    dispatchEvent() { return true; },
  };
  const label = {
    childNodes: [{ nodeType: 3, textContent: labelTekst }],
    textContent: labelTekst, children: [],
    querySelector: () => null,
    getAttribute: (k) => (k === "for" ? "veld" : null),
  };
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout, clearTimeout, Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
  };
  zand.window = zand;
  zand.self = zand;
  zand.location = { hostname: "www.2dehands.be", href: "https://www.2dehands.be/plaats/820/3046" };
  zand.document = {
    body: { click() {}, contains: () => false },
    querySelectorAll: (q) => (q.startsWith("label") ? [label] : q.includes("singleSelectAttribute") ? [select] : []),
    querySelector: () => null,
    getElementById: (id) => (id === "veld" ? select : null),
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  zand.HTMLSelectElement = function () {};
  Object.defineProperty(zand.HTMLSelectElement.prototype, "value", {
    configurable: true,
    get() { return this._v || ""; },
    set(v) { this._v = v; },
  });
  vm.createContext(zand);
  vm.runInContext(bron, zand, { filename: "shared.js" });
  return { CL: zand.window.CL, select };
}

const VOERTUIG = ["Auto", "Fiets", "Motor"];
function fout(bron, item) {
  const { CL } = laadCL(bron, "Bestemd voor", VOERTUIG);
  CL.selectIntendedFor(item);
  try { CL.verifyMpGroupFields(item); return ""; } catch (e) { return String(e.message); }
}
function kies(bron, item) {
  const { CL, select } = laadCL(bron, "Bestemd voor", VOERTUIG);
  CL.selectIntendedFor(item);
  return select._v;
}
function maat(bron, opties, waarde) {
  const { CL, select } = laadCL(bron, "Maat", opties);
  CL.kiesMetTerugval(select, "Maat", waarde);
  return select._v;
}

const KOORD = { title: "Telefoonkoord print", category: "electronics telefoonhouders",
  description: "Handig op de fiets, in de auto en voor op de motor", condition: "new_with_tags" };
const HOED = ["56 of 57 cm (M, 7 of ⅛ inch)", "58 of 59 cm (L, 7¼ of ⅜ inch)", "60 of 61 cm (XL, 7½ of ⅝ inch)"];

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
const bronOud = execSync("git show 633a861f:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

console.log("VOOR de reparatie");
check("koord werd tegengehouden op intended for", fout(bronOud, KOORD).includes("intended for"), fout(bronOud, KOORD));
check("hoed maat L vond zijn optie niet", maat(bronOud, HOED, "L") !== HOED[1], maat(bronOud, HOED, "L"));

console.log("\nNA de reparatie");
check("koord wordt niet meer tegengehouden", !fout(bronNu, KOORD).includes("intended for"), fout(bronNu, KOORD));
check("koord blijft leeg ondanks fiets en auto in de omschrijving", kies(bronNu, KOORD) === "", kies(bronNu, KOORD));
for (const [title, verwacht] of [
  ["Autohouder voor telefoon", "Auto"], ["Telefoonhouder auto magnetisch", "Auto"],
  ["Stevige telefoonhouder voor fiets", "Fiets"], ["Fietshouder gsm", "Fiets"],
  ["Motor telefoonhouder", "Motor"], ["Scooter gsm houder", "Motor"],
  ["Automatische telefoonhouder", ""],
]) {
  check(`"${title}" -> ${verwacht || "leeg"}`, kies(bronNu, { title }) === verwacht, kies(bronNu, { title }));
}
check("hoed maat L kiest L", maat(bronNu, HOED, "L") === HOED[1], maat(bronNu, HOED, "L"));
check("hoed maat XL kiest XL", maat(bronNu, HOED, "XL") === HOED[2], maat(bronNu, HOED, "XL"));

console.log("\nEen lijst die we niet kennen blijft tegengehouden");
{
  const { CL } = laadCL(bronNu, "Bestemd voor", ["Hond", "Kat"]);
  let tekst = "";
  try { CL.verifyMpGroupFields({ title: "Mand" }); } catch (e) { tekst = String(e.message); }
  check("onbekende lege lijst: intended for", tekst.includes("intended for"), tekst);
}

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
