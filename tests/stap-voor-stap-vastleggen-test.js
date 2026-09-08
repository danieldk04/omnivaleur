/**
 * Een plaatsing die vastloopt moet zeggen WAAR ze vastliep.
 *
 * GEMETEN AAN HET ECHTE OPDRACHTENLOGBOEK (08-09-2026, Egbert Brouwer).
 * 51 bewaarde foutmeldingen voor 2dehands, en alle 51 zeggen letterlijk
 * hetzelfde: "no response after 3 minutes". In geen van die opdrachten staat
 * één stap opgeschreven, want de stappen van het invulformulier gingen alleen
 * naar de console van een venster dat niemand openhad. Een scan meldt zijn
 * voortgang wel, een plaatsing deed dat niet, en juist daar liep het vast: na
 * 671 pogingen wisten we nog steeds niets.
 *
 * Deze proef DRAAIT de echte code uit background.js, hij leest hem niet.
 *
 * Draaien: node tests/stap-voor-stap-vastleggen-test.js
 *          node tests/stap-voor-stap-vastleggen-test.js --oud   (MOET falen)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const BASIS = "c4aa961";          // de staat vlak voor deze reparatie
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync(`git show ${BASIS}:extension/background.js`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

/** Haalt een functie met balancerende accolades uit de bron. */
function functie(naam) {
  const start = BG.indexOf(`function ${naam}(`);
  if (start < 0) return null;
  let i = BG.indexOf("{", start), diep = 0;
  for (let j = i; j < BG.length; j++) {
    if (BG[j] === "{") diep++;
    else if (BG[j] === "}" && --diep === 0) return BG.slice(start, j + 1);
  }
  return null;
}

// ── 1. De stap komt bij de opdracht terecht ───────────────────────────────
console.log("\nElke stap van het formulier wordt vastgelegd");

const bron = functie("meldStapAanServer");
check("meldStapAanServer bestaat", !!bron,
      "zonder deze functie blijft een vastgelopen plaatsing een raadsel");

if (bron) {
  const opslag = { jobtab_7: { jobId: "job-1", serverUrl: "https://s", platform: "2dehands", action: "create" } };
  const verstuurd = [];
  let nu = 1000;
  const chrome = {
    runtime: { getManifest: () => ({ version: "1.0.312" }) },
    storage: { local: {
      get: (k, cb) => cb({ [k]: opslag[k] }),
      set: (o) => Object.assign(opslag, o),
    } },
  };
  const fn = new Function(
    "chrome", "reportProgress", "Date", "_laatsteStapKlok",
    bron + "; return meldStapAanServer;",
  )(chrome, (s, j, p) => verstuurd.push({ s, j, p }), { now: () => nu }, new Map());

  fn(7, "stap title: ok");
  check("de stap gaat naar de server", verstuurd.length === 1 && verstuurd[0].j === "job-1",
        JSON.stringify(verstuurd));
  check("met de stap er letterlijk in", (verstuurd[0] || {}).p?.stap === "stap title: ok");
  check("en de versie van de kopie erbij", (verstuurd[0] || {}).p?.versie === "1.0.312");
  check("de opdracht onthoudt zijn laatste stap",
        opslag.jobtab_7.laatsteStap === "stap title: ok");

  // Vlak erna nog een regel: die overstroomt de server niet, maar de laatste
  // stap moet wél meebewegen — anders wijst de foutmelding naar de verkeerde plek.
  nu += 300;
  fn(7, "stap prijs: ok");
  check("een regel vlak erna overstroomt de server niet", verstuurd.length === 1);
  check("maar de laatst bekende stap schuift wel mee",
        opslag.jobtab_7.laatsteStap === "stap prijs: ok");

  nu += 2000;
  fn(7, "foto's: 4 ophalen");
  check("na de tussenpoos gaat hij weer door", verstuurd.length === 2);

  // Een tabblad zonder opdracht mag niets doen.
  fn(99, "stap title: ok");
  check("een tabblad zonder opdracht wordt genegeerd", verstuurd.length === 2);
}

// ── 2. De bewaker noemt die stap in zijn melding ──────────────────────────
console.log("\nDe tijdsoverschrijding zegt waar het ophield");

const wd = functie("fireJobWatchdog") || "";
check("de bewaker leest de laatst bekende stap", /meta\.laatsteStap/.test(wd),
      "anders is elke tijdsoverschrijding weer dezelfde nietszeggende zin");
check("en zegt het met zoveel woorden als er nooit een stap kwam",
      /geen enkele stap gemeld/.test(wd),
      "dat verschil (nooit begonnen / halverwege gestrand) is de hele diagnose");

const nooit = functie("meldNooitBegonnen") || "";
check("ook 'formulier ging nooit open' draagt de laatste stap mee",
      /meta\.laatsteStap/.test(nooit));

// ── 3. Het invulscript meldt zich vóór het eerste wachten ─────────────────
console.log("\nHet invulscript geeft meteen een levensteken");
for (const bestand of ["extension/content/tweedehands.js", "extension/content/marktplaats.js"]) {
  const src = oud
    ? execSync(`git show ${BASIS}:${bestand}`, { cwd: WORTEL, maxBuffer: 8e6 }).toString()
    : fs.readFileSync(path.join(WORTEL, bestand), "utf8");
  const kop = src.slice(0, src.indexOf("try {"));
  check(`${path.basename(bestand)}: meldt zich zodra de opdracht binnen is`,
        /clog\(/.test(kop),
        "zonder dit is 'opdracht opgehaald' niet te onderscheiden van 'formulier stond er niet'");
  check(`${path.basename(bestand)}: en zodra het titelveld er staat`,
        /clog\("titelveld staat er"\)/.test(src));
}

// ── 4. De LOG-regel is echt aangesloten ───────────────────────────────────
console.log("\nDe verbinding staat");
check("de LOG-afhandeling roept meldStapAanServer aan",
      /msg\.type === "LOG"[\s\S]{0,300}meldStapAanServer\(sender\.tab\?\.id, msg\.text\)/.test(BG));

console.log(mislukt ? `\n${mislukt} proef(en) mislukt.` : "\nAlles goed.");
process.exit(mislukt ? 1 : 0);
