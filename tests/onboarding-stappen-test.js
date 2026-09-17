/**
 * De "Get started"-lijst vinkt af op wat er ECHT gebeurde, niet op wat er
 * aangeklikt is. Draait de echte OB.stappen en OB.kanaalStatus uit
 * frontend/onboarding.js.
 *
 * AANLEIDING 17-09-2026, Johan Kist: 24 advertenties geïmporteerd, 83 kanaaliconen
 * aangeklikt, nergens iets geplaatst, en hij dacht dat het gelukt was. Op de
 * Platforms-pagina stond bij elk kanaal "✓ Auto-detected", wat er ook aan de hand
 * was.
 *
 * Draaien:  node tests/onboarding-stappen-test.js
 */
const fs = require("fs");
const path = require("path");

const BRON = fs.readFileSync(path.join(__dirname, "..", "frontend", "onboarding.js"), "utf8");

function laad(extState) {
  const window = {};
  const document = { getElementById: () => null, head: { appendChild() {} }, createElement: () => ({}) };
  new Function("window", "document", "extState", BRON)(window, document, extState);
  return window.OB;
}

let mislukt = 0;
const ok = (naam, v, kreeg) => {
  if (v) return console.log(`  ✓ ${naam}`);
  mislukt++;
  console.log(`  ✗ ${naam} — kreeg ${JSON.stringify(kreeg)}`);
};
const klaar = (stappen) => Object.fromEntries(stappen.map((s) => [s.id, s.klaar]));

const OB = laad({ status: "ready", kanalen: {} });

console.log("1. Nieuw account: niets gebeurd");
const leeg = klaar(OB.stappen({}));
ok("geen enkele stap afgevinkt", Object.values(leeg).every((v) => v === false), leeg);

console.log("2. Johan op 14-09: extensie, 24 items, iconen aangeklikt maar nooit geplaatst");
const johan = klaar(OB.stappen({ extensie: true, kanaal: false, gepubliceerd: false, items: 24 }));
ok("extensie en items afgevinkt", johan.extensie && johan.items, johan);
ok("inloggen en publiceren NIET afgevinkt (aanklikken telt niet)", !johan.inloggen && !johan.publiceren, johan);

console.log("3. Eerder gelukt, maar nu bewezen uitgelogd op 2dehands");
const uit = OB.stappen({ extensie: true, kanaal: true, gepubliceerd: true, items: 24, nietIngelogd: ["2dehands"] });
const stap2 = uit.find((s) => s.id === "inloggen");
ok("inloggen gaat weer open, met 'Action needed'", !stap2.klaar && stap2.let_op && /2dehands/.test(stap2.waarschuwing), stap2);

console.log("4. eBay of Shopify gekoppeld");
ok("optionele stap afgevinkt", klaar(OB.stappen({ gekoppeld: ["ebay"] })).api === true);
ok("en blijft optioneel", OB.stappen({}).find((s) => s.id === "api").optioneel === true);

console.log("5. Platforms: geen 'Auto-detected' meer");
const zonderMeting = OB.kanaalStatus("marktplaats", 0);
ok("zonder meting: 'Uses your Chrome login', geen belofte dat hij ingelogd is",
   /Uses your Chrome login/.test(zonderMeting.badge) && !/Auto-detected|Connected|signed in ✓/i.test(zonderMeting.badge), zonderMeting.badge);
ok("nul advertenties: zegt dat er nog niets geplaatst is", /No adverts placed or imported here yet/.test(zonderMeting.regel), zonderMeting.regel);
const OB2 = laad({ status: "ready", kanalen: { "2dehands": { ingelogd: false } } });
const uitgelogd = OB2.kanaalStatus("2dehands", 4);
ok("bewezen uitgelogd: 'Not signed in' met link", /Not signed in/.test(uitgelogd.badge) && /2dehands\.be/.test(uitgelogd.regel), uitgelogd);

console.log(mislukt ? `\n${mislukt} MISLUKT` : "\nalles groen");
process.exit(mislukt ? 1 : 0);
