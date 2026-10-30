/**
 * Mieneke (Voordeelsieraden), 30-10-2026: "bij alle items standaard het vinkje
 * Bieden toestaan aan, met bieden vanaf 0."
 *
 * Zonder instelling zet zetBieden "bieden toestaan" UIT voor elk artikel zonder
 * eigen minimumbod (Egbert, 10-09-2026). Met de instelling bieden_standaard "aan"
 * blijft hij AAN en blijft "Bieden vanaf" leeg (= vanaf 0), ook als het formulier
 * de schakelaar van de vorige keer onthield (uit) of een oud bedrag vasthoudt.
 *
 * Deze proef draait de ECHTE code uit shared.js op een nagemaakt formulier, en
 * dezelfde opdracht tegen de versie van vóór de wijziging (vast nummer, NIET HEAD).
 *
 * Draaien: node tests/bieden-standaard-aan-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR = "cd5f3b2d";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function maakFormulier({ aan = true, bedrag = "" } = {}) {
  const schakelaar = {
    tagName: "INPUT", type: "checkbox", id: "syi-bidding-switch-input", checked: aan,
    click() { this.checked = !this.checked; },
  };
  const veld = {
    tagName: "INPUT", type: "text", name: "price.minimumBidPrice", _v: bedrag,
    get value() { return this._v; }, set value(v) { this._v = String(v); },
    dispatchEvent() {}, focus() {}, blur() {},
    setSelectionRange() {}, getBoundingClientRect: () => ({ top: 0, left: 0 }),
  };
  return { schakelaar, bedrag: veld };
}

function draai(bron, formulier) {
  const document = {
    querySelector(sel) {
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
    setTimeout, clearTimeout, setInterval, clearInterval, document,
    MutationObserver: class { observe() {} disconnect() {} },
    Event: class { constructor(t) { this.type = t; } },
    KeyboardEvent: class { constructor(t) { this.type = t; } },
    InputEvent: class { constructor(t) { this.type = t; } },
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

const NU = fs.readFileSync(path.join(WORTEL, "extension", "content", "shared.js"), "utf8");
const OUD = execSync(`git show ${VOOR}:extension/content/shared.js`,
  { cwd: WORTEL, encoding: "utf8", maxBuffer: 40 * 1024 * 1024 });

(async () => {
  console.log("\nNU");

  { // 1. De schakelaar staat aan: hij blijft aan, het veld blijft leeg.
    const f = maakFormulier();
    const uit = await draai(NU, f).zetBieden({ price: 17.95, bid_percentage: null, bieden_standaard: "aan" });
    check("aan blijft aan", f.schakelaar.checked === true && uit === true, `uitkomst ${uit}`);
    check("bieden vanaf blijft leeg (= 0)", f.bedrag.value === "", `veld bevat "${f.bedrag.value}"`);
  }
  { // 2. Het formulier onthield uit: de instelling zet hem aan.
    const f = maakFormulier({ aan: false });
    const uit = await draai(NU, f).zetBieden({ price: 35, bid_percentage: null, bieden_standaard: "aan" });
    check("een schakelaar die uit stond gaat aan", f.schakelaar.checked === true && uit === true,
      `schakelaar ${f.schakelaar.checked ? "aan" : "UIT"}, uitkomst ${uit}`);
  }
  { // 3. Een oud bedrag in het veld (onthouden stand) wordt gewist: bieden vanaf 0.
    const f = maakFormulier({ aan: true, bedrag: "25,00" });
    await draai(NU, f).zetBieden({ price: 35, bid_percentage: null, bieden_standaard: "aan" });
    check("een oud minimumbod wordt gewist", f.bedrag.value === "", `veld bevat "${f.bedrag.value}"`);
  }
  { // 4. Een eigen minimumbod op het artikel gaat voor de instelling.
    const f = maakFormulier();
    await draai(NU, f).zetBieden({ price: 100, bid_percentage: 70, bieden_standaard: "aan" });
    check("eigen percentage gaat voor", f.schakelaar.checked === true && f.bedrag.value === "70,00",
      `veld bevat "${f.bedrag.value}"`);
  }
  { // 5. Zonder de instelling verandert er niets: vaste prijs, bieden gaat UIT.
    const f = maakFormulier();
    await draai(NU, f).zetBieden({ price: 17.95, bid_percentage: null });
    check("zonder instelling gaat bieden nog steeds uit", f.schakelaar.checked === false);
  }
  { // 6. 'volg' / ander woord doet niets bijzonders.
    const f = maakFormulier();
    await draai(NU, f).zetBieden({ price: 17.95, bid_percentage: null, bieden_standaard: "volg" });
    check("'volg' is gewoon de oude regel", f.schakelaar.checked === false);
  }
  { // 7. Een advertentie zonder vraagprijs blijft met rust.
    const f = maakFormulier({ aan: false });
    const uit = await draai(NU, f).zetBieden({ price: 0, bid_percentage: null, bieden_standaard: "aan" });
    check("zonder prijs met rust gelaten", uit === null && f.schakelaar.checked === false);
  }
  { // 8. Geen schakelaar op het formulier: geen storing.
    const uit = await draai(NU, { schakelaar: null, bedrag: null }).zetBieden(
      { price: 20, bid_percentage: null, bieden_standaard: "aan" }).catch((e) => "fout: " + e.message);
    check("geen schakelaar op het formulier geeft geen fout", uit === null, `uitkomst ${uit}`);
  }

  console.log(`\nVÓÓR DE WIJZIGING (commit ${VOOR})`);
  {
    const f = maakFormulier();
    await draai(OUD, f).zetBieden({ price: 17.95, bid_percentage: null, bieden_standaard: "aan" });
    check("de oude code zette bieden UIT, ook met de instelling — dit is de klacht",
      f.schakelaar.checked === false, "de oude code liet hem aan staan; dan meet deze proef niets");
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
  process.exit(mislukt ? 1 : 0);
})();
