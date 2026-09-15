/**
 * De échte proef: loopt de klok van een Vinted-werktabblad ook als het niet in
 * beeld staat?
 *
 * Daniel, 15-09-2026: "iedere keer als ik iets op Vinted probeer te publiceren
 * gebeurt er niks in dat tabblad totdat ik er zelf naartoe klik." Chrome knijpt
 * de klok van een verborgen tabblad af tot één tik per seconde, en na vijf
 * minuten verborgen tot ongeveer één per minuut. Onze eigen pauzes lopen via een
 * Web Worker en merken dat niet, maar het formulier van Vinted zelf draait op
 * die klok en staat dan stil.
 *
 * Deze proef laadt de échte extensie in een echte Chrome, laat haar een echt
 * werk-tabblad openen op het Vinted-plaatsformulier (achtergrondtabblad, precies
 * zoals bij een echte opdracht) en leest daarna in dat tabblad uit wat de pagina
 * zelf denkt: staat ze in beeld, en hoe vaak tikt haar klok?
 *
 * Er wordt niets gepubliceerd: zonder Vinted-sessie komt het tabblad op de
 * inlogpagina uit, en dat is voor deze meting genoeg — het gaat om de klok van
 * het tabblad, niet om het formulier.
 *
 * Draaien: node tests/vinted-tabblad-klok-echt-test.mjs [pad naar extensie]
 * Voor-en-na-proef met de versie van vóór de reparatie:
 *   git archive <commit>:extension | tar -x -C /tmp/oud
 *   node tests/vinted-tabblad-klok-echt-test.mjs /tmp/oud
 * Zonder de reparatie hoort er "hidden" uit te komen en een klok die stilstaat.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = process.argv[2] || new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const FORMULIER = "https://www.vinted.nl/items/new";

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
  "--window-size=800,600", "about:blank",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const [inp, uitp] = [chrome.stdio[3], chrome.stdio[4]];
let nr = 0; const wacht = new Map(); let buf = Buffer.alloc(0);
uitp.on("data", (d) => {
  buf = Buffer.concat([buf, d]);
  let i;
  while ((i = buf.indexOf(0)) >= 0) {
    let m = null;
    try { m = JSON.parse(buf.subarray(0, i).toString()); } catch (_) { /* gebeurtenis, geen antwoord */ }
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
  // De service worker wordt door Chrome tussendoor afgebroken en opnieuw gestart;
  // hecht je aan de oude, dan bestaat `chrome` daar niet meer. Opnieuw zoeken tot
  // de motor antwoordt.
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

  // Precies wat een echte Vinted-opdracht doet: een achtergrondtabblad in het
  // venster waar de verkoper toch al werkt.
  // Een eigen venster met een actief tabblad ervoor, zodat het werk-tabblad er
  // écht achter staat — net als bij een verkoper die in zijn eigen venster werkt.
  // (Een extensie die via de pijp is geladen ziet het venster waarmee Chrome
  //  startte niet, vandaar dat we er zelf een maken.)
  // De échte weg die een opdracht ook neemt, inclusief de keuze voor een eigen
  // venster bij het Vinted-formulier. Er staat eerst een gewoon venster open,
  // zodat de keuze iets te kiezen heeft.
  const tabId = await doe(
    `chrome.windows.create({ url: "about:blank" })
       .then(() => new Promise((res) => openWorkerTab(${JSON.stringify(FORMULIER)}, (t) => res(t ? t.id : "fout: geen tabblad"))))
       .catch(e => "fout: " + (e && e.message))`);
  check("er is een werk-tabblad geopend", typeof tabId === "number", String(tabId));
  if (typeof tabId !== "number") throw new Error("geen tabblad");
  console.log("Tabblad:", tabId, "(staat op de achtergrond)");

  // In wat voor venster is hij terechtgekomen, en staat hij daar vooraan?
  console.log("Venster:", await doe(
    `chrome.tabs.get(${tabId}).then(t => chrome.windows.get(t.windowId, {populate:true})
       .then(w => \`state=\${w.state} focused=\${w.focused} tabbladen=\${w.tabs.length} actief=\${t.active}\`))`));

  // Wachten tot Vinted geladen is (zonder sessie: de inlogpagina).
  for (let i = 0; i < 40; i++) {
    const klaar = await doe(`chrome.tabs.get(${tabId}).then(t => t.status + " " + (t.active ? "actief" : "achtergrond"))`);
    if (String(klaar).startsWith("complete")) { console.log("Status:", klaar); break; }
    await pauze(500);
  }

  // Nu in het tabblad zelf kijken. Niet via de extensie vragen maar rechtstreeks
  // meten: wat denkt de pagina, en hoe vaak tikt haar klok werkelijk?
  const targets = await stuur("Target.getTargets", { filter: [{}] });
  const pagina = targets.result.targetInfos.find((t) => t.type === "page" && /vinted\./.test(t.url));
  check("het tabblad staat op Vinted", !!pagina, targets.result.targetInfos.map(t => t.url).join(" | ").slice(0, 200));
  if (!pagina) throw new Error("geen Vinted-tabblad");

  const ps = await stuur("Target.attachToTarget", { targetId: pagina.targetId, flatten: true });
  const psid = ps.result.sessionId;
  const inPagina = async (expr) => {
    const u = await stuur("Runtime.evaluate",
      { expression: expr, awaitPromise: true, returnByValue: true }, psid);
    const r = u.result?.result;
    return r && "value" in r ? r.value : (r?.description || JSON.stringify(u.result));
  };

  const zichtbaarheid = await inPagina("document.visibilityState");
  console.log("Heeft de pagina focus?", await inPagina("document.hasFocus()"));
  console.log("De pagina zelf zegt:", zichtbaarheid);
  check("de pagina denkt dat ze in beeld staat", zichtbaarheid === "visible",
        `document.visibilityState = ${zichtbaarheid}`);

  // De harde meting: een ketting van pauzes van 100 ms, tien seconden lang.
  // Ongeremd horen dat er ongeveer 100 te zijn; een verborgen tabblad haalt er
  // ongeveer 10 en een zwaar geremd tabblad nul.
  console.log("Tien seconden lang de klok van de pagina tellen…");
  const tikken = await inPagina(`new Promise((res) => {
    let n = 0; const eind = Date.now() + 10000;
    (function lus(){ setTimeout(() => { n++; Date.now() < eind ? lus() : res(n); }, 100); })();
  })`);
  console.log("Tikken in 10 seconden:", tikken);
  // Een echte Vinted-pagina doet zelf ook werk, dus de 100 van een lege pagina
  // wordt hier niet gehaald: gemeten 48 tot 91. Zonder de reparatie zijn het er
  // precies 10 (één per seconde), en na vijf minuten verborgen 0. Alles boven de
  // 25 kan dus alleen een tabblad zijn dat niet meer afgeknepen wordt.
  check("de klok van de pagina is niet afgeknepen", Number(tikken) >= 25,
        `${tikken} tikken in 10 sec; afgeknepen zijn dat er 10 of minder`);

  // FASE 2: hetzelfde tabblad, maar nu met het venster geminimaliseerd. Dat is
  // wat er bij een verkoper gebeurt zodra hij zijn browser wegklikt of er een
  // ander venster overheen legt: het tabblad is dan niet alleen onzichtbaar maar
  // het hele venster is weg. Daniel mat op 15-09-2026 in zijn eigen browser
  // 0,2 tikken per seconde terwijl de pagina "visible+focus" meldde — precies
  // het teken dat de focus-emulatie alleen het rapport verandert en niet de rem.
  console.log("\nVenster minimaliseren en opnieuw meten…");
  await doe(`chrome.tabs.get(${tabId}).then(t => chrome.windows.update(t.windowId, { state: "minimized" })).then(() => "ok")`);
  await pauze(3000);
  const zicht2 = await inPagina("document.visibilityState + (document.hasFocus() ? \"+focus\" : \"\")");
  const tikken2 = await inPagina(`new Promise((res) => {
    let n = 0; const eind = Date.now() + 10000;
    (function lus(){ setTimeout(() => { n++; Date.now() < eind ? lus() : res(n); }, 100); })();
  })`);
  console.log("Met geminimaliseerd venster:", zicht2, "|", tikken2, "tikken in 10 sec");
  check("ook met een geminimaliseerd venster loopt de klok door", Number(tikken2) >= 25,
        `${tikken2} tikken in 10 sec terwijl de pagina "${zicht2}" meldt`);
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
