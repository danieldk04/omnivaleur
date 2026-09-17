/**
 * Een bewerkscherm dat al openstond mag bij opslaan niets terugzetten wat de
 * verkoper zelf niet heeft aangeraakt.
 *
 * WAAROM DIT ER IS (17-09-2026). Johan Kist (Blackbird Guitars) had een
 * inkoopadvertentie zonder vraagprijs. Op 13-09-2026 om 21:26 is de prijsvorm
 * van dat artikel op de server op SEE_DESCRIPTION gezet; om 21:32 stond hij weer
 * leeg met prijs 0,01. De enige plek die de prijsvorm leeg kan schrijven is
 * PATCH /api/items/{id}, en het enige scherm dat dat veld meestuurt is het
 * bewerkscherm: het stuurde bij opslaan het héle formulier, zoals het eruitzag
 * toen het openging. Met prijsvorm leeg en 0,01 gaat die advertentie voor
 * EUR 0,01 naar Vinted, eBay en Facebook.
 *
 * Hetzelfde gold voor elk ander veld: een omschrijving die de scan ophaalde,
 * foto's die verhuisd werden, een rubriek of maat die achteraf werd rechtgezet.
 *
 * Deze proef draait de échte editItem en saveItem uit frontend/app.html:
 * scherm openen, de rij op de server wijzigen, één ander veld aanpassen,
 * opslaan, en de rij weer uitlezen. De nagebouwde server doet wat
 * backend/api/items.py update_item doet: elk meegestuurd veld overschrijven en
 * de rest laten staan.
 *
 * Draaien:  node tests/bewerkscherm-overschrijft-geen-reparatie-test.js
 * Voor-en-na: node tests/bewerkscherm-overschrijft-geen-reparatie-test.js <oude app.html>
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

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── Een nagebouwd scherm ──────────────────────────────────────────────────────
// Net als een echt invoerveld maakt `value = null` er een lege tekst van.
function element() {
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

function bouwWereld() {
  const elementen = {};
  const document = {
    getElementById: (id) => (elementen[id] ||= element()),
    createElement: () => element(),
    querySelectorAll: () => [],
  };
  const server = { rij: null, verzoeken: [] };
  const state = { items: [] };
  const meldingen = [];
  let fotos = [];

  const hulp = {
    document, state,
    API: "",
    PLATFORM_LABELS: {},
    alert: (t) => meldingen.push(t),
    // Wat het dashboard bij het laden van de lijst binnenkrijgt.
    loadAll: async () => { state.items = [JSON.parse(JSON.stringify(server.rij))]; },
    apiFetchRetry: async (url, opties) => {
      const body = JSON.parse(opties.body);
      server.verzoeken.push({ url, method: opties.method, body });
      // backend/api/items.py update_item: `.update(clean)` op precies deze velden.
      server.rij = { ...server.rij, ...body };
      return { ok: true, json: async () => server.rij };
    },
    apiFetch: async () => { throw new Error("onverwacht verzoek"); },
    requireOk: async (r) => r.json(),
    setBusy() {}, closeModal() {}, showToast() {}, meldAlLive: async () => {},
    resetEbayCategory: (id) => { document.getElementById("f-ebay-category").value = id || ""; },
    loadEbayCategorySuggestions() {},
    getEbayCategoryId: () => document.getElementById("f-ebay-category").value || null,
    updateBidLabel() {}, toggleBidField() {},
    itemTypeForCategory: () => "clothing",
    onItemTypeChange() {},
    // De echte houdt een onbekende rubriek vast (_bewaarOnbekendeCategorie).
    updateCategoryOptions: (c) => { if (c !== undefined) document.getElementById("f-category").value = c; },
    updateConditionHint() {},
    resetPhotoUpload: (lijst) => { fotos = [...lijst]; },
    getPhotoUrls: () => fotos.filter((u) => !u.startsWith("blob:")),
  };

  const bron = [
    "let importCreateCandidateId = null;",
    "let _uploadsInFlight = 0;",
    "let alLiveNaOpslaan = [];",
    "let _bewerkBeginstand = null;",
    functieUit("numOrNull"),
    functieUit("setSizeValue"),
    functieUit("onPriceTypeChange"),
    functieUit("leesItemFormulier", false),
    functieUit("gewijzigdeVelden", false),
    functieUit("editItem"),
    functieUit("saveItem"),
    "return { editItem, saveItem };",
  ].join("\n");
  const namen = Object.keys(hulp);
  const { editItem, saveItem } = new Function(...namen, bron)(...namen.map((n) => hulp[n]));
  return { document, server, state, meldingen, editItem, saveItem, zetFotos: (l) => { fotos = l; } };
}

const ID = "51f3c6e1-8cdb-4adc-90c1-a6d56faa0e80";
const ARTIKEL = {
  id: ID, title: "Inkoop gitaren", sku: "BB-1", description: "Wij kopen uw gitaar",
  shopify_title: null, bid_percentage: null, price: 0.01, price_type: null,
  compare_at_price: null, purchase_price: null,
  price_marktplaats: null, price_2dehands: null, price_vinted: null,
  price_ebay: null, price_shopify: null,
  brand: "Gibson", size: "", color: "zwart", material: null,
  ebay_category_id: null, category: "muziek gitaren", gender: "", condition: "good",
  photo_urls: ["https://img/1.jpg"],
};

// Scherm openen met de lijst zoals het dashboard hem had, daarna wijzigt de
// server de rij, daarna past de verkoper iets aan en slaat op.
async function draai({ rij = ARTIKEL, opDeServer = {}, verkoper = () => {} }) {
  const w = bouwWereld();
  w.server.rij = JSON.parse(JSON.stringify(rij));
  w.state.items = [JSON.parse(JSON.stringify(rij))];
  w.editItem(ID);
  w.server.rij = { ...w.server.rij, ...opDeServer };
  verkoper(w.document, w);
  w.document.getElementById("save-btn");
  await w.saveItem();
  return w;
}

(async () => {
  console.log(`\nBron: ${path.relative(process.cwd(), BESTAND)}`);

  // ── 1. Precies wat er bij Johan Kist gebeurde ──────────────────────────────
  console.log("\nJohan Kist, 13-09-2026: prijsvorm hersteld terwijl het scherm openstond:");
  {
    const w = await draai({
      opDeServer: { price_type: "SEE_DESCRIPTION", price: null },
      verkoper: (d) => { d.getElementById("f-desc").value = "Wij kopen uw gitaar, bel ons"; },
    });
    check("zijn eigen wijziging is opgeslagen",
          w.server.rij.description === "Wij kopen uw gitaar, bel ons", w.server.rij.description);
    check("de prijsvorm blijft SEE_DESCRIPTION",
          w.server.rij.price_type === "SEE_DESCRIPTION", `staat nu op ${w.server.rij.price_type}`);
    check("het bedrag wordt niet teruggezet op 0,01",
          w.server.rij.price === null, `staat nu op ${w.server.rij.price}`);
    check("geen foutmelding", !w.meldingen.length, w.meldingen.join(" | "));
  }

  // ── 2. Het herstelde artikel daarna gewoon kunnen bewerken ─────────────────
  // Zonder bedrag en met een prijsvorm. Blokkeert het scherm dat, dan is de
  // enige uitweg voor de verkoper de prijsvorm terugzetten op vraagprijs.
  console.log("\nHet herstelde artikel (vorm zonder bedrag) bewerken:");
  {
    const hersteld = { ...ARTIKEL, price_type: "SEE_DESCRIPTION", price: null };
    const w = await draai({
      rij: hersteld,
      verkoper: (d) => { d.getElementById("f-desc").value = "Nieuwe tekst"; },
    });
    check("opslaan lukt zonder bedrag", !w.meldingen.length, w.meldingen.join(" | "));
    check("de wijziging staat op de server", w.server.rij.description === "Nieuwe tekst");
    check("de prijsvorm staat er nog", w.server.rij.price_type === "SEE_DESCRIPTION");
  }

  // ── 3. Elk ander veld: op de server gewijzigd, verkoper raakte het niet aan ─
  console.log("\nElk veld dat de server wijzigde terwijl het scherm openstond:");
  const velden = {
    title: "Inkoop gitaren en versterkers",
    sku: "BB-2",
    description: "Tekst die de scan ophaalde",
    shopify_title: "Gitaar inkoop",
    bid_percentage: 80,
    price: 12.5,
    price_type: "FAST_BID",
    compare_at_price: 20,
    purchase_price: 5,
    price_marktplaats: 11,
    price_2dehands: 11,
    price_vinted: 13,
    price_ebay: 14,
    price_shopify: 15,
    brand: "Fender",
    size: "M",
    color: "rood",
    material: "hout",
    ebay_category_id: "33034",
    category: "muziek versterkers",
    gender: "heren",
    condition: "very_good",
    photo_urls: ["https://img.omnivaleur.com/1.jpg", "https://img.omnivaleur.com/2.jpg"],
  };
  for (const [veld, waarde] of Object.entries(velden)) {
    const w = await draai({
      opDeServer: { [veld]: waarde },
      // Aan de titel draait de verkoper, behalve als de titel zelf het veld is.
      verkoper: (d) => {
        if (veld === "title") d.getElementById("f-desc").value = "Andere tekst";
        else d.getElementById("f-title").value = "Inkoop gitaren (bijgewerkt)";
      },
    });
    const staat = w.server.rij[veld];
    check(`${veld} blijft wat de server schreef`,
          JSON.stringify(staat) === JSON.stringify(waarde),
          `teruggezet naar ${JSON.stringify(staat)}`);
  }

  // ── 4. Wat de verkoper wél verandert, komt er nog steeds door ──────────────
  console.log("\nWat de verkoper zelf verandert:");
  {
    const w = await draai({
      rij: { ...ARTIKEL, price_type: "SEE_DESCRIPTION", price: null },
      verkoper: (d) => {
        d.getElementById("f-price-type").value = "";
        d.getElementById("f-price").value = "450";
        d.getElementById("f-brand").value = "";
        d.getElementById("f-size").value = "L";
      },
    });
    check("prijsvorm terug naar vraagprijs wordt opgeslagen", w.server.rij.price_type === null,
          JSON.stringify(w.server.rij.price_type));
    check("het nieuwe bedrag wordt opgeslagen", w.server.rij.price === 450, w.server.rij.price);
    check("een leeggemaakt merk wordt opgeslagen", w.server.rij.brand === "", w.server.rij.brand);
    check("een nieuwe maat wordt opgeslagen", w.server.rij.size === "L", w.server.rij.size);
    const body = w.server.verzoeken[0]?.body || {};
    check("en verder niets", JSON.stringify(Object.keys(body).sort())
          === JSON.stringify(["brand", "price", "price_type", "size"]),
          JSON.stringify(Object.keys(body)));
  }
  {
    const w = bouwWereld();
    w.server.rij = { ...ARTIKEL };
    w.state.items = [{ ...ARTIKEL }];
    w.editItem(ID);
    w.zetFotos(["https://img/1.jpg", "https://img/nieuw.jpg"]);
    await w.saveItem();
    check("een toegevoegde foto wordt opgeslagen",
          JSON.stringify(w.server.rij.photo_urls) === JSON.stringify(["https://img/1.jpg", "https://img/nieuw.jpg"]));
  }
  {
    const w = await draai({ opDeServer: { description: "van de scan" } });
    check("opslaan zonder wijziging schrijft niets over",
          w.server.rij.description === "van de scan" && w.server.rij.price === 0.01,
          JSON.stringify(w.server.verzoeken.map((v) => v.body)));
  }

  console.log(mislukt ? `\n${mislukt} FOUT(EN)\n` : "\nAlles in orde\n");
  process.exit(mislukt ? 1 : 0);
})();
