/**
 * Johan Kist (Blackbird Guitars), 14-09-2026: bij 23 gitaren elk grijs
 * kanaalicoon aangeklikt en telkens "Mark this item as listed on X?" bevestigd,
 * in de veronderstelling dat hij plaatste. Het zette alleen "staat online" aan:
 * 83 advertenties die nergens bestonden, ook op eBay en Shopify die niet eens
 * gekoppeld waren.
 *
 * Een grijs icoon moet dus doen wat een nieuwe klant ervan verwacht: plaatsen.
 * "Staat er al" mag alleen met de link naar die advertentie, en bij een
 * niet-gekoppeld eBay of Shopify is er alleen de weg naar koppelen.
 *
 * Deze test draait de échte functies uit app.html. Met een pad als argument
 * draait hij tegen een oudere kopie: zo is te zien dat die hier faalt.
 *
 * Draaien: node tests/kanaalicoon-is-geen-publiceren-test.js
 *          git show c7119a04:frontend/app.html > /tmp/oud.html
 *          node tests/kanaalicoon-is-geen-publiceren-test.js /tmp/oud.html
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const bestand = process.argv[2] || path.join(__dirname, "..", "frontend/app.html");
const html = fs.readFileSync(bestand, "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function pakFunctie(naam) {
  const start = html.search(new RegExp(`(async )?function ${naam}\\(`));
  if (start < 0) return null;
  let diepte = 0, i = html.indexOf("{", html.indexOf(`function ${naam}(`));
  // Sla de standaardwaarden in de parameterlijst over: pas na ") {" begint de body.
  i = html.indexOf(") {", html.indexOf(`function ${naam}(`)) + 2;
  for (; i < html.length; i++) {
    if (html[i] === "{") diepte++;
    else if (html[i] === "}") { diepte--; if (!diepte) break; }
  }
  return html.slice(start, i + 1);
}

const ITEM = "b1ac0bd2-0000-4000-8000-000000000001";
const elementen = {};
const oproepen = { api: [], alert: [], toast: [], loadAll: 0, views: [] };
let serverAntwoord = { ok: true, status: 200, data: { ok: true, linked: true } };

function element(id) {
  return (elementen[id] ||= {
    id, style: {}, innerHTML: "", textContent: "", value: "", disabled: false, dataset: {},
    remove() { delete elementen[id]; }, focus() {},
  });
}

const ctx = {
  PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook", "ebay", "shopify"],
  PLATFORM_LABELS: { marktplaats: "Marktplaats", "2dehands": "2dehands", vinted: "Vinted",
                     facebook: "Facebook Marketplace", ebay: "eBay", shopify: "Shopify" },
  PLATFORM_ICONS: { marktplaats: "M", "2dehands": "2", vinted: "V", facebook: "F", ebay: "E", shopify: "S" },
  API_PLATFORMS_FE: new Set(["ebay", "shopify"]),
  API: "",
  esc: (s) => String(s == null ? "" : s),
  state: { items: [{ id: ITEM, title: "Gibson Les Paul Studio" }], jobs: [], connected: [],
           dupSisters: {},
           listings: [{ item_id: ITEM, platform: "marktplaats", status: "active", platform_listing_id: "m2212345678" }] },
  document: {
    getElementById: (id) => elementen[id] || null,
    querySelector: (sel) => {
      const m = sel.match(/input\[value="([^"]+)"\]/);
      return m ? element("vakje-" + m[1]) : null;
    },
    body: {
      insertAdjacentHTML: (_waar, stuk) => {
        const id = (stuk.match(/id="([^"]+)"/) || [])[1];
        if (id) element(id).innerHTML = stuk;
        const veld = (stuk.match(/<input[^>]*id="([^"]+)"/) || [])[1];
        if (veld) element(veld);
        const knop = (stuk.match(/<button[^>]*id="([^"]+)"/) || [])[1];
        if (knop) element(knop);
      },
    },
  },
  apiFetch: async (url, opts) => {
    oproepen.api.push({ url, body: JSON.parse(opts.body) });
    return { ok: serverAntwoord.ok, status: serverAntwoord.status, _data: serverAntwoord.data };
  },
  parseJsonSafe: async (r) => r._data,
  alert: (m) => oproepen.alert.push(m),
  confirm: () => true,
  showToast: (m) => oproepen.toast.push(m),
  loadAll: async () => { oproepen.loadAll++; },
  showView: (v) => oproepen.views.push(v),
  renderPlatformCheckboxes: () => {},
  resetCrosslistButton: () => {},
  console,
};
ctx.window = ctx;
vm.createContext(ctx);

(async () => {
  // ── 1. Wat hij ziet als hij op een grijs icoon klikt ─────────────────
  console.log("Johans gitaar staat alleen op Marktplaats. Wat doet een klik op de rest?");
  vm.runInContext(pakFunctie("renderPlatformMatrix"), ctx);
  const matrix = ctx.renderPlatformMatrix(ITEM);
  const klikken = {};
  for (const m of matrix.matchAll(/onclick="([^"]*)"[^>]*title="([^"]*)"/g)) {
    const p = (m[1].match(/'(marktplaats|2dehands|vinted|facebook|ebay|shopify)'/) || [])[1];
    klikken[p] = { klik: m[1], titel: m[2] };
  }
  for (const p of ["2dehands", "vinted", "facebook", "ebay", "shopify"]) {
    check(`${p}: klik zet niets meteen op 'listed'`,
          klikken[p] && !/markPlatformListed/.test(klikken[p].klik),
          klikken[p] ? `onclick="${klikken[p].klik}"` : "icoon niet klikbaar");
    check(`${p}: klik opent de keuze`, klikken[p] && /kanaalKeuze\(/.test(klikken[p].klik));
  }
  check("de uitleg bij het icoon noemt publiceren, niet markeren",
        klikken.vinted && /publish/i.test(klikken.vinted.titel) && !/mark it listed/i.test(klikken.vinted.titel),
        klikken.vinted && klikken.vinted.titel);
  check("Marktplaats (al live) is niet klikbaar", !klikken.marktplaats);

  // Vastgelopen publicatie en mislukte publicatie: eigen, bestaande routes.
  ctx.state.jobs = [{ item_id: ITEM, platform: "vinted", status: "pending" }];
  ctx.state.listings.push({ item_id: ITEM, platform: "2dehands", status: "error", error_message: "x" });
  const matrix2 = ctx.renderPlatformMatrix(ITEM);
  check("oranje (vastgelopen) mag nog steeds afgesloten worden",
        /markPlatformListed\('[^']+','vinted','Vinted',true\)/.test(matrix2));
  check("rood (mislukt) opent de reden in plaats van meteen 'listed'",
        /showPublishError\('[^']+'\)/.test(matrix2) && !/markPlatformListed\('[^']+','2dehands'/.test(matrix2));
  ctx.state.jobs = [];
  ctx.state.listings.pop();

  // ── 2. De keuze zelf ────────────────────────────────────────────────
  console.log("\nHet keuzevenster voor Vinted:");
  const keuzeBron = pakFunctie("kanaalKeuze");
  const opslaanBron = pakFunctie("kanaalAlOnline");
  check("kanaalKeuze bestaat", !!keuzeBron);
  check("kanaalAlOnline bestaat", !!opslaanBron);
  if (keuzeBron && opslaanBron) {
    vm.runInContext(keuzeBron + "\n" + opslaanBron, ctx);
    ctx.kanaalKeuze(ITEM, "vinted");
    const venster = (elementen["modal-kanaal-keuze"] || {}).innerHTML || "";
    check("de eerste knop is plaatsen via Omnivaleur",
          /openCrosslist\('[^']+','vinted'\)/.test(venster) &&
          venster.indexOf("openCrosslist(") < venster.indexOf("kanaalAlOnline("));
    check("'staat er al' vraagt een link", /id="kanaal-keuze-link"/.test(venster));
    check("en gaat via de link-opslag, niet via een kale markering",
          /kanaalAlOnline\('[^']+','vinted'\)/.test(venster) && !/mark-active/.test(venster));

    console.log("\nZonder link op 'Link this advert' drukken:");
    element("kanaal-keuze-link").value = "   ";
    await ctx.kanaalAlOnline(ITEM, "vinted");
    check("er gaat niets naar de server", oproepen.api.length === 0);
    check("hij krijgt te horen wat er ontbreekt", /link/i.test(oproepen.alert.at(-1) || ""));

    console.log("\nMet link:");
    element("kanaal-keuze-link").value = "https://www.vinted.nl/items/5123456789-gibson";
    await ctx.kanaalAlOnline(ITEM, "vinted");
    const verzoek = oproepen.api.at(-1);
    check("de link gaat mee naar de server",
          verzoek && /mark-active$/.test(verzoek.url) &&
          verzoek.body.platform_listing_url === "https://www.vinted.nl/items/5123456789-gibson");
    check("het venster sluit en de lijst wordt bijgewerkt",
          !elementen["modal-kanaal-keuze"] && oproepen.loadAll === 1);

    console.log("\nServer weigert (geen advertentielink):");
    ctx.kanaalKeuze(ITEM, "vinted");
    serverAntwoord = { ok: false, status: 422, data: { detail: "That link isn't a Vinted advert." } };
    element("kanaal-keuze-link").value = "https://www.blackbirdguitars.nl/";
    await ctx.kanaalAlOnline(ITEM, "vinted");
    check("de reden van de server staat in de melding",
          /isn't a Vinted advert/.test(oproepen.alert.at(-1) || ""));
    check("het venster blijft open om het te verbeteren", !!elementen["modal-kanaal-keuze"]);
    check("de knop is weer te gebruiken", !element("kanaal-keuze-opslaan").disabled);
    serverAntwoord = { ok: true, status: 200, data: { ok: true, linked: true } };

    console.log("\neBay, niet gekoppeld (zijn situatie):");
    ctx.kanaalKeuze(ITEM, "ebay");
    const ebay = (elementen["modal-kanaal-keuze"] || {}).innerHTML || "";
    check("alleen de weg naar koppelen", /showView\('platforms'\)/.test(ebay));
    check("geen 'staat er al'-knop", !/kanaalAlOnline\(/.test(ebay));
    check("geen publiceerknop die toch niets kan", !/openCrosslist\(/.test(ebay));

    console.log("\neBay, wél gekoppeld:");
    ctx.state.connected = ["ebay"];
    ctx.kanaalKeuze(ITEM, "ebay");
    const ebay2 = (elementen["modal-kanaal-keuze"] || {}).innerHTML || "";
    check("plaatsen én link plakken", /openCrosslist\(/.test(ebay2) && /kanaalAlOnline\(/.test(ebay2));
    ctx.state.connected = [];
  }

  // ── 3. Plaatsen opent het publiceervenster met dat kanaal aangevinkt ──
  console.log("\n'Publish to Vinted' opent het publiceervenster:");
  const openBron = pakFunctie("openCrosslist");
  vm.runInContext(openBron, ctx);
  element("crosslist-item-name"); element("modal-crosslist");
  ctx.openCrosslist(ITEM, "vinted");
  check("Vinted staat al aangevinkt", element("vakje-vinted").checked === true);
  element("vakje-2dehands").disabled = true;
  ctx.openCrosslist(ITEM, "2dehands");
  check("een geblokkeerd vakje wordt niet stiekem aangevinkt", !element("vakje-2dehands").checked);

  // ── 4. De oude valkuilen zijn weg ──────────────────────────────────────
  console.log("\nGeen andere knop die met één bevestiging 'live' zet:");
  check("markListingActive is weg", !/function markListingActive\(/.test(html));
  check("het afvinkvenster 'Mark as published' is weg", !/function openMarkActiveModal\(/.test(html));

  console.log(mislukt ? `\n${mislukt} FOUT` : "\nAlles ok");
  process.exit(mislukt ? 1 : 0);
})();
