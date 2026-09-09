/**
 * Egbert Brouwer (papas-plectrums), 09-09-2026:
 *   "Ik probeer nu listings op 2eHands te krijgen, ineens zie ik 3 nieuwe tabs
 *    geopend van 2eHands, met allemaal factuurtjes die betaald moeten worden.
 *    Dit is natuurlijk niet wat we willen."
 *
 * DE GEMETEN OORZAAK, uit zijn eigen opdrachten in de database:
 *
 *   [tab op https://www.2dehands.be/payments/orderOverview/index.html,
 *    titel "2dehands - De plek om nieuwe en tweedehands zaken te kopen e",
 *    4 invulveld(en), invulscript geladen: nee]
 *   [laatste stap: "plaatsen: op de knop geklikt, wachten op de advertentie",
 *    190s geleden] [extensie 1.0.314]
 *
 * Drie opdrachten (18:59, 19:08, 19:13) dragen dat adres letterlijk. Precies de
 * drie tabbladen met factuurtjes die hij zag.
 *
 * Het formulier ging dus WEL open, werd WEL ingevuld, en er werd WEL op
 * plaatsen geklikt. 2dehands.be publiceerde de advertentie alleen niet: het
 * zette haar als bestelregel van EUR 9,00 ("Websitevermelding") in een
 * openstaande bestelling. Wij wachtten daarna drie minuten op een
 * advertentie-adres dat nooit komt, en meldden vervolgens "het formulier ging
 * nooit open, je bent misschien niet ingelogd". Hij was ingelogd; zijn eigen
 * scan van diezelfde minuut gaf HTTP 200 op het afgeschermde overzicht.
 *
 * En de rem maakte het duurder in plaats van goedkoper: die zette het kanaal op
 * pauze maar liet bewust één proefadvertentie per ronde door. Elke proef was
 * weer EUR 9,00. Zijn winkelmandje: 17 regels, EUR 153,00.
 *
 * Draaien: node tests/2dehands-betaalmuur-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function functieUit(bron, naam, woord = "function") {
  const start = bron.indexOf(`${woord} ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return bron.slice(start, eind + 2);
}

// Het adres dat in zijn opdrachten staat. Niet verzonnen: overgenomen.
const BETAALADRES = "https://www.2dehands.be/payments/orderOverview/index.html";

// ── 1. Herkennen we het adres uberhaupt? ──────────────────────────────────
console.log("\nHet adres uit zijn eigen opdrachten wordt herkend");

const MP_BETAALPAGINA = eval(BG.match(/const MP_BETAALPAGINA = (\/.*\/i);/)[1]);
const MP_LOGINPAGINA = eval(BG.match(/const MP_LOGINPAGINA = (\/.*\/i);/)[1]);

check("de betaalpagina wordt herkend", MP_BETAALPAGINA.test(BETAALADRES));
check("ook de Marktplaats-variant", MP_BETAALPAGINA.test(
  "https://www.marktplaats.nl/payments/orderOverview/index.html"));
check("een gewone geplaatste advertentie NIET",
  !MP_BETAALPAGINA.test("https://www.2dehands.be/v/muziek/m2295707200-miniatuur-gitaar"));
check("het plaatsformulier zelf NIET",
  !MP_BETAALPAGINA.test("https://www.2dehands.be/plaats/728/748"));
check("het verkopersoverzicht NIET",
  !MP_BETAALPAGINA.test("https://www.2dehands.be/my-account/sell/index.html"));

// VOOR-EN-NA, op het niveau waar het misging: de oude code had maar één
// vangnet voor een tabblad dat ergens anders uitkwam, en dat was de
// inlogpagina. Op dit adres greep dat niet, en dus viel het door naar de
// bewaker van drie minuten en daarna naar de gok over inloggen.
console.log("\nVOOR: de oude code kon dit adres met geen mogelijkheid zien");
check("VOOR: de inlogherkenning slaat op dit adres niet aan",
  !MP_LOGINPAGINA.test(BETAALADRES),
  "daarom liep het door naar de bewaker en werd het 'formulier ging nooit open'");
check("VOOR: het is ook geen advertentie-adres, dus 'gelukt' werd het ook nooit",
  !/2dehands\.be\/v\/[^/]+\/(m\d+)/.test(BETAALADRES));
check("NA: de nieuwe herkenning ziet het wel", MP_BETAALPAGINA.test(BETAALADRES));

// ── 2. Alleen een plaatsing, nooit een scan of een verwijdering ──────────
console.log("\nEen betaalpagina mag alleen een plaatsing afbreken");

const raakt = new Function("return " + functieUit(BG, "betaalmuurRaaktDezeOpdracht"))();
check("een plaatsing op 2dehands telt mee",
  raakt({ platform: "2dehands", action: "create" }));
check("een verversing ook",
  raakt({ platform: "2dehands", action: "content_refresh" }));
check("een verwijdering niet",
  !raakt({ platform: "2dehands", action: "delete" }));
check("een scan niet",
  !raakt({ platform: "2dehands", action: "scan" }));
check("Vinted niet", !raakt({ platform: "vinted", action: "create" }));
check("een leeg geval niet", !raakt(null));

// ── 3. Wat de verkoper te lezen krijgt, en wat er met de rij gebeurt ─────
console.log("\nDe melding zegt wat er is, en de rij gaat dicht");

const omgeving = { verstuurdeFouten: [], geslotenTabs: [], gestopt: [], opslag: {} };
const chrome = {
  alarms: { clear: () => {} },
  runtime: { getManifest: () => ({ version: "1.0.315" }) },
  storage: {
    local: {
      get: async (k) => (k in omgeving.opslag ? { [k]: omgeving.opslag[k] } : {}),
      set: async (o) => Object.assign(omgeving.opslag, o),
      remove: async (k) => { delete omgeving.opslag[k]; },
    },
  },
};
const stubs = `
  const reportError = async (jobId, serverUrl, tekst) => { omgeving.verstuurdeFouten.push(tekst); };
  const sluitWerkTabblad = (tabId) => omgeving.geslotenTabs.push(tabId);
  const clearJobWatchdog = () => { omgeving.bewakerGewist = true; };
  const getAuthHeaders = async () => ({ Authorization: "Bearer x" });
  const fetch = async (url, opties) => {
    omgeving.gestopt.push({ url, body: JSON.parse(opties.body) });
    return { json: async () => ({ ok: true, cancelled: 732 }) };
  };
`;
const bron = [
  stubs,
  BG.slice(BG.indexOf("const SITE_NAAM"), BG.indexOf("\n};", BG.indexOf("const SITE_NAAM")) + 3),
  functieUit(BG, "stopPlatformWachtrij", "async function"),
  functieUit(BG, "meldBetaalmuur", "async function"),
  "return meldBetaalmuur;",
].join("\n");
const meldBetaalmuur = new Function("chrome", "omgeving", bron)(chrome, omgeving);

(async () => {
  const meta = {
    jobId: "j1", serverUrl: "https://omnivaleur.com", platform: "2dehands",
    action: "create", submitClicked: true,
  };
  omgeving.opslag["jobtab_7"] = meta;
  await meldBetaalmuur(7, meta, BETAALADRES + "?orderId=2957072004");

  const tekst = omgeving.verstuurdeFouten[0] || "";
  check("de melding zegt dat het account niet gratis kan plaatsen",
    /does not let this account place adverts for free/i.test(tekst), tekst.slice(0, 120));
  check("en dat het formulier wel degelijk is ingevuld en geplaatst",
    /form was filled in and published/i.test(tekst),
    "hij heeft het zien gebeuren; ontkennen kost het laatste vertrouwen");
  check("en dat er niets online staat en niets betaald is",
    /nothing went online/i.test(tekst) && /nothing has been paid/i.test(tekst));
  check("de melding wijst naar de bestelling die hij moet leegmaken",
    tekst.includes(BETAALADRES), tekst.slice(-200));
  check("de vraagtekens uit het adres zijn eraf",
    !/orderId=2957072004/.test(tekst),
    "een bestelnummer van gisteren stuurt hem naar de verkeerde bestelling");
  check("de melding zegt dat zijn andere kanalen blijven werken",
    /other channels keep working/i.test(tekst));
  check("de oude, onjuiste gok over inloggen staat er NIET in",
    !/sign(ed)? in/i.test(tekst) && !/never opened/i.test(tekst),
    "dat is precies de tekst die hem een week de verkeerde kant op stuurde");

  check("de bewaker van drie minuten wordt meteen afgezet",
    omgeving.bewakerGewist === true,
    "anders staat hij alsnog drie minuten naar een betaalpagina te kijken");
  check("het tabblad met de factuur gaat dicht",
    omgeving.geslotenTabs.includes(7),
    "hij zag drie van die tabbladen tegelijk openstaan");
  check("er blijven geen spookgegevens achter", !("jobtab_7" in omgeving.opslag));

  check("de hele rij voor dit kanaal wordt in EEN keer teruggenomen",
    omgeving.gestopt.length === 1, JSON.stringify(omgeving.gestopt).slice(0, 150));
  check("en dan alleen voor 2dehands",
    (omgeving.gestopt[0] || {}).body?.platform === "2dehands");
  check("de reden gaat mee naar de server, met het adres erin",
    ((omgeving.gestopt[0] || {}).body?.reason || "").includes(BETAALADRES));

  // EEN KEER IS GENOEG. Bij "formulier ging nooit open" wacht de code bewust op
  // een tweede keer, want eenmalige pech mag geen 279 opdrachten kosten. Hier
  // niet: elke volgende poging is weer EUR 9,00.
  check("bij de EERSTE betaalpagina gaat de rij al dicht",
    omgeving.gestopt.length === 1,
    "wachten op een tweede keer kost hem hier echt geld");

  // ── 4. Zonder plaatsklik: een ander verhaal, dezelfde uitkomst ─────────
  console.log("\nEn als hij al bij het openen op de betaalpagina belandt");
  omgeving.verstuurdeFouten.length = 0;
  omgeving.opslag["jobtab_9"] = { ...meta, jobId: "j2", submitClicked: false };
  await meldBetaalmuur(9, { ...meta, jobId: "j2", submitClicked: false }, BETAALADRES);
  const tweede = omgeving.verstuurdeFouten[0] || "";
  check("dan zeggen we niet dat het formulier is ingevuld",
    !/form was filled in/i.test(tweede), tweede.slice(0, 120));
  check("maar dat 2dehands ons meteen naar de betaalpagina stuurde",
    /straight to its payment page/i.test(tweede));
  check("en de uitkomst is dezelfde: kanaal uit",
    omgeving.gestopt.length === 2);

  // ── 5. Zit het ook echt in de adresbewaking? ──────────────────────────
  console.log("\nDe sprong wordt live opgevangen, niet pas na drie minuten");
  const bewakingsblok = BG.slice(BG.indexOf("chrome.tabs.onUpdated.addListener(async (tabId, changeInfo)"));
  check("de adresbewaking kent de betaalpagina",
    /MP_BETAALPAGINA\.test\(changeInfo\.url\)/.test(bewakingsblok),
    "zonder dit sterft het invulscript bij de navigatie en meldt niemand iets");
  check("en roept dezelfde afhandeling aan",
    /await meldBetaalmuur\(tabId, meta, changeInfo\.url\)/.test(bewakingsblok));
  check("de controle staat VOOR de 'alleen bij create'-afslag",
    bewakingsblok.indexOf("MP_BETAALPAGINA") <
    bewakingsblok.indexOf('if (meta.action && meta.action !== "create") return;'),
    "anders valt een verversing eruit voordat we haar zien");

  const bewaker = functieUit(BG, "fireJobWatchdog", "async function");
  check("en de bewaker heeft hetzelfde vangnet voor een slapend achtergrondproces",
    /MP_BETAALPAGINA\.test\(snap\.url/.test(bewaker));
  check("dat vangnet staat VOOR de nietszeggende tijdsoverschrijding",
    bewaker.indexOf("MP_BETAALPAGINA") <
    bewaker.indexOf("Extension timed out waiting for this"),
    "anders wint 'de pagina is misschien veranderd' alsnog");

  console.log(mislukt ? `\n${mislukt} controle(s) MISLUKT` : "\nAlles groen");
  process.exit(mislukt ? 1 : 0);
})();
