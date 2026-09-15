// Herkent de extensie dat een advertentie na het verwijderen echt weg is?
//
// 15-09-2026. Bij Zilverwebsite liepen op één ochtend 57 herplaatsingen vast met
// "Relist failed — still live". Het verwijderen was elke keer gelukt: de server
// gaf HTTP 410 en van die 57 advertenties stond er nul nog op Marktplaats. De
// extensie eiste er alleen een tekstbevestiging bij, en zocht daarvoor naar
// "verlopen advertentie" terwijl Marktplaats "Deze advertentie is helaas
// verlopen" schrijft. Geen match, dus "mislukt", dus werd de nieuwe plaatsing
// overgeslagen en stond het artikel nergens meer.
//
// Deze test draait de ECHTE functie uit background.js, één keer uit de versie
// van vóór de reparatie en één keer uit de huidige, met exact wat productie op
// 15-09-2026 terugkreeg. En hij legt de patronen langs de echte pagina's van
// Marktplaats en 2dehands, zodat een volgende wijziging aan die pagina's hier
// opvalt en niet bij een klant.
//
// Draaien:  node tests/marktplaats-verlopen-herkennen-test.mjs
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const VORIGE_COMMIT = process.env.VORIGE_COMMIT || "HEAD";
let fouten = 0, gedaan = 0;
const ok = (naam, waar, extra = "") => {
  gedaan++;
  if (!waar) { fouten++; console.log(`  FOUT  ${naam} ${extra}`); }
  else console.log(`  ok    ${naam} ${extra}`);
};

// --- de echte functie uit een versie van background.js lichten ----------------
function sliceFunctie(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let diepte = 0, i = bron.indexOf("{", start);
  for (let j = i; j < bron.length; j++) {
    if (bron[j] === "{") diepte++;
    else if (bron[j] === "}") { diepte--; if (diepte === 0) return bron.slice(start, j + 1); }
  }
  throw new Error("geen sluitende accolade");
}

