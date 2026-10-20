/**
 * Een Vinted-prijswijziging die wél lukte, maar als "timed out" werd geboekt.
 *
 * 20-10-2026: sinds augustus 42 Vinted-prijswijzigingen, alle 42 mislukt met
 * "timed out" en als laatste stap "prijs gezet via de pagina zelf". Klant
 * 8f91a370 (broek 10424476795, doel 29,97): de openbare Vinted-pagina toonde
 * daarna gewoon 29,97. De bewaker draait hier ECHT, met een nagebootste chrome
 * en een fetch die het echte Product-blok van die pagina teruggeeft.
 *
 * Draaien:  node tests/vinted-prijs-nagekeken-test.js
 *           BG=/pad/naar/oude/background.js node tests/vinted-prijs-nagekeken-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(process.env.BG || path.join(__dirname, "..", "extension", "background.js"), "utf8");

const stuk = (naam) => {
  const start = BG.indexOf(`async function ${naam}(`) >= 0
    ? BG.indexOf(`async function ${naam}(`) : BG.indexOf(`function ${naam}(`);
  if (start < 0) return "";
  let i = BG.indexOf("{", BG.indexOf(")", start)), diep = 0;
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diep++;
    else if (BG[i] === "}") { diep--; if (diep === 0) return BG.slice(start, i + 1); }
  }
  throw new Error(`${naam} loopt niet af`);
};

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — " + JSON.stringify(extra) : ""}`);
};

// Het Product-blok zoals vinted.nl/items/10424476795 het op 20-10-2026 gaf
// (omschrijving ingekort).
const pagina = (prijs, nummer = "10424476795") => `<html><head>
<script type="application/ld+json">{"@type":"Product","name":"Nieuwe heren outdoorbroek / cargo wandelbroek – groen/bruin","description":"Helemaal nieuwe heren outdoorbroek","offers":{"@type":"Offer","url":"https://www.vinted.nl/items/${nummer}-nieuwe-heren-outdoorbroek-cargo-wandelbroek-groenbruin","priceCurrency":"EUR","price":${prijs},"availability":"InStock","itemCondition":"NewCondition"}}</script>
</head><body></body></html>`;

async function bewaker({ meta, html, status = 200 }) {
  const opslag = { jobtab_7: meta };
  const gemeld = [];
  const fouten = [];
  const gevraagd = [];
  const omgeving = {
    chrome: {
      storage: { local: {
        get: async (k) => ({ [k]: opslag[k] }),
        set: async (o) => Object.assign(opslag, o),
        remove: async (k) => { for (const x of [].concat(k)) delete opslag[x]; },
      } },
      alarms: { create() {}, clear() {} },
    },
    console: { log() {}, warn() {}, error() {} },
    fetch: async (u) => { gevraagd.push(u); return { ok: status === 200, status, text: async () => html }; },
    VINTED_ORIGINS: ["https://www.vinted.nl"],
    JOB_TAB_TIMEOUT_MIN: 3,
    JOB_WATCHDOG_PREFIX: "jobwd_",
    MANUELE_CONTROLES_MAX: 15,
    MP_LOGINPAGINA: /x^/, MP_BETAALPAGINA: /x^/,
    betaalmuurRaaktDezeOpdracht: () => false,
    bekijkVastgelopenTabblad: async () => null,
    bgVindVintedAdvertentie: async () => null,
    finaliseJob: async (_s, id, st, extra) => { gemeld.push({ id, st, extra }); },
    reportError: async (id, _s, tekst) => { fouten.push(tekst); },
    meldNooitBegonnen: async () => {},
    sluitWerkTabblad: () => {},
    ontkoppelVroeg: () => {},
  };
  const fn = new Function(...Object.keys(omgeving),
    `${stuk("bgVintedPrijsOpPagina")}\n${stuk("fireJobWatchdog")}; return fireJobWatchdog;`)(...Object.values(omgeving));
  await fn(7);
  return { gemeld, fouten, gevraagd };
}

const META = {
  platform: "vinted", action: "content_refresh", jobId: "27ebed46", serverUrl: "https://s",
  scriptSeen: true, laatsteStap: "prijs gezet via de pagina zelf: 29,97", laatsteStapAt: 0,
  payload: {
    _price_update: true, price: 29.97, platform_listing_id: "10424476795",
    platform_listing_url: "https://www.vinted.nl/items/10424476795-nieuwe-heren-outdoorbroek-cargo-wandelbroek-groenbruin",
  },
};

(async () => {
  console.log("\nVinted-prijswijziging na de time-out nakijken");

  let r = await bewaker({ meta: META, html: pagina(29.97) });
  ok("nieuwe prijs staat op Vinted -> als gelukt afgemeld, geen foutmelding",
     r.gemeld[0]?.st === "complete" && r.fouten.length === 0, r);
  ok("gekeken op de pagina van precies deze advertentie",
     r.gevraagd[0] === "https://www.vinted.nl/items/10424476795", r.gevraagd);

  r = await bewaker({ meta: META, html: pagina(35) });
  ok("Vinted toont nog de oude prijs -> blijft een mislukking", r.gemeld.length === 0 && r.fouten.length === 1, r);

  r = await bewaker({ meta: META, html: pagina(29.97, "999") });
  ok("Product-blok van een andere advertentie telt niet", r.gemeld.length === 0 && r.fouten.length === 1, r);

  r = await bewaker({ meta: META, html: "", status: 403 });
  ok("pagina niet te lezen -> blijft een mislukking", r.gemeld.length === 0 && r.fouten.length === 1, r);

  r = await bewaker({ meta: { ...META, payload: { ...META.payload, _price_update: false } }, html: pagina(29.97) });
  ok("gewone verversing (foto's) wordt niet op prijs afgemeld", r.gemeld.length === 0 && r.fouten.length === 1, r);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
