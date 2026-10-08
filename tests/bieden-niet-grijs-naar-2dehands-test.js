/**
 * Amanda (amandaonline001, 8f91a370), 08-10-2026: "waarom ik continue vastloop
 * met tekst om iets te crosslisten".
 *
 * 56 van haar Marktplaats-advertenties staan op "Bieden": geen bedrag. De server
 * kent die vorm (zonder_bedrag, en _prijsvorm_uit_eigen_advertentie leest hem van
 * haar eigen Marktplaats-advertentie als hij nog niet bekend is), maar het
 * publiceervenster eiste altijd een bedrag. 2dehands stond bij elk van die 56
 * dus grijs met "Missing: Price — fill in", terwijl 2dehands Bieden gewoon kent.
 *
 * Deze test draait de échte functie uit app.html.
 *
 * Draaien: node tests/bieden-niet-grijs-naar-2dehands-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const html = fs.readFileSync(path.join(__dirname, "..", "frontend/app.html"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function pakFunctie(naam) {
  const start = html.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  let diepte = 0, i = html.indexOf("{", start);
  for (; i < html.length; i++) {
    if (html[i] === "{") diepte++;
    else if (html[i] === "}") { diepte--; if (!diepte) break; }
  }
  return html.slice(start, i + 1);
}

const ctx = {
  CROSSLIST_UNIVERSAL_REQUIRED: ["price", "description", "photo_urls"],
  CROSSLIST_PLATFORM_REQUIRED: {
    marktplaats: ["category", "gender", "brand", "size", "color"],
    "2dehands": ["category", "gender", "brand", "size", "color"],
  },
  CROSSLIST_NON_CLOTHING_PLATFORM_REQUIRED: ["category"],
  CROSSLIST_FIELD_LABELS: { price: "Price" },
  isNonClothingItem: () => false,
  state: { listings: [] },
};
vm.createContext(ctx);
for (const naam of ["missingFieldsForPlatform", "prijsvormZonderBedrag"]) {
  if (html.includes(`function ${naam}(`)) vm.runInContext(pakFunctie(naam), ctx);
}

// Een echt artikel van Amanda: Cast Iron-overhemd, op Marktplaats als Bieden.
const OVERHEMD = {
  id: "art-1", title: "Cast Iron heren overhemd - Nieuw met kaartjes", price: null,
  description: "Nieuw en ongedragen", photo_urls: ["a.jpg"], category: "heren overhemden",
  gender: "men", brand: "Cast Iron", size: "M", color: "blauw",
};
const MP_ADVERTENTIE = { item_id: "art-1", platform: "marktplaats", status: "active",
  platform_listing_url: "https://www.marktplaats.nl/v/kleding-heren/overhemden/m2450203581" };
const mist = (item, p) => vm.runInContext("missingFieldsForPlatform", ctx)(item, p);

console.log("\nBekende prijsvorm Bieden:");
check("2dehands vraagt geen bedrag", !mist({ ...OVERHEMD, price_type: "FAST_BID" }, "2dehands").includes("Price"),
  JSON.stringify(mist({ ...OVERHEMD, price_type: "FAST_BID" }, "2dehands")));
check("Marktplaats ook niet", !mist({ ...OVERHEMD, price_type: "FAST_BID" }, "marktplaats").includes("Price"));
check("Vinted kent geen Bieden, daar blijft een bedrag nodig",
  mist({ ...OVERHEMD, price_type: "FAST_BID" }, "vinted").includes("Price"));
check("FIXED zonder bedrag blijft een gebrek",
  mist({ ...OVERHEMD, price_type: "FIXED" }, "2dehands").includes("Price"));

console.log("\nVorm nog onbekend, wel een eigen Marktplaats-advertentie (Amanda's 56):");
ctx.state.listings = [MP_ADVERTENTIE];
check("2dehands laat de server de vorm opzoeken", !mist(OVERHEMD, "2dehands").includes("Price"),
  JSON.stringify(mist(OVERHEMD, "2dehands")));
check("Vinted blijft om een bedrag vragen", mist(OVERHEMD, "vinted").includes("Price"));

console.log("\nGeen advertentie om de vorm van te lezen:");
ctx.state.listings = [];
check("dan blijft een bedrag nodig", mist(OVERHEMD, "2dehands").includes("Price"));
ctx.state.listings = [{ ...MP_ADVERTENTIE, platform_listing_url: null }];
check("ook niet bij een rij zonder adres", mist(OVERHEMD, "2dehands").includes("Price"));
check("met een bedrag is er niets aan de hand",
  !mist({ ...OVERHEMD, price: 20 }, "2dehands").includes("Price"));

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
process.exit(mislukt ? 1 : 0);
