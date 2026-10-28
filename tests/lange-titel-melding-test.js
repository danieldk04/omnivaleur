/**
 * Melding in het dashboard als een titel langer is dan 60 tekens.
 *
 * WAAROM DIT ER IS (28-10-2026, Mieneke van Voordeelsieraden). Shopify-titels zijn
 * vaak langer dan de 60 tekens die Marktplaats en 2dehands nemen. De server kort
 * ze bij het plaatsen in, maar de klant zag dat vooraf niet en vroeg om een
 * melding zoals "Voeg rubriek toe voor Marktplaats".
 *
 * Deze proef draait de ECHTE functies uit frontend/app.html.
 *
 * Draaien:  node tests/lange-titel-melding-test.js
 */
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const SRC = fs.readFileSync(path.resolve(__dirname, "..", "frontend", "app.html"), "utf8");
const a = SRC.indexOf("const MP_MAX_TITEL = 60;");
const b = SRC.indexOf("function smartMissingBadgeHoofd(item) {");
if (a < 0 || b < 0 || b < a) { console.error("functies niet gevonden in app.html"); process.exit(1); }
const CODE = SRC.slice(a, b);

function maak(state) {
  const f = new Function("state", "esc", "smartMissingBadgeHoofd",
    CODE + "\nreturn { langeTitelBadge, smartMissingBadge };");
  return f(state, (t) => String(t).replace(/"/g, "&quot;"), () => "<HOOFD>");
}

const tekens = (n) => "a".repeat(n);
const basis = { connected: ["marktplaats", "2dehands", "shopify"], listings: [] };
let fouten = 0;
function proef(naam, fn) {
  try { fn(); console.log("ok    " + naam); }
  catch (e) { fouten++; console.log("FOUT  " + naam + "\n      " + e.message); }
}

proef("60 tekens: geen melding", () => {
  const { langeTitelBadge } = maak(basis);
  assert.strictEqual(langeTitelBadge({ id: "1", title: tekens(60) }), "");
});
proef("61 tekens: melding met het aantal", () => {
  const { langeTitelBadge } = maak(basis);
  const h = langeTitelBadge({ id: "1", title: tekens(61) });
  assert.ok(h.includes("Title is 61 characters"), h);
  assert.ok(h.includes("missing-data-badge"));
});
proef("spaties aan de randen tellen niet mee (de server stript ook)", () => {
  const { langeTitelBadge } = maak(basis);
  assert.strictEqual(langeTitelBadge({ id: "1", title: "  " + tekens(60) + "  " }), "");
});
proef("100 tekens (lange Shopify-titel) geeft melding", () => {
  const { langeTitelBadge } = maak(basis);
  assert.ok(langeTitelBadge({ id: "1", title: tekens(100) }).includes("100 characters"));
});
proef("zonder gekoppeld Marktplaats of 2dehands: geen melding", () => {
  const { langeTitelBadge } = maak({ connected: ["shopify", "vinted"], listings: [] });
  assert.strictEqual(langeTitelBadge({ id: "1", title: tekens(90) }), "");
});
proef("alleen 2dehands gekoppeld: wel melding", () => {
  const { langeTitelBadge } = maak({ connected: ["2dehands"], listings: [] });
  assert.ok(langeTitelBadge({ id: "1", title: tekens(90) }) !== "");
});
proef("al live op beide: geen melding meer", () => {
  const l = (p) => ({ item_id: "1", platform: p, status: "active" });
  const { langeTitelBadge } = maak({ connected: basis.connected, listings: [l("marktplaats"), l("2dehands")] });
  assert.strictEqual(langeTitelBadge({ id: "1", title: tekens(90) }), "");
});
proef("live op Marktplaats, nog niet op 2dehands: nog wel melding", () => {
  const { langeTitelBadge } = maak({ connected: basis.connected,
    listings: [{ item_id: "1", platform: "marktplaats", status: "active" }] });
  assert.ok(langeTitelBadge({ id: "1", title: tekens(90) }) !== "");
});
proef("mislukte plaatsing telt niet als online", () => {
  const { langeTitelBadge } = maak({ connected: basis.connected,
    listings: [{ item_id: "1", platform: "marktplaats", status: "error" },
               { item_id: "1", platform: "2dehands", status: "error" }] });
  assert.ok(langeTitelBadge({ id: "1", title: tekens(90) }) !== "");
});
proef("advertentie van een ander artikel telt niet", () => {
  const { langeTitelBadge } = maak({ connected: basis.connected,
    listings: [{ item_id: "2", platform: "marktplaats", status: "active" },
               { item_id: "2", platform: "2dehands", status: "active" }] });
  assert.ok(langeTitelBadge({ id: "1", title: tekens(90) }) !== "");
});
proef("komt NAAST de melding over ontbrekende velden, vervangt hem niet", () => {
  const { smartMissingBadge } = maak(basis);
  const h = smartMissingBadge({ id: "1", title: tekens(90) });
  assert.ok(h.startsWith("<HOOFD>") && h.includes("90 characters"), h);
});
proef("geen titel: geen fout, geen melding", () => {
  const { langeTitelBadge } = maak(basis);
  assert.strictEqual(langeTitelBadge({ id: "1" }), "");
  assert.strictEqual(langeTitelBadge({ id: "1", title: null }), "");
});

console.log(fouten ? `\n${fouten} proef(proeven) rood` : "\nalles groen");
process.exit(fouten ? 1 : 0);
