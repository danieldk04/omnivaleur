/**
 * Wat de advertentiepagina antwoordde, moet in de foutmelding van een mislukte
 * Marktplaats/2dehands-verwijdering staan.
 *
 * Aanleiding: 30-09-2026 strandden bij Zilverwebsite (26cf5471) 55
 * herplaatsingen in 17 minuten op "the advert's own page gave no answer
 * either". Achteraf was niet te zeggen of Marktplaats blokkeerde (403), de
 * verkoper uitgelogd was of het tabblad wegviel: de controle gaf in alle
 * gevallen alleen null terug.
 *
 * De functie die in het tabblad draait komt letterlijk uit de bron.
 *
 * Draaien:  node tests/verwijderen-antwoord-advertentiepagina-test.js
 *           node tests/verwijderen-antwoord-advertentiepagina-test.js --oud=85e84d99   (faalt)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const oudArg = process.argv.find((a) => a.startsWith("--oud="));
const BG = oudArg
  ? execSync(`git show ${oudArg.slice(6)}:extension/background.js`,
             { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const kop = "await execInTab(tabId, async (u, wegBron, markerBron) => {";
const start = BG.indexOf(kop);
if (start < 0) throw new Error("de controle op de advertentiepagina is niet gevonden");
const eind = BG.indexOf("}, [adUrl, WEG_TEKST_BRON, WEG_MARKER_BRON])", start);
const body = BG.slice(start + kop.length, eind);
const inTabblad = new Function("u", "wegBron", "markerBron", "fetch", "URL",
  `return (async () => {${body}})();`);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};
const antwoordVan = (r) => (r && typeof r === "object" ? r.antwoord : r);
const levend = (r) => (r && typeof r === "object" ? r.live : r);

(async () => {
  console.log("\nVerwijderen: wat zei de advertentiepagina");
  const url = "https://www.marktplaats.nl/seller/view/m2436458145";

  // 1. Marktplaats blokkeert: 403.
  let r = await inTabblad(url, "helaas verlopen", "zzz-marker",
    async () => ({ ok: false, status: 403, redirected: false, url }), URL);
  ok("403 -> niets bewezen (null)", levend(r) === null, r);
  ok("403 -> 'HTTP 403' reist mee", /HTTP 403/.test(String(antwoordVan(r))), r);

  // 2. Uitgelogd: doorgestuurd naar de inlogpagina, die zelf 200 geeft.
  r = await inTabblad(url, "helaas verlopen", "zzz-marker",
    async () => ({ ok: true, status: 200, redirected: true,
                   url: "https://www.marktplaats.nl/identity/v2/login?x=1",
                   text: async () => "<html>inloggen</html>" }), URL);
  ok("doorgestuurd -> het pad van de inlogpagina reist mee",
     /identity\/v2\/login/.test(String(antwoordVan(r))), r);

  // 3. Netwerkfout.
  r = await inTabblad(url, "helaas verlopen", "zzz-marker",
    async () => { throw new TypeError("Failed to fetch"); }, URL);
  ok("netwerkfout -> null met de reden", levend(r) === null && /Failed to fetch/.test(String(antwoordVan(r))), r);

  // 4. Echt weg: 410 blijft 'weg' (niets veranderd aan de uitkomst).
  r = await inTabblad(url, "helaas verlopen", "zzz-marker",
    async () => ({ ok: false, status: 410, redirected: false, url }), URL);
  ok("410 -> weg (false)", levend(r) === false, r);

  // 5. Beide foutmeldingen zonder bewijs dragen de staart.
  const blok = BG.slice(BG.indexOf("if (live !== false) {", start), BG.indexOf("// Aantoonbaar weg = doel bereikt.", start));
  ok("beide meldingen eindigen op het antwoord van de pagina",
     (blok.match(/\+\s*antwoordStaart/g) || []).length === 2, blok.slice(0, 80));

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
