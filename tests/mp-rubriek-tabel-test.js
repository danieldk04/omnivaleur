/**
 * Elke regel van MP_CATEGORIES moet kloppen met het plaatsformulier van Marktplaats zelf.
 *
 * WAAROM (02-11-2026, Esther). De rubriek is na het plaatsen niet meer te wijzigen. Gemeten tegen
 * de ingelogde boom (tests/fixtures/marktplaats_formulierboom_02-11-2026.json): alle regels
 * bestaan, maar zwemkleding, ondergoed, leggings en accessoires gingen onder een verkeerde rubriek.
 * Draaien:    node tests/mp-rubriek-tabel-test.js
 * Voor-en-na: node tests/mp-rubriek-tabel-test.js <oude background.js>
 */
const fs = require("fs");
const path = require("path");
const BESTAND = process.argv[2] || path.join(__dirname, "..", "extension", "background.js");
const SRC = fs.readFileSync(BESTAND, "utf8");
const BOOM = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "marktplaats_formulierboom_02-11-2026.json"), "utf8")).boom;

const a = SRC.indexOf("const MP_CATEGORIES = {");
const b = SRC.indexOf("\n};", a);
const BLOK = SRC.slice(a, b + 3);
// De tabel verwijst naar maatlijsten (sizeMap: MP_BABY_SIZES); voor deze test zijn lege lijsten genoeg.
const NAMEN = [...new Set([...BLOK.matchAll(/sizeMap:\s*([A-Z_]+)/g)].map((m) => m[1]))];
const MP = new Function(NAMEN.map((x) => `const ${x} = {};`).join("\n") + "\n" +
  BLOK.replace("const MP_CATEGORIES =", "return").replace(/\n};$/, "\n}"))();
let fouten = 0;
const eis = (naam, ok, extra = "") => { if (!ok) { fouten++; console.log("FOUT  " + naam + " " + extra); } };

let n = 0;
for (const [sleutel, r] of Object.entries(MP)) {
  const t = BOOM[String(r.cat1)];
  if (!t) { eis(sleutel, false, `hoofdrubriek ${r.cat1} niet in de boom`); continue; }
  const buckets = r.bucketId == null ? Object.keys(t) : [String(r.bucketId)];
  const ok = buckets.some((bk) => (t[bk] || []).includes(r.cat3));
  eis(sleutel, ok, `cat3 ${r.cat3} staat niet in bucket ${r.bucketId} van ${r.cat1}`);
  n++;
}
console.log(`${n} regels nagelopen tegen de boom van Marktplaats`);

const isRegel = (k, c1, c3, bk) => { const r = MP[k]; return r && r.cat1 === c1 && r.cat3 === c3 && r.bucketId === bk; };
eis("zwemkleding is Badmode en Zwemkleding", isRegel("zwemkleding", 621, 622, 160));
eis("badkleding is Badmode en Zwemkleding", isRegel("badkleding", 621, 622, 160));
eis("ondergoed is Ondergoed en Lingerie", isRegel("ondergoed", 621, 632, 160));
eis("leggings is Leggings en Panty's", isRegel("leggings", 621, 1676, 164));
eis("heren zwembroeken is Badmode, Zwemkleding", isRegel("heren zwembroeken", 1776, 1778, 167));
eis("heren ondergoed is Ondergoed", isRegel("heren ondergoed", 1776, 1675, 167));
eis("accessoires dames valt niet meer terug op Blouses", MP["accessoires dames"].cat3 !== 628);
eis("heren accessoires valt niet meer terug op Truien", MP["heren accessoires"].cat3 !== 652);

// De titelkeuze voor accessoires
const f = SRC.indexOf("const MP_ACCESSOIRES = {");
if (f < 0) {
  eis("accessoires worden per titel gekozen", false, "(mpAccessoireRubriek ontbreekt)");
} else {
  const f = SRC.indexOf("const MP_ACCESSOIRES = {");
  const g = SRC.indexOf("function getMpSyiUrl(");
  const acc = new Function(SRC.slice(f, g) + "\nreturn mpAccessoireRubriek;")();
  const kies = (cat, gender, titel) => { const r = acc(cat, gender, titel); return r ? `${r.cat1}/${r.cat3}/${r.bucketId}` : null; };
  eis("vintage hoed -> Hoeden en Petten", kies("accessoires dames", "dames", "Vintage zwarte hoed met veer") === "621/624/159");
  eis("zijden sjaal -> Mutsen, Sjaals", kies("accessoires dames", "dames", "Zijden sjaal Hermes stijl") === "621/1679/159");
  eis("lederen riem -> Riemen", kies("unisex accessoires", "dames", "Lederen riem 80 cm") === "621/1493/159");
  eis("handtas -> Damestassen", kies("accessoires dames", "dames", "Krokodillenleer handtas") === "621/626/159");
  eis("stropdas heren -> Stropdassen", kies("heren accessoires", "heren", "Zijden stropdas bordeaux") === "1776/643/166");
  eis("unisex + heren + pet -> heren Hoeden", kies("unisex accessoires", "heren", "Platte pet tweed") === "1776/641/166");
  eis("onbekend accessoire -> geen keuze (terugval uit de tabel)", kies("accessoires dames", "dames", "Broche parel") === null);
  eis("andere categorie -> geen keuze", kies("jurken", "dames", "Hoed jurk") === null);
  // elke gekozen accessoirerubriek moet in de boom staan
  for (const lijst of Object.values(new Function(SRC.slice(f, SRC.indexOf("function mpAccessoireRubriek")) + "\nreturn MP_ACCESSOIRES;")()))
    for (const [, r] of lijst) eis(`accessoire ${r.cat1}/${r.cat3}`, (BOOM[String(r.cat1)][String(r.bucketId)] || []).includes(r.cat3));
}

console.log(fouten ? `\n${fouten} FOUT` : "\nalles ok");
process.exit(fouten ? 1 : 0);
