/**
 * De hele weg van één artikel van De Juiste Toon naar Marktplaats en 2dehands,
 * gemeten met de échte functies uit frontend/app.html.
 *
 * WAAROM DIT ER IS (22-09-2026). Toon liep er deze maand achter elkaar tegen
 * drie verschillende dingen aan, en elke keer kwam hij er pas achter nadat er
 * iets misging: eerst de rubriek die hij niet kon kiezen, daarna het lijstje
 * waar hij in zocht, en van 11 tot en met 16 september strandden ál zijn
 * 2dehands-plaatsingen op een leeg adresblok — telkens pas ná afloop, per
 * mislukking, met de hele wachtrij voor dat kanaal erachteraan teruggenomen.
 *
 * Deze proef loopt het pad af zoals het scherm het aan hem toont: wat zegt het
 * publiceervenster over elk kanaal, en klopt dat met wat er daarna echt kan?
 * Niet één losse functie, maar de keten platformOordeel → missingFieldsForPlatform
 * → renderPlatformCheckboxes.
 *
 * Draaien:      node tests/toon-hele-weg-naar-2dehands-test.js
 * Voor-en-na:   node tests/toon-hele-weg-naar-2dehands-test.js <oude app.html>
 */
const fs = require("fs");
const path = require("path");

const BESTAND = process.argv[2] || path.join(__dirname, "..", "frontend", "app.html");
const APP = fs.readFileSync(BESTAND, "utf8");

