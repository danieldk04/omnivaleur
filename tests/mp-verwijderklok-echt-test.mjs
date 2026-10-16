/**
 * De echte proef bij tests/mp-verwijderklok-test.js: komt een stukje code ín de
 * pagina nog af als het verwijdertabblad al een paar minuten niet in beeld is?
 *
 * Aanleiding (16-10-2026, klant 26cf5471): het eerste Marktplaats-verwijderen na
 * het wakker worden van zijn computer hing 81 minuten, en zolang vroeg de
 * extensie Marktplaats niets meer. bgDeleteMp2dh opende zijn tabblad zonder
 * klokVast; elke stap in de pagina (miniaturen tellen, overzicht openklappen,
 * bevestigvenster) wacht op de klok van die pagina.
 *
 * Twee tabbladen naast elkaar in één echte Chrome, met de echte extensie:
 *   kaal  : geopend zoals bgDeleteMp2dh vóór 16-10 ({ silent: true })
 *   vast  : geopend zoals nu ({ silent: true, klokVast: true }, _klokTabbladen,
 *           startOntdooiTeller)
 * Na MINUTEN minuten op de achtergrond draait in beide hetzelfde stukje als
 * mpAdvertentieSnapshot: tien keer een halve seconde wachten in de pagina. Hoort
 * te duren: vijf seconden.
 *
 * Draaien: node tests/mp-verwijderklok-echt-test.mjs
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = process.argv[2] || new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const MP = "https://www.marktplaats.nl/";
const MINUTEN = Number(process.env.KLOKPROEF_MINUTEN || 3);
const GRENS_MS = 120000;

const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-klok-"));
let mislukt = 0;
const check = (naam, goed, uitleg) => {
  if (goed) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
};

// Chrome geeft het Extensions-domein alleen vrij over de pijp, en alleen met
// --enable-unsafe-extension-debugging (zie tests/wakker-houden-echt-test.mjs).
const chrome = spawn(CHROME, [
  "--remote-debugging-pipe", "--enable-unsafe-extension-debugging",
  `--user-data-dir=${profiel}`, "--no-first-run", "--no-default-browser-check",
  "--window-size=1200,800", "about:blank",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const [inp, uitp] = [chrome.stdio[3], chrome.stdio[4]];
let nr = 0; const wacht = new Map(); let buf = Buffer.alloc(0);
uitp.on("data", (d) => {
  buf = Buffer.concat([buf, d]);
  let i;
  while ((i = buf.indexOf(0)) >= 0) {
    let m = null;
    try { m = JSON.parse(buf.subarray(0, i).toString()); } catch (_) { /* gebeurtenis */ }
    buf = buf.subarray(i + 1);
    if (m && m.id && wacht.has(m.id)) { wacht.get(m.id)(m); wacht.delete(m.id); }
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
  if (!extId) throw new Error("extensie niet geladen");

  let worker = null;
  for (let i = 0; i < 40 && !worker; i++) {
    const t = await stuur("Target.getTargets", { filter: [{}] });
    worker = t.result.targetInfos.find((x) => x.type === "service_worker" && x.url.includes(extId));
    if (!worker) await pauze(300);
  }
  check("de achtergrondmotor draait", !!worker);
  if (!worker) throw new Error("geen service worker");

  const s = await stuur("Target.attachToTarget", { targetId: worker.targetId, flatten: true });
  let sid = s.result.sessionId;
  const doe = async (expr) => {
    const u = await stuur("Runtime.evaluate",
      { expression: expr, awaitPromise: true, returnByValue: true }, sid);
    const r = u.result?.result;
    return r && "value" in r ? r.value : (r?.description || JSON.stringify(u.result));
  };
  // Chrome breekt de service worker tussendoor af; hecht je aan de oude, dan
  // bestaat `chrome` daar niet meer. Opnieuw zoeken tot de motor antwoordt.
  let versie = await doe("chrome.runtime.getManifest().version");
  for (let i = 0; i < 6 && String(versie).includes("not defined"); i++) {
    await pauze(1000);
    const t = await stuur("Target.getTargets", { filter: [{}] });
    const w = t.result.targetInfos.find((x) => x.type === "service_worker" && x.url.includes(extId));
    if (!w) continue;
    const ns = await stuur("Target.attachToTarget", { targetId: w.targetId, flatten: true });
    sid = ns.result.sessionId;
    versie = await doe("chrome.runtime.getManifest().version");
  }
  console.log("\nExtensieversie:", versie);

  const eigenVenster = await doe(
    `chrome.windows.create({ url: "https://example.com/" }).then(w => w.id)`);
  await pauze(1500);

  const opties = {
    kaal: "{ silent: true }",
    vast: "{ silent: true, klokVast: true }",
  };
  const tab = {};
  for (const [naam, opt] of Object.entries(opties)) {
    tab[naam] = await doe(
      `new Promise((res) => openWorkerTab(${JSON.stringify(MP)}, (t) => res(t ? t.id : "fout"), ${opt}))
         .then((id) => {
           if (${naam === "vast"} && typeof id === "number") { _klokTabbladen.add(id); startOntdooiTeller(); }
           return id;
         })`);
    check(`${naam}: werk-tabblad geopend`, typeof tab[naam] === "number", String(tab[naam]));
    const plek = await doe(`chrome.tabs.get(${tab[naam]}).then(t => JSON.stringify({ actief: t.active }))`);
    check(`${naam}: staat op de achtergrond`, JSON.parse(plek).actief === false, plek);
  }

  console.log(`\n${MINUTEN} minuten wachten met beide tabbladen op de achtergrond…`);
  await pauze(MINUTEN * 60000);

  // Precies het patroon van mpAdvertentieSnapshot, via de echte execInTab.
  const meet = (id) => doe(
    `(async () => {
       const t0 = Date.now();
       const uit = await Promise.race([
         execInTab(${id}, async () => {
           const s = (ms) => new Promise((r) => setTimeout(r, ms));
           for (let i = 0; i < 10; i++) await s(500);
           return "klaar";
         }).catch((e) => "fout: " + e.message),
         new Promise((r) => setTimeout(() => r("hangt"), ${GRENS_MS})),
       ]);
       return JSON.stringify({ uit, ms: Date.now() - t0 });
     })()`);
  const [kaal, vast] = await Promise.all([meet(tab.kaal), meet(tab.vast)]);
  console.log(`  kaal: ${kaal}`);
  console.log(`  vast: ${vast}`);
  const k = JSON.parse(kaal), v = JSON.parse(vast);
  check("vast: tien halve seconden in de pagina duren hooguit 15 seconden",
        v.uit === "klaar" && v.ms <= 15000, vast);
  console.log(`  (kaal ter vergelijking: ${k.uit} na ${(k.ms / 1000).toFixed(0)} s)`);
} catch (e) {
  mislukt++;
  console.log("  FOUT proef afgebroken —", e && e.message);
} finally {
  chrome.kill();
  await pauze(1500);
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) { /* Chrome ruimt zelf nog op */ }
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
