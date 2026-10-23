/**
 * 2dehands verlengen: direct en in een keten (23-10-2026, Egbert bcdf9aa4).
 *
 * Gemeten in zijn opdrachten (3 dagen, 417 verlengingen): 42 s werk plus 38 s
 * pauze per zoekertje, ~46 per uur, en zijn computer staat zo'n 7 uur per dag aan.
 * Nagemeten op het ingelogde account Revaleur: de knop "Verlengen" is niets
 * anders dan POST /my-account/sell/extend.json {itemId} met de sleutel van de
 * pagina (header x-mp-xsrf, ook in window.__ENV_CONFIG__.xsrfToken). Antwoord
 * 200 in ~0,3 s, de einddatum schuift daarna precies 28 dagen. Zonder sleutel: 403.
 *
 * Wat deze proef vastlegt:
 *  - met sleutel wordt er niet geklikt en niet gebladerd; het bewijs blijft de
 *    nieuwe einddatum (ook als die pas na een paar keer lezen schuift);
 *  - 403 of "betaling nodig" geeft een fout en verlengt niets;
 *  - zonder sleutel werkt het oude pad met de knop nog;
 *  - een keten verlengt meerdere zoekertjes in één tabblad: één keer openen, één
 *    keer sluiten, de lijst "Loopt af" niet bij elke verlenging opnieuw lezen;
 *  - een keten stopt bij de eerste fout en bij Calm mode.
 *
 * Draaien:  node tests/verlengen-2dehands-direct-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de wijziging. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "d814ad0c";

const ROOT = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, ok, uitleg) {
  if (ok) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " : " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const s = bron.indexOf(`async function ${naam}(`);
  const e = bron.indexOf("\n}\n", s);
  if (s < 0 || e < 0) throw new Error(`${naam} niet gevonden`);
  return bron.slice(s, e + 2);
}

const overNdagen = (n) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + n); return d.toISOString(); };

// opties.sleutel: false = de pagina heeft geen sleutel. opties.status: antwoord
// van extend.json. opties.vertraging: zoveel keer lezen voor de einddatum schuift.
// opties.betaling: antwoord vraagt om geld.
function maakZand(bron, ads, opties = {}) {
  const sleutel = opties.sleutel === false ? null : "sleutel-123";
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    Date, URL, JSON, Number, Math, String, Map, Set, Promise,
    setTimeout: (f) => setTimeout(f, 0),
    finalise: [], fouten: [], klikken: 0, posts: [], lezingen: 0, tabs: 0, gesloten: 0,
    aflopendGelezen: 0,
  };
  let db = JSON.parse(JSON.stringify(ads));
  const wacht = {};            // itemId -> aantal lezingen dat de verlenging nog "duurt"
  zand.window = sleutel ? { __ENV_CONFIG__: { xsrfToken: sleutel } } : {};
  zand.fetch = async (url, init) => {
    const u = new URL(String(url), "https://www.2dehands.be");
    if (u.pathname === "/my-account/sell/extend.json") {
      const kop = (init && init.headers) || {};
      zand.posts.push({ body: init && init.body, sleutel: kop["x-mp-xsrf"] });
      if (!kop["x-mp-xsrf"] || kop["x-mp-xsrf"] !== sleutel) {
        return { ok: false, status: 403, text: async () => "Forbidden" };
      }
      if (opties.status && opties.status !== 200) {
        return { ok: false, status: opties.status, text: async () => "nee" };
      }
      if (opties.betaling) {
        return { ok: true, status: 200, text: async () => JSON.stringify({ paymentRequired: true }) };
      }
      const id = JSON.parse(init.body).itemId;
      wacht[id] = opties.vertraging || 0;
      const ad = db.find((a) => a.itemId === id);
      if (ad && !wacht[id]) { ad.closeDate = (() => { const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28); return d.toISOString(); })(); ad.status = "ACTIVE"; }
      return { ok: true, status: 200, text: async () => JSON.stringify({ paymentRequired: false, orderId: 1 }) };
    }
    if (u.pathname === "/my-account/sell/api/listings") {
      zand.lezingen++;
      const nr = Math.max(1, Number(u.searchParams.get("batchNumber") || 1));
      const grootte = Math.min(200, Number(u.searchParams.get("batchSize") || 50));
      const aflopend = u.searchParams.get("inExpirationWindow") === "true";
      if (aflopend) zand.aflopendGelezen++;
      // De einddatum schuift pas na een paar lezingen (zo gedraagt 2dehands zich).
      for (const id of Object.keys(wacht)) {
        if (wacht[id] > 0 && --wacht[id] === 0) {
          const ad = db.find((a) => a.itemId === id);
          const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28);
          ad.closeDate = d.toISOString(); ad.status = "ACTIVE";
        }
      }
      const bron2 = aflopend ? db.filter((a) => a.status === "EXPIRING") : db;
      const stuk = bron2.slice((nr - 1) * grootte, nr * grootte);
      return { ok: true, status: 200,
               json: async () => JSON.parse(JSON.stringify({ ads: stuk, totalNumberOfResults: bron2.length })) };
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => "" };
  };
  zand.document = {
    scripts: [],
    querySelector(sel) {
      const m = sel.match(/data-ad-id="([^"]+)"/);
      const ad = m && db.find((a) => a.itemId === m[1]);
      if (!ad || ad.status !== "EXPIRING") return null;
      return { scrollIntoView() {}, click() {
        zand.klikken++;
        const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28);
        ad.closeDate = d.toISOString(); ad.status = "ACTIVE";
      } };
    },
    querySelectorAll() { return []; },
  };
  zand.openWorkerTab = (_u, cb) => { zand.tabs++; cb({ id: 7 }); };
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.zetWerkStatus = async () => {};
  zand.wachtendAantal = () => 0;
  zand.sluitWerkTabblad = () => { zand.gesloten++; };
  zand.stuurWerkTabbladNaar = async () => {};
  zand._klokTabbladen = new Set();
  zand.startOntdooiTeller = () => {};
  zand.execInTab = async (_t, fn, args = []) => fn(...args);
  zand.finaliseJob = async (_s, id, kind, body) => { zand.finalise.push({ id, kind, body }); };
  zand.reportError = async (id, _s, msg) => { zand.fouten.push({ id, msg: String(msg) }); };
  zand.gaEvent = () => {};
  zand.calmAan = async () => !!opties.calm;
  zand.volgende = (opties.volgende || []).slice();
  zand.haalVolgendeVerlenging = async () => zand.volgende.shift() || null;
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "bgExtend2dh"), zand);
  if (bron.includes("async function bgExtendKeten(")) {
    vm.runInContext("const KETEN_MAX_OPDRACHTEN = 40, KETEN_MAX_MS = 720000, KETEN_PAUZE_MS = [0, 1];", zand);
    vm.runInContext(functieUit(bron, "bgExtendKeten"), zand);
  }
  return zand;
}

const job = (id) => ({ id: "j" + id, platform: "2dehands", action: "extend", payload: { platform_listing_id: id } });
const lijst = (n) => Array.from({ length: n }, (_, i) => ({
  itemId: "m" + (2000000000 - i), status: "EXPIRING", closeDate: overNdagen(3 + (i % 3)), reserved: false }));

async function enkel(bron, ads, itemId, opties) {
  const zand = maakZand(bron, ads, opties);
  try { await zand.bgExtend2dh(job(itemId), "https://omnivaleur.com"); }
  catch (e) { zand.fouten.push({ id: "j" + itemId, msg: String(e && e.message || e) }); }
  return zand;
}

async function keten(bron, ads, ids, opties) {
  const zand = maakZand(bron, ads, { ...opties, volgende: ids.slice(1).map(job) });
  try { await zand.bgExtendKeten(job(ids[0]), "https://omnivaleur.com"); }
  catch (e) { zand.fouten.push({ id: "?", msg: String(e && e.message || e) }); }
  return zand;
}

async function draai(bron, label) {
  console.log(`\n${label}`);
  const ads = lijst(300);
  const id = ads[250].itemId;

  console.log("Een zoekertje, met sleutel");
  let z = await enkel(bron, ads, id);
  check("verlengd met bewijs (~28 dagen)", z.finalise.length === 1 && z.finalise[0].body.verlengd === true
    && z.finalise[0].body.shift_days >= 27, JSON.stringify(z.finalise[0] && z.finalise[0].body) + JSON.stringify(z.fouten));
  check("geen klik op de knop", z.klikken === 0, `${z.klikken} klik(ken)`);
  check("één aanroep van extend.json met de sleutel", z.posts.length === 1 && z.posts[0].sleutel === "sleutel-123",
    JSON.stringify(z.posts));

  console.log("De einddatum schuift pas na een paar lezingen");
  z = await enkel(bron, ads, id, { vertraging: 3 });
  check("toch verlengd met bewijs", z.finalise.length === 1 && z.finalise[0].body.verlengd === true,
    JSON.stringify(z.fouten));

  console.log("2dehands zegt 403");
  z = await enkel(bron, ads, id, { status: 403 });
  check("fout, niets als verlengd gemeld", z.finalise.length === 0 && z.fouten.length === 1
    && /403/.test(z.fouten[0].msg), JSON.stringify(z.fouten));

  console.log("2dehands vraagt om geld");
  z = await enkel(bron, ads, id, { betaling: true });
  check("fout, niets als verlengd gemeld", z.finalise.length === 0 && /payment/i.test((z.fouten[0] || {}).msg || ""),
    JSON.stringify(z.fouten));

  console.log("Pagina zonder sleutel");
  z = await enkel(bron, ads, id, { sleutel: false });
  check("oude pad met de knop werkt nog", z.finalise.length === 1 && z.finalise[0].body.verlengd === true
    && z.klikken === 1 && z.posts.length === 0, JSON.stringify(z.fouten));

  console.log("Een keten van vijf");
  const vijf = [250, 251, 252, 253, 254].map((i) => ads[i].itemId);
  z = await keten(bron, ads, vijf, {});
  check("alle vijf verlengd met bewijs", z.finalise.length === 5 && z.finalise.every((f) => f.body.verlengd === true),
    `${z.finalise.length} klaar, fouten ${JSON.stringify(z.fouten)}`);
  check("één tabblad geopend en één gesloten", z.tabs === 1 && z.gesloten === 1, `${z.tabs} open, ${z.gesloten} dicht`);
  check("de lijst Loopt af maar één keer meegestuurd", z.finalise.filter((f) => f.body.aflopend).length === 1,
    `${z.finalise.filter((f) => f.body.aflopend).length} keer`);
  check("niet vijf keer het hele overzicht bladeren", z.aflopendGelezen <= 12, `${z.aflopendGelezen} lezingen van de lijst Loopt af`);

  console.log("Een keten stopt bij de eerste fout");
  z = await keten(bron, ads, vijf, { status: 403 });
  check("één fout gemeld, geen tweede poging", z.fouten.length === 1 && z.finalise.length === 0 && z.volgende.length === 4,
    `${z.fouten.length} fouten, ${z.volgende.length} over`);
  check("tabblad toch dicht", z.gesloten === 1, `${z.gesloten} dicht`);

  console.log("Calm mode houdt de keten kort");
  z = await keten(bron, ads, vijf, { calm: true });
  check("precies één verlengd", z.finalise.length === 1 && z.volgende.length === 4, `${z.finalise.length} klaar`);
}

(async () => {
  const nieuw = fs.readFileSync(path.join(ROOT, "extension/background.js"), "utf8");
  await draai(nieuw, "NIEUWE VERSIE");

  if (process.argv.includes("--voor")) {
    let oud;
    try {
      oud = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`], { cwd: ROOT, maxBuffer: 1 << 28 }).toString();
    } catch (e) { console.log("oude versie niet op te halen:", String(e).slice(0, 120)); process.exit(2); }
    const voor = mislukt;
    mislukt = 0;
    try { await draai(oud, "OUDE VERSIE (moet falen)"); } catch (e) { console.log("  oude versie liep stuk:", String(e.message || e).slice(0, 100)); mislukt++; }
    console.log(`\noude versie: ${mislukt} controle(s) mislukt (moet > 0 zijn)`);
    process.exit(voor === 0 && mislukt > 0 ? 0 : 1);
  }
  console.log(mislukt ? `\n${mislukt} controle(s) mislukt.` : "\nAlles groen.");
  process.exit(mislukt ? 1 : 0);
})();
