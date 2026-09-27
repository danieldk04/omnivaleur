// Een blokkade (403) na het verwijderen is geen bewijs dat de advertentie er nog staat.
//
// 27-09-2026. Een verkoper verkocht twee artikelen op Vinted; binnen een minuut
// liepen vier verwijderingen op Marktplaats en 2dehands. Het venster "Heb je dit
// verkocht via Marktplaats?" werd netjes met "Niet verkocht" beantwoord, daarna
// gaf de controlepagina drie keer 403 met twee seconden ertussen, en de opdracht
// werd geboekt als "Nothing was removed". Drie van die vier advertenties stonden
// aantoonbaar niet meer in de openbare verkoperslijst.
//
// Deze test draait de ECHTE functie uit background.js, uit de versie van vóór de
// reparatie (vastgezet, nooit HEAD) en uit de werkmap, met de diagnostiek van
// productie: eerst drie keer 403, daarna het normale 410.
//
// Draaien:  node tests/verwijderen-blokkade-403-test.mjs
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const VORIGE_COMMIT = process.env.VORIGE_COMMIT || "9a4a0a5c";
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

function laad(bron, antwoorden) {
  const consts = [...bron.matchAll(/^const WEG_(?:TEKST|MARKER)_BRON =[\s\S]*?;$/gm)].map(m => m[0]).join("\n");
  const wachttijden = [];
  const fetches = [];
  const sandbox = {
    console: { log() {}, error() {} },
    // Nep-klok: registreert hoe lang de functie wil wachten, maar wacht niet echt.
    setTimeout: (fn, ms) => { wachttijden.push(ms); return setImmediate(fn); },
    URL,
    stuurWerkTabbladNaar: async () => {},
    waitForTabLoad: async () => {},
    execInTab: async (tabId, fn) => {
      const src = String(fn);
      if (src.includes("fetch(")) {
        const status = antwoorden[Math.min(fetches.length, antwoorden.length - 1)];
        fetches.push(status);
        if (status === 404 || status === 410) return { weg: true, status, via: "status" };
        if (status !== 200) return { weg: false, status, via: "not-ok" };
        return { weg: false, status, via: "no-match", htmlLen: 5000 };
      }
      if (src.includes("_bevestig") || src.includes("jaBron")) {
        return { open: false };
      }
      if (src.includes("innerText")) return { url: "x", textHit: null };
      return { ok: true };
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(`
    let _laatsteVerwijderpagina = "niet gekeken";
    let _laatsteVerwijderDiag = [];
    const BEVESTIG_JA_BRON = "^ja"; const BEVESTIG_NEE_BRON = "^nee";
    function _bevestigInVenster(jaBron, neeBron) { return { open: false }; }
    ${consts}
    ${sliceFunctie(bron, "verwijderViaAdvertentiepagina")}
    globalThis.__fn = verwijderViaAdvertentiepagina;
  `, sandbox);
  return { fn: sandbox.__fn, wachttijden, fetches };
}

const OUD = execSync(`git show ${VORIGE_COMMIT}:extension/background.js`, { encoding: "utf8", maxBuffer: 64e6 });
const NIEUW = readFileSync("extension/background.js", "utf8");
const URL_ = "https://www.marktplaats.nl/seller/view/m2438895939";

console.log("\n1. Productie 27-09: drie keer 403, daarna 410 (advertentie was echt weg)");
for (const [label, bron, verwacht] of [[`oud (${VORIGE_COMMIT})`, OUD, false], ["nieuw (werkmap)", NIEUW, true]]) {
  const t = laad(bron, [403, 403, 403, 410]);
  const gelukt = await t.fn(1, URL_, "marktplaats");
  ok(`${label}: gemeld als ${gelukt ? "GELUKT" : "MISLUKT"}`, gelukt === verwacht,
     `(controles: ${t.fetches.join(",")})`);
}

console.log("\n2. Blijvende blokkade: nooit een succes zonder bewijs, en elke wachttijd onder 30 s");
{
  const t = laad(NIEUW, [403]);
  const gelukt = await t.fn(1, URL_, "marktplaats");
  ok("nieuw: blijft MISLUKT", gelukt === false, `(${t.fetches.length} controles)`);
  ok("nieuw: geen wachttijd van 30 s of langer", Math.max(...t.wachttijden) < 30000,
     `(langste ${Math.max(...t.wachttijden)} ms)`);
  ok("nieuw: houdt op na hooguit zes controles", t.fetches.length <= 6);
}

console.log("\n3. Levende advertentie (200): zoals altijd drie controles, geen extra wachten");
{
  const t = laad(NIEUW, [200]);
  const gelukt = await t.fn(1, URL_, "marktplaats");
  ok("nieuw: blijft MISLUKT", gelukt === false);
  ok("nieuw: precies drie controles", t.fetches.length === 3, `(${t.fetches.length})`);
}

console.log("\n4. Gewoon 410 meteen: één controle, klaar");
{
  const t = laad(NIEUW, [410]);
  ok("nieuw: GELUKT", (await t.fn(1, URL_, "marktplaats")) === true && t.fetches.length === 1);
}

console.log(fouten ? `\n${fouten} fout(en)` : "\nalles ok");
process.exit(fouten ? 1 : 0);
