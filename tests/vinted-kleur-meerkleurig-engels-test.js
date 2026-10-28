/**
 * "Meerkleurig" moet ook op een Engelstalige Vinted-pagina op de tegel VARIOUS
 * landen. Daar heet die tegel "Multi", in de lijstvorm zonder kleurcode.
 *
 * Aanleiding: 45f9caba (27-10-2026), kerstbeeld met kleur Meerkleurig:
 * "colour (Meerkleurig — "Meerkleurig" was not in Vinted's list of 30 colours
 * (multi, black, grey, ...))". COLOUR_MAP kende "meerkleurig" niet, dus de zoeker
 * zocht het Nederlandse woord tussen Engelse tegels. Op 1.0.404 faalt deze proef.
 *
 * Draaien: node tests/vinted-kleur-meerkleurig-engels-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Een tegel met de zichtbare naam en eventueel Vinteds code (rastervorm).
function maakRij(tekst, code) {
  return {
    _naam: tekst,
    textContent: tekst,
    querySelector(sel) {
      if (sel.includes("Cell__title")) return { textContent: tekst };
      if (code && sel.includes("color_code_")) return { dataset: { testid: "color_code_" + code } };
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

const ENGELS = ["Multi", "Black", "Grey", "White", "Cream", "Beige", "Red", "Blue"];
const vormen = {
  "Engelse lijstvorm zonder code": ENGELS.map((t) => maakRij(t)),
  "Engelse rastervorm met code": ENGELS.map((t) => maakRij(t, t === "Multi" ? "VARIOUS" : t.toUpperCase())),
  "Nederlandse lijstvorm zonder code": ["Meerkleurig", "Zwart", "Grijs", "Wit"].map((t) => maakRij(t)),
};
const zoeker = laadZoeker(fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8"));
for (const [vorm, rijen] of Object.entries(vormen)) {
  console.log(vorm);
  const doel = rijen[0]._naam;
  for (const kleur of ["Meerkleurig", "meerkleurig", "Multicolour", "Various"]) {
    const gewenst = zoeker.parseColours({ color: kleur, title: "" });
    const rij = gewenst.length ? zoeker.findColourOption(gewenst[0], rijen) : null;
    check(`"${kleur}" landt op ${doel}`, rij && rij._naam === doel, `kreeg ${rij ? rij._naam : "(niets)"}`);
  }
  const zwart = zoeker.findColourOption(zoeker.parseColours({ color: "Zwart", title: "" })[0], rijen);
  check(`"Zwart" blijft op ${rijen[1]._naam}`, zwart && zwart._naam === rijen[1]._naam);
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
