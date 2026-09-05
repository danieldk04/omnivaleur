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
async function ronde({ knopGevonden, wegNa }) {
  const uitgevoerd = [];
  const gemeld = [];
  const omgeving = {
    openWorkerTab: (url, cb) => cb({ id: 7 }),
    waitForTabLoad: async () => {},
    sluitWerkTabblad: () => {},
    _mwVintedVerwijderen: () => {},
    finaliseJob: async (_s, id, status, extra) => { gemeld.push({ id, status, extra }); },
    execInTab: async (tabId, fn) => {
      uitgevoerd.push(fn);
      const n = uitgevoerd.length;
      if (n === 1) return { userId: "12345", present: true, closed: false };   // stond er nog
      if (n === 2) return { photo_urls: ["a.jpg"], description: "tekst" };      // momentopname
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

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
