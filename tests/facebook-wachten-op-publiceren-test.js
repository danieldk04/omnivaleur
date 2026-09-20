/**
 * FACEBOOK: EERST WACHTEN, DAN PAS OPGEVEN — EN ZEGGEN WAT ER STOND.
 *
 * AANLEIDING 20-09-2026, Blackbird Guitars (proefklant). 25 pogingen op rij
 * eindigden met exact dezelfde zin: "its Publish button stayed disabled, which
 * means a required field is still empty". Nul advertenties op Facebook. Die zin
 * was een gok: Facebook zelf klaagde nergens ([role="alert"] leverde niets op),
 * en niemand kon zien wélk veld leeg zou zijn, of dat het ergens anders aan lag.
 *
 * Twee dingen zaten fout in de oude routine:
 *   1. Er werd ÉÉN keer gekeken of Publiceren aanklikbaar was. Facebook houdt
 *      die knop óók uitgeschakeld zolang het de zojuist geüploade foto's nog
 *      verwerkt, en de uploadstap wacht maar op het eerste miniatuur. Bij 7 tot
 *      19 foto's (de normale maat bij deze verkoper) is dat seconden later.
 *   2. De fout droeg geen enkel spoor van de stand van het formulier, dus elke
 *      mislukking zag er identiek uit.
 *
 * Deze proef draait de ECHTE publicatieroutine uit extension/content/facebook.js
 * tegen een namaak-Facebook met een eigen klok, en dezelfde proef tegen de
 * versie van vóór de reparatie.
 *
 * findField/fieldNameCandidates zijn hier vereenvoudigd nagebouwd: die code is
 * niet veranderd en staat buiten het stuk dat deze proef uitsnijdt.
 *
 * Draaien:  node tests/facebook-wachten-op-publiceren-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// Vastgezet op de laatste versie van vóór de reparatie, nooit HEAD: na de commit
// zou de proef zichzelf met zichzelf vergelijken.
const VOOR_DE_REPARATIE = "9bf3c6ed";

const NIEUW = fs.readFileSync(path.join(WORTEL, "extension/content/facebook.js"), "utf8");
const OUD = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/facebook.js`, { cwd: WORTEL }).toString();

function routineUit(bron) {
  const start = bron.indexOf("  async function publishAndCapture(");
  const eind = bron.indexOf("  // Best-effort delete.");
  if (start < 0 || eind < 0) throw new Error("publishAndCapture niet gevonden in facebook.js");
  return bron.slice(start, eind);
}

const FOTO_SEL = 'img[alt="Advertentiefoto"], img[src*="fbcdn.net"]';

/**
 * Namaak-Facebook. `knopUitMs` is hoe lang Facebook de knop Publiceren
 * uitgeschakeld houdt (het verwerken van de foto's); `Infinity` = nooit
 * aanklikbaar.
 */
function maakPagina({ knopUitMs = 0, kaarten = [], velden = {}, fotos = 0 } = {}) {
  let nu = 1_000_000;
  const start = nu;
  const gepland = [];
  const location = { href: "https://www.facebook.com/marketplace/create/item" };
  let geklikt = 0;

  const el = (props) => ({
    textContent: "", disabled: false, value: "", _attr: {},
    getAttribute(n) { return this._attr[n] ?? null; },
    querySelectorAll() { return []; },
    getClientRects: () => [{ width: 10, height: 10 }],
    click() {}, ...props,
  });

  const publiceer = el({ textContent: "Publiceren" });
  publiceer.getAttribute = function (n) {
    if (n === "aria-disabled") return (nu - start) < knopUitMs ? "true" : null;
    return this._attr[n] ?? null;
  };
  publiceer.click = () => {
    geklikt++;
    if ((nu - start) >= knopUitMs) {
      gepland.push({ om: nu + 2000, doe: () => { location.href = "https://www.facebook.com/marketplace/you/selling"; } });
    }
  };

  // Kaarten op "Jouw advertenties": kaart > link.
  const lijst = el({});
  const links = [];
  for (const k of kaarten) {
    const link = el({ _attr: { href: `/marketplace/item/${k.id}` } });
    const kaart = el({ textContent: k.titel, parentElement: lijst });
    link.parentElement = kaart;
    kaart.querySelectorAll = () => [link];
    links.push(link);
  }
  lijst.textContent = kaarten.map((k) => k.titel).join(" ");
  lijst.querySelectorAll = () => links;

  // Formuliervelden zoals ze op het scherm staan.
  const tekstvelden = Object.entries(velden.tekst || {}).map(([label, waarde]) =>
    el({ _attr: { "aria-label": label }, value: waarde }));
  const combos = Object.entries(velden.keuze || {}).map(([label, waarde]) =>
    el({ _attr: { "aria-label": label, role: "combobox" }, textContent: waarde }));
  const fotoElementen = Array.from({ length: fotos }, () => el({}));

  const document = {
    querySelectorAll(sel) {
      if (sel.includes("img[alt=")) return fotoElementen;
      if (sel.includes("combobox")) return combos;
      if (sel.includes('[role="alert"]')) return [];
      if (sel.includes('a[href*="/marketplace/item/"]')) return /you\/selling/.test(location.href) ? links : [];
      if (sel.includes("textarea") || sel.includes("textbox")) return tekstvelden;
      if (sel.includes('[role="button"]')) return [publiceer];
      return [];
    },
  };
  const sleep = async (ms) => {
    nu += ms;
    for (const g of gepland.splice(0)) { if (g.om <= nu) g.doe(); else gepland.push(g); }
  };
  return { document, location, sleep, FakeDate: { now: () => nu }, geklikt: () => geklikt,
           verstreken: () => nu - start };
}

