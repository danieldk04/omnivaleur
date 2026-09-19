// Een VERLOPEN advertentie is geen verkoop — en dus geen verkoopvraag.
//
// 19-09-2026, Lynn van De Juiste Toon: "Bij Items staat bij 'did these items
// sell?' de melding 'Not found on the platform anymore', maar als ik die dan na
// ga staan ze er wel nog op. Voornamelijk bij 2dehands."
//
// Allebei waar. Zo'n zoekertje is van de zoekresultaten af, maar zijn eigen
// pagina staat er nog: foto's, tekst, en VERLOPEN erop. Gemeten op haar account:
// van de 74 gemelde 2dehands-zoekertjes gaven er 55 HTTP 410 met "Dit zoekertje
// is helaas verlopen"; van vijf bewezen levende advertenties gaf er nul dat
// signaal. bekijkEigenPagina las die tekst niet eens: bij 410 gaf hij meteen
// "weg" terug, en "weg" wordt een verkoopvraag.
//
// Deze test draait de ECHTE functie uit background.js — eerst uit de versie van
// vóór de reparatie, dan uit de huidige — tegen de ECHTE pagina's zoals ze op
// 19-09-2026 terugkwamen (tests/fixtures, ongewijzigd, inclusief statuscode).
//
// Draaien:  node tests/verlopen-is-geen-verkoop-test.mjs
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import vm from "node:vm";

// De versie van VÓÓR de reparatie, met de hand vastgezet. Niet "HEAD": zodra de
// reparatie gecommit is vergelijkt HEAD zich met zichzelf en bewijst de proef
// niets meer (zie docs/kennisbank.md).
const VORIGE_COMMIT = process.env.VORIGE_COMMIT || "69c8ad7d";

let fouten = 0, gedaan = 0;
const ok = (naam, waar, extra = "") => {
  gedaan++;
  if (!waar) { fouten++; console.log(`  FOUT  ${naam} ${extra}`); }
  else console.log(`  ok    ${naam} ${extra}`);
};

function sliceFunctie(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let diepte = 0;
  const i = bron.indexOf("{", start);
  for (let j = i; j < bron.length; j++) {
    if (bron[j] === "{") diepte++;
    else if (bron[j] === "}") { diepte--; if (diepte === 0) return bron.slice(start, j + 1); }
  }
  throw new Error("geen sluitende accolade");
}

// De echte bekijkEigenPagina uit een versie van background.js, met een fetch die
// exact teruggeeft wat 2dehands teruggaf.
function laadKijker(bron, antwoord) {
  const consts = [...bron.matchAll(/^const (?:WEG_(?:TEKST|MARKER)_BRON|NIET_MEER_BESCHIKBAAR|IS_VERLOPEN) =[\s\S]*?;$/gm)]
    .map(m => m[0]).join("\n");
  const code = `
    ${consts}
    ${sliceFunctie(bron, "bekijkEigenPagina")}
    globalThis.__fn = bekijkEigenPagina;
  `;
  const sandbox = {
    console: { log() {}, warn() {}, error() {} },
    RegExp, String, Date, Promise,
    fetch: async () => ({
      status: antwoord.status,
      ok: antwoord.status >= 200 && antwoord.status < 300,
      redirected: false,
      url: antwoord.url,
      text: async () => antwoord.html,
    }),
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  return sandbox.__fn;
}

function pagina(naam, status, id) {
  const html = gunzipSync(readFileSync(new URL(`./fixtures/${naam}`, import.meta.url))).toString("utf8");
  return { html, status, url: `https://www.2dehands.be/seller/view/${id}`, id };
}

const VERLOPEN = pagina("2dehands-verlopen-m2222688236.html.gz", 410, "m2222688236");
const LEVEND  = pagina("2dehands-levend-m2437353800.html.gz", 200, "m2437353800");

const nu = readFileSync(new URL("../extension/background.js", import.meta.url), "utf8");
let oud = null;
try {
  oud = execSync(`git show ${VORIGE_COMMIT}:extension/background.js`, {
    cwd: new URL("..", import.meta.url).pathname, maxBuffer: 64 * 1024 * 1024,
  }).toString("utf8");
} catch (e) {
  console.log(`  LET OP  versie ${VORIGE_COMMIT} niet op te halen — de voor-en-na-proef is overgeslagen`);
}

console.log("Echte 2dehands-pagina's, echte functie uit background.js\n");

if (oud) {
  console.log(`VOOR de reparatie (${VORIGE_COMMIT}) — hier zat de fout:`);
  const voorVerlopen = await laadKijker(oud, VERLOPEN)("2dehands", VERLOPEN.id);
  ok("verlopen zoekertje werd 'weg' (en dus een verkoopvraag)",
     voorVerlopen === "weg", `-> ${voorVerlopen}`);
  const voorLevend = await laadKijker(oud, LEVEND)("2dehands", LEVEND.id);
  ok("levende advertentie was toen al goed", voorLevend === "leeft", `-> ${voorLevend}`);
  console.log("");
}

console.log("NA de reparatie:");
const naVerlopen = await laadKijker(nu, VERLOPEN)("2dehands", VERLOPEN.id);
ok("verlopen zoekertje heet nu 'verlopen', geen verkoopvraag meer",
   naVerlopen === "verlopen", `-> ${naVerlopen}`);
const naLevend = await laadKijker(nu, LEVEND)("2dehands", LEVEND.id);
ok("levende advertentie blijft 'leeft' — geen vals alarm",
   naLevend === "leeft", `-> ${naLevend}`);

// Een 404 zonder verlopen-tekst blijft een echte verdenking: daar zegt de pagina
// niet waarom de advertentie weg is, en dan hoort de vraag er juist wél te zijn.
const kaal404 = await laadKijker(nu, { html: "<html><body>Oeps</body></html>", status: 404, url: "x" })("2dehands", "m1");
ok("404 zonder uitleg blijft 'weg' — de verkoopvraag blijft bestaan", kaal404 === "weg", `-> ${kaal404}`);

// En een geblokkeerde aanvraag bewijst nog steeds niets.
const geblokkeerd = await laadKijker(nu, { html: "", status: 403, url: "x" })("2dehands", "m1");
ok("403 blijft 'onbekend' — niets bewezen, niets doen", geblokkeerd === "onbekend", `-> ${geblokkeerd}`);

console.log(`\n${gedaan - fouten}/${gedaan} goed`);
process.exit(fouten ? 1 : 0);