function laadVerwijderaar(bron) {
  const consts = [...bron.matchAll(/^const WEG_(?:TEKST|MARKER)_BRON =[\s\S]*?;$/gm)].map(m => m[0]).join("\n");
  const code = `
    let _laatsteVerwijderpagina = "niet gekeken";
    let _laatsteVerwijderDiag = [];
    ${consts}
    ${sliceFunctie(bron, "verwijderViaAdvertentiepagina")}
    globalThis.__fn = verwijderViaAdvertentiepagina;
    globalThis.__diag = () => _laatsteVerwijderDiag;
  `;
  const sandbox = {
    console: { log() {}, error() {} },
    setTimeout,
    URL,
    stuurWerkTabbladNaar: async () => {},
    waitForTabLoad: async () => {},
    execInTab: null,   // per scenario gezet
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  return sandbox;
}

// Precies wat de pagina op 15-09-2026 teruggaf bij de 57 vastgelopen klussen:
// de verwijderknop werd geklikt en bevestigd, daarna gaf de server 410 en zei de
// gerenderde pagina "Deze advertentie is helaas verlopen" (dat laatste herkende
// de oude tekstcontrole niet, vandaar textHit: null in de echte diagnostiek).
const GERENDERD_VERLOPEN = "terug\ndeze advertentie is helaas verlopen\nverlopen\nzilveren soeplepel met ebbenhouten handvat, empire.";

function maakExecInTab({ status, innerText }) {
  return async (tabId, fn, args = []) => {
    const src = String(fn);
    if (src.includes("WEG.test(tekst(b))") || src.includes("const WEG =") && src.includes("knoppen")) {
      return { ok: true };                       // verwijderknop gevonden en geklikt
    }
    if (src.includes("niet\\s+verkocht") || src.includes("niet\\s+verkocht".replace("\\s","\\s"))) {
      return { open: true, clicked: true, knop: "Niet verkocht via Marktplaats", gezien: [] };
    }
    if (src.includes("fetch(")) {                // de fetch-check
      const wegBron = args[1], markerBron = args[2];
      if (status === 404 || status === 410) return { weg: true, status, via: "status" };
      const html = innerText;
      if (markerBron && new RegExp(markerBron).test(html)) return { weg: true, status, via: "marker" };
      const oud = /niet meer beschikbaar|is verwijderd|verlopen advertentie|no longer available/;
      const re = wegBron ? new RegExp(wegBron) : oud;
      const m = re.exec(html);
      return { weg: !!m, status, via: m ? `text:${m[0]}` : "no-match", htmlLen: html.length };
    }
    if (src.includes("innerText")) {             // de dom-tegencontrole
      const wegBron = args[1];
      const oud = /niet meer beschikbaar|is verwijderd|verlopen advertentie|no longer available|pagina niet gevonden|niet gevonden/;
      const re = wegBron ? new RegExp(wegBron) : oud;
      const m = re.exec(innerText);
      return { url: "https://www.marktplaats.nl/v/…", textHit: m ? m[0] : null };
    }
    return { ok: true };
  };
}

console.log("\n1. De echte functie, met wat productie op 15-09-2026 terugkreeg (410 + 'is helaas verlopen')");
for (const [label, bron] of [
  ["oud  (" + VORIGE_COMMIT + ")", execSync(`git show ${VORIGE_COMMIT}:extension/background.js`, { encoding: "utf8", maxBuffer: 64e6 })],
  ["nieuw (werkmap)", readFileSync("extension/background.js", "utf8")],
]) {
  const s = laadVerwijderaar(bron);
  s.execInTab = maakExecInTab({ status: 410, innerText: GERENDERD_VERLOPEN });
  const gelukt = await s.__fn(1, "https://www.marktplaats.nl/seller/view/m2430388819", "marktplaats");
  const verwacht = label.startsWith("nieuw");
  ok(`${label}: verwijderen gemeld als ${gelukt ? "GELUKT" : "MISLUKT"}`, gelukt === verwacht,
     verwacht ? "(hoort te lukken)" : "(dit is de fout die 57 advertenties kostte)");
}

console.log("\n2. Een advertentie die nog gewoon online staat blijft 'niet verwijderd'");
{
  const s = laadVerwijderaar(readFileSync("extension/background.js", "utf8"));
  s.execInTab = maakExecInTab({ status: 200, innerText: "zilveren gaucho mes uit argentinië, leren schede, gratis verzonden" });
  const gelukt = await s.__fn(1, "https://www.marktplaats.nl/seller/view/m2442967992", "marktplaats");
  ok("nieuw: levende advertentie wordt niet als verwijderd geboekt", gelukt === false);
}

console.log("\n3. De echte pagina's van Marktplaats en 2dehands");
const bron = readFileSync("extension/background.js", "utf8");
const pak = n => new Function(bron.match(new RegExp(`^const ${n} =[\\s\\S]*?;$`, "m"))[0] + `; return ${n};`)();
const NIEUW = new RegExp(pak("WEG_TEKST_BRON"));
const MARKER = new RegExp(pak("WEG_MARKER_BRON"));
const OUD = /niet meer beschikbaar|is verwijderd|verlopen advertentie|no longer available/;
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const paginas = [
  ["Marktplaats, verwijderd", "https://www.marktplaats.nl/v/antiek-en-kunst/antiek-bestek/m2430388819-zilveren-soeplepel-met-ebbenhouten-handvat-empire", true],
  ["2dehands, verwijderd", "https://www.2dehands.be/v/vetements-hommes/jeans/m2426669185-1327-navy-suitsupply-pak-broek", true],
  ["Marktplaats, nog online", "https://www.marktplaats.nl/v/antiek-en-kunst/antiek-goud-en-zilver/m2442967992-argentijns-gaucho-mes-met-zilveren-heft-en-schedebeslag", false],
];
for (const [naam, url, hoortWegTeZijn] of paginas) {
  let r;
  try { r = await fetch(url, { headers: { "User-Agent": UA } }); }
  catch (e) { console.log(`  OVERGESLAGEN ${naam}: geen verbinding (${e.message})`); continue; }
  const html = (await r.text()).toLowerCase();
  const status = r.status;
  const nieuwZegtWeg = status === 404 || status === 410 || MARKER.test(html) || NIEUW.test(html);
  const oudZegtWeg = status === 404 || status === 410 || OUD.test(html);
  ok(`${naam}: nieuwe controle zegt ${nieuwZegtWeg ? "weg" : "leeft"}`, nieuwZegtWeg === hoortWegTeZijn, `(HTTP ${status})`);
  if (hoortWegTeZijn) {
    ok(`${naam}: oude TEKSTcontrole herkende de pagina niet`, !OUD.test(html),
       "(daarom moest de statuscode alleen al genoeg zijn)");
    ok(`${naam}: nieuwe tekstcontrole herkent hem wel`, NIEUW.test(html), `("${(NIEUW.exec(html) || [""])[0]}")`);
  } else {
    ok(`${naam}: geen vals alarm op een levende pagina`, !NIEUW.test(html) && !MARKER.test(html));
  }
}

console.log(`\n${gedaan - fouten}/${gedaan} controles goed`);
process.exit(fouten ? 1 : 0);
