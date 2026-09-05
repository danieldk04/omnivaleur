/**
 * Amanda Haas, 05-09-2026:
 *   "Die toestemming geven betrof elke keer als een nieuwe pagina werd geopend,
 *    rechts van de werkbalk."
 *
 * WAT DAT IS. Chrome kent per extensie drie standen voor site-toegang: "Op alle
 * sites", "Op specifieke sites" en "Als je erop klikt". Bij die laatste moet de
 * verkoper bij ELKE nieuwe pagina eerst op het icoontje rechts van de adresbalk
 * klikken voordat de extensie iets van die pagina ziet. Onze werk-tabbladen
 * openen zichzelf, dus dan gebeurt er domweg niets — geen invulstap, geen
 * foutmelding, en na drie minuten "Extension timed out waiting for this job to
 * finish". Dat is exact waarom ze erbij moest blijven zitten.
 *
 * Chrome geeft die stand gewoon terug via permissions.contains(). Deze proef
 * meet drie dingen:
 *   1. weten we het zeker, dan stopt de opdracht meteen met een leesbare uitleg;
 *   2. mag het wél, dan verandert er niets aan de gang van zaken;
 *   3. kunnen we het niet vaststellen, dan houdt deze rem NIETS tegen.
 *
 * Draaien: node tests/extensie-sitetoegang-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const BACKGROUND = fs.readFileSync(path.join(WORTEL, "extension", "background.js"), "utf8");
const VOOR = "266fac7";
const OUD_BACKGROUND = execFileSync("git", ["show", `${VOOR}:extension/background.js`],
                                    { cwd: WORTEL }).toString();

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const re = new RegExp(`(?:^|\\n)\\s*(?:async\\s+)?function ${naam}\\s*\\(`);
  const m = re.exec(bron);
  if (!m) return null;
  const start = m.index + m[0].search(/async|function/);
  let i = bron.indexOf("(", m.index + m[0].indexOf(naam)), haakjes = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "(") haakjes++;
    else if (bron[i] === ")") { haakjes--; if (haakjes === 0) { i++; break; } }
  }
  i = bron.indexOf("{", i);
  let diep = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diep++;
    else if (bron[i] === "}") { diep--; if (diep === 0) return bron.slice(start, i + 1); }
  }
  return null;
}

function constUit(bron, naam) {
  const start = bron.indexOf(`const ${naam} = `);
  if (start < 0) return null;
  let i = bron.indexOf("{", start), diep = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "{") diep++;
    else if (bron[i] === "}") { diep--; if (diep === 0) return bron.slice(start, i + 2); }
  }
  return null;
}

// `toegestaan` is de lijst origins die Chrome zegt te hebben; null = Chrome
// gooit een fout (dan weten we niets).
function maakControle(bron, toegestaan) {
  const src = functieUit(bron, "siteToegangOntbreekt");
  if (!src) return null;
  const sandbox = {
    console,
    chrome: {
      permissions: {
        contains: async ({ origins }) => {
          if (toegestaan === null) throw new Error("Chrome doet moeilijk");
          return origins.every((o) => toegestaan.includes(o));
        },
      },
    },
    URL,
  };
  vm.createContext(sandbox);
  vm.runInContext(constUit(bron, "SITE_ORIGINS") + "\n" + src, sandbox);
  return (platform, payload) => {
    sandbox.__p = platform; sandbox.__pl = payload || {};
    return vm.runInContext("siteToegangOntbreekt(__p, __pl)", sandbox);
  };
}

const ALLES = [
  "https://www.marktplaats.nl/*", "https://www.2dehands.be/*",
  "https://www.vinted.nl/*", "https://www.vinted.be/*",
  "https://www.vinted.com/*", "https://www.vinted.de/*",
  "https://www.vinted.fr/*", "https://www.facebook.com/*",
];

(async () => {
  console.log("Chrome's site-toegang: herkennen in plaats van drie minuten wachten\n");

  const nieuw = maakControle(BACKGROUND, ALLES);
  check("de controle bestaat", nieuw !== null, "siteToegangOntbreekt ontbreekt");
  if (nieuw) {
    console.log("\nToegang staat goed (Op alle sites):");
    check("marktplaats mag door", (await nieuw("marktplaats")) === false);
    check("vinted mag door", (await nieuw("vinted")) === false);

    console.log("\nToegang staat op \"Als je erop klikt\":");
    const dicht = maakControle(BACKGROUND, []);
    check("marktplaats wordt tegengehouden", (await dicht("marktplaats")) === true);
    check("2dehands wordt tegengehouden", (await dicht("2dehands")) === true);
    check("vinted wordt tegengehouden", (await dicht("vinted")) === true);

    console.log("\nEén Vinted-land toegestaan, en dat is haar eigen land:");
    const nlOnly = maakControle(BACKGROUND, ["https://www.vinted.nl/*"]);
    check("vinted.nl mag door",
          (await nlOnly("vinted", { _create_origin: "https://www.vinted.nl" })) === false);
    check("vinted.de wordt tegengehouden",
          (await nlOnly("vinted", { _create_origin: "https://www.vinted.de" })) === true);

    console.log("\nBij twijfel houdt deze rem niets tegen:");
    const stuk = maakControle(BACKGROUND, null);
    check("Chrome gooit een fout: gewoon doorgaan", (await stuk("marktplaats")) === false);
    check("onbekend kanaal: gewoon doorgaan", (await maakControle(BACKGROUND, [])("etsy")) === false);
  }

  console.log("\nDe opdracht stopt er ook echt op:");
  const nu = functieUit(BACKGROUND, "processJob") || "";
  check("processJob controleert de toegang vóór het werk",
        /siteToegangOntbreekt\(job\.platform, job\.payload\)/.test(nu));
  check("en meldt het als een echte fout aan de verkoper",
        /reportError\(job\.id, serverUrl, GEEN_SITETOEGANG\)/.test(nu));
  check("de uitleg vertelt waar hij moet klikken",
        /puzzelstukje/.test(BACKGROUND) && /Op alle sites/.test(BACKGROUND));

  console.log("\nOude versie:");
  check("kende deze controle niet",
        functieUit(OUD_BACKGROUND, "siteToegangOntbreekt") === null);
  check("liet de opdracht dus gewoon in een lege pagina lopen",
        !/siteToegangOntbreekt/.test(functieUit(OUD_BACKGROUND, "processJob") || ""));

  console.log("");
  if (mislukt) { console.log(`${mislukt} controle(s) mislukt`); process.exit(1); }
  console.log("alles goed");
})();
