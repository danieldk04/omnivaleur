/**
 * Vinted tekent de kleurkiezer soms als lijst met aanvinkvakjes. Die rijen hebben
 * GEEN color_code_…, alleen de Nederlandse naam ("Zilver"). Elke kleur uit het
 * keuzemenu moet daar toch op zijn eigen rij landen.
 *
 * Aanleiding: Janneke (31d28378, 08-10-2026), kinderlaarzen in Zilver:
 * "colour (Silver — none of the colour tiles responded to a click)". Op de
 * versie vóór 1.0.375 vindt de zoeker in deze vorm geen enkele kleur.
 *
 * Draaien: node tests/vinted-kleur-lijstvorm-nl-test.js
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

// Een rij zoals de lijstvorm hem tekent: titel-element met de Nederlandse naam,
// geen kleurbolletje en dus geen code.
function maakRij(nl) {
  return {
    _naam: nl,
    textContent: nl,
    querySelector(sel) {
      if (sel.includes("Cell__title")) return { textContent: nl };
      return null;
    },
  };
}

function laadZoeker(bron) {
  const stukken = [];
  const pak = (naam) => {
    const start = bron.indexOf(`  function ${naam}`);
    if (start === -1) return;
    const eind = bron.indexOf("\n  }\n", start);
    stukken.push(bron.slice(start, eind + 5));
  };
  const pakConst = (naam) => {
    const start = bron.indexOf(`  const ${naam} = {`);
    if (start === -1) return;
    const eind = bron.indexOf("\n  };\n", start);
    stukken.push(bron.slice(start, eind + 6));
  };
  pakConst("COLOUR_MAP");
  pakConst("AFWERKING_MAP");
  ["colourOptionLabel", "woordTreffer", "findColourOption", "kaartKleur", "parseColours"].forEach(pak);
  const zand = { console: { log() {} } };
  vm.createContext(zand);
  vm.runInContext("(function(){\n" + stukken.join("\n") +
    "\n; this.findColourOption = findColourOption; this.parseColours = parseColours;" +
    "}).call(this);", zand, { filename: "vinted-kleur.js" });
  return zand;
}

const rijen = KLEUREN.map(([, nl]) => maakRij(nl));
const zoeker = laadZoeker(fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8"));
console.log("Lijstvorm zonder kleurcode, Nederlandse namen\n");
for (const [en, nl] of KLEUREN) {
  const gewenst = zoeker.parseColours({ color: en, title: "" });
  const rij = gewenst.length ? zoeker.findColourOption(gewenst[0], rijen) : null;
  check(`${en} landt op ${nl}`, rij && rij._naam === nl, `kreeg ${rij ? rij._naam : "(niets)"}`);
}
// De kleur zoals hij uit Shopify of het dashboard in het Nederlands komt.
for (const [woord, nl] of [["zilver", "Zilver"], ["zwart", "Zwart"], ["grijs", "Grijs"]]) {
  const gewenst = zoeker.parseColours({ color: woord, title: "" });
  const rij = gewenst.length ? zoeker.findColourOption(gewenst[0], rijen) : null;
  check(`"${woord}" landt op ${nl}`, rij && rij._naam === nl, `kreeg ${rij ? rij._naam : "(niets)"}`);
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
