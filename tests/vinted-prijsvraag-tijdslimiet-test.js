/**
 * Janneke, 12-10-2026: elke automatische Vinted-plaatsing die bij haar
 * mislukte (11 keer sinds 10-10, extensie 1.0.374 tot 1.0.383, Chrome 128)
 * stopte op dezelfde plek: laatste regel "stap category: ok", daarna drie
 * minuten niets, en op Vinted een concept van EUR 0.
 *
 * Direct na de rubriek vraagt het invulscript de achtergrond om de prijs vanuit
 * de pagina zelf te zetten (SET_PRICE_MAIN). Dat was de enige vraag naar de
 * pagina zonder tijdslimiet: antwoordt de pagina niet, dan wacht het script
 * voor altijd. Gemeten op Chrome 127 met een pagina waarvan de klok stilstaat:
 * na 35 seconden nog geen antwoord.
 *
 * Deze proef draait het ECHTE blok uit background.js, nu en van vóór de
 * reparatie, met een pagina die nooit antwoordt.
 * Draaien: node tests/vinted-prijsvraag-tijdslimiet-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Het blok `if (msg.type === "SET_PRICE_MAIN") { ... return true; }` uit de bron.
function blok(bron) {
  const begin = bron.indexOf('if (msg.type === "SET_PRICE_MAIN")');
  const eind = bron.indexOf("return true;\n  }", begin) + "return true;\n  }".length;
  if (begin < 0 || eind < begin) throw new Error("SET_PRICE_MAIN-blok niet gevonden");
  return bron.slice(begin, eind);
}

// Draai het blok met een pagina die nooit antwoordt, en een klok die we zelf
// vooruitzetten. Geeft terug wat het invulscript na `seconden` heeft gekregen.
function draai(bron, { antwoordtNooit = true, seconden = 30 } = {}) {
  const wekkers = [];
  const nepTimeout = (fn, ms) => { wekkers.push({ fn, ms }); return wekkers.length; };
  const chrome = {
    runtime: { lastError: null },
    scripting: {
      executeScript(_opts, cb) {
        if (!antwoordtNooit) cb([{ result: { ok: true, used: "29,50" } }]);
      },
    },
  };
  const antwoorden = [];
  const handler = new Function("msg", "sender", "sendResponse", "chrome", "setTimeout", "_mwSetVintedPrice", "console",
    blok(bron));
  handler({ type: "SET_PRICE_MAIN", selector: "x", values: ["29,50"] }, { tab: { id: 1 } },
    (r) => antwoorden.push(r), chrome, nepTimeout, function _mwSetVintedPrice() {}, { log() {}, error() {} });
  for (const w of wekkers) if (w.ms <= seconden * 1000) w.fn();
  return antwoorden;
}

const bronNu = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const bronOud = execSync("git show 418249e8:extension/background.js", { cwd: WORTEL, maxBuffer: 1 << 26 }).toString();

console.log("VOOR de reparatie (1.0.384)");
check("een pagina die niet antwoordt laat het invulscript eindeloos wachten",
  draai(bronOud).length === 0);

console.log("\nNA de reparatie");
const na = draai(bronNu, { seconden: 20 });
check("na 20 seconden komt er toch een antwoord", na.length === 1, JSON.stringify(na));
check("dat antwoord zegt 'niet gelukt', zodat de gewone typroute het overneemt",
  na[0] && na[0].ok === false && /20 s/.test(na[0].reason || ""), JSON.stringify(na[0]));
check("vóór 20 seconden nog geen antwoord (geen valse haast)", draai(bronNu, { seconden: 19 }).length === 0);
const snel = draai(bronNu, { antwoordtNooit: false, seconden: 30 });
check("antwoordt de pagina wel, dan precies één antwoord, het echte",
  snel.length === 1 && snel[0].ok === true, JSON.stringify(snel));

console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
