/**
 * "Extension not detected" bij iemand die hem gewoon heeft.
 *
 * WAAROM DIT ER IS (03-09-2026, Amanda Haas). "Ook geeft hij dan wel/dan weer
 * niet aan dat de extensie niet is gevonden (als je bijvoorbeeld bezig bent met
 * het dashboard), terwijl deze up-to-date is (als je deze dan controleert bij de
 * Chrome store)."
 *
 * Het dashboard vroeg het aan de achtergrond van de extensie en gaf na ~8,8
 * seconde op. Dat antwoord moet twee heen-en-weertjes met een service worker
 * overleven die Chrome koud moet starten — en juist terwijl er gepubliceerd
 * wordt duurt dat het langst. Daarna stond er "Extension not detected" mét een
 * blokkerend installatievenster over haar scherm.
 *
 * Sinds 1.0.285 zet content/ext_stamp.js bij het laden van de pagina het
 * versienummer op <html data-omnivaleur-ext="…">. Daar komt geen achtergrond
 * aan te pas. Deze proef draait de ECHTE functies uit app.html in beide
 * situaties, met de oude versie van _extGeefOp ernaast.
 *
 * Draaien:  node tests/extensie-stempel-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");

let mislukt = 0;
function ok(v, wat) { if (v) { console.log("  ✓", wat); return; } console.log("  ✗", wat); mislukt++; }

function functieUit(naam) {
  const start = `function ${naam}(`;
  const i = APP.indexOf(start);
  if (i < 0) throw new Error(`${naam} niet gevonden in app.html`);
  const eind = APP.indexOf("\n}\n", i);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(i, eind + 2);
}

function bouwScherm(stempel) {
  const el = () => ({ style: {}, textContent: "", className: "", classList: { add(c) { this._c = c; } } });
  const vakken = {
    "ext-dot": el(), "ext-label": el(), "ext-overlay": el(), "ext-signin-callout": el(),
    "ext-outdated-overlay": el(), "ext-outdated-version": el(),
    "ext-update-banner": el(), "ext-update-current": el(), "ext-update-latest": el(),
  };
  const opslag = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) }; };
  const sandbox = {
    console: { log() {} },
    document: {
      getElementById: (id) => vakken[id] || null,
      documentElement: { getAttribute: (n) => (n === "data-omnivaleur-ext" ? stempel : null) },
    },
    localStorage: opslag(),
    sessionStorage: opslag(),
    state: { jobs: [] },
    _gepubliceerdeVersie: "",
    extState: { status: "checking", version: "", email: "" },
  };
  vm.createContext(sandbox);
  for (const naam of ["extStempel", "_extGeefOp", "renderExtSetup", "renderExtStatus",
                      "extVersionIsOld", "extVersionAchter", "versieLager"]) {
    vm.runInContext(functieUit(naam), sandbox);
  }
  vm.runInContext("const EXT_MIN_VERSION = '1.0.244';", sandbox);
  return { sandbox, vakken };
}

// Precies wat er tot 1.0.284 gebeurde als er binnen ~8,8s geen antwoord kwam.
const OUDE_OPGEEFREGEL = `
function _oudGeefOp() {
  if (extState.status !== 'checking') return;
  extState = { status: 'missing', version: '', email: '' };
  renderExtSetup();
  renderExtStatus();
}`;

console.log("\n1. De oude weg: extensie geïnstalleerd, achtergrond nog niet wakker");
{
  const { sandbox, vakken } = bouwScherm("1.0.285");
  vm.runInContext(OUDE_OPGEEFREGEL + "\n_oudGeefOp();", sandbox);
  ok(sandbox.extState.status === "missing", "oude code: oordeelt 'niet gevonden'");
  ok(vakken["ext-label"].textContent === "Extension not detected", "oude code: 'Extension not detected' in beeld");
  ok(vakken["ext-overlay"].style.display === "flex", "oude code: het installatievenster gaat blokkerend over haar scherm");
}

console.log("\n2. De nieuwe weg, in exact dezelfde situatie");
{
  const { sandbox, vakken } = bouwScherm("1.0.285");
  vm.runInContext("_extGeefOp();", sandbox);
  ok(sandbox.extState.status === "waking", "de extensie geldt als aanwezig, want haar stempel staat op de pagina");
  ok(sandbox.extState.version === "1.0.285", "en we kennen haar versie zonder ook maar iets te vragen");
  ok(vakken["ext-overlay"].style.display === "none", "geen installatievenster meer over het scherm");
  ok(/starting up/.test(vakken["ext-label"].textContent), `de zijbalk zegt wat er aan de hand is: "${vakken["ext-label"].textContent}"`);
}

console.log("\n3. Echt niet geïnstalleerd blijft gewoon 'niet gevonden'");
{
  const { sandbox, vakken } = bouwScherm("");
  vm.runInContext("_extGeefOp();", sandbox);
  ok(sandbox.extState.status === "missing", "zonder stempel: 'niet gevonden'");
  ok(vakken["ext-overlay"].style.display === "flex", "en het installatievenster hoort er dan ook te staan");
}

console.log("\n4. Een wakkere extensie wordt niet overschreven");
{
  const { sandbox } = bouwScherm("1.0.285");
  sandbox.extState = { status: "ready", version: "1.0.285", email: "a@b.nl" };
  vm.runInContext("_extGeefOp();", sandbox);
  ok(sandbox.extState.status === "ready", "wie al antwoord gaf, blijft 'ready'");
}

console.log("\n5. Het stempel zelf staat in de extensie en in het manifest");
{
  const stamp = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "ext_stamp.js"), "utf8");
  ok(/data-omnivaleur-ext/.test(stamp) && /getManifest\(\)\.version/.test(stamp),
     "ext_stamp.js zet het versienummer op de pagina");
  ok(!/sendMessage/.test(stamp), "en heeft de achtergrond daar niet voor nodig — dat was juist het probleem");
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "extension", "manifest.json"), "utf8"));
  const entry = manifest.content_scripts.find((c) => c.js.includes("content/ext_stamp.js"));
  ok(!!entry, "het staat in het manifest");
  ok(entry && entry.run_at === "document_start", "en draait bij het allereerste moment van de pagina, vóór het dashboard iets vraagt");
  ok(entry && entry.matches.includes("https://omnivaleur.com/*") && entry.matches.includes("https://www.omnivaleur.com/*"),
     "op allebei de adressen van het dashboard");
}

console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} proef(en) mislukt.\n`);
process.exit(mislukt === 0 ? 0 : 1);
