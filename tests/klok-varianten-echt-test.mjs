/**
 * Welke behandeling laat de klok van een ACHTERGRONDTABBLAD echt doorlopen?
 * Alle varianten tegelijk in één Chrome, zodat ze dezelfde machine en hetzelfde
 * moment delen. Elke variant krijgt een eigen tabblad; er staat één ander
 * tabblad vooraan, precies zoals bij een verkoper die gewoon doorwerkt.
 */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const MINUTEN = Number(process.argv[2] || 8);

const PAGINA = `<!doctype html><meta charset=utf-8><title>klokproef</title><body>proef
<script>
let tikken = 0;
(function lus(){ setTimeout(() => { tikken++; lus(); }, 100); })();
let drift = 0, stilste = 0;
const blob = URL.createObjectURL(new Blob([
  "let v=Date.now();setInterval(()=>{const n=Date.now();postMessage(n-v-1000);v=n;},1000);"
], {type:"text/javascript"}));
const w = new Worker(blob);
w.onmessage = (e) => { if (e.data > drift) drift = e.data; };
window.__meet = () => {
  const r = { tikken, drift, vis: document.visibilityState, focus: (()=>{try{return document.hasFocus()}catch(_){return null}})() };
  tikken = 0; drift = 0; return r;
};
window.__geluid = () => {
  const ac = new (window.AudioContext||window.webkitAudioContext)();
  const o = ac.createOscillator(), g = ac.createGain();
  o.frequency.value = 60; g.gain.value = 0.02; o.connect(g); g.connect(ac.destination); o.start();
  return ac.state;
};
<\/script>`;

const server = createServer((req, res) => {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(PAGINA);
}).listen(0, "127.0.0.1");
await new Promise((r) => server.on("listening", r));
const BASIS = `http://127.0.0.1:${server.address().port}/`;

const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-klokproef-"));
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

// De varianten. venster: "gewoon" = achtergrondtabblad in een gewoon venster,
// "ingeklapt" = actief tabblad in een geminimaliseerd venster (de Vinted-weg nu).
const VARIANTEN = [
  { naam: "kaal achtergrondtabblad",            venster: "gewoon" },
  { naam: "debugger",                           venster: "gewoon", attach: true },
  { naam: "debugger+focus",                     venster: "gewoon", attach: true, focus: true },
  { naam: "debugger+focus+ontdooi",             venster: "gewoon", attach: true, focus: true, ontdooi: true },
  { naam: "debugger+focus+screencast",          venster: "gewoon", attach: true, focus: true, screencast: true },
  { naam: "debugger+focus+ontdooi+screencast",  venster: "gewoon", attach: true, focus: true, ontdooi: true, screencast: true },
  { naam: "geluid (geen debugger)",             venster: "gewoon", geluid: true },
  { naam: "ingeklapt venster, actief tabblad",  venster: "ingeklapt" },
  { naam: "ingeklapt + debugger + focus",       venster: "ingeklapt", attach: true, focus: true, ontdooi: true },
];

