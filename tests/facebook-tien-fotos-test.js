/**
 * FACEBOOK NEEMT ER MAXIMAAL TIEN.
 *
 * GEMETEN 20-09-2026 op het echte Facebook-formulier (NL, Daniels eigen
 * account), met de echte code van de extensie erin gedraaid:
 *
 *   19 foto's aangeboden → "Foto's · 19 / 10 — je kunt maximaal 10 foto's
 *   toevoegen", waarschuwing "Je kunt maximaal 10 foto's selecteren", en de knop
 *   Volgende bleef UITGESCHAKELD. Er verschijnt dan nooit een knop Publiceren.
 *   10 foto's aangeboden → "Foto's · 10 / 10", geen klacht, formulier gewoon
 *   in te vullen, Volgende gaat aan.
 *
 * Wij boden er tot twintig aan (`slice(0, 20)`). Van de 25 mislukte plaatsingen
 * bij Blackbird Guitars hadden er 19 meer dan tien foto's.
 *
 * Deze proef draait de ECHTE fillForm uit extension/content/facebook.js en telt
 * hoeveel foto's hij aanbiedt, met de versie van vóór de reparatie ernaast.
 *
 * Draaien:  node tests/facebook-tien-fotos-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "9bf3c6ed";

const NIEUW = fs.readFileSync(path.join(WORTEL, "extension/content/facebook.js"), "utf8");
const OUD = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/facebook.js`, { cwd: WORTEL }).toString();

function vulroutineUit(bron) {
  const start = bron.indexOf("  const FB_MAX_FOTOS");
  const vanaf = start >= 0 ? start : bron.indexOf("  async function fillForm(");
  const eind = bron.indexOf("  // Click through FB's \"Next\" → \"Publish\"");
  if (vanaf < 0 || eind < 0) throw new Error("fillForm niet gevonden in facebook.js");
  return bron.slice(vanaf, eind);
}

let mislukt = 0;
const ok = (naam, v, kreeg) => {
  if (v) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam} — kreeg ${JSON.stringify(kreeg)}`);
};

async function draai(bron, { fotos, klachtNaUpload = "" }) {
  const aangeboden = [];
  const stubs = {
    document: { querySelectorAll: () => [] },
    sleep: async () => {},
    waitForEl: async () => ({}),
    uploadPhotos: async (urls) => { aangeboden.push(urls.length); return urls.length; },
    klachtenFb: () => klachtNaUpload,
    findField: () => ({ value: "", focus() {} }),
    typeInto: async () => true,
    smartTrunc: (s, n) => String(s || "").slice(0, n),
    platteTekst: (s) => String(s || ""),
    formatPrice: (p) => String(Math.round(Number(p))),
    selectCombo: async () => true,
    fbCategoryCandidates: () => ["Overig"],
    CONDITION_MAP: { good: ["Gebruikt - in goede staat"] },
    FB_PHOTO_THUMBS: "img",
  };
  const namen = Object.keys(stubs);
  const maak = new Function(...namen, vulroutineUit(bron) + "\n;return fillForm;");
  const fillForm = maak(...namen.map((n) => stubs[n]));
  const item = { title: "Eastman Parlor", price: 549, condition: "good",
                 description: "gitaar", photo_urls: Array.from({ length: fotos }, (_, i) => `foto${i}.jpg`) };
  try {
    await fillForm(item);
    return { aangeboden: aangeboden[0], fout: null };
  } catch (e) {
    return { aangeboden: aangeboden[0], fout: e.message };
  }
}

(async () => {
  console.log("\n1. EEN ARTIKEL MET 19 FOTO'S (zoals bij Blackbird Guitars)");
  {
    const oud = await draai(OUD, { fotos: 19 });
    ok("oud: biedt er 19 aan — Facebook weigert de hele set", oud.aangeboden === 19, oud);
    const nieuw = await draai(NIEUW, { fotos: 19 });
    ok("nieuw: biedt er precies 10 aan", nieuw.aangeboden === 10, nieuw);
    ok("nieuw: en gaat gewoon door met invullen", nieuw.fout === null, nieuw);
  }

  console.log("\n2. TWINTIG FOTO'S, DE OUDE BOVENGRENS");
  {
    const oud = await draai(OUD, { fotos: 25 });
    ok("oud: kapte af op 20, ruim boven de grens van Facebook", oud.aangeboden === 20, oud);
    const nieuw = await draai(NIEUW, { fotos: 25 });
    ok("nieuw: kapt af op 10", nieuw.aangeboden === 10, nieuw);
  }

  console.log("\n3. MINDER DAN TIEN BLIJFT ONGEMOEID");
  {
    const nieuw = await draai(NIEUW, { fotos: 7 });
    ok("nieuw: biedt alle 7 aan", nieuw.aangeboden === 7, nieuw);
  }

  console.log("\n4. FACEBOOK KLAAGT ALSNOG OVER HET AANTAL FOTO'S");
  {
    const klacht = " (Facebook says: Je kunt maximaal 10 foto's selecteren.)";
    const nieuw = await draai(NIEUW, { fotos: 10, klachtNaUpload: klacht });
    ok("nieuw: stopt meteen, met de reden die Facebook zelf geeft",
       !!nieuw.fout && /maximaal 10 foto/.test(nieuw.fout) && /Nothing was published/.test(nieuw.fout), nieuw.fout);
    const oud = await draai(OUD, { fotos: 10, klachtNaUpload: klacht });
    ok("oud: liep gewoon door naar een knop die nooit aan zou gaan", oud.fout === null, oud);
  }

  console.log("\n5. GITAREN HOREN NIET IN 'OVERIG'");
  {
    const rubriekUit = (bron) => {
      const start = bron.indexOf("  function fbCategoryCandidates(item)");
      const eind = bron.indexOf("  async function fillForm(");
      return new Function(bron.slice(start, eind) + "\n;return fbCategoryCandidates;")();
    };
    const gitaar = { category: "muziek snaarinstrumenten gitaren akoestisch", gender: "muziek", title: "Eastman Parlor" };
    const versterker = { category: "muziek versterkers bas en gitaar", gender: "muziek", title: "Positive Grid" };
    const oud = rubriekUit(OUD)(gitaar);
    const nieuw = rubriekUit(NIEUW)(gitaar);
    ok("oud: elke gitaar belandde in 'Overig'", oud[0] === "Overig", oud);
    ok("nieuw: gitaar gaat naar Muziekinstrumenten", nieuw[0] === "Muziekinstrumenten", nieuw);
    ok("nieuw: versterker ook", rubriekUit(NIEUW)(versterker)[0] === "Muziekinstrumenten", rubriekUit(NIEUW)(versterker));
    ok("nieuw: 'Overig' blijft als terugval in de lijst", nieuw.includes("Overig"), nieuw);
    const jurk = { category: "dames jurken", gender: "dames", title: "Zomerjurk" };
    ok("nieuw: kleding blijft ongemoeid", /Dameskleding/.test(rubriekUit(NIEUW)(jurk)[0]), rubriekUit(NIEUW)(jurk));
  }

  console.log(mislukt ? `\n${mislukt} MISLUKT\n` : "\nalles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
