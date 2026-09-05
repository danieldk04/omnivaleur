/**
 * Toon (dejuistetoon), 05-09-2026. Van de 39 publicaties die we voor hem
 * opnieuw in de wachtrij zetten was er één voor 2dehands, en juist die kwam
 * terug met:
 *
 *   "Not published — complete the fields marked in red and click publish
 *    yourself. Geen postcode ingevuld. | Fields marked invalid:
 *    contactInformation.postCode=LEEG"
 *
 * Hetzelfde account publiceerde op 2dehands al tien keer met succes, met
 * precies dezelfde code. Het contactblok wordt dus normaal door de site zelf
 * uit het account gevuld en was op dat moment alleen nog niet aangekomen.
 * Doorklikken levert dan geen advertentie op, alleen een foutmelding waar de
 * verkoper niets mee kan.
 *
 * Deze proef draait de échte wachtOpPostcode uit extension/content/shared.js
 * tegen een nagebouwd formulier, en zet oud naast nieuw: de oude versie kende
 * de stap niet en ging meteen door naar de knop.
 *
 * Draaien: node tests/postcode-wachten-test.js
 */
const fs = require("fs");
const path = require("path");

const SHARED = fs.readFileSync(
  path.join(__dirname, "..", "extension", "content", "shared.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(bron, naam) {
  const start = bron.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n  }\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return bron.slice(start, eind + 4);
}

// Een formulier dat alleen het postcodeveld kent. `waarde` is wat erin staat;
// `vulNa` laat de site hem alsnog invullen na zoveel milliseconden, precies
// zoals het contactblok normaal binnenkomt.
function nepFormulier({ heeftVeld = true, waarde = "", vulNa = null } = {}) {
  const veld = heeftVeld ? { name: "contactInformation.postCode", value: waarde } : null;
  if (veld && vulNa != null) setTimeout(() => { veld.value = "4879 AK"; }, vulNa);
  return veld;
}

function bouw(veld) {
  const logs = [];
  const scope = {
    qs: (sel) => (sel === 'input[name="contactInformation.postCode"]' ? veld : null),
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    clog: (m) => logs.push(m),
  };
  // Alles wat de stap zelf nodig heeft komt uit de bron, niet uit een kopie.
  const wacht = /const POSTCODE_WACHT_MS = \d+;/.exec(SHARED);
  const veldFn = /function postcodeVeld\(\) \{[\s\S]*?\n  \}/.exec(SHARED);
  if (!wacht || !veldFn) throw new Error("POSTCODE_WACHT_MS of postcodeVeld niet gevonden");
  const src = `${wacht[0]}\n${veldFn[0]}\n${functieUit(SHARED, "wachtOpPostcode")}`;
  const maak = new Function("qs", "sleep", "clog",
    `${src}\n return wachtOpPostcode;`);
  return { fn: maak(scope.qs, scope.sleep, scope.clog), logs };
}

(async () => {
  console.log("\nNIEUWE VERSIE");

  // 1. Postcode staat er al: meteen door, geen wachttijd.
  {
    const { fn } = bouw(nepFormulier({ waarde: "4879 AK" }));
    const t0 = Date.now();
    const ok = await fn();
    check("gevulde postcode gaat meteen door", ok === true && Date.now() - t0 < 300,
          `duurde ${Date.now() - t0} ms`);
  }

  // 2. Formulier zonder dit veld (Vinted): niet ons probleem, meteen door.
  {
    const { fn } = bouw(nepFormulier({ heeftVeld: false }));
    const t0 = Date.now();
    const ok = await fn();
    check("formulier zonder postcodeveld gaat meteen door",
          ok === true && Date.now() - t0 < 300);
  }

  // 3. De echte storing: leeg bij aankomst, komt kort daarna alsnog binnen.
  //    Oud gedrag klikte hier op plaatsen en kreeg "Geen postcode ingevuld".
  {
    const { fn } = bouw(nepFormulier({ waarde: "", vulNa: 700 }));
    const t0 = Date.now();
    const ok = await fn();
    const duur = Date.now() - t0;
    check("wacht op een postcode die nog binnenkomt", ok === true && duur >= 500 && duur < 4000,
          `duurde ${duur} ms`);
  }

  // 4. Blijft leeg: niet klikken, en zeggen wat de verkoper zelf moet doen.
  {
    const { fn, logs } = bouw(nepFormulier({ waarde: "" }));
    let boodschap = null;
    try { await fn(); } catch (e) { boodschap = e.message; }
    check("blijft leeg: plaatsen wordt geweigerd", boodschap !== null);
    check("melding noemt de postcode", /postcode/i.test(boodschap || ""));
    check("melding zegt dat er niets is gepubliceerd",
          /nothing was published/i.test(boodschap || ""));
    check("melding zegt wat hij zelf moet doen",
          /account settings/i.test(boodschap || "") && /once/i.test(boodschap || ""));
    check("melding is geen kale velddump",
          !/contactInformation/.test(boodschap || ""));
    check("het logboek legt de weigering vast", logs.some((m) => /postcode/i.test(m)));
  }

  // VOOR-EN-NA. De oude versie had deze stap niet: submitListing ging van de
  // fotocontrole rechtstreeks naar de knop.
  console.log("\nOUDE VERSIE (ter vergelijking)");
  const oud = SHARED.replace(/\n *await wachtOpPostcode\(\);\n/, "\n");
  check("oud: submitListing kende geen postcodestap",
        !/await wachtOpPostcode\(\)/.test(oud));
  check("nieuw: submitListing wacht vóór de knop",
        SHARED.indexOf("await wachtOpPostcode()") <
        SHARED.indexOf('qs(\'[data-testid="place-listing-submit-button"]\')'));

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
