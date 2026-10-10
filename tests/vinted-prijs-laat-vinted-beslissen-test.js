/**
 * Janneke, 10-10-2026: zes Vinted-plaatsingen stopten met "Vinted accepteerde
 * deze velden niet: price (50)", zonder dat Vinted onder het prijsveld iets zei.
 * Draait de echte prijsBesluit uit extension/content/vinted.js.
 */
const fs = require("fs");
const path = require("path");
const SRC = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "vinted.js"), "utf8");
function functie(naam) {
  const i = SRC.indexOf(`  function ${naam}(`);
  if (i < 0) throw new Error(`${naam} niet gevonden`);
  return SRC.slice(i, SRC.indexOf("\n  }\n", i) + 4);
}
const { prijsBesluit } = new Function(functie("_num") + functie("prijsBesluit") + "return { prijsBesluit };")();
let mislukt = 0;
function check(naam, ok, extra) { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}${ok ? "" : " — " + JSON.stringify(extra)}`); if (!ok) mislukt++; }

let b = prijsBesluit(50, "50", 0, null);
check("veld toont 50, geen klacht: Vinted beslist zelf", b.door === true, b);
check("en we onthouden wat we zagen", /field showed 50, Vinted's form held 0/.test(b.twijfel), b);
b = prijsBesluit(29.5, "29,50", null, null);
check("komma in het veld telt ook", b.door === true, b);
b = prijsBesluit(50, "5", 0, null);
check("veld toont een andere prijs: stoppen", b.door === false && /field showed "5"/.test(b.gat), b);
b = prijsBesluit(50, "50", 0, "Price must be greater than or equal to 1.0");
check("Vinted klaagt: stoppen, met de klacht erbij", b.door === false && /Vinted says/.test(b.gat), b);
b = prijsBesluit(50, null, null, null);
check("geen prijsveld: stoppen", b.door === false && /no field/.test(b.gat), b);
check("de melding begint nog steeds met price (", /^price \(50;/.test(b.gat), b);
process.exit(mislukt ? 1 : 0);
