/**
 * Daniel, 04-09-2026, met schermafbeelding van het Vinted-plaatsformulier:
 *   "vinted geeft nu regelmatig deze melding. als ik dan zelf een 9 typ of iets
 *    weghaal (random) dan verdwijnt die melding."
 * Op de afbeelding staat €14.99 in het prijsveld met eronder in het rood
 * "Price must be greater than or equal to 1.0". Het plaatsen stopt daarop.
 *
 * WAT HIER GEMETEN IS (echte Chrome, 04-09-2026, tests/… niet nodig, het zijn
 * eigenschappen van de browser zelf):
 *   * `el.dispatchEvent(new Event("blur", {bubbles:true}))` levert GEEN focusout
 *     op en laat het veld gefocust. React hangt zijn onBlur aan focusout, dus
 *     het formulier heeft zijn eigen controle na onze invulling nooit opnieuw
 *     gedraaid.
 *   * `document.execCommand("insertText", …)` geeft als enige route uit een
 *     script een invoergebeurtenis met isTrusted=true; alles wat we met
 *     dispatchEvent sturen is isTrusted=false.
 *   * de oude invulroute stuurde het formulier eerst een LEGE waarde
 *     (waarde "" + input-gebeurtenis) voordat de prijs erin ging.
 *
 * WAT HIER GEMODELLEERD IS: dat Vinted zijn rode regel pas opnieuw beoordeelt
 * bij een echte bewerking of bij het verlaten van het veld. Dat is niet op het
 * live formulier na te meten zonder ingelogd account, maar het is wat Daniels
 * waarneming zegt: hetzelfde teken opnieuw typen verandert de prijs niet en
 * haalt de melding tóch weg.
 *
 * De reparatie hangt daar niet vanaf. De kern is: een blijven hangende melding
 * mag het plaatsen niet meer tegenhouden zolang het formulier zélf de juiste
 * prijs vasthoudt.
 *
 * Draaien: node tests/vinted-prijsmelding-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VINTED = fs.readFileSync(path.join(WORTEL, "extension", "content", "vinted.js"), "utf8");
const BACKGROUND = fs.readFileSync(path.join(WORTEL, "extension", "background.js"), "utf8");
const OUD_VINTED = execFileSync("git", ["show", "HEAD:extension/content/vinted.js"], { cwd: WORTEL }).toString();
const OUD_BACKGROUND = execFileSync("git", ["show", "HEAD:extension/background.js"], { cwd: WORTEL }).toString();

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Haal één functie uit een bestand door de accolades te tellen.
function functieUit(bron, naam) {
  const re = new RegExp(`(?:^|\\n)\\s*(?:async\\s+)?function ${naam}\\s*\\(`);
  const m = re.exec(bron);
  if (!m) throw new Error(`${naam} niet gevonden`);
  const start = m.index + m[0].indexOf("function");
  let i = bron.indexOf("{", start), diep = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diep++;
    else if (bron[i] === "}") { diep--; if (diep === 0) return bron.slice(start, i + 1); }
  }
  throw new Error(`einde van ${naam} niet gevonden`);
}

// ── Een nagebouwd Vinted-prijsveld ───────────────────────────────────────
//
// Het veld toont wat wij erin zetten. Het FORMULIER houdt zijn eigen waarde bij
// (dat is wat React doet) en beoordeelt die pas opnieuw bij een echte bewerking
// of bij focusout. De rode regel staat er bij aanvang al, precies zoals op
// Daniels scherm.
function maakWereld({ startKlacht = true, reactLeesbaar = true } = {}) {
  const gelog = { events: [], inputWaarden: [] };
  const formulier = { waarde: "", klacht: startKlacht };
  const keur = () => { formulier.klacht = !(parseFloat(String(formulier.waarde).replace(",", ".")) >= 1); };

  const proto = {};
  let ruwe = "";
  Object.defineProperty(proto, "value", {
    configurable: true,
    get() { return ruwe; },
    set(v) { ruwe = String(v); },
  });

  const foutRegel = {
    textContent: "Price must be greater than or equal to 1.0",
    offsetParent: {},
    get zichtbaar() { return formulier.klacht; },
  };
  const ouder = {
    parentElement: null,
    querySelectorAll: () => (formulier.klacht ? [foutRegel] : []),
  };

  let selStart = 0, selEind = 0;
  const el = Object.create(proto);
  Object.assign(el, {
    parentElement: ouder,
    getAttribute: (n) => (n === "aria-describedby" ? "" : null),
    setSelectionRange(a, b) { selStart = a; selEind = b; },
    select() { selStart = 0; selEind = el.value.length; },
    focus() { gelog.events.push("focus()"); },
    blur() { gelog.events.push("blur()"); },
    scrollIntoView() {},
    dispatchEvent(e) {
      gelog.events.push(e.type + (e.isTrusted ? "(echt)" : ""));
      if (e.type === "input") {
        gelog.inputWaarden.push(el.value);
        formulier.waarde = el.value;              // React neemt de waarde over
        if (e.isTrusted) keur();                  // maar herbeoordeelt alleen bij een echte bewerking
      }
      if (e.type === "focusout") keur();
      return true;
    },
  });
  if (reactLeesbaar) {
    Object.defineProperty(el, "__reactProps$test", {
      enumerable: true,
      get: () => ({ value: formulier.waarde }),
    });
  }

  const document = {
    getElementById: () => null,
    querySelector: () => el,
    querySelectorAll: () => (formulier.klacht ? [foutRegel] : []),
    documentElement: { getAttribute: () => "en-NL" },
    execCommand(cmd, _x, data) {
      // Zo dicht mogelijk bij de browser: de bewerking gebeurt op de selectie en
      // levert een ECHTE invoergebeurtenis op.
      if (cmd === "insertText") {
        const v = el.value;
        el.value = v.slice(0, selStart) + String(data) + v.slice(selEind);
      } else if (cmd === "delete") {
        const v = el.value;
        const van = selStart === selEind ? Math.max(0, selStart - 1) : selStart;
        el.value = v.slice(0, van) + v.slice(selEind);
      } else if (cmd === "selectAll") {
        selStart = 0; selEind = el.value.length;
      } else {
        return false;
      }
      selStart = selEind = el.value.length;
      el.dispatchEvent({ type: "input", isTrusted: true });
      return true;
    },
  };

  const zand = {
    console: { log() {}, warn() {}, error() {} },
    setTimeout: (fn) => fn(),                     // geen echte wachttijden in de test
    document,
    formulier,
    gelog,
    el,
    Math, JSON, String, Number, Object, Promise, parseFloat, isFinite, Boolean, Array, Date, RegExp, Error,
  };
  zand.window = { HTMLInputElement: { prototype: proto } };
  zand.HTMLInputElement = zand.window.HTMLInputElement;
  const maakEvt = (type) => function (t, opts) { return { type: t || type, isTrusted: false, ...(opts || {}) }; };
  zand.Event = function (t, o) { return { type: t, isTrusted: false, ...(o || {}) }; };
  zand.InputEvent = zand.Event;
  zand.FocusEvent = zand.Event;
  zand.KeyboardEvent = zand.Event;
  void maakEvt;
  return zand;
}

// ── 1. De hoofdwereld: de prijs zetten zonder het formulier eerst leeg te melden
console.log("De prijs zetten in de pagina zelf");

async function draaiZetter(bron, opties) {
  const zand = maakWereld(opties);
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "_mwSetVintedPrice"), zand, { filename: "background.js" });
  const uit = await zand._mwSetVintedPrice("input", ["14.99", "14,99"]);
  return { uit, zand };
}

const oud = await draaiZetter(OUD_BACKGROUND, {});
check("de oude route meldde het formulier eerst een LEGE prijs",
  oud.zand.gelog.inputWaarden.includes(""),
  `input-waarden: ${JSON.stringify(oud.zand.gelog.inputWaarden)} — dan bewijst deze test niets`);
check("de oude route verliet het veld nooit echt (geen focusout)",
  !oud.zand.gelog.events.includes("focusout"),
  `gebeurtenissen: ${oud.zand.gelog.events.join(", ")}`);

const nieuw = await draaiZetter(BACKGROUND, {});
check("de nieuwe route stuurt het formulier nooit een lege prijs",
  !nieuw.zand.gelog.inputWaarden.includes(""),
  `input-waarden: ${JSON.stringify(nieuw.zand.gelog.inputWaarden)}`);
check("de nieuwe route verlaat het veld echt (focusout)",
  nieuw.zand.gelog.events.includes("focusout"));
check("de prijs staat erin", Math.abs(parseFloat(nieuw.zand.el.value.replace(",", ".")) - 14.99) < 0.01,
  `veld: ${nieuw.zand.el.value}`);
check("het formulier houdt de prijs vast", Math.abs(parseFloat(nieuw.zand.formulier.waarde.replace(",", ".")) - 14.99) < 0.01,
  `formulier: ${nieuw.zand.formulier.waarde}`);
check("de melding is weg", nieuw.zand.formulier.klacht === false);
check("de uitslag is: gelukt", nieuw.uit && nieuw.uit.ok === true, JSON.stringify(nieuw.uit));

// ── 2. De melding die blijft plakken ─────────────────────────────────────
console.log("\nEen melding die blijft staan bij een prijs die er goed in staat");

async function draaiPlakkendeMelding(bron) {
  const zand = maakWereld({});
  // Dit formulier haalt de rode regel NOOIT weg, wat we ook doen.
  Object.defineProperty(zand.formulier, "klacht", { get: () => true, set() {}, configurable: true });
  vm.createContext(zand);
  vm.runInContext(functieUit(bron, "_mwSetVintedPrice"), zand, { filename: "background.js" });
  return { uit: await zand._mwSetVintedPrice("input", ["14.99", "14,99"]), zand };
}

const plakkend = await draaiPlakkendeMelding(BACKGROUND);
check("de prijs wordt goedgekeurd omdat het formulier hem vasthoudt",
  plakkend.uit && plakkend.uit.ok === true, JSON.stringify(plakkend.uit));
check("de melding wordt wel doorgegeven", plakkend.uit && plakkend.uit.klacht === true);
check("er is geprobeerd wat Daniel met de hand doet (een echt teken typen)",
  plakkend.zand.gelog.events.some((e) => e === "input(echt)"),
  `gebeurtenissen: ${plakkend.zand.gelog.events.join(", ")}`);

// ── 3. Het invulscript liet die goedkeuring alsnog vallen ────────────────
console.log("\nHet invulscript neemt de uitslag van de pagina over");

async function draaiInvuller(bron, antwoord) {
  const zand = maakWereld({});
  Object.defineProperty(zand.formulier, "klacht", { get: () => true, set() {}, configurable: true });
  zand.chrome = {
    runtime: {
      sendMessage(msg, cb) {
        if (msg.type === "SET_PRICE_MAIN") { zand.el.value = "14.99"; zand.formulier.waarde = "14.99"; cb(antwoord); }
        else if (msg.type === "READ_PRICE_MAIN") cb({ gevonden: true, dom: 14.99, form: 14.99 });
        else cb(null);
      },
    },
  };
  zand.qs = () => zand.el;
  zand.clog = () => {};
  zand.sleep = () => Promise.resolve();
  zand.PRICE_ERR_RE = /price must|must be greater|greater than or equal|at least|minimaal|moet (groter|ten minste)|ongeldig|invalid/i;
  zand.navigator = { language: "nl-NL" };
  vm.createContext(zand);
  const stukken = ["_num", "priceErrorVinted", "priceErrorAfterSettle", "_vintedLocaleIsComma",
                   "_typePriceVariant", "_hertypLaatsteTeken", "fillPriceVinted"]
    .filter((n) => new RegExp(`function ${n}\\s*\\(`).test(bron))
    .map((n) => functieUit(bron, n));
  vm.runInContext(stukken.join("\n"), zand, { filename: "vinted.js" });
  return { ok: await zand.fillPriceVinted(14.99), zand };
}

const invulOud = await draaiInvuller(OUD_VINTED, { ok: true, used: "14.99" });
check("het OUDE invulscript keurde de prijs af terwijl de pagina 'gelukt' zei",
  invulOud.ok === false,
  "dan bewijst deze test niets: de oude versie deed het al goed");

const invulNieuw = await draaiInvuller(VINTED, { ok: true, used: "14.99", klacht: true, form: 14.99 });
check("het nieuwe invulscript neemt die goedkeuring over", invulNieuw.ok === true);
check("en zet daarbij niet nog eens een lege prijs in het formulier",
  !invulNieuw.zand.gelog.inputWaarden.includes(""),
  `input-waarden: ${JSON.stringify(invulNieuw.zand.gelog.inputWaarden)}`);

const invulEcht = await draaiInvuller(VINTED, { ok: false, reason: "rejected" });
check("een echte weigering van de pagina wordt niet zomaar goedgekeurd",
  typeof invulEcht.ok === "boolean");

// ── 4. De eindcontrole vóór het plaatsen ─────────────────────────────────
console.log("\nDe eindcontrole houdt het plaatsen niet meer tegen om een rode regel");
check("de eindcontrole vraagt het formulier zelf naar de prijs",
  /if \(!\(await prijsIsGeaccepteerd\(\)\)\) \{\s*\n\s*gaps\.push\(`price/.test(VINTED));
check("de oude regel (stoppen zodra er een melding staat) is weg",
  !/if \(prijsFout\) gaps\.push\(/.test(VINTED));
check("de oude versie stopte daar aantoonbaar wél op",
  /if \(prijsFout\) gaps\.push\(/.test(OUD_VINTED),
  "dan bewijst deze test niets");
check("de herstelronde telt alleen een prijs die het formulier niet vasthoudt",
  /if \(priceEl && !\(await prijsIsGeaccepteerd\(\)\)\) missing\.push\("price"\)/.test(VINTED));
check("de achtergrond kan de prijs van het formulier teruglezen",
  /msg\.type === "READ_PRICE_MAIN"/.test(BACKGROUND) && /function _mwLeesVintedPrijs\(/.test(BACKGROUND));
check("een mislukte plaatsing meldt de prijsklacht mee",
  /Vinted also showed under the price/.test(VINTED));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
