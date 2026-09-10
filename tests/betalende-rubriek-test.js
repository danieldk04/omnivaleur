/**
 * Nooit op "Naar betalen" klikken.
 *
 * Egbert Brouwer (Papa's Plectrums), 10-09-2026: "Hij is nu nog druk bezig maar
 * op dit moment zijn er al 23 niet gelukt, die hebben weer zo'n rode balk."
 *
 * GEMETEN IN ZIJN EIGEN OPDRACHTEN. Alle 24 mislukten met "Je hebt geen
 * zoekertjesvorm gekozen", alle 24 in dezelfde drie gitaarrubrieken
 * (/plaats/728/746, /747, /748). De paginatekst hieronder is LETTERLIJK die uit
 * opdracht 4b77d41f-5ded-4ecd-895a-1b07785e8f5e: "Dit is een betalende
 * categorie". De gratis keuze (bundle-option-FREE) bestond er niet, en de
 * plaatsknop heette "Naar betalen" in plaats van "Plaats zoekertje".
 *
 * De "zoekertjesvorm" die het formulier mist is dus geen prijsvorm maar een
 * BETAALD pakket. Doorklikken is niet alleen zinloos maar duur: elke klik is een
 * regel in een bestelling. Zijn winkelmandje stond eerder al op EUR 153,00.
 *
 * Draaien: node tests/betalende-rubriek-test.js
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

// Letterlijk uit zijn mislukte opdracht.
const BETAALDE_PAGINA =
  "Help en info Voorwaarden Veiligheidscentrum Chat Meldingen 18 Papa's Plectrums FR " +
  "Plaats zoekertje Gekozen categorie Muziek en Instrumenten Gitaren | Elektrisch Wijzigen " +
  "Dit is een betalende categorie Gitaren | Elektrisch";
// En zoals een gratis rubriek er bij hem uitzag (Behuizingen en koffers: die
// gingen op datzelfde moment gewoon online).
const GRATIS_PAGINA =
  "Plaats zoekertje Gekozen categorie Muziek en Instrumenten Behuizingen en koffers Wijzigen " +
  "Hoe wil je adverteren? Gratis Plus Premium";

function laad(bron, paginaTekst, gratisKnopBestaat) {
  const document = {
    querySelector(sel) {
      if (sel === '[data-testid="bundle-option-FREE"]') {
        return gratisKnopBestaat ? { tagName: "DIV" } : null;
      }
      return null;
    },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    documentElement: {}, contains() { return true; },
    body: { innerText: paginaTekst },
  };
  const sandbox = {
    console: { log() {}, warn() {} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    document,
    location: { hostname: "www.2dehands.be", pathname: "/plaats/728/748", href: "", search: "" },
    MutationObserver: class { observe() {} disconnect() {} },
    Event: class { constructor(t) { this.type = t; } },
    chrome: { runtime: { sendMessage(m, cb) { if (cb) cb("niet bereikbaar"); } } },
  };
  sandbox.window = sandbox;
  sandbox.window.HTMLSelectElement = class {};
  sandbox.window.HTMLInputElement = function () {};
  sandbox.window.HTMLInputElement.prototype = {};
  Object.defineProperty(sandbox.window.HTMLInputElement.prototype, "value",
    { set(v) { this._v = v; }, get() { return this._v; }, configurable: true });
  sandbox.window.HTMLTextAreaElement = function () {};
  sandbox.window.HTMLTextAreaElement.prototype = {};
  Object.defineProperty(sandbox.window.HTMLTextAreaElement.prototype, "value",
    { set(v) { this._v = v; }, get() { return this._v; }, configurable: true });
  vm.createContext(sandbox);
  vm.runInContext(bron, sandbox);
  return sandbox.window.CL;
}

const NU = fs.readFileSync(path.join(WORTEL, "extension", "content", "shared.js"), "utf8");
const knop = (tekst) => ({ tagName: "BUTTON", textContent: tekst });

console.log("\nNU (de code zoals hij in de map staat)");
{
  const CL = laad(NU, BETAALDE_PAGINA, false);
  const bezwaar = CL.betaalrubriekBezwaar(knop("Naar betalen"));
  check("de betalende rubriek van Egbert wordt herkend", !!bezwaar);
  check("de melding noemt de rubriek zoals 2dehands hem toont",
    bezwaar && /Muziek en Instrumenten Gitaren \| Elektrisch/.test(bezwaar.melding),
    bezwaar && bezwaar.melding);
  check("de melding zegt dat er niets besteld is",
    bezwaar && /nothing was ordered/i.test(bezwaar.melding));
  check("de server herkent deze melding als betalende rubriek",
    bezwaar && /charges for an advert in this category/i.test(bezwaar.melding));
}
{
  // Alleen de knopnaam is al genoeg: die staat er ook als de zin over de
  // rubriek anders wordt gespeld of in het Frans staat.
  const CL = laad(NU, "Plaats zoekertje", false);
  check("de knopnaam alleen is al genoeg", !!CL.betaalrubriekBezwaar(knop("Naar betalen")));
}
{
  const CL = laad(NU, GRATIS_PAGINA, true);
  check("een gewone, gratis rubriek gaat gewoon door",
    CL.betaalrubriekBezwaar(knop("Plaats zoekertje")) === null);
}
{
  // Een betalende rubriek waar nog wél een gratis keuze staat mag niet
  // stilvallen: dat zijn precies de eerste twee die bij hem wél lukten.
  const CL = laad(NU, BETAALDE_PAGINA, true);
  check("betalende rubriek mét gratis keuze gaat gewoon door",
    CL.betaalrubriekBezwaar(knop("Plaats zoekertje")) === null);
}

console.log(`\nVÓÓR DE REPARATIE (commit ${VOOR_DE_REPARATIE})`);
{
  const bron = execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`,
    { cwd: WORTEL, encoding: "utf8", maxBuffer: 40 * 1024 * 1024 });
  const CL = laad(bron, BETAALDE_PAGINA, false);
  check("de oude code kende deze controle niet",
    typeof CL.betaalrubriekBezwaar !== "function",
    "de controle bestond al — dan bewijst deze proef niets");
}

console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
process.exit(mislukt ? 1 : 0);
