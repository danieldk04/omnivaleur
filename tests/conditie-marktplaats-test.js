/**
 * Daniel, 04-09-2026 — de staat op Marktplaats klopte niet met wat er in
 * Omnivaleur stond.
 *
 * Wat hij zag. Advertentie (1357) "Lilac Profuomo Shirt - Men 45 - New With
 * Tags" stond in het dashboard op "New with tags" en op marktplaats.nl onder
 * Kenmerken als "Conditie: Zo goed als nieuw".
 *
 * Waarom dat gebeurde. selectCondition had per staat een rijtje LETTERLIJKE
 * opties en koos het eerste rijtje-woord dat exact in de keuzelijst van die
 * categorie stond:
 *
 *     new_with_tags: ["Nieuw met etiket", "Nieuw", "Zo goed als nieuw"]
 *
 * Marktplaats spelt de "nieuw met kaartje"-optie per categorie anders — "Nieuw
 * met prijskaartje", "Nieuw met kaartje", "Nieuw met etiket", "Nieuw met label"
 * — en het rijtje kende er één van. Bood de categorie daarnaast geen kale
 * "Nieuw" aan, dan viel de keuze door naar het derde woord, en dat was "Zo goed
 * als nieuw". Er ging technisch niets mis: het veld was gevuld, dus de
 * eindcontrole (verifyMpGroupFields, die alleen op leeg controleert) zei niets.
 *
 * Dezelfde doorval werkte ook de verkeerde kant op: "Gedragen" viel terug op
 * "Zo goed als nieuw" zodra "Gedragen" niet bestond — en dan belooft de
 * advertentie méér dan het artikel is.
 *
 * Deze proef draait de ECHTE code uit shared.js tegen conditielijsten met alle
 * schrijfwijzen die Marktplaats gebruikt, en doet dat twee keer: met de versie
 * zoals hij nu in de map staat, en met de versie van vóór de reparatie (vaste
 * commit 4687587 — NIET HEAD, want de auto-push-hook commit werk in uitvoering
 * onder "auto: update ...", en dan bevat HEAD de reparatie al).
 *
 * Draaien: node tests/conditie-marktplaats-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "4687587";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── De conditielijsten zoals Marktplaats ze aanbiedt ──────────────────────
//
// Elke categorie heeft zijn eigen lijst; het veld heet ook per categorie anders
// (condition, clothingCondition, condition_kids_clothing, …). Welke van deze
// vormen op Overhemden staat is van buitenaf niet te meten — en dat is precies
// het punt: de reparatie mag daar niet van afhangen. Daarom draaien we alle
// vormen die in deze code al zijn vastgelegd:
//   - "Nieuw met prijskaartje"  → backend/services/mp_enrich.py, bewezen in
//                                 tests/test_relist_foto_en_venster.py
//   - "Nieuw met etiket"        → de oude lijst in shared.js zelf
//   - "Nieuw met label(s)"      → extension/content/vinted.js, dat
//                                 Marktplaats-labels naar Vinted vertaalt
// plus de kale vorm zonder "nieuw met"-optie.
const LIJSTEN = {
  "kleding, met prijskaartje": [
    "Nieuw met prijskaartje", "Nieuw zonder prijskaartje", "Zo goed als nieuw",
    "Gebruikt", "Beschadigd",
  ],
  "kleding, met etiket": [
    "Nieuw met etiket", "Nieuw zonder etiket", "Zo goed als nieuw", "Gedragen",
  ],
  "kleding, met label": [
    "Nieuw met label", "Nieuw zonder label", "Zo goed als nieuw", "Gedragen",
    "Beschadigd",
  ],
  "kale lijst zonder kaartje-optie": [
    "Nieuw", "Zo goed als nieuw", "Gebruikt", "Beschadigd",
  ],
  "kinderkleding (geen Gedragen)": [
    "Nieuw met prijskaartje", "Nieuw zonder prijskaartje", "Zo goed als nieuw",
    "Gebruikt",
  ],
  "elektronica (verpakking in plaats van kaartje)": [
    "Nieuw, in verpakking", "Nieuw, niet in verpakking", "Zo goed als nieuw",
    "Gebruikt", "Defect",
  ],
};

// Wat er in elke lijst gekozen HOORT te worden. Nooit een staat die het artikel
// mooier voorstelt dan het is; is de exacte trap er niet, dan de dichtstbijzijnde
// eronder.
const VERWACHT = {
  "kleding, met prijskaartje": {
    new_with_tags: "Nieuw met prijskaartje",
    new: "Nieuw zonder prijskaartje",
    good: "Zo goed als nieuw",
    fair: "Gebruikt",
    poor: "Beschadigd",
  },
  "kleding, met etiket": {
    new_with_tags: "Nieuw met etiket",
    new: "Nieuw zonder etiket",
    good: "Zo goed als nieuw",
    fair: "Gedragen",
    poor: "Gedragen",       // geen Beschadigd in deze lijst
  },
  "kleding, met label": {
    new_with_tags: "Nieuw met label",
    new: "Nieuw zonder label",
    good: "Zo goed als nieuw",
    fair: "Gedragen",
    poor: "Beschadigd",
  },
  "kale lijst zonder kaartje-optie": {
    new_with_tags: "Nieuw",
    new: "Nieuw",
    good: "Zo goed als nieuw",
    fair: "Gebruikt",
    poor: "Beschadigd",
  },
  "kinderkleding (geen Gedragen)": {
    new_with_tags: "Nieuw met prijskaartje",
    new: "Nieuw zonder prijskaartje",
    good: "Zo goed als nieuw",
    fair: "Gebruikt",
    poor: "Gebruikt",       // geen Beschadigd in deze lijst
  },
  "elektronica (verpakking in plaats van kaartje)": {
    new_with_tags: "Nieuw, in verpakking",
    new: "Nieuw, niet in verpakking",
    good: "Zo goed als nieuw",
    fair: "Gebruikt",
    poor: "Defect",
  },
};

// ── Een nagemaakt <select> en genoeg document om de echte code te draaien ──
function maakSelect(opties) {
  const el = {
    tagName: "SELECT",
    name: "singleSelectAttribute[clothingCondition]",
    _v: "",
    options: [{ value: "", text: "Kies...", disabled: false }]
      .concat(opties.map((t) => ({ value: t, text: t, disabled: false }))),
    dispatchEvent() { return true; },
  };
  return new Proxy(el, {
    get(t, k) { return k === "value" ? (t._v || "") : t[k]; },
    set(t, k, v) { if (k === "value") t._v = v; else t[k] = v; return true; },
  });
}

// Een nagemaakt label "Conditie" dat naar de keuzelijst wijst. Nodig voor het
// ene geval hieronder waarin de OPTIES onbekend zijn: zonder label vindt
// conditionSelect() het veld dan namelijk helemaal niet — het zoekt een lijst op
// de woorden die erin staan — en dan meet je iets anders dan je denkt.
function maakLabel() {
  return {
    childNodes: [{ nodeType: 3, textContent: "Conditie" }],
    textContent: "Conditie",
    children: [],
    querySelector: () => null,
    getAttribute: (k) => (k === "for" ? "conditie-veld" : null),
    contains: () => false,
    parentElement: null,
    nextElementSibling: null,
  };
}

function laadCL(bron, select, metLabel = false) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout, clearTimeout, Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
    chrome: { runtime: { sendMessage() {} } },
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false },
    // Alleen de keuzelijst met kenmerken bestaat in deze proef. Er is dus geen
    // label "Conditie" te vinden, precies zoals op een echte categorie waar het
    // veld anders heet: dan zoekt conditionSelect() het veld op de WOORDEN die
    // erin staan, en dat is het pad dat we hier willen meten.
    querySelectorAll: (sel) => {
      if (/singleSelectAttribute/.test(sel)) return [select];
      if (metLabel && /label/.test(sel)) return [maakLabel()];
      return [];
    },
    querySelector: () => null,
    getElementById: (id) => (metLabel && id === "conditie-veld" ? select : null),
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
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

async function kies(bron, opties, conditie, metLabel = false) {
  const select = maakSelect(opties);
  const CL = laadCL(bron, select, metLabel);
  await CL.selectCondition(conditie);
  return select.value || "";
}

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
const bronOud = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`,
                         { cwd: WORTEL, maxBuffer: 1 << 24 }).toString();

// Onze eigen staten, met het woord dat de verkoper in het dashboard ziet.
const STATEN = [
  ["new_with_tags", "New with tags"],
  ["new", "New (without tags)"],
  ["good", "Like new"],
  ["fair", "Used"],
  ["poor", "Damaged"],
];

(async () => {
  console.log("Het geval van Daniel: (1357) Lilac Profuomo Shirt, staat = New with tags\n");

  // Marktplaats' eigen kledinglijst spelt het "Nieuw met prijskaartje" (zie
  // mp_enrich); daar liep de oude code op stuk.
  const kleding = LIJSTEN["kleding, met prijskaartje"];
  const oudeKeuze = await kies(bronOud, kleding, "new_with_tags");
  const nieuweKeuze = await kies(bronNu, kleding, "new_with_tags");
  console.log(`  lijst:  ${kleding.join(" | ")}`);
  console.log(`  VOOR:   "${oudeKeuze}"`);
  console.log(`  NA:     "${nieuweKeuze}"\n`);
  check("de oude code koos aantoonbaar de verkeerde staat",
        oudeKeuze === "Zo goed als nieuw",
        `koos "${oudeKeuze}" — dan bewijst deze proef niets`);
  check("de nieuwe code kiest de staat die de verkoper invulde",
        nieuweKeuze === "Nieuw met prijskaartje", `koos "${nieuweKeuze}"`);

  console.log("\nElke conditielijst, elke staat");
  let foutOud = 0, foutNu = 0;
  for (const [naam, opties] of Object.entries(LIJSTEN)) {
    console.log(`\n  ${naam}`);
    console.log(`    (${opties.join(" | ")})`);
    for (const [sleutel, label] of STATEN) {
      const verwacht = VERWACHT[naam][sleutel];
      const oud = await kies(bronOud, opties, sleutel);
      const nu = await kies(bronNu, opties, sleutel);
      if (oud !== verwacht) foutOud++;
      if (nu !== verwacht) foutNu++;
      check(`${label} → ${verwacht}`, nu === verwacht,
            `koos "${nu}"${oud === nu ? "" : ` (oude code koos "${oud}")`}`);
    }
  }

  console.log("\nDe voor-en-na-proef over alle lijsten");
  console.log(`  VOOR: ${foutOud} van de ${Object.keys(LIJSTEN).length * STATEN.length} verkeerd`);
  console.log(`  NA:   ${foutNu} van de ${Object.keys(LIJSTEN).length * STATEN.length} verkeerd`);
  check("de oude code zat er aantoonbaar naast", foutOud > 0);
  check("de nieuwe code zit er nergens meer naast", foutNu === 0);

  console.log("\nBij gelijke afstand wint de lagere staat");
  // De dichtstbijzijnde trap wint altijd — ook als die erboven ligt, want
  // "Beschadigd" kiezen voor iets wat niet stuk is, is niet bescheiden maar
  // onwaar. Alleen bij een gelijkspel gaat de voorkeur naar beneden: "New
  // (without tags)" ligt precies tussen "Nieuw met prijskaartje" en "Nieuw
  // zonder prijskaartje" in, en dan hoort er niet ineens een prijskaartje te
  // worden beloofd.
  const beideKanten = ["Nieuw met prijskaartje", "Nieuw zonder prijskaartje",
                       "Zo goed als nieuw"];
  const gelijkspel = await kies(bronNu, beideKanten, "new");
  check("New (without tags) → Nieuw zonder prijskaartje, niet 'met'",
        gelijkspel === "Nieuw zonder prijskaartje", `koos "${gelijkspel}"`);
  // En andersom hoort de bovenste gewoon gekozen te worden als die het dichtst
  // bij ligt: een gedragen artikel in een lijst zonder "Gebruikt" of "Gedragen".
  const zonderGedragen = ["Nieuw", "Zo goed als nieuw", "Beschadigd"];
  const nuFair = await kies(bronNu, zonderGedragen, "fair");
  check("Used → Zo goed als nieuw als er niets tussen zit",
        nuFair === "Zo goed als nieuw", `koos "${nuFair}"`);

  console.log("\nEen lijst met alleen samengestelde opties wordt nu wél gevonden");
  // Het veld heet per categorie anders, dus zonder label wordt de conditielijst
  // gezocht op de woorden die erin staan — en dat waren vier LETTERLIJKE
  // woorden. Een lijst waarin geen van die vier kaal voorkomt werd helemaal niet
  // gevonden: geen staat op de advertentie, en geen melding, want de
  // eindcontrole zoekt het veld op dezelfde manier.
  const alleenSamengesteld = ["Nieuw met prijskaartje", "Nieuw zonder prijskaartje",
                              "Gebruikt met gebruikssporen"];
  const oudSamengesteld = await kies(bronOud, alleenSamengesteld, "new_with_tags");
  const nuSamengesteld = await kies(bronNu, alleenSamengesteld, "new_with_tags");
  check("de oude code vond de lijst niet eens", oudSamengesteld === "",
        `koos "${oudSamengesteld}"`);
  check("de nieuwe code vindt hem op betekenis",
        nuSamengesteld === "Nieuw met prijskaartje", `koos "${nuSamengesteld}"`);

  console.log("\nEen lijst die we niet begrijpen laten we leeg");
  // Hier stond "pak dan maar de eerste optie", en de eerste optie op een
  // conditielijst is bijna altijd de nieuwste. Leeg laten is eerlijk: het
  // plaatsen stopt en de verkoper krijgt te lezen wat er wél in de lijst staat.
  // Met label, want zonder herkenbare woorden in de opties is dat de enige
  // manier waarop de code het veld überhaupt vindt.
  const onbekend = ["Categorie A", "Categorie B"];
  const oudOnbekend = await kies(bronOud, onbekend, "fair", true);
  const nuOnbekend = await kies(bronNu, onbekend, "fair", true);
  check("de oude code vulde zomaar de eerste optie in", oudOnbekend === "Categorie A",
        `koos "${oudOnbekend}"`);
  check("de nieuwe code raadt niet", nuOnbekend === "", `koos "${nuOnbekend}"`);

  console.log("\nZonder staat in het item blijft het bij de standaard van het dashboard");
  const kaal = await kies(bronNu, LIJSTEN["kale lijst zonder kaartje-optie"], "");
  check("leeg → Zo goed als nieuw (dashboardstandaard 'Like new')",
        kaal === "Zo goed als nieuw", `koos "${kaal}"`);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})();
