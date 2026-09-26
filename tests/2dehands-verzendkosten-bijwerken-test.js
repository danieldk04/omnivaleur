/**
 * De verzendkosten van een zoekertje dat al op 2dehands staat bijwerken.
 *
 * Egbert Brouwer (Papa's Plectrums), 25-09-2026: patches op 2dehands kregen Bpost
 * EUR 7,10, terwijl hij ze op Marktplaats zelf verstuurt voor zijn eigen bedrag.
 * Nieuwe zoekertjes krijgen sinds 1.0.353 zijn eigen bedrag; deze proef gaat over
 * de 116 die er al stonden.
 *
 * LIVE NAGEMETEN op 26-09-2026 op een eigen zoekertje van Daniel (m2446468449):
 *  - het wijzigformulier staat op /plaats/m{id}/edit, knop
 *    [data-testid="update-listing-submit-button"] "Opslaan";
 *  - button.click() vanuit een script doet niets; een echte muisklik slaat op;
 *  - na opslaan landt het tabblad op /seller/view/m{id} ("Je zoekertje is
 *    aangepast"), de openbare pagina toont "Zelf Verzenden € 6,95";
 *  - daarna teruggezet naar Bpost 0-2 kg, EUR 7,10.
 *
 * Deze proef draait de echte code uit background.js en content/tweedehands.js,
 * met een nagebouwd formulier, en dezelfde code zoals hij was op 252d3b01
 * (1.0.353) als voor-en-na-proef.
 *
 * Draaien: node tests/2dehands-verzendkosten-bijwerken-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "252d3b01";   // 1.0.353: nieuw plaatsen wel, bijwerken niet

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

function functie(bron, naam) {
  const m = new RegExp(`^function ${naam}\\(`, "m").exec(bron);
  if (!m) return null;
  let i = bron.indexOf("{", m.index), diepte = 0;
  for (let k = i; k < bron.length; k++) {
    if (bron[k] === "{") diepte++;
    else if (bron[k] === "}" && --diepte === 0) return bron.slice(m.index, k + 1);
  }
  return null;
}

// ── background.js ───────────────────────────────────────────────────────────
function achtergrond(commit) {
  const bron = lees("extension/background.js", commit);
  const ctx = { URL };
  vm.createContext(ctx);
  for (const naam of ["getEditUrl", "bewerkingOpgeslagen2dh"]) {
    const f = functie(bron, naam);
    if (f) vm.runInContext(f + `\nthis.${naam} = ${naam};`, ctx);
  }
  return ctx;
}

console.log("background.js");
const bg = achtergrond();
check("wijzigadres voor 2dehands",
  bg.getEditUrl("2dehands", { platform_listing_id: "m2446754373" })
    === "https://www.2dehands.be/plaats/m2446754373/edit");
check("ook zonder letter voor het nummer",
  bg.getEditUrl("2dehands", { platform_listing_id: "2446754373" })
    === "https://www.2dehands.be/plaats/m2446754373/edit");
check("zonder nummer geen adres", bg.getEditUrl("2dehands", {}) === null);
check("Vinted blijft zoals het was",
  bg.getEditUrl("vinted", { platform_listing_id: "9331465721" })
    === "https://www.vinted.com/items/9331465721/edit");

const meta = { platform: "2dehands", action: "content_refresh", submitClicked: true,
               payload: { platform_listing_id: "m2446468449" } };
check("opgeslagen: landt op zijn eigen verkoperspagina",
  bg.bewerkingOpgeslagen2dh("https://www.2dehands.be/seller/view/m2446468449", meta));
check("opgeslagen: of op de advertentiepagina",
  bg.bewerkingOpgeslagen2dh(
    "https://www.2dehands.be/v/kleding-heren/truien-en-vesten/m2446468449-1373-navy", meta));
check("het wijzigformulier zelf telt nooit",
  !bg.bewerkingOpgeslagen2dh("https://www.2dehands.be/plaats/m2446468449/edit", meta));
check("een ander zoekertje telt niet",
  !bg.bewerkingOpgeslagen2dh("https://www.2dehands.be/seller/view/m2446468450", meta));
check("zonder klik op Opslaan telt niets",
  !bg.bewerkingOpgeslagen2dh("https://www.2dehands.be/seller/view/m2446468449",
    { ...meta, submitClicked: false }));
check("een plaatsing is geen bijwerking",
  !bg.bewerkingOpgeslagen2dh("https://www.2dehands.be/seller/view/m2446468449",
    { ...meta, action: "create" }));

const oudBg = achtergrond(VOOR_DE_REPARATIE);
check("voor de reparatie: 2dehands had geen wijzigadres (de opdracht zou mislukken)",
  oudBg.getEditUrl("2dehands", { platform_listing_id: "m2446754373" }) === null);

// ── content/tweedehands.js met een nagebouwd formulier ──────────────────────
async function draai(commit, { job, formulier, klikSlaatOp = true, zetLukt = true }) {
  const bron = lees("extension/content/tweedehands.js", commit);
  const berichten = [];
  const aanroepen = [];
  const f = { methode: "bpost", bedrag: "", ...formulier };
  const location = { pathname: "/plaats/m2446754373/edit", href: "https://www.2dehands.be/plaats/m2446754373/edit" };
  const qs = (sel) => {
    if (sel === 'input[name="shippingMethod"]') return {};
    if (sel === 'input[name="shippingMethod"]:checked') return { value: f.methode };
    if (sel === 'input[name="othersPrice"]') return f.methode === "diy" ? { value: f.bedrag } : null;
    return null;
  };
  const nep = (naam) => async () => { aanroepen.push(naam); return true; };
  const CL = new Proxy({
    clog: () => {}, qs, sleep: async () => {},
    zetPrijs: async () => null,   // echte zetPrijs: null = gelukt, anders de fout
    step: async (_n, fn) => { try { await fn(); } catch (_) {} },
    waitUntil: async (voorwaarde) => { try { return !!voorwaarde(); } catch (_) { return false; } },
    centenUitTekst: (t) => {
      const m = String(t || "").replace(/[^\d,.]/g, "").match(/^(\d{1,4})(?:[.,](\d{1,2}))?$/);
      return m ? Number(m[1]) * 100 + Number((m[2] || "0").padEnd(2, "0")) : null;
    },
    zetVerzendkosten: async (item) => {
      aanroepen.push("zetVerzendkosten");
      if (zetLukt) { f.methode = "diy"; f.bedrag = (item.verzending.cents / 100).toFixed(2).replace(".", ","); }
      return zetLukt ? `zelf versturen voor € ${f.bedrag}` : "zelf versturen lukte niet (test), terug naar de standaardverzending";
    },
  }, { get: (doel, naam) => (naam in doel ? doel[naam] : nep(String(naam))) });
  const chrome = { runtime: {
    lastError: null,
    sendMessage(bericht, cb) {
      berichten.push(bericht);
      if (bericht.type === "GET_JOB") return cb && cb({ job });
      if (bericht.type === "KLIK_ECHT" && klikSlaatOp) location.pathname = "/seller/view/m2446754373";
      if (cb) cb(bericht.type === "KLIK_ECHT" ? "geklikt" : true);
    },
  } };
  const ctx = { window: { CL }, chrome, location, document: {}, console: { log() {}, warn() {}, error() {} },
                setTimeout: (fn) => { fn(); return 0; }, clearTimeout() {}, Promise };
  vm.createContext(ctx);
  vm.runInContext(bron, ctx);
  for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));
  return { berichten, aanroepen, formulier: f };
}

const bijwerken = {
  id: "j1", serverUrl: "https://omnivaleur.com", action: "content_refresh", platform: "2dehands",
  payload: { platform_listing_id: "m2446754373", _verzending_bijwerken: true,
             verzending: { soort: "zelf", cents: 495 } },
};

(async () => {
  console.log("content/tweedehands.js");
  let r = await draai(null, { job: bijwerken });
  const soorten = r.berichten.map((b) => b.type);
  check("zet zijn eigen bedrag", r.formulier.methode === "diy" && r.formulier.bedrag === "4,95");
  check("ontwapent, meldt de klik en klikt echt, in die volgorde",
    JSON.stringify(soorten.filter((t) => ["ONTWAPEN_AFSLUITVRAAG", "SUBMIT_CLICKED", "KLIK_ECHT"].includes(t)))
      === JSON.stringify(["ONTWAPEN_AFSLUITVRAAG", "SUBMIT_CLICKED", "KLIK_ECHT"]));
  check("klikt op Opslaan en niet op de plaatsknop",
    r.berichten.find((b) => b.type === "KLIK_ECHT")?.selector === '[data-testid="update-listing-submit-button"]');
  const klaar = r.berichten.find((b) => b.type === "JOB_DONE");
  check("meldt klaar met het bewijs", klaar && klaar.result && klaar.result.verzending_bijgewerkt === true);
  check("vult NOOIT het plaatsformulier opnieuw in",
    !r.aanroepen.some((a) => /fill|upload|submitListing|zetPrijs|typBeschrijving/.test(a)), r.aanroepen.join(","));

  r = await draai(null, { job: bijwerken, formulier: { methode: "diy", bedrag: "4,95" } });
  check("stond al goed: niets aangeraakt, niets opgeslagen",
    !r.berichten.some((b) => b.type === "KLIK_ECHT") && !r.aanroepen.includes("zetVerzendkosten")
      && r.berichten.find((b) => b.type === "JOB_DONE")?.result?.al_goed === true);

  r = await draai(null, { job: bijwerken, zetLukt: false });
  check("bedrag niet te zetten: niet opgeslagen, wel een fout",
    !r.berichten.some((b) => b.type === "KLIK_ECHT") && r.berichten.some((b) => b.type === "JOB_ERROR"));

  r = await draai(null, { job: bijwerken, klikSlaatOp: false });
  check("blijft op het formulier staan: fout, geen klaar",
    r.berichten.some((b) => b.type === "JOB_ERROR") && !r.berichten.some((b) => b.type === "JOB_DONE"));

  r = await draai(null, { job: { ...bijwerken, payload: { platform_listing_id: "m2446754373" } } });
  check("een bijwerking zonder bedrag verandert niets",
    r.berichten.some((b) => b.type === "JOB_ERROR") && !r.berichten.some((b) => b.type === "KLIK_ECHT")
      && !r.aanroepen.some((a) => /fill|upload/.test(a)));

  // Een PLAATSING meldt of het eigen bedrag er echt op stond; zo niet, dan zet de
  // server vanzelf een bijwerking klaar (_verzending_alsnog_bijwerken).
  const plaatsing = { ...bijwerken, action: "create",
                      payload: { title: "Patch", price: 11.95, verzending: { soort: "zelf", cents: 495 } } };
  r = await draai(null, { job: plaatsing });
  check("plaatsing met eigen bedrag meldt verzending_gezet",
    r.berichten.find((b) => b.type === "JOB_DONE")?.result?.verzending_gezet === true,
    JSON.stringify(r.berichten.find((b) => b.type === "JOB_DONE")));
  r = await draai(null, { job: plaatsing, zetLukt: false });
  check("lukte het niet, dan meldt de plaatsing dat ook",
    r.berichten.find((b) => b.type === "JOB_DONE")?.result?.verzending_gezet === false);

  // Voor de reparatie viel een bijwerking door naar het plaatsformulier. Daarom
  // krijgt een kopie onder 1.0.354 dit werk nooit (MINIMALE_2DH_BIJWERK_VERSIE).
  r = await draai(VOOR_DE_REPARATIE, { job: bijwerken });
  check("voor de reparatie: de bijwerking zou het hele formulier opnieuw invullen",
    r.aanroepen.some((a) => /fill|upload/.test(a)), r.aanroepen.join(","));

  console.log(mislukt ? `\n${mislukt} proef(ven) mislukt` : "\nalles in orde");
  process.exit(mislukt ? 1 : 0);
})();
