/**
 * Een mislukte Admarkt-import moet zeggen wat er misging.
 *
 * WAT ER AAN DE HAND WAS (klant 4c30200f, 22-09-2026, extensie 1.0.347).
 * Drie importpogingen binnen één minuut, alle drie met exact deze tekst:
 *
 *   Error: Admarkt: Admarkt returned no live adverts. page="?" steps=[none]
 *
 * Die tekst is aantoonbaar onjuist. `stappen` krijgt zijn eerste regel
 * ("campagnes: N") direct ná de eerste tRPC-aanroep, dus `steps=[none]`
 * bewijst dat die aanroep is afgebroken. En `page="?"` betekent dat er
 * helemaal geen meta terugkwam, dus de injectie heeft nooit iets teruggegeven.
 * Er is met andere woorden nooit vastgesteld dat er geen advertenties zijn.
 *
 * HET MECHANISME. De scan draait in de pagina via chrome.scripting
 * .executeScript met een async functie. Geeft die functie een AFGEWEZEN belofte
 * terug, dan komt er bij de achtergrond `results[0].result === undefined`
 * binnen zonder foutmelding. execInTab doet `resolve(results?.[0]?.result)`,
 * dus de reden (HTTP 401 omdat er geen Admarkt-sessie is, html in plaats van
 * json, een procedurenaam die afwijkt) verdween. Wat overbleef was de
 * vangnettekst "no live adverts", en die stuurt de klant de verkeerde kant op:
 * hij gaat zijn advertenties nakijken terwijl hij moet inloggen.
 *
 * WAT DEZE PROEF DOET. De echte bgScanAdmarkt uit background.js, met een
 * nep-Chrome eronder die de injectie ook echt uitvoert. De nep-execInTab
 * bootst Chrome na op het enige punt dat hier telt: een afgewezen belofte
 * wordt `undefined`. Dat is geen aanname maar precies wat de productie liet
 * zien (steps=[none] + page="?" kan niet anders ontstaan).
 *
 * Draaien:  node tests/admarkt-zegt-wat-er-misging-test.js
 *           node tests/admarkt-zegt-wat-er-misging-test.js --oud   (hoort te falen)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// Vast commitnummer, geen HEAD: na de commit zou de proef zichzelf vergelijken.
const VOOR_DE_REPARATIE = "6765d602";
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${extra !== undefined ? " — kreeg: " + String(extra).slice(0, 220) : ""}`);
};

function blokUit(naam) {
  let start = BG.indexOf(`function ${naam}(`);
  if (start < 0) return null;
  if (BG.slice(Math.max(0, start - 6), start) === "async ") start -= 6;
  let diepte = 0, i = BG.indexOf("{", start);
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(start, i + 1);
}

const BRON = blokUit("bgScanAdmarkt");
if (!BRON) { console.log("  FOUT bgScanAdmarkt niet gevonden in background.js"); process.exit(1); }

/**
 * @param antwoord  functie(url) -> {status, type, body}  voor de tRPC-aanroepen
 * @param tabWeg    true = het werktabblad is verdwenen, de injectie geeft niets
 */
async function draai({ antwoord, tabWeg = false, titel = "Admarkt", adres = "https://admarkt.marktplaats.nl/advertisements" }) {
  const ctx = {
    console: { log() {}, warn() {} },
    ADMARKT_MAX: 500,
    JSON, Promise, Set, Array, Number, Math, String, Object, Error,
    setTimeout: (f) => f(),            // geen echte wachttijden in de proef
    encodeURIComponent,
    zorgVoorAdmarktMeekijker: async () => true,
    admarktUrl: () => adres,
    openWorkerTab: (url, cb) => cb({ id: 7 }),
    waitForTabLoad: async () => {},
    sluitWerkTabblad: () => {},
    // Chrome-gedrag: een injectie die een afgewezen belofte teruggeeft komt
    // terug als `undefined`, zonder foutmelding.
    execInTab: async (tabId, func, args) => {
      if (tabWeg) return undefined;
      try { return await func(...args); } catch (_) { return undefined; }
    },
  };
  ctx.globalThis = ctx;
  ctx.document = { title: titel };
  ctx.location = { href: adres };
  ctx.fetch = async (url) => {
    const a = antwoord(url);
    return {
      ok: a.status >= 200 && a.status < 300,
      status: a.status,
      headers: { get: (n) => (n.toLowerCase() === "content-type" ? a.type : null) },
      json: async () => a.body,
    };
  };
  vm.createContext(ctx);
  vm.runInContext(BRON + "\nglobalThis.__scan = bgScanAdmarkt;", ctx);
  const job = { platform: "marktplaats", payload: { scan_offset: 0, bekende_ids: [] } };
  try {
    const r = await ctx.__scan(job, "https://omnivaleur.com");
    return { uitkomst: r, fout: null };
  } catch (e) {
    return { uitkomst: null, fout: String(e && e.message || e) };
  }
}

