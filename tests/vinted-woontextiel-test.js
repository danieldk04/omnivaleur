/**
 * De Juiste Toon, 16-10-2026: "blijft mislukken als ik nieuwe adv wil plaatsen".
 *
 * Geen enkele Vinted-plaatsing van hem lukte ooit (19 van 19 mislukt). Ruim 900
 * van zijn artikelen zijn kleden, dekens en tafelkleden, en zijn Vinted staat in
 * het Nederlands. Twee meldingen bij dezelfde soort deken:
 *   "Kies een subcategorie"   en   "Vinted wouldn't accept these fields: size (empty)".
 *
 * Gemeten op vinted.nl (16-10): woontextiel had geen vast pad (V_PAD), dus liep
 * het via het zoekvak met het Engelse "blanket", en dan koos Vinted zelf uit de
 * foto's. En de juiste rubriek, Home > Textiel > Dekens, heeft een VERPLICHTE
 * maat: "70 x 90 cm" … "150 x 200 cm" en "Overige". Kussens ook; vloerkleden,
 * tafelkleden en wandtapijten niet.
 *
 * Deze proef draait de echte categoriekeuze uit vinted.js tegen Vinteds eigen
 * Nederlandse boom (harnas uit vinted-elke-taal-test.js), oud tegen nieuw, en de
 * maatkeuze tegen de gemeten maatlijsten.
 *
 * Draaien: node tests/vinted-woontextiel-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const NIEUW = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
// Vaste commit van vóór deze reparatie, geen HEAD (auto-push-hook).
const VOOR = "92f566e2";
const OUD = execFileSync("git", ["show", `${VOOR}:extension/content/vinted.js`], { cwd: WORTEL }).toString();

// Het nagebouwde Vinted (boom, kiezer, draai) uit de proef van 15-10, ongewijzigd.
const HARNAS = fs.readFileSync(path.join(WORTEL, "tests", "vinted-elke-taal-test.js"), "utf8");
const harnas = HARNAS.slice(HARNAS.indexOf("const boomUit"), HARNAS.indexOf("(async () => {"))
  .replace(/^let mislukt = 0;[\s\S]*?^}\n/m, "");
const H = new Function("fs", "path", "vm", "WORTEL",
  harnas + "\nreturn { maakKiezer, draai, idVoorEngelsPad, engels, isBlad, blokUit };")(fs, path, vm, WORTEL);

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function maatKiezer(bron) {
  const s = {};
  vm.createContext(s);
  vm.runInContext([
    H.blokUit(bron, "function afmetingUitTekst("),
    H.blokUit(bron, "function kiesAfmetingOptie("),
    "globalThis.__kies = (labels, item) => { const i = kiesAfmetingOptie(labels, afmetingUitTekst(item)); return i < 0 ? null : labels[i]; };",
  ].join("\n"), s);
  return s.__kies;
}

(async () => {
  // Wat Vinted uit de foto van een gehaakte deken kan raden: een kinderslaapzak.
  const SLAAPZAK = H.idVoorEngelsPad(["Kids", "Sleep & bedding", "Sleep sacks & wearable blankets"]);
  const gevallen = [
    ["wonen plaids en woondekens", "Zigzag Granny Deken 180/125", "Home > Textiles > Blankets"],
    ["wonen tapijten en kleden", "Granny vloerkleed 200/140", "Home > Textiles > Rugs & mats > Rugs"],
    ["wonen vachten", "Koeienhuid vacht 210/190", "Home > Textiles > Rugs & mats > Rugs"],
    ["wonen tafelkleden", "Elegant gehaakt kleed 100/100", "Home > Textiles > Table linen > Tablecloths"],
    ["wonen kussens", "Gehaakt kussen 45/45", "Home > Textiles > Cushions"],
    // Gemengde rubrieken: op het soort woord in Toons eigen titels.
    ["antiek kleden en textiel", "Perzisch handgeknoopt tapijt 135/85m", "Home > Textiles > Rugs & mats > Rugs"],
    ["antiek kleden en textiel", "Vintage wollen Smyrna wandkleed 36/26 cm", "Home > Textiles > Tapestries"],
    ["antiek kleden en textiel", "Vintage brocante tafelkleed antiek bloemen pa", "Home > Textiles > Table linen > Tablecloths"],
    ["wonen wanddecoraties", "Leuk wandkleed met franjes 147/77 cm", "Home > Textiles > Tapestries"],
    ["wonen wanddecoraties", "Rode Handgeweven Kelim - Wandkleed / Tafellop", "Home > Textiles > Tapestries"],
  ];
  console.log("Categorie op een Nederlandse Vinted, Vinted raadt een kinderslaapzak:");
  for (const [cat, titel, verwacht] of gevallen) {
    const item = { title: titel, description: "", category: cat, gender: "" };
    const nu = await H.draai(NIEUW, H.maakKiezer("nl", [SLAAPZAK]), item);
    const was = await H.draai(OUD, H.maakKiezer("nl", [SLAAPZAK]), item);
    check(`${cat}: ${H.engels(nu.id)}`, H.engels(nu.id) === verwacht && H.isBlad(nu.id), `verwacht ${verwacht}`);
    check(`  oud koos niet ${verwacht} (${H.engels(was.id)})`, H.engels(was.id) !== verwacht,
          "de oude versie deed het al goed, dan bewijst deze proef niets");
  }

  // De maatlijsten zoals vinted.nl ze op 16-10-2026 toonde.
  const DEKENS = ["70 x 90 cm", "80 x 100 cm", "90 x 90 cm", "100 x 150 cm", "110 x 150 cm", "110 x 170 cm",
                  "120 x 160 cm", "125 x 150 cm", "130 x 170 cm", "150 x 200 cm", "Overige"];
  const KUSSENS = ["30 x 50 cm", "35 x 50 cm", "40 x 40 cm", "40 x 60 cm", "45 x 45 cm", "50 x 50 cm",
                   "60 x 60 cm", "65 x 65 cm", "Overige"];
  const KLEDING = ["XS", "S", "M", "L", "XL", "Overige"];
  const kies = maatKiezer(NIEUW);
  console.log("Maat bij een artikel zonder maat:");
  for (const [labels, titel, verwacht] of [
    [DEKENS, "Zigzag Granny Deken 180/125", "Overige"],
    [DEKENS, "Granny-square Bruintinten 200/140", "Overige"],
    [DEKENS, "Grote Granny Woondeken 220/220cm", "Overige"],
    [DEKENS, "Wollen deken 150x200", "150 x 200 cm"],
    [DEKENS, "Wollen deken 200/150", "150 x 200 cm"],
    [DEKENS, "Plaid 130 x 170 cm", "130 x 170 cm"],
    [DEKENS, "Gehaakte deken roze", "Overige"],
    [KUSSENS, "Gehaakt kussen 45/45", "45 x 45 cm"],
    [KLEDING, "Trui zonder maat", null],
  ]) {
    const uit = kies(labels, { title: titel, description: "" });
    check(`${titel} → ${uit}`, uit === verwacht, `verwacht ${verwacht}`);
  }
  check("oude versie kende geen maat uit de afmeting", !OUD.includes("function kiesAfmetingOptie("));

  console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
