/**
 * Boeken, speelgoed, fietsen, sportartikelen, witgoed, klussen en computers op
 * Vinted (24-09-2026).
 *
 * Tot vandaag kende de boomwandeling op Vinted alleen kledingpaden. Alles
 * daarbuiten ging via zoeken op een trefwoord en dan de beste regel aanklikken,
 * wat de code zelf een loterij noemt. Voor de nieuwe takken staat in V_PAD per
 * rubriek het exacte pad, nagelopen in Vinteds eigen boom
 * (tests/fixtures/vinted_paden_24-09-2026.json). Heeft Vinted de rubriek niet,
 * dan staat er null en moet de extensie stoppen in plaats van te gokken.
 *
 * Deze proef bouwt Vinteds kiezer na uit de nagelopen paden en meet:
 *   1. dat een rubriek via zijn pad precies op het goede blad uitkomt;
 *   2. dat een tussenlaag daarna nog één niveau dieper gaat (tot een blad);
 *   3. dat een rubriek zonder Vinted-plek een duidelijke fout geeft;
 *   4. dat kleding ongemoeid blijft ("heren jeans" loopt zoals altijd).
 *
 * Draaien: node tests/vinted-nieuwe-takken-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VINTED = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
const PADEN = JSON.parse(fs.readFileSync(
  path.join(WORTEL, "tests", "fixtures", "vinted_paden_24-09-2026.json"), "utf8")).paden;

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function blokUit(bron, begin) {
  const i = bron.indexOf(begin);
  if (i < 0) return null;
  let j = bron.indexOf("{", i), diep = 0;
  for (; j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}") { diep--; if (diep === 0) return bron.slice(i, j + 1) + ";"; }
  }
  return null;
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

// Vinteds boom, opgebouwd uit de nagelopen paden. Een pad dat bij een
// tussenlaag stopt krijgt hier twee bladen eronder, zoals in het echt.
function bouwBoom() {
  const wortel = new Map();
  const zet = (delen) => {
    let laag = wortel;
    for (const d of delen) {
      if (!laag.has(d)) laag.set(d, new Map());
      laag = laag.get(d);
    }
  };
  for (const p of PADEN) zet(p.split(">"));
  const naarLijst = (m) => [...m.entries()].map(([naam, kind]) => ({ naam, kinderen: naarLijst(kind) }));
  const boom = naarLijst(wortel);
  return boom;
}

function metBladen(boom, pad) {
  // Kopie van de boom waarin het eindpunt van `pad` twee bladen krijgt als het
  // in de fixture geen kinderen heeft maar in het echt een tussenlaag is.
  const kopie = JSON.parse(JSON.stringify(boom));
  let laag = kopie, knoop = null;
  for (const stap of pad) { knoop = laag.find((k) => k.naam === stap); laag = knoop.kinderen; }
  return { kopie, knoop };
}

function maakKiezer(boom) {
  const veld = { value: "" };
  let laag = boom;
  const geklikt = [];
  const maakCel = (k) => ({
    naam: k.naam, kinderen: k.kinderen, offsetParent: {},
    className: "web_ui__Cell__clickable",
    querySelector: (sel) => (/Cell__title/.test(sel) ? { textContent: k.naam } : null),
    querySelectorAll: () => [1],
    get textContent() { return k.naam; },
  });
  const document = {
    querySelectorAll: (sel) => (/Cell/.test(sel) ? laag.map(maakCel) : []),
    querySelector: () => veld,
  };
  return {
    veld, geklikt, document,
    klik(cel) {
      if (cel === veld) return;
      geklikt.push(cel.naam);
      if (cel.kinderen && cel.kinderen.length) { laag = cel.kinderen; return; }
      laag = []; veld.value = cel.naam;
    },
  };
}

function sandboxVoor(kiezer) {
  const s = {
    document: kiezer.document,
    qs: (sel) => kiezer.document.querySelector(sel),
    sleep: async () => {}, clog: () => {},
    realClickEl: (el) => kiezer.klik(el),
    bladReden: null, console, BLAD_VOORKEUR: [],
    enkelvoud: (w) => (w.length > 4 && /s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w),
  };
  vm.createContext(s);
  vm.runInContext([
    blokUit(VINTED, "const V_PAD = {"),
    blokUit(VINTED, "const V_KLEDING = {"),
    functieUit(VINTED, "vintedPathFor"),
    functieUit(VINTED, "kiesBlad"),
    functieUit(VINTED, "walkVintedCategoryPath"),
    "globalThis.V_PAD = V_PAD; globalThis.vintedPathFor = vintedPathFor;",
    "globalThis.loop = walkVintedCategoryPath;",
  ].join("\n"), s);
  return s;
}

(async () => {
  const boom = bouwBoom();

  console.log("\n1. een nieuwe rubriek loopt precies zijn pad af");
  const gevallen = [
    ["boeken stripboeken", ["Books & Media", "Books", "Comics, manga & graphic novels"]],
    ["fietsen racefietsen", ["Sports", "Cycling", "Bikes", "Road bikes"]],
    ["speelgoed duplo en lego", ["Kids", "Toys", "Blocks & building toys"]],
    ["witgoed wasmachines", ["Home", "Large appliances", "Washing machines"]],
    ["computers apple ipads", ["Electronics", "Tablets, e-readers & accessories", "Tablets"]],
    ["sportartikelen tennis", ["Sports", "Racket sports", "Tennis"]],
    ["games controllers playstation", ["Electronics", "Video games & consoles", "Controllers"]],
  ];
  for (const [cat, verwacht] of gevallen) {
    const { kopie, knoop } = metBladen(boom, verwacht);
    if (!knoop.kinderen.length && cat === "sportartikelen tennis") {
      knoop.kinderen.push({ naam: "Tennis rackets", kinderen: [] }, { naam: "Other tennis accessories", kinderen: [] });
    }
    const kiezer = maakKiezer(kopie);
    const s = sandboxVoor(kiezer);
    const ok = await s.loop({ title: cat, description: "" }, cat, "");
    const begin = kiezer.geklikt.slice(0, verwacht.length).join(" > ");
    check(`${cat} → ${verwacht.join(" > ")}`, ok && begin === verwacht.join(" > ") && !!kiezer.veld.value,
          `geklikt: ${kiezer.geklikt.join(" > ")}, veld: "${kiezer.veld.value}"`);
  }

  console.log("\n2. een tussenlaag gaat door tot een blad (Other … als de titel niets zegt)");
  {
    const pad = ["Sports", "Racket sports", "Tennis"];
    const { kopie, knoop } = metBladen(boom, pad);
    knoop.kinderen.push({ naam: "Tennis rackets", kinderen: [] }, { naam: "Other tennis accessories", kinderen: [] });
    const k1 = maakKiezer(JSON.parse(JSON.stringify(kopie)));
    await sandboxVoor(k1).loop({ title: "Wilson Pro Staff tennis racket", description: "" }, "sportartikelen tennis", "");
    check("titel noemt racket → Tennis rackets", k1.veld.value === "Tennis rackets", k1.veld.value);
    const k2 = maakKiezer(JSON.parse(JSON.stringify(kopie)));
    await sandboxVoor(k2).loop({ title: "Balletjes emmer", description: "" }, "sportartikelen tennis", "");
    check("titel zegt niets → Other tennis accessories", k2.veld.value === "Other tennis accessories", k2.veld.value);
  }

  console.log("\n3. een rubriek zonder Vinted-plek");
  {
    const s = sandboxVoor(maakKiezer(boom));
    check("klussen tegels heeft uitdrukkelijk geen pad", s.V_PAD["klussen tegels"] === null);
    check("vintedPathFor geeft dan null", s.vintedPathFor("klussen tegels", "") === null);
    const fill = functieUit(VINTED, "fillCategoryVinted");
    const sb = { qs: () => ({ value: "" }), V_PAD: s.V_PAD, console };
    vm.createContext(sb);
    vm.runInContext(fill + "\nglobalThis.__p = fillCategoryVinted({ category: 'klussen tegels', title: 'Tegels' });", sb);
    let fout = null;
    try { await sb.__p; } catch (e) { fout = String(e.message || e); }
    check("de extensie stopt met een duidelijke reden", !!fout && /no category/.test(fout), fout || "geen fout");
  }

  console.log("\n4. kleding loopt zoals altijd");
  {
    const s = sandboxVoor(maakKiezer(boom));
    const pad = s.vintedPathFor("heren jeans", "heren");
    check("heren jeans krijgt nog steeds het kledingpad", Array.isArray(pad) && pad[0] === "Men" && pad[1] === "Clothing",
          JSON.stringify(pad));
    check("sport bh is geen V_PAD-rubriek", !Object.prototype.hasOwnProperty.call(s.V_PAD, "sport bh"));
  }

  console.log(mislukt ? `\n${mislukt} fout(en)` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
