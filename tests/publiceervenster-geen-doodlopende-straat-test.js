/**
 * Toon (dejuistetoon), 02-09-2026: "Lukt niet alles blijft vaag en kan niets
 * aanklikken."
 *
 * Hij had 244 geïmporteerde artikelen zonder omschrijving. Zonder omschrijving
 * zet het publiceervenster elk kanaal op grijs met de tekst "Missing:
 * description" — en daar hield het op. Geen knop, geen link, geen uitleg. Een
 * doodlopende straat.
 *
 * Deze test draait de échte tekenfunctie uit app.html en kijkt wat er uit komt.
 *
 * Draaien: node tests/publiceervenster-geen-doodlopende-straat-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const html = fs.readFileSync(
  path.join(__dirname, "..", "frontend/app.html"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// De echte functie uit het dashboard halen, niet een nagebouwde kopie: anders
// test je je eigen kopie en niet wat de verkoper ziet.
function pakFunctie(naam) {
  const start = html.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  let diepte = 0, i = html.indexOf("{", start);
  const begin = i;
  for (; i < html.length; i++) {
    if (html[i] === "{") diepte++;
    else if (html[i] === "}") { diepte--; if (!diepte) break; }
  }
  return html.slice(start, i + 1);
}

const ctx = {
  PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook"],
  PLATFORM_LABELS: { marktplaats: "Marktplaats", "2dehands": "2dehands",
                     vinted: "Vinted", facebook: "Facebook Marketplace" },
  PLATFORM_ICONS: { marktplaats: "M", "2dehands": "2", vinted: "V", facebook: "F" },
  API_PLATFORMS_FE: new Set(["ebay", "shopify"]),
  BETA_PLATFORMS: new Set(["facebook"]),
  esc: (s) => String(s == null ? "" : s),
  platformOordeel: () => ({ oordeel: "ok", reden: "" }),
  missingFieldsForPlatform: () => ["description"],
  state: { connected: [], listings: [], items: [] },
  document: { getElementById: () => ({ set innerHTML(v) { ctx._uit = v; }, get innerHTML() { return ctx._uit; } }) },
  console,
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(pakFunctie("renderPlatformCheckboxes"), ctx);

const ITEM = "aa18f1f2-9204-425b-aadc-e6166205bb82";

// ── Geval 1: artikel staat nog op Vinted, tekst is daar dus op te halen ──
console.log("Artikel zonder tekst dat nog op Vinted staat");
ctx.state.items = [{ id: ITEM, title: "Schapenvacht kussentje panda patroon" }];
ctx.state.listings = [{ item_id: ITEM, platform: "vinted", status: "active" }];
ctx.renderPlatformCheckboxes("crosslist-platform-checkboxes", ITEM);
let uit = ctx._uit;

check("Marktplaats meldt nog steeds wát er mist", /Missing: description/.test(uit));
check("er zit een klik op, geen dode tekst", /onclick=/.test(uit),
  "dit was precies de klacht: niets aanklikbaar");
check("de klik haalt de tekst van Vinted", /haalOmschrijvingOp\('/.test(uit));
check("het artikelnummer gaat mee", uit.includes(ITEM));
check("het staat er ook bij 2dehands en Facebook",
  (uit.match(/haalOmschrijvingOp/g) || []).length >= 3);
check("Vinted zelf krijgt geen ophaalknop (staat er al op)",
  !/Vinted<\/span>\s*<span[^>]*haalOmschrijvingOp/.test(uit));

// ── Geval 2: advertentie bestaat niet meer — dan zelf invullen ──────────
console.log("\nArtikel zonder tekst waarvan de Vinted-advertentie weg is");
ctx.state.listings = [{ item_id: ITEM, platform: "vinted", status: "delisted" }];
ctx.renderPlatformCheckboxes("crosslist-platform-checkboxes", ITEM);
uit = ctx._uit;
check("geen loze belofte om iets op te halen", !/haalOmschrijvingOp/.test(uit));
check("wel een weg naar het invulscherm", /editItem\('/.test(uit));
check("en de uitnodiging staat erbij", /fill in →/.test(uit));

// ── Geval 3: er mist meer dan alleen tekst ─────────────────────────────
console.log("\nArtikel waar meer aan ontbreekt dan de tekst");
ctx.missingFieldsForPlatform = () => ["description", "photos"];
ctx.state.listings = [{ item_id: ITEM, platform: "vinted", status: "active" }];
ctx.renderPlatformCheckboxes("crosslist-platform-checkboxes", ITEM);
uit = ctx._uit;
check("dan niet ophalen maar zelf invullen", !/haalOmschrijvingOp/.test(uit),
  "foto's haalt deze knop niet op, dus die belofte hoort er niet te staan");
check("beide ontbrekende dingen staan er", /description/.test(uit) && /photos/.test(uit));
check("en er is een weg heen", /editItem\('/.test(uit));

// ── Geval 4: niets mist — dan geen ruis ────────────────────────────────
console.log("\nArtikel dat compleet is");
ctx.missingFieldsForPlatform = () => [];
ctx.renderPlatformCheckboxes("crosslist-platform-checkboxes", ITEM);
uit = ctx._uit;
check("gewoon aanvinkbaar", /<input type="checkbox" value="marktplaats">/.test(uit));
check("geen Missing-tekst", !/Missing:/.test(uit));

// ── De voor-proef ──────────────────────────────────────────────────────
console.log("\nDe oude versie, ter vergelijking");
const oud = `<label class="platform-checkbox platform-checkbox-disabled" title="Missing: \${esc(missing.join(', '))}">
        <input type="checkbox" value="\${p}" disabled>
        <span>\${PLATFORM_ICONS[p]} \${label}</span>
        <span class="pm-cb-missing">Missing: \${esc(missing.join(', '))}</span>
      </label>`;
check("die dode versie staat niet meer in app.html", !html.includes(oud),
  "het venster is nog steeds een doodlopende straat");

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
