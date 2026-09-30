/**
 * bgDeleteVinted draait hier ECHT; alleen de antwoorden uit het tabblad zijn nagebootst.
 *
 * Aanleiding (30-09-2026, De Juiste Toon): "vinted delete mislukt: Error: Frame
 * with ID 0 was removed." Advertentie 8791506164 stond om 13:03 in de kast, de
 * opdracht faalde om 13:44 met deze fout, en daarna gaf de pagina 404: de
 * verwijdering was gelukt. Vinted stuurt het tabblad door na de bevestigklik,
 * en dan breekt Chrome ons wachtende script af. De kast moet beslissen.
 *
 * Draaien:  node tests/vinted-verwijderen-frame-weg-test.js
 *           node tests/vinted-verwijderen-frame-weg-test.js --oud  (faalt, code van 976bce47)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show 976bce47:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const start = BG.indexOf("async function bgDeleteVinted(");
const bron = BG.slice(start, BG.indexOf("\n}\n", start) + 2);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

// `wegNa` = staat de advertentie na afloop niet meer in de kast.
// `eersteKastFrameWeg` = de eerste kastcontrole valt ook nog in de doorsturing.
async function ronde({ wegNa, eersteKastFrameWeg = false, fout = "Frame with ID 0 was removed." }) {
  const gemeld = [];
  let n = 0;
  const omgeving = {
    openWorkerTab: (url, cb) => cb({ id: 7 }),
    zetDoorlopendeKlok: async () => {},
    stuurWerkTabbladNaar: async () => {},
    vintedIngelogdOrigin: async () => null,
    _mwVintedKast: () => {},
    waitForTabLoad: async () => {},
    sluitWerkTabblad: () => {},
    _mwVintedVerwijderen: () => {},
    finaliseJob: async (_s, id, status, extra) => { gemeld.push({ id, status, extra }); },
    execInTab: async () => {
      n++;
      if (n === 1) return { userId: "51887752", present: true, closed: false };
      if (n === 2) return { photo_urls: ["a.jpg"], description: "tapijtje" };
      if (n === 3) throw new Error(fout);                                  // de bevestigklik
      if (n === 4 && eersteKastFrameWeg) throw new Error(fout);
      return wegNa ? false : true;                                         // kastcontroles en venstercheck
    },
    console,
  };
  const fn = new Function(...Object.keys(omgeving), `${bron}; return bgDeleteVinted;`)(...Object.values(omgeving));
  let f = null;
  try {
    await fn({ id: "0e158054", payload: { platform_listing_id: "8791506164",
      platform_listing_url: "https://www.vinted.nl/items/8791506164" } }, "https://s");
  } catch (e) { f = e.message; }
  return { fout: f, gemeld };
}

(async () => {
  console.log("\nVinted verwijderen: pagina verdwijnt tijdens de bevestigklik");

  let r = await ronde({ wegNa: true });
  ok("pagina weg tijdens klikken, advertentie uit de kast -> geslaagd",
     !r.fout && r.gemeld[0]?.status === "complete", r);
  ok("momentopname gaat mee", r.gemeld[0]?.extra?.captured_listing?.description === "tapijtje", r.gemeld[0]);

  r = await ronde({ wegNa: true, eersteKastFrameWeg: true });
  ok("ook de eerste kastcontrole valt in de doorsturing -> opnieuw kijken, geslaagd",
     !r.fout && r.gemeld[0]?.status === "complete", r);

  r = await ronde({ wegNa: false });
  ok("pagina weg maar advertentie staat er nog -> fout, niet als geslaagd afmelden",
     /still in your wardrobe/.test(r.fout || "") && r.gemeld.length === 0, r);

  r = await ronde({ wegNa: true, fout: "No tab with id: 7." });
  ok("andere fout (tabblad dicht) blijft een fout",
     /No tab with id/.test(r.fout || "") && r.gemeld.length === 0, r);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