try {
  await pauze(2500);
  // Eén gewoon venster met een actief tabblad vooraan; alle "gewoon"-varianten
  // komen daar als achtergrondtabblad bij.
  const eersteDoelen = await stuur("Target.getTargets", { filter: [{}] });
  const startPagina = eersteDoelen.result.targetInfos.find((t) => t.type === "page");
  const hoofdVenster = startPagina ? (await stuur("Browser.getWindowForTarget", { targetId: startPagina.targetId })).result?.windowId : null;

  for (const v of VARIANTEN) {
    if (v.venster === "gewoon") {
      const t = await stuur("Target.createTarget", { url: BASIS, background: true });
      v.targetId = t.result.targetId;
    } else {
      const t = await stuur("Target.createTarget", { url: BASIS, newWindow: true });
      v.targetId = t.result.targetId;
      const w = await stuur("Browser.getWindowForTarget", { targetId: v.targetId });
      v.windowId = w.result?.windowId;
    }
    await pauze(400);
  }
  // Het startvenster weer naar voren en de losse vensters inklappen.
  for (const v of VARIANTEN) {
    if (v.venster === "ingeklapt" && v.windowId != null) {
      await stuur("Browser.setWindowBounds", { windowId: v.windowId, bounds: { windowState: "minimized" } });
    }
  }
  await pauze(1500);

  for (const v of VARIANTEN) {
    const s = await stuur("Target.attachToTarget", { targetId: v.targetId, flatten: true });
    v.sid = s.result.sessionId;                       // altijd nodig om te kunnen meten
    if (v.geluid) {
      await stuur("Runtime.evaluate", { expression: "window.__geluid()", returnByValue: true }, v.sid);
    }
    if (v.focus) {
      const r = await stuur("Emulation.setFocusEmulationEnabled", { enabled: true }, v.sid);
      v.focusFout = r.error ? JSON.stringify(r.error) : null;
    }
    if (v.screencast) {
      const r = await stuur("Page.startScreencast", { format: "jpeg", quality: 1, maxWidth: 32, maxHeight: 32, everyNthFrame: 60 }, v.sid);
      v.screencastFout = r.error ? JSON.stringify(r.error) : null;
    }
  }
  // Let op: elke variant is nu "attached" omdat meten zonder sessie niet gaat.
  // Het verschil tussen "kaal" en "debugger" is daarmee weg; dat is bewust, de
  // vergelijking die telt is focus/ontdooi/screencast/geluid ertegenover.

  const ontdooiers = VARIANTEN.filter((v) => v.ontdooi);
  const tik = setInterval(() => {
    for (const v of ontdooiers) {
      stuur("Page.setWebLifecycleState", { state: "active" }, v.sid);
    }
  }, 10000);

  console.log(`Meten, elke 30 seconden, ${MINUTEN} minuten lang.`);
  console.log("tikken per seconde (10 = vol tempo) | drift = langste stilstand van de Web Worker\n");
  const kop = "tijd  " + VARIANTEN.map((v, i) => String(i).padStart(5)).join("");
  console.log(kop);
  const geschiedenis = VARIANTEN.map(() => []);
  const start = Date.now();
  for (let ronde = 0; ronde * 30 < MINUTEN * 60; ronde++) {
    await pauze(30000);
    const uitslagen = [];
    for (const v of VARIANTEN) {
      const u = await stuur("Runtime.evaluate",
        { expression: "JSON.stringify(window.__meet ? window.__meet() : null)", returnByValue: true }, v.sid);
      let val = null;
      try { val = JSON.parse(u.result?.result?.value ?? "null"); } catch (_) {}
      uitslagen.push(val);
    }
    const min = ((Date.now() - start) / 60000).toFixed(1);
    console.log(`${String(min).padStart(4)}m ` + uitslagen.map((u) => {
      if (!u) return "    ?";
      return (u.tikken / 30).toFixed(1).padStart(5);
    }).join(""));
    uitslagen.forEach((u, i) => u && geschiedenis[i].push(u));
  }
  clearInterval(tik);

  console.log("\n================ UITSLAG ================");
  VARIANTEN.forEach((v, i) => {
    const g = geschiedenis[i];
    if (!g.length) return console.log(`${i}. ${v.naam}: geen meting`);
    const perSec = g.map((x) => x.tikken / 30);
    const laatste = g.slice(-4);
    const gem = (a) => a.reduce((s, x) => s + x, 0) / a.length;
    console.log(
      `${i}. ${v.naam}\n` +
      `   tempo: gemiddeld ${gem(perSec).toFixed(1)}/s, laatste 2 min ${gem(laatste.map(x=>x.tikken/30)).toFixed(1)}/s, ` +
      `laagste ${Math.min(...perSec).toFixed(1)}/s\n` +
      `   langste stilstand: ${Math.max(...g.map((x) => x.drift))} ms | pagina zegt: ${g.at(-1).vis}${g.at(-1).focus ? "+focus" : ""}` +
      (v.focusFout ? ` | focus mislukt: ${v.focusFout}` : "") +
      (v.screencastFout ? ` | screencast mislukt: ${v.screencastFout}` : "")
    );
  });
} catch (e) {
  console.log("FOUT:", e && e.stack);
} finally {
  chrome.kill();
  await pauze(1200);
  server.close();
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) {}
}
process.exit(0);
