/**
 * De rubriekkeuze in het bewerkscherm mag nooit doodlopen, ook niet als er al
 * een doelgroep in het artikel staat.
 *
 * WAAROM DIT ER IS (22-09-2026, De Juiste Toon). Toon verkoopt schapenvachten,
 * lamsvachten, kleden en lederhosen. Zijn appje: *"Paar keer geprobeerd de
 * categorie te wijzigen en op te slaan, maar lukt niet? Alles staat in categorie
 * clothing en shoes."* Op 07-09 was dit al een keer gerepareerd, maar alleen voor
 * een artikel ZONDER doelgroep. Staat er wél een doelgroep in — en die zet de
 * import er zelf in — dan bouwde updateCategoryOptions uitsluitend de
 * kledingrubrieken van die doelgroep op: 29 voor heren, 34 voor dames. "wonen
 * vachten" zat daar niet bij, dus `select.value = 'wonen vachten'` deed in de
 * browser niets en het veld bleef leeg. Opslaan stuurde daarna niets naar de
 * server en meldde toch "Item saved — figures updated".
 *
 * Deze proef draait de ÉCHTE functies uit frontend/app.html (editItem,
 * updateCategoryOptions, onCategoryPicked, onItemTypeChange, leesItemFormulier,
 * gewijzigdeVelden, saveItem) tegen een nagebouwde <select> die zich gedraagt als
 * een echte: een waarde die niet in de lijst staat wordt NIET overgenomen. Zonder
 * die eigenschap bewijst de proef niets — een gewoon invoerveld slikt alles.
 *
 * Draaien:      node tests/rubriek-doodlopende-straat-test.js
 * Voor-en-na:   node tests/rubriek-doodlopende-straat-test.js <oude app.html>
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

// Een const die over één of over veertig regels loopt: lezen tot de puntkomma
// op diepte nul. `indexOf("\n};")` zou bij een eenregelige const het halve
// bestand meenemen.
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

// ── Een <select> die zich gedraagt als een echte ─────────────────────────────
// Dit is de kern van de proef. In de browser geldt: `select.value = "x"` waar
// geen <option value="x"> bestaat, laat het veld leeg achter. Een nagebouwd
// invoerveld dat elke tekst bewaart zou de storing onzichtbaar maken.
function optionEl() { return { value: "", textContent: "", selected: false }; }
function selectEl() {
  const el = {
    options: [], style: {}, parentElement: { style: {} },
    querySelector: () => null,
    appendChild(o) { this.options.push(o); if (o.selected) this._kies(o); },
    _kies(o) { this.options.forEach((x) => { x.selected = x === o; }); },
    get innerHTML() { return ""; },
    set innerHTML(html) {
      this.options = [];
      const re = /<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g;
      let m;
      while ((m = re.exec(html))) {
        const o = optionEl(); o.value = m[1]; o.textContent = m[2]; this.options.push(o);
      }
      if (this.options.length) this._kies(this.options[0]);
    },
  };
  Object.defineProperty(el, "value", {
    get() { const s = this.options.find((o) => o.selected); return s ? s.value : ""; },
    set(v) {
      const gezocht = v == null ? "" : String(v);
      const o = this.options.find((x) => x.value === gezocht);
      if (o) this._kies(o); else this.options.forEach((x) => { x.selected = false; });
    },
  });
  return el;
}
function inputEl() {
  const el = {
    _v: "", checked: false, disabled: false, textContent: "",
    style: {}, parentElement: { style: {} }, options: [],
    querySelector: () => null, appendChild() {},
  };
  Object.defineProperty(el, "value", {
    get() { return this._v; },
    set(v) { this._v = v == null ? "" : String(v); },
  });
  return el;
}

// Precies de keuzelijsten die in app.html staan.
const VASTE_OPTIES = {
  "f-item-type": ["clothing", "games", "electronics", "audio", "sieraden", "muziek", "antiek", "wonen"],
  "f-gender": ["", "dames", "heren", "kinderen", "unisex"],
  "f-condition": ["new_with_tags", "new", "good", "fair", "poor"],
  "f-price-type": ["", "FIXED", "FAST_BID", "SEE_DESCRIPTION", "FREE"],
  "f-size": ["", "S", "M", "L", "XL", "XXL", "XXXL"],
  "f-category": [""],
  "f-ebay-category": [""],
};

function bouwWereld() {
  const elementen = {};
  const document = {
    getElementById: (id) => (elementen[id] ||= VASTE_OPTIES[id] ? selectEl() : inputEl()),
    createElement: () => optionEl(),
    querySelectorAll: () => [],
    body: { insertAdjacentHTML() {} },
  };
  for (const [id, waarden] of Object.entries(VASTE_OPTIES)) {
    document.getElementById(id).innerHTML =
      waarden.map((v) => `<option value="${v}">${v || "—"}</option>`).join("");
  }

  const server = { rij: null, verzoeken: [] };
  const state = { items: [], listings: [] };
  const meldingen = [], toasts = [];
  let fotos = [];

  const hulp = {
    document, state, API: "", PLATFORM_LABELS: {}, PRIJSVORM_UITLEG: {},
    alert: (t) => meldingen.push(t),
    showToast: (t) => toasts.push(t),
    loadAll: async () => { state.items = [JSON.parse(JSON.stringify(server.rij))]; },
    // Doet wat backend/api/items.py update_item doet: alleen de meegestuurde
    // velden overschrijven.
    apiFetchRetry: async (url, opties) => {
      const body = JSON.parse(opties.body);
      server.verzoeken.push({ url, method: opties.method, body });
      server.rij = { ...server.rij, ...body };
      return { ok: true, json: async () => server.rij };
    },
    apiFetch: async () => { throw new Error("onverwacht verzoek"); },
    requireOk: async (r) => r.json(),
    setBusy() {}, setBusyText() {}, startBusyProgress() {}, stopBusyProgress() {},
    closeModal() {}, meldAlLive: async () => {}, nudgeExtension() {},
    resetEbayCategory: (id) => {
      document.getElementById("f-ebay-category").innerHTML = `<option value="${id || ""}">x</option>`;
    },
    loadEbayCategorySuggestions() {},
    getEbayCategoryId: () => document.getElementById("f-ebay-category").value || null,
    updateBidLabel() {}, toggleBidField() {}, updateConditionHint() {},
    onContextInputForEbay() {}, onPriceTypeChange() {},
    setSizeValue: (v) => { document.getElementById("f-size").value = v; },
    resetPhotoUpload: (lijst) => { fotos = [...lijst]; },
    getPhotoUrls: () => fotos.filter((u) => !u.startsWith("blob:")),
  };

  const bron = [
    "let importCreateCandidateId = null;",
    "let _uploadsInFlight = 0;",
    "let alLiveNaOpslaan = [];",
    "let _bewerkBeginstand = null;",
    constUit("CATEGORIES"),
    constUit("CATEGORIE_TAK_LABEL"),
    constUit("CATEGORIE_TAK_VOLGORDE"),
    constUit("NON_CLOTHING_PREFIXES"),
    constUit("GEEN_MAAT_CATEGORIEEN"),
    functieUit("isNonClothingItem"),
    functieUit("itemTypeForCategory"),
    functieUit("currentItemType"),
    functieUit("onItemTypeChange"),
    functieUit("_bewaarOnbekendeCategorie"),
    functieUit("updateCategoryOptions"),
    functieUit("onCategoryPicked"),
    functieUit("numOrNull"),
    functieUit("leesItemFormulier"),
    functieUit("gewijzigdeVelden"),
    functieUit("editItem"),
    functieUit("saveItem"),
    "return { editItem, saveItem, updateCategoryOptions, onCategoryPicked, onItemTypeChange };",
  ].join("\n");
  const namen = Object.keys(hulp);
  const api = new Function(...namen, bron)(...namen.map((n) => hulp[n]));
  return { document, server, state, meldingen, toasts, ...api };
}

const ID = "3b0f1f2a-0000-4000-8000-000000000001";
function artikel(extra) {
  return {
    id: ID, title: "Schapenvachtjes 2 stuks 15 euro", sku: null,
    description: "Twee originele schapenvachten", shopify_title: null,
    bid_percentage: null, price: 15, price_type: null, compare_at_price: null,
    purchase_price: null, price_marktplaats: null, price_2dehands: null,
    price_vinted: null, price_ebay: null, price_shopify: null,
    brand: "DJT", size: "", color: "wit", material: null,
    ebay_category_id: null, category: "", gender: "", condition: "good",
    photo_urls: ["https://img/1.jpg"], ...extra,
  };
}

// Scherm openen, eventueel eerst het soort omzetten zoals de verkoper dat doet,
// dan een rubriek kiezen, dan opslaan.
async function kies(rij, rubriek, soort) {
  const w = bouwWereld();
  w.server.rij = JSON.parse(JSON.stringify(rij));
  w.state.items = [JSON.parse(JSON.stringify(rij))];
  w.editItem(ID);
  if (soort) {
    w.document.getElementById("f-item-type").value = soort;
    w.onItemTypeChange();
  }
  const sel = w.document.getElementById("f-category");
  const stondErin = sel.options.some((o) => o.value === rubriek);
  sel.value = rubriek;
  w.onCategoryPicked();
  await w.saveItem();
  return { w, sel, stondErin, opties: sel.options.length };
}

(async () => {
  console.log(`\nBron: ${BESTAND}`);

  // ── 1. Precies wat Toon meldde ────────────────────────────────────────────
  // Een schapenvacht waar de import "heren" op heeft gezet. Zo zag zijn scherm
  // eruit: Item type op Clothing & Shoes, en in de rubrieklijst geen enkele
  // woonrubriek.
  console.log("\nToon, 22-09-2026 — schapenvacht met doelgroep 'heren' naar Home:");
  {
    const { w, stondErin, opties } = await kies(artikel({ gender: "heren" }), "wonen vachten");
    check("de woonrubriek staat in de keuzelijst", stondErin,
          `de lijst had ${opties} opties en 'wonen vachten' zat er niet bij`);
    check("het veld houdt de keuze vast",
          w.document.getElementById("f-category").value === "wonen vachten",
          `staat op ${JSON.stringify(w.document.getElementById("f-category").value)}`);
    check("opslaan stuurt de rubriek naar de server",
          w.server.rij.category === "wonen vachten",
          `de rij staat op ${JSON.stringify(w.server.rij.category)}`);
    check("de doelgroep gaat eraf, want een vacht heeft er geen",
          w.server.rij.gender === "", `staat op ${JSON.stringify(w.server.rij.gender)}`);
    check("geen foutmelding", !w.meldingen.length, w.meldingen.join(" | "));
  }

  // ── 2. Hetzelfde met doelgroep 'dames' ───────────────────────────────────
  console.log("\nDezelfde vacht met doelgroep 'dames':");
  {
    const { w, stondErin } = await kies(artikel({ gender: "dames" }), "wonen tapijten en kleden");
    check("de woonrubriek staat in de keuzelijst", stondErin);
    check("opslaan stuurt de rubriek naar de server",
          w.server.rij.category === "wonen tapijten en kleden",
          `de rij staat op ${JSON.stringify(w.server.rij.category)}`);
  }

  // ── 3. Toons lederhosen ───────────────────────────────────────────────────
  // Die moeten juist WEL bij kleding blijven, met de doelgroep erbij, anders
  // weigert Marktplaats ze nog steeds.
  console.log("\nLederhosen (heren verkleedkleding), met en zonder doelgroep vooraf:");
  for (const vooraf of ["", "dames", "heren"]) {
    const { w, stondErin } = await kies(
      artikel({ title: "Originele Lederhosen maat 3XL", size: "XXXL", gender: vooraf }),
      "heren verkleedkleding");
    check(`keuzelijst bevat de rubriek (doelgroep vooraf: ${vooraf || "geen"})`, stondErin);
    check(`rubriek opgeslagen (doelgroep vooraf: ${vooraf || "geen"})`,
          w.server.rij.category === "heren verkleedkleding",
          `staat op ${JSON.stringify(w.server.rij.category)}`);
    check(`doelgroep staat op heren (doelgroep vooraf: ${vooraf || "geen"})`,
          w.server.rij.gender === "heren", `staat op ${JSON.stringify(w.server.rij.gender)}`);
    check(`de maat blijft staan (doelgroep vooraf: ${vooraf || "geen"})`,
          w.server.rij.size === "XXXL", `staat op ${JSON.stringify(w.server.rij.size)}`);
  }

  // ── 4. Elke rubriek is bereikbaar, welke doelgroep er ook staat ──────────
  console.log("\nElke rubriek uit de lijst is bereikbaar vanuit elke doelgroep:");
  {
    const w = bouwWereld();
    const rij = artikel({ gender: "heren" });
    w.server.rij = JSON.parse(JSON.stringify(rij));
    w.state.items = [JSON.parse(JSON.stringify(rij))];
    w.editItem(ID);
    const zonder = new Set(w.document.getElementById("f-category").options.map((o) => o.value));
    const w2 = bouwWereld();
    const rij2 = artikel({ gender: "" });
    w2.server.rij = JSON.parse(JSON.stringify(rij2));
    w2.state.items = [JSON.parse(JSON.stringify(rij2))];
    w2.editItem(ID);
    const alle = [...w2.document.getElementById("f-category").options.map((o) => o.value)];
    const mist = alle.filter((v) => !zonder.has(v));
    check("de lijst mét doelgroep is net zo volledig als die zonder",
          mist.length === 0, `deze ontbreken: ${mist.slice(0, 5).join(", ")}${mist.length > 5 ? ` (+${mist.length - 5})` : ""}`);
    check("de eigen doelgroep staat vooraan",
          w.document.getElementById("f-category").options[1].value === "heren jeans",
          `eerste rubriek is ${JSON.stringify(w.document.getElementById("f-category").options[1].value)}`);
  }

  // ── 5. Opslaan zonder wijziging mag niet "saved" melden ─────────────────
  // Dit is wat Toon een paar keer zag: hij kwam niet bij zijn rubriek, drukte op
  // Save, en het scherm zei dat het gelukt was.
  console.log("\nOpslaan terwijl er niets veranderd is:");
  {
    const w = bouwWereld();
    const rij = artikel({ gender: "heren" });
    w.server.rij = JSON.parse(JSON.stringify(rij));
    w.state.items = [JSON.parse(JSON.stringify(rij))];
    w.editItem(ID);
    await w.saveItem();
    check("er gaat niets naar de server", w.server.verzoeken.length === 0,
          `${w.server.verzoeken.length} verzoek(en)`);
    check("het scherm meldt niet dat er iets is opgeslagen",
          !w.toasts.some((t) => /Item saved/i.test(t)), w.toasts.join(" | "));
    check("het scherm zegt wél wat er gebeurde", w.toasts.length === 1, w.toasts.join(" | "));
  }

  // ── 6. Het soort mag de lijst ook niet afsluiten ─────────────────────────
  // Toons tweede appje van 22-09, met een foto van het opengeklapte lijstje:
  // "Verder kan ik niet naar onderen scrollen, zie geen rugscof scheep skin
  // etc. Zo kan ik ze niet plaatsen?" Zijn Item type stond op "Audio, TV, Photo
  // & Video". De rubriekenlijst bood dan alleen de 68 audio-rubrieken.
  console.log("\nItem type op een ander soort (Toons schermafdruk van 15:30):");
  for (const soort of ["audio", "games", "electronics", "muziek", "antiek", "sieraden"]) {
    const { w, stondErin, opties } = await kies(artikel({ gender: "heren" }), "wonen vachten", soort);
    check(`met Item type "${soort}" staat de woonrubriek er nog steeds in`, stondErin,
          `de lijst had ${opties} opties`);
    check(`en opslaan legt hem vast (Item type "${soort}")`,
          w.server.rij.category === "wonen vachten",
          `staat op ${JSON.stringify(w.server.rij.category)}`);
  }
  {
    // Het eigen soort hoort nog wél vooraan te staan — anders wordt kiezen
    // binnen je eigen tak juist lastiger.
    const { w } = await kies(artikel({ gender: "" }), "audio luidsprekers", "audio");
    const eerste = w.document.getElementById("f-category").options[1];
    check("de rubrieken van het gekozen soort staan vooraan, zonder tak ervoor",
          eerste.value.startsWith("audio ") && !eerste.textContent.includes(" · "),
          `${eerste.value} / ${eerste.textContent}`);
    check("en een rubriek uit het eigen soort wordt gewoon opgeslagen",
          w.server.rij.category === "audio luidsprekers", w.server.rij.category);
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
