/**
 * Het verwijder-tabblad van Vinted moet met een vaste klok open.
 *
 * Aanleiding (Daniel, 21-09-2026, artikel 795 "Khaki Ralph Lauren Zip Vest").
 * Het artikel was verkocht op Marktplaats en werd van 2dehands afgehaald, maar
 * bleef op Vinted staan met de melding "Delete control not found ... Zichtbaar
 * op het scherm: skip to content | #header-logo-id | ... | #favourite-button".
 * Dat is precies het knoppenlijstje van een artikelpagina zoals een BEZOEKER
 * hem ziet, dus de pagina was er wel maar de knoppen van de eigenaar niet.
 *
 * Aan de opmaak van Vinted ligt het niet: hun eigen bestanden dragen
 * `item-delete-button` en `item-delete-confirmation-button` nog gewoon
 * (nagekeken 21-09-2026 op www.vinted.nl), en onze zoeker matcht daarop.
 *
 * Wat er wel scheelde: elke andere schrijvende klus opent zijn tabblad met
 * `klokVast` en krijgt daarmee Emulation.setFocusEmulationEnabled. Zonder dat
 * valt een achtergrond-tabblad terug naar 0,0 tikken per seconde na anderhalve
 * minuut (gemeten in tests/klok-varianten-echt-test.mjs). Alleen het Vinted-
 * verwijderen opende zijn tabblad kaal.
 *
 * Draaien:  node tests/vinted-verwijderklok-test.js
 *           node tests/vinted-verwijderklok-test.js --oud   (hoort te falen)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// Vast commit-nummer, geen HEAD: na het committen van deze reparatie zou HEAD
// de nieuwe code zijn en vergeleek de proef zich met zichzelf.
const VOOR = "2cdf26a4";
const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync(`git show ${VOOR}:extension/background.js`, { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const start = BG.indexOf("async function bgDeleteVinted(");
const bron = BG.slice(start, BG.indexOf("\n}\n", start) + 2);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

// Eén echte ronde, met een klik die faalt zodat de tweede route ook langskomt.
async function ronde({ koekje }) {
  const geopendMet = [];
  const klokAan = [];
  const verzonden = [];
  let tweedeRoute = null;

  const nepDocument = {
    cookie: koekje || "",
    querySelector: (sel) => (sel.includes("csrf-token") ? null : null),
  };
  const nepFetch = async (adres, opties) => {
    verzonden.push({ adres, kop: (opties && opties.headers) || {} });
    return { status: 403, ok: false };
  };

  const omgeving = {
    openWorkerTab: (url, cb, opts) => { geopendMet.push(opts || {}); cb({ id: 7 }); },
    zetDoorlopendeKlok: async (tabId, url, altijd) => { klokAan.push({ tabId, altijd }); },
    stuurWerkTabbladNaar: async () => {},
    vintedIngelogdOrigin: async () => null,
    _mwVintedKast: () => {},
    waitForTabLoad: async () => {},
    sluitWerkTabblad: () => {},
    _mwVintedVerwijderen: () => {},
    finaliseJob: async () => {},
    execInTab: async (tabId, fn, args) => {
      const n = ++omgeving._n;
      if (n === 1) return { userId: "12345", present: true, closed: false };
      if (n === 2) return { photo_urls: ["a.jpg"], description: "tekst" };
      if (n === 3) return { clickedDelete: false, opScherm: "kopregel | hartje" };
      if (n === 4) {
        // Dit is de tweede route: echt uitvoeren, met een nagebootste pagina.
        const bewaard = [global.document, global.fetch, global.self];
        global.document = nepDocument; global.fetch = nepFetch; global.self = {};
        try { tweedeRoute = await fn(...(args || [])); }
        finally { [global.document, global.fetch, global.self] = bewaard; }
        return tweedeRoute;
      }
      return true;  // staat nog in de kast
    },
    _n: 0,
    console: { log: () => {}, warn: () => {}, error: () => {} },
  };
  const fabriek = new Function(...Object.keys(omgeving), `${bron}; return bgDeleteVinted;`);
  const fn = fabriek(...Object.values(omgeving));
  let fout = null;
  try {
    await fn({ id: "job1", payload: {
      platform_listing_id: "7798044269",
      platform_listing_url: "https://www.vinted.nl/items/7798044269-795-khaki",
    } }, "https://s");
  } catch (e) { fout = e.message; }
  return { fout, geopendMet, klokAan, verzonden, tweedeRoute };
}

(async () => {
  console.log(OUD ? "OUDE CODE (hoort te falen)" : "NIEUWE CODE");

  console.log("\n1. Het tabblad gaat open met een vaste klok");
  const a = await ronde({ koekje: "anon_id=xyz; _csrf_token=abc123def456" });
  ok("openWorkerTab krijgt klokVast mee", a.geopendMet[0] && a.geopendMet[0].klokVast === true, a.geopendMet[0]);
  ok("de klok wordt na het laden ook echt vastgezet", a.klokAan.some(k => k.altijd === true), a.klokAan);

  console.log("\n2. De tweede route stuurt een beveiligingstoken mee");
  const kop = (a.verzonden[0] || {}).kop || {};
  ok("er is een POST naar het verwijder-adres gegaan",
     (a.verzonden[0] || {}).adres === "/api/v2/items/7798044269/delete", (a.verzonden[0] || {}).adres);
  ok("met een X-CSRF-Token uit het koekje", kop["X-CSRF-Token"] === "abc123def456", kop["X-CSRF-Token"]);
  ok("en met het anon-nummer erbij", kop["X-Anon-Id"] === "xyz", kop["X-Anon-Id"]);

  console.log("\n3. De melding vertelt waar het token vandaan kwam");
  ok("de fout noemt de bron van het token", /token uit koekje:_csrf_token/.test(a.fout || ""), a.fout);
  ok("de fout noemt de gevonden koekjes", /koekjes: /.test(a.fout || ""), a.fout);

  console.log("\n4. Geen enkel koekje: dan zegt de melding dat ook");
  const b = await ronde({ koekje: "" });
  ok("geen token gevonden wordt met zoveel woorden gemeld",
     /token uit geen \(geen koekjes met een token\)/.test(b.fout || ""), b.fout);

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
  process.exit(mislukt ? 1 : 0);
})();
