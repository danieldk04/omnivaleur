/**
 * bgDeleteVinted draait hier ECHT, met nagebootste antwoorden uit het tabblad.
 *
 * Aanleiding (05-09-2026): een herplaatsing meldde "Delete control not found on
 * Vinted item page for ID 7606902151", terwijl die advertentie daarna
 * aantoonbaar weg was — https://www.vinted.nl/items/7606902151 en .com geven
 * allebei 404. Aan het begin van diezelfde ronde stond hij nog in de kast,
 * anders was de melding "not in your wardrobe" geweest. De knop is dus geen
 * bewijs; de kast wel.
 *
 * Draaien:  node tests/vinted-verwijderen-knop-vs-kast-test.js
 *           node tests/vinted-verwijderen-knop-vs-kast-test.js --oud  (faalt)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const start = BG.indexOf("async function bgDeleteVinted(");
const bron = BG.slice(start, BG.indexOf("\n}\n", start) + 2);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

// Eén ronde spelen. `knopGevonden` = vond de code de verwijderknop,
// `wegNa` = staat de advertentie na afloop nog in de kast.
async function ronde({ knopGevonden, wegNa, eerste, kast, anderOrigin = null }) {
  const kastAntwoorden = Array.isArray(kast) ? kast.slice() : [kast];
  const eersteAntwoord = eerste || { userId: "12345", present: true, closed: false };  // stond er nog
  const uitgevoerd = [];
  const gemeld = [];
  const omgeving = {
    openWorkerTab: (url, cb) => cb({ id: 7 }),
    stuurWerkTabbladNaar: async () => {},
    vintedIngelogdOrigin: async () => anderOrigin,
    _mwVintedKast: () => {},
    waitForTabLoad: async () => {},
    sluitWerkTabblad: () => {},
    _mwVintedVerwijderen: () => {},
    finaliseJob: async (_s, id, status, extra) => { gemeld.push({ id, status, extra }); },
    execInTab: async (tabId, fn) => {
      uitgevoerd.push(fn);
      const n = uitgevoerd.length;
      if (n === 1) return eersteAntwoord;
      if (eersteAntwoord.httpStatus === 404) return kastAntwoorden.shift();
      if (n === 2) return { photo_urls: ["a.jpg"], description: "tekst" };
      if (n === 3) return knopGevonden                                          // de verwijderpoging
        ? { clickedDelete: true, clickedConfirm: true, venster: true }
        : { clickedDelete: false, opScherm: "menu | delen" };
      return wegNa ? false : true;                                              // kastcontroles
    },
    console,
  };
  const fabriek = new Function(...Object.keys(omgeving), `${bron}; return bgDeleteVinted;`);
  const fn = fabriek(...Object.values(omgeving));
  let fout = null;
  try {
    await fn({ id: "job1", payload: { platform_listing_id: "7606902151", platform_listing_url: "https://www.vinted.nl/items/7606902151" } }, "https://s");
  } catch (e) { fout = e.message; }
  return { fout, gemeld };
}

(async () => {
  console.log("\nVinted verwijderen: telt de knop of de kast?");

  let r = await ronde({ knopGevonden: false, wegNa: true });
  ok("knop niet gevonden maar advertentie is wél weg -> geslaagd, geen fout",
     !r.fout && r.gemeld[0]?.status === "complete", r);
  ok("de momentopname gaat gewoon mee naar de herplaatsing",
     r.gemeld[0]?.extra?.captured_listing?.description === "tekst", r.gemeld[0]);

  r = await ronde({ knopGevonden: false, wegNa: false });
  ok("knop niet gevonden en advertentie staat er nog -> wél de knopfout",
     /Delete control not found/.test(r.fout || ""), r.fout);

  r = await ronde({ knopGevonden: true, wegNa: false });
  ok("geklikt maar advertentie staat er nog -> niet als geslaagd afmelden",
     /still in your wardrobe/.test(r.fout || "") && r.gemeld.length === 0, r.fout);

  r = await ronde({ knopGevonden: true, wegNa: true });
  ok("gewoon gelukt blijft gelukt", !r.fout && r.gemeld[0]?.status === "complete", r);

  console.log("\nAdvertentiepagina bestaat niet meer (404)");
  const WEG = { userId: null, httpStatus: 404 };

  r = await ronde({ eerste: WEG, kast: { userId: "12345", present: false } });
  ok("weg én niet in de kast -> als 'al weg' afgemeld, herplaatsing loopt door",
     !r.fout && r.gemeld[0]?.status === "complete" && r.gemeld[0]?.extra?.note === "already_absent", r);

  r = await ronde({ eerste: WEG, kast: { userId: "12345", present: true, closed: true } });
  ok("weg maar in de kast als verkocht -> verkoop melden, niet herplaatsen",
     !r.fout && r.gemeld[0]?.extra?.sold_on_platform === true, r);

  r = await ronde({ eerste: WEG, kast: { userId: null, present: null } });
  ok("echt uitgelogd -> dan pas de inlogmelding",
     /member id/.test(r.fout || "") && r.gemeld.length === 0, r.fout);

  r = await ronde({ eerste: WEG, kast: { userId: "12345", present: null } });
  ok("kast onleesbaar -> niets aannemen, geen afmelding",
     /Could not read your Vinted wardrobe/.test(r.fout || "") && r.gemeld.length === 0, r.fout);

  r = await ronde({
    eerste: WEG,
    kast: [{ userId: null, present: null }, { userId: "12345", present: false }],
    anderOrigin: "https://www.vinted.com",
  });
  ok("geen sessie op vinted.nl maar wel op .com -> daar kijken, dan pas oordelen",
     !r.fout && r.gemeld[0]?.extra?.note === "already_absent", r);

  r = await ronde({ eerste: { userId: "12345", present: false, httpStatus: 404 } });
  ok("lidnummer bekend, kast leeg, pagina weg -> 'al weg', herplaatsing loopt door",
     !r.fout && r.gemeld[0]?.extra?.note === "already_absent", r);

  r = await ronde({ eerste: { userId: "12345", present: false, httpStatus: 200 } });
  ok("kast leeg maar de advertentie bestaat wél -> afblijven, foutmelding",
     /not in your wardrobe/.test(r.fout || "") && r.gemeld.length === 0, r.fout);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