function functieUit(naam, verplicht = true) {
  let start = APP.indexOf(`async function ${naam}(`);
  if (start < 0) start = APP.indexOf(`function ${naam}(`);
  if (start < 0) {
    if (verplicht) throw new Error(`${naam} niet gevonden in app.html`);
    return "";
  }
  const eind = APP.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(start, eind + 2);
}
function constUit(naam) {
  const start = APP.indexOf(`const ${naam} = `);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  // Een regex-literal telt zijn eigen haakjes niet mee: `/(a|b)/i` zou de
  // dieptemeting hieronder laten ontsporen en het halve bestand meenemen. Die
  // staan hier altijd op één regel.
  const na = APP.slice(start + `const ${naam} = `.length);
  if (na[0] === "/" && na[1] !== "/") return APP.slice(start, start + `const ${naam} = `.length + na.indexOf("\n"));
  let diep = 0, inStr = null, gestart = false;
  for (let i = start; i < APP.length; i++) {
    const c = APP[i];
    if (inStr) { if (c === "\\") { i++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === "'" || c === '"' || c === "`") { inStr = c; continue; }
    if (c === "/" && APP[i + 1] === "/") { i = APP.indexOf("\n", i); if (i < 0) break; continue; }
    if (c === "{" || c === "[" || c === "(") { diep++; gestart = true; continue; }
    if (c === "}" || c === "]" || c === ")") { diep--; continue; }
    if (c === ";" && gestart && diep === 0) return APP.slice(start, i + 1);
  }
  throw new Error(`einde van ${naam} niet gevonden`);
}

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function bouwWereld(settings, items) {
  const html = {};
  const document = {
    getElementById: (id) => (html[id] ||= { innerHTML: "", value: "", style: {}, textContent: "" }),
    createElement: () => ({ value: "", textContent: "", selected: false, style: {} }),
    querySelectorAll: () => [],
  };
  const state = { settings, items, listings: [], connected: [] };
  const hulp = {
    document, state,
    esc: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"),
    PLATFORM_ICONS: new Proxy({}, { get: () => "" }),
  };
  const bron = [
    constUit("PLATFORMS"),
    constUit("API_PLATFORMS_FE"),
    constUit("BETA_PLATFORMS"),
    constUit("CROSSLIST_UNIVERSAL_REQUIRED"),
    constUit("CROSSLIST_PLATFORM_REQUIRED"),
    constUit("CROSSLIST_FIELD_LABELS"),
    constUit("CROSSLIST_NON_CLOTHING_PLATFORM_REQUIRED"),
    constUit("NON_CLOTHING_PREFIXES"),
    constUit("GEEN_MAAT_CATEGORIEEN"),
    constUit("PLATFORM_LABELS"),
    constUit("TREFWOORDSTAART_RE"),
    constUit("VINTED_VERBODEN_RE"),
    constUit("VINTED_TWIJFEL"),
    constUit("NIET_OP_VINTED"),
    constUit("VINTED_GROEP_LABELS"),
    functieUit("itemGroep"),
    functieUit("isNonClothingItem"),
    functieUit("missingFieldsForPlatform"),
    functieUit("fabrikantCompleet"),
    functieUit("locatieblokLeeg"),
    functieUit("platformOordeel"),
    functieUit("renderPlatformCheckboxes"),
    "return { platformOordeel, missingFieldsForPlatform, renderPlatformCheckboxes };",
  ].join("\n");
  const namen = Object.keys(hulp);
  return { ...new Function(...namen, bron)(...namen.map((n) => hulp[n])), html };
}

// Zijn instellingen zoals ze op 11 september stonden: verantwoordelijke partij
// ingevuld (Marktplaats plaatste immers gewoon), locatieblok leeg.
const ZONDER_LOCATIE = {
  fabrikant_naam: "De Juiste Toon", fabrikant_adres: "Etten-Leur", fabrikant_email: "x@y.nl",
  fabrikant_meesturen: true,
  locatie_land: "", locatie_plaats: "", locatie_postcode: "",
};
const MET_LOCATIE = { ...ZONDER_LOCATIE, locatie_land: "Nederland", locatie_plaats: "Etten-Leur" };
// Een Belgische verkoper: leeg blok is voor hem de goede stand.
const BELG = { ...ZONDER_LOCATIE, locatie_postcode: "2000" };

const LEDERHOSE = {
  id: "b1", title: "Originele Lederhosen maat 3XL", description: "Echt leer, bruin.",
  price: 25, photo_urls: ["u"], category: "heren verkleedkleding", gender: "heren",
  brand: "DJT", size: "XXXL", color: "bruin",
};

function oordeelVan(settings, item, platform) {
  const w = bouwWereld(settings, [item]);
  return w.platformOordeel(item, platform);
}

(async () => {
  console.log(`\nBron: ${BESTAND}`);

  // ── 1. Het artikel zelf is compleet ──────────────────────────────────────
  console.log("\nDe lederhose met rubriek, doelgroep, merk, maat en kleur:");
  {
    const w = bouwWereld(MET_LOCATIE, [LEDERHOSE]);
    for (const plat of ["marktplaats", "2dehands"]) {
      const mist = w.missingFieldsForPlatform(LEDERHOSE, plat);
      check(`${plat}: niets ontbreekt meer`, mist.length === 0, mist.join(", "));
    }
  }

  // ── 2. Het lege adresblok wordt VOORAF gemeld, op 2dehands ──────────────
  console.log("\nLeeg locatieblok (Toons stand van 11 t/m 16 september):");
  {
    const o2 = oordeelVan(ZONDER_LOCATIE, LEDERHOSE, "2dehands");
    check("2dehands waarschuwt vooraf", o2.oordeel === "twijfel",
          `oordeel is ${o2.oordeel}`);
    check("en wijst naar Preferences", /Preferences/.test(o2.reden), o2.reden);
    const oMp = oordeelVan(ZONDER_LOCATIE, LEDERHOSE, "marktplaats");
    check("Marktplaats blijft gewoon 'ok' (daar komt de postcode uit het account)",
          oMp.oordeel === "ok", `${oMp.oordeel}: ${oMp.reden}`);
    const oV = oordeelVan(ZONDER_LOCATIE, LEDERHOSE, "vinted");
    check("Vinted blijft ongemoeid", oV.oordeel === "ok", `${oV.oordeel}: ${oV.reden}`);
  }

  // ── 3. Het is een waarschuwing, geen blokkade ───────────────────────────
  // Een Belgische verkoper hoort het blok leeg te mogen laten. Hem tegenhouden
  // zou een nieuwe doodlopende straat zijn, en die hebben we er net drie uit.
  console.log("\nHet vakje blijft aan te vinken:");
  {
    const w = bouwWereld(ZONDER_LOCATIE, [LEDERHOSE]);
    w.renderPlatformCheckboxes("x", "b1");
    const uit = w.html["x"].innerHTML;
    const i = uit.indexOf('value="2dehands"');
    const blok = uit.slice(Math.max(0, i - 400), i + 500);
    check("2dehands staat er niet uitgeschakeld bij",
          !/value="2dehands" disabled/.test(uit), blok.slice(0, 200));
    check("de waarschuwing staat erbij", /Check first/.test(blok), blok.slice(0, 200));
    check("en is aanklikbaar naar Preferences", /showView\('preferences'\)/.test(blok));
  }

  // ── 4. Ingevuld: geen ruis meer ─────────────────────────────────────────
  console.log("\nZodra de locatie is ingevuld:");
  {
    const o = oordeelVan(MET_LOCATIE, LEDERHOSE, "2dehands");
    check("geen waarschuwing meer", o.oordeel === "ok", `${o.oordeel}: ${o.reden}`);
  }
  console.log("\nEen Belgische verkoper met alleen een postcode:");
  {
    const o = oordeelVan(BELG, LEDERHOSE, "2dehands");
    check("ook geen waarschuwing", o.oordeel === "ok", `${o.oordeel}: ${o.reden}`);
  }

  // ── 4b. Instellingen niet binnengekomen: dan zeggen we niets ────────────
  // Zelfde afspraak als fabrikantCompleet. Een verzonnen waarschuwing bij een
  // haperende verbinding zou iedere verkoper raken, ook wie het allang goed had.
  console.log("\nAls de instellingen niet geladen zijn:");
  {
    const o = oordeelVan({}, LEDERHOSE, "2dehands");
    check("geen waarschuwing op een lege state", o.oordeel === "ok", `${o.oordeel}: ${o.reden}`);
  }

  // ── 5. De verantwoordelijke partij blijft wél een harde blokkade ────────
  console.log("\nDe bestaande blokkade is niet verzwakt:");
  {
    const zonderFab = { ...MET_LOCATIE, fabrikant_naam: "", fabrikant_adres: "", fabrikant_email: "" };
    for (const plat of ["marktplaats", "2dehands"]) {
      const o = oordeelVan(zonderFab, LEDERHOSE, plat);
      check(`${plat}: zonder verantwoordelijke partij nog steeds geblokkeerd`,
            o.oordeel === "blokkade", `${o.oordeel}: ${o.reden}`);
    }
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
