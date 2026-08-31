// Draait de ECHTE bladkeuze uit extension/content/vinted.js tegen de bladen die
// Vinted zelf toont. De code wordt uit het verscheepte bestand gesneden, zodat
// deze proef nooit een verouderde kopie test.
//
// AANLEIDING 31-08-2026. "(1356) Beige Suitsupply Jumper - Men M - Very Good"
// belandde onder "Other jumpers & sweaters", terwijl "Jumpers" er letterlijk in
// de titel staat. Oorzaak: het vangblad herhaalt de woorden van zijn buren, dus
// "jumper" gold niet meer als een eigen woord van "Jumpers" — en dan wint het
// vangblad via de laatste terugval.
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.resolve(__dirname, "../../extension/content/vinted.js"), "utf8");
const stuk = (van, tot) => {
  const a = SRC.indexOf(van);
  const b = SRC.indexOf(tot, a);
  if (a < 0 || b < 0) { console.error(`niet gevonden: ${van}`); process.exit(1); }
  return SRC.slice(a, b);
};

const code =
  stuk("  const BLAD_VOORKEUR = [", "  const job = await getJob();") +
  stuk("  function kiesBlad(namen, tekst) {", "  // Loopt het pad af in Vinted's kiezer.");
const { kiesBlad } = new Function(code + "\nreturn { kiesBlad };")();

// Zoals Vinted ze toont onder Men → Clothing → Jumpers & sweaters.
const TRUIEN = ["Cardigans", "Hoodies", "Jumpers", "Sweatshirts", "Turtlenecks",
                "V-necks", "Zip-throughs", "Other jumpers & sweaters"];
const OVERHEMDEN = ["Checked shirts", "Denim shirts", "Flannel shirts", "Linen shirts",
                    "Oxford shirts", "Striped shirts", "Other shirts"];
const BROEKEN = ["Cargo trousers", "Chinos", "Jeans", "Shorts", "Sweatpants",
                 "Other trousers"];

const gevallen = [
  [TRUIEN, "(1356) beige suitsupply jumper - men m - very good", "Jumpers"],
  [TRUIEN, "grey suitsupply cardigan men m", "Cardigans"],
  [TRUIEN, "nike hoodie zwart", "Hoodies"],
  // Waar een half-zip hoort is door Daniel bepaald op 31-08-2026: Zip-throughs.
  [TRUIEN, "profuomo half zip trui", "Zip-throughs"],
  [TRUIEN, "(1275) Grey Profuomo Half Zip - Men XS - Very Good", "Zip-throughs"],
  [TRUIEN, "denham quarter zip navy", "Zip-throughs"],
  [TRUIEN, "coltrui van wol", "Turtlenecks"],
  // Zegt de titel niets over het model, dan is het vangblad wél het goede
  // antwoord — die terugval moet blijven werken.
  [TRUIEN, "suitsupply bovenstuk maat m", "Other jumpers & sweaters"],
  [OVERHEMDEN, "geruit overhemd van suitsupply", "Checked shirts"],
  [OVERHEMDEN, "linnen overhemd wit", "Linen shirts"],
  [BROEKEN, "levis jeans w36", "Jeans"],
  [BROEKEN, "suitsupply chino beige", "Chinos"],
];

let fout = 0;
for (const [namen, tekst, verwacht] of gevallen) {
  const i = kiesBlad(namen, tekst);
  const gekozen = i == null ? "(niets)" : namen[i];
  const ok = gekozen === verwacht;
  if (!ok) fout++;
  console.log(`${ok ? "ok  " : "STUK"}  "${tekst}" → ${gekozen}${ok ? "" : ` (verwacht ${verwacht})`}`);
}
console.log(fout ? `\n${fout} FOUT` : "\nalle gevallen goed");
process.exit(fout ? 1 : 0);
