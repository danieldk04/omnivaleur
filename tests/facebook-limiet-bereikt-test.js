/**
 * Klant f8c0cce9, 03-10-2026 12:20 UTC: een Facebook-plaatsing (Fender
 * Telecaster) kwam niet uit op het formulier maar op
 *   https://www.facebook.com/marketplace/np/create/limit_reached/
 * en de klant kreeg "We could not tell from here whether that page was a login
 * screen or something else ... Please send them to us." Het adres zei het al:
 * Facebook laat dit account voorlopig geen nieuwe advertentie maken.
 *
 * Draait de echte meldNooitBegonnen uit extension/background.js met de
 * waarneming die de bewaker die middag uit het tabblad haalde.
 *
 * Draaien: node tests/facebook-limiet-bereikt-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function functieUit(bron, naam, woord = "function") {
  const start = bron.indexOf(`${woord} ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n}\n", start);
  return bron.slice(start, eind + 2);
}

const omgeving = { verstuurdeFouten: [], opslag: {}, waarneming: null };
const chrome = {
  scripting: { executeScript: async () => [{ result: omgeving.waarneming }] },
  storage: {
    local: {
      get: async (k) => (k in omgeving.opslag ? { [k]: omgeving.opslag[k] } : {}),
      set: async (o) => Object.assign(omgeving.opslag, o),
      remove: async (k) => { delete omgeving.opslag[k]; },
    },
  },
};
const bron = [
  `const reportError = async (j, s, tekst) => { omgeving.verstuurdeFouten.push(tekst); };
   const sluitWerkTabblad = () => {};
   const getAuthHeaders = async () => ({});
   const fetch = async () => ({ json: async () => ({ ok: true }) });`,
  BG.slice(BG.indexOf("const NIET_GESTART_PREFIX"), BG.indexOf("const SITE_NAAM")),
  BG.slice(BG.indexOf("const SITE_NAAM"), BG.indexOf("\n};", BG.indexOf("const SITE_NAAM")) + 3),
  functieUit(BG, "stopPlatformWachtrij", "async function"),
  functieUit(BG, "bekijkVastgelopenTabblad", "async function"),
  functieUit(BG, "meldNooitBegonnen", "async function"),
  "return meldNooitBegonnen;",
].join("\n");
const meldNooitBegonnen = new Function("chrome", "omgeving", bron)(chrome, omgeving);
const meta = { jobId: "6350e559", serverUrl: "https://omnivaleur.com", platform: "facebook", action: "create" };

(async () => {
  console.log("\nFacebook toont zijn limietpagina in plaats van het formulier");
  // Letterlijk wat de bewaker om 12:20 UTC in het tabblad zag.
  omgeving.waarneming = {
    url: "https://www.facebook.com/marketplace/np/create/limit_reached/",
    titel: "(4) Facebook", begin: "Aantal ongelezen meldingen\n4\nMarketplace\nNieuwe advertentie maken\nFilters\nParijs",
    stempel: null, velden: 8, wachtwoordveld: false,
  };
  await meldNooitBegonnen(1, meta);
  const t = omgeving.verstuurdeFouten[0] || "";
  check("de melding noemt de limiet van Facebook", /limit reached/i.test(t), t.slice(0, 120));
  check("en zegt dat Facebook die grens zet, niet wij", /Facebook sets that limit itself/.test(t));
  check("en vraagt de klant niet meer om de gegevens naar ons te sturen", !/send them to us/i.test(t));
  check("het gemeten adres blijft erbij staan", /limit_reached/.test(t));

  console.log("\nEen gewone Facebookpagina blijft de oude, voorzichtige melding geven");
  omgeving.waarneming = { ...omgeving.waarneming, url: "https://www.facebook.com/marketplace/create/item" };
  await meldNooitBegonnen(2, { ...meta, jobId: "j2" });
  const t2 = omgeving.verstuurdeFouten[1] || "";
  check("geen limiet genoemd waar Facebook er geen toonde", !/limit reached/i.test(t2), t2.slice(0, 120));

  console.log(mislukt ? `\n${mislukt} FOUT(EN)` : "\nAlles groen");
  process.exit(mislukt ? 1 : 0);
})();
