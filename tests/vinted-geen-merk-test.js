/**
 * De Juiste Toon, 16-10-2026: "word als merk IKEA ingevuld terwijl dat niet in
 * de advertentie staat". Gemeten op vinted.nl met de echte 1.0.391: Vinted vult
 * na de foto's zelf IKEA in, en de merkstap deed niets bij een artikel zonder
 * merk. Nu kiest de extensie Vinteds eigen "Geen merk", behalve als Vinteds gok
 * letterlijk in titel of tekst staat. Deze proef draait de echte regel uit
 * vinted.js, oud tegen nieuw.
 *
 * Draaien: node tests/vinted-geen-merk-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const NIEUW = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
const OUD = execFileSync("git", ["show", "c828254d:extension/content/vinted.js"], { cwd: WORTEL }).toString();
const HARNAS = fs.readFileSync(path.join(WORTEL, "tests", "vinted-elke-taal-test.js"), "utf8");
const harnas = HARNAS.slice(HARNAS.indexOf("const boomUit"), HARNAS.indexOf("(async () => {"))
  .replace(/^let mislukt = 0;[\s\S]*?^}\n/m, "");
const H = new Function("fs", "path", "vm", "WORTEL", harnas + "\nreturn { blokUit };")(fs, path, vm, WORTEL);

let mislukt = 0;
const check = (naam, ok) => { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}`); if (!ok) mislukt++; };

const s = {};
vm.createContext(s);
vm.runInContext([H.blokUit(NIEUW, "function isGeenMerk("), H.blokUit(NIEUW, "function merkStaatInTekst(")].join("\n")
  + "\nglobalThis.r = { isGeenMerk, merkStaatInTekst };", s);
const { isGeenMerk, merkStaatInTekst } = s.r;

const wandkleed = { title: "Adam en Eva Ingegerd Lagerloef wandkleed 212/134",
  description: "Kenmerkende zweedse volkskunststijl. #DeJuisteToon" };
check("Vinteds gok IKEA bij het wandkleed wordt vervangen", !merkStaatInTekst("IKEA", wandkleed));
check("IKEA in de titel blijft staan", merkStaatInTekst("IKEA", { title: "IKEA kussenhoes Gurli", description: "" }));
check("geen halve woorden (ikea in 'Mikea')", !merkStaatInTekst("IKEA", { title: "Mikea plaid", description: "" }));
check("merk met leesteken (H&M)", merkStaatInTekst("H&M", { title: "Trui van H&M", description: "" }));
check("'Geen merk' wordt herkend", isGeenMerk(" Geen merk ") && isGeenMerk("No brand") && !isGeenMerk("IKEA"));
check("merkstap kiest bij een leeg merk Geen merk",
  NIEUW.includes('item.brand ? fillAttributeVinted(["brand"], item.brand) : geenMerkVinted(item)'));
check("oude versie deed niets bij een leeg merk",
  OUD.includes('item.brand && fillAttributeVinted(["brand"], item.brand)') && !OUD.includes("geenMerkVinted"));
// De valkuil van 16-10: een const onder `await getJob()` bestaat nog niet tijdens het invullen.
const naJob = NIEUW.slice(NIEUW.indexOf("const job = await getJob();"));
check("geen const voor het merk na await getJob", !/const GEEN_MERK/.test(NIEUW) && !/^\s*const\s+(isGeenMerk|merkStaatInTekst)\b/m.test(naJob));

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles ok");
process.exit(mislukt ? 1 : 0);
