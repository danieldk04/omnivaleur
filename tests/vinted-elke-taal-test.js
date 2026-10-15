/**
 * Janneke (31d28378), 15-10-2026:
 *   "Deze blijft haken. Ik denk weer door de categorie"
 *   "Het gaat echt wel beter, maar ik kan er nog niet blind op vertrouwen dat
 *    het geplaatst wordt."
 *
 * WAT HAAR OPDRACHTEN ZEGGEN. Elke Vinted-plaatsing bij haar meldt "stap
 * category: NIET gelukt". Op haar 29 geplaatste jassen en truien koos Vinted de
 * categorie zelf uit de foto: meisjesjassen bij Jongenskleding, en bij de
 * tienermaten (152) weigerde het formulier met "Kies een subcategorie" en "Vul
 * je maat in" (aceee8b4 en ccb9798e, 15-10 19:21 en 19:31 UTC).
 *
 * WAT ERONDER ZAT. De extensie kiest op Engelse namen ("Kids", "Girls
 * clothing"). Daniels Vinted staat in het Engels (html lang="en-NL"), haar
 * Vinted in het Nederlands ("Kinderen", "Meisjeskleding"). Dan raakt geen
 * enkele regel. Elke regel draagt wel een vast nummer (id="catalog-1195", in
 * de zoekresultaten "catalog-search-2548-result"), in elke taal hetzelfde.
 *
 * Deze proef bouwt Vinted's kiezer na uit de ECHTE boom (opgehaald op
 * 15-10-2026, in het Nederlands en het Engels, fixtures hieronder), laat de
 * echte categoriecode van de extensie erop los, en meet waar het artikel
 * terechtkomt. De oude code (ef85fbd3, extensie 1.0.389) moet hier falen.
 *
 * Draaien: node tests/vinted-elke-taal-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const NIEUW = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
const VOOR = "ef85fbd3";
const OUD = execFileSync("git", ["show", `${VOOR}:extension/content/vinted.js`], { cwd: WORTEL }).toString();
const boomUit = (taal) => JSON.parse(fs.readFileSync(
  path.join(WORTEL, "tests", "fixtures", `vinted_catalogus_${taal}_15-10-2026.json`), "utf8")).boom;
const BOOM = { nl: boomUit("nl"), en: boomUit("en") };

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function blokUit(bron, begin) {
  const i = bron.indexOf(begin);
  if (i < 0) throw new Error(`niet gevonden: ${begin}`);
  let j = bron.indexOf(begin.trim().endsWith("[") ? "[" : "{", i), diep = 0;
  const open = bron[j], dicht = open === "[" ? "]" : "}";
  for (; j < bron.length; j++) {
    if (bron[j] === open) diep++;
    else if (bron[j] === dicht) { diep--; if (diep === 0) return bron.slice(i, j + 1) + ";"; }
  }
  throw new Error(`geen einde: ${begin}`);
}
// Alles van vintedPathFor tot en met verifyCategory: daar staat de hele
// categoriekeuze, in beide versies in dezelfde volgorde.
function regio(bron) {
  const begin = bron.indexOf("  function vintedPathFor(cat, gender) {");
  const v = bron.indexOf("  function verifyCategory(", begin);
  let j = bron.indexOf("{", v), diep = 0;
  for (; j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}") { diep--; if (diep === 0) break; }
  }
  return bron.slice(begin, j + 1);
}

// ── Vinted's kiezer, nagebouwd ────────────────────────────────────────────
const kinderenVan = (boom) => {
  const k = {};
  for (const [id, [, ouder]] of Object.entries(boom)) (k[ouder] = k[ouder] || []).push(id);
  return k;
};
const KINDEREN = kinderenVan(BOOM.nl);
function padVan(boom, id) {
  const d = [];
  for (let n = boom[id], i = 0; n && i < 10; i++) { d.unshift(n[0]); n = boom[n[1]]; }
  return d;
}
function idVoorEngelsPad(delen) {
  let ouder = "0";
  for (const naam of delen) {
    const id = (KINDEREN[ouder] || []).find((i) => BOOM.en[i][0] === naam);
    if (!id) throw new Error(`geen Vinted-regel ${delen.join(" > ")}`);
    ouder = id;
  }
  return ouder;
}

function maakKiezer(taal, voorstelIds) {
  const boom = BOOM[taal];
  const veld = { value: "", focus() {}, click() { kiezer.open(); }, scrollIntoView() {} };
  let zicht = [];          // de regels die nu in beeld staan
  let gekozen = null;
  const cel = (id, soort) => {
    const titel = boom[id][0];
    const heeftKinderen = !!(KINDEREN[id] || []).length;
    const kruimel = soort === "boom" ? "" : padVan(boom, id).slice(0, -1).join(" > ");
    const radio = soort === "boom" ? null : { checked: false, id: "", click() {} };
    const e = {
      // Vinted's voorstellen dragen hier GEEN nummer: zo moet de vertaling ook
      // op naam plus kruimelpad lukken (de zoekresultaten dragen het wel).
      id: soort === "boom" ? `catalog-${id}` : soort === "zoek" ? `catalog-search-${id}-result` : "",
      className: "web_ui__Cell__cell web_ui__Cell__clickable",
      offsetParent: {}, parentElement: null, getClientRects: () => [1],
      _id: id, _kinderen: heeftKinderen, _soort: soort, _radio: radio,
      querySelector(sel) {
        if (/radio/.test(sel)) return radio;
        if (/Cell__title/.test(sel)) return { textContent: titel };
        if (/Cell__body/.test(sel)) return kruimel ? { textContent: kruimel } : null;
        return null;
      },
      querySelectorAll(sel) {
        if (/Cell__title/.test(sel)) return [{ textContent: titel }];
        return [];
      },
      closest() { return e; },
      get textContent() { return titel + kruimel; },
    };
    if (radio) radio.closest = () => e, radio.matches = () => true;
    return e;
  };
  const zoekvak = {
    placeholder: taal === "nl" ? "Zoek een categorie" : "Find a category",
    className: "web_ui__InputBar__value", offsetParent: {}, focus() {}, dispatchEvent() {},
    _zet(v) {
      const t = String(v || "").toLowerCase().trim();
      if (!t) return;
      zicht = Object.keys(boom).filter((id) => boom[id][0].toLowerCase().includes(t)).slice(0, 30)
        .map((id) => cel(id, "zoek"));
    },
  };
  const kiezer = {
    veld, zoekvak, gekozenId: () => gekozen, open: false, geklikt: [],
    open() {
      kiezer.isOpen = true;
      zicht = [...voorstelIds.map((id) => cel(id, "voorstel")), ...(KINDEREN["0"] || []).map((id) => cel(id, "boom"))];
    },
    klik(e) {
      if (e === veld) { kiezer.open(); return; }
      if (!e || e._id == null) return;
      kiezer.geklikt.push(boom[e._id][0]);
      if (e._radio) e._radio.checked = true;
      if (e._kinderen) { zicht = KINDEREN[e._id].map((id) => cel(id, "boom")); return; }
      gekozen = e._id; veld.value = boom[e._id][0]; zicht = []; kiezer.isOpen = false;
    },
    document: {
      documentElement: { lang: taal === "nl" ? "nl-NL" : "en-NL" },
      dispatchEvent() {},
      querySelector: (sel) => (/catalog-select-dropdown-input/.test(sel) ? veld : null),
      querySelectorAll(sel) {
        if (/input\[type="text"\]/.test(sel)) return kiezer.isOpen ? [veld, zoekvak] : [veld];
        if (/input\[type="radio"\]/.test(sel)) return zicht.map((e) => e._radio).filter(Boolean);
        if (/Cell__body|Cell__title|Cell__heading/.test(sel)) return [];
        if (/Cell/.test(sel)) return zicht;
        return [];
      },
    },
  };
  return kiezer;
}

function draai(bron, kiezer, item) {
  let klok = 1_000_000;
  function HTMLInputElement() {}
  Object.defineProperty(HTMLInputElement.prototype, "value", {
    set(v) { this._v = v; if (this._zet) this._zet(v); else this.value_ = v; },
    get() { return this._v; },
  });
  class Ev { constructor(type, o) { this.type = type; Object.assign(this, o || {}); } }
  const s = {
    document: kiezer.document,
    window: { HTMLInputElement },
    location: { origin: "https://www.vinted.nl" },
    chrome: { runtime: {
      lastError: null,
      sendMessage(msg, terug) {
        if (msg.type === "VINTED_CATALOGUS") terug(BOOM[msg.taal] || BOOM.en);
        else terug(null);
      },
    } },
    Event: Ev, KeyboardEvent: Ev, InputEvent: Ev, FocusEvent: Ev,
    Date: { now: () => klok },
    qs: (sel) => kiezer.document.querySelector(sel),
    sleep: async (ms) => { klok += ms || 0; },
    clog: () => {}, console: { log() {}, warn() {} },
    realClickEl: (e) => kiezer.klik(e),
  };
  vm.createContext(s);
  vm.runInContext([
    "var bladReden = null;",
    blokUit(bron, "const CAT_HINTS = {"),
    blokUit(bron, "const V_PAD = {"),
    blokUit(bron, "const ACCESSORY_TERMS = ["),
    blokUit(bron, "const V_KLEDING = {"),
    blokUit(bron, "const BLAD_VOORKEUR = ["),
    "const enkelvoud = (w) => (w.length > 4 && /s$/.test(w) && !/ss$/.test(w) ? w.slice(0, -1) : w);",
    regio(bron),
    "globalThis.__vul = fillCategoryVinted;",
  ].join("\n"), s);
  // De zoekvak-setter in typeSearch gaat via window.HTMLInputElement.
  Object.setPrototypeOf(kiezer.zoekvak, HTMLInputElement.prototype);
  return s.__vul(item).then((ok) => ({ ok, id: kiezer.gekozenId() }), (e) => ({ ok: false, fout: String(e) }));
}

const engels = (id) => (id ? padVan(BOOM.en, id).join(" > ") : "(niets gekozen)");
const isBlad = (id) => !!id && !(KINDEREN[id] || []).length;

(async () => {
  const DAMES_PARKA = idVoorEngelsPad(["Women", "Clothing", "Outerwear", "Coats", "Parkas"]);
  const JONGENS_FLEECE = idVoorEngelsPad(["Kids", "Boys clothing", "Outerwear", "Jackets", "Fleece jackets"]);
  const MEISJES_FLEECE = idVoorEngelsPad(["Kids", "Girls clothing", "Outerwear", "Jackets", "Fleece jackets"]);

  const gevallen = [
    {
      naam: "tienermeisje, Vinted gokt een damesparka (aceee8b4)",
      item: { title: "Tussenjas Only maat 152", description: "Nieuw met labels", title_en: "Transitional jacket Only size 152",
              category: "tieners meisjes", gender: "kinderen" },
      voorstel: [DAMES_PARKA], verwachtBegin: "Kids > Girls clothing > Outerwear > Jackets",
    },
    {
      naam: "meisjeskleding, Vinted gokt jongens-fleece",
      item: { title: "Tussenjas Noppies maat 134", description: "", title_en: "Transitional jacket Noppies size 134",
              category: "meisjes kleding", gender: "kinderen" },
      voorstel: [JONGENS_FLEECE], verwachtBegin: "Kids > Girls clothing > Outerwear > Jackets",
    },
    {
      naam: "babykleding (jongen of meisje onbekend), Vinted stelt jongens-fleece voor",
      item: { title: "Tussenjas Noppies maat 68", description: "", title_en: "Transitional jacket Noppies size 68",
              category: "babykleding", gender: "kinderen" },
      voorstel: [JONGENS_FLEECE], verwachtBegin: "Kids > Boys clothing > Outerwear > Jackets > Fleece jackets",
    },
    {
      naam: "jongenstrui zonder voorstel",
      item: { title: "Trui Lyle & Scott maat 110-116", description: "", title_en: "Sweater Lyle & Scott size 110-116",
              category: "jongens kleding", gender: "kinderen" },
      voorstel: [], verwachtBegin: "Kids > Boys clothing > Jumpers & hoodies",
    },
    {
      naam: "meisjesjas, Vinted stelt meisjes-fleece voor: dat voorstel volgen",
      item: { title: "Tussenjas Daily Seven maat 92", description: "", title_en: "Transitional jacket Daily Seven size 92",
              category: "meisjes kleding", gender: "kinderen" },
      voorstel: [MEISJES_FLEECE], verwachtBegin: "Kids > Girls clothing > Outerwear > Jackets > Fleece jackets",
    },
  ];

  for (const taal of ["nl", "en"]) {
    console.log(`\nVinted in het ${taal === "nl" ? "Nederlands (Janneke)" : "Engels (Daniel)"}`);
    for (const g of gevallen) {
      const nieuw = await draai(NIEUW, maakKiezer(taal, g.voorstel), { ...g.item });
      const pad = engels(nieuw.id);
      check(`nieuw: ${g.naam} → ${pad}`,
            isBlad(nieuw.id) && pad.startsWith(g.verwachtBegin),
            `verwacht een blad onder ${g.verwachtBegin}${nieuw.fout ? `, fout ${nieuw.fout}` : ""}`);
    }
  }

  console.log(`\nOude code (${VOOR}) op Janneke's Nederlandse Vinted: moet falen`);
  let oudGoed = 0;
  for (const g of gevallen) {
    const oud = await draai(OUD, maakKiezer("nl", g.voorstel), { ...g.item });
    const pad = engels(oud.id);
    const goed = isBlad(oud.id) && pad.startsWith(g.verwachtBegin);
    if (goed) oudGoed++;
    console.log(`  oud: ${g.naam} → ${pad}${oud.fout ? ` (${oud.fout})` : ""}`);
  }
  check("de oude code zet geen enkel geval goed", oudGoed === 0, `${oudGoed} goed`);

  console.log(mislukt ? `\n${mislukt} fout(en)` : "\nalles goed");
  process.exit(mislukt ? 1 : 0);
})();
