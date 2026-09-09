/**
 * De prijs moet op het formulier staan — met de oude code ernaast.
 *
 * WAAROM DIT ER IS (05-09-2026, Zilverwebsite / Jaap). Hij mailde: "vanmorgen
 * het verversen aangezet ... helaas werd de prijs niet meegenomen en stond
 * overal 'zie omschrijving' onder. Deze hebben we allemaal handmatig weer
 * aangepast in marktplaats zelf." Ook een advertentie die hij daarna zelf
 * aanmaakte, mét prijs, kwam er zo uit.
 *
 * NAGEMETEN IN ZIJN EIGEN OPDRACHTEN (05-09-2026). De zestig plaatsingen van
 * die ochtend hadden allemaal gewoon een prijs (44,27 tot 1474,32) en prijsvorm
 * FIXED in de opdracht; in zijn laatste duizend plaatsingen heeft de extensie
 * zelf nooit "Zie omschrijving" gekozen. De vorm kwam dus niet uit onze
 * opdracht maar van het plaatsformulier: Marktplaats zet de vorm van de vorige
 * advertentie alvast klaar, en hij had één advertentie (een partij Delfts
 * blauw) op "Zie omschrijving" staan.
 *
 * En bij die vorm bestaat input[name="price.value"] niet. De oude code raakte
 * de keuzelijst niet aan zolang er een prijs was, vulde dus een veld dat er niet
 * was, kreeg netjes false terug, en plaatste de advertentie zonder prijs.
 *
 * Deze proef draait de ECHTE shared.js tegen een nagebouwd plaatsformulier dat
 * op "Zie omschrijving" begint, en laat de vorige versie (uit git) er onder
 * exact dezelfde omstandigheden op vallen.
 *
 * Draaien:  node tests/prijs-blijft-op-het-formulier-test.js
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

let mislukt = 0;
function ok(voorwaarde, wat) {
  if (voorwaarde) { console.log("  ✓", wat); return; }
  console.log("  ✗", wat); mislukt++;
}

// ── Het plaatsformulier, zoals het zich echt gedraagt ────────────────────────
// De vier keuzes zijn nagemeten op het echte, ingelogde formulier (03-09-2026,
// twee categorieën). Bij elke vorm behalve "Vraagprijs" haalt Marktplaats het
// prijsveld uit het formulier.
const MP_OPTIES = [
  { text: "Vraagprijs", value: "FIXED" },
  { text: "Bieden", value: "FAST_BID" },
  { text: "Zie omschrijving", value: "SEE_DESCRIPTION" },
  { text: "Gratis", value: "FREE" },
];

class FakeSelect {
  constructor(id, opties, start) {
    this.tagName = "SELECT";
    this.id = id;
    this.options = opties.map((o) => ({ ...o, disabled: false }));
    this._v = start || opties[0].value;
    this.events = [];
    this.weigert = null;
  }
  get selectedIndex() { return this.options.findIndex((o) => o.value === this._v); }
  dispatchEvent(e) {
    this.events.push(e && e.type);
    if (this.weigert && this._v === this.weigert) this._v = this.formulier.startvorm;
    if (this.formulier) this.formulier.prijsWeg = !["FIXED", "MIN_BID"].includes(this._v);
    return true;
  }
}
Object.defineProperty(FakeSelect.prototype, "value", {
  get() { return this._v; }, set(v) { this._v = String(v); }, configurable: true,
});

class FakeInput {
  constructor(naam) { this.tagName = "INPUT"; this.name = naam; this.type = "text"; this._v = ""; }
  dispatchEvent() { return true; }
}
Object.defineProperty(FakeInput.prototype, "value", {
  get() { return this._v; }, set(v) { this._v = String(v); }, configurable: true,
});

// startvorm: wat Marktplaats zelf al klaarzet. "SEE_DESCRIPTION" is de stand
// waar Jaap in terechtkwam.
function nieuwFormulier({ startvorm = "SEE_DESCRIPTION", opties = MP_OPTIES, lijst = true } = {}) {
  const select = lijst ? new FakeSelect("Dropdown-prijstype", opties, startvorm) : null;
  const f = { select, prijs: new FakeInput("price.value"), startvorm };
  f.prijsWeg = lijst ? !["FIXED", "MIN_BID"].includes(startvorm) : false;
  if (select) select.formulier = f;
  return f;
}

// Wat er op Marktplaats komt te staan als er op "Plaats je advertentie" wordt
// geklikt: de vorm die in de lijst staat, en de prijs alleen als die vorm er een
// heeft én het veld is ingevuld.
function watDeKoperZiet(f) {
  const vorm = f.select ? f.select.value : "FIXED";
  if (!["FIXED", "MIN_BID"].includes(vorm)) return "Zie omschrijving";
  const p = String(f.prijs.value || "").trim();
  return p ? `€ ${p}` : "(leeg prijsveld — Marktplaats weigert)";
}

// ── De echte shared.js laden (of de vorige versie uit git) ───────────────────
function laadCL(formulier, bron) {
  const document = {
    querySelector(sel) {
      if (!formulier) return null;
      if (sel === "select#Dropdown-prijstype" || sel === 'select[name="priceType"]'
          || sel === 'select[name="price.priceType"]') return formulier.select;
      if (sel === 'input[name="price.value"]') return formulier.prijsWeg ? null : formulier.prijs;
      return null;
    },
    querySelectorAll() { return []; },
    documentElement: {},
    contains() { return true; },
  };
  const sandbox = {
    console: { log() {} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    document,
    MutationObserver: class { observe() {} disconnect() {} },
    Event: class { constructor(type) { this.type = type; } },
    chrome: { runtime: { sendMessage() {} } },
  };
  sandbox.window = sandbox;
  sandbox.window.HTMLSelectElement = FakeSelect;
  sandbox.window.HTMLInputElement = FakeInput;
  sandbox.window.HTMLTextAreaElement = class {};
  vm.createContext(sandbox);
  vm.runInContext(bron, sandbox);
  return sandbox.window.CL;
}

const NU = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "shared.js"), "utf8");
// De vorige versie erbij halen: anders bewijst deze proef alleen dat de nieuwe
// code werkt, niet dat ze iets repareert.
//
// VAST COMMITNUMMER, EN MET OPZET. Hier stond `HEAD:`, en dat werkte precies
// één keer: zolang de reparatie nog niet gecommit was. Daarna wás HEAD de
// nieuwe code en vergeleek blok 1 de reparatie met zichzelf — vier rode
// regels, terwijl er niets kapot was. cb1358c0 is de commit die dit
// repareerde, dus cb1358c0^ is de code van vlak ervoor. Die verandert nooit
// meer, en dat is hier de bedoeling.
const VOOR_DE_REPARATIE = "cb1358c0^:extension/content/shared.js";
let OUD = null;
try {
  OUD = execFileSync("git", ["show", VOOR_DE_REPARATIE],
                     { cwd: path.join(__dirname, ".."), encoding: "utf8", maxBuffer: 8e6 });
} catch (e) {
  console.log("  (de vorige versie kon niet uit git gehaald worden:", e.message, ")");
}

(async () => {
  console.log("\n1. De oude code op Jaaps formulier (staat voorgezet op 'Zie omschrijving')");
  if (OUD) {
    const f = nieuwFormulier();
    const CL = laadCL(f, OUD);
    const item = { price: 550, mp_prijstype: { soort: "FIXED" } };
    // Letterlijk wat marktplaats.js tot vandaag deed.
    const vorm = CL.mpPrijsvorm(item);
    if (vorm) await CL.kiesPrijsvorm(vorm);
    if (!(vorm && CL.MP_ZONDER_BEDRAG.has(vorm))) {
      const el = f.prijsWeg ? null : f.prijs;
      if (el) el.value = CL.mpPrijs(item.price, el);
    }
    ok(vorm === null, "oude code: bij een prijs van 550 wordt er geen advertentievorm gekozen");
    ok(f.select.value === "SEE_DESCRIPTION", "oude code: de lijst blijft op 'Zie omschrijving' staan");
    ok(f.prijs.value === "", "oude code: het prijsveld bestaat niet, dus de prijs wordt stil overgeslagen");
    ok(watDeKoperZiet(f) === "Zie omschrijving",
       "oude code: de advertentie gaat online met 'Zie omschrijving' — precies Jaaps klacht");
  } else {
    ok(false, "de vorige versie kon niet geladen worden, dus de voor-en-na-proef is niet gedaan");
  }

  console.log("\n2. Dezelfde advertentie, hetzelfde formulier, met de nieuwe code");
  {
    const f = nieuwFormulier();
    const CL = laadCL(f, NU);
    const item = { price: 550, mp_prijstype: { soort: "FIXED" } };
    let fout = null;
    try { await CL.zetPrijs(item); } catch (e) { fout = e; }
    ok(fout === null, "het invullen verloopt zonder fout");
    ok(f.select.value === "FIXED", "de lijst wordt zelf op 'Vraagprijs' gezet in plaats van afgewacht");
    ok(f.prijs.value === "550,00", "en de prijs staat op het formulier");
    ok(watDeKoperZiet(f) === "€ 550,00", "de koper ziet € 550,00 in plaats van 'Zie omschrijving'");
  }

  console.log("\n3. Een formulier dat al goed stond verandert niet van uitkomst");
  {
    const f = nieuwFormulier({ startvorm: "FIXED" });
    const CL = laadCL(f, NU);
    let fout = null;
    try { await CL.zetPrijs({ price: 12.5 }); } catch (e) { fout = e; }
    ok(fout === null && f.select.value === "FIXED", "de lijst staat (nog steeds) op Vraagprijs");
    ok(f.prijs.value === "12,50", "en de prijs staat er precies zo in als eerst");
  }

  console.log("\n4. Een artikel zonder prijs blijft gewoon 'Bieden'");
  {
    const f = nieuwFormulier({ startvorm: "FIXED" });
    const CL = laadCL(f, NU);
    let fout = null;
    try { await CL.zetPrijs({ price: 0, mp_prijstype: { soort: "FAST_BID" } }); } catch (e) { fout = e; }
    ok(fout === null, "geen fout");
    ok(f.select.value === "FAST_BID", "de lijst gaat naar Bieden");
    ok(f.prijs.value === "", "en het prijsveld blijft leeg — bij Bieden hoort geen bedrag");
  }

  console.log("\n5. Een categorie zonder keuzelijst werkt zoals altijd");
  {
    const f = nieuwFormulier({ lijst: false });
    const CL = laadCL(f, NU);
    let fout = null;
    try { await CL.zetPrijs({ price: 99 }); } catch (e) { fout = e; }
    ok(fout === null, "geen keuzelijst is geen fout: dat was hiervoor ook zo");
    ok(f.prijs.value === "99,00", "de prijs wordt gewoon ingevuld");
  }

  console.log("\n6. Lukt het toch niet, dan gaat de advertentie NIET zonder prijs online");
  {
    // Het formulier weigert om te schakelen (React zet de keuze terug), dus het
    // prijsveld blijft weg. Dit is precies de situatie waarin de oude code
    // doorplaatste.
    const f = nieuwFormulier();
    f.select.weigert = "FIXED";
    const CL = laadCL(f, NU);
    let fout = null;
    try { await CL.zetPrijs({ price: 550 }); } catch (e) { fout = e; }
    ok(fout !== null, "het plaatsen stopt met een fout in plaats van stil door te gaan");
    ok(fout && /did not end up on the form/.test(fout.message), "de melding zegt dat de prijs er niet op staat");
    ok(fout && /Zie omschrijving/.test(fout.message), "en welke vorm het prijsveld verbergt");
  }

  console.log("\n7. 'Vraagprijs' valt nooit terug op 'Bieden'");
  {
    // Zou de terugval hier gelden, dan zou een artikel mét prijs op Bieden
    // eindigen: het prijsveld verdwijnt en de prijs is alsnog weg.
    const f = nieuwFormulier({ startvorm: "AAA", opties: [
      { text: "Onbekend", value: "AAA" }, { text: "Bieden", value: "FAST_BID" },
    ] });
    const CL = laadCL(f, NU);
    let fout = null;
    try { await CL.kiesPrijsvorm("Vraagprijs", { terugval: false }); } catch (e) { fout = e; }
    ok(fout !== null, "ontbreekt Vraagprijs, dan stopt het");
    ok(f.select.value !== "FAST_BID", "en wordt het zeker geen Bieden");
  }

  console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} proef(en) mislukt.\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
