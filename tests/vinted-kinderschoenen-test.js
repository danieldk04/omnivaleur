/**
 * Janneke (31d28378), 08-10-2026: "Regenlaarzen Bergstein schoenmaat 27".
 *
 * Kinderen hebben op Vinted geen vast pad in de extensie, dus de categorie
 * wordt gekozen uit Vinteds voorstellen en zoekresultaten. Daar kreeg een regel
 * onder Kids geen voorkeur en een regel onder Women of Men geen straf. Bij
 * regenlaarzen stelt Vinted dames-, heren- en kinderlaarzen voor; de oude code
 * zag dames en heren gelijk staan en koos daarom NIETS (of een damesschoen).
 *
 * Deze proef bouwt Vinteds kiezer na in een echte browser (Chromium) en draait
 * de echte fillCategoryVinted uit extension/content/vinted.js, oud en nieuw.
 *
 * Draaien: node tests/vinted-kinderschoenen-test.js
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const WORTEL = path.join(__dirname, "..");
const NIEUW = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
// Vaste commit van vóór deze reparatie (merge van PR 12).
const VOOR = "f608939";
let OUD = null;
try {
  OUD = execFileSync("git", ["show", `${VOOR}:extension/content/vinted.js`], { cwd: WORTEL }).toString();
} catch (_) { /* ondiepe kloon: alleen de nieuwe code meten */ }

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function blokUit(bron, begin, open = "{", dicht = "}") {
  const i = bron.indexOf(begin);
  if (i < 0) throw new Error("niet gevonden: " + begin);
  let j = bron.indexOf(open, i + begin.length - 1), diep = 0;
  for (; j < bron.length; j++) {
    if (bron[j] === open) diep++;
    else if (bron[j] === dicht) { diep--; if (diep === 0) return bron.slice(i, j + 1) + ";"; }
  }
  throw new Error("niet gesloten: " + begin);
}
function functieUit(bron, kop) { return blokUit(bron, kop); }

function bouwCode(bron) {
  return [
    "const sleep = (ms) => new Promise((r) => setTimeout(r, Math.min(ms, 60)));",
    "const qs = (s) => document.querySelector(s);",
    "const clog = () => {};",
    "let bladReden = null;",
    "const BLAD_VOORKEUR = [];",
    "const ACCESSORY_TERMS = [];",
    "const enkelvoud = (w) => w;",
    "async function walkVintedCategoryPath() { return false; }",
    blokUit(bron, "const CAT_HINTS = {"),
    blokUit(bron, "const V_PAD = {"),
    functieUit(bron, "function realClickEl("),
    functieUit(bron, "function catCellen("),
    functieUit(bron, "function catTitel("),
    functieUit(bron, "function kiesBlad("),
    functieUit(bron, "async function kiesRestSubcategorie("),
    functieUit(bron, "function verifyCategory("),
    functieUit(bron, "async function fillCategoryVinted("),
    "window.__fill = fillCategoryVinted;",
  ].join("\n");
}

// Vinteds voorstellen bij een foto van regenlaarzen: titel + kruimelpad.
const VOORSTELLEN = [
  ["Wellies", "Women > Shoes > Boots"],
  ["Wellies", "Men > Shoes > Boots"],
  ["Wellies", "Kids > Girls > Shoes > Boots"],
  ["Wellies", "Kids > Boys > Shoes > Boots"],
];

const PAGINA = `<!doctype html><html><body>
<input data-testid="catalog-select-dropdown-input" value="">
<script>
  const inp = document.querySelector('[data-testid="catalog-select-dropdown-input"]');
  const RIJEN = ${JSON.stringify(VOORSTELLEN)};
  inp.addEventListener("click", () => {
    if (document.getElementById("lijst")) return;
    const lijst = document.createElement("div");
    lijst.id = "lijst"; lijst.setAttribute("role", "listbox");
    lijst.innerHTML = '<input placeholder="Find a category">';
    RIJEN.forEach(([t, p], i) => {
      const rij = document.createElement("label");
      rij.className = "web_ui__Cell web_ui__Cell__clickable";
      rij.innerHTML = '<div class="web_ui__Cell__title">' + t + '</div><div class="web_ui__Cell__body">' + p + '</div>'
        + '<input type="radio" name="c" id="r' + i + '" style="opacity:0">';
      rij.addEventListener("click", () => { inp.value = p + " > " + t; lijst.remove(); });
      lijst.appendChild(rij);
    });
    document.body.appendChild(lijst);
  });
</script></body></html>`;

const ITEM = {
  title: "Schoenen | Regenlaarzen Bergstein schoenmaat 27",
  description: "Regenlaarzen van Bergstein, schoenmaat 27.",
  category: "kinderen schoenen",
  gender: "kinderen",
};

async function meet(browser, bron) {
  const page = await browser.newPage();
  await page.setContent(PAGINA);
  await page.addScriptTag({ content: bouwCode(bron) });
  const ok = await page.evaluate(async (item) => {
    try { return { ok: await window.__fill(item) }; } catch (e) { return { fout: String(e) }; }
  }, ITEM);
  const waarde = await page.$eval('[data-testid="catalog-select-dropdown-input"]', (e) => e.value);
  await page.close();
  return { ...ok, waarde };
}

(async () => {
  const browser = await chromium.launch(
    fs.existsSync("/opt/pw-browsers/chromium") ? { executablePath: "/opt/pw-browsers/chromium" } : {});
  try {
    console.log("Regenlaarzen maat 27 (kinderen schoenen) op Vinted:");
    const nieuw = await meet(browser, NIEUW);
    check("nieuwe code kiest een categorie", !!nieuw.waarde, JSON.stringify(nieuw));
    check("en die ligt onder Kids", /^Kids >/.test(nieuw.waarde), nieuw.waarde);
    check("en is een laarzenblad", /Boots > Wellies$/.test(nieuw.waarde), nieuw.waarde);
    if (OUD) {
      const oud = await meet(browser, OUD);
      check("oude code ging hier mis (geen of geen Kids-categorie)",
        !/^Kids >/.test(oud.waarde), `oud koos: "${oud.waarde}"`);
      console.log(`  (oud koos: "${oud.waarde || "niets"}")`);
    }
  } finally {
    await browser.close();
  }
  if (mislukt) { console.log(`\n${mislukt} FOUT`); process.exit(1); }
  console.log("\nalles ok");
})();