const jsonAntwoord = (body) => ({ status: 200, type: "application/json", body });

(async () => {
  console.log(oud ? "\nOUDE CODE (moet falen)\n" : "\nNIEUWE CODE\n");

  // 1. Niet ingelogd op Admarkt: de tRPC-aanroep geeft 401 met een html-pagina.
  {
    const r = await draai({ antwoord: () => ({ status: 401, type: "text/html", body: null }) });
    ok("401 komt bij de klant terecht", /401/.test(r.fout || ""), r.fout);
    ok("401 zegt niet 'no live adverts'", !/no live adverts/i.test(r.fout || ""), r.fout);
    ok("401 noemt inloggen", /sign(ed)? in/i.test(r.fout || ""), r.fout);
  }

  // 2. De site geeft 200 maar met html (de catch-all van de React-app).
  {
    const r = await draai({ antwoord: () => ({ status: 200, type: "text/html", body: null }) });
    ok("html-in-plaats-van-json komt terecht", /text\/html/.test(r.fout || ""), r.fout);
    ok("html zegt niet 'no live adverts'", !/no live adverts/i.test(r.fout || ""), r.fout);
  }

  // 3. De procedurenaam bestaat niet op deze tenant (404 op de procedure).
  {
    const r = await draai({ antwoord: () => ({ status: 404, type: "application/json", body: null }) });
    ok("onbekende procedure noemt de naam", /campaign\.getAllCampaigns/.test(r.fout || ""), r.fout);
  }

  // 4. Nul campagnes: bestaat niet op een echt zakelijk account, dus dat is de
  //    verkeerde sessie en geen lege voorraad.
  {
    const r = await draai({ antwoord: () => jsonAntwoord([{ result: { data: { campaigns: [] } } }]) });
    ok("nul campagnes wijst naar het account", /account/i.test(r.fout || "") && !/no live adverts/i.test(r.fout || ""), r.fout);
  }

  // 5. Het werktabblad is weg: dat is iets anders dan een lege Admarkt.
  {
    const r = await draai({ tabWeg: true, antwoord: () => jsonAntwoord([{ result: { data: { campaigns: [] } } }]) });
    ok("tabblad weg wordt zo gemeld", /tab closed|no answer/i.test(r.fout || ""), r.fout);
    ok("tabblad weg zegt niet 'no live adverts'", !/no live adverts/i.test(r.fout || ""), r.fout);
  }

  // 6. GEEN TERUGVAL: een account dat het gewoon doet levert nog steeds items.
  {
    const r = await draai({
      antwoord: (url) => url.includes("getAllCampaigns")
        ? jsonAntwoord([{ result: { data: { campaigns: [{ id: "c1", title: "Campagne" }] } } }])
        : jsonAntwoord([{ result: { data: { count: 1, ads: [{
            id: 42, title: "Apple Watch Series 7", status: "ACTIVE", categoryId: 1234,
            images: [{ links: { "1024x1024": "//img/a.jpg" } }],
          }], nextPageToken: null } } }]),
    });
    ok("werkend account geeft 1 advertentie", (r.uitkomst && r.uitkomst.items || []).length === 1, r.fout || JSON.stringify(r.uitkomst && r.uitkomst.items));
    ok("werkend account geeft de titel mee",
      (((r.uitkomst || {}).items || [])[0] || {}).title === "Apple Watch Series 7",
      JSON.stringify(((r.uitkomst || {}).items || [])[0]));
    ok("foto krijgt https: ervoor",
      (((r.uitkomst || {}).items || [])[0] || {}).photo_url === "https://img/a.jpg",
      JSON.stringify(((r.uitkomst || {}).items || [])[0]));
  }

  // 7. Echt leeg (campagne zonder advertenties) blijft de oude melding houden.
  {
    const r = await draai({
      antwoord: (url) => url.includes("getAllCampaigns")
        ? jsonAntwoord([{ result: { data: { campaigns: [{ id: "c1" }] } } }])
        : jsonAntwoord([{ result: { data: { count: 0, ads: [], nextPageToken: null } } }]),
    });
    ok("lege campagne meldt nog steeds 'no live adverts'", /no live adverts/i.test(r.fout || ""), r.fout);
    ok("lege campagne toont wél de stappen", /campagnes: 1/.test(r.fout || ""), r.fout);
  }

  console.log(mislukt ? `\n${mislukt} controle(s) omgevallen\n` : "\nalles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
