/**
 * De ene kleurenlijst (backend/services/kleur.py KLEUREN): elke kleur uit het
 * keuzemenu moet op Vinted zijn EIGEN tegel landen, niet op een buurman.
 * Draaien: node tests/kleurenlijst-vinted-test.js
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

const KLEUREN = JSON.parse(execSync(
  `python3 -c "import json;from backend.services.kleur import KLEUREN;print(json.dumps(KLEUREN))"`,
  { cwd: WORTEL }).toString());
const VINTED_TEGELS = KLEUREN.map(([, nl, code]) => [nl, code]);

// Een tegel nabootsen: de echte code leest een titel-element en een
// data-testid="color_code_…". Meer heeft colourOptionLabel niet nodig.
function maakTegel([naam, code]) {
  const el = {
    _naam: naam,
    textContent: naam,
    querySelector(sel) {
      if (sel.includes("color_code_")) return { dataset: { testid: "color_code_" + code } };
      if (sel.includes("Cell__title")) return { textContent: naam };
      return null;
    },
  };
  return el;
}

// De stukken uit vinted.js die over de kleurkeuze gaan, zonder de rest van het
// bestand (dat verwacht een echte browser). We knippen op functienamen, zodat
// dit de echte code blijft en geen kopie die uit de pas kan lopen.
function laadZoeker(bron) {
  const stukken = [];
  const pak = (naam, soort) => {
    const start = bron.indexOf(`  ${soort} ${naam}`);
    if (start === -1) return false;
    // Tot en met de sluitende accolade op inspringniveau twee.
    const eind = bron.indexOf("\n  }\n", start);
    if (eind === -1) return false;
    stukken.push(bron.slice(start, eind + 5));
    return true;
  };
  const pakConst = (naam) => {
    const start = bron.indexOf(`  const ${naam} = {`);
    if (start === -1) return false;
    const eind = bron.indexOf("\n  };\n", start);
    if (eind === -1) return false;
    stukken.push(bron.slice(start, eind + 6));
    return true;
  };
  pakConst("COLOUR_MAP");
  pakConst("AFWERKING_MAP");           // bestaat alleen in de nieuwe versie
  pak("colourOptionLabel", "function");
  pak("woordTreffer", "function");     // bestaat alleen in de nieuwe versie
  pak("findColourOption", "function");
  pak("kaartKleur", "function");       // bestaat pas sinds 29-09-2026
  pak("parseColours", "function");

  const zand = { console: { log() {} } };
  vm.createContext(zand);
  vm.runInContext(
    "(function(){\n" + stukken.join("\n") +
    "\n; this.findColourOption = findColourOption; this.parseColours = parseColours;" +
    "}).call(this);",
    zand, { filename: "vinted-kleur.js" });
  return zand;
}


const zoeker = laadZoeker(fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8"));
const tegels = VINTED_TEGELS.map(maakTegel);
console.log("Elke kleur van het keuzemenu op zijn Vinted-tegel\n");
check("de lijst heeft 29 kleuren", KLEUREN.length === 29);
for (const [en, nl, code] of KLEUREN) {
  const gewenst = zoeker.parseColours({ color: en, title: "" });
  const tegel = gewenst.length ? zoeker.findColourOption(gewenst[0], tegels) : null;
  const gekregen = tegel ? tegel.querySelector("color_code_").dataset.testid.replace("color_code_", "") : "(niets)";
  check(`${en} landt op ${code}`, gekregen === code, `kreeg ${gekregen}`);
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
