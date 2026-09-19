/**
 * MOGEN DRIE KANALEN NAAST ELKAAR PUBLICEREN?
 *
 * Publiceren gebeurt in één geminimaliseerd werkvenster; het werk-tabblad is
 * daar het actieve tabblad. Willen kanalen naast elkaar draaien, dan staan er
 * straks meerdere werk-tabbladen in dat venster en is er hooguit één actief.
 * De vraag die dat oproept is niet "gaat het sneller" maar "blijft een tabblad
 * dat NIET actief is in een ingeklapt venster wel op tempo werken" — want een
 * tabblad dat Chrome afknijpt vult geen formulier in, en dan levert parallel
 * publiceren juist mislukkingen op.
 *
 * Alle varianten draaien tegelijk in één Chrome, zodat ze dezelfde machine en
 * hetzelfde moment delen. Meet minstens acht minuten en beoordeel alleen het
 * laatste stuk: Chrome knijpt in stappen af en is de eerste dertig seconden nog
 * bijna vriendelijk (zie docs/kennisbank.md, "Korte klokmeting bewijst niets").
 *
 * Gebruik:  node tests/parallel-tabbladen-echt-test.mjs [minuten]
 */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const MINUTEN = Number(process.argv[2] || 10);

// De proefpagina doet na wat het invulscript doet: een lus van pauzes via een
// Web Worker (zo pauzeert shared.js sinds 1.0.309), plus een gewone klok.
const PAGINA = `<!doctype html><meta charset=utf-8><title>parallelproef</title><body>proef
<script>
let tikken = 0;
(function lus(){ setTimeout(() => { tikken++; lus(); }, 100); })();
let drift = 0;
const blob = URL.createObjectURL(new Blob([
  "let v=Date.now();setInterval(()=>{const n=Date.now();postMessage(n-v-1000);v=n;},1000);"
], {type:"text/javascript"}));
const w = new Worker(blob);
w.onmessage = (e) => { if (e.data > drift) drift = e.data; };

// EEN NABOOTSING VAN HET ECHTE INVULLEN: stap, pauze van 300 ms, stap...
// Dit telt wat er van het formulier écht af zou komen in deze tijd.
const pauzeBlob = URL.createObjectURL(new Blob([
  "onmessage=(e)=>{setTimeout(()=>postMessage(e.data), e.data);}"
], {type:"text/javascript"}));
const pw = new Worker(pauzeBlob);
const wachters = [];
pw.onmessage = () => { const f = wachters.shift(); if (f) f(); };
const slaap = (ms) => new Promise((res) => { wachters.push(res); pw.postMessage(ms); });
let stappen = 0;
// Elke "stap" doet wat het invulscript doet: even wachten, dan echt werk in de
// pagina (een stuk DOM bouwen en opmaken) en af en toe iets ophalen. Zonder dat
// werk zou deze proef alleen meten of de klok tikt, niet of drie tabbladen
// elkaar in de weg zitten.
(async function formulier(){
  for(;;){
    await slaap(300);
    const d = document.createElement("div");
    d.textContent = "stap " + stappen;
    for (let i = 0; i < 300; i++) {
      const s2 = document.createElement("span");
      s2.textContent = String(i);
      s2.style.color = i % 2 ? "#333" : "#666";
      d.appendChild(s2);
    }
    document.body.replaceChildren(d);
    void d.getBoundingClientRect().height;
    if (stappen % 10 === 0) { try { await fetch("bezig?n=" + stappen); } catch (_) {} }
    stappen++;
  }
})();

window.__meet = () => {
  const r = { tikken, drift, stappen, vis: document.visibilityState,
              focus: (()=>{try{return document.hasFocus()}catch(_){return null}})() };
  tikken = 0; drift = 0; stappen = 0; return r;
};
<\/script>`;

const server = createServer((_req, res) => {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(PAGINA);
}).listen(0, "127.0.0.1");
await new Promise((r) => server.on("listening", r));
const BASIS = `http://127.0.0.1:${server.address().port}/`;

