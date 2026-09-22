/**
 * Vraagt Chrome zelf of een toestemming in het manifest een NIEUWE
 * waarschuwing oplevert. Dat is de enige meting die telt.
 *
 * WAAROM (30-08-2026, Egbert Brouwer). Een update die een toestemming met een
 * eigen waarschuwing toevoegt, zet Chrome bij ELKE bestaande klant de extensie
 * uit tot hij hem goedkeurt: stil, zonder foutmelding. tests/
 * test_extensie_permissies.py bewaakt dat, maar die test kan alleen een lijstje
 * met namen vergelijken. Of een naam écht een nieuwe goedkeuringsvraag oplevert
 * weet alleen Chrome, via chrome.management.getPermissionWarningsByManifest.
 * Zo is "background" op 03-09-2026 afgedekt (zie docs/team-notes.md).
 *
 * Deze proef doet dat na met het ECHTE manifest: eerst de waarschuwingenlijst
 * van het manifest zoals het nu is, dan die van hetzelfde manifest zonder de
 * toestemming die je wilt toetsen. Zijn beide lijsten gelijk, dan krijgt geen
 * enkele bestaande klant een nieuwe vraag en valt niemand stil.
 *
 * Draaien: node tests/permissie-waarschuwing-echt-test.mjs [permissie ...]
 * Zonder argumenten toetst hij "power" en "background".
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const TOETSEN = process.argv.slice(2).length ? process.argv.slice(2) : ["power", "background"];
if (process.platform !== "darwin") {
  console.log("Deze proef start een echte Chrome; op dit systeem niet te draaien.");
  process.exit(0);
}
const MANIFEST = JSON.parse(readFileSync(join(EXT, "manifest.json"), "utf8"));
const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-permissie-"));
let mislukt = 0;
const check = (naam, goed, uitleg) => {
  if (goed) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
};

const chrome = spawn(CHROME, [
  "--remote-debugging-pipe", "--enable-unsafe-extension-debugging",
  `--user-data-dir=${profiel}`, "--no-first-run", "--no-default-browser-check",
  "--window-size=700,500", "about:blank",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const [inp, uitp] = [chrome.stdio[3], chrome.stdio[4]];
let nr = 0; const wacht = new Map(); let buf = Buffer.alloc(0);
uitp.on("data", (d) => {
  buf = Buffer.concat([buf, d]);
  let i;
  while ((i = buf.indexOf(0)) >= 0) {
    const m = JSON.parse(buf.subarray(0, i).toString());
    buf = buf.subarray(i + 1);
    if (m.id && wacht.has(m.id)) { wacht.get(m.id)(m); wacht.delete(m.id); }
  }
});
const stuur = (method, params = {}, sessionId) => new Promise((res) => {
  const n = ++nr; wacht.set(n, res);
  inp.write(JSON.stringify({ id: n, method, params, sessionId }) + "\0");
});
const pauze = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  await pauze(2500);
  const geladen = await stuur("Extensions.loadUnpacked", { path: EXT });
  const extId = geladen.result?.id;
  check("de extensie laadt in een echte Chrome", !!extId, JSON.stringify(geladen.error || ""));
  if (!extId) throw new Error("niet geladen");

  let worker = null;
  for (let i = 0; i < 40 && !worker; i++) {
    const t = await stuur("Target.getTargets", { filter: [{}] });
    worker = t.result.targetInfos.find((x) => x.type === "service_worker" && x.url.includes(extId));
    if (!worker) await pauze(300);
  }
  check("de achtergrondmotor draait", !!worker);
  if (!worker) throw new Error("geen service worker");

  const s = await stuur("Target.attachToTarget", { targetId: worker.targetId, flatten: true });
  const sid = s.result.sessionId;
  const doe = async (expr) => {
    const u = await stuur("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }, sid);
    const r = u.result?.result;
    return r && "value" in r ? r.value : (r?.description || JSON.stringify(u.result));
  };
  const waarschuwingen = async (manifest) => doe(
    `chrome.management.getPermissionWarningsByManifest(${JSON.stringify(JSON.stringify(manifest))})`);

  console.log("\nExtensieversie:", MANIFEST.version, "\n");
  const nu = await waarschuwingen(MANIFEST);
  check("Chrome geeft een waarschuwingenlijst terug", Array.isArray(nu), String(nu));
  if (!Array.isArray(nu)) throw new Error("geen lijst");
  console.log(`Het manifest zoals het nu is (${nu.length} waarschuwing(en)):`);
  nu.forEach((w) => console.log("       - " + w));

  for (const perm of TOETSEN) {
    console.log(`\nZelfde manifest, maar zonder "${perm}":`);
    if (!(MANIFEST.permissions || []).includes(perm)) {
      console.log(`       (staat niet in het manifest, overgeslagen)`);
      continue;
    }
    const zonder = { ...MANIFEST, permissions: MANIFEST.permissions.filter((p) => p !== perm) };
    const oud = await waarschuwingen(zonder);
    if (!Array.isArray(oud)) { check(`"${perm}" te meten`, false, String(oud)); continue; }
    oud.forEach((w) => console.log("       - " + w));
    const erbij = nu.filter((w) => !oud.includes(w));
    check(`"${perm}" levert geen nieuwe goedkeuringsvraag op`, erbij.length === 0,
          `nieuw: ${JSON.stringify(erbij)} — bestaande klanten liggen stil tot ze klikken`);
  }
} finally {
  chrome.kill();
  await pauze(1500);
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) { /* Chrome ruimt zelf nog op */ }
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
