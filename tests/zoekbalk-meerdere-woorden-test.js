/**
 * De zoekbalk van Items: elk woord los, in elke volgorde (Janneke, 08-10-2026).
 * "winterjas noppies" vond niets, omdat de hele zin aaneen gezocht werd.
 * Draait de echte code uit frontend/app.html: leesZoekterm en het zoekblok.
 * Draaien: node tests/zoekbalk-meerdere-woorden-test.js
 */
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "../frontend/app.html"), "utf8");

const start = html.indexOf("function leesZoekterm(");
const leesZoekterm = new Function(html.slice(start, html.indexOf("\n}\n", start) + 2) + "; return leesZoekterm;")();
const blokStart = html.indexOf("    if (search) {", html.indexOf("const filtered = state.items.filter"));
const blok = html.slice(blokStart, html.indexOf("\n    }\n", blokStart) + 6);
const past = new Function("item", "search", blok + "; return true;");

const items = [
  { title: "Winterjas meisje Noppies maat 104", brand: "Noppies", size: "104" },
  { title: "Winterjas Z8 maat 110", brand: "Z8" },
  { title: "Longsleeve Noppies maat 44/50", brand: "Noppies" },
];
const zoek = (q) => items.filter((it) => past(it, leesZoekterm(q).los)).map((it) => it.title);
let fout = 0;
const check = (naam, ok) => { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}`); if (!ok) fout++; };
check("winterjas noppies → alleen de Noppies-winterjas",
  JSON.stringify(zoek("winterjas noppies")) === JSON.stringify(["Winterjas meisje Noppies maat 104"]));
check("andere volgorde werkt ook", zoek("noppies winterjas").length === 1);
check("één woord blijft werken", zoek("noppies").length === 2);
check("winterjas 104 via de maat", zoek("winterjas 104").length === 1);
check("leeg zoekveld laat alles zien", zoek("").length === 3);
process.exit(fout ? 1 : 0);
