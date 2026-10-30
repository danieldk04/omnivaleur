/**
 * De startpoort (frontend/poort.js) beslist puur uit feiten wie het dashboard in
 * mag. Draait de echte P.fase, P.toegestaan en P.guard.
 *
 * AANLEIDING 30-10-2026: nieuwe klanten zeiden "het werkt niet" terwijl ze de
 * extensie, de login op de marktplaats of hun items nog misten. Twee dingen mogen
 * nooit misgaan: een klant die al werkt mag er nooit in, en een storing van ons
 * (server geeft geen antwoord) mag nooit iemand buitensluiten.
 *
 * Draaien:  node tests/poort-fase-test.js
 */
const fs = require("fs");
const path = require("path");

const BRON = fs.readFileSync(path.join(__dirname, "..", "frontend", "poort.js"), "utf8");
const window = {};
const document = { getElementById: () => null, querySelector: () => null, querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}), hidden: true };
new Function("window", "document", "setInterval", "setTimeout", "addEventListener", "localStorage", "navigator", BRON)(
  window, document, () => {}, () => {}, () => {}, { getItem: () => null, setItem() {} }, {});
const P = window.OBPoort;

let mislukt = 0;
const ok = (naam, v, kreeg) => {
  if (v) return console.log(`  ✓ ${naam}`);
  mislukt++;
  console.log(`  ✗ ${naam} — kreeg ${JSON.stringify(kreeg)}`);
};
const basis = { bekend: true, server: {}, extStatus: "checking", items: 0, gekoppeld: [], nietIngelogd: [], gekozen: [], kanalenOk: false };
const fase = (o) => P.fase({ ...basis, ...o, server: { ...basis.server, ...(o.server || {}) } });

console.log("1. Wie niets gedaan heeft zit in stap 1");
let r = fase({});
ok("nieuw account, extensie wordt gezocht", r.fase === "extensie" && r.sub === "zoeken", r);
ok("extensie ontbreekt na het zoeken", fase({ extStatus: "missing" }).sub === "installeren");
ok("extensie staat er maar is uitgelogd", fase({ extStatus: "signed-out" }).sub === "inloggen");
ok("telefoon krijgt 'ga naar je computer'", fase({ telefoon: true }).sub === "telefoon");
ok("Safari of Firefox krijgt 'open Chrome'", fase({ andereBrowser: true }).sub === "andere");

console.log("2. Stap 2: kanalen kiezen en daar ingelogd zijn");
ok("extensie ok maar nog niets gekozen", fase({ extStatus: "ready" }).sub === "kiezen");
r = fase({ extStatus: "ready", gekozen: ["marktplaats"], nietIngelogd: ["marktplaats"], kanalenOk: true });
ok("bewezen uitgelogd op een gekozen kanaal houdt hem hier", r.fase === "kanalen" && r.sub === "inloggen", r);
r = fase({ extStatus: "ready", gekozen: ["vinted"], nietIngelogd: ["marktplaats"], kanalenOk: true, items: 3 });
ok("uitgelogd op een kanaal dat hij niet gekozen heeft telt niet", r.fase === "plaatsen", r);
ok("gekozen maar nog niet bevestigd", fase({ extStatus: "ready", gekozen: ["vinted"] }).sub === "bevestigen");
ok("heartbeat op de server telt als extensie, ook als dit tabblad hem niet ziet",
  fase({ server: { extensie: true }, extStatus: "missing" }).nr === 2);

console.log("3. Stap 3 en 4");
const klaar2 = { extStatus: "ready", gekozen: ["vinted"], kanalenOk: true };
ok("zonder items: stap 3", fase(klaar2).fase === "items");
ok("items volgens de server tellen ook (scherm nog niet geladen)", fase({ ...klaar2, server: { items: true } }).fase === "plaatsen");
ok("met items maar nooit geplaatst: stap 4, niets dicht", P.toegestaan("plaatsen", "dashboard") && fase({ ...klaar2, items: 5 }).fase === "plaatsen");

console.log("4. Wie al werkt komt er nooit in");
ok("gelukte plaatsing", fase({ server: { gepubliceerd: true } }).fase === "vrij");
ok("gelukte opdracht op een kanaal", fase({ server: { kanaal: true } }).fase === "vrij");
ok("eBay gekoppeld", fase({ gekoppeld: ["ebay"] }).fase === "vrij");
ok("Shopify gekoppeld", fase({ gekoppeld: ["shopify"] }).fase === "vrij");

console.log("5. Een storing van ons sluit niemand buiten");
ok("server geeft geen antwoord: vrij", fase({ bekend: false }).fase === "vrij");
ok("helemaal geen feiten: vrij", P.fase().fase === "vrij" && P.fase({}).fase === "vrij");

console.log("6. Wat is open per fase");
ok("fase 1 en 2: alleen Help en Account", ["help", "prijs"].every((v) => P.toegestaan("extensie", v) && P.toegestaan("kanalen", v)) &&
  !["dashboard", "items", "import", "analytics", "platforms", "preferences"].some((v) => P.toegestaan("extensie", v) || P.toegestaan("kanalen", v)));
ok("fase 3: Import, Items en Platforms open, rest dicht", ["import", "items", "platforms", "help", "prijs"].every((v) => P.toegestaan("items", v)) &&
  !["dashboard", "analytics", "berichten", "refresh", "preferences"].some((v) => P.toegestaan("items", v)));
ok("vrij en plaatsen: alles open", ["dashboard", "analytics", "preferences"].every((v) => P.toegestaan("vrij", v) && P.toegestaan("plaatsen", v)));
ok("terugval: dashboard (overlay) of import", P.terugval("extensie") === "dashboard" && P.terugval("items") === "import");
ok("guard laat alles door zolang de poort nog niets weet", P.guard("analytics") === "analytics");

console.log(mislukt ? `\n${mislukt} mislukt` : "\nAlles ok");
process.exit(mislukt ? 1 : 0);
