/**
 * De bevestiglus van bgDeleteMp2dh draait hier letterlijk uit de bron.
 *
 * Aanleiding (21-11-2026, klant 0b28c1ce): "marktplaats delete mislukt: Error:
 * Frame with ID 0 was removed." De advertentie m2399104659 gaf daarna 404: de
 * verwijdering was gelukt, Marktplaats ververste het overzicht na de klik en
 * Chrome brak ons wachtende script af. De controle op de advertentiepagina
 * moet beslissen, de lus mag niet gooien. Een andere fout blijft wel een fout.
 *
 * Draaien:  node tests/mp-bevestigen-frame-weg-test.js
 *           node tests/mp-bevestigen-frame-weg-test.js --oud=54eb1353   (faalt)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const oudArg = process.argv.find((a) => a.startsWith("--oud="));
const BG = oudArg
  ? execSync(`git show ${oudArg.slice(6)}:extension/background.js`, { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const a = BG.indexOf("const CONFIRM_STEPS = 3;", BG.indexOf("async function bgDeleteMp2dh("));
const b = BG.indexOf("// NAKIJKEN OP DE ADVERTENTIE ZELF", a);
if (a < 0 || b < 0) throw new Error("bevestiglus niet gevonden");
const lus = BG.slice(a, b);
const draai = new Function("execInTab", "tabId", "_bevestigInVenster", "BEVESTIG_JA_BRON", "BEVESTIG_NEE_BRON",
  "platform", "title", "sleep", "waitForTabLoad",
  `return (async () => {${lus}; return "door";})();`);
let mislukt = 0;
const ok = (n, v, x) => { if (v) console.log("  ✓ " + n); else { mislukt++; console.log("  ✗ " + n + (x !== undefined ? " — " + x : "")); } };
const run = (exec) => draai(exec, 1, null, "", "", "marktplaats", "t", async () => {}, async () => {})
  .then((r) => r, (e) => "FOUT: " + e.message);
(async () => {
  let r = await run(async () => { throw new Error("Frame with ID 0 was removed."); });
  ok("Frame removed bij bevestigen -> geen fout, door naar controle", r === "door", r);
  r = await run(async () => { throw new Error("Cannot access contents of the page"); });
  ok("andere fout blijft een fout", /^FOUT/.test(r), r);
  r = await run(async () => ({ open: false }));
  ok("venster weg -> door", r === "door", r);
  process.exit(mislukt ? 1 : 0);
})();
