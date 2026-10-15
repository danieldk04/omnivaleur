/**
 * De échte proef: gaat de uurlijkse updatecontrole ook af als Chrome de
 * achtergrondmotor tussendoor stillegt en weer opstart?
 *
 * Janneke (15-10-2026) draaide drie dagen 1.0.384 terwijl de Web Store 1.0.388
 * aan haar Chrome 128 aanbood. Haar Chrome herstart nooit (macOS 10.15 krijgt
 * geen Chrome-updates meer), dus alleen onze eigen controle kon haar bijwerken.
 * Die wekker werd bovenin background.js bij elke start opnieuw gezet, en
 * chrome.alarms.create met een bestaande naam vervangt hem: de eerste keer
 * afgaan schuift dan weer een uur op. Start de motor vaker dan eens per uur, dan
 * gaat de controle nooit af.
 *
 * Deze proef laadt de echte extensie in een echte Chrome, leest het tijdstip van
 * de wekker, legt de service worker stil, wacht tot Chrome hem zelf weer wekt en
 * leest het tijdstip opnieuw. Het mag niet verschoven zijn.
 *
 * Draaien (alleen macOS): node tests/update-wekker-echt-test.mjs [pad naar extensie]
 * Voor de voor-en-na-proef: git archive <commit>:extension | tar -x -C /tmp/oud
 * en geef /tmp/oud als pad mee.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = process.argv[2] || new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
if (process.platform !== "darwin") {
  console.log("Deze proef start de Chrome van macOS; op dit systeem niet te draaien.");
  process.exit(0);
}
const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-proef-"));
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

async function vindWorker(extId) {
  for (let i = 0; i < 150; i++) {
    const t = await stuur("Target.getTargets", { filter: [{}] });
    const w = t.result.targetInfos.find((x) => x.type === "service_worker" && x.url.includes(extId));
    if (w) return w;
    await pauze(400);
  }
  return null;
}
// Een opnieuw opgestarte worker kan hetzelfde targetId krijgen; het merkteken
// op self overleeft een herstart niet, dus daaraan zie je dat het een verse is.
async function vindVerseWorker(extId) {
  for (let i = 0; i < 40; i++) {
    const w = await vindWorker(extId);
    if (w) {
      const doe = await koppel(w);
      if (await doe("typeof chrome === 'object' && self.__proefMerk !== 1")) return doe;
    }
    await pauze(2000);
  }
  return null;
}
async function koppel(worker) {
  const s = await stuur("Target.attachToTarget", { targetId: worker.targetId, flatten: true });
  const sid = s.result.sessionId;
  return async (expr) => {
    const u = await stuur("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }, sid);
    const r = u.result?.result;
    return r && "value" in r ? r.value : (r?.description || JSON.stringify(u.result));
  };
}
const wekkerTijd = `chrome.alarms.get("update-check").then((a) => a ? a.scheduledTime : null)`;

try {
  await pauze(2500);
  const geladen = await stuur("Extensions.loadUnpacked", { path: EXT });
  const extId = geladen.result?.id;
  check("de extensie laadt in een echte Chrome", !!extId, JSON.stringify(geladen.error || ""));

  const eerste = await vindWorker(extId);
  check("de achtergrondmotor draait", !!eerste);
  if (!eerste) throw new Error("geen service worker");
  let doe = await koppel(eerste);
  for (let i = 0; i < 20 && (await doe("typeof chrome")) !== "object"; i++) await pauze(300);
  await doe("self.__proefMerk = 1");
  console.log("\nExtensieversie:", await doe("chrome.runtime.getManifest().version"));
  await pauze(1500);   // laat de opstartcode uitlopen
  const voor = await doe(wekkerTijd);
  console.log("       updatecontrole gaat af om", voor && new Date(voor).toISOString());
  check("er staat een uurlijkse updatecontrole", typeof voor === "number");

  // Een update die wacht op het einde van een klus: het wachten moet de
  // herstart overleven, anders begint de grens van twee uur telkens opnieuw.
  const wachtSinds = Date.now() - 90 * 60 * 1000;
  console.log("       wachten vastleggen:", await doe(`typeof legUpdateWachtenVast === "function"
    ? (_updateWachtSinds = ${wachtSinds}, legUpdateWachtenVast().then(() => "ja")) : "bestaat niet"`));

  // Even wachten, zodat een nieuw gezette wekker aantoonbaar later uitkomt.
  await pauze(8000);
  console.log("\nChrome legt de achtergrondmotor stil en wekt hem weer:");
  await stuur("Target.closeTarget", { targetId: eerste.targetId });
  doe = await vindVerseWorker(extId);
  check("de achtergrondmotor is opnieuw opgestart", !!doe);
  if (!doe) throw new Error("geen nieuwe service worker");
  await pauze(1500);
  const na = await doe(wekkerTijd);
  console.log("       updatecontrole gaat af om", na && new Date(na).toISOString());
  check("de updatecontrole is niet vooruitgeschoven", na === voor,
    `${Math.round((na - voor) / 1000)} s later dan voor de herstart`);
  const nogSteeds = await doe(`typeof updateWachtSinds === "function" ? updateWachtSinds() : null`);
  check("een wachtende update is na de herstart niet vergeten", nogSteeds === wachtSinds,
    `na de herstart: ${nogSteeds}`);
  // Herstartten we al voor een update en draait nog dezelfde versie, dan stond
  // er niets klaar: niet elk uur blijven herstarten, maar opnieuw vragen.
  const leeg = await doe(`typeof updateWachtSinds === "function" ? (async () => {
      _updateWachtSinds = 0; await legUpdateWachtenVast({ herstart: true });
      _updateWachtSinds = 0; const w = await updateWachtSinds();
      const o = await chrome.storage.local.get(UPDATE_WACHT_SLEUTEL);
      return w === 0 && !o[UPDATE_WACHT_SLEUTEL]; })() : false`);
  check("na een herstart zonder nieuwe versie blijft hij niet herstarten", leeg === true);
} finally {
  chrome.kill();
  await pauze(1500);
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) { /* Chrome ruimt zelf nog op */ }
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
