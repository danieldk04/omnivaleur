/**
 * De echte controle uit bgDeleteVinted draait hier, tegen drie nagebootste
 * situaties. Aanleiding: een herplaatsing van Daniels eigen Vinted-item
 * 8289521490 meldde "je bent niet ingelogd" terwijl hij ingelogd was — de
 * advertentiepagina bestond simpelweg niet meer. Gemeten op 05-09-2026:
 * https://www.vinted.nl/items/8289521490 geeft 404, met en zonder slug.
 *
 * Draaien:  node tests/vinted-verwijderen-404-test.js
 *           node tests/vinted-verwijderen-404-test.js --oud   (vorige commit: faalt)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

// De functie die in het tabblad draait, letterlijk uit de bron.
const start = BG.indexOf("const before = await execInTab(tabId, async (lid) => {");
if (start < 0) throw new Error("de controle uit bgDeleteVinted is niet gevonden");
const eind = BG.indexOf("}, [listingId]);", start);
const body = BG.slice(BG.indexOf("{", BG.indexOf("async (lid) =>", start)) + 1, eind);
const inTabblad = new Function("lid", "document", "fetch", "location", "setTimeout",
  `return (async () => {${body}})();`);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

const doc = (links) => ({
  querySelectorAll: () => links.map(h => ({ getAttribute: () => h })),
  querySelector: () => null,
});

const kast = (ids) => async () => ({
  ok: true, status: 200,
  json: async () => ({ items: ids.map(id => ({ id, is_closed: false })), pagination: { total_pages: 1 } }),
});

(async () => {
  console.log("\nVinted verwijderen: waarom lukt het niet");

  // 1. Ingelogd, advertentie staat gewoon in de kast.
  let r = await inTabblad("8289521490", doc(["/member/12345"]), kast([8289521490]),
                          { href: "https://www.vinted.nl/items/8289521490" }, setTimeout);
  ok("ingelogd + advertentie leeft -> present", r.userId === "12345" && r.present === true, r);

  // 2. De advertentie bestaat niet meer: 404-pagina, geen menu, geen lidnummer.
  const vierNulVier = async () => ({ ok: false, status: 404, json: async () => ({}) });
  r = await inTabblad("8289521490", doc([]), vierNulVier,
                      { href: "https://www.vinted.nl/items/8289521490" }, setTimeout);
  ok("advertentie weg -> statuscode 404 wordt teruggegeven", r.userId === null && r.httpStatus === 404, r);

  // 3. Echt uitgelogd: de pagina bestaat wel (200), er is alleen geen menu.
  const paginaBestaat = async () => ({ ok: true, status: 200, json: async () => ({}) });
  r = await inTabblad("8289521490", doc([]), paginaBestaat,
                      { href: "https://www.vinted.nl/items/8289521490" }, setTimeout);
  ok("uitgelogd -> geen 404, dus geen valse 'advertentie weg'",
     r.userId === null && r.httpStatus !== 404, r);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
