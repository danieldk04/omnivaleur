/**
 * Zilver blijft zilver, en de ringmaat komt uit de omschrijving.
 *
 * WAAROM (02-11-2026, Mieneke van Voordeelsieraden): de Engelse kleur "Silver" werd
 * "Grijs" terwijl Marktplaats en 2dehands "Zilver" aanbieden, en 316 van haar 320
 * ringen hebben de maat alleen in de omschrijving, dus "Maat" bleef leeg.
 * Draaien:      node tests/ring-maat-en-zilver-test.js
 * Voor-en-na:   node tests/ring-maat-en-zilver-test.js <oude shared.js>   (de oude faalt)
 */
const fs = require("fs");
const path = require("path");
const BESTAND = process.argv[2] || path.join(__dirname, "..", "extension", "content", "shared.js");
const S = fs.readFileSync(BESTAND, "utf8");
const a = S.indexOf("const COLOUR_NL"), b = S.indexOf("// ── ALS ONZE WAARDE NIET IN DE LIJST");
const dc = new Function(S.slice(a, b) + "\nreturn { dutchColor };")();
const s = S.indexOf("function ringMaatUitTekst(");
let maat = () => "";
if (s >= 0) { const e = S.indexOf("\n  }\n", s) + 4; maat = new Function(S.slice(s, e) + "\nreturn ringMaatUitTekst;")(); }

let fouten = 0;
const eis = (naam, ok) => { console.log((ok ? "ok    " : "FOUT  ") + naam); if (!ok) fouten++; };
eis("Silver wordt Zilver", dc.dutchColor("Silver") === "Zilver");
eis("silver wordt Zilver", dc.dutchColor("silver") === "Zilver");
eis("Zilver blijft Zilver", dc.dutchColor("Zilver") === "Zilver");
eis("Grey blijft Grijs", dc.dutchColor("Grey") === "Grijs");
eis("Gold blijft Goud", dc.dutchColor("Gold") === "Goud");
const ring = (d, extra) => ({ category: "sieraden ringen", title: "Gouden ring", description: d, ...(extra || {}) });
eis("15,75(49) is Kleiner dan 17", maat(ring("Mooie ring, ringmaat is 15,75(49), breedte 3mm")) === "Kleiner dan 17");
eis("17,25(54) is 17 tot 18", maat(ring("ringmaat is 17,25(54), breedte")) === "17 tot 18");
eis("18 is 18 tot 19", maat(ring("ringmaat 18, breedte ringkop 6mm.")) === "18 tot 19");
eis("19,5 is 19 tot 20", maat(ring("Ringmaat: 19,5")) === "19 tot 20");
eis("20,5 is 20 of groter", maat(ring("ringmaat is 20,5")) === "20 of groter");
eis("ca. 15,5/16 pakt het eerste getal", maat(ring("ringmaat is ca. 15,5/16 (slank)")) === "Kleiner dan 17");
eis("eigen maat van het artikel gaat voor", maat(ring("ringmaat 18", { size: "ringmaat 19,5" })) === "ringmaat 19,5");
eis("geen ringmaat in tekst: leeg, geen gok", maat(ring("Mooie ring met diamant")) === "");
eis("omtrek alleen (54): leeg, geen gok", maat(ring("ringmaat 54")) === "");
eis("geen ring (jas): nooit", maat({ category: "dames jassen", description: "ringmaat 18" }) === "");
process.exit(fouten ? 1 : 0);
