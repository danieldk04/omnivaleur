/**
 * Vinted en verbogen kleurnamen (29-09-2026, Vagif).
 *
 * Van zijn 86 sieraden hebben er 51 als kleur "zilveren" en een "gele". De
 * Vinted-kaart in vinted.js kende alleen "zilver", dus parseColours gaf
 * "zilveren" ongewijzigd door, en geen enkele Vinted-tegel ("Zilver" /
 * color_code_SILVER) heet zo: het verplichte kleurveld bleef leeg en de
 * plaatsing liep vast. Voor Marktplaats en 2dehands kende shared.js die vormen
 * al (CL.dutchColor: "zilveren" → Zilver, "gele" → Geel); vinted.js gebruikte
 * dat niet.
 *
 * Draait de ECHTE shared.js en de ECHTE parseColours uit vinted.js, en dezelfde
 * functie uit de versie van vóór de reparatie (vaste commit, niet HEAD).
 *
 * Draaien: node tests/vinted-kleur-verbogen-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const OUD = "84849c5e";

// shared.js zoals Chrome hem vóór vinted.js in de pagina laadt. Klokken staan
// uit: die zijn voor de pagina, niet voor deze proef.
function laadShared() {
  const nep = () => new Proxy(function () {}, {
    get: (_t, k) => (k === Symbol.toPrimitive ? () => "" : nep()),
    apply: () => nep(),
  });
  const niets = () => 0;
  const ctx = {
    console, URL, setTimeout: niets, clearTimeout: niets, setInterval: niets, clearInterval: niets,
    location: { href: "https://www.vinted.nl/items/new", hostname: "www.vinted.nl" },
    document: nep(), chrome: nep(), navigator: { userAgent: "proef" },
    MutationObserver: function () { return { observe() {}, disconnect() {} }; },
  };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx;
  vm.runInNewContext(fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8"), ctx);
  return ctx.CL;
}

function laad(bron, CL) {
  const kaart = bron.match(/const COLOUR_MAP = \{[\s\S]*?\n  \};/)[0];
  const hulp = (bron.match(/function kaartKleur\(w\) \{[\s\S]*?\n  \}\n/) || [""])[0];
  const functie = bron.match(/function parseColours\(item\) \{[\s\S]*?\n  \}\n/)[0];
  const ctx = { CL };
  vm.runInNewContext(`${kaart}\n${hulp}\n${functie}\nthis.parseColours = parseColours;`, ctx);
  return ctx.parseColours;
}

const CL = laadShared();
const nieuw = laad(fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8"), CL);
const oud = laad(execSync(`git show ${OUD}:extension/content/vinted.js`, { cwd: WORTEL }).toString(), CL);

// Vinteds eigen tegelcodes (GET /api/v2/item_upload/colors, 21-09-2026; zie
// tests/vinted-kleur-afwerking-test.js). Alleen wat hier nodig is.
const TEGELS = { Silver: "SILVER", Yellow: "YELLOW", Gold: "GOLD", Red: "RED", White: "WHITE" };

let mislukt = 0;
function check(naam, ok, uitleg) {
  console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}${ok || !uitleg ? "" : " — " + uitleg}`);
  if (!ok) mislukt++;
}

// Echte waarden uit Vagifs voorraad (kleurveld, titel) en wat Vinted moet krijgen.
const GEVALLEN = [
  [{ color: "zilveren", title: "Zilveren armband met echte robijn (925 zilver)" }, "Silver"],
  [{ color: "zilveren", title: "Nieuwe Zilveren Ketting zilver 925" }, "Silver"],
  [{ color: "zilver", title: "Zilver 925 Sieradenset met Zultaniet" }, "Silver"],
  [{ color: "gele", title: "Amber tesbih / Misbaha pressed amber" }, "Yellow"],
  [{ color: "gouden", title: "Gouden ring" }, "Gold"],
  [{ color: null, title: "Zilveren oorbellen met zirkonia" }, "Silver"],
  // Wat al goed ging, moet goed blijven.
  [{ color: null, title: "Nieuwe Robijn Ketting met Natuurlijke Steentjes" }, "Red"],
  [{ color: "wit", title: "Witte blouse" }, "White"],
];

console.log("Nieuwe versie:");
for (const [item, verwacht] of GEVALLEN) {
  const uit = nieuw(item);
  check(`${item.color ?? "(leeg)"} / "${item.title}" → ${verwacht}`, uit[0] === verwacht,
        `kreeg ${JSON.stringify(uit)}`);
  check(`  ${verwacht} is een echte Vinted-tegel`, !!TEGELS[verwacht]);
}
check("een onbekend woord blijft zoals het is (nooit een verzonnen kleur)",
      JSON.stringify(nieuw({ color: "Sunburst", title: "" })) === JSON.stringify(["Sunburst"]));
check("zonder kleur en zonder kleurwoord in de titel: leeg, niet geraden",
      nieuw({ color: null, title: "Elegante Zoetwater Parel Ketting" }).length === 0);

console.log("Oude versie (" + OUD + ") moet falen op de verbogen vormen:");
check("oud gaf 'zilveren' ongewijzigd door", oud({ color: "zilveren", title: "" })[0] === "zilveren");
check("oud gaf 'gele' ongewijzigd door", oud({ color: "gele", title: "" })[0] === "gele");

console.log(mislukt ? `\n${mislukt} FOUT` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
