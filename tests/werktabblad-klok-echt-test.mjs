/**
 * De échte proef: loopt de klok van een WERK-TABBLAD ook als de verkoper er niet
 * bij zit, minutenlang, op Marktplaats én op Vinted?
 *
 * Daniel, 18-09-2026: "los nu echt met 1000% zekerheid op dat ik niet op het
 * tabblad hoef te zitten om te publiceren, dit loopt telkens fout bij
 * marktplaats en 2dehands", en even later: "vinted opent nog steeds in een ander
 * venster in plaats van een ander tabblad, maar zelfde verhaal".
 *
 * WAAROM DEZE PROEF VIJF MINUTEN DUURT EN NIET TIEN SECONDEN.
 *
 * De vorige versie van dit bestand mat tien seconden en gaf groen licht. Dat was
 * te kort: Chrome knijpt een tabblad dat niet in beeld staat pas na ruim een
 * minuut echt af. Gemeten met tests/klok-varianten-echt-test.mjs, negen minuten
 * lang, op deze machine:
 *
 *   achtergrondtabblad, kaal                : 1,5/s na 30 sec → 0,0/s na 90 sec
 *   achtergrondtabblad + alleen de debugger : 1,5/s → 0,0/s
 *   eigen venster, ingeklapt, actief tabblad: 2,4/s → 0,0/s
 *   achtergrondtabblad + focus-emulatie     : 9,7/s, negen minuten lang
 *
 * Een proef die na tien seconden stopt ziet daar niets van. Vandaar dat hier
 * vijf minuten wordt gemeten en dat de laatste drie minuten tellen, niet de
 * eerste dertig seconden.
 *
 * Draaien: node tests/werktabblad-klok-echt-test.mjs [pad naar extensie]
 * Voor-en-na-proef met de versie van vóór de reparatie:
 *   git archive <commit>:extension | tar -x -C /tmp/oud
 *   node tests/werktabblad-klok-echt-test.mjs /tmp/oud
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = process.argv[2] || new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const MP = "https://www.marktplaats.nl/plaats/1776/642?bucketId=171&title=";
const VINTED = "https://www.vinted.nl/items/new";
const MINUTEN = Number(process.env.KLOKPROEF_MINUTEN || 5);

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

  // Een gewoon venster van de verkoper, met een tabblad dat vooraan staat. Alle
  // werk-tabbladen horen daar als ACHTERGRONDTABBLAD bij te komen.
  // (Een extensie die via de pijp is geladen ziet het startvenster niet, vandaar
  //  dat we er zelf een maken.)
  const eigenVenster = await doe(
    `chrome.windows.create({ url: "https://example.com/" }).then(w => w.id)`);
  await pauze(1500);

  const kanalen = [
    { naam: "Marktplaats", url: MP },
    { naam: "Vinted", url: VINTED },
  ];
  for (const k of kanalen) {
    // Precies wat processJob doet voor een schrijvende klus: klokVast mee, en
    // daarna de jobtab-sleutel zetten zodat de klok ook na een navigatie of een
    // herstart van de service worker hersteld wordt.
    k.tabId = await doe(
      `new Promise((res) => openWorkerTab(${JSON.stringify(k.url)},
         (t) => res(t ? t.id : "fout: geen tabblad"), { klokVast: true }))
         .then(id => typeof id === "number"
           ? chrome.storage.local.set({ ["jobtab_" + id]:
               { jobId: "proef", platform: "proef", action: "create",
                 serverUrl: "https://omnivaleur.com", startedAt: Date.now(), klokVast: true } })
               .then(() => { startOntdooiTeller(); return verzekerKlok(id); }).then(() => id)
           : id)
         .catch(e => "fout: " + (e && e.message))`);
    check(`${k.naam}: er is een werk-tabblad geopend`, typeof k.tabId === "number", String(k.tabId));
    if (typeof k.tabId !== "number") throw new Error("geen tabblad");

    const plek = await doe(
      `chrome.tabs.get(${k.tabId}).then(t => chrome.windows.get(t.windowId)
         .then(w => JSON.stringify({ zelfdeVenster: w.id === ${eigenVenster}, actief: t.active, staat: w.state })))`);
    const p = JSON.parse(plek);
    console.log(`${k.naam}: ${plek}`);
    check(`${k.naam}: een achtergrondtabblad in het venster van de verkoper, geen eigen venster`,
          p.zelfdeVenster && p.actief === false, plek);
    await pauze(500);
  }

  // Wachten tot de pagina's geladen zijn (zonder sessie: de inlogpagina).
  await pauze(9000);

  const sessies = {};
  for (const k of kanalen) {
    const targets = await stuur("Target.getTargets", { filter: [{}] });
    // Het tabblad kan doorgestuurd zijn (Vinted stuurt een uitgelogde bezoeker
    // naar registreren); zoek daarom op tab-id via Browser, niet op url.
    const url = await doe(`chrome.tabs.get(${k.tabId}).then(t => t.url)`);
    const pagina = targets.result.targetInfos.find((t) => t.type === "page" && t.url === url);
    check(`${k.naam}: het tabblad is te bereiken (${String(url).slice(0, 60)})`, !!pagina);
    if (!pagina) continue;
    const ps = await stuur("Target.attachToTarget", { targetId: pagina.targetId, flatten: true });
    sessies[k.naam] = ps.result.sessionId;
    // De teller wordt pas NA het laden in de pagina gezet: hij moet meten wat de
    // echte pagina doet, niet wat een leeg tabblad deed.
    await stuur("Runtime.evaluate",
      { expression: `window.__t=0;(function l(){setTimeout(()=>{window.__t++;l();},100);})();`,
        returnByValue: true }, ps.result.sessionId);
    const staat = await stuur("Runtime.evaluate",
      { expression: "document.visibilityState + (document.hasFocus() ? '+focus' : '')", returnByValue: true },
      ps.result.sessionId);
    console.log(`${k.naam}: de pagina zegt "${staat.result?.result?.value}"`);
    check(`${k.naam}: de pagina denkt dat ze in beeld staat`,
          String(staat.result?.result?.value).startsWith("visible"),
          String(staat.result?.result?.value));
  }

  console.log(`\nDe klok tellen, ${MINUTEN} minuten lang, elke 30 seconden…`);
  const gesch = {};
  for (const k of kanalen) gesch[k.naam] = [];
  for (let ronde = 0; ronde * 30 < MINUTEN * 60; ronde++) {
    await pauze(30000);
    const regel = [];
    for (const k of kanalen) {
      const sess = sessies[k.naam];
      if (!sess) { regel.push(`${k.naam}: ?`); continue; }
      const u = await stuur("Runtime.evaluate",
        { expression: "(()=>{const n=window.__t;window.__t=0;return n===undefined?null:n})()", returnByValue: true }, sess);
      const n = u.result?.result?.value;
      if (typeof n === "number") { gesch[k.naam].push(n / 30); regel.push(`${k.naam}: ${(n / 30).toFixed(1)}/s`); }
      else regel.push(`${k.naam}: ?`);
    }
    console.log(`  ${String((ronde + 1) * 0.5).padStart(4)}m  ${regel.join("   ")}`);
  }

  console.log("");
  for (const k of kanalen) {
    const g = gesch[k.naam];
    // Alleen de LAATSTE drie minuten tellen. De eerste minuut zegt niets: daarin
    // knijpt Chrome nog niet af, en precies daardoor gaf de vorige proef ten
    // onrechte groen licht.
    const laat = g.slice(-6);
    const gem = laat.length ? laat.reduce((a, b) => a + b, 0) / laat.length : 0;
    // Een echte site doet zelf ook werk, dus de tien van een lege pagina wordt
    // niet gehaald. Afgeknepen is 1 per seconde, en na een minuut of twee nul.
    // Alles boven de 5 kan alleen een tabblad zijn dat niet meer afgeknepen wordt.
    check(`${k.naam}: de klok loopt ook na ${MINUTEN} minuten nog op tempo`,
          gem >= 5, `${gem.toFixed(1)} tikken/s over de laatste ${laat.length * 0.5} minuten ` +
                    `(afgeknepen is 1,0 of minder); verloop: ${g.map(x => x.toFixed(1)).join(" ")}`);
  }
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
