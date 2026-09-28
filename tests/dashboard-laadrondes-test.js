/**
 * Het dashboard mag de database niet platleggen (28-09-2026, Egbert Brouwer).
 *
 * Om 12:25 UTC begon zijn extensie aan 235 verzendkost-bijwerkingen, een per
 * 9 seconden, terwijl zijn dashboard openstond. Elke keer dat er een klaar was,
 * haalde pollActivity de hele voorraad opnieuw op: 5.533 artikelen in zeven
 * pagina's plus alle advertenties, zo'n 5 MB. Gemeten in de Railway-logs: van
 * 5 MB per tien minuten naar 33 tot 38 MB, 90 procent van alles wat de server
 * verstuurde. De rondes werden trager, begonnen voor de vorige klaar was, en om
 * 13:05 lag de database eruit, voor iedereen. Om 13:20 zag hij "1,000 loaded"
 * en daarna een storing.
 *
 * Deze proef draait de échte loadAll en pollActivity uit app.html.
 *
 * Draaien: node tests/dashboard-laadrondes-test.js
 *          node tests/dashboard-laadrondes-test.js /tmp/oude-app.html   (moet falen)
 */
const fs = require("fs");
const path = require("path");

const bestand = process.argv[2] || path.join(__dirname, "..", "frontend", "app.html");
const APP = fs.readFileSync(bestand, "utf8");

let mislukt = 0;
function ok(v, wat, uitleg) {
  if (v) { console.log("  ✓", wat); return; }
  console.log("  ✗", wat + (uitleg ? " — " + uitleg : "")); mislukt++;
}

function functieUit(naam, verplicht = true) {
  let start = APP.indexOf(`function ${naam}(`);
  if (start < 0) {
    if (verplicht) throw new Error(`${naam} niet gevonden in ${path.basename(bestand)}`);
    return "";
  }
  if (APP.slice(start - 6, start) === "async ") start -= 6;
  const eind = APP.indexOf("\n}\n", start);
  return APP.slice(start, eind + 2);
}

function blokUit(begin, eindTekst) {
  const start = APP.indexOf(begin);
  if (start < 0) return "";
  return APP.slice(start, APP.indexOf(eindTekst, start) + eindTekst.length);
}

const wacht = (ms) => new Promise((r) => setTimeout(r, ms));

// Een nagebootst dashboard met een database die per verzoek `traag` ms nodig heeft.
function dashboard() {
  const code = [
    blokUit("let _laadRonde = null;", "let _laadNaRonde = null;"),
    functieUit("loadAll"),
    functieUit("_loadAllNu", false),
    functieUit("pollActivity"),
  ].join("\n");
  const t = { traag: 20, volledig: 0, sync: 0, listings: 0, bezig: 0, maxBezig: 0,
              rondesKlaar: 0, actief: [] };
  const stubs = {
    API: "",
    LISTINGS_INTERVAL: 60000,
    state: { items: [{ id: "a", updated_at: "2026-09-28T12:00:00Z" }], listings: [], jobs: [] },
    _itemsSinds: "2026-09-28T12:00:00Z",
    _listingsOpgehaald: Date.now(),
    _laadPoging: { bezig: false, om: null },
    _activityState: { working: [], queued: [] },
    async fetchAllItems() { t.volledig++; t.bezig++; t.maxBezig = Math.max(t.maxBezig, t.bezig);
                            await wacht(t.traag * 7); t.bezig--; return stubs.state.items; },
    async syncItems() { t.sync++; t.bezig++; t.maxBezig = Math.max(t.maxBezig, t.bezig);
                        await wacht(t.traag); t.bezig--; return stubs.state.items; },
    async apiFetch(url) {
      if (url.includes("/api/jobs/active")) {
        return { ok: true, json: async () => ({ working: t.actief, queued: [] }) };
      }
      if (url.includes("/api/listings/")) t.listings++;
      await wacht(t.traag);
      return { ok: true, json: async () => (url.includes("/api/listings/") ? [] : {}) };
    },
    async parseJsonSafe(r) { return r.json(); },
    _toonLaadVoortgang() {}, _onthoudItemsStempel() {},
    async loadDuplicates() {},
    renderDashboard() { if (t.gooi) { t.gooi = false; throw new Error("kapot"); } t.rondesKlaar++; }, renderExtStatus() {},
    renderActivityBar() {}, renderKanaalSessie() {}, applyFilters() {}, renderAnalytics() {},
    renderStaleStock() {}, renderStaleBadge() {}, loadRelistStatus() {},
    document: { getElementById: () => ({ classList: { contains: () => false } }) },
  };
  const namen = Object.keys(stubs);
  const maak = new Function(...namen, `${code}\nreturn { loadAll, pollActivity };`);
  const fns = maak(...namen.map((n) => stubs[n]));
  return { t, stubs, ...fns };
}

