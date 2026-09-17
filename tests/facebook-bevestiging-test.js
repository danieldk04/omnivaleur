/**
 * Draait de ECHTE publicatieroutine uit extension/content/facebook.js tegen een
 * namaakpagina van Facebook, in de oude en de nieuwe versie naast elkaar.
 *
 * AANLEIDING 17-09-2026, Johan Kist. Acht keer "klaar" op Facebook, zonder
 * advertentienummer, en niemand kon zeggen of er iets op Marketplace stond. De
 * oude routine wachtte 15 seconden en meldde daarna ALTIJD "klaar", ook als
 * Facebook gewoon op het formulier bleef staan of de knop uitgeschakeld was.
 *
 * Draaien:  node tests/facebook-bevestiging-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
// Vastgezet op de laatste versie van vóór de reparatie. "HEAD" zou na de commit
// de nieuwe code zijn, en dan vergelijkt de proef zichzelf.
const VOOR_DE_REPARATIE = "48a9c4b9";

const NIEUW = fs.readFileSync(path.join(ROOT, "extension/content/facebook.js"), "utf8");
const OUD = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/facebook.js`, { cwd: ROOT }).toString();

function routineUit(bron) {
  const start = bron.indexOf("  async function publishAndCapture(");
  const eind = bron.indexOf("  // Best-effort delete.");
  if (start < 0 || eind < 0) throw new Error("publishAndCapture niet gevonden in facebook.js");
  return bron.slice(start, eind);
}

// Namaak-Facebook met een eigen klok: sleep() zet de klok vooruit en laat
// geplande gebeurtenissen (de doorverwijzing na Publiceren) op tijd gebeuren.
function maakPagina({ knopUit = false, naKlik = null, kaarten = [], alerts = [] }) {
  let nu = 1_000_000;
  const gepland = [];
  const location = { href: "https://www.facebook.com/marketplace/create/item" };
  const el = (props) => ({
    textContent: "", disabled: false, parentElement: null, _attr: {},
    getAttribute(n) { return this._attr[n] ?? null; },
    querySelectorAll() { return []; },
    click() {}, ...props,
  });
  const publiceer = el({ textContent: "Publiceren", _attr: knopUit ? { "aria-disabled": "true" } : {} });
  let geklikt = 0;
  publiceer.click = () => {
    geklikt++;
    if (!knopUit && naKlik) gepland.push({ om: nu + naKlik.naMs, doe: () => { location.href = naKlik.naar; } });
  };
  // Kaarten op "Jouw advertenties": kaart > link, allemaal in één lijst.
  const lijst = el({ textContent: "" });
  const links = [];
  for (const k of kaarten) {
    const link = el({ _attr: { href: `/marketplace/item/${k.id}` }, textContent: "" });
    const kaart = el({ textContent: k.titel, parentElement: lijst });
    link.parentElement = kaart;
    kaart.querySelectorAll = () => [link];
    links.push(link);
  }
  lijst.textContent = kaarten.map((k) => k.titel).join(" ");
  lijst.querySelectorAll = () => links;
  const document = {
    querySelectorAll(sel) {
      if (sel.includes('[role="button"]')) return [publiceer];
      if (sel.includes('a[href*="/marketplace/item/"]')) return /you\/selling/.test(location.href) ? links : [];
      if (sel.includes('[role="alert"]')) return alerts.map((t) => el({ textContent: t }));
      return [];
    },
  };
  const sleep = async (ms) => {
    nu += ms;
    for (const g of gepland.splice(0)) { if (g.om <= nu) g.doe(); else gepland.push(g); }
  };
  const FakeDate = { now: () => nu };
  return { document, location, sleep, FakeDate, geklikt: () => geklikt };
}

async function draai(bron, pagina, item) {
  const maak = new Function("document", "location", "sleep", "isVisible", "normApos", "Date",
    routineUit(bron) + "\n;return { publishAndCapture };");
  const { publishAndCapture } = maak(pagina.document, pagina.location, pagina.sleep, () => true,
    (s) => s.replace(/[‘’ʼ]/g, "'"), pagina.FakeDate);
  try {
    // Zo meldde de extensie het: alles wat terugkomt wordt JOB_DONE.
    return { gemeld: "JOB_DONE", ...(await publishAndCapture(item)) };
  } catch (e) {
    return { gemeld: "JOB_ERROR", fout: e.message };
  }
}

let mislukt = 0;
const ok = (naam, v, kreeg) => {
  if (v) return console.log(`  ✓ ${naam}`);
  mislukt++;
  console.log(`  ✗ ${naam} — kreeg ${JSON.stringify(kreeg)}`);
};
const ITEM = { title: "Martin D-28 Custom Ambertone 2003" };

(async () => {
  console.log("1. Facebook blijft na Publiceren op het formulier staan");
  const oud1 = await draai(OUD, maakPagina({}), ITEM);
  const nieuw1 = await draai(NIEUW, maakPagina({ alerts: ["Voeg een locatie toe"] }), ITEM);
  ok("oud: meldt toch 'klaar' zonder nummer (de fout)", oud1.gemeld === "JOB_DONE" && oud1.id === null, oud1);
  ok("nieuw: meldt een fout, met wat Facebook zegt", nieuw1.gemeld === "JOB_ERROR"
     && /did not confirm/.test(nieuw1.fout) && /Voeg een locatie toe/.test(nieuw1.fout), nieuw1);

  console.log("2. De knop Publiceren is uitgeschakeld (verplicht veld leeg)");
  const oud2 = await draai(OUD, maakPagina({ knopUit: true }), ITEM);
  const p2 = maakPagina({ knopUit: true });
  const nieuw2 = await draai(NIEUW, p2, ITEM);
  ok("oud: meldt toch 'klaar'", oud2.gemeld === "JOB_DONE", oud2);
  ok("nieuw: fout 'stayed disabled', en er is niet geklikt", nieuw2.gemeld === "JOB_ERROR"
     && /stayed disabled/.test(nieuw2.fout) && p2.geklikt() === 0, nieuw2);

  console.log("3. Facebook stuurt door naar Jouw advertenties, met de nieuwe advertentie als kaart");
  const kaarten = [{ id: "111", titel: "Gibson Hummingbird Sunburst Standard" },
                   { id: "222", titel: "Martin D-28 Custom Ambertone 2003" }];
  const naar = { naMs: 3000, naar: "https://www.facebook.com/marketplace/you/selling" };
  const oud3 = await draai(OUD, maakPagina({ naKlik: naar, kaarten }), ITEM);
  const nieuw3 = await draai(NIEUW, maakPagina({ naKlik: naar, kaarten }), ITEM);
  ok("oud: klaar maar zonder nummer", oud3.gemeld === "JOB_DONE" && oud3.id === null, oud3);
  ok("nieuw: klaar, bevestigd, en het nummer van DE JUISTE kaart (222, niet 111)",
     nieuw3.gemeld === "JOB_DONE" && nieuw3.id === "222" && nieuw3.bevestigd === "jouw-advertenties", nieuw3);

  console.log("4. Doorverwezen, maar de lijst toont (nog) geen link naar de advertentie");
  const nieuw4 = await draai(NIEUW, maakPagina({ naKlik: naar, kaarten: [] }), ITEM);
  ok("nieuw: klaar en bevestigd, zonder verzonnen nummer", nieuw4.gemeld === "JOB_DONE"
     && nieuw4.id === null && nieuw4.bevestigd === "jouw-advertenties"
     && /you\/selling/.test(nieuw4.url), nieuw4);

  console.log("5. Facebook opent direct de advertentiepagina");
  const nieuw5 = await draai(NIEUW, maakPagina({ naKlik: { naMs: 2000, naar: "https://www.facebook.com/marketplace/item/987654/" } }), ITEM);
  ok("nieuw: nummer 987654, bevestigd", nieuw5.id === "987654" && nieuw5.bevestigd === "advertentiepagina", nieuw5);

  console.log(mislukt ? `\n${mislukt} MISLUKT` : "\nalles groen");
  process.exit(mislukt ? 1 : 0);
})();
