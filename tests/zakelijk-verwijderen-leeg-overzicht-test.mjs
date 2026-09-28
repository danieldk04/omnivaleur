// Verwijderen bij een zakelijk account: een leeg overzicht mag de route via de
// advertentiepagina niet afsnijden.
//
// 28-09-2026. Een zakelijk Marktplaats- of 2dehands-account heeft altijd een leeg
// persoonlijk overzicht. bgDeleteMp2dh gooide dan meteen "Couldn't read your
// listings overview" en kwam nooit bij verwijderViaAdvertentiepagina, de route die
// op advertentienummer werkt en bij zes zakelijke verkopers honderden keren
// gelukt is. Daardoor kon vervangen (herplaatsen) bij zakelijke accounts niet.
//
// Deze test draait de ECHTE bgDeleteMp2dh uit de versie van vóór de reparatie
// (vastgezet, nooit HEAD) en uit de werkmap.
//
// Draaien:  node tests/zakelijk-verwijderen-leeg-overzicht-test.mjs
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const VORIGE_COMMIT = process.env.VORIGE_COMMIT || "2394639c";
let fouten = 0;
const ok = (naam, waar, extra = "") => {
  if (!waar) fouten++;
  console.log(`  ${waar ? "ok  " : "FOUT"}  ${naam} ${extra}`);
};

function sliceFunctie(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  let diepte = 0;
  for (let j = bron.indexOf("{", start); j < bron.length; j++) {
    if (bron[j] === "{") diepte++;
    else if (bron[j] === "}" && --diepte === 0) return bron.slice(start, j + 1);
  }
  throw new Error("geen sluitende accolade");
}

// overzicht: wat de zoekstap in het overzicht teruggeeft.
// live: wat de controle op /seller/view zegt (true = staat online, false = weg, null = onbewezen).
// advertentiepagina: of verwijderen via de advertentiepagina lukt.
function laad(bron, { overzicht, live, advertentiepagina }) {
  const consts = [...bron.matchAll(/^const WEG_(?:TEKST|MARKER)_BRON =[\s\S]*?;$/gm)].map(m => m[0]).join("\n");
  const spoor = { afgemeld: null, viaPagina: [] };
  const sandbox = {
    console: { log() {}, error() {} },
    setTimeout: (fn) => setImmediate(fn),
    URL,
    openWorkerTab: (url, cb) => cb({ id: 7 }),
    waitForTabLoad: async () => {},
    stuurWerkTabbladNaar: async () => {},
    mpAdvertentieSnapshot: async () => ({}),
    expandMp2dhOverview: async () => {},
    sluitWerkTabblad: () => {},
    execInTab: async (tabId, fn) => {
      const src = String(fn);
      if (src.includes("fetch(")) return live;
      return overzicht;
    },
    verwijderViaAdvertentiepagina: async (tabId, url) => { spoor.viaPagina.push(url); return advertentiepagina; },
    finaliseJob: async (_s, _id, status, res) => { spoor.afgemeld = { status, ...res }; },
  };
  vm.createContext(sandbox);
  vm.runInContext(`
    let _laatsteVerwijderpagina = "niet gekeken";
    let _laatsteVerwijderDiag = [];
    ${consts}
    ${sliceFunctie(bron, "bgDeleteMp2dh")}
    globalThis.__fn = bgDeleteMp2dh;
  `, sandbox);
  return { fn: sandbox.__fn, spoor };
}

async function draai(t, job) {
  try { await t.fn(job, "https://server"); return null; } catch (e) { return String(e.message || e); }
}

const OUD = execSync(`git show ${VORIGE_COMMIT}:extension/background.js`, { encoding: "utf8", maxBuffer: 64e6 });
const NIEUW = readFileSync("extension/background.js", "utf8");
const JOB = { id: "j1", platform: "marktplaats",
  payload: { title: "Ralph Lauren Zip Hoodie", platform_listing_id: "m2438895939" } };

console.log("\n1. Zakelijk account: overzicht leeg, advertentie staat online, verwijderen via zijn pagina lukt");
for (const [label, bron, verwachtGelukt] of [[`oud (${VORIGE_COMMIT})`, OUD, false], ["nieuw (werkmap)", NIEUW, true]]) {
  const t = laad(bron, { overzicht: { found: false, rendered: 0 }, live: true, advertentiepagina: true });
  const fout = await draai(t, JOB);
  const gelukt = !fout && t.spoor.afgemeld?.note === "deleted_via_ad_page";
  ok(`${label}: ${gelukt ? "VERWIJDERD via de advertentiepagina" : "MISLUKT: " + String(fout).slice(0, 70)}`,
     gelukt === verwachtGelukt);
}

console.log("\n2. Uitgelogd: overzicht leeg en de advertentiepagina onbewezen. Nooit een succes");
{
  const t = laad(NIEUW, { overzicht: { found: false, rendered: 0 }, live: null, advertentiepagina: true });
  const fout = await draai(t, JOB);
  ok("nieuw: fout, niets afgemeld als gelukt", !!fout && t.spoor.afgemeld === null, `(${String(fout).slice(0, 60)})`);
  ok("nieuw: de fout noemt inloggen", /logged in/.test(String(fout)));
  ok("nieuw: niets aangeklikt op de advertentiepagina", t.spoor.viaPagina.length === 0);
}

console.log("\n3. Knop op de advertentiepagina werkt niet: fout, geen succes");
{
  const t = laad(NIEUW, { overzicht: { found: false, rendered: 0 }, live: true, advertentiepagina: false });
  const fout = await draai(t, JOB);
  ok("nieuw: fout, niets afgemeld", !!fout && t.spoor.afgemeld === null);
}

console.log("\n4. Server zegt 410 (al weg): afgemeld als al afwezig, zoals bij een gevuld overzicht");
{
  const t = laad(NIEUW, { overzicht: { found: false, rendered: 0 }, live: false, advertentiepagina: true });
  const fout = await draai(t, JOB);
  ok("nieuw: already_absent", !fout && t.spoor.afgemeld?.note === "already_absent");
}

console.log("\n5. Zonder advertentienummer blijft een leeg overzicht een fout (niets te zoeken op nummer)");
{
  const t = laad(NIEUW, { overzicht: { found: false, rendered: 0 }, live: true, advertentiepagina: true });
  const fout = await draai(t, { ...JOB, payload: { title: "x" } });
  ok("nieuw: fout over het overzicht", /Couldn't read your marktplaats listings overview/.test(String(fout)));
}

console.log(fouten ? `\n${fouten} fout(en)` : "\nalles ok");
process.exit(fouten ? 1 : 0);
