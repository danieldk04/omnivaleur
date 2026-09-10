/**
 * Egbert Brouwer (Papa's Plectrums), 10-09-2026:
 * "Alles staat op bieden toestaan, ik werk met vaste prijzen en ga niet
 *  onderhandelen over de prijs."
 *
 * NAGEMETEN, LIVE, OP ZIJN EIGEN ZOEKERTJES. Via de openbare zoek-API van
 * 2dehands (sellerIds[]=27364566) stonden op 10-09-2026 elf van de elf
 * zoekertjes op priceType MIN_BID — dat is een vraagprijs MET "bieden vanaf".
 * Zijn 3.000 Marktplaats-advertenties staan wel gewoon op FIXED.
 *
 * DE OORZAAK. Wij zetten bieden niet aan; wij zetten het nooit UIT. De
 * schakelaar input#syi-bidding-switch-input ("Bieden toestaan") staat op het
 * plaatsformulier standaard aan, en fillBidding werd alleen aangeroepen als de
 * verkoper zelf een minimumbod had ingevuld. Deed hij dat niet — zijn vinkje
 * "Allow bidding" in het dashboard staat standaard uit — dan raakten we de
 * schakelaar helemaal niet aan.
 *
 * Deze proef draait de ECHTE code uit shared.js op een nagemaakt formulier met
 * die schakelaar erop, en doet dat twee keer: met de versie zoals hij nu in de
 * map staat, en met de versie van vóór de reparatie (vaste commit af816f80 —
 * NIET HEAD, want de auto-push-hook commit werk in uitvoering onder
 * "auto: update ...", en dan bevat HEAD de reparatie al).
 *
 * Draaien: node tests/bieden-toestaan-uit-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "af816f80";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── Het formulier zoals Marktplaats/2dehands het aanbiedt ────────────────
// De schakelaar staat AAN als je op het formulier komt; dat is de hele reden
// dat deze proef bestaat.
function maakFormulier() {
  const schakelaar = {
    tagName: "INPUT", type: "checkbox", id: "syi-bidding-switch-input",
    checked: true,
    click() { this.checked = !this.checked; },
  };
  // Het bedragveld schrijft via de native value-setter, net als het echte
  // formulier — vandaar accessors in plaats van een gewone eigenschap.
  const bedrag = {
    tagName: "INPUT", type: "text", name: "price.minimumBidPrice", _v: "",
    get value() { return this._v; }, set value(v) { this._v = String(v); },
    dispatchEvent() {}, focus() {}, blur() {},
    setSelectionRange() {}, getBoundingClientRect: () => ({ top: 0, left: 0 }),
  };
  return { schakelaar, bedrag };
}

function laadCL(formulier) {
  const bron = fs.readFileSync(path.join(WORTEL, "extension", "content", "shared.js"), "utf8");
  return draai(bron, formulier);
}

function laadOudeCL(formulier) {
  const bron = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`,
    { cwd: WORTEL, encoding: "utf8", maxBuffer: 40 * 1024 * 1024 });
  return draai(bron, formulier);
}

function draai(bron, formulier) {
  const document = {
    querySelector(sel) {
      if (!formulier) return null;
      if (sel === "input#syi-bidding-switch-input") return formulier.schakelaar;
      if (sel === '#syi-bidding-switch input[type="checkbox"]') return formulier.schakelaar;
      if (sel === 'input[name="price.minimumBidPrice"]') return formulier.bedrag;
      return null;
    },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    documentElement: {}, contains() { return true; }, body: { innerText: "" },
  };
  const sandbox = {
    console: { log() {}, warn() {} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    document,
    MutationObserver: class { observe() {} disconnect() {} },
    Event: class { constructor(t) { this.type = t; } },
    KeyboardEvent: class { constructor(t) { this.type = t; } },
    InputEvent: class { constructor(t) { this.type = t; } },
    // De achtergrond is er in deze proef niet: elke echte-klik-terugval loopt
    // hier dus dood, en dat is precies goed — we willen weten of de gewone weg
    // het al doet.
    chrome: { runtime: { sendMessage(msg, cb) { if (cb) cb("niet bereikbaar"); } } },
  };
  sandbox.window = sandbox;
  sandbox.window.HTMLSelectElement = class { };
  sandbox.window.HTMLInputElement = function () {};
  sandbox.window.HTMLInputElement.prototype = {};
  Object.defineProperty(sandbox.window.HTMLInputElement.prototype, "value", {
    set(v) { this._v = String(v); }, get() { return this._v; }, configurable: true,
  });
  sandbox.window.HTMLTextAreaElement = function () {};
  sandbox.window.HTMLTextAreaElement.prototype = {};
  Object.defineProperty(sandbox.window.HTMLTextAreaElement.prototype, "value", {
    set(v) { this._v = v; }, get() { return this._v; }, configurable: true,
  });
  vm.createContext(sandbox);
  vm.runInContext(bron, sandbox);
  return sandbox.window.CL;
}

(async () => {
  console.log("\nNU (de code zoals hij in de map staat)");

  // 1. Vaste prijs, geen bieden gewild → de schakelaar moet UIT.
  {
    const f = maakFormulier();
    const CL = laadCL(f);
    check("zetBieden bestaat", typeof CL.zetBieden === "function");
    const uit = await CL.zetBieden({ price: 17.95, bid_percentage: null });
    check("bieden toestaan gaat uit bij een vaste prijs",
      f.schakelaar.checked === false && uit === true,
      `schakelaar staat ${f.schakelaar.checked ? "AAN" : "uit"}, uitkomst ${uit}`);
  }

  // 2. Verkoper wil WEL bieden → de schakelaar blijft aan en het minimumbod
  //    wordt ingevuld. De reparatie mag die keuze niet omkeren.
  {
    const f = maakFormulier();
    const CL = laadCL(f);
    await CL.zetBieden({ price: 100, bid_percentage: 70 });
    check("bieden toestaan blijft aan als de verkoper het aanvinkte",
      f.schakelaar.checked === true, "de schakelaar werd uitgezet");
    check("minimumbod ingevuld op 70% van 100", f.bedrag.value === "70,00",
      `veld bevat "${f.bedrag.value}"`);
  }

  // 3. Advertentie zonder vraagprijs is zelf een bied-advertentie: met rust laten.
  {
    const f = maakFormulier();
    const CL = laadCL(f);
    const uit = await CL.zetBieden({ price: 0, bid_percentage: null });
    check("een advertentie zonder prijs wordt met rust gelaten",
      uit === null && f.schakelaar.checked === true,
      `uitkomst ${uit}, schakelaar ${f.schakelaar.checked ? "aan" : "UIT"}`);
  }

  // 4. Stond de schakelaar al uit, dan blijft hij uit (en gaat hij niet AAN).
  {
    const f = maakFormulier();
    f.schakelaar.checked = false;
    const CL = laadCL(f);
    await CL.zetBieden({ price: 12.95, bid_percentage: null });
    check("een schakelaar die al uit staat blijft uit", f.schakelaar.checked === false);
  }

  console.log(`\nVÓÓR DE REPARATIE (commit ${VOOR_DE_REPARATIE})`);
  {
    const f = maakFormulier();
    const CL = laadOudeCL(f);
    check("de oude code kende zetBieden niet", typeof CL.zetBieden !== "function",
      "zetBieden bestond toen al — dan meet deze proef niets");
    // Precies doen wat de oude marktplaats.js/tweedehands.js deden:
    //   item.bid_percentage && Number(item.price) > 0 && fillBidding(...)
    const item = { price: 17.95, bid_percentage: null };
    if (item.bid_percentage && Number(item.price) > 0) {
      await CL.fillBidding(item.price, item.bid_percentage);
    }
    check("de oude code liet 'bieden toestaan' AAN staan — dit is de klacht",
      f.schakelaar.checked === true,
      "de oude code zette hem al uit; dan verklaart deze reparatie de klacht niet");
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
  process.exit(mislukt ? 1 : 0);
})();
