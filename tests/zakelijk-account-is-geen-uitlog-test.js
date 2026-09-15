/**
 * Een zakelijk account is geen uitgelogde verkoper.
 *
 * GEMETEN 15-09-2026 (Egbert Brouwer / Papa's Plectrums).
 *
 *   13-09 09:24 UTC  zijn persoonlijke advertentieoverzicht op 2dehands: HTTP 200,
 *                    109 advertenties, signed_in true.
 *   13-09 11:40 UTC  laatste geslaagde plaatsing (129 die ochtend).
 *   14-09 18:08 UTC  vanaf hier elke poging HTTP 401, werktabblad op
 *                    https://www.2dehands.be/identity/v2/login, en zijn scan
 *                    schakelde voor het eerst over op de Admarkt-kant.
 *   15-09 13:47 UTC  zijn openbare advertentiepagina op 2dehands zegt
 *                    "sellerType":"TRADER". Een particuliere verkoper ernaast
 *                    (sellerId 28108986) zegt "CONSUMER".
 *
 * Zijn account is dus zakelijk geworden, en voor een zakelijk account bestaat het
 * persoonlijke advertentieoverzicht niet: dat geeft 401 en verwijst door naar de
 * inlogpagina, precies zoals bij een uitgelogde bezoeker. Andere klanten
 * publiceerden op 14 en 15 september gewoon door op 2dehands, dus aan de site lag
 * het niet. Wij lazen die 401 als "je bent niet ingelogd" en namen zijn hele
 * wachtrij van 231 zoekertjes terug. Hij was de hele tijd ingelogd.
 *
 * De neutrale bron is de kopbalk van de site zelf: "isLoggedIn" staat precies één
 * keer in de HTML van www.marktplaats.nl en www.2dehands.be (gemeten 15-09-2026)
 * en is voor een particulier en een zakelijk account hetzelfde.
 *
 * Draaien: node tests/zakelijk-account-is-geen-uitlog-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
// Laatste commit VÓÓR deze reparatie (1.0.331). Zonder deze vergelijking weet je
// alleen dat de nieuwe code werkt, niet dat ze iets repareert.
const VOOR_DE_REPARATIE = "9d30fbca";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function haalBlok(bron, kop) {
  const start = bron.indexOf(kop);
  if (start < 0) return null;
  let i = bron.indexOf("(", start);
  if (i < 0) return null;
  let haakjes = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "(") haakjes++;
    else if (bron[i] === ")" && --haakjes === 0) { i++; break; }
  }
  let diep = 0;
  for (let j = bron.indexOf("{", i); j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}" && --diep === 0) return bron.slice(start, j + 1);
  }
  return null;
}

// De vier gemeten situaties, zoals eerstepartijStatus ze teruggeeft.
const SITUATIES = {
  zakelijk:  { status: 401, header: true,  url: "https://www.2dehands.be/identity/v2/login" },
  uitgelogd: { status: 401, header: false, url: "https://www.2dehands.be/identity/v2/login" },
  gewoon:    { status: 200, header: true,  url: "https://www.2dehands.be/my-account/sell/index.html" },
  onleesbaar:{ status: 401, header: null,  url: "https://www.2dehands.be/identity/v2/login" },
};

function bouwOordeel(bron) {
  const blok = haalBlok(bron, "async function mpIngelogdOpDeSiteZelf");
  if (!blok) throw new Error("mpIngelogdOpDeSiteZelf niet gevonden");
  const ctx = {
    console,
    EERSTEPARTIJ_TTL_MS: 0,             // nooit uit het geheugen antwoorden
    _eerstepartijOordeel: {},
    MP_OVERZICHT_URL: { "2dehands": "https://www.2dehands.be/my-account/sell/index.html" },
    MP_SESSIE_URL: { "2dehands": "https://www.2dehands.be/my-account/sell/api/listings" },
    onthoudKanaalSessie: (p, ingelogd, extra) => { ctx.bewaard.push({ p, ingelogd, extra }); },
    bewaard: [],
    _situatie: null,
    eerstepartijStatus: async () => ctx._situatie,
  };
  vm.createContext(ctx);
  vm.runInContext(blok, ctx);
  return ctx;
}

function bouwKlaarzetten(bron, oordeelVoorPlatform) {
  const blok = haalBlok(bron, "async function mpPlaatsenKlaarzetten");
  if (!blok) throw new Error("mpPlaatsenKlaarzetten niet gevonden");
  const ctx = {
    console: { warn: () => {}, log: () => {} },
    gestopt: [],
    mpSessie: async () => ({ ingelogd: false, status: 401 }),   // het vermoeden
    mpIngelogdOpDeSiteZelf: oordeelVoorPlatform,
    mpNietIngelogdMelding: () => "je bent niet ingelogd",
    stopPlatformWachtrij: async (s, p, m) => { ctx.gestopt.push({ p, m }); },
  };
  vm.createContext(ctx);
  vm.runInContext(blok, ctx);
  return ctx;
}

(async () => {
  const nu = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
  const oud = execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`,
                       { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

  console.log("\n1. Het oordeel over Egberts browser (kopbalk zegt: ingelogd, overzicht geeft 401)");
  const n = bouwOordeel(nu);
  n._situatie = SITUATIES.zakelijk;
  const nZak = await n.mpIngelogdOpDeSiteZelf("2dehands");
  check("nu: hij geldt als ingelogd", nZak.ingelogd === true, `kreeg ${nZak.ingelogd}`);
  check("nu: en het heet een zakelijk account", nZak.zakelijk === true);
  check("nu: er wordt geen 'uitgelogd' bewaard",
        !n.bewaard.some((b) => b.ingelogd === false));

  const o = bouwOordeel(oud);
  o._situatie = SITUATIES.zakelijk;
  const oZak = await o.mpIngelogdOpDeSiteZelf("2dehands");
  check("1.0.331 deed het fout: die zei uitgelogd", oZak.ingelogd === false,
        `kreeg ${oZak.ingelogd}, dan bewijst deze test niets`);
  check("1.0.331 stempelde het kanaal ook nog rood",
        o.bewaard.some((b) => b.ingelogd === false));

  console.log("\n2. Wie echt uitgelogd is wordt nog steeds gevonden");
  const n2 = bouwOordeel(nu);
  n2._situatie = SITUATIES.uitgelogd;
  const nUit = await n2.mpIngelogdOpDeSiteZelf("2dehands");
  check("kopbalk zegt uitgelogd -> uitgelogd", nUit.ingelogd === false);
  check("en dat wordt bewaard voor het uitklapvenster",
        n2.bewaard.some((b) => b.ingelogd === false));
  check("het heet dan geen zakelijk account", nUit.zakelijk === false);

  console.log("\n3. De gewone verkoper verandert niet");
  const n3 = bouwOordeel(nu);
  n3._situatie = SITUATIES.gewoon;
  check("200 -> ingelogd", (await n3.mpIngelogdOpDeSiteZelf("2dehands")).ingelogd === true);

  console.log("\n4. Onleesbare kopbalk: geen oordeel, dus geen wachtrij kwijt");
  const n4 = bouwOordeel(nu);
  n4._situatie = SITUATIES.onleesbaar;
  const nOnb = await n4.mpIngelogdOpDeSiteZelf("2dehands");
  check("nu: weet niet", nOnb.ingelogd === null, `kreeg ${nOnb.ingelogd}`);
  const o4 = bouwOordeel(oud);
  o4._situatie = SITUATIES.onleesbaar;
  check("1.0.331 zei hier alsnog uitgelogd",
        (await o4.mpIngelogdOpDeSiteZelf("2dehands")).ingelogd === false);

  console.log("\n5. De wachtrij van 231 zoekertjes");
  const kNu = bouwKlaarzetten(nu, async () => nZak);
  const rNu = await kNu.mpPlaatsenKlaarzetten({ platform: "2dehands" }, "http://x");
  check("nu: de opdracht mag door", rNu.ok === true);
  check("nu: de wachtrij wordt niet stilgezet", kNu.gestopt.length === 0);

  const kOud = bouwKlaarzetten(oud, async () => oZak);
  const rOud = await kOud.mpPlaatsenKlaarzetten({ platform: "2dehands" }, "http://x");
  check("1.0.331 zette hem stil", rOud.ok === false && kOud.gestopt.length === 1,
        "zonder dit bewijst deze test niets");

  const kUit = bouwKlaarzetten(nu, async () => nUit);
  const rUit = await kUit.mpPlaatsenKlaarzetten({ platform: "2dehands" }, "http://x");
  check("echt uitgelogd wordt nog wel stilgezet", rUit.ok === false && kUit.gestopt.length === 1);

  console.log("\n6. De kopbalk uitlezen uit de ECHTE pagina-HTML (gemeten 15-09-2026)");
  const snip = nu.match(/const treffers = Array\.from[\s\S]*?header = treffers\[0\];/);
  check("de leescode staat in background.js", !!snip);
  const leesHeader = (html) => {
    const c = { html, header: null };
    vm.createContext(c);
    vm.runInContext(`let header = null; ${snip[0]}; this.header = header;`, c);
    return c.header;
  };
  const ECHT_BE = '"navBar":{"locale":"nl-BE","userDetails":{"isLoggedIn":false},"headerLinks":[{"text":"Help en';
  const ECHT_NL = '"navBar":{"locale":"nl-NL","userDetails":{"isLoggedIn":false},"headerLinks":[{"text":"Help en';
  check("2dehands, uitgelogd -> false", leesHeader(ECHT_BE) === false);
  check("marktplaats, uitgelogd -> false", leesHeader(ECHT_NL) === false);
  check("ingelogd, met naam ervoor -> true",
        leesHeader('"userDetails":{"userName":"Papa\'s Plectrums","isLoggedIn":true}') === true);
  check("staat het er niet -> weet niet", leesHeader("<html>niets</html>") === null);
  check("spreken twee vermeldingen elkaar tegen -> weet niet",
        leesHeader('"isLoggedIn":true ... "isLoggedIn":false') === null);

  console.log("\n7. De scan stempelt geen 'uitgelogd' meer");
  check("nu: geen onthoudKanaalSessie(..., false) in de scan",
        !/onthoudKanaalSessie\(job\.platform, false/.test(nu));
  check("1.0.331 deed dat wel", /onthoudKanaalSessie\(job\.platform, false/.test(oud));

  console.log(mislukt === 0
    ? "\nAlles goed.\n"
    : `\n${mislukt} controle(s) mislukt.\n`);
  process.exit(mislukt ? 1 : 0);
})();
