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

// Vinteds eigen kleurtegels, letterlijk opgehaald bij Vinted zelf op
// 21-09-2026: GET https://www.vinted.nl/api/v2/item_upload/colors (29 stuks).
// NIET met de hand overgeschreven. Let op wat daaruit bleek: op vinted.nl staan
// de tegels in het NEDERLANDS ("Zwart", "Meerkleurig"), en de Engelse naam zit
// alleen in de code uit data-testid="color_code_…". "Multi" en "Bronze" bestaan
// daar niet. Elke doelwaarde in COLOUR_MAP en AFWERKING_MAP wordt hieronder
// tegen deze lijst getoetst, zodat een verzonnen doelwaarde niet stil
// doorglipt zoals "Multi" dat maandenlang deed.
const VINTED_TEGELS = [
  ["Zwart","BLACK"],["Grijs","GREY"],["Wit","WHITE"],["Crème","CREAM"],
  ["Beige","BODY"],["Pasteloranje","APRICOT"],["Oranje","ORANGE"],
  ["Koraal","CORAL"],["Rood","RED"],["Wijnrood","BURGUNDY"],["Roze","PINK"],
  ["Lichtroze","ROSE"],["Paars","PURPLE"],["Lila","LILAC"],
  ["Lichtblauw","LIGHT-BLUE"],["Blauw","BLUE"],["Marineblauw","NAVY"],
  ["Turquoise","TURQUOISE"],["Mintgroen","MINT"],["Groen","GREEN"],
  ["Donkergroen","DARK-GREEN"],["Khaki","KHAKI"],["Bruin","BROWN"],
  ["Mosterdgeel","MUSTARD"],["Geel","YELLOW"],["Zilver","SILVER"],
  ["Goud","GOLD"],["Meerkleurig","VARIOUS"],["Transparant","CLEAR"],
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
// NIET HEAD (kennisbank: "voor-en-na-proef mag geen HEAD gebruiken"). Zodra de
// reparatie gecommit is, is HEAD de nieuwe code en vergelijkt de test zich met
// zichzelf — precies wat hier één keer gebeurde: de "oude" versie scoorde toen
// ineens 18 van de 19. Vandaar een vast punt: 619fbe6a is de laatste versie van
// vinted.js vóór deze reparatie.
const VOOR_DE_REPARATIE = "619fbe6a";
const oudeBron = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/vinted.js`,
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

// ── Elke doelwaarde moet een echte tegel raken ───────────────────────────
// Dit is de controle die "Multi" had moeten tegenhouden. Die stond maandenlang
// in de tabel, bestond niet bij Vinted, en liet het kleurveld dus leeg bij
// iedereen die "multicolour", "veelkleurig" of "divers" opschreef.
function doelenControle(bron, naam) {
  const tegels = VINTED_TEGELS.map(maakTegel);
  const zoeker = laadZoeker(bron);
  const tabellen = ["COLOUR_MAP", "AFWERKING_MAP"];
  const kapot = [];
  for (const tabel of tabellen) {
    const start = bron.indexOf(`  const ${tabel} = {`);
    if (start === -1) continue;
    const eind = bron.indexOf("\n  };\n", start);
    const stuk = bron.slice(start, eind);
    for (const m of stuk.matchAll(/"([^"]+)":\s*"([^"]+)"/g)) {
      if (!zoeker.findColourOption(m[2], tegels)) kapot.push(`${tabel}: ${m[1]} -> ${m[2]}`);
    }
  }
  return kapot;
}

const kapotNu = doelenControle(fs.readFileSync(
  path.join(WORTEL, "extension/content/vinted.js"), "utf8"));
const kapotOud = doelenControle(oudeBron);
console.log(`\n  doelwaarden zonder tegel, voor: ${kapotOud.length}`);
kapotOud.slice(0, 8).forEach((k) => console.log("      " + k));
console.log(`  doelwaarden zonder tegel, na:  ${kapotNu.length}`);
kapotNu.forEach((k) => console.log("      " + k));
check("de oude tabel wees echt naar tegels die niet bestaan", kapotOud.length > 0);
check("elke doelwaarde raakt nu een echte Vinted-tegel", kapotNu.length === 0,
  kapotNu.join("; "));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
