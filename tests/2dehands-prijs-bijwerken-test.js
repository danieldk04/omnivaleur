/**
 * De PRIJS van een zoekertje dat al op 2dehands staat bijwerken (02-11-2026, Toon).
 *
 * Toon vroeg of een prijswijziging in Omni overal meegaat. Naar Marktplaats en
 * 2dehands ging hij niet. De extensie kon alleen de verzendkosten van een
 * bestaand zoekertje bijwerken.
 *
 * LIVE NAGEMETEN 02-11-2026 op een eigen zoekertje (m2446468449), ingelogd:
 *  - vraagprijs: input[name="price.value"] = "34,99"
 *  - "bieden vanaf" aan: input[name="price.minimumBidPrice"] = "24,49", precies
 *    70% van de prijs, schakelaar input#syi-bidding-switch-input (aangevinkt)
 *  - knop [data-testid="update-listing-submit-button"] "Opslaan"
 *
 * Deze proef draait de echte content/tweedehands.js met een nagebouwd formulier
 * en dezelfde code zoals hij was voor de wijziging (f53be0d3) als voor-en-na-proef.
 *
 * Draaien: node tests/2dehands-prijs-bijwerken-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR = "f53be0d3";
const FOUT_0511 = "c17c3c45"; // extensie 1.0.416

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function lees(pad, commit) {
  if (!commit) return fs.readFileSync(path.join(WORTEL, pad), "utf8");
  return execSync(`git show ${commit}:${pad}`, { cwd: WORTEL, encoding: "utf8", maxBuffer: 64 << 20 });
}
const cent = (t) => {
  const m = String(t || "").replace(/[^\d,.]/g, "").match(/^(\d{1,4})(?:[.,](\d{1,2}))?$/);
  return m ? Number(m[1]) * 100 + Number((m[2] || "0").padEnd(2, "0")) : null;
};

let BESTAND = "tweedehands.js";
async function draai(commit, { job, prijs = "34,99", bod = "24,49", bieden = true, geenPrijsveld = false,
                              klikSlaatOp = true, veldNeemtNietAan = false }) {
  const bron = lees("extension/content/" + BESTAND, commit);
  const berichten = [];
  const prijsEl = { value: prijs, type: "text" };
  const bodEl = { value: bod, type: "text" };
  const schakelaar = { checked: bieden };
  const location = { pathname: "/plaats/m2446468449/edit", href: "https://www.2dehands.be/plaats/m2446468449/edit" };
  const qs = (sel) => {
    if (sel === 'input[name="price.value"]') return geenPrijsveld ? null : prijsEl;
    if (sel === 'input[name="price.minimumBidPrice"]') return bieden ? bodEl : null;
    if (sel === "input#syi-bidding-switch-input") return schakelaar;
    return null;
  };
  const CL = new Proxy({
    clog: () => {}, qs, sleep: async () => {},
    step: async (_n, fn) => { try { await fn(); } catch (_) {} },
    // Zoals de echte waitUntil in shared.js: true of false, nooit het veld zelf.
    // Deze nabouw gaf eerst het veld terug, en zo zag de proef op 02-11-2026 niet
    // dat elke prijswijziging bij klanten omviel (7 van 7, 05-11-2026).
    waitUntil: async (v) => { try { return !!v(); } catch (_) { return false; } },
    centenUitTekst: cent,
    mpPrijs: (w, el) => Number(w).toFixed(2).replace(".", ","),
    fillInputHuman: async (el, w) => { if (typeof el !== "object") throw new TypeError("el.dispatchEvent is not a function"); if (!veldNeemtNietAan) el.value = w; },
    // dezelfde som als fillBidding in shared.js
    fillBidding: async (p, pct) => {
      const min = Math.round(p * pct / 100 * 100) / 100;
      if (!veldNeemtNietAan) bodEl.value = min.toFixed(2).replace(".", ",");
      return true;
    },
  }, { get: (d, n) => (n in d ? d[n] : async () => true) });
  const chrome = { runtime: { lastError: null, sendMessage(b, cb) {
    berichten.push(b);
    if (b.type === "GET_JOB") return cb && cb({ job });
    if (b.type === "KLIK_ECHT" && klikSlaatOp) location.pathname = "/seller/view/m2446468449";
    if (cb) cb(b.type === "KLIK_ECHT" ? "geklikt" : true);
  } } };
  const ctx = { window: { CL }, chrome, location, document: {}, console: { log() {}, warn() {}, error() {} },
                setTimeout: (fn) => { fn(); return 0; }, clearTimeout() {}, Promise };
  vm.createContext(ctx);
  vm.runInContext(bron, ctx);
  for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));
  return { berichten, prijs: prijsEl.value, bod: bodEl.value };
}

const opdracht = (price, extra = {}) => ({
  id: "j1", serverUrl: "https://omnivaleur.com", action: "content_refresh", platform: BESTAND === "marktplaats.js" ? "marktplaats" : "2dehands",
  payload: { platform_listing_id: "m2446468449", price, _prijs_bijwerken: true, ...extra },
});
const klik = (r) => r.berichten.filter((b) => b.type === "KLIK_ECHT").length;
const fout = (r) => r.berichten.some((b) => b.type === "JOB_ERROR");
const klaar = (r) => r.berichten.find((b) => b.type === "JOB_DONE");

async function proef() {
  let r = await draai(null, { job: opdracht(40) });
  check("nieuwe prijs staat op het formulier", r.prijs === "40,00", r.prijs);
  check("minimumbod volgt de prijs (70%)", r.bod === "28,00", r.bod);
  check("klikt echt op Opslaan, één keer", klik(r) === 1);
  check("meldt klaar met het bewijs", klaar(r)?.result?.prijs_bijgewerkt === true);

  r = await draai(null, { job: opdracht(34.99) });
  check("stond al goed: niets opgeslagen", klik(r) === 0 && klaar(r)?.result?.al_goed === true);

  r = await draai(null, { job: opdracht(29.5), prijs: "34,99", bieden: false });
  check("zonder bieden: alleen de prijs", r.prijs === "29,50" && klik(r) === 1 && klaar(r)?.result?.prijs_bijgewerkt === true);

  r = await draai(null, { job: opdracht(40), geenPrijsveld: true });
  check("geen prijsveld (Bieden/Zie omschrijving): niets opgeslagen, wel een fout", klik(r) === 0 && fout(r));

  r = await draai(null, { job: opdracht(40), veldNeemtNietAan: true });
  check("formulier neemt de prijs niet aan: niet opgeslagen, wel een fout", klik(r) === 0 && fout(r));

  r = await draai(null, { job: opdracht(40), klikSlaatOp: false });
  check("blijft op het formulier: fout, geen klaar", fout(r) && !klaar(r));

  r = await draai(null, { job: opdracht(0) });
  check("een prijs van 0 wordt nooit gezet", klik(r) === 0 && fout(r) && r.prijs === "34,99");

  r = await draai(null, { job: opdracht(40), bod: "geen getal" });
  check("onleesbaar minimumbod: niets aangeraakt", klik(r) === 0 && fout(r) && r.prijs === "34,99");

  // De echte waitUntil moet een boolean blijven, anders klopt de nabouw hierboven niet.
  check("nabouw volgt shared.js: waitUntil geeft een boolean",
    /const check = \(\) => \{ try \{ return !!voorwaarde\(\);/.test(lees("extension/content/shared.js")));

  // Voor-en-na van 05-11-2026: de versie die bij klanten omviel.
  r = await draai(FOUT_0511, { job: opdracht(40) });
  check("1.0.416 met bieden: valt om op een onleesbare prijs", klik(r) === 0 && fout(r), `prijs ${r.prijs}`);
  r = await draai(FOUT_0511, { job: opdracht(29.5), bieden: false });
  check("1.0.416 zonder bieden: valt om op dispatchEvent", klik(r) === 0 && fout(r), `prijs ${r.prijs}`);

  // Voor-en-na: de oude code kende alleen verzendkosten.
  r = await draai(VOOR, { job: opdracht(40) });
  check("voor de wijziging: de prijs bleef staan en er was geen bewijs van opslaan",
    r.prijs === "34,99" && klaar(r)?.result?.prijs_bijgewerkt !== true, `prijs ${r.prijs}`);

}

(async () => {
  for (const b of ["tweedehands.js", "marktplaats.js"]) {
    BESTAND = b;
    console.log(b);
    await proef();
  }
  console.log(mislukt ? `\n${mislukt} proef(ven) mislukt` : "\nalles in orde");
  process.exit(mislukt ? 1 : 0);
})();
