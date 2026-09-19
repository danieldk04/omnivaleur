/**
 * WAT HET SCHERM DOET ALS DE DATABASE ER UIT LIGT.
 *
 * WAAROM DIT ER IS (19-09-2026, Lynn van De Juiste Toon). Supabase lag die
 * middag van 15:10 tot 17:00 plat. Elk verzoek van het dashboard kwam terug als
 * fout. Lynn zat een uur naar de itemlijst te kijken, dacht dat het aan haar
 * eigen laptop of haar inlog bij Marktplaats lag ("ben gewoon ingelogd op
 * marktplaats enzo"), en meldde: "als ik op try again klik gebeurt er (optisch
 * in iedergeval) niks".
 *
 * Beide klachten waren waar en beide zaten in deze code:
 *   1. Het scherm zei "Loading your listings… Nothing is missing — we are still
 *      fetching", terwijl het ophalen al mislukt WAS.
 *   2. "Try again" riep loadAll(). Mislukte dat weer, dan was de HTML letter
 *      voor letter dezelfde, en dan slaat de stempelvergelijking in
 *      renderItemsTable het tekenen over. Dus: nul verandering op het scherm.
 *   3. Een foutantwoord ({"detail": "..."}) werd door loadAll als geldig
 *      antwoord aangenomen: de kanalenlijst werd leeg ("je bent nergens meer
 *      gekoppeld") en de voorkeuren werden overschreven.
 *
 * Deze test draait de ECHTE functies uit app.html, en dezelfde proef tegen de
 * versie van vóór de reparatie (commit defcd54d) om te bewijzen dat die faalt.
 *
 * Draaien:  node tests/laadstoring-scherm-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const NIEUW = fs.readFileSync(path.join(WORTEL, "frontend", "app.html"), "utf8");
const VOOR_COMMIT = "defcd54d";
const OUD = execSync(`git show ${VOOR_COMMIT}:frontend/app.html`, { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

let fouten = 0;
function eis(voorwaarde, wat) {
  if (voorwaarde) console.log(`  ok   ${wat}`);
  else { console.log(`  FOUT ${wat}`); fouten++; }
}

function functieUit(bron, naam, start = `function ${naam}(`) {
  const i = bron.indexOf(start);
  if (i < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n}\n", i);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return bron.slice(i, eind + 2);
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ── Een namaakscherm met precies één vak, dat bijhoudt hoe vaak er echt iets
//    op het scherm wordt gezet. Dát is de klacht van Lynn: niet "de tekst is
//    verkeerd" maar "er gebeurt niks".
function maakScherm(bron) {
  let inhoud = "";
  let schrijfrondes = 0;
  const vak = {
    get innerHTML() { return inhoud; },
    set innerHTML(v) { inhoud = v; schrijfrondes++; },
  };
  const document = {
    getElementById: (id) => (id === "items-body" ? vak : null),
  };
  const state = {
    items: [], listings: [], jobs: [], connected: [], settings: {},
    listingsLoaded: false, listingsLoadError: null, itemsLoadError: null,
  };
  const laadPoging = { bezig: false, om: null };
  const code = [
    "let _itemsTabelStempel = null;",
    "let _itemsRijStempels = null; let _itemsRijVolgorde = '';",
    "let itemsGroepeerOpDatum = false;",
    functieUit(bron, "renderItemsTable"),
    functieUit(bron, "_tekenRijen"),
    "return function(){ renderItemsTable(state.items); };",
  ].join("\n");
  if (!code.includes("updateBulkBar();")) throw new Error("renderItemsTable niet volledig geknipt");
  // eslint-disable-next-line no-new-func
  const teken = new Function(
    "document", "state", "esc", "_laadPoging", "advertIndex", "renderSoldConfirmBar",
    "renderDuplicateBar", "renderPublishErrorBar", "updateBulkBar", "publishedAt",
    "EMPTY_TAB", "itemsTab", "loadAll", "probeerOpnieuwLaden", "applyFilters", code
  )(document, state, esc, laadPoging, () => new Map(), () => {}, () => {}, () => {},
    () => {}, () => null, { live: { h: "", p: "" } }, "live", () => {}, () => {}, () => {});
  return { teken, state, laadPoging, get html() { return inhoud; }, get rondes() { return schrijfrondes; } };
}

// ── Proef 1: de storing heet een storing ──────────────────────────────────────
console.log("\nHet scherm tijdens de storing (nieuw):");
const n = maakScherm(NIEUW);
n.state.listingsLoadError = "Could not load your listings";
n.state.itemsLoadError = "Connection hiccup — you're still signed in. Please try again in a moment.";
n.teken();
const eerste = n.html;
eis(!/Loading your listings/.test(eerste), "zegt niet meer 'Loading your listings…'");
eis(!/still fetching/.test(eerste), "zegt niet meer dat hij nog aan het ophalen is");
eis(/on our side/.test(eerste), "zegt dat het aan onze kant ligt");
eis(/not your computer/.test(eerste) && /not your login/.test(eerste),
    "zegt dat het niet haar laptop en niet haar inlog is");
eis(/Nothing of yours is lost/.test(eerste), "zegt dat er niets van haar kwijt is");
eis(/Could not load your listings/.test(eerste), "noemt ook wat er technisch misging");
eis(/probeerOpnieuwLaden/.test(eerste), "de knop gaat via de zichtbare herkansing");

console.log("\nDezelfde storing op de oude versie (" + VOOR_COMMIT + "):");
const o = maakScherm(OUD);
o.state.listingsLoadError = "Could not load your listings";
o.state.itemsLoadError = "Connection hiccup — you're still signed in. Please try again in a moment.";
o.teken();
eis(/Loading your listings/.test(o.html),
    "oud: beweert dat hij nog aan het laden is (dit was de klacht)");
eis(/Nothing is missing/.test(o.html),
    "oud: zegt 'Nothing is missing' terwijl het ophalen mislukte");

// ── Proef 2: een klik op Try again doet zichtbaar iets ────────────────────────
console.log("\nTwee keer 'Try again' bij een storing die blijft duren:");
const rondesVoorKlik = n.rondes;
n.laadPoging.bezig = true;            // wat probeerOpnieuwLaden meteen doet
n.teken();
const bezigHtml = n.html;
eis(n.rondes === rondesVoorKlik + 1, "nieuw: de klik zet meteen iets op het scherm");
eis(/Checking/.test(bezigHtml), "nieuw: het scherm zegt dat hij aan het kijken is");
n.laadPoging.bezig = false;           // de poging mislukt opnieuw
n.laadPoging.om = new Date(2026, 8, 19, 16, 42, 11);
n.teken();
eis(n.rondes === rondesVoorKlik + 2, "nieuw: de uitslag van de poging komt ook op het scherm");
eis(/Last checked at/.test(n.html) && /still no answer/.test(n.html),
    "nieuw: het scherm zegt hoe laat er voor het laatst gekeken is en dat er nog geen antwoord is");
n.laadPoging.bezig = true; n.teken();
n.laadPoging.bezig = false; n.laadPoging.om = new Date(2026, 8, 19, 16, 43, 27);
n.teken();
eis(n.rondes === rondesVoorKlik + 4, "nieuw: ook de tweede klik is zichtbaar");

const oudRondes = o.rondes;
o.teken();  // dit is alles wat loadAll() deed bij een tweede mislukte poging
o.teken();
eis(o.rondes === oudRondes,
    `oud: twee pogingen later is er nul keer iets op het scherm gezet (${o.rondes - oudRondes} tekenrondes)`);

// ── Proef 3: een foutantwoord is geen antwoord ────────────────────────────────
// loadAll echt draaien, met een server die op alles een 503 met een JSON-body
// teruggeeft — precies wat er tijdens de storing gebeurde.
function draaiLoadAll(bron) {
  const state = {
    items: [{ id: "it1", title: "oude trui" }], listings: [], jobs: [],
    connected: ["marktplaats", "2dehands", "vinted"],
    settings: { verkoopvraag_aan: true, land: "NL" },
    listingsLoaded: false, listingsLoadError: null, itemsLoadError: null,
  };
  const laadPoging = { bezig: false, om: null };
  const antwoord = () => ({
    ok: false, status: 503,
    text: async () => JSON.stringify({ detail: "Connection hiccup — you're still signed in. Please try again in a moment." }),
  });
  const code = [
    functieUit(bron, "parseJsonSafe", "async function parseJsonSafe("),
    functieUit(bron, "fetchAllItems", "async function fetchAllItems("),
    functieUit(bron, "loadAll", "async function loadAll("),
    "return loadAll;",
  ].join("\n");
  // eslint-disable-next-line no-new-func
  const loadAll = new Function(
    "state", "_laadPoging", "apiFetch", "API", "syncItems", "_itemsSinds",
    "_listingsOpgehaald", "LISTINGS_INTERVAL", "_toonLaadVoortgang", "_onthoudItemsStempel",
    "loadDuplicates", "renderDashboard", "renderExtStatus", "document", "applyFilters",
    "renderAnalytics", "renderStaleStock", "renderStaleBadge", "loadRelistStatus", code
  )(state, laadPoging, async () => antwoord(), "", async () => [], null, 0, 60000,
    () => {}, () => {}, async () => {}, () => {}, () => {},
    { getElementById: () => ({ classList: { contains: () => false } }) },
    () => {}, () => {}, () => {}, () => {}, () => {});
  return { loadAll, state, laadPoging };
}

(async () => {
  console.log("\nloadAll tegen een server die alleen fouten geeft (nieuw):");
  const a = draaiLoadAll(NIEUW);
  await a.loadAll();
  eis(a.state.connected.length === 3,
      "nieuw: de gekoppelde kanalen blijven staan (geen valse 'niet gekoppeld')");
  eis(a.state.settings.land === "NL" && a.state.settings.verkoopvraag_aan === true,
      "nieuw: de eigen voorkeuren blijven staan");
  eis(!!a.state.itemsLoadError && !!a.state.listingsLoadError,
      "nieuw: het mislukken wordt wel onthouden");
  eis(a.laadPoging.om instanceof Date && a.laadPoging.bezig === false,
      "nieuw: de ronde legt vast wanneer hij klaar was");

  console.log("\nDezelfde server op de oude versie (" + VOOR_COMMIT + "):");
  const b = draaiLoadAll(OUD);
  await b.loadAll();
  eis(b.state.connected.length === 0,
      "oud: alle kanalen lijken losgekoppeld (dit is de valse melding)");
  eis(b.state.settings.land === undefined && "detail" in b.state.settings,
      "oud: de voorkeuren zijn overschreven door de foutmelding");

  console.log(fouten ? `\n${fouten} fout(en)` : "\nAlles goed.");
  process.exit(fouten ? 1 : 0);
})();
