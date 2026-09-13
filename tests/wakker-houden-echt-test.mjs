/**
 * De échte proef: houdt de extensie de computer ook werkelijk wakker?
 *
 * tests/wakker-houden-test.js draait background.js in een nagebouwde omgeving en
 * bewijst dat onze code chrome.power aanroept. Dat zegt nog niets over de
 * computer zelf. Deze proef start een echte Chrome met de echte extensie erin,
 * laat de echte pollJobsEenRonde draaien, en leest daarna bij het
 * besturingssysteem uit of er werkelijk een slaapblokkade staat.
 *
 * Alleen het net en de instellingen zijn nagebouwd: fetch geeft één wachtende
 * opdracht terug en Calm mode staat aan met een pauze tot over een uur, zodat de
 * opdracht netjes blijft wachten en er niets echt gepubliceerd wordt.
 *
 * Draaien (alleen macOS): node tests/wakker-houden-echt-test.mjs [pad naar extensie]
 * Voor de voor-en-na-proef: haal een oude versie op met
 *   git archive <commit>:extension | tar -x -C /tmp/oud
 * en geef /tmp/oud als pad mee. Zonder de reparatie hoort er geen enkele
 * blokkade te staan.
 */
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EXT = process.argv[2] || new URL("../extension", import.meta.url).pathname;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
if (process.platform !== "darwin") {
  console.log("Deze proef leest de slaapblokkades van macOS uit; op dit systeem niet te draaien.");
  process.exit(0);
}
const profiel = mkdtempSync(join(tmpdir(), "omnivaleur-proef-"));
let mislukt = 0;
const check = (naam, goed, uitleg) => {
  if (goed) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
};
const blokkade = () => {
  const uit = execFileSync("pmset", ["-g", "assertions"], { encoding: "utf8" });
  return uit.split("\n").filter((r) => /Google Chrome/i.test(r) && /NoIdleSleep|PreventUserIdleSystemSleep/i.test(r));
};

// Chrome geeft het Extensions-domein alleen vrij over de pijp, en alleen met
// --enable-unsafe-extension-debugging. Met --load-extension op de opdrachtregel
// laadt hij sinds Chrome 152 niets meer.
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
  console.log("\nExtensieversie:", await doe("chrome.runtime.getManifest().version"), "\n");

  await doe(`self.fetch = async (u) => {
      const jobs = String(u).includes('/api/jobs/pending') &&
        new URL(String(u)).searchParams.get('platform') === 'marktplaats'
        ? [{id:'proef-1', action:'create', platform:'marktplaats', item_id:'x', payload:{}}] : [];
      return new Response(JSON.stringify(jobs), {status:200, headers:{'Content-Type':'application/json'}});
    }; 'net nagebouwd'`);
  await doe(`(async()=>{await chrome.storage.sync.set({calmMode:true});
    await chrome.storage.local.set({calmVolgendeNa: Date.now()+3600000});})()`);
  await pauze(2000);   // laat een ronde die door de instelling is gewekt eerst uitlopen

  console.log("Er staat werk in de wachtrij:");
  console.log("       ronde:", await doe("pollJobsEenRonde().then(()=>'klaar').catch(e=>'fout: '+e.message)"));
  let met = [];
  for (let i = 0; i < 10 && !met.length; i++) { await pauze(500); met = blokkade(); }
  check("de computer mag niet in slaap vallen", met.length > 0, "geen blokkade van Chrome gevonden");
  if (met.length) console.log("       " + met[0].trim());

  console.log("\nDe wachtrij is leeg:");
  await doe("self.fetch = async () => new Response('[]', {status:200, headers:{'Content-Type':'application/json'}}); 'leeg'");
  console.log("       ronde:", await doe("pollJobsEenRonde().then(()=>'klaar').catch(e=>'fout: '+e.message)"));
  let na = blokkade();
  for (let i = 0; i < 10 && na.length; i++) { await pauze(500); na = blokkade(); }
  check("de computer mag weer gaan slapen", na.length === 0, na.join(" | "));
} finally {
  chrome.kill();
  await pauze(1500);
  try { rmSync(profiel, { recursive: true, force: true }); } catch (_) { /* Chrome ruimt zelf nog op */ }
}
console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
process.exit(mislukt ? 1 : 0);
