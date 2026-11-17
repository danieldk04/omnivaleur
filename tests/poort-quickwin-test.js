/**
 * Quick win voor nieuwe klanten (Daniel, 16-11-2026): de poort start het inlezen
 * zelf en zet één artikel klaar voor "Place it now". Draait de echte code uit
 * frontend/poort.js met een nagebouwd dashboard eromheen.
 *
 * Draaien:  node tests/poort-quickwin-test.js
 */
const fs = require("fs");
const path = require("path");
const BRON = fs.readFileSync(path.join(__dirname, "..", "frontend", "poort.js"), "utf8");
let mislukt = 0;
const ok = (naam, v, kreeg) => { if (v) return console.log(`  ✓ ${naam}`); mislukt++; console.log(`  ✗ ${naam} - kreeg ${JSON.stringify(kreeg)}`); };

function bouw(opslagInhoud, state, extra) {
  const window = Object.assign({ state }, extra || {});
  const opslag = Object.assign({}, opslagInhoud);
  const ls = { getItem: (k) => (k in opslag ? opslag[k] : null), setItem: (k, v) => { opslag[k] = String(v); } };
  const document = { getElementById: () => null, querySelector: () => null, querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}), hidden: true };
  new Function("window", "document", "setInterval", "setTimeout", "addEventListener", "localStorage", "navigator", BRON)(
    window, document, () => {}, () => {}, () => {}, ls, {});
  return { P: window.OBPoort, window, opslag };
}
const item = (id, o) => Object.assign({ id, title: "Jas " + id, price: 25, description: "mooi", photo_urls: ["x.jpg"] }, o || {});
const klaar = () => [];

console.log("1. Beste artikel voor de eerste plaatsing");
const ING = (...p) => Object.fromEntries(p.map((k) => [k, { ingelogd: true }]));
let t = bouw({}, { items: [item("a", { price: 0 }), item("b", { photo_urls: [] }), item("c")], listings: [] },
  { missingFieldsForPlatform: (i, p) => (i.id === "c" ? [] : ["x"]) });
let b = t.P.besteArtikel({ kanalen: ING("marktplaats") });
ok("kiest het artikel met foto, prijs en niets ontbrekend", b && b.item.id === "c" && b.kanaal === "marktplaats", b);
ok("geen ingelogd kanaal: geen artikel", t.P.besteArtikel({ kanalen: {} }) === null);
ok("kanaal bewezen uitgelogd: geen artikel", t.P.besteArtikel({ kanalen: { marktplaats: { ingelogd: false } } }) === null);
t = bouw({}, { items: [item("a")], listings: [] }, { missingFieldsForPlatform: () => ["category"] });
ok("alles mist iets: geen artikel (nooit meteen een foutmelding)", t.P.besteArtikel({ kanalen: ING("vinted") }) === null);
t = bouw({}, { items: [item("a")], listings: [{ item_id: "a", platform: "marktplaats", status: "active" }] }, { missingFieldsForPlatform: klaar });
ok("al live op Marktplaats: valt daar af", t.P.besteArtikel({ kanalen: ING("marktplaats") }) === null);
b = t.P.besteArtikel({ kanalen: ING("marktplaats", "2dehands") });
ok("maar mag wel naar 2dehands (de echte winst na een Marktplaats-import)", b && b.kanaal === "2dehands", b);
t = bouw({}, { items: [item("a")], listings: [] }, { missingFieldsForPlatform: klaar });
ok("Marktplaats gaat voor Vinted", t.P.besteArtikel({ kanalen: ING("vinted", "marktplaats") }).kanaal === "marktplaats");
t = bouw({}, { items: [item("v", { photo_urls: ["https://images1.vinted.net/a.jpeg"] }), item("e", { photo_urls: ["https://img.omnivaleur.com/a.jpg"] })], listings: [] }, { missingFieldsForPlatform: klaar });
ok("Marktplaats: eerst het artikel met eigen foto's, niet de Vinted-fotolink", t.P.besteArtikel({ kanalen: ING("marktplaats") }).item.id === "e");
ok("Vinted zelf mag wel een Vinted-foto", t.P.besteArtikel({ kanalen: ING("vinted") }).item.id === "v");

// Verantwoordelijke partij (17-11-2026): zonder die gegevens weigert Marktplaats/2dehands te plaatsen.
t = bouw({}, { items: [item("a")], listings: [] }, { missingFieldsForPlatform: klaar, fabrikantCompleet: () => false });
b = t.P.besteArtikel({ kanalen: ING("vinted", "marktplaats", "2dehands") });
ok("gegevens leeg: eerst Vinted, daar is niets voor nodig", b && b.kanaal === "vinted" && b.nodigGegevens === false, b);
b = t.P.besteArtikel({ kanalen: ING("marktplaats", "2dehands") });
ok("gegevens leeg en alleen MP/2dehands: kaart vraagt ze zelf", b && b.kanaal === "marktplaats" && b.nodigGegevens === true, b);
t = bouw({}, { items: [item("a")], listings: [] }, { missingFieldsForPlatform: klaar, fabrikantCompleet: () => true });
b = t.P.besteArtikel({ kanalen: ING("vinted", "marktplaats") });
ok("gegevens ingevuld: Marktplaats gaat weer voor, zonder vraag", b && b.kanaal === "marktplaats" && b.nodigGegevens === false, b);

console.log("2. Automatisch inlezen");
let aantal = 0, scherm = null;
t = bouw({}, { items: [], listings: [] }, { importAllesBezig: false, importeerAlleKanalen: () => { aantal++; return Promise.resolve(); }, showView: (v) => { scherm = v; } });
t.P.autoImport({ gekozen: ["marktplaats", "facebook"] });
ok("start het inlezen zonder klik", aantal === 1, aantal);
ok("alleen leesbare kanalen (Facebook niet)", t.opslag.importKanalen === JSON.stringify(["marktplaats"]), t.opslag.importKanalen);
ok("gaat naar het importscherm", scherm === "import", scherm);
t.P.autoImport({ gekozen: ["marktplaats"] });
ok("niet nog een keer binnen tien minuten", aantal === 1, aantal);
aantal = 0;
t = bouw({ "ob-auto-import-om": String(Date.now() - 11 * 60 * 1000) }, { items: [] }, { importAllesBezig: false, importeerAlleKanalen: () => { aantal++; return Promise.resolve(); } });
t.P.autoImport({ gekozen: ["vinted"] });
ok("na tien minuten zonder artikel opnieuw", aantal === 1, aantal);
aantal = 0;
t = bouw({}, { items: [] }, { importAllesBezig: true, importeerAlleKanalen: () => { aantal++; } });
t.P.autoImport({ gekozen: ["vinted"] });
ok("tijdens een lopende import geen tweede", aantal === 0, aantal);
t = bouw({}, { items: [] }, { importAllesBezig: false, importeerAlleKanalen: () => { aantal++; } });
t.P.autoImport({ gekozen: ["facebook"] });
ok("alleen Facebook gekozen: niets te lezen, dus niets starten", aantal === 0, aantal);

console.log(mislukt ? `\n${mislukt} mislukt` : "\nAlles ok");
process.exit(mislukt ? 1 : 0);
