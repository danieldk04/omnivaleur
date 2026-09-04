/**
 * Egbert Brouwer (Papa's Plectrums), 04-09-2026, twee klachten in één mail:
 *
 *  1. "Waar kan ik die knop vinden om alle rode balken weg te halen, ik zie hem
 *     niet maar heb al wel de laatste versie?" — de knop bestond, maar zat
 *     verstopt achter een klik op een rode balk in de lijst.
 *  2. "Je vraagt: publiceer een enkel artikel naar Marktplaats. Die
 *     mogelijkheid is er niet omdat MP al geselecteerd staat." — al zijn 5.533
 *     advertenties komen uit de Marktplaats-import, dus élk artikel stond in
 *     het publiceervenster op "✓ Listed" zonder aanvinkvakje. Op Publish kwam
 *     alleen "Choose at least one platform".
 *
 * Deze test draait de échte functies uit app.html. Met een pad als argument
 * draait hij tegen een oudere kopie: zo is te zien dat die oude kopie hier
 * faalt en de nieuwe niet.
 *
 * Draaien: node tests/egbert-rode-balken-en-listed-test.js
 *          node tests/egbert-rode-balken-en-listed-test.js /tmp/oude-app.html
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
  const start = html.indexOf(`function ${naam}(`);
  if (start < 0) return null;
  let diepte = 0, i = html.indexOf("{", start);
  for (; i < html.length; i++) {
    if (html[i] === "{") diepte++;
    else if (html[i] === "}") { diepte--; if (!diepte) break; }
  }
  return html.slice(start, i + 1);
}

const balken = {};
const ctx = {
  PLATFORMS: ["marktplaats", "2dehands", "vinted", "facebook"],
  PLATFORM_LABELS: { marktplaats: "Marktplaats", "2dehands": "2dehands",
                     vinted: "Vinted", facebook: "Facebook Marketplace" },
  PLATFORM_ICONS: { marktplaats: "M", "2dehands": "2", vinted: "V", facebook: "F" },
  API_PLATFORMS_FE: new Set(["ebay", "shopify"]),
  BETA_PLATFORMS: new Set(["facebook"]),
  esc: (s) => String(s == null ? "" : s),
  platformOordeel: () => ({ oordeel: "ok", reden: "" }),
  missingFieldsForPlatform: () => [],
  state: { connected: [], listings: [], items: [] },
  document: {
    getElementById: (id) => (balken[id] ||= { id, style: {}, innerHTML: "" }),
  },
  console,
};
ctx.window = ctx;
vm.createContext(ctx);

// ── 1. De opruimknop moet boven de lijst staan ───────────────────
console.log("Zes bladzijden rood: is er één knop die ze allemaal opruimt?");

const bron = pakFunctie("renderPublishErrorBar");
check("renderPublishErrorBar bestaat", !!bron,
      "de opruimknop zit alleen in het foutvenster, niet boven de lijst");
check("de lijst tekent hem ook echt",
      /renderDuplicateBar\(\);\s*\n\s*renderPublishErrorBar\(\);/.test(html),
      "de functie wordt nergens aangeroepen");
check("er staat een plek voor in het scherm",
      /id="publish-error-bar"/.test(html));

if (bron) {
  vm.runInContext(bron, ctx);
  // Zijn echte situatie: 303 mislukte 2dehands-publicaties en 11 op Marktplaats.
  ctx.state.listings = [
    ...Array.from({ length: 303 }, (_, i) => ({ item_id: "i" + i, platform: "2dehands", status: "error" })),
    ...Array.from({ length: 11 }, (_, i) => ({ item_id: "m" + i, platform: "marktplaats", status: "error" })),
    { item_id: "ok1", platform: "marktplaats", status: "active" },
  ];
  ctx.renderPublishErrorBar();
  const uit = balken["publish-error-bar"].innerHTML;
  check("hij noemt het totaal", /314 publishes failed/.test(uit), uit.slice(0, 120));
  check("één knop ruimt alles op, over de kanalen heen",
        /clearAllPublishErrors\(\)/.test(uit) && /Clear all 314/.test(uit));
  check("per kanaal blijft het uit te splitsen", /303 on 2dehands/.test(uit));
  check("en Marktplaats staat er apart bij", /11 on Marktplaats/.test(uit));
  check("het grootste kanaal staat vooraan",
        uit.indexOf("303 on") < uit.indexOf("11 on"));
  check("elk kanaal is een klik naar de bestaande opruiming",
        /clearPublishError\(null,'2dehands'/.test(uit));
  check("hij zegt dat er niets van het platform af gaat",
        /nothing is removed from any platform/i.test(uit));
  check("de knoppenbalk is er niet meer", !/Clear 303 on 2dehands/.test(uit),
        "vier kanalen = vier knoppen naast elkaar, breder dan de melding zelf");
  check("de opruimronde bestaat", /function clearAllPublishErrors\(/.test(html));
  check("gezonde advertenties tellen niet mee", !/315|304/.test(uit));

  // Zonder fouten hoort de balk weg te zijn, anders staat er eeuwig rood.
  ctx.state.listings = [{ item_id: "ok1", platform: "marktplaats", status: "active" }];
  ctx.renderPublishErrorBar();
  check("geen fouten = geen balk", balken["publish-error-bar"].style.display === "none");
}

// ── 2. Een artikel dat al op Marktplaats staat, moet te kiezen zijn ──
console.log("\nAlles komt uit de import: valt er dan nog iets te publiceren?");

vm.runInContext(pakFunctie("renderPlatformCheckboxes"), ctx);
const ITEM = "8f2c1a44-77b1-4d0e-9a3c-0b5e2d9f1a10";
ctx.state.items = [{ id: ITEM, title: "Golfballen bedrukt - I Love Golf! - set van 3" }];
ctx.state.listings = [{ item_id: ITEM, platform: "marktplaats", status: "active" }];
ctx.renderPlatformCheckboxes("crosslist-platform-checkboxes", ITEM);
const venster = balken["crosslist-platform-checkboxes"].innerHTML;

const mpBlok = venster.slice(venster.indexOf("Marktplaats") - 400,
                            venster.indexOf("Marktplaats") + 200);
check("Marktplaats blijft zichtbaar als 'Listed'", /✓ Listed/.test(venster));
check("maar is nu wél aan te vinken",
      /<input type="checkbox" value="marktplaats"(?![^>]*disabled)/.test(venster),
      "het vakje is een mededeling, geen keuze — publiceren naar Marktplaats kan niet");
check("met een waarschuwing eraan vast",
      /bevestigOpnieuwPlaatsen/.test(venster));

const waarschuwing = pakFunctie("bevestigOpnieuwPlaatsen");
check("de waarschuwing bestaat", !!waarschuwing);
if (waarschuwing) {
  check("hij noemt de tweede advertentie met zoveel woorden",
        /SECOND advert/.test(waarschuwing));
  check("niet bevestigen = vakje weer uit",
        /if \(!ok\) cb\.checked = false;/.test(waarschuwing));
}

// ── 3. En als er écht niets te kiezen is, geen loze vraag ──
console.log("\nNiets aan te vinken: krijgt hij dan uitleg of alleen een vraag?");
const tekstfn = pakFunctie("geenPlatformGekozen");
check("geenPlatformGekozen bestaat", !!tekstfn,
      "Publish antwoordt met 'Choose at least one platform' en verder niets");
check("Publish gebruikt hem ook",
      /return alert\(geenPlatformGekozen\('crosslist-platform-checkboxes'\)\)/.test(html));
if (tekstfn) {
  vm.runInContext(tekstfn, ctx);
  balken["leeg"] = { innerHTML: "", querySelectorAll: () => [
    { disabled: true }, { disabled: true },
  ]};
  check("alles op slot geeft uitleg",
        /no channel you can publish this to/.test(ctx.geenPlatformGekozen("leeg")));
  balken["half"] = { innerHTML: "", querySelectorAll: () => [
    { disabled: true }, { disabled: false },
  ]};
  check("valt er wél iets te kiezen, dan gewoon de korte vraag",
        /Choose at least one platform/.test(ctx.geenPlatformGekozen("half")));
}

// ── 4. "Fill from Marktplaats" is een actie, geen filter ──
console.log("\nStaat 'Fill 61 from Marktplaats' op een logische plek?");
const filterbalk = html.slice(html.indexOf('<div class="filter-bar">'),
                              html.indexOf('<div class="bulk-bar" id="bulk-bar">'));
check("hij hangt niet meer tussen de keuzelijstjes",
      !/id="mp-fill-btn"/.test(filterbalk),
      "hij zweeft op een eigen regel naast het aantal artikelen");
check("en staat bij de knoppen boven de lijst",
      /id="mp-fill-btn"[\s\S]{0,900}?onclick="openAddItem\(\)"/.test(html));
check("Vinted gaat mee", !/id="vinted-fill-btn"/.test(filterbalk));
check("het aantal artikelen staat onder de titel, niet achteraan een rij die afbreekt",
      /items-sub-label'\);\n\s*if \(teller\) teller\.textContent/.test(html)
      && !/id="filter-count"/.test(html),
      "het hing achter een flex-spacer en belandde dus linksonder op een eigen regel");
check("de filterbalk bevat alleen nog filters",
      !/filter-reset|filter-spacer|mp-fill-btn|vinted-fill-btn/.test(filterbalk));
check("'Clear filters' staat bij het aantal dat overblijft",
      /id="items-sub-label"[\s\S]{0,260}id="filter-reset"/.test(html));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
