/**
 * Toon (dejuistetoon), 02-09-2026 — twee dingen die aantoonbaar misgingen.
 *
 * 1. De scan haalde elke keer alle duizend Vinted-advertentiepagina's opnieuw
 *    op, ook die waarvan we de tekst al hadden. Vinted knijpt dat af, dus liep
 *    het budget leeg vóór de advertenties die het nodig hadden. Gemeten in zijn
 *    drie scans van dezelfde kast: 52, 776 en 507 zonder tekst.
 *
 * 2. Een maat of kleur die Marktplaats in díe categorie niet aanbiedt liet het
 *    verplichte veld leeg, en dan komt de advertentie er niet. "Universeel" bij
 *    heren shorts: zeven keer geprobeerd, zeven keer mislukt.
 *
 * Draaien: node tests/vinted-tekst-en-terugval-test.js
 */
const fs = require("fs");
const path = require("path");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;

function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── 1. De scan slaat over wat we al hebben ───────────────────────────────
const bg = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const scan = bg.split("async function bgScanVinted(")[1] || "";

console.log("Scan: alleen ophalen wat we nog niet hebben");
check("de lijst 'tekst al bekend' wordt uit de opdracht gelezen",
  /job\.payload\?\.tekst_bekend/.test(scan));
check("advertenties uit die lijst worden overgeslagen",
  /toEnrich\s*=\s*openStaand\.filter\(it\s*=>\s*!alBekend\.has/.test(scan));
check("het dode item-endpoint wordt na één 404 niet meer geprobeerd",
  /apiDood\s*=\s*true/.test(scan) && /apiDood\s*\?\s*\[\]/.test(scan));
check("bij 429 wordt echt gewacht, niet 1,2 seconde",
  /sleep\(30000\)/.test(scan));
check("blijft Vinted dicht, dan stoppen we in plaats van leeg door te vragen",
  /knepen\s*>=\s*MAX_KNEPEN/.test(scan) && /break;/.test(scan));

// De voor-proef: de oude regel deed precies het omgekeerde.
console.log("\nScan: de oude regel haalde alles op");
const oudeRegel = "const toEnrich = result.items.filter(it => !it.is_closed && !it.is_draft);";
check("die regel staat er niet meer", !bg.includes(oudeRegel),
  "de scan haalt nog steeds elke advertentie opnieuw op");

// De server moet de lijst ook echt meesturen, anders slaat de extensie niets over.
const imports = fs.readFileSync(path.join(WORTEL, "backend/api/imports.py"), "utf8");
console.log("\nServer: stuurt de lijst mee");
check("er is een aparte tak voor vinted", /elif platform == "vinted":/.test(imports));
check("tekst_bekend wordt in de opdracht gezet",
  /payload\["tekst_bekend"\]\s*=\s*_vinted_ids_met_tekst/.test(imports));
check("een mislukte lijst houdt de scan niet tegen",
  /Kon 'tekst al bekend'-lijst niet maken/.test(imports));
check("alleen nummers worden gelezen, nooit de teksten zelf",
  !/select\("platform_listing_id,description"\)/.test(imports));

// ── 2. Maat en kleur die niet in de lijst staan ──────────────────────────
const shared = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
console.log("\nFormulier: een waarde die niet in de lijst staat");
check("er is een terugval voor kleuren", /const COLOUR_FALLBACK = \{/.test(shared));
check("bordeaux valt terug op rood", /bordeaux:\s*\["Rood"/.test(shared));
check("universele maten hebben een eigen lijst", /const MAAT_UNIVERSEEL = \[/.test(shared));
check("Universeel staat erin", /"Universeel"/.test(shared));
check("de reparatieronde gebruikt de terugval",
  /kiesMetTerugval\(el, label, value\)/.test(shared));
check("de terugval is naar buiten gedeeld", /kiesMetTerugval, lijstOpties/.test(shared));

console.log("\nFoutmelding: zegt wélke waarde niet paste");
check("de melding noemt de waarde", /staat niet in de lijst bij/.test(shared));
check("de melding noemt wat er wél kan", /die biedt: \$\{opties\.join/.test(shared));
check("de uitleg zit in de opgeworpen fout", /uitleg\.length \? uitleg\.join/.test(shared));

// De voor-proef: de oude reparatieronde liet het veld gewoon leeg.
const oudeVulling = "if (el?.tagName === \"SELECT\" && !el.value) { fillNativeSelect(el, value); await sleep(300); }";
check("de oude, terugvalloze regel staat er niet meer", !shared.includes(oudeVulling),
  "een onbekende maat of kleur laat het veld nog steeds leeg");

// ── 3. Een afgeknepen scan mag niets wissen ──────────────────────────────
const jobs = fs.readFileSync(path.join(WORTEL, "backend/api/jobs.py"), "utf8");
console.log("\nOpslaan: een lege scan wist niets");
check("de vorige waarden worden gelezen", /prior_rich\[str\(pid\)\]/.test(jobs));
check("de samenvoegregel bestaat apart", /def _rijke_velden\(/.test(jobs));
check("de opslagronde gebruikt hem", /_rijke_velden\(row, photo_urls,/.test(jobs));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
