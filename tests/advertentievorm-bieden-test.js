/**
 * "Bieden" in plaats van een lege vraagprijs — met de oude code ernaast.
 *
 * WAAROM DIT ER IS (03-09-2026, Amanda Haas). Zij mailde: "Als er advertenties
 * met 'geen vraagprijs, maar bieden' opnieuw worden geplaatst blijft het
 * programma hier in hangen en gaat deze niet verder. Dat betekent dus dat ik de
 * hele tijd bij de pc in de buurt moet blijven."
 *
 * Gemeten in haar eigen gegevens (03-09-2026): 179 van haar 479 artikelen
 * hebben geen vraagprijs, en van de 168 die op Marktplaats terug te vinden zijn
 * staan er 161 als "Bieden" (FAST_BID) en 1 als "Gratis". Haar opdrachtenlog
 * gaf letterlijk terug:
 *   "Not published — complete the fields marked in red and click publish
 *    yourself. € | Geen prijs ingevuld. | Fields marked invalid: price.value=LEEG"
 *   "Je hebt geen advertentievorm gekozen."
 * Elf van haar advertenties waren daardoor helemaal weg: het verwijderen was
 * gelukt, het opnieuw plaatsen niet.
 *
 * Deze proef draait de ECHTE shared.js tegen een nagebouwd plaatsformulier dat
 * precies die twee klachten geeft, en laat de oude weg (alleen mpPrijs, de
 * keuzelijst onaangeroerd) er onder dezelfde omstandigheden op vallen.
 *
 * Draaien:  node tests/advertentievorm-bieden-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

let mislukt = 0;
function ok(voorwaarde, wat) {
  if (voorwaarde) { console.log("  ✓", wat); return; }
  console.log("  ✗", wat); mislukt++;
}

// ── Een minimaal formulier dat zich gedraagt als het echte ────────────────────
class FakeSelect {
  constructor(id, opties) {
    this.tagName = "SELECT";
    this.id = id;
    this._v = opties[0].value;          // Marktplaats begint op "Vraagprijs"
    this.options = opties.map((o) => ({ ...o, disabled: false }));
    this.events = [];
    // React zet een waarde die hij niet aannam terug (zie kiesPrijsvorm).
    this.weigert = null;
  }
  dispatchEvent(e) {
    this.events.push(e && e.type);
    if (this.weigert && this._v === this.weigert) this._v = this.options[0].value;
    // Het echte formulier haalt het prijsveld weg bij een vorm zonder bedrag.
    if (this.formulier) this.formulier.prijsWeg = this._v !== "FIXED";
    return true;
  }
}
Object.defineProperty(FakeSelect.prototype, "value", {
  get() { return this._v; },
  set(v) { this._v = String(v); },
  configurable: true,
});

class FakeInput {
  constructor(naam) { this.tagName = "INPUT"; this.name = naam; this.type = "text"; this.value = ""; }
  dispatchEvent() { return true; }
}

// LETTERLIJK OVERGENOMEN VAN HET ECHTE, INGELOGDE PLAATSFORMULIER (03-09-2026),
// in twee categorieën gemeten (kleding 621/636 en Huis en Inrichting > Servies
// 504/1262, de hoek waarin Amanda verkoopt). Allebei exact deze vier en verder
// geen. Op het echte formulier verdween het prijsveld zodra "Bieden" gekozen
// werd, en React nam de keuze aan — precies wat kiesPrijsvorm hieronder doet.
const MP_OPTIES = [
  { text: "Vraagprijs", value: "FIXED" },
  { text: "Bieden", value: "FAST_BID" },
  { text: "Zie omschrijving", value: "SEE_DESCRIPTION" },
  { text: "Gratis", value: "FREE" },
];

function nieuwFormulier(opties = MP_OPTIES) {
  const select = new FakeSelect("Dropdown-prijstype", opties);
  const prijs = new FakeInput("price.value");
  const f = { select, prijs, prijsWeg: false };
  select.formulier = f;
  return f;
}

// Wat Marktplaats zelf doet als je op "Plaats je advertentie" klikt. De twee
// klachten hieronder staan letterlijk in Amanda's mislukte opdrachten.
function marktplaatsPlaatst(f) {
  if (!f.select.value) return { geplaatst: false, klacht: "Je hebt geen advertentievorm gekozen." };
  const heeftBedrag = f.select.value === "FIXED" || f.select.value === "MIN_BID";
  if (heeftBedrag && !String(f.prijs.value).trim()) {
    return { geplaatst: false, klacht: "Geen prijs ingevuld." };
  }
  return { geplaatst: true };
}

// ── De echte shared.js laden ─────────────────────────────────────────────────
function laadCL(formulier) {
  const bron = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "shared.js"), "utf8");
  const document = {
    querySelector(sel) {
      if (!formulier) return null;
      if (sel === "select#Dropdown-prijstype") return formulier.select;
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
  vm.createContext(sandbox);
  vm.runInContext(bron, sandbox);
  return sandbox.window.CL;
}

(async () => {
  console.log("\n1. Welke advertentievorm hoort bij dit artikel?");
  const CL = laadCL(null);
  const vorm = (item) => CL.mpPrijsvorm(item);
  ok(vorm({ price: 12.5 }) === null, "met vraagprijs blijft het formulier onaangeraakt (geen enkel verschil met vandaag)");
  ok(vorm({ price: 12.5, mp_prijstype: { soort: "FAST_BID" } }) === null,
     "een echte prijs wint: die gooien we nooit weg voor een oude vorm");
  ok(vorm({ price: 0 }) === "Bieden", "geen prijs en niets bekend → Bieden");
  ok(vorm({ price: null }) === "Bieden", "prijs ontbreekt helemaal → Bieden");
  ok(vorm({ price: 0, mp_prijstype: { soort: "FAST_BID" } }) === "Bieden", "de advertentie stond op Bieden → Bieden");
  ok(vorm({ price: 0, mp_prijstype: { soort: "FREE" } }) === "Gratis", "stond op Gratis → Gratis");
  ok(vorm({ price: 0, mp_prijstype: { soort: "SEE_DESCRIPTION" } }) === "Zie omschrijving", "stond op Zie omschrijving → idem");
  ok(vorm({ price: 0, mp_prijstype: { soort: "FIXED" } }) === "Bieden",
     "stond op vraagprijs maar er ís geen prijs → Bieden (anders weigert het formulier)");

  console.log("\n2. De oude weg, op een echte bied-advertentie van Amanda");
  {
    const f = nieuwFormulier();
    const CL2 = laadCL(f);
    // Precies wat marktplaats.js tot vandaag deed: alleen het prijsveld vullen.
    f.prijs.value = CL2.mpPrijs(0, f.prijs);
    const uit = marktplaatsPlaatst(f);
    ok(uit.geplaatst === false && uit.klacht === "Geen prijs ingevuld.",
       "oude code: Marktplaats weigert met 'Geen prijs ingevuld.' — precies haar foutmelding");
    ok(f.select.value === "FIXED", "oude code: de advertentievorm bleef op Vraagprijs staan");
  }

  console.log("\n3. Dezelfde advertentie met de nieuwe weg");
  {
    const f = nieuwFormulier();
    const CL3 = laadCL(f);
    const item = { price: 0, mp_prijstype: { soort: "FAST_BID" } };
    const gekozen = CL3.mpPrijsvorm(item);
    await CL3.kiesPrijsvorm(gekozen);
    if (!CL3.MP_ZONDER_BEDRAG.has(gekozen)) f.prijs.value = CL3.mpPrijs(item.price, f.prijs);
    const uit = marktplaatsPlaatst(f);
    ok(f.select.value === "FAST_BID", "de lijst staat nu op Bieden");
    ok(f.prijs.value === "", "en het prijsveld blijft leeg — bij Bieden hoort geen bedrag");
    ok(uit.geplaatst === true, "Marktplaats plaatst de advertentie");
  }

  console.log("\n4. Een artikel mét prijs verandert niet");
  {
    const f = nieuwFormulier();
    const CL4 = laadCL(f);
    const item = { price: 12.5 };
    const gekozen = CL4.mpPrijsvorm(item);
    ok(gekozen === null, "er wordt niets gekozen");
    f.prijs.value = CL4.mpPrijs(item.price, f.prijs);
    ok(f.prijs.value === "12,50", "de prijs staat er nog precies zo in als eerst");
    ok(f.select.events.length === 0, "de keuzelijst is niet eens aangeraakt");
    ok(marktplaatsPlaatst(f).geplaatst === true, "en de advertentie gaat online");
  }

  console.log("\n5. Heet de keuze bij Marktplaats anders, dan zegt de fout wélke keuzes er zijn");
  {
    const f = nieuwFormulier([
      { text: "Vaste prijs", value: "FIXED" },
      { text: "Bod", value: "FAST_BID" },
    ]);
    const CL5 = laadCL(f);
    await CL5.kiesPrijsvorm("Bieden");
    ok(f.select.value === "FAST_BID", "andere tekst, zelfde waarde: hij vindt hem alsnog op FAST_BID");
  }
  {
    const f = nieuwFormulier([
      { text: "Vaste prijs", value: "AAA" },
      { text: "Onderhandelbaar", value: "BBB" },
    ]);
    const CL6 = laadCL(f);
    let fout = null;
    try { await CL6.kiesPrijsvorm("Bieden"); } catch (e) { fout = e; }
    ok(fout !== null, "onbekende lijst: het plaatsen stopt in plaats van te stranden op een lege prijs");
    ok(/Vaste prijs \(AAA\)/.test(fout.message) && /Onderhandelbaar \(BBB\)/.test(fout.message),
       "en de foutmelding noemt de échte keuzes, dus de volgende melding wijst zichzelf aan");
  }

  console.log("\n6. Springt het formulier terug, dan weten we dat");
  {
    const f = nieuwFormulier();
    f.weigert = "FAST_BID";
    f.select.weigert = "FAST_BID";
    const CL7 = laadCL(f);
    let fout = null;
    try { await CL7.kiesPrijsvorm("Bieden"); } catch (e) { fout = e; }
    ok(fout !== null && /snapped back/.test(fout.message), "een geweigerde keuze wordt gemeld, niet genegeerd");
  }

  console.log("\n7. Geen keuzelijst op het formulier");
  {
    const CL8 = laadCL(null);
    let fout = null;
    try { await CL8.kiesPrijsvorm("Bieden"); } catch (e) { fout = e; }
    ok(fout !== null && /listing-type dropdown/.test(fout.message),
       "dan stopt het met een uitleg in plaats van een advertentie kwijt te raken");
  }

    console.log("\n8. Het prijsveld verdwijnt bij Bieden, net als op het echte formulier");
  {
    const f = nieuwFormulier();
    const CL9 = laadCL(f);
    await CL9.kiesPrijsvorm("Bieden");
    ok(f.prijsWeg === true, "het formulier haalt het prijsveld weg");
    // De invulstap slaat de prijs over; zou hij het tóch proberen, dan is er niets.
    ok(CL9.MP_ZONDER_BEDRAG.has("Bieden"), "en onze invulstap slaat de prijs dus over");
  }

  console.log("\n9. Een vorm die Marktplaats niet aanbiedt valt terug op Bieden");
  {
    // Marktplaats biedt maar vier vormen aan; "Gereserveerd" staat er niet bij.
    // Zonder terugval zou zo'n advertentie stranden op een leeg prijsveld.
    const f = nieuwFormulier();
    const CL10 = laadCL(f);
    const gekozen = CL10.mpPrijsvorm({ price: 0, mp_prijstype: { soort: "RESERVED" } });
    ok(gekozen === "Gereserveerd", "we vragen eerst om zijn eigen vorm");
    await CL10.kiesPrijsvorm(gekozen);
    ok(f.select.value === "FAST_BID", "die staat er niet, dus wordt het Bieden in plaats van een mislukking");
    ok(marktplaatsPlaatst(f).geplaatst === true, "en de advertentie gaat gewoon online");
  }

console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} proef(en) mislukt.\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
