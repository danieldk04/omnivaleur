/**
 * Een werktabblad mag nooit in een incognitovenster landen.
 *
 * GEMETEN 14-09-2026 (Egbert Brouwer / Papa's Plectrums). Zijn werktabblad kreeg
 * van 2dehands een 401 op het verkopersoverzicht en belandde op
 * https://www.2dehands.be/identity/v2/login. Nagemeten met een kale aanvraag
 * zonder cookies: precies dezelfde 302 naar precies diezelfde pagina. Dat is dus
 * wat een browser ZONDER sessie ziet, terwijl hij ingelogd was.
 *
 * Een incognitovenster heeft zijn eigen koekjespot en die is altijd leeg. Stond
 * de extensie daar aan en had hij zo'n venster open, dan landde elk werktabblad
 * daarin en lukte er niets, met "je bent niet ingelogd" als melding. Dat verwijt
 * kreeg deze man tussen 22-08 en 09-09 al 27 keer ten onrechte.
 *
 * Draaien: node tests/werktabblad-nooit-incognito-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "154839ed";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Alleen de functie zelf uit background.js halen: de rest van dat bestand praat
// met een echte Chrome en hoort hier niet te draaien.
function haalFunctie(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let diep = 0, i = bron.indexOf("{", start);
  for (let j = i; j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}" && --diep === 0) return bron.slice(start, j + 1);
  }
  throw new Error(`${naam} loopt niet af`);
}

function maakOmgeving(bron, vensters) {
  const geopend = [];
  const zand = {
    console,
    chrome: {
      windows: { getAll: async () => vensters.map(v => ({ ...v })) },
      tabs: {
        create: async (o) => { geopend.push(o); return { id: 1, ...o }; },
        update: async () => ({}),
      },
    },
    // Wat maakWerkTabblad verder aanroept, hier tot het bot teruggebracht.
    async maakWerkTabblad(opties, url) { geopend.push({ ...opties, url }); return { id: 1 }; },
  };
  vm.createContext(zand);
  vm.runInContext(haalFunctie(bron, "openAchtergrondTabblad") + "\nthis.f = openAchtergrondTabblad;", zand);
  return { zand, geopend };
}

const NU = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const TOEN = execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`,
                      { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

(async () => {
  console.log("Werktabblad en incognito");

  // Zijn situatie: een incognitovenster vooraan, zijn gewone venster erachter.
  const vensters = [
    { id: 7, incognito: true, state: "normal" },
    { id: 3, incognito: false, state: "normal" },
  ];

  const nu = maakOmgeving(NU, vensters);
  await nu.zand.f("https://www.2dehands.be/my-account/sell/index.html");
  check("nu: het tabblad gaat naar zijn gewone venster",
        nu.geopend.length === 1 && nu.geopend[0].windowId === 3,
        `het ging naar venster ${nu.geopend[0] && nu.geopend[0].windowId}`);

  const toen = maakOmgeving(TOEN, vensters);
  await toen.zand.f("https://www.2dehands.be/my-account/sell/index.html");
  check("vroeger: het tabblad ging naar het incognitovenster",
        toen.geopend.length === 1 && toen.geopend[0].windowId === 7,
        "de oude versie keek niet of het venster incognito was");

  // Alleen incognito open: dan hier geen tabblad, en valt het terug op ons
  // eigen werkvenster (dat is nooit incognito).
  const alleen = maakOmgeving(NU, [{ id: 7, incognito: true, state: "normal" }]);
  const uit = await alleen.zand.f("https://www.2dehands.be/");
  check("alleen een incognitovenster open: geen tabblad daarin",
        uit === null && alleen.geopend.length === 0);

  // En een geminimaliseerd gewoon venster blijft gewoon de tweede keus.
  const min = maakOmgeving(NU, [
    { id: 9, incognito: false, state: "minimized" },
    { id: 4, incognito: false, state: "normal" },
  ]);
  await min.zand.f("https://www.2dehands.be/");
  check("een venster dat openstaat gaat voor een geminimaliseerd venster",
        min.geopend[0].windowId === 4);

  console.log(mislukt === 0 ? "\nAlles goed." : `\n${mislukt} fout(en).`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
