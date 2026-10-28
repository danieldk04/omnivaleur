/**
 * Materiaal bij sieraden op Marktplaats en 2dehands.
 *
 * WAAROM DIT ER IS (28-10-2026, Mieneke van Voordeelsieraden). Marktplaats zet in
 * elke sieradenrubriek zelf Materiaal "Zilver" klaar en wij raakten het veld
 * nooit aan: elke gouden ring kwam als zilver online. Gemeten op het echte
 * formulier, zie de toelichting bij materiaalKeuze in extension/content/shared.js.
 *
 * Deze proef draait de ECHTE functies uit shared.js met de echte optielijsten
 * van het formulier (ringen, kettingen, armbanden, oorbellen, kettinghangers).
 *
 * Draaien:  node tests/extensie-materiaal-test.js
 */
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const SRC = fs.readFileSync(path.resolve(__dirname, "..", "extension", "content", "shared.js"), "utf8");
const a = SRC.indexOf("const MATERIAAL_ENGELS");
const b = SRC.indexOf("  // DE BESCHRIJVING ECHT TYPEN.");
if (a < 0 || b < 0) { console.error("materiaalfuncties niet gevonden in shared.js"); process.exit(1); }
const CODE = SRC.slice(a, b);

function maak(select, gezet) {
  const f = new Function("qs", "fillNativeSelect", "clog",
    CODE + "\nreturn { materiaalKeuze, vulMateriaal };");
  return f(() => select,
    (el, tekst) => { const i = el.options.findIndex((o) => o.text === tekst); if (i < 0) return false; el.selectedIndex = i; gezet.push(tekst); return true; },
    () => {});
}
const opt = (t, extra = {}) => ({ text: t, value: t === "Kies..." ? "" : t, disabled: t === "Kies...", ...extra });
const select = (lijst, gekozen = "Zilver") => {
  const options = ["Kies...", ...lijst].map((t) => opt(t));
  return { options, selectedIndex: options.findIndex((o) => o.text === gekozen) };
};
const LIJSTEN = {
  ringen: ["Goud", "Zilver", "IJzer of Staal", "Kunststof", "Overige materialen"],
  kettingen: ["Goud", "Kunststof", "Steen of Mineraal", "Zilver", "Overige materialen"],
  armbanden: ["Elastiek", "Goud", "Hout", "Kunststof of Plastic", "Leer", "Staal", "Zilver", "Overige materialen"],
  oorbellen: ["Goud", "Zilver", "Glas", "Overige materialen"],
  kettinghangers: ["Goud", "Zilver", "Glas of Kristal", "Steen of Mineraal", "Overige materialen"],
};

let fouten = 0;
function proef(naam, fn) {
  try { fn(); console.log("ok    " + naam); }
  catch (e) { fouten++; console.log("FOUT  " + naam + "\n      " + e.message); }
}
const keuze = (item, lijst = LIJSTEN.ringen) => maak(null, []).materiaalKeuze(item, lijst);

proef("gouden ring met kleur Gold: Goud (was Zilver)", () => {
  assert.strictEqual(keuze({ title: "Diamanten 14k gouden luxe dames ring", color: "Gold" }), "Goud");
});
proef("kleur Goud in het Nederlands", () => {
  assert.strictEqual(keuze({ title: "Saffier diamanten 18k Lady DI ring briljant", color: "Goud" }), "Goud");
});
proef("zilveren ring met kleur Silver: Zilver", () => {
  assert.strictEqual(keuze({ title: "Ring met steen", color: "Silver" }), "Zilver");
});
proef("titel zegt zilver, kleur zegt goud: titel wint", () => {
  assert.strictEqual(keuze({ title: "Zilveren hanger 925", color: "Gold" }, LIJSTEN.kettinghangers), "Zilver");
});
proef("titel noemt goud en zilver: kleur beslist", () => {
  assert.strictEqual(keuze({ title: "Goud en zilver armband", color: "Silver" }, LIJSTEN.armbanden), "Zilver");
  assert.strictEqual(keuze({ title: "Goud en zilver armband", color: "Gold" }, LIJSTEN.armbanden), "Goud");
});
proef("geen titelwoord en geen goud/zilver-kleur: Overige materialen, nooit Zilver", () => {
  assert.strictEqual(keuze({ title: "Ring met steen", color: "Blue" }), "Overige materialen");
  assert.strictEqual(keuze({ title: "Ring met steen", color: null }), "Overige materialen");
});
proef("eigen materiaal gaat voor: 'Stainless steel' bij armbanden wordt Staal", () => {
  assert.strictEqual(keuze({ title: "Armband", color: "Gold", material: "Stainless steel" }, LIJSTEN.armbanden), "Staal");
});
proef("eigen materiaal 'gouden': Goud; 'Silver': Zilver", () => {
  assert.strictEqual(keuze({ title: "x", material: "gouden" }), "Goud");
  assert.strictEqual(keuze({ title: "x", material: "Silver" }), "Zilver");
});
proef("onbekend eigen materiaal: Overige, niet Zilver", () => {
  assert.strictEqual(keuze({ title: "x", material: "Titanium", color: "Silver" }), "Overige materialen");
});
proef("lijst zonder Goud en Zilver (geen sieraden), geen eigen materiaal: niets doen", () => {
  assert.strictEqual(keuze({ title: "Tafel", color: "Bruin" }, ["Hout", "Metaal", "Overige materialen"]), "");
});
proef("alle vijf sieradenlijsten geven Goud voor een gouden artikel", () => {
  for (const [naam, lijst] of Object.entries(LIJSTEN)) {
    assert.strictEqual(keuze({ title: "Mooi sieraad", color: "Gold" }, lijst), "Goud", naam);
  }
});
proef("vulMateriaal zet het vooringevulde Zilver om naar Goud", async () => {
  const gezet = [], s = select(LIJSTEN.ringen, "Zilver");
  const ok = await maak(s, gezet).vulMateriaal({ title: "Gouden ring", color: "Gold" });
  assert.ok(ok); assert.deepStrictEqual(gezet, ["Goud"]);
  assert.strictEqual(s.options[s.selectedIndex].text, "Goud");
});
proef("vulMateriaal doet niets als het al goed staat (herhaalde reparatieronde)", async () => {
  const gezet = [], s = select(LIJSTEN.ringen, "Goud");
  await maak(s, gezet).vulMateriaal({ title: "Gouden ring", color: "Gold" });
  assert.deepStrictEqual(gezet, []);
});
proef("vulMateriaal zonder materiaalveld: geen fout, geen wijziging", async () => {
  const gezet = [];
  assert.strictEqual(await maak(null, gezet).vulMateriaal({ title: "x" }), true);
  assert.deepStrictEqual(gezet, []);
});

setTimeout(() => {
  console.log(fouten ? `\n${fouten} proef(proeven) rood` : "\nalles groen");
  process.exit(fouten ? 1 : 0);
}, 50);
