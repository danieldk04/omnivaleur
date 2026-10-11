/**
 * 2dehands verlengen: niet meer twee keer het hele overzicht lezen per verlenging.
 *
 * 11-10-2026, Egbert (bcdf9aa4, 2.437 zoekertjes, extensie 1.0.376): "het vinden
 * van de betreffende advertentie gaat nu wel snel, maar nadat er 1 vernieuwd is
 * duurt het erg lang voordat er een nieuwe opgepakt wordt". Gemeten in zijn
 * opdrachten van 11-10: 25 verlengingen achter elkaar, elk 73 tot 84 s van
 * oppakken tot klaar. bgExtend2dh las vóór de klik en erna (het bewijs) de
 * overzicht-API van voren af aan, 100 per bladzijde, en de aflopende staan
 * achteraan (nieuwste eerst): 25 bladzijden, twee keer.
 *
 * Het nagebootste overzicht gedraagt zich als de echte API (nagemeten op
 * Revaleur 11-10): nieuwste itemId eerst, batchNumber 1-based, totaal in
 * totalNumberOfResults, inExpirationWindow=true geeft alleen de aflopende.
 *
 * Draaien:  node tests/verlengen-2dehands-gericht-lezen-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// Vast commitnummer van vóór de reparatie. NOOIT HEAD (auto-push-hook).
const OUDE_COMMIT = "6279f2b8";

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

// opties.naarBoven: na verlengen schuift het zoekertje naar de top (een volgorde
// die we niet verwachten; dan moet het oude pad het alsnog vinden).
function maakZand(bron, ads, opties = {}) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    Date, URL, JSON, Number, Math, String, setTimeout: (f) => setTimeout(f, 0),
    finalise: [], fouten: [], verzoeken: 0,
  };
  let db = JSON.parse(JSON.stringify(ads));
  zand.fetch = async (url) => {
    const u = new URL(String(url), "https://www.2dehands.be");
    if (u.pathname === "/my-account/sell/api/listings") {
      zand.verzoeken++;
      const nr = Math.max(1, Number(u.searchParams.get("batchNumber") || 1));
      const grootte = Math.min(200, Number(u.searchParams.get("batchSize") || 50));
      const bron = u.searchParams.get("inExpirationWindow") === "true"
        ? db.filter((a) => a.status === "EXPIRING") : db;
      const stuk = bron.slice((nr - 1) * grootte, nr * grootte);
      return { ok: true, status: 200,
               json: async () => JSON.parse(JSON.stringify({ ads: stuk, totalNumberOfResults: bron.length })) };
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => "" };
  };
  zand.document = {
    querySelector(sel) {
      const m = sel.match(/data-ad-id="([^"]+)"/);
      const ad = m && db.find((a) => a.itemId === m[1]);
      if (!ad || ad.status !== "EXPIRING") return null;
      return { scrollIntoView() {}, click() {
        const d = new Date(ad.closeDate); d.setUTCDate(d.getUTCDate() + 28);
        ad.closeDate = d.toISOString(); ad.status = "ACTIVE";
        if (opties.naarBoven) db = [ad, ...db.filter((a) => a !== ad)];
      } };
    },
    querySelectorAll() { return []; },
  };
  zand.openWorkerTab = (_u, cb) => cb({ id: 7 });
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.zetWerkStatus = async () => {};
  zand.wachtendAantal = () => 0;
  zand.sluitWerkTabblad = () => {};
  zand.stuurWerkTabbladNaar = async () => {};
  zand.execInTab = async (_t, fn, args = []) => fn(...args);
  zand.finaliseJob = async (_s, _i, kind, body) => { zand.finalise.push({ kind, body }); };
  zand.reportError = async (_i, _s, msg) => { zand.fouten.push(String(msg)); };
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "bgExtend2dh"), zand);
  return zand;
}

async function draai(bron, ads, itemId, opties) {
  const zand = maakZand(bron, ads, opties);
  const job = { id: "j", platform: "2dehands", action: "extend", payload: { platform_listing_id: itemId } };
  try { await zand.bgExtend2dh(job, "https://omnivaleur.com"); }
  catch (e) { zand.fouten.push(String(e && e.message || e)); }
  return zand;
}

const klaarMet = (z) => z.finalise.find((f) => f.kind === "complete");

(async () => {
  // 2.437 zoekertjes zoals bij Egbert, nieuwste eerst; de oudste 40 lopen af.
  const ads = [];
  for (let i = 0; i < 2437; i++) {
    const oud = i >= 2437 - 40;
    ads.push({ itemId: `m${2452349003 - i * 1371}`, status: oud ? "EXPIRING" : "ACTIVE",
               closeDate: overNdagen(oud ? 3 : 20), reserved: false });
  }
  const doel = ads[2420].itemId;

  const OUD = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const NIEUW = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");

  console.log(`Oude versie (${OUDE_COMMIT}) bij 2.437 zoekertjes`);
  const oud = await draai(OUD, ads, doel);
  check("verlengt wel", !!klaarMet(oud), oud.fouten.join(" | "));
  check("maar leest daarvoor het overzicht twee keer helemaal door (de klacht)",
    oud.verzoeken >= 48, `${oud.verzoeken} verzoeken`);

  console.log("\nNieuwe versie bij 2.437 zoekertjes");
  const nieuw = await draai(NIEUW, ads, doel);
  const k = klaarMet(nieuw);
  check("geen fout", nieuw.fouten.length === 0, nieuw.fouten.join(" | "));
  check("verlengd met bewijs (~28 dagen)",
    k && k.body.verlengd === true && k.body.shift_days >= 27 && k.body.shift_days <= 29, JSON.stringify(k && k.body));
  check("hooguit 12 verzoeken in plaats van 50", nieuw.verzoeken <= 12, `${nieuw.verzoeken} verzoeken`);
  console.log(`       (oud ${oud.verzoeken} verzoeken, nieuw ${nieuw.verzoeken})`);

  console.log("\nNieuwe versie: elk van de 40 aflopende zoekertjes");
  let goed = 0, meest = 0;
  for (let i = 2437 - 40; i < 2437; i++) {
    const z = await draai(NIEUW, ads, ads[i].itemId);
    const kk = klaarMet(z);
    if (kk && kk.body.verlengd && kk.body.shift_days >= 27 && !z.fouten.length) goed++;
    meest = Math.max(meest, z.verzoeken);
  }
  check("alle 40 verlengd met bewijs", goed === 40, `${goed} van 40`);
  check("nooit meer dan 12 verzoeken", meest <= 12, `${meest}`);

  console.log("\nNieuwe versie: randgevallen gaan nog steeds goed");
  const nietAanDeBeurt = await draai(NIEUW, ads, ads[1500].itemId);
  const n1 = klaarMet(nietAanDeBeurt);
  check("nog niet in het venster: niets geklikt, gemeld als not_in_extend_window",
    n1 && n1.body.note === "not_in_extend_window", JSON.stringify(n1 && n1.body));

  const alVerlengd = ads.map((a) => ({ ...a }));
  alVerlengd[2430].status = "ACTIVE"; alVerlengd[2430].closeDate = overNdagen(27);
  const n2 = klaarMet(await draai(NIEUW, alVerlengd, alVerlengd[2430].itemId));
  check("al verlengd: gemeld als already_extended", n2 && n2.body.note === "already_extended", JSON.stringify(n2 && n2.body));

  const weg = await draai(NIEUW, ads, "m2400000001");
  check("echt weg: pas na een volledige lezing 'niet gevonden' (2437 gelezen)",
    /\(2437 listings read\)/.test(weg.fouten[0] || ""), weg.fouten[0]);
  check("niets als klaar gemeld", !klaarMet(weg));

  const naarBoven = await draai(NIEUW, ads, doel, { naarBoven: true });
  const n3 = klaarMet(naarBoven);
  check("verlengd zoekertje springt naar boven: toch gevonden en bewezen",
    n3 && n3.body.verlengd === true && n3.body.shift_days >= 27, naarBoven.fouten.join(" | ") || JSON.stringify(n3 && n3.body));

  const oplopend = ads.map((a) => ({ ...a })).reverse();
  const n4 = klaarMet(await draai(NIEUW, oplopend, doel));
  check("andere volgorde dan verwacht: valt terug op alles lezen en verlengt",
    n4 && n4.body.verlengd === true && n4.body.shift_days >= 27, JSON.stringify(n4 && n4.body));

  console.log(mislukt === 0 ? "\nAlles groen." : `\n${mislukt} controle(s) mislukt.`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