const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-parallelproef-"));
const chrome = spawn(CHROME, [
  "--remote-debugging-pipe", `--user-data-dir=${profiel}`,
  "--no-first-run", "--no-default-browser-check", "--window-size=1200,800",
  "about:blank",
], { stdio: ["ignore", "ignore", "inherit", "pipe", "pipe"] });
const [inp, uitp] = [chrome.stdio[3], chrome.stdio[4]];
let nr = 0; const wacht = new Map(); let buf = Buffer.alloc(0);
uitp.on("data", (d) => {
  buf = Buffer.concat([buf, d]);
  let i;
  while ((i = buf.indexOf(0)) >= 0) {
    let m = null;
    try { m = JSON.parse(buf.subarray(0, i).toString()); } catch (_) {}
    buf = buf.subarray(i + 1);
    if (m && m.id && wacht.has(m.id)) { wacht.get(m.id)(m); wacht.delete(m.id); }
  }
});
const stuur = (method, params = {}, sessionId) => new Promise((res) => {
  const n = ++nr; wacht.set(n, res);
  inp.write(JSON.stringify({ id: n, method, params, sessionId }) + "\0");
});
const pauze = (ms) => new Promise((r) => setTimeout(r, ms));

// groep "nu"     = zoals het vandaag draait: één werk-tabblad, actief, in het
//                  ingeklapte werkvenster (naast het ankertabblad).
// groep "samen"  = drie werk-tabbladen in datzelfde ene ingeklapte venster.
//                  Eén ervan is actief, de andere twee niet. Dit is wat
//                  parallel publiceren met het huidige werkvenster oplevert.
// groep "apart"  = drie ingeklapte vensters, elk met één actief werk-tabblad.
//                  Het alternatief als "samen" niet op tempo blijft.
// Zoals de extensie het sinds 18-09-2026 doet: werk-tabbladen zijn ACHTERGROND-
// tabbladen in het venster waar de verkoper toch al zit (openAchtergrondTabblad),
// met Emulation.setFocusEmulationEnabled eraan. Het aparte geminimaliseerde
// venster is alleen nog een terugval, en het venster doet er niet toe — alleen
// de focus-emulatie doet er iets toe (tests/klok-varianten-echt-test.mjs).
const VARIANTEN = [
  { naam: "kanaal 1 (draait de hele proef)", fase: 1 },
  { naam: "kanaal 2 (komt er halverwege bij)", fase: 2 },
  { naam: "kanaal 3 (komt er halverwege bij)", fase: 2 },
  { naam: "controle: zonder focus-emulatie", fase: 1, geenFocus: true },
];

