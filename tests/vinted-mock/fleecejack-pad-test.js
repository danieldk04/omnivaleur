// Een fleecejack hoort op Vinted onder Outerwear > Jackets > Fleece jackets,
// ook als het dashboard hem onder "heren truien" heeft staan (artikel 721,
// Ralph Lauren, 27-11-2026: hij kwam bij "Other jumpers & sweaters" uit).
const fs = require("fs");
const path = require("path");
const S = fs.readFileSync(path.resolve(__dirname, "../../extension/content/vinted.js"), "utf8");
const a = S.indexOf("  function fleecejackPad"), b = S.indexOf("  const job = await getJob();");
if (a < 0 || b < a) { console.error("fleecejackPad niet gevonden"); process.exit(1); }
const f = new Function(S.slice(a, b) + "\nreturn fleecejackPad;")();
if (!/fleecejackPad\(cat, item\)\)\s*\n\s*\|\| \(typeof kinderPad/.test(S)) { console.error("niet aangesloten op walkVintedCategoryPath"); process.exit(1); }
const M = ["Men", "Clothing", "Outerwear", "Jackets", "Fleece jackets"].join(">");
const W = M.replace("Men", "Women");
const g = [
  ["heren truien", "(721) Beige Ralph Lauren Fleece Jacket - Men M - Very Good", "", M],
  ["heren truien", "Ralph Lauren fleecevest beige M", "", M],
  ["heren jassen", "Beige fleecejack Ralph Lauren", "", M],
  ["dames truien", "Patagonia Fleece Jas dames", "", W],
  ["heren truien", "Ralph Lauren Full Zip Fleece", "", M],
  ["heren truien", "Ralph Lauren Beige Jacket", "Soft fleece jacket by Ralph Lauren", M],
  // Geen fleecejack:
  ["heren truien", "Ralph Lauren Half Zip Fleece - Men M", "", null],
  ["heren truien", "Profuomo Half Zip", "", null],
  ["heren jassen", "North Face fleece lined jacket", "", null],
  ["heren jassen", "North Face Fleece Bodywarmer", "", null],
  ["heren truien", "Zwarte trui", "Voelt als een fleece jacket", null],
  ["heren jeans", "Fleece jacket", "", null],
  ["unisex truien", "Fleece jacket", "", null],
];
let fout = 0;
for (const [cat, titel, desc, want] of g) {
  const got = f(cat, { title: titel, description: desc, gender: cat.split(" ")[0] });
  const ok = (got ? got.join(">") : null) === want;
  if (!ok) fout++;
  console.log(`${ok ? "ok  " : "STUK"} ${cat} | ${titel} → ${got ? got.join(">") : null}`);
}
process.exit(fout ? 1 : 0);
