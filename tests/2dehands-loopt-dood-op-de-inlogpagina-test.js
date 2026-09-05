/**
 * Egbert Brouwer (papas-plectrums), 04-09-2026: "Ik ben ingelogd op 2dehands,
 * dus weet niet wat er nu mis gaat?"
 *
 * GEMETEN AAN ZIJN EIGEN ACCOUNT (05-09-2026):
 *   305 opdrachten voor 2dehands, nul geslaagd, nul voortgangsberichten.
 *   Elke afgebroken opdracht duurde 195 tot 230 seconden: de bewaker van drie
 *   minuten, niet het werk. Bij andere verkopers duurt een geslaagde plaatsing
 *   op 2dehands 10 tot 50 seconden.
 *
 * GEMETEN IN EEN ECHTE BROWSER:
 *   https://www.2dehands.be/plaats/728/748 zonder sessie komt niet uit op een
 *   foutpagina maar op https://www.2dehands.be/identity/v2/login?target=...
 *   Ons invulscript luistert alleen op /plaats/*, dus daar draait het niet en
 *   meldt zich nooit iemand terug.
 *
 * GEMETEN, DRIE KEER, OP HETZELFDE ADRES:
 *   /my-account/sell/api/listings geeft zonder sessie 401 (twaalf bytes
 *   "Unauthorized") en verwijst niet door. Met sessie 200. Dat is dus een
 *   eerlijk ja of nee op "ben je ingelogd".
 *
 * Draaien: node tests/2dehands-loopt-dood-op-de-inlogpagina-test.js
 *          node tests/2dehands-loopt-dood-op-de-inlogpagina-test.js --oud
 *          (tegen de vorige commit; die MOET falen)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync("git show HEAD:extension/background.js", { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

/** Haal een blok op naam uit background.js, met accolades tellen. */
function blokUit(naam, woord = "function") {
  const start = BG.indexOf(`${woord} ${naam}`);
  if (start < 0) return null;
  let diepte = 0, i = BG.indexOf("{", start);
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(start, i + 1);
}
function constUit(naam) {
  const start = BG.indexOf(`const ${naam} = `);
  if (start < 0) return null;
  const na = BG.indexOf("=", start) + 1;
  if (BG.slice(na).trimStart().startsWith("{")) {
    let diepte = 0, i = BG.indexOf("{", na);
    for (; i < BG.length; i++) {
      if (BG[i] === "{") diepte++;
      else if (BG[i] === "}") { diepte--; if (!diepte) break; }
    }
    return BG.slice(start, i + 2);
  }
  return BG.slice(start, BG.indexOf("\n", start));
}

// ── 1. De sessiecontrole zelf ──────────────────────────────────────────────
const bron = ["MP_SESSIE_URL", "MP_INLOG_URL"].map(constUit).join("\n")
  + "\n" + blokUit("mpSessie", "async function")
  + "\n" + blokUit("mpNietIngelogdMelding");

if (!blokUit("mpSessie", "async function")) {
  check("er is een sessiecontrole voor Marktplaats/2dehands", false,
    "mpSessie bestaat niet: elke plaatsing opent gewoon een tabblad en wacht drie minuten op stilte");
} else {
  const antwoorden = [];
  const ctx = {
    console,
    SITE_NAAM: { marktplaats: "Marktplaats (marktplaats.nl)", "2dehands": "2dehands (2dehands.be)" },
    fetch: async () => antwoorden.shift(),
  };
  vm.createContext(ctx);
  vm.runInContext(bron, ctx);

  const proef = async (antwoord) => {
    antwoorden.length = 0;
    if (antwoord instanceof Error) ctx.fetch = async () => { throw antwoord; };
    else ctx.fetch = async () => antwoord;
    return await vm.runInContext(`mpSessie("2dehands")`, ctx);
  };

  (async () => {
    const uitgelogd = await proef({ status: 401, ok: false });
    check("401 op het advertentieoverzicht = niet ingelogd", uitgelogd.ingelogd === false,
      `kreeg ${JSON.stringify(uitgelogd)}`);

    const ingelogd = await proef({ status: 200, ok: true });
    check("200 = wel ingelogd", ingelogd.ingelogd === true, `kreeg ${JSON.stringify(ingelogd)}`);

    const storing = await proef({ status: 503, ok: false });
    check("een storing bij de site houdt het werk NIET tegen", storing.ingelogd === null,
      `kreeg ${JSON.stringify(storing)}`);

    const geenNet = await proef(new Error("net::ERR_INTERNET_DISCONNECTED"));
    check("geen netwerk houdt het werk NIET tegen", geenNet.ingelogd === null,
      `kreeg ${JSON.stringify(geenNet)}`);

    const tekst = vm.runInContext(`mpNietIngelogdMelding("2dehands", 401)`, ctx);
    check("de melding noemt de site en waar hij moet inloggen",
      /2dehands \(2dehands\.be\)/.test(tekst) && tekst.includes("https://www.2dehands.be"), tekst);
    check("de melding zegt dat er niets is gepubliceerd",
      /nothing was published/i.test(tekst), tekst);
    check("de melding bevat geen gedachtestreepje",
      !/ [—–-] /.test(tekst), tekst);

    klaar();
  })();
}

// ── 2. De controle staat VOOR het openen van het tabblad ───────────────────
const processJob = blokUit("processJob", "async function") || "";
const iVoor = processJob.indexOf("mpPlaatsenKlaarzetten");
const iTab = processJob.indexOf("openWorkerTab(");
check("er wordt geen tabblad geopend zonder sessie",
  iVoor > -1 && iTab > -1 && iVoor < iTab,
  "processJob opent het tabblad zonder eerst te vragen of de browser een sessie heeft");

// ── 3. De inlogpagina wordt herkend, het formulier niet ────────────────────
const patroonRegel = constUit("MP_LOGINPAGINA");
if (!patroonRegel) {
  check("een tabblad dat op de inlogpagina landt wordt herkend", false,
    "MP_LOGINPAGINA bestaat niet: het tabblad blijft drie minuten stil hangen");
} else {
  const c = {};
  vm.createContext(c);
  vm.runInContext(patroonRegel.replace(/^const /, "var "), c);
  const p = c.MP_LOGINPAGINA;
  check("de echt waargenomen inlog-url wordt herkend",
    p.test("https://www.2dehands.be/identity/v2/login?target=%2Fplaats%2F728%2F748%3Ftitle%3D"));
  check("het plaatsformulier wordt NIET voor een inlogpagina aangezien",
    !p.test("https://www.2dehands.be/plaats/728/748?title="));
  check("een zojuist geplaatste advertentie wordt NIET voor een inlogpagina aangezien",
    !p.test("https://www.2dehands.be/v/muziek-en-instrumenten/m2439226665-fender"));
}

// Bestaat de sessiecontrole niet (oude versie), dan draait het blok hierboven
// niet en moet de uitslag hier alsnog geteld worden.
if (!blokUit("mpSessie", "async function")) klaar();

function klaar() {
  console.log(mislukt ? `\n${mislukt} controle(s) mislukt.` : "\nAlles goed.");
  process.exit(mislukt ? 1 : 0);
}
