/**
 * Vinted weigert een titel met "te veel hoofdletters" (10-10-2026, Daniel).
 *
 * "Vermarc Cycling Kit Men XL - Shanks Group ATM REYM Jersey" kwam bij het
 * plaatsen terug met "Title contains too many capital letters, try using
 * lowercase letters" (gezien op vinted.nl, de controle zit op Vinted's server).
 * De extensie wachtte daarna nog anderhalve minuut in de kast en gaf op.
 *
 * Deze proef draait het echte plaatsstuk uit vinted.js in Node, de versie van
 * vóór de reparatie (e496aa40) en die uit de werkmap, tegen een nagebootst
 * Vinted dat de titel weigert zolang er meer dan één hoofdletter in staat.
 * Draaien: node tests/vinted-hoofdletters-titel-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "e496aa40";
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

const NIEUW = fs.readFileSync(path.join(WORTEL, "extension/content/vinted.js"), "utf8");
const OUD = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/vinted.js`, { cwd: WORTEL }).toString();

// Het plaatsstuk: van "let id;" tot het JOB_DONE-bericht.
function plaatsStuk(bron) {
  const begin = bron.indexOf("      let id;\n      try {\n        id = await submitListing(");
  const eind = bron.indexOf('      send("JOB_DONE"', begin);
  if (begin < 0 || eind < 0) throw new Error("plaatsstuk niet gevonden");
  return bron.slice(begin, eind) + "      return id;\n";
}

// De hulpfuncties rond de hoofdletters (alleen in de nieuwe versie).
function hulpStuk(bron) {
  const begin = bron.indexOf("  const HOOFDLETTER_KLACHT_RE");
  const eind = bron.indexOf("  // Waar klaagt het formulier over", begin);
  return begin < 0 ? "" : bron.slice(begin, eind);
}

const TITEL = "Vermarc Cycling Kit Men XL - Shanks Group ATM REYM Jersey";
const KLACHT = "Title contains too many capital letters, try using lowercase letters";

async function draai(bron) {
  // Het titelvak met zijn omhullende blok, waar Vinted de melding onder zet.
  const blok = { innerText: "", parentElement: null };
  const titleEl = { value: TITEL, innerText: "", parentElement: blok };
  const pogingen = [];
  const ctx = {
    document: { body: { innerText: "" } },
    item: { title: TITEL, brand: "Vermarc Sport", platform_listing_id: null },
    qs: (sel) => (sel.includes("title--input") ? titleEl : null),
    fillInput: (el, v) => { el.value = v; },
    sleep: async () => {},
    clog: () => {},
    console: { log() {}, warn() {} },
    // Nagebootst Vinted: meer dan één hoofdletter wordt geweigerd.
    submitListing: async () => {
      pogingen.push(titleEl.value);
      const hoofd = (titleEl.value.match(/\p{Lu}/gu) || []).length;
      if (hoofd > 1) {
        blok.innerText = "Title\n" + KLACHT;
        throw new Error("Clicked publish but no listing appeared");
      }
      blok.innerText = "Title";
      return "12345";
    },
    // De kast: daar staat niets, want Vinted plaatste niets.
    resolveCreatedVintedItem: async () => null,
  };
  vm.createContext(ctx);
  const code = `${hulpStuk(bron)}\n(async () => {\n${plaatsStuk(bron)}})()`;
  try {
    const id = await vm.runInContext(code, ctx);
    return { id, pogingen, titel: titleEl.value };
  } catch (e) {
    return { fout: String(e.message || e), pogingen, titel: titleEl.value };
  }
}

(async () => {
  console.log("Voor de reparatie (" + VOOR_DE_REPARATIE + "):");
  const oud = await draai(OUD);
  check("oude versie faalt op de schreeuwerige titel", !!oud.fout && !oud.id, JSON.stringify(oud));
  check("oude versie probeert het maar één keer", oud.pogingen.length === 1, JSON.stringify(oud.pogingen));

  console.log("Na de reparatie:");
  const nieuw = await draai(NIEUW);
  check("nieuwe versie plaatst alsnog", nieuw.id === "12345", JSON.stringify(nieuw));
  check("precies één tweede poging", nieuw.pogingen.length === 2, JSON.stringify(nieuw.pogingen));
  check("titel rustig geschreven, merk behoudt hoofdletter",
    nieuw.titel === "Vermarc cycling kit men xl - shanks group atm reym jersey", nieuw.titel);

  // De herschrijving zelf.
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(hulpStuk(NIEUW), ctx);
  const r = (t, m) => vm.runInContext(`rustigeTitelVinted(${JSON.stringify(t)}, ${JSON.stringify(m)})`, ctx);
  check("merk midden in de titel houdt zijn hoofdletter",
    r("VINTAGE RALPH LAUREN POLO SHIRT XL", "Ralph Lauren") === "Vintage Ralph Lauren polo shirt xl", r("VINTAGE RALPH LAUREN POLO SHIRT XL", "Ralph Lauren"));
  check("accenten en ß blijven heel", r("ÉCHARPE HERMÈS GROẞ", "") === "Écharpe hermès groß", r("ÉCHARPE HERMÈS GROẞ", ""));
  check("cijfers en leestekens blijven staan", r("NIKE AIR MAX 90 - Maat 42,5 (Wit)", "Nike") === "Nike air max 90 - maat 42,5 (wit)", r("NIKE AIR MAX 90 - Maat 42,5 (Wit)", "Nike"));
  const klacht = (t) => vm.runInContext(`HOOFDLETTER_KLACHT_RE.test(${JSON.stringify(t)})`, ctx);
  check("klacht herkend in het Engels", klacht(KLACHT));
  check("klacht herkend in het Nederlands en Frans", klacht("Titel bevat te veel hoofdletters") && klacht("Le titre contient trop de majuscules"));
  check("geen klacht bij een andere melding", !klacht("Please upload at least 1 photo"));

  console.log(mislukt ? `\n${mislukt} fout(en)` : "\nAlles goed");
  process.exit(mislukt ? 1 : 0);
})();
