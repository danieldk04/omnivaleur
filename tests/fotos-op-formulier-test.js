/**
 * De Juiste Toon, 13-09-2026: "Originele Lederhosen XXXL maat 60" (13 foto's) en
 * "Konijnenvacht Setje bruin" (5 foto's) stonden online zonder één foto.
 *
 * Live gemeten op het /plaats-formulier van Marktplaats en 2dehands: het veld
 * images.ids krijgt per ontvangen foto een nummer; tijdens een lopende upload
 * bestaat het veld niet, na een mislukte upload is het leeg. De extensie zag in
 * die toestand geen miniatuur, ging "toch door" en klikte Plaatsen.
 *
 * Deze proef draait de echte uploadPhotos en submitListing uit shared.js. Komt
 * de routine voorbij de fotocontrole, dan strandt hij op "publish button could
 * not be found" (er is in deze proef geen knop): dat is het teken dat hij had
 * geplaatst.
 *
 * Draaien: node tests/fotos-op-formulier-test.js
 *          node tests/fotos-op-formulier-test.js --oud   (vóór de reparatie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "cbae5876";
const oud = process.argv.includes("--oud");
const BRON = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// scenario: wat Marktplaats doet met een aangeboden stapel foto's.
//   "lukt"      : meteen een nummer per foto
//   "faalt"     : "Fout opgetreden", veld blijft leeg, ook bij opnieuw aanbieden
//   "hangt"     : upload komt nooit terug, veld blijft weg
//   "tweedekeer": eerste keer mislukt, opnieuw aanbieden lukt
//   "druppel"   : foto's komen één voor één binnen, tussendoor is het veld weg
//   "deel"      : een deel komt binnen, de rest mislukt blijvend
function laad(scenario, host = "www.marktplaats.nl") {
  let klok = 1_000_000;
  const staat = { veld: "", aanbiedingen: 0, log: [] };
  const invoer = {
    set files(f) { this._f = f; },
    get files() { return this._f; },
    dispatchEvent() {
      staat.aanbiedingen++;
      const n = this._f.length;
      const ids = Array.from({ length: n }, (_, i) => `id-${staat.aanbiedingen}-${i}`).join(",");
      if (scenario === "lukt") staat.veld = ids;
      else if (scenario === "faalt") staat.veld = "";
      else if (scenario === "hangt") staat.veld = null;
      else if (scenario === "tweedekeer") staat.veld = staat.aanbiedingen >= 2 ? ids : "";
      else if (scenario === "deel") staat.veld = ids.split(",").slice(0, 3).join(",");
      else if (scenario === "druppel") staat.druppel = ids.split(",");
      return true;
    },
  };
  class NepDatum extends Date { static now() { return klok; } }
  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout: (f, ms) => { klok += ms || 0; setImmediate(f); return 1; },
    clearTimeout() {},
    Date: NepDatum,
    Event: function (t) { this.type = t; },
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
    DataTransfer: function () { const l = []; this.items = { add: (f) => l.push(f) }; this.files = l; },
    File: function (delen, naam, opt) { this.name = naam; this.type = opt && opt.type; },
    fetch: async () => ({ ok: true, blob: async () => ({ type: "image/jpeg" }) }),
    location: { hostname: host, href: `https://${host}/plaats/1776/646` },
    chrome: { runtime: { sendMessage: (m, cb) => { staat.log.push(m.text || m.type); if (cb) cb(undefined); }, lastError: null } },
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false, innerText: "" },
    querySelectorAll: (sel) => (sel === "img" ? [] : []),
    querySelector: (sel) => {
      if (sel === 'input[name="images.ids"]') {
        if (staat.druppel) {
          // elke keer dat er gekeken wordt is er een foto meer binnen
          staat.gezien = (staat.gezien || 0) + 1;
          return { value: staat.druppel.slice(0, Math.min(staat.druppel.length, Math.floor(staat.gezien / 3))).join(",") };
        }
        return staat.veld === null ? null : { value: staat.veld };
      }
      if (sel === '#imageUploader-hiddenInput' || /input\[type="file"\]/.test(sel)) return invoer;
      return null;
    },
    getElementById: () => null,
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  vm.createContext(zand);
  vm.runInContext(BRON, zand, { filename: "shared.js" });
  return { CL: zand.window.CL, staat };
}

async function plaats(scenario, aantal, host) {
  const { CL, staat } = laad(scenario, host);
  const urls = Array.from({ length: aantal }, (_, i) => `https://img.omnivaleur.com/x/imported/${i}.jpg`);
  await CL.uploadPhotos(urls);
  try {
    await CL.submitListing(/marktplaats\.nl\/v\/[^/]+\/(m\d+)/);
    return { fout: "", staat };
  } catch (e) {
    return { fout: String(e && e.message || e), staat };
  }
}

const hadGeplaatst = (r) => /publish button could not be found/.test(r.fout);

(async () => {
  console.log(oud ? `Tegen ${VOOR_DE_REPARATIE} (vóór de reparatie):` : "Tegen de huidige shared.js:");

  const faalt = await plaats("faalt", 13);
  check("mislukte upload: niet geplaatst", !hadGeplaatst(faalt), `fout was: ${faalt.fout.slice(0, 90)}`);
  check("mislukte upload: melding noemt de foto's", /photo/i.test(faalt.fout), faalt.fout.slice(0, 90));
  check("mislukte upload: één keer opnieuw aangeboden", faalt.staat.aanbiedingen === 2, `aanbiedingen: ${faalt.staat.aanbiedingen}`);

  const hangt = await plaats("hangt", 5);
  check("hangende upload: niet geplaatst", !hadGeplaatst(hangt), `fout was: ${hangt.fout.slice(0, 90)}`);
  check("hangende upload: melding zegt dat het uploaden nog liep", /still uploading/i.test(hangt.fout), hangt.fout.slice(0, 90));

  const tweede = await plaats("tweedekeer", 13);
  check("tweede aanbieding lukt: wél geplaatst", hadGeplaatst(tweede), `fout was: ${tweede.fout.slice(0, 90)}`);

  const lukt = await plaats("lukt", 13);
  check("gewone upload: geplaatst", hadGeplaatst(lukt), `fout was: ${lukt.fout.slice(0, 90)}`);
  check("gewone upload: niet opnieuw aangeboden", lukt.staat.aanbiedingen === 1, `aanbiedingen: ${lukt.staat.aanbiedingen}`);

  const deel = await plaats("deel", 13);
  check("deels gelukt: wel geplaatst, zonder opnieuw aanbieden (anders dubbele foto's)", hadGeplaatst(deel) && deel.staat.aanbiedingen === 1, `fout: ${deel.fout.slice(0, 60)}, aanbiedingen ${deel.staat.aanbiedingen}`);

  const dr = await plaats("druppel", 13);
  const laatste = dr.staat.log.filter((r) => /op het formulier:/.test(r)).pop() || "";
  check("foto's druppelen binnen: pas plaatsen als alle 13 er zijn", hadGeplaatst(dr) && /13 van 13/.test(laatste), laatste);

  const dh = await plaats("faalt", 4, "www.2dehands.be");
  check("2dehands, mislukte upload: niet geplaatst", !hadGeplaatst(dh), `fout was: ${dh.fout.slice(0, 90)}`);

  // Vinted heeft dit veld niet: daar mag deze controle niets tegenhouden.
  const vi = await plaats("hangt", 4, "www.vinted.nl");
  check("Vinted: deze controle houdt niets tegen", !/still uploading|did not accept/i.test(vi.fout), vi.fout.slice(0, 90));

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})();
