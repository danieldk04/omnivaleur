/**
 * "Change category…" op een selectie: wat het scherm doet en wat het belooft.
 *
 * WAAROM DIT ER IS (22-09-2026, De Juiste Toon). Toon vroeg: *"Kan je bij mijn
 * account een vaste rubriek maken voor alleen home bv."* Hij verkoopt vachten,
 * kleden en tafelkleden en zette de rubriek tot nu toe artikel voor artikel.
 *
 * Twee dingen moeten kloppen, en allebei zijn ze eerder ergens anders misgegaan:
 *
 * 1. De doelgroep moet mee. Een kledingrubriek ZONDER doelgroep is op
 *    Marktplaats even onpubliceerbaar als een lege rubriek; een schapenvacht MÉT
 *    doelgroep is gewoon fout. Het scherm moet daarin hetzelfde beslissen als
 *    _doelgroep_bij_rubriek in backend/api/items.py, anders zegt de lijst iets
 *    anders dan de server doet.
 * 2. De melding achteraf mag niet suggereren dat het artikel nu klaarstaat. Een
 *    rubriek invullen haalt één blokkade weg en zet er bij kleding juist vier
 *    terug (doelgroep, merk, maat, kleur). Wie leest "4 items set to …" en
 *    daarna niets ziet verschijnen, meldt dat terecht als storing.
 *
 * Draaien:      node tests/rubriek-voor-een-hele-selectie-test.js
 * Voor-en-na:   node tests/rubriek-voor-een-hele-selectie-test.js <oude app.html>
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

function element() {
  const el = {
    _v: "", checked: false, disabled: false, textContent: "", innerHTML: "",
    style: {}, options: [], parentElement: { style: {} },
    querySelector: () => null, appendChild(o) { this.options.push(o); },
  };
  Object.defineProperty(el, "value", {
    get() { return this._v; },
    set(v) { this._v = v == null ? "" : String(v); },
  });
  return el;
}

function bouwWereld(items) {
  const elementen = {};
  const document = {
    getElementById: (id) => (elementen[id] ||= element()),
    createElement: () => element(),
    querySelectorAll: () => [],
  };
  const server = { verzoeken: [], antwoord: null };
  const state = { items: JSON.parse(JSON.stringify(items)), listings: [] };
  const meldingen = [], vragen = [];
  const selectedIds = new Set(items.map((i) => i.id));

  const hulp = {
    document, state, selectedIds, API: "",
    alert: (t) => meldingen.push(t),
    confirm: (t) => { vragen.push(t); return true; },
    esc: (s) => String(s),
    setBusy() {}, closeModal() {}, applyFilters() {},
    clearSelection: () => selectedIds.clear(),
    parseJsonSafe: async (r) => r.json(),
    apiFetchRetry: async (url, opties) => {
      const body = JSON.parse(opties.body);
      server.verzoeken.push({ url, body });
      // Doet wat backend/api/items.py bulk_category doet.
      return {
        ok: true,
        json: async () => (server.antwoord || { updated: body.ids.length, category: body.category }),
      };
    },
  };

  const bron = [
    constUit("CATEGORIES"),
    constUit("CATEGORIE_TAK_LABEL"),
    constUit("CATEGORIE_TAK_VOLGORDE"),
    constUit("NON_CLOTHING_PREFIXES"),
    constUit("GEEN_MAAT_CATEGORIEEN"),
    constUit("PLATFORMS"),
    constUit("CROSSLIST_UNIVERSAL_REQUIRED"),
    constUit("CROSSLIST_PLATFORM_REQUIRED"),
    constUit("CROSSLIST_FIELD_LABELS"),
    constUit("CROSSLIST_NON_CLOTHING_PLATFORM_REQUIRED"),
    functieUit("isNonClothingItem"),
    functieUit("missingFieldsForPlatform"),
    functieUit("bulkCategoryOpties"),
    functieUit("bulkCategoryDoelgroep"),
    functieUit("bulkCategoryRestwerk"),
    functieUit("renderBulkCategoryHint"),
    functieUit("openBulkCategory"),
    functieUit("doBulkCategory"),
    "return { bulkCategoryOpties, bulkCategoryDoelgroep, bulkCategoryRestwerk,",
    "         renderBulkCategoryHint, openBulkCategory, doBulkCategory };",
  ].join("\n");
  const namen = Object.keys(hulp);
  const api = new Function(...namen, bron)(...namen.map((n) => hulp[n]));
  return { document, state, server, meldingen, vragen, selectedIds, ...api };
}

// Toons vier artikelen uit de schermafdruk van 22-09-2026.
const VACHTEN = [
  { id: "a1", title: "Schapenvachtjes 2 stuks 15 euro", price: 15, description: "x",
    photo_urls: ["u"], category: "", gender: "heren", brand: "DJT", size: "", color: "wit" },
  { id: "a2", title: "2 stuks Originele lamsvachten", price: 35, description: "x",
    photo_urls: ["u"], category: "", gender: "dames", brand: "DJT", size: "", color: "wit" },
];
const LEDERHOSEN = [
  { id: "b1", title: "Originele Lederhosen maat 3XL", price: 25, description: "x",
    photo_urls: ["u"], category: "", gender: "", brand: "DJT", size: "XXXL", color: "" },
  { id: "b2", title: "Grote maat originele Lederhosen", price: 50, description: "x",
    photo_urls: ["u"], category: "", gender: "", brand: "Karl Klüber", size: "XXXL", color: "bruin" },
];

(async () => {
  console.log(`\nBron: ${BESTAND}`);

  // ── 1. De keuzelijst ──────────────────────────────────────────────────────
  console.log("\nDe keuzelijst van de knop:");
  {
    const w = bouwWereld(VACHTEN);
    const opties = w.bulkCategoryOpties();
    check("elke tak zit erin",
          ["Home & garden ·", "Women's ·", "Men's ·", "Antiques & art ·", "Music ·", "Games ·"]
            .every((p) => opties.some(([, label]) => label.startsWith(p))));
    check("de woonrubriek voor vachten staat erin",
          opties.some(([v]) => v === "wonen vachten"));
    check("kleding staat vooraan", opties[0][1].startsWith("Women's ·"), opties[0][1]);
  }

  // ── 2. Doelgroep: hetzelfde besluit als de server ────────────────────────
  console.log("\nDe doelgroep hoort bij de rubriek:");
  {
    const w = bouwWereld(VACHTEN);
    const paren = [
      ["heren verkleedkleding", "heren"], ["verkleedkleding", "dames"],
      ["kinderen schoenen", "kinderen"], ["unisex jassen", "unisex"],
      ["wonen vachten", ""], ["antiek klokken", ""], ["muziek orgels", ""],
      ["sieraden ringen", ""], ["games pc", ""], ["audio luidsprekers", ""],
    ];
    for (const [rubriek, verwacht] of paren)
      check(`${rubriek} → ${verwacht || "(geen)"}`,
            w.bulkCategoryDoelgroep(rubriek) === verwacht,
            `kreeg ${JSON.stringify(w.bulkCategoryDoelgroep(rubriek))}`);
  }

  // ── 3. Toons vachten naar Home ───────────────────────────────────────────
  console.log("\nTwee vachten in één keer naar Home & garden · Sheepskins & Hides:");
  {
    const w = bouwWereld(VACHTEN);
    w.document.getElementById("bulk-category-pick").value = "wonen vachten";
    await w.doBulkCategory();
    const verzoek = w.server.verzoeken[0];
    check("er gaat één verzoek uit", w.server.verzoeken.length === 1);
    check("het gaat naar bulk-category", /\/api\/items\/bulk-category$/.test(verzoek.url), verzoek.url);
    check("beide artikelen zitten erin", verzoek.body.ids.join(",") === "a1,a2", verzoek.body.ids.join(","));
    check("de rubriek staat in het verzoek", verzoek.body.category === "wonen vachten");
    check("de doelgroep is eraf gehaald in het scherm",
          w.state.items.every((i) => i.gender === ""),
          JSON.stringify(w.state.items.map((i) => i.gender)));
    const melding = w.meldingen.join(" | ");
    check("de melding noemt het aantal en de rubriek",
          /2 items set to "Home & garden · Sheepskins & Hides"/.test(melding), melding);
    check("en meldt geen restwerk, want een vacht heeft verder niets nodig",
          !/Still needed/i.test(melding), melding);
    check("de selectie is leeg na afloop", w.selectedIds.size === 0);
  }

  // ── 4. De lederhosen: kleding, dus met restwerk ──────────────────────────
  // Dit is de belofte die niet gebroken mag worden. b1 heeft geen kleur, dus na
  // het zetten van de rubriek staat hij er nog steeds niet op.
  console.log("\nTwee lederhosen naar Men's · Costumes & Fancy Dress:");
  {
    const w = bouwWereld(LEDERHOSEN);
    w.document.getElementById("bulk-category-pick").value = "heren verkleedkleding";
    await w.doBulkCategory();
    check("de doelgroep is op heren gezet in het scherm",
          w.state.items.every((i) => i.gender === "heren"),
          JSON.stringify(w.state.items.map((i) => i.gender)));
    const melding = w.meldingen.join(" | ");
    check("de melding noemt wat er nog ontbreekt", /Still needed/i.test(melding), melding);
    check("en noemt precies de kleur van één artikel", /color \(1\)/.test(melding), melding);
    check("maat en merk worden niet als ontbrekend genoemd",
          !/size|brand/.test(melding), melding);
  }

  // ── 5. Zonder keuze gebeurt er niets ─────────────────────────────────────
  console.log("\nZonder gekozen rubriek:");
  {
    const w = bouwWereld(VACHTEN);
    w.document.getElementById("bulk-category-pick").value = "";
    await w.doBulkCategory();
    check("er gaat niets uit", w.server.verzoeken.length === 0);
    check("er wordt niets gemeld", w.meldingen.length === 0, w.meldingen.join(" | "));
  }

  // ── 6. De uitleg in het venster vóór het toepassen ───────────────────────
  console.log("\nDe uitleg in het venster:");
  {
    const w = bouwWereld(LEDERHOSEN);
    w.document.getElementById("bulk-category-pick").value = "heren verkleedkleding";
    w.renderBulkCategoryHint();
    const tekst = w.document.getElementById("bulk-category-hint").innerHTML;
    check("zegt dat de doelgroep meegaat", /heren/.test(tekst), tekst);
    check("waarschuwt vooraf voor het restwerk", /Still missing/i.test(tekst), tekst);
    check("Apply staat aan", w.document.getElementById("bulk-category-apply").disabled === false);
  }
  {
    const w = bouwWereld(VACHTEN);
    w.document.getElementById("bulk-category-pick").value = "";
    w.renderBulkCategoryHint();
    check("Apply staat uit zolang er niets gekozen is",
          w.document.getElementById("bulk-category-apply").disabled === true);
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
