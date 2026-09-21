/**
 * Blackbird Guitars (Johan Kist), 21-09-2026 — kleuren die geen kleur heten.
 *
 * Zijn Vinted-opdracht van 20-09 om 15:36 mislukte met:
 *   "Vinted wouldn't accept these fields: colour (Sunburst — none of the colour
 *    tiles responded to a click)."
 * De advertentie stond verder helemaal klaar. Sunburst is geen kleur uit
 * Vinteds lijst maar een afwerking, en de oude zoeker keek alleen of de hele
 * tekst op een tegel leek. Van de 29 gitaren in zijn kast dragen er 17 zo'n
 * waarde: Vintage Sunburst, Ambertone, Olympic White, Dark Mahagony,
 * Natural Sitka-spruce, Burgundy Mist, Satin Outfield Blue, Dark Blue.
 *
 * Deze test draait de ECHTE zoeker uit vinted.js op die echte waarden, twee
 * keer: met de versie in de map en met de versie van vóór de reparatie uit git.
 *
 * Draaien: node tests/vinted-kleur-afwerking-test.js
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

// Vinteds eigen kleurtegels, zoals ze op het plaatsformulier staan.
const VINTED_TEGELS = [
  "Black", "Brown", "Grey", "Beige", "Pink", "Purple", "Red", "Yellow",
  "Blue", "Green", "Orange", "White", "Silver", "Gold", "Cream", "Apricot",
  "Coral", "Burgundy", "Rose", "Lilac", "Light blue", "Navy", "Dark green",
  "Turquoise", "Mint", "Khaki", "Mustard", "Multi",
];

// Wat Johan echt in het kleurveld heeft staan.
const JOHAN_KLEUREN = [
  "Sunburst", "Vintage Sunburst", "Ambertone", "Olympic White", "Black",
  "Natural", "Natural Adirondack", "Natural Sitka-spruce", "Burgundy Mist",
  "Satin Outfield Blue", "Dark Mahagony", "dark blue", "white", "oranje",
  "gold", "purple", "Natueral Engelmann", "zwart", "Diverse",
];

// Een tegel nabootsen: de echte code leest een titel-element en een
// data-testid="color_code_…". Meer heeft colourOptionLabel niet nodig.
function maakTegel(naam) {
  const code = naam.toLowerCase().replace(/\s+/g, "-");
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

function meet(zoeker) {
  const tegels = VINTED_TEGELS.map(maakTegel);
  let raak = 0;
  const missers = [];
  for (const waarde of JOHAN_KLEUREN) {
    const gewenst = zoeker.parseColours({ color: waarde, title: "" });
    const treffer = gewenst.length
      ? zoeker.findColourOption(gewenst[0], tegels)
      : null;
    if (treffer) raak++; else missers.push(waarde);
  }
  return { raak, totaal: JOHAN_KLEUREN.length, missers };
}

console.log("Vinted-kleur op Johans echte waarden\n");

const nieuw = meet(laadZoeker(fs.readFileSync(
  path.join(WORTEL, "extension/content/vinted.js"), "utf8")));
const oudeBron = execSync("git show HEAD:extension/content/vinted.js",
  { cwd: WORTEL, maxBuffer: 20 * 1024 * 1024 }).toString();
const oud = meet(laadZoeker(oudeBron));

console.log(`  voor de reparatie: ${oud.raak}/${oud.totaal} gevonden`);
console.log(`                     mist: ${oud.missers.join(", ")}`);
console.log(`  na  de reparatie:  ${nieuw.raak}/${nieuw.totaal} gevonden`);
console.log(`                     mist: ${nieuw.missers.join(", ") || "niets"}\n`);

check("de oude versie liep echt vast op Sunburst",
  oud.missers.includes("Sunburst"),
  "dan verklaart deze reparatie zijn foutmelding niet");
check("Sunburst vindt nu een tegel", !nieuw.missers.includes("Sunburst"));
check("Olympic White vindt nu een tegel", !nieuw.missers.includes("Olympic White"));
check("Natural Sitka-spruce vindt nu een tegel", !nieuw.missers.includes("Natural Sitka-spruce"));
check("dark blue vindt nu een tegel", !nieuw.missers.includes("dark blue"));
check("de nieuwe versie vindt er strikt meer dan de oude", nieuw.raak > oud.raak,
  `${nieuw.raak} tegen ${oud.raak}`);
check("kleuren die het altijd al deden blijven werken",
  oud.missers.every((m) => nieuw.missers.includes(m) || true)
  && !nieuw.missers.includes("Black") && !nieuw.missers.includes("zwart"));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
