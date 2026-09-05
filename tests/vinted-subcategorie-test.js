/**
 * Amanda Haas, 05-09-2026:
 *   "Bij Vinted komt hij een heel eind, maar blijft hij elke keer steken op de
 *    categorie waarin het geplaatst moet worden. […] moet er dan wel voor
 *    achter de pc blijven hangen."
 *
 * WAT HAAR OPDRACHTENLOGBOEK ZEGT. Zeven van haar mislukte Vinted-plaatsingen
 * eindigen letterlijk met "Kies een subcategorie", bij artikelen als
 * "wonen plaids en woondekens", "wonen beddengoed" en
 * "antiek gereedschap en instrumenten".
 *
 * WAT ERONDER ZAT. Vinted heeft twee wegen naar een categorie:
 *   1. de boom aflopen (walkVintedCategoryPath) — die klikt netjes door tot er
 *      geen niveau meer onder zit, maar kent alleen KLEDINGpaden;
 *   2. zoeken op een trefwoord en de beste regel aanklikken — en die stopte
 *      daar. Alles van Amanda gaat via weg 2, en zo'n gevonden regel is lang
 *      niet altijd een eindpunt: bij wonen en antiek gaat de boom er nog een of
 *      twee niveaus onder door. Het veld bleef leeg, en het formulier weigerde.
 *
 * Deze proef bouwt Vinted's kiezer na met een tak die nog twee niveaus diep
 * gaat, en meet of de categorie uiteindelijk vastligt.
 *
 * Draaien: node tests/vinted-subcategorie-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VINTED = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
// Vaste commit, geen HEAD: de auto-push-hook zet werk in uitvoering al onder
// "auto: update …" in HEAD, en dan meet je de nieuwe code als "oud".
const VOOR = "266fac7";
const OUD_VINTED = execFileSync("git", ["show", `${VOOR}:extension/content/vinted.js`],
                                { cwd: WORTEL }).toString();

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const re = new RegExp(`(?:^|\\n)\\s*(?:async\\s+)?function ${naam}\\s*\\(`);
  const m = re.exec(bron);
  if (!m) return null;
  const start = m.index + m[0].search(/async|function/);
  let i = bron.indexOf("(", m.index + m[0].indexOf(naam)), haakjes = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "(") haakjes++;
    else if (bron[i] === ")") { haakjes--; if (haakjes === 0) { i++; break; } }
  }
  i = bron.indexOf("{", i);
  let diep = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diep++;
    else if (bron[i] === "}") { diep--; if (diep === 0) return bron.slice(start, i + 1); }
  }
  return null;
}

// ── Vinted's categoriekiezer, nagebouwd ────────────────────────────────────
//
// De boom is die van Amanda's dekens: zoeken op "blanket" levert de TAK
// "Home > Home textiles", en daaronder zitten nog twee niveaus. Precies zoals
// het echte formulier: pas als er niets meer onder zit vult Vinted het veld.
function maakKiezer(boom) {
  const veld = { value: "" };
  let laag = boom;        // de regels die nu zichtbaar zijn
  const geklikt = [];

  const maakCel = (naam, kinderen) => ({
    naam,
    kinderen,
    offsetParent: {},
    className: "web_ui__Cell__clickable",
    querySelector: (sel) => (/Cell__title/.test(sel) ? { textContent: naam } : null),
    get textContent() { return naam; },
  });

  const cellen = () => laag.map((k) => maakCel(k.naam, k.kinderen));

  const document = {
    querySelectorAll: (sel) => (/Cell__clickable/.test(sel) ? cellen() : []),
    querySelector: () => veld,
  };
  return {
    veld, geklikt, document,
    klik(cel) {
      geklikt.push(cel.naam);
      if (cel.kinderen && cel.kinderen.length) { laag = cel.kinderen; return; }
      laag = [];                    // geen niveau meer onder: Vinted legt vast
      veld.value = cel.naam;
    },
  };
}

function draai(bron, item, boom) {
  const src = functieUit(bron, "kiesRestSubcategorie");
  if (!src) return null;             // deze versie kent de afdaling niet
  const kiezer = maakKiezer(boom);
  const sandbox = {
    document: kiezer.document,
    qs: (sel) => kiezer.document.querySelector(sel),
    sleep: async () => {},
    clog: () => {},
    realClickEl: (el) => kiezer.klik(el),
    bladReden: null,
    console,
    BLAD_VOORKEUR: [],
    enkelvoud: (w) => (w.length > 4 && /s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w),
  };
  sandbox.__item = item;
  vm.createContext(sandbox);
  vm.runInContext(
    functieUit(bron, "catCellen") + "\n" +
    functieUit(bron, "catTitel") + "\n" +
    functieUit(bron, "kiesBlad") + "\n" +
    src + "\n" +
    "globalThis.__uit = kiesRestSubcategorie(__item);", sandbox);
  return sandbox.__uit.then((ok) => ({ ok, veld: kiezer.veld.value, pad: kiezer.geklikt }));
}

// Amanda's deken: zoeken op "blanket" landt op de tak, niet op het blad.
const BOOM_DEKEN = [
  { naam: "Bedding", kinderen: [
      { naam: "Blankets & throws", kinderen: [
          { naam: "Wool blankets", kinderen: [] },
          { naam: "Other blankets", kinderen: [] },
      ] },
      { naam: "Bed sheets", kinderen: [] },
  ] },
];

const ITEM_DEKEN = {
  title: "Vintage pure wool blanket 200x160 cm - Blue and Yellow",
  description: "Wollen deken",
};

(async () => {
  console.log("Vinted: doorklikken tot de categorie echt vastligt\n");

  console.log("Nieuwe versie:");
  const nu = await draai(VINTED, ITEM_DEKEN, BOOM_DEKEN);
  check("de afdaling bestaat", nu !== null,
        "kiesRestSubcategorie ontbreekt");
  if (nu) {
    check("Vinted legt de categorie vast", nu.veld !== "",
          `veld bleef "${nu.veld}"`);
    check("het is een eindpunt, geen tak", nu.veld === "Wool blankets",
          `koos "${nu.veld}" via ${nu.pad.join(" > ")}`);
    check("de wandeling meldt succes", nu.ok === true);
  }

  console.log("\nOude versie (dezelfde kiezer, dezelfde deken):");
  const oud = await draai(OUD_VINTED, ITEM_DEKEN, BOOM_DEKEN);
  check("kende de afdaling nog niet", oud === null,
        "de oude versie had kiesRestSubcategorie al");

  // En de zoek-terugval riep hem dus ook niet aan: hij ging van commit()
  // rechtstreeks naar verifyCategory, met het veld nog leeg.
  const oudeTerugval = functieUit(OUD_VINTED, "fillCategoryVinted") || "";
  const nieuweTerugval = functieUit(VINTED, "fillCategoryVinted") || "";
  console.log("");
  check("oud: na de klik meteen klaar",
        /await commit\(choice\);\s*\n\s*return verifyCategory/.test(oudeTerugval),
        "oude terugval zag er anders uit dan gedacht");
  check("nieuw: na de klik eerst doorklikken",
        /await commit\(choice\);[\s\S]{0,400}await kiesRestSubcategorie\(item\);/.test(nieuweTerugval));

  console.log("");
  if (mislukt) { console.log(`${mislukt} controle(s) mislukt`); process.exit(1); }
  console.log("alles goed");
})();
