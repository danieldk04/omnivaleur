/**
 * Vinted-verwijderknop aangeklikt voordat hij leefde.
 *
 * Aanleiding (24-09-2026, klant 3bfbed2c, advertentie 9618700667): "Confirm-
 * delete button not found". De verwijderknop wás aangeklikt, maar er kwam geen
 * venster. Nagemeten op de echte vinted.nl-pagina: de knoppen staan als kant-en-
 * klare HTML 3 tot 5 seconden op de pagina voordat React ze klikbaar maakt; een
 * klik in dat gat doet niets, een klik erna wel.
 *
 * Deze proef draait de ECHTE routine uit background.js in een echte Chrome tegen
 * een pagina die precies dat doet: knop meteen zichtbaar, pas na 2,5 s levend
 * (met React's eigen kenmerk __reactProps$), en pas dan opent een klik het
 * bevestigvenster met Vinted's echte data-testid's.
 *
 * Draaien:  node tests/vinted-verwijderen-voor-hydratie-echt-test.mjs
 *           node tests/vinted-verwijderen-voor-hydratie-echt-test.mjs --oud   (hoort te falen)
 */
import { spawn, execSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
// Vast commit-nummer, geen HEAD: na het committen zou HEAD de nieuwe code zijn.
const VOOR = "9b39f008";
const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync(`git show ${VOOR}:extension/background.js`, { cwd: ROOT, maxBuffer: 1 << 28 }).toString()
  : readFileSync(join(ROOT, "extension", "background.js"), "utf8");
const start = BG.indexOf("async function _mwVintedVerwijderen()");
const routine = BG.slice(start, BG.indexOf("\nfunction execInTab(", start));

const PAGINA = `<!doctype html><html><body>
<header><a href="/">Vinted</a><button>Sell now</button></header>
<main><button data-testid="item-edit-button">Edit listing</button>
<button data-testid="item-delete-button" id="weg">Delete</button></main>
<footer><a>Help centre</a><a>Privacy centre</a></footer>
<script>
  window.__verwijderd = false; window.__klikkenVoorLeven = 0;
  const knop = document.getElementById("weg");
  knop.addEventListener("click", () => { if (!knop.__reactProps$abc) window.__klikkenVoorLeven++; });
  // Wat een echte pagina ook doet: af en toe iets bijzetten (advertenties, foto's).
  setInterval(() => document.body.appendChild(document.createElement("i")), 700);
  setTimeout(() => {
    knop.__reactProps$abc = { onClick: true };
    knop.addEventListener("click", () => {
      const v = document.createElement("div");
      v.setAttribute("role", "dialog"); v.setAttribute("data-testid", "item-delete-modal");
      v.innerHTML = '<h2>Delete item?</h2><button data-testid="item-delete-cancelation-button">Cancel</button>'
                  + '<button data-testid="item-delete-confirmation-button">Confirm and delete</button>';
      document.body.appendChild(v);
      v.querySelector('[data-testid="item-delete-confirmation-button"]').addEventListener("click", () => {
        window.__verwijderd = true; v.remove();
      });
    });
  }, 2500);
</script></body></html>`;

const server = createServer((req, res) => { res.setHeader("content-type", "text/html"); res.end(PAGINA); });
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const poort = server.address().port;
const profiel = mkdtempSync(join(tmpdir(), "vt-hydratie-"));
const dbg = 9400 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${dbg}`, `--user-data-dir=${profiel}`,
  "--no-first-run", "about:blank"], { stdio: "ignore" });

let mislukt = 0;
try {
  let doelen;
  for (let i = 0; i < 50 && !doelen; i++) {
    try { doelen = await (await fetch(`http://127.0.0.1:${dbg}/json`)).json(); }
    catch { await new Promise((r) => setTimeout(r, 200)); }
  }
  const ws = new WebSocket(doelen.find((d) => d.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let n = 0; const wacht = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (wacht.has(m.id)) { wacht.get(m.id)(m); wacht.delete(m.id); } });
  const cmd = (method, params = {}) => new Promise((r) => { const id = ++n; wacht.set(id, r); ws.send(JSON.stringify({ id, method, params })); });

  await cmd("Page.enable");
  await cmd("Page.navigate", { url: `http://127.0.0.1:${poort}/items/9618700667` });
  // Zodra de knop er staat, zoals de extensie hem aantreft: HTML er, React nog niet.
  for (let i = 0; i < 50; i++) {
    const r = await cmd("Runtime.evaluate", { expression: "!!document.querySelector('#weg')", returnByValue: true });
    if (r.result?.result?.value) break;
    await new Promise((r) => setTimeout(r, 50));
  }
  const r = await cmd("Runtime.evaluate", {
    expression: `(${routine})().then(u => JSON.stringify({ u, verwijderd: window.__verwijderd, dood: window.__klikkenVoorLeven }))`,
    awaitPromise: true, returnByValue: true,
  });
  const uit = JSON.parse(r.result?.result?.value || "{}");
  console.log(`${OUD ? "oude" : "nieuwe"} code →`, JSON.stringify(uit));
  const ok = (naam, v) => { console.log(`  ${v ? "✓" : "✗"} ${naam}`); if (!v) mislukt++; };
  ok("de verwijderknop is aangeklikt", uit.u?.clickedDelete === true);
  ok("het bevestigvenster is gevonden en bevestigd", uit.u?.clickedConfirm === true);
  ok("de advertentie is echt verwijderd", uit.verwijderd === true);
  ws.close();
} finally {
  chrome.kill(); server.close();
  try { rmSync(profiel, { recursive: true, force: true }); } catch {}
}
process.exit(mislukt ? 1 : 0);