async function eenKlusjeKlaar(d) {
  d.t.actief = [{ id: "job" }];
  await d.pollActivity();
  d.t.actief = [];
  await d.pollActivity();
}

(async () => {
  console.log(`\nBestand: ${path.basename(bestand)}\n`);

  console.log("1. Een klaar klusje haalt niet de hele voorraad opnieuw op");
  {
    const d = dashboard();
    for (let i = 0; i < 10; i++) { await eenKlusjeKlaar(d); await wacht(d.t.traag * 12); }
    ok(d.t.volledig === 0, `0 keer alle artikelen na 10 klusjes (was ${d.t.volledig})`,
       "bij Egbert elke keer 5.533 artikelen");
    ok(d.t.rondesKlaar >= 1 && d.t.listings >= 1,
       `het scherm werd wel ververst, met de advertenties (${d.t.rondesKlaar} rondes, ${d.t.listings}x advertenties)`);
  }

  console.log("\n2. Een trage database krijgt geen stapel rondes over zich heen");
  {
    const d = dashboard();
    d.t.traag = 60;                       // elke vraag een stuk trager, zoals om 13:00
    const lopend = [];
    for (let i = 0; i < 8; i++) {         // om de paar tellen een klusje klaar, en de tik
      d.t.actief = [{ id: "job" }]; await d.pollActivity();
      d.t.actief = []; await d.pollActivity();
      lopend.push(d.loadAll({ snel: true }));
      lopend.push(d.loadAll());           // en de verkoper klikt ook nog iets
      await wacht(15);
    }
    await Promise.all(lopend);
    await wacht(d.t.traag * 12);
    ok(d.t.maxBezig <= 1, `hooguit één laadronde tegelijk (was ${d.t.maxBezig})`);
    ok(d.t.rondesKlaar <= 6, `de vragen van 8 rondes vallen samen (${d.t.rondesKlaar} rondes gedraaid)`);
  }

  console.log("\n3. Wie na een handeling wacht, krijgt een beeld van ná zijn handeling");
  {
    const d = dashboard();
    d.t.traag = 30;
    d.loadAll({ snel: true });            // er loopt al een ronde
    await wacht(5);
    const volledigVoor = d.t.volledig;
    const rondesVoor = d.t.rondesKlaar;
    await d.loadAll();                    // "opslaan" gevolgd door een volledige ververs
    ok(d.t.rondesKlaar >= rondesVoor + 2, "de lopende ronde én een nieuwe ronde erna zijn klaar");
    ok(d.t.volledig === volledigVoor + 1, "en die nieuwe ronde was volledig, zoals gevraagd");
  }

  console.log("\n4. Een fout in een ronde houdt de volgende niet tegen");
  {
    const d = dashboard();
    d.t.gooi = true;                      // de lopende ronde gaat stuk
    const eerste = d.loadAll().then(() => "klaar", () => "fout");
    const tweede = d.loadAll().then(() => "klaar", () => "fout");
    ok(await eerste === "fout", "voorwaarde: de eerste ronde faalde");
    ok(await tweede === "klaar", "de ronde die erachter wachtte liep toch");
    ok(await d.loadAll().then(() => "klaar", () => "fout") === "klaar", "en daarna loopt alles gewoon door");
  }

  console.log(mislukt ? `\n${mislukt} mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