try {
  await pauze(2500);
  // Het startvenster is het venster van de verkoper: dat blijft vooraan staan en
  // alle werk-tabbladen komen daar als achtergrondtabblad bij.
  const eerste = await stuur("Target.getTargets", { filter: [{}] });
  const startPagina = eerste.result.targetInfos.find((t) => t.type === "page");
  const venster = startPagina
    ? (await stuur("Browser.getWindowForTarget", { targetId: startPagina.targetId })).result?.windowId
    : null;

  const aanzetten = async (v) => {
    const t = await stuur("Target.createTarget",
      { url: BASIS, windowId: venster, background: true });   // achtergrondtabblad
    v.targetId = t.result.targetId;
    const sess = await stuur("Target.attachToTarget", { targetId: v.targetId, flatten: true });
    v.sid = sess.result.sessionId;
    if (!v.geenFocus) {
      const r = await stuur("Emulation.setFocusEmulationEnabled", { enabled: true }, v.sid);
      v.focusFout = r.error ? JSON.stringify(r.error) : null;
      await stuur("Page.setWebLifecycleState", { state: "active" }, v.sid);
    }
    v.gestart = Date.now();
  };

  for (const v of VARIANTEN.filter((x) => x.fase === 1)) await aanzetten(v);
  if (startPagina) await stuur("Target.activateTarget", { targetId: startPagina.targetId });

  // De ontdooier van de extensie: elke tien seconden, voor elk werk-tabblad.
  const tik = setInterval(() => {
    for (const v of VARIANTEN) {
      if (v.sid && !v.geenFocus) stuur("Page.setWebLifecycleState", { state: "active" }, v.sid);
    }
  }, 10000);

  const meet = async () => {
    const uit = [];
    for (const v of VARIANTEN) {
      if (!v.sid) { uit.push(null); continue; }
      const u = await stuur("Runtime.evaluate",
        { expression: "JSON.stringify(window.__meet ? window.__meet() : null)", returnByValue: true }, v.sid);
      let val = null;
      try { val = JSON.parse(u.result?.result?.value ?? "null"); } catch (_) {}
      uit.push(val);
    }
    return uit;
  };

  const helft = Math.max(2, Math.round(MINUTEN / 2));
  console.log(`Fase 1: alleen kanaal 1 (en de controle), ${helft} minuten.`);
  console.log(`Fase 2: kanaal 2 en 3 komen erbij, ${MINUTEN - helft} minuten.\n`);
  console.log("tijd  " + VARIANTEN.map((_v, i) => String(i).padStart(7)).join(""));

  const fase1 = VARIANTEN.map(() => []);
  const fase2 = VARIANTEN.map(() => []);
  await meet();                                   // tellers op nul na het laden
  const start = Date.now();
  for (let ronde = 0; ronde * 30 < MINUTEN * 60; ronde++) {
    await pauze(30000);
    const verstreken = (Date.now() - start) / 60000;
    if (verstreken >= helft && !VARIANTEN[1].sid) {
      for (const v of VARIANTEN.filter((x) => x.fase === 2)) await aanzetten(v);
      if (startPagina) await stuur("Target.activateTarget", { targetId: startPagina.targetId });
      console.log("      ---- kanaal 2 en 3 erbij ----");
      await pauze(1500);
      await meet();
      continue;
    }
    const u = await meet();
    console.log(`${verstreken.toFixed(1).padStart(4)}m ` +
      u.map((x) => (x ? String(x.stappen).padStart(7) : "      -")).join(""));
    u.forEach((x, i) => { if (x) (verstreken < helft ? fase1 : fase2)[i].push(x); });
  }
  clearInterval(tik);

  const gem = (a) => (a.length ? a.reduce((s2, x) => s2 + x, 0) / a.length : 0);
  console.log("\n================ UITSLAG ================");
  console.log("stappen per 30 seconden; vol tempo is ongeveer 100 (pauze van 300 ms per stap)\n");
  VARIANTEN.forEach((v, i) => {
    const a = gem(fase1[i].map((x) => x.stappen));
    const b = gem(fase2[i].map((x) => x.stappen));
    const klok = gem(fase2[i].concat(fase1[i]).map((x) => x.tikken)) / 30;
    const drift = Math.max(0, ...fase1[i].concat(fase2[i]).map((x) => x.drift));
    console.log(
      `${i}. ${v.naam}\n` +
      `   alleen: ${a.toFixed(0)} stappen/30s  |  met drie tegelijk: ${b.toFixed(0)}  |  ` +
      `klok ${klok.toFixed(1)}/s van 10  |  langste stilstand ${drift} ms  |  ` +
      `pagina: ${(fase2[i].at(-1) || fase1[i].at(-1) || {}).vis}` +
      (v.focusFout ? ` | focus mislukt: ${v.focusFout}` : "")
    );
  });
  const eenKanaal = gem(fase1[0].map((x) => x.stappen));
  const drieKanalen = gem(fase2[0].map((x) => x.stappen));
  console.log(`\nHINDER: kanaal 1 deed ${eenKanaal.toFixed(0)} stappen per 30s alleen en ` +
    `${drieKanalen.toFixed(0)} met twee kanalen ernaast ` +
    `(${eenKanaal ? Math.round((1 - drieKanalen / eenKanaal) * 100) : "?"}% verschil).`);
} catch (e) {
  console.log("FOUT:", e && e.stack);
} finally {
  chrome.kill();
  await pauze(1200);
  server.close();
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) {}
}
process.exit(0);
