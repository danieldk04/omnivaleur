/**
 * De andere helft van de keten: doet het plaatsformulier ook echt wat de
 * opdracht vraagt?
 *
 * tests/prijsvorm-test.py bewijst dat een artikel met prijsvorm "Zie
 * omschrijving" gepubliceerd mág worden en dat de opdracht mp_prijstype
 * meedraagt. Dat zegt nog niets over het formulier. Deze proef draait de echte
 * zetPrijs uit extension/content/shared.js tegen een nagebouwd
 * Marktplaats-formulier, inclusief het gedrag dat het prijsveld bij een vorm
 * zonder bedrag helemaal uit de pagina verdwijnt — precies waar het op
 * 05-09-2026 stil op misging.
 *
 * Draaien: node tests/prijsvorm-formulier-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const BRON = fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// De vier keuzes die op het echte, ingelogde formulier staan (nagemeten
// 03-09-2026, zie MP_PRIJSVORM in shared.js).
const KEUZES = [
  { value: "FIXED", text: "Vraagprijs" },
  { value: "FAST_BID", text: "Bieden" },
  { value: "SEE_DESCRIPTION", text: "Zie omschrijving" },
  { value: "FREE", text: "Gratis" },
];
// Vormen waarbij Marktplaats het prijsveld uit het formulier haalt.
const ZONDER_PRIJSVELD = new Set(["FAST_BID", "SEE_DESCRIPTION", "FREE"]);

function bouwFormulier() {
  const staat = { log: [], prijsGevuld: null };

  const select = {
    tagName: "SELECT",
    _v: "SEE_DESCRIPTION",          // het formulier onthoudt de vorige advertentie
    options: KEUZES.map((k) => ({ ...k, disabled: false })),
    dispatchEvent() { return true; },
  };
  Object.defineProperty(select, "value", {
    get() { return this._v; },
    set(v) { this._v = v; },
  });

  const prijsveld = {
    tagName: "INPUT",
    _v: "",
    focus() {}, blur() {}, click() {}, select() {}, setSelectionRange() {},
    dispatchEvent() { return true; },
    getBoundingClientRect: () => ({ top: 0, left: 0, width: 10, height: 10 }),
    closest: () => null,
    setAttribute() {}, removeAttribute() {}, getAttribute: () => null,
  };
  Object.defineProperty(prijsveld, "value", {
    get() { return this._v; },
    set(v) { this._v = v; staat.prijsGevuld = String(v); },
  });

  return { staat, select, prijsveld };
}

function laad() {
  const { staat, select, prijsveld } = bouwFormulier();
  let klok = 1_000_000;
  class NepDatum extends Date { static now() { return klok; } }

  function prototypeMetWaarde() {
    const P = function () {};
    Object.defineProperty(P.prototype, "value", {
      configurable: true,
      get() { return this._v; },
      set(v) { this._v = v; if (this.tagName === "INPUT") staat.prijsGevuld = String(v); },
    });
    return P;
  }

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
    location: { hostname: "www.marktplaats.nl", href: "https://www.marktplaats.nl/plaats/1776/646" },
    chrome: { runtime: { sendMessage: (m, cb) => { staat.log.push(m.text || m.type); if (cb) cb(undefined); }, lastError: null } },
    HTMLSelectElement: prototypeMetWaarde(),
    HTMLInputElement: prototypeMetWaarde(),
    HTMLTextAreaElement: prototypeMetWaarde(),
  };
  zand.window = zand;
  zand.self = zand;
  zand.document = {
    body: { click() {}, contains: () => false, innerText: "" },
    querySelectorAll: () => [],
    querySelector: (sel) => {
      if (/Dropdown-prijstype|priceType|price\.priceType/.test(sel)) return select;
      if (sel === 'input[name="price.value"]') {
        // Zoals het echte formulier: bij een vorm zonder bedrag is dit veld er niet.
        return ZONDER_PRIJSVELD.has(String(select.value)) ? null : prijsveld;
      }
      return null;
    },
    getElementById: () => null,
    createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
    addEventListener() {},
  };
  vm.createContext(zand);
  vm.runInContext(BRON, zand, { filename: "shared.js" });
  return { CL: zand.window.CL, staat, select, prijsveld };
}

(async () => {
  console.log("De echte zetPrijs op een nagebouwd plaatsformulier:\n");

  // 1. Toons advertentie: geen bedrag, wel een vorm.
  {
    const { CL, select, staat } = laad();
    const fout = await CL.zetPrijs({ price: 0, mp_prijstype: { soort: "SEE_DESCRIPTION", cents: 0 } });
    check("zie omschrijving: het formulier staat op die vorm", select.value === "SEE_DESCRIPTION", select.value);
    check("zie omschrijving: er wordt geen bedrag ingevuld", staat.prijsGevuld === null, staat.prijsGevuld);
    check("zie omschrijving: geen fout", !fout, String(fout && fout.message));
  }

  // 2. Bieden, zoals 161 van Amanda's advertenties.
  {
    const { CL, select, staat } = laad();
    const fout = await CL.zetPrijs({ price: 0, mp_prijstype: { soort: "FAST_BID", cents: 0 } });
    check("bieden: het formulier staat op Bieden", select.value === "FAST_BID", select.value);
    check("bieden: er wordt geen bedrag ingevuld", staat.prijsGevuld === null, staat.prijsGevuld);
    check("bieden: geen fout", !fout, String(fout && fout.message));
  }

  // 3. Gratis.
  {
    const { CL, select } = laad();
    await CL.zetPrijs({ price: 0, mp_prijstype: { soort: "FREE", cents: 0 } });
    check("gratis: het formulier staat op Gratis", select.value === "FREE", select.value);
  }

  // 4. Een gewone vraagprijs moet de onthouden vorm van de vorige advertentie
  //    overschrijven. Dit is de fout die zestig advertenties zonder prijs
  //    opleverde (Zilverwebsite, 05-09-2026).
  {
    const { CL, select, staat } = laad();
    await CL.zetPrijs({ price: 25 });
    check("vraagprijs: de onthouden vorm wordt teruggezet naar Vraagprijs",
          select.value === "FIXED", select.value);
    check("vraagprijs: het bedrag staat in het veld",
          String(staat.prijsGevuld).replace(/[^0-9]/g, "").startsWith("25"), staat.prijsGevuld);
  }

  // 5. Zonder prijs en zonder vorm valt hij terug op Bieden: dat is de enige
  //    vorm die klopt bij een artikel zonder bedrag.
  {
    const { CL, select, staat } = laad();
    await CL.zetPrijs({ price: 0 });
    check("geen prijs en geen vorm: terugval op Bieden", select.value === "FAST_BID", select.value);
    check("geen prijs en geen vorm: geen bedrag ingevuld", staat.prijsGevuld === null, staat.prijsGevuld);
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})().catch((e) => { console.error("proef zelf stukgelopen:", e); process.exit(2); });