async function draai(bron, pagina, item) {
  const findField = (re) => pagina.document.querySelectorAll('input[type="text"], textarea')
    .find((f) => re.test(String(f.getAttribute("aria-label") || "")));
  const fieldNameCandidates = (e) => [e.getAttribute("aria-label")];
  const maak = new Function("document", "location", "sleep", "isVisible", "normApos", "Date",
    "findField", "fieldNameCandidates", "FB_PHOTO_THUMBS",
    routineUit(bron) + "\n;return { publishAndCapture };");
  const { publishAndCapture } = maak(pagina.document, pagina.location, pagina.sleep, () => true,
    (s) => s.replace(/[‘’ʼ]/g, "'"), pagina.FakeDate, findField, fieldNameCandidates, FOTO_SEL);
  try {
    return { gemeld: "JOB_DONE", ...(await publishAndCapture(item)) };
  } catch (e) {
    return { gemeld: "JOB_ERROR", fout: e.message };
  }
}

let mislukt = 0;
const ok = (naam, v, kreeg) => {
  if (v) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam} — kreeg ${JSON.stringify(kreeg)}`);
};
const ITEM = { title: "Eastman Parlor" };
const VELDEN = {
  tekst: { Titel: "Eastman Parlor", Prijs: "549", Beschrijving: "Prachtige parlor gitaar" },
  keuze: { Categorie: "Overig", Staat: "Nieuw" },
};

(async () => {
  console.log("\n1. FACEBOOK VERWERKT DE FOTO'S NOG (knop 8 seconden uitgeschakeld)");
  {
    const a = maakPagina({ knopUitMs: 8000, kaarten: [{ id: "555", titel: "Eastman Parlor" }] });
    const oud = await draai(OUD, a, ITEM);
    ok("oud: geeft meteen op met 'stayed disabled'",
       oud.gemeld === "JOB_ERROR" && /stayed disabled/.test(oud.fout), oud);
    ok("oud: heeft de knop nooit aangeraakt", a.geklikt() === 0, a.geklikt());

    const b = maakPagina({ knopUitMs: 8000, kaarten: [{ id: "555", titel: "Eastman Parlor" }] });
    const nieuw = await draai(NIEUW, b, ITEM);
    ok("nieuw: wacht tot de knop aan gaat en publiceert alsnog",
       nieuw.gemeld === "JOB_DONE" && nieuw.id === "555", nieuw);
    ok("nieuw: bevestigd door Facebook zelf", nieuw.bevestigd === "jouw-advertenties", nieuw);
  }

  console.log("\n2. DE KNOP BLIJFT UIT (er is echt iets mis)");
  {
    const a = maakPagina({ knopUitMs: Infinity, velden: VELDEN, fotos: 9 });
    const nieuw = await draai(NIEUW, a, ITEM);
    ok("nieuw: meldt nog steeds een fout, niets gepubliceerd",
       nieuw.gemeld === "JOB_ERROR" && a.geklikt() === 0, nieuw);
    ok("nieuw: wacht daar wel 30 seconden op", a.verstreken() >= 30000, a.verstreken());
    ok("nieuw: de fout draagt de stand van het formulier mee",
       /titel="Eastman Parlor"/.test(nieuw.fout) && /prijs="549"/.test(nieuw.fout), nieuw.fout);
    ok("nieuw: inclusief categorie, staat en het aantal foto's",
       /categorie="Overig"/.test(nieuw.fout) && /staat="Nieuw"/.test(nieuw.fout)
       && /foto's op het formulier: 9/.test(nieuw.fout), nieuw.fout);

    const b = maakPagina({ knopUitMs: Infinity, velden: VELDEN, fotos: 9 });
    const oud = await draai(OUD, b, ITEM);
    ok("oud: dezelfde nietszeggende zin, zonder één meetbaar gegeven",
       /required field is still empty/.test(oud.fout) && !/formulier:/.test(oud.fout), oud.fout);
  }

  console.log("\n3. EEN LEEG VELD IS NU AANWIJSBAAR");
  {
    const leeg = { tekst: { Titel: "Eastman Parlor", Prijs: "", Beschrijving: "" }, keuze: { Categorie: "", Staat: "Nieuw" } };
    const a = maakPagina({ knopUitMs: Infinity, velden: leeg, fotos: 0 });
    const nieuw = await draai(NIEUW, a, ITEM);
    ok("nieuw: noemt prijs en categorie met zoveel woorden LEEG",
       /prijs=LEEG/.test(nieuw.fout) && /categorie="LEEG"/.test(nieuw.fout), nieuw.fout);
    ok("nieuw: en meldt dat er nul foto's op het formulier staan",
       /foto's op het formulier: 0/.test(nieuw.fout), nieuw.fout);
  }

  console.log(mislukt ? `\n${mislukt} MISLUKT\n` : "\nalles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
