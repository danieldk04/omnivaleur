/**
 * Papa's Plectrums (Egbert Brouwer), 05-09-2026: "Ik heb 1 artikel gepubliceerd
 * naar MP, ik kreeg geen foutmelding of zo. Na 5 minuten was het artikel nog
 * niet zichtbaar op MP."
 *
 * Er is die dag geen enkele opdracht aangemaakt. De server sloeg Marktplaats
 * bewust over omdat het artikel er al op stond (al zijn 1000 artikelen staan er
 * al op, geimporteerd uit Admarkt) en gaf `status: "active"` terug. Het scherm
 * hield alleen `error` en `duplicate` tegen, dus "active" telde als succes en de
 * melding luidde "Queued for Marktplaats — the extension starts right away".
 * Precies het tegenovergestelde van wat er gebeurde.
 *
 * Deze test draait de ECHTE doCrosslist uit app.html.
 *
 * Draaien: node tests/publiceren-zegt-queued-terwijl-er-niets-gebeurt-test.js
 *          node tests/... --oud     (tegen de vorige commit; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const oud = process.argv.includes("--oud");
const html = oud
  ? execSync("git show HEAD:frontend/app.html", { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "frontend/app.html"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function pakFunctie(bron, naam) {
  const start = bron.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  let diepte = 0, i = bron.indexOf("{", start);
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diepte++;
    else if (bron[i] === "}") { diepte--; if (!diepte) break; }
  }
  return "async " + bron.slice(start, i + 1);
}

/** Wat ziet de verkoper als de server dit antwoordt? */
async function watZietHij(resultaten) {
  const gezien = { toast: null, alert: null };
  const ctx = {
    console,
    API: "",
    PLATFORM_LABELS: { marktplaats: "Marktplaats", "2dehands": "2dehands", vinted: "Vinted" },
    state: { crosslistItemId: "item-1", items: [] },
    document: {
      querySelectorAll: () => [{ value: "marktplaats" }],
      querySelector: () => ({ disabled: false, textContent: "" }),
      getElementById: () => ({ style: {}, textContent: "" }),
    },
    apiFetch: async () => ({
      ok: true, status: 200,
      text: async () => JSON.stringify({ results: resultaten }),
    }),
    alert: (t) => { gezien.alert = t; },
    showToast: (t) => { gezien.toast = t; },
    closeModal: () => {}, nudgeExtension: () => {}, setBusy: () => {},
    loadAll: async () => {}, resetCrosslistButton: () => {},
    geenPlatformGekozen: () => "niets gekozen",
    publishFailureMessage: () => "mislukt",
  };
  vm.createContext(ctx);
  vm.runInContext(pakFunctie(html, "doCrosslist") + "\ndoCrosslist();", ctx);
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  return gezien;
}

(async () => {
  console.log(oud ? "VORIGE VERSIE (hier hoort het fout te gaan)" : "HUIDIGE VERSIE");

  // 1. Het geval van Egbert: staat er al op, er is niets in de wachtrij gezet.
  const alLive = await watZietHij([{
    platform: "marktplaats", status: "already_live",
    message: "Already live on this channel, so nothing was published and nothing was queued.",
  }]);
  check("staat er al op: geen 'queued'-melding", !alLive.toast,
        `kreeg toch: ${JSON.stringify(alLive.toast)}`);
  check("staat er al op: hij hoort dat er niets gepubliceerd is",
        !!alLive.alert && /Not published/.test(alLive.alert) && /Marktplaats/.test(alLive.alert),
        `melding was: ${JSON.stringify(alLive.alert)}`);

  // 2. Echt in de wachtrij gezet: dan hoort de bevestiging er gewoon te staan.
  const gequeued = await watZietHij([{ platform: "marktplaats", status: "queued", job_id: "x" }]);
  check("echt gequeued: bevestiging blijft", !!gequeued.toast && !gequeued.alert,
        `toast=${JSON.stringify(gequeued.toast)} alert=${JSON.stringify(gequeued.alert)}`);

  // 3. Een echte fout blijft een fout.
  const fout = await watZietHij([{ platform: "vinted", status: "error", error: "no photos" }]);
  check("fout blijft zichtbaar", !!fout.alert && /no photos/.test(fout.alert));

  // 4. Server en scherm moeten dezelfde term gebruiken. Wijzigt een van de twee,
  //    dan valt het geval stil terug in "queued" en is de klacht terug.
  if (!oud) {
    const py = fs.readFileSync(path.join(WORTEL, "backend/services/crosslist.py"), "utf8");
    check("backend stuurt 'already_live'",
          (py.match(/"status": "already_live"/g) || []).length === 2,
          "beide plekken (extensiekanaal en API-kanaal) moeten die status geven");
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
  process.exit(oud ? (mislukt ? 0 : 1) : (mislukt ? 1 : 0));
})();
