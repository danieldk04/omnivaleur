/**
 * Toon (dejuistetoon), 03-09-2026 — kleuren die Marktplaats niet herkent.
 *
 * Zijn kast telt 1.024 artikelen met 59 verschillende kleurwaarden, opgeschreven
 * zoals een mens dat doet: "bruine", "zwarte", "rode", "lichtblauw", "crème",
 * "olijfgroene", "Beige bruin", "divers". Marktplaats biedt in zijn Kleur-lijst
 * alleen de kale grondvorm aan (Zwart, Wit, Grijs, Beige, Bruin, Rood, Bordeaux,
 * Roze, Oranje, Geel, Groen, Blauw, Paars, Goud, Multicolour).
 *
 * De oude vertaaltabel ging alleen van Engels naar Nederlands, dus "bruine" ging
 * er ongewijzigd doorheen, matchte op geen enkele optie en liet het verplichte
 * veld leeg. Een leeg kenmerkveld betekent bij Marktplaats geen advertentie
 * (gemeten 21-08-2026). Geteld over Toons eigen kast: 217 van de 1.024.
 *
 * Deze test draait de ECHTE code uit shared.js tegen die 59 echte waarden, en
 * doet dat twee keer: één keer met de versie zoals hij nu in de map staat, en
 * één keer met de versie van vóór de reparatie (uit git). Zonder die tweede
 * ronde weet je alleen dat de nieuwe code werkt, niet dat ze iets repareert.
 *
 * Draaien: node tests/kleur-en-maat-terugval-test.js
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

// ── De kleuren die Toon echt in zijn kast heeft, met hun aantallen ────────
// Geteld op 03-09-2026 uit zijn 1.024 artikelen.
const TOON_KLEUREN = [
  ["rood",81],["bruin",78],["beige",52],["ecru",52],["bruine",41],["groen",41],
  ["zwart",30],["roze",28],["blauw",27],["zwarte",20],["oranje",19],["grijs",18],
  ["rode",16],["taupe",16],["groene",15],["geel",15],["crème",13],["paars",11],
  ["witte",10],["goud",9],["wit",9],["lichtblauw",7],["bordeaux",7],["blauwe",7],
  ["Bruin",5],["khaki",5],["olijfgroene",4],["zalm",4],["donkerblauw",4],
  ["olijfgroen",4],["Meerkleurig",4],["Wit",3],["paarse",3],["grijze",3],
  ["camel",2],["gouden",2],["gele",2],["donkergroene",2],["Rood",2],
  ["donkergroen",2],["Blauw",1],["mint",1],["Beige bruin",1],["donkergrijs",1],
  ["kaki",1],["Zwart, Rood",1],["lichtblauwe",1],["lila",1],["red",1],
  ["bruin olijfgroen",1],["Zwart",1],["Donkergroen zwart",1],["Kleurrijk",1],
  ["Taupe",1],["Bruin taupe",1],["divers",1],["Ecru",1],["Grijs",1],["marine",1],
];

// Wat Marktplaats in de Kleur-lijst aanbiedt. Let op: het veld heet per
// categorie anders (plaidsKleur, …) en de lijst verschilt. "Meerkleurig" is
// gemeten op 03-09-2026 aan Toons eigen live advertentie in "plaids en
// woondekens" — daar heet de optie NIET "Multicolour". Vandaar dat de extensie
// altijd uit de echte lijst kiest en meerdere schrijfwijzen langsgaat.
const MP_KLEUREN = ["Zwart","Grijs","Wit","Beige","Bruin","Rood","Bordeaux",
                    "Roze","Oranje","Geel","Groen","Blauw","Paars","Goud",
                    "Zilver","Meerkleurig"];

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

function meet(CL, opties) {
  let ok = 0, leeg = 0, artikelenLeeg = 0, artikelenOk = 0;
  const missers = [];
  for (const [waarde, aantal] of TOON_KLEUREN) {
    const { veldwaarde } = vulKleur(CL, waarde, opties);
    if (veldwaarde) { ok++; artikelenOk += aantal; }
    else { leeg++; artikelenLeeg += aantal; missers.push(`${waarde} (${aantal}x)`); }
  }
  return { ok, leeg, artikelenOk, artikelenLeeg, missers };
}

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
const bronOud = execSync("git show aa82f8b^:extension/content/shared.js", { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

const CLnu = laadCL(bronNu);
const CLoud = laadCL(bronOud);

console.log("Marktplaats-kleurlijst:", MP_KLEUREN.join(", "), "\n");

const oud = meet(CLoud, MP_KLEUREN);
const nu = meet(CLnu, MP_KLEUREN);

console.log("VOOR de reparatie (versie 1.0.280 — wat Toon draaide toen het misging)");
console.log(`  ${oud.leeg} van de ${TOON_KLEUREN.length} kleurwaarden lieten het veld leeg`);
console.log(`  dat raakt ${oud.artikelenLeeg} van Toons 1024 artikelen`);
console.log(`  bijvoorbeeld: ${oud.missers.slice(0, 12).join(", ")}`);

console.log("\nNA de reparatie");
console.log(`  ${nu.leeg} van de ${TOON_KLEUREN.length} kleurwaarden laten het veld leeg`);
console.log(`  dat raakt ${nu.artikelenLeeg} van Toons 1024 artikelen`);
if (nu.missers.length) console.log(`  namelijk: ${nu.missers.join(", ")}`);

console.log("\nDe voor-en-na-proef");
check("de oude code liet aantoonbaar kleurvelden leeg", oud.artikelenLeeg > 0,
  "dan bewijst deze test niets — de opzet klopt niet");
check("de nieuwe code lost er echt iets van op", nu.artikelenLeeg < oud.artikelenLeeg);
check("geen enkele kleurwaarde blijft meer leeg", nu.leeg === 0,
  `blijft staan: ${nu.missers.join(", ")}`);

console.log("\nWat er per geval gekozen wordt");
for (const [waarde, verwacht] of [
  ["bruine", "Bruin"], ["zwarte", "Zwart"], ["rode", "Rood"], ["witte", "Wit"],
  ["gele", "Geel"], ["grijze", "Grijs"], ["gouden", "Goud"], ["paarse", "Paars"],
  ["lichtblauw", "Blauw"], ["donkerblauw", "Blauw"], ["olijfgroene", "Groen"],
  ["donkergroen", "Groen"], ["crème", "Wit"], ["ecru", "Wit"], ["taupe", "Beige"],
  ["camel", "Beige"], ["marine", "Blauw"], ["zalm", "Roze"], ["lila", "Paars"],
  ["kaki", "Groen"], ["khaki", "Groen"], ["mint", "Groen"],
  ["Meerkleurig", "Meerkleurig"], ["Kleurrijk", "Meerkleurig"],
  ["divers", "Meerkleurig"], ["Beige bruin", "Beige"], ["Bruin taupe", "Bruin"],
  ["Zwart, Rood", "Zwart"], ["bruin olijfgroen", "Bruin"],
  ["Donkergroen zwart", "Groen"], ["red", "Rood"], ["bordeaux", "Bordeaux"],
]) {
  const { veldwaarde } = vulKleur(CLnu, waarde, MP_KLEUREN);
  check(`"${waarde}" → ${verwacht}`, veldwaarde === verwacht, `koos "${veldwaarde}"`);
}

console.log("\nEen categorie met een kortere lijst (geen Bordeaux, geen Multicolour)");
const kort = ["Zwart", "Wit", "Grijs", "Bruin", "Blauw", "Groen", "Rood", "Overige"];
for (const [waarde, verwacht] of [
  ["bordeaux", "Rood"], ["divers", "Overige"], ["Meerkleurig", "Overige"],
  ["beige", "Bruin"], ["taupe", "Bruin"],
]) {
  const { veldwaarde } = vulKleur(CLnu, waarde, kort);
  check(`"${waarde}" → ${verwacht}`, veldwaarde === verwacht, `koos "${veldwaarde}"`);
}

console.log("\nNiets verzinnen als er niets past");
const geenKleuren = ["Katoen", "Wol", "Linnen"];
const leeg = vulKleur(CLnu, "bruine", geenKleuren);
check("een lijst zonder enige kleur blijft leeg", leeg.veldwaarde === "",
  `koos "${leeg.veldwaarde}" uit een lijst met alleen stoffen`);


// ── Maten met een getal erin ─────────────────────────────────────────────
// Vinted schrijft kindermaten als "10 jaar / 140 cm"; Marktplaats biedt
// "Maat 140" aan. Toon heeft er vijftien van dat soort.
console.log("\nMaten met een getal erin");
function vulMaat(CL, waarde, opties) {
  const el = maakSelect(opties);
  const proxy = new Proxy(el, {
    get(t, k) { return k === "value" ? (t._v || "") : t[k]; },
    set(t, k, v) { if (k === "value") t._v = v; else t[k] = v; return true; },
  });
  for (const v of CL.valueVariants ? CL.valueVariants(waarde) : [waarde]) {
    if (CL.fillNativeSelect(proxy, v)) break;
  }
  return el._v || "";
}
const KINDERMATEN = ["Maat 98","Maat 104","Maat 116","Maat 134","Maat 140",
                     "Maat 152","Maat 158","Maat 164","Overige maten"];
for (const [waarde, verwacht] of [
  ["10 jaar / 140 cm", "Maat 140"], ["3 jaar / 98 cm", "Maat 98"],
  ["12 jaar / 152 cm", "Maat 152"], ["14 jaar / 164 cm", "Maat 164"],
]) {
  check(`"${waarde}" → ${verwacht}`, vulMaat(CLnu, waarde, KINDERMATEN) === verwacht,
    `koos "${vulMaat(CLnu, waarde, KINDERMATEN)}"`);
  check(`"${waarde}" lukte vóór de reparatie niet`,
    vulMaat(CLoud, waarde, KINDERMATEN) !== verwacht);
}
// Het kale getal is een grove sleutel en mag nooit voorgaan op iets beters.
const VOLWASSEN = ["Maat 36 (S)","Maat 38 (M)","Maat 40 (M)","Maat 42 (L)","Overige maten"];
check('"M / 38 / 10" kiest nog steeds op de maat zelf',
  vulMaat(CLnu, "M / 38 / 10", VOLWASSEN) === "Maat 38 (M)",
  `koos "${vulMaat(CLnu, "M / 38 / 10", VOLWASSEN)}"`);
check('"40 x 40 cm" (een kussen) pakt geen kledingmaat uit een lijst zonder cm',
  vulMaat(CLnu, "40 x 40 cm", ["Rond","Vierkant","Rechthoekig"]) === "");

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
