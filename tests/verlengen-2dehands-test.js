/**
 * Automatisch verlengen op 2dehands — het bewijs dat het verlengt en niet
 * herplaatst.
 *
 * Egbert Brouwer vroeg ernaar, Daniel wilde het (docs/team-notes.md,
 * 10-09-2026). Het gevaar: het Marktplaats-pad klakkeloos kopiëren zou een
 * bijna verlopen 2dehands-zoekertje WEGHALEN en OPNIEUW PLAATSEN. Opnieuw
 * plaatsen kost in een betalende rubriek geld of eet het gratis tegoed op;
 * verlengen is altijd gratis. Zie ook docs/kennisbank.md:
 *   - "herplaatsen-verliest-advertenties" (eerst weg = advertentie kwijt)
 *   - "succes-nooit-uit-uitsluitingslijst" ("geen fout" is geen bewijs)
 *
 * Gemeten op het ingelogde account Revaleur (10-09-2026): het overzicht
 * /my-account/sell/api/listings geeft per zoekertje { itemId, status, closeDate }.
 * status "EXPIRING" toont een <a href="#verlengen" data-ad-id="m…">-knop; klikken
 * verlengt meteen en closeDate springt 28 dagen verder. Twee echte advertenties
 * zo verlengd, allebei +28 dagen, EUR 0,00.
 *
 * Draaien:  node tests/verlengen-2dehands-test.js
 *           node tests/verlengen-2dehands-test.js --oud   (voor-proef expliciet)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

// De commit van vlak vóór deze functie bestond. NOOIT HEAD: de auto-push-hook
// commit werk in uitvoering onder "auto: update …", dus HEAD bevat de reparatie
// al binnen seconden. Zie docs/kennisbank.md "voor-en-na-proef-mag-geen-head-gebruiken".
const OUDE_COMMIT = "a3d3083c";

let mislukt = 0;
function check(naam, ok, uitleg) {
  if (ok) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

const ROOT = path.join(__dirname, "..");
const BG = fs.readFileSync(path.join(ROOT, "extension", "background.js"), "utf8");

function functieUit(bron, naam) {
  const s = bron.indexOf(`async function ${naam}(`);
  if (s < 0) throw new Error(`${naam} niet gevonden`);
  // De functie eindigt bij de eerste "\n}\n" op kolom 0.
  const e = bron.indexOf("\n}\n", s);
  if (e < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return bron.slice(s, e + 2);
}

// ── Een nagebootst 2dehands-overzicht ───────────────────────────────────────
//
// `ads` is de lijst zoals /my-account/sell/api/listings hem geeft. Een klik op
// de verlengknop van een EXPIRING-zoekertje zet closeDate 28 dagen verder en de
// status op ACTIVE — precies wat er live gebeurde. Met `klikDoetNiets` bootsen
// we een 2dehands na dat de klik negeert (dan mag er NIETS als verlengd worden
// gemeld).
function maakZand(ads, opties = {}) {
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    Date, URL, JSON, setTimeout,
    navigaties: [],      // elke url waar het werk-tabblad heen gestuurd wordt
    finalise: [],        // elke finaliseJob-aanroep
    fouten: [],
  };
  zand.window = zand;

  const db = JSON.parse(JSON.stringify(ads));

  zand.fetch = async (url) => {
    if (String(url).includes("/my-account/sell/api/listings")) {
      return { ok: true, status: 200, json: async () => ({ ads: JSON.parse(JSON.stringify(db)) }) };
    }
    zand.navigaties.push(String(url));
    return { ok: true, status: 200, text: async () => "", json: async () => ({}) };
  };

  zand.document = {
    querySelector(sel) {
      const m = sel.match(/data-ad-id="([^"]+)"/);
      if (!sel.includes("#verlengen") || !m) return null;
      const ad = db.find((a) => a.itemId === m[1]);
      if (!ad || ad.status !== "EXPIRING") return null;
      return {
        scrollIntoView() {},
        click() {
          if (opties.klikDoetNiets) return;
          if (opties.klikOpentBetaalvenster) zand._betaalvensterGeopend = true;
          const d = new Date(ad.closeDate);
          d.setUTCDate(d.getUTCDate() + 28);
          ad.closeDate = d.toISOString();
          ad.status = "ACTIVE";
        },
      };
    },
    querySelectorAll() { return []; },
  };

  // Stubs voor alles wat bgExtend2dh uit background.js verwacht.
  zand.openWorkerTab = (url, cb) => { zand.navigaties.push(String(url)); cb({ id: 7 }); };
  zand.waitForTabLoad = async () => {};
  zand.expandMp2dhOverview = async () => {};
  zand.sluitWerkTabblad = () => {};
  zand.execInTab = async (_tabId, fn, args = []) => fn(...args);
  zand.finaliseJob = async (_srv, _id, kind, body) => { zand.finalise.push({ kind, body }); };
  zand.reportError = async (_id, _srv, msg) => { zand.fouten.push(String(msg)); };

  vm.createContext(zand);
  vm.runInContext(functieUit(BG, "bgExtend2dh"), zand, { filename: "background.js" });
  return zand;
}

const dagenGeleden = (n) => { const d = new Date(); d.setUTCDate(d.getUTCDate() - n); return d.toISOString(); };
const overNdagen  = (n) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + n); return d.toISOString(); };

async function draaiJob(zand, itemId) {
  const job = { id: "job-1", platform: "2dehands", action: "extend",
                payload: { platform_listing_id: itemId, _listing_row_id: "row-1" } };
  try { await zand.bgExtend2dh(job, "https://omnivaleur.com"); }
  catch (e) { zand.fouten.push(String(e && e.message ? e.message : e)); }
  return job;
}

(async () => {
  // ── 1. DE VOOR-PROEF: de oude code kende geen 'extend' ─────────────────
  console.log("Wat de oude versie deed (commit " + OUDE_COMMIT + ")");
  const OUD_BG = execFileSync("git", ["show", `${OUDE_COMMIT}:extension/background.js`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const OUD_JOBS = execFileSync("git", ["show", `${OUDE_COMMIT}:backend/api/jobs.py`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const OUD_SCHED = execFileSync("git", ["show", `${OUDE_COMMIT}:backend/scheduler.py`],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

  check("de oude background.js had geen bgExtend2dh",
    !/bgExtend2dh/.test(OUD_BG), "dan bewijst deze test niets");
  check("de oude processJob had geen enkele 'extend'-tak",
    !/action === "extend"/.test(OUD_BG), "dan liep 'extend' NIET door de create/SYI-weg");
  check("de oude jobs.py wist niet dat 'extend' schrijvend is",
    /SCHRIJVEND = \("create", "delete", "content_refresh"\)/.test(OUD_JOBS),
    "dan werd 'extend' niet als één-tegelijk behandeld");
  check("de oude jobs.py had geen afronding voor 'extend'",
    !/job\["action"\] == "extend"/.test(OUD_JOBS),
    "dan schoof listed_at nooit op en bleef het zoekertje eeuwig relist-kandidaat");
  check("de oude scheduler kende geen extend_expiring_2dehands",
    !/extend_expiring_2dehands/.test(OUD_SCHED));

  // In de oude wereld belandde een 'extend'-opdracht in de url-keuze van
  // processJob. Die keuze is een ladder van action-vergelijkingen; zonder
  // 'extend' erin valt hij door naar getMpSyiUrl — de PLAATS-pagina. Dat is
  // precies het weghalen-en-opnieuw-plaatsen dat geld kost.
  const oudeUrlKeuze = OUD_BG.slice(OUD_BG.indexOf("    url = job.action === \"delete\""),
                                   OUD_BG.indexOf("getMpSyiUrl(job.platform, job.payload);") + 40);
  check("de oude url-keuze stuurde alles wat geen delete/content_refresh is naar getMpSyiUrl",
    /getMpSyiUrl\(job\.platform, job\.payload\)/.test(oudeUrlKeuze) &&
    !/extend/.test(oudeUrlKeuze),
    "een extend-opdracht opende dus het plaatsformulier — een tweede advertentie");

  // ── 2. DE NIEUWE VERSIE: verlengt echt, plaatst niks ───────────────────
  console.log("\nDe nieuwe versie op een bijna verlopen zoekertje");
  const zandOk = maakZand([
    { itemId: "m2431571489", status: "EXPIRING", closeDate: overNdagen(3), reserved: false },
    { itemId: "m9999999999", status: "ACTIVE", closeDate: overNdagen(20), reserved: false },
  ], { klikOpentBetaalvenster: true });
  await draaiJob(zandOk, "m2431571489");

  check("geen fouten", zandOk.fouten.length === 0, zandOk.fouten.join(" | "));
  const done = zandOk.finalise.find((f) => f.kind === "complete");
  check("de opdracht is als klaar gemeld", !!done);
  check("met bewijs: verlengd = true", done && done.body.verlengd === true);
  check("de nieuwe vervaldatum ligt ~4 weken verder",
    done && done.body.shift_days >= 27 && done.body.shift_days <= 29,
    done && `shift_days = ${done.body.shift_days}`);
  check("er is NIETS naar het plaatsformulier of een verwijderpagina gestuurd",
    !zandOk.navigaties.some((u) => /\/plaats\/|\/syi\/|verwijder/i.test(u)),
    zandOk.navigaties.join(" | "));
  check("alleen het eigen overzicht is geopend",
    zandOk.navigaties.every((u) => u.includes("/my-account/sell/index.html")),
    zandOk.navigaties.join(" | "));

  // ── 3. GEEN BEWIJS = GEEN SUCCES ──────────────────────────────────────
  console.log("\nAls 2dehands de klik negeert");
  const zandDood = maakZand(
    [{ itemId: "m2431571489", status: "EXPIRING", closeDate: overNdagen(3), reserved: false }],
    { klikDoetNiets: true });
  await draaiJob(zandDood, "m2431571489");
  check("er is GEEN 'complete' met verlengd=true gemeld",
    !zandDood.finalise.some((f) => f.kind === "complete" && f.body.verlengd === true));
  check("het is als fout teruggekomen", zandDood.fouten.length === 1,
    zandDood.fouten.join(" | "));
  check("de fout noemt dat de vervaldatum niet opschoof",
    /did not move|expiry date/i.test(zandDood.fouten[0] || ""), zandDood.fouten[0]);

  // ── 4. NOG NIET IN HET VERLENGVENSTER ────────────────────────────────
  console.log("\nAls het zoekertje nog niet verlengd kan worden");
  const zandVroeg = maakZand(
    [{ itemId: "m2431571489", status: "ACTIVE", closeDate: overNdagen(20), reserved: false }]);
  await draaiJob(zandVroeg, "m2431571489");
  check("geen fout", zandVroeg.fouten.length === 0, zandVroeg.fouten.join(" | "));
  const vroegDone = zandVroeg.finalise.find((f) => f.kind === "complete");
  check("klaar gemeld zonder verlengd-vlag", vroegDone && !vroegDone.body.verlengd);
  check("met de reden 'niet in het verlengvenster'",
    vroegDone && vroegDone.body.note === "not_in_extend_window", vroegDone && vroegDone.body.note);

  // ── 5. LEEG OVERZICHT BEWIJST NIETS ──────────────────────────────────
  console.log("\nAls het overzicht leeg terugkomt (uitgelogd?)");
  const zandLeeg = maakZand([]);
  await draaiJob(zandLeeg, "m2431571489");
  check("geen enkele 'complete'", !zandLeeg.finalise.some((f) => f.kind === "complete"));
  check("het is als fout teruggekomen die om inloggen vraagt",
    /logged in|overview/i.test(zandLeeg.fouten[0] || ""), zandLeeg.fouten[0]);

  // ── 6. VERKOCHT/GERESERVEERD WORDT NOOIT VERLENGD ────────────────────
  console.log("\nEen gereserveerd zoekertje");
  const zandRes = maakZand(
    [{ itemId: "m2431571489", status: "EXPIRING", closeDate: overNdagen(3), reserved: true }]);
  await draaiJob(zandRes, "m2431571489");
  const resDone = zandRes.finalise.find((f) => f.kind === "complete");
  check("niet verlengd, wel netjes afgemeld",
    resDone && resDone.body.note === "reserved_not_extended" && !resDone.body.verlengd);

  console.log(mislukt === 0 ? "\nAlles groen." : `\n${mislukt} controle(s) mislukt.`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
