/**
 * Elke kleur uit het keuzemenu tegen de ECHTE kleurlijst van elke Marktplaats-
 * rubriek (30-09-2026, uitgelezen uit het plaatsformulier zelf, zie
 * tests/fixtures/marktplaats_kleurlijsten_30-09-2026.json).
 *
 * Marktplaats biedt per rubriek een eigen, vaak korte lijst (spijkerbroeken:
 * Blauw, Grijs, Wit, Zwart, Overige kleuren). Deze proef draait de ECHTE
 * kiesMetTerugval uit shared.js voor elke rubriek met een kleurveld en elk van
 * de 29 menukleuren, en meldt waar het veld leeg blijft, of iets gekozen wordt
 * dat er niet bij past.
 *
 * Draaien: node tests/mp-kleurlijsten-alle-rubrieken-test.js [--details]
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const DETAILS = process.argv.includes("--details");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Wat de server met een menukleur doet voordat de opdracht de extensie bereikt
// (normaliseer_kleur in backend/api/jobs.py), rechtstreeks uit de Python-code.
const VOOR_MP = JSON.parse(execSync(
  `python3 -c "import json;from backend.services.kleur import KLEUREN,normaliseer_kleur;print(json.dumps([[en,normaliseer_kleur(en) or en] for en,_,_ in KLEUREN]))"`,
  { cwd: WORTEL }).toString());
// ── Een nagemaakt <select>, genoeg om de echte code op te draaien ─────────
function maakSelect(opties) {
  const options = [{ value: "", text: "Kies...", disabled: false }]
    .concat(opties.map((t) => ({ value: t, text: t, disabled: false })));
  return { tagName: "SELECT", value: "", options, dispatchEvent() { return true; } };
}

function laadCL(bron) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout, clearTimeout, Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false },
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  // De echte code zet de waarde via de setter op het prototype. Nagemaakt met
  // een gewone property, zodat we niet de browser hoeven na te bouwen.
  zand.HTMLSelectElement = function () {};
  Object.defineProperty(zand.HTMLSelectElement.prototype, "value", {
    configurable: true,
    get() { return this._v || ""; },
    set(v) { this._v = v; },
  });
  vm.createContext(zand);
  vm.runInContext(bron, zand, { filename: "shared.js" });
  return zand.window.CL;
}

// Zoals repairOnce het doet: eerst de vertaalde waarde, dan de terugval.
function vulKleur(CL, waarde, opties) {
  const el = maakSelect(opties);
  const proxy = new Proxy(el, {
    get(t, k) { return k === "value" ? (t._v || "") : t[k]; },
    set(t, k, v) { if (k === "value") t._v = v; else t[k] = v; return true; },
  });
  const vertaald = CL.dutchColor(waarde);
  // 1.0.280 kende de terugval nog niet en deed alleen fillNativeSelect. Zo
  // meten we van beide versies precies wat ze in het echt deden.
  const gekozen = CL.kiesMetTerugval
    ? CL.kiesMetTerugval(proxy, "Kleur", vertaald)
    : CL.fillNativeSelect(proxy, vertaald);
  return { gekozen, veldwaarde: el._v || "" };
}


const CL = laadCL(fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8"));
const data = JSON.parse(fs.readFileSync(path.join(WORTEL,
  "tests/fixtures/marktplaats_kleurlijsten_30-09-2026.json"), "utf8"));
const lijsten = data.lijsten;
let totaal = 0, leeg = 0, leegVerplicht = 0;
const perKleurLeeg = {}, verplichtLeeg = [], keuzes = {}, rubriekenLeeg = {};
for (const k of lijsten) {
  for (const [menu, naarMp] of VOOR_MP) {
    totaal += k.aantalRubrieken;
    const { veldwaarde } = vulKleur(CL, naarMp, k.values);
    const sleutel = `${menu} -> ${veldwaarde || "(leeg)"}`;
    keuzes[sleutel] = (keuzes[sleutel] || 0) + k.aantalRubrieken;
    if (!veldwaarde) {
      leeg += k.aantalRubrieken; perKleurLeeg[menu] = (perKleurLeeg[menu] || 0) + k.aantalRubrieken;
      if (k.mandatory) { leegVerplicht += k.aantalRubrieken; verplichtLeeg.push(`[${k.values.join("/")}] ${menu}`); }
    }
  }
}
const rubrieken = { length: data.rubriekenMetKleurveld };
data.rubrieken = { length: data.rubriekenGetest };
console.log(`rubrieken met kleurveld: ${rubrieken.length} van ${data.rubrieken.length}`);
console.log(`combinaties getest: ${totaal}; veld leeg: ${leeg}; leeg EN verplicht: ${leegVerplicht}`);
console.log("leeg per kleur:", JSON.stringify(perKleurLeeg));
if (DETAILS) { for (const [k, n] of Object.entries(keuzes).sort()) console.log(`   ${n}\t${k}`); }
verplichtLeeg.slice(0, 40).forEach((v) => console.log("   verplicht+leeg: " + v));

// Wat mag een kleur op een ANDERE optie uitkomen dan zijn eigen naam?
const MAG_OOK = {
  Wit: ["Instelbaar wit", "Koel wit", "Neutraal wit", "Warm wit", "Daglicht"],
  Grijs: ["Zilver of Grijs", "Lichtgrijs", "Antraciet"],
  Zilver: ["Zilver of Grijs", "Grijs"],
  Beige: ["Crème of Beige", "Crème", " Ivoor of Crème"],
  Roze: ["Roze of Coral", "Rose Goud"],
  Bordeaux: ["Rood"],
  Meerkleurig: ["Multi", "Multicolour"],
  Goud: ["Rose Goud"],
};
const fout = [];
for (const k of lijsten) {
  for (const [menu, naarMp] of VOOR_MP) {
    const { veldwaarde } = vulKleur(CL, naarMp, k.values);
    if (!veldwaarde) continue;
    const eigen = CL.dutchColor(naarMp);
    const ok = veldwaarde === eigen || /^Overige/.test(veldwaarde) ||
      (MAG_OOK[eigen] || []).includes(veldwaarde) ||
      new RegExp("(^|[\\s(/-])" + eigen + "([\\s)/-]|$)", "i").test(veldwaarde);
    if (!ok) fout.push(`${menu} (${naarMp}) -> ${veldwaarde} in [${k.values.join("/")}]`);
  }
}

console.log("\nUitkomst per controle");
check("het Kleur-veld is in geen enkele rubriek verplicht (gemeten)",
  data.verplichtAantal === 0 && lijsten.every((k) => !k.mandatory));
check("een leeg veld komt nooit voor bij een verplicht veld", leegVerplicht === 0);
check("geen enkele kleur belandt op een kleur die er niet bij past", fout.length === 0,
  fout.slice(0, 5).join(" ; "));
check("geen enkele kleur behalve Meerkleurig belandt op Meerkleurig",
  !Object.keys(keuzes).some((s) => /-> (Meerkleurig|Multi)$/.test(s) && !s.startsWith("Various")));
check("elke lijst met een eigen naam voor de kleur krijgt die kleur",
  ["Black -> Zwart", "Blue -> Blauw", "Green -> Groen", "Red -> Rood", "Grey -> Grijs"].every((s) => keuzes[s] > 100));
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
