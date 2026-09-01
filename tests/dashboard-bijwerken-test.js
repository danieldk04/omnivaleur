/**
 * Het dashboard werkt bij zonder de hele catalogus opnieuw op te halen.
 *
 * WAAROM DIT ER IS (01-09-2026). De ronde die elke 15 seconden liep haalde élke
 * keer alles op: bij het grootste account 15 MB en zo'n negentig opvragingen,
 * vier keer per minuut. Dat was de verklaring voor 2,17 GB Supabase-verkeer in
 * anderhalve dag bij zeven gebruikers.
 *
 * Bijwerken-op-wijziging is goedkoop, maar het mag nooit een verkeerd scherm
 * opleveren: een verwijderd item moet verdwijnen, een gewijzigd item moet
 * veranderen, en een hapering mag geen lege catalogus tonen (dat is de fout die
 * Egbert Brouwer zijn 240 zojuist geïmporteerde items "kwijt" liet raken).
 * Daarom draait hier de échte functie uit app.html.
 *
 * Draaien:  node tests/dashboard-bijwerken-test.js
 */
const fs = require("fs");
const path = require("path");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");

function functieUit(naam) {
  let start = APP.indexOf(`async function ${naam}(`);
  if (start < 0) start = APP.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  const eind = APP.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(start, eind + 2);
}

let volledigOpgehaald = 0;
let antwoord = { ok: true, body: {} };

const state = { items: [] };
const API = "";
const encodeURIComponent_ = encodeURIComponent;

async function apiFetch() {
  return { ok: antwoord.ok, status: antwoord.ok ? 200 : 500 };
}
async function parseJsonSafe() {
  return antwoord.body;
}
async function fetchAllItems() {
  volledigOpgehaald++;
  return antwoord.alles || [];
}

// `_itemsSinds` staat in app.html buiten de functie; hier zetten we hem zelf.
const bron = "let _itemsSinds = '2026-09-01T00:00:00Z';\n"
  + functieUit("_sorteerAlsServer") + "\n" + functieUit("syncItems");
const syncItems = new Function(
  "state", "API", "apiFetch", "parseJsonSafe", "fetchAllItems",
  bron + "\nreturn syncItems;"
)(state, API, apiFetch, parseJsonSafe, fetchAllItems);

const it = (id, updated, titel) => ({
  id, title: titel || id, created_at: "2026-01-01T00:00:00+00:00", updated_at: updated,
});

let mislukt = 0;
function check(naam, gelukt) {
  console.log(`${gelukt ? "  ok" : "FOUT"}  ${naam}`);
  if (!gelukt) mislukt++;
}

(async () => {
  // 1. Niets veranderd: dezelfde catalogus, en geen volledige ophaalronde.
  state.items = [it("a", "2026-09-01T10:00:00Z"), it("b", "2026-09-01T09:00:00Z")];
  volledigOpgehaald = 0;
  antwoord = { ok: true, body: { items: [], count: 2, truncated: false } };
  let uit = await syncItems();
  check("niets veranderd → catalogus blijft heel", uit.length === 2);
  check("niets veranderd → niets volledig opgehaald", volledigOpgehaald === 0);

  // 2. Eén gewijzigd item vervangt precies die ene rij.
  antwoord = { ok: true, body: {
    items: [it("a", "2026-09-01T12:00:00Z", "nieuwe titel")], count: 2, truncated: false } };
  uit = await syncItems();
  check("gewijzigd item wordt vervangen",
        uit.find(i => i.id === "a").title === "nieuwe titel");
  check("de rest blijft ongemoeid", uit.find(i => i.id === "b").title === "b");
  check("er komen geen dubbele rijen bij", uit.length === 2);

  // 3. Dezelfde rij nog een keer (dat gebeurt: de grens is >=, niet >).
  state.items = uit;
  antwoord = { ok: true, body: {
    items: [it("a", "2026-09-01T12:00:00Z", "nieuwe titel")], count: 2, truncated: false } };
  uit = await syncItems();
  check("dezelfde rij nogmaals levert geen duplicaat", uit.length === 2);

  // 4. Een verwijderd item laat geen wijziging achter — alleen het totaal.
  state.items = [it("a", "2026-09-01T10:00:00Z"), it("b", "2026-09-01T09:00:00Z")];
  volledigOpgehaald = 0;
  antwoord = { ok: true, alles: [it("a", "2026-09-01T10:00:00Z")],
               body: { items: [], count: 1, truncated: false } };
  uit = await syncItems();
  check("verwijderd item → alles opnieuw ophalen", volledigOpgehaald === 1);
  check("verwijderd item → verdwijnt van het scherm", uit.length === 1);

  // 5. Te veel wijzigingen tegelijk (een import).
  state.items = [it("a", "2026-09-01T10:00:00Z")];
  volledigOpgehaald = 0;
  antwoord = { ok: true, alles: [it("a", "x"), it("b", "x")],
               body: { items: [it("a", "x")], count: 99, truncated: true } };
  uit = await syncItems();
  check("te veel wijzigingen → alles opnieuw ophalen", volledigOpgehaald === 1);

  // 6. Een nieuw item komt op de plek waar de server het ook zou zetten.
  state.items = [
    { id: "oud", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  ];
  volledigOpgehaald = 0;
  antwoord = { ok: true, body: {
    items: [{ id: "nieuw", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" }],
    count: 2, truncated: false } };
  uit = await syncItems();
  check("nieuwste staat vooraan", uit[0].id === "nieuw");

  // 7. Een hapering is een fout, geen lege catalogus.
  state.items = [it("a", "2026-09-01T10:00:00Z")];
  antwoord = { ok: false, body: { detail: "Connection hiccup" } };
  let gooide = false;
  try { await syncItems(); } catch (e) { gooide = true; }
  check("een hapering wordt gemeld, niet als 'geen items'", gooide);

  console.log(mislukt ? `\n${mislukt} test(s) mislukt` : "\nAlles goed.");
  process.exit(mislukt ? 1 : 0);
})();
