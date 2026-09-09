/**
 * "Your extension has not checked in" terwijl de extensie gewoon geïnstalleerd is.
 *
 * WAT ER MISGING (09-09-2026, Daniel). Het klantendashboard verhuisde zijn
 * inlogbewijs op 08-09-2026 van sessionStorage naar localStorage, zodat je
 * ingelogd blijft als je een tabblad sluit. content/webapp_sync.js — het stukje
 * dat datzelfde bewijs aan de browserextensie doorgeeft — bleef sessionStorage
 * lezen. Daar stond niets meer, dus kreeg de extensie geen token meer van het
 * dashboard. Zodra haar eigen token na een uur verliep lag ze stil: geen scans,
 * geen publicaties, geen verkoopcontrole, en op het dashboard "your extension has
 * not checked in".
 *
 * Deze proef zet het bewijs in localStorage (zoals het dashboard nu doet) met
 * een lege sessionStorage, en meet of webapp_sync.js het token dan alsnog naar
 * de service worker stuurt. De versie van vóór de fix staat ernaast en zakt.
 *
 * Draaien: node tests/extensie-token-uit-localstorage-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const PAD = "extension/content/webapp_sync.js";
const VOOR = "321a8460"; // HEAD vóór de fix: webapp_sync.js las alleen sessionStorage
const NIEUW = fs.readFileSync(path.join(WORTEL, PAD), "utf8");
const OUD = execFileSync("git", ["show", `${VOOR}:${PAD}`], { cwd: WORTEL }).toString();

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Draai webapp_sync.js met een nagebootste browser. `local` en `session` bepalen
// wat er in local- en sessionStorage staat. Geeft terug welke boodschappen naar
// de service worker gingen, en de SYNC_TOKEN eruit gelicht.
async function draai(bron, { local = {}, session = {} }) {
  const verstuurd = [];
  const maakOpslag = (data) => ({
    getItem: (k) => (Object.prototype.hasOwnProperty.call(data, k) ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    removeItem: (k) => { delete data[k]; },
  });
  const sandbox = {
    console,
    localStorage: maakOpslag({ ...local }),
    sessionStorage: maakOpslag({ ...session }),
    chrome: {
      runtime: {
        lastError: null,
        id: "test",
        getManifest: () => ({ version: "1.0.314" }),
        sendMessage: (msg, cb) => {
          verstuurd.push(msg);
          if (typeof cb === "function") {
            cb(msg && msg.type === "GET_AUTH_STATE"
              ? { signedIn: true, email: "x@y.nl" }
              : undefined);
          }
        },
      },
    },
  };
  sandbox.window = {
    location: { origin: "https://omnivaleur.com", href: "https://omnivaleur.com/app" },
    addEventListener: () => {},
    postMessage: () => {},
  };
  vm.createContext(sandbox);
  vm.runInContext(bron, sandbox);
  await new Promise((r) => setTimeout(r, 10)); // announce() is async
  return { verstuurd, sync: verstuurd.find((m) => m && m.type === "SYNC_TOKEN") || null };
}

(async () => {
  console.log("webapp_sync.js: token uit localStorage doorgeven aan de extensie\n");

  const bewijs = { cl_token: "abc.def.ghi", cl_refresh: "r-123", cl_email: "seller@shop.nl" };

  console.log("Dashboard van nu (bewijs in localStorage, sessionStorage leeg):");
  const na = await draai(NIEUW, { local: bewijs, session: {} });
  check("de extensie krijgt het token", na.sync !== null,
        "geen SYNC_TOKEN naar de service worker");
  check("met het access-token erbij", !!na.sync && na.sync.token === bewijs.cl_token);
  check("en het refresh-token, anders valt ze na een uur alsnog stil",
        !!na.sync && na.sync.refresh === bewijs.cl_refresh);
  check("en het e-mailadres", !!na.sync && na.sync.email === bewijs.cl_email);

  console.log("\nOudere pagina (bewijs nog in sessionStorage): blijft werken:");
  const oudePagina = await draai(NIEUW, { local: {}, session: bewijs });
  check("de extensie krijgt het token nog steeds", oudePagina.sync !== null);
  check("met het access-token erbij",
        !!oudePagina.sync && oudePagina.sync.token === bewijs.cl_token);

  console.log("\nEcht uitgelogd (nergens een token): niets doorsturen:");
  const leeg = await draai(NIEUW, { local: {}, session: {} });
  check("geen SYNC_TOKEN", leeg.sync === null);

  console.log("\nDe versie van vóór de fix, op datzelfde dashboard van nu:");
  const voor = await draai(OUD, { local: bewijs, session: {} });
  check("stuurde de extensie GEEN token", voor.sync === null,
        "als dit slaagt, reproduceert de proef de fout niet");

  console.log("");
  if (mislukt) { console.log(`${mislukt} controle(s) mislukt`); process.exit(1); }
  console.log("alles goed");
})();
