/**
 * walkVintedCategoryPath draait hier ECHT, tegen een nagebouwde categoriekiezer
 * van Vinted, inclusief de voorstellen die Vinted zelf bovenaan zet.
 *
 * Daniel, 05-09-2026: "laat hem op Vinted gewoon de aanbevolen categorie kiezen,
 * slim, wel even fact checkend." Tot nu toe won ons eigen raadwerk uit de titel
 * en werd Vinted's voorstel alleen gebruikt als wij niets wisten — terwijl
 * Vinted de foto's heeft gezien en wij niet. Nu is het andersom, met één rem:
 * zegt de tekst van het artikel zelf iets anders, dan wint de tekst.
 *
 * Draaien:  node tests/vinted-voorstel-wint-test.js
 *           node tests/vinted-voorstel-wint-test.js --oud   (vorige commit)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const OUD = process.argv.includes("--oud");
const BRON = OUD
  ? execFileSync("git", ["show", "HEAD:extension/content/vinted.js"], { cwd: WORTEL, maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — " + extra : ""}`);
};

function functieUit(bron, naam) {
  const re = new RegExp(`(?:^|\\n)\\s*(?:async\\s+)?function ${naam}\\s*\\(`);
  const m = re.exec(bron);
  if (!m) throw new Error(`${naam} niet gevonden`);
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
  throw new Error(`${naam} loopt niet af`);
}

// De boom onder Women > Clothing > Jumpers & sweaters, zoals hij op vinted.nl
// staat. Plus de voorstellen die Vinted bovenaan de kiezer zet.
const BOOM = {
  Women: { Clothing: { "Jumpers & sweaters": {
    "Turtlenecks": null, "Cardigans": null, "Hoodies": null,
    "Jumpers": null, "Other jumpers & sweaters": null,
  } } },
};

function kiezer(voorstellen) {
  const veld = { value: "" };
  let laag = BOOM;
  const geklikt = [];
  const cel = (naam, extra) => ({
    naam, offsetParent: {},
    querySelector: (sel) => (/Cell__title/.test(sel) ? { textContent: naam }
                          : /Cell__body/.test(sel) ? (extra ? { textContent: extra } : null) : null),
    querySelectorAll: (sel) => (/Cell__title/.test(sel) ? [{ textContent: naam }] : []),
    get textContent() { return naam; },
  });
  const zichtbaar = () => (laag ? Object.keys(laag).map((n) => cel(n)) : []);
  // De voorstelregels staan er alleen zolang de kiezer nog op het eerste niveau
  // staat, precies zoals in het echte formulier.
  const voorstelCellen = () => (laag === BOOM
    ? voorstellen.map(([naam, kruimel]) => cel(naam, kruimel)) : []);
  const document = {
    querySelectorAll: (sel) => (/Cell__clickable/.test(sel) ? zichtbaar()
                             : /Cell/.test(sel) ? [...voorstelCellen(), ...zichtbaar()] : []),
    querySelector: () => veld,
  };
  return {
    veld, geklikt, document,
    klik(el) {
      geklikt.push(el.naam);
      const kind = laag[el.naam];
      if (kind && typeof kind === "object") { laag = kind; return; }
      laag = null;
      veld.value = el.naam;
    },
  };
}

async function draai(item, voorstellen) {
  const k = kiezer(voorstellen);
  const zand = {
    document: k.document,
    qs: () => k.veld,
    sleep: async () => {},
    clog: () => {},
    realClickEl: (el) => k.klik(el),
    bladReden: null,
    console,
    BLAD_VOORKEUR: [[/ripped|kapot|gaten/i, /ripped/i]],
    enkelvoud: (w) => (w.length > 4 && /s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w),
    V_KLEDING: { dames: { truien: ["Jumpers & sweaters"] }, heren: {} },
  };
  zand.__item = item;
  vm.createContext(zand);
  vm.runInContext(
    functieUit(BRON, "vintedPathFor") + "\n" +
    functieUit(BRON, "kiesBlad") + "\n" +
    functieUit(BRON, "walkVintedCategoryPath") + "\n" +
    "globalThis.__uit = walkVintedCategoryPath(__item, 'truien', 'dames');", zand);
  await zand.__uit;
  return k.veld.value;
}

const KRUIMEL = "Women > Clothing > Jumpers & sweaters";

(async () => {
  console.log("\nVinted's eigen voorstel, met feitencontrole");

  // 1. De coltrui van Daniel: de titel zegt niets over het model ("Turtleneck"
  //    staat er wél in, maar zonder dat woord in de tekst zou onze gok op het
  //    vangblad vallen). Vinted stelt Turtlenecks voor.
  let v = await draai({ title: "(1071) Light Blue Massimo Dutti - Women XS - Very Good", description: "Wool/Cashmere" },
                      [["Turtlenecks", KRUIMEL]]);
  ok("tekst zegt niets over het model -> Vinted's voorstel", v === "Turtlenecks", `koos "${v}"`);

  // 2. Voorstel dat ook in de tekst terugkomt: dubbel bevestigd.
  v = await draai({ title: "(1071) Light Blue Massimo Dutti Turtleneck - Women XS", description: "" },
                  [["Turtlenecks", KRUIMEL]]);
  ok("voorstel dat de tekst bevestigt -> hetzelfde blad", v === "Turtlenecks", `koos "${v}"`);

  // 3. TEGENSPRAAK. De titel zegt letterlijk "cardigan", Vinted denkt op de
  //    foto's een hoodie te zien. Dan wint de tekst.
  v = await draai({ title: "(999) Grey Cardigan - Women M - Very Good", description: "Vest met knopen" },
                  [["Hoodies", KRUIMEL]]);
  ok("tekst zegt cardigan, foto zegt hoodie -> de tekst wint", v === "Cardigans", `koos "${v}"`);

  // 4. Geen voorstel: gewoon onze eigen keuze uit de tekst.
  v = await draai({ title: "(998) Black Hoodie - Women M", description: "" }, []);
  ok("geen voorstel -> gewoon de keuze uit de tekst", v === "Hoodies", `koos "${v}"`);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
