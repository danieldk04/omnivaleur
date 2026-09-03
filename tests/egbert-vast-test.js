/**
 * Egbert Brouwer (papas-plectrums), 03-09-2026:
 *   "Ik loop compleet vast hier, kan niet doen wat ik wil doen."
 *   "Ik wilde alle artikelen die het woordje miniatuur in zich hebben
 *    selecteren... ik kwam niet verder dan 150 artikelen."
 *   "Ik zie ook geen knop om deze alsnog op te halen."
 *
 * Drie klachten, drie oorzaken, alle drie gemeten aan zijn eigen account
 * (5.533 artikelen: miniatuurgitaren en plectrums).
 *
 * 1. VASTGELOPEN. Van zijn 305 opdrachten voor 2dehands is er nooit één
 *    geslaagd. 26 werden er afgebroken door de bewaker na exact drie minuten,
 *    telkens zonder één teken van leven uit het tabblad; 279 stonden er nog
 *    achter. Zijn Marktplaats-opdrachten uit dezelfde ronde liepen wel door
 *    (15 geplaatst) en bij andere verkopers slaagde 2dehands in dezelfde
 *    periode 97 keer. www.2dehands.be antwoordt op het plaatsadres met
 *    HTTP 401 zolang je daar niet bent ingelogd (nagemeten: 12 bytes platte
 *    tekst, geen formulier). Op zo'n pagina draait ons invulscript niet.
 *
 * 2. SELECTEREN. Het vinkje in de kop pakte alleen de getekende bladzijde,
 *    vijftig rijen. Zijn zoekopdracht levert er 434 op: negen bladzijden.
 *
 * 3. DE KNOP. "Fill from Marktplaats" telde merk en maat mee. Geen enkele
 *    gitaar heeft een maat en vrijwel geen een merk, dus stond er eeuwig
 *    "Fill 5533 from Marktplaats" terwijl er 11 artikelen iets misten.
 *
 * Draaien: node tests/egbert-vast-test.js
 */
const fs = require("fs");
const path = require("path");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");
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

// ── 1. Het formulier ging nooit open ────────────────────────────────────
console.log("\nDe bewaker onderscheidt 'vastgelopen' van 'nooit opengegaan'");

const bewaker = functieUit(BG, "fireJobWatchdog", "async function");
check("de bewaker kijkt of het invulscript zich ooit meldde",
  /if \(!meta\.scriptSeen\)/.test(bewaker),
  "zonder deze splitsing krijgt iedereen 'de pagina is misschien veranderd'");
check("die controle staat VOOR de algemene tijdsoverschrijding",
  bewaker.indexOf("!meta.scriptSeen") < bewaker.indexOf("did not finish in time"),
  "anders wint de oude, nietszeggende melding alsnog");
check("GET_JOB stempelt dat het invulscript er echt was",
  /scriptSeen: true/.test(BG),
  "zonder stempel weet de bewaker nooit of het formulier openging");

// De echte meldNooitBegonnen draaien, met een nagebootste browser.
const omgeving = { verstuurdeFouten: [], geslotenTabs: [], gestopt: [], opslag: {} };
const chrome = {
  tabs: {
    get: async () => ({ url: "https://www.2dehands.be/plaats/728/748?title=" }),
  },
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
  const getAuthHeaders = async () => ({ Authorization: "Bearer x" });
  const fetch = async (url, opties) => {
    omgeving.gestopt.push({ url, body: JSON.parse(opties.body) });
    return { json: async () => ({ ok: true, cancelled: 279 }) };
  };
`;
const bron = [
  stubs,
  BG.slice(BG.indexOf("const NIET_GESTART_PREFIX"), BG.indexOf("const SITE_NAAM")),
  BG.slice(BG.indexOf("const SITE_NAAM"), BG.indexOf("\n};", BG.indexOf("const SITE_NAAM")) + 3),
  functieUit(BG, "stopPlatformWachtrij", "async function"),
  functieUit(BG, "meldNooitBegonnen", "async function"),
  "return meldNooitBegonnen;",
].join("\n");
const meldNooitBegonnen = new Function("chrome", "omgeving", bron)(chrome, omgeving);

const meta = { jobId: "j1", serverUrl: "https://omnivaleur.com", platform: "2dehands", action: "create" };

(async () => {
  omgeving.opslag["jobtab_7"] = meta;
  await meldNooitBegonnen(7, meta);

  const eerste = omgeving.verstuurdeFouten[0] || "";
  check("de melding zegt dat het formulier nooit openging",
    /never opened/i.test(eerste), eerste.slice(0, 90));
  check("de melding noemt de site waar hij moet inloggen",
    /2dehands\.be/.test(eerste) && /sign in/i.test(eerste), eerste.slice(0, 90));
  check("de melding legt uit dat het twee aparte logins zijn",
    /separate logins/i.test(eerste),
    "hij is op Marktplaats wel ingelogd, dus zonder dit klopt 'log in' niet voor hem");
  check("de oude, nietszeggende reden staat er NIET meer bij",
    !/page may have changed/i.test(eerste));
  check("het lege tabblad wordt opgeruimd",
    omgeving.geslotenTabs.includes(7),
    "er valt niets met de hand af te maken: er staat geen formulier");
  check("de opdracht laat geen spookgegevens achter",
    !("jobtab_7" in omgeving.opslag));

  check("na één keer wordt de wachtrij NOG NIET gestopt",
    omgeving.gestopt.length === 0,
    "eenmalige pech mag niet 279 opdrachten kosten");

  // Tweede keer op rij: nu is het geen pech meer.
  omgeving.opslag["jobtab_8"] = meta;
  await meldNooitBegonnen(8, { ...meta, jobId: "j2" });
  check("na twee keer op rij wordt de rest van de rij teruggenomen",
    omgeving.gestopt.length === 1, JSON.stringify(omgeving.gestopt));
  check("de rij wordt gestopt voor het juiste kanaal",
    (omgeving.gestopt[0] || {}).body?.platform === "2dehands");
  check("de reden gaat mee naar de server",
    /never opened/i.test((omgeving.gestopt[0] || {}).body?.reason || ""));
  check("de teller staat daarna weer op nul",
    !("nietgestart_2dehands" in omgeving.opslag),
    "anders stopt de eerstvolgende mislukking meteen de hele rij");

  // VOOR-EN-NA. De oude bewaker kende geen scriptSeen: die stuurde ALTIJD
  // dezelfde tekst en stopte de rij nooit. Bewijs dat het verschil echt is.
  const oudeTekst = "Extension timed out waiting for this 2dehands job to finish " +
    "(no response after 3 minutes). The page may have changed, needs a manual step, " +
    "or the extension lost track of the tab.";
  check("VOOR: de oude tekst noemt inloggen niet",
    !/sign in/i.test(oudeTekst) && !/2dehands\.be/.test(oudeTekst));
  check("NA: de nieuwe tekst wel", /sign in/i.test(eerste));

  // ── 2. Alles selecteren wat aan het filter voldoet ────────────────────
  console.log("\nAlle artikelen die aan het filter voldoen, in één klik");

  // Zijn echte aantallen: 5.533 artikelen, 434 met "miniatuur" in de titel.
  const alle = [];
  for (let i = 0; i < 5533; i++) {
    alle.push({ id: "i" + i, title: i < 434 ? `Miniatuur replica gitaar ${i}` : `Plectrum ${i}` });
  }
  const gefilterd = alle.filter(i => i.title.toLowerCase().includes("miniatuur"));
  check("de zoekopdracht levert 434 artikelen op", gefilterd.length === 434);

  const kop = { checked: false };
  const rijen = gefilterd.slice(0, 50).map(i => ({
    id: "row-" + i.id, className: "", querySelector: () => ({ checked: false }),
  }));
  const document = {
    getElementById: (id) => (id === "check-all" ? kop : null),
    querySelectorAll: () => rijen,
  };
  const selectedIds = new Set();
  const selectAllFiltered = new Function(
    "document", "selectedIds", "itemsGefilterd", "updateBulkBar",
    functieUit(APP, "selectAllFiltered") + "\nreturn selectAllFiltered;"
  )(document, selectedIds, gefilterd, () => {});

  // VOOR: het vinkje in de kop pakte alleen de getekende bladzijde.
  const alleenBladzijde = new Set(rijen.map(r => r.id.replace("row-", "")));
  check("VOOR: het kopvinkje kwam niet verder dan 50 van de 434",
    alleenBladzijde.size === 50,
    "drie bladzijden aanklikken is de 150 waar hij op vastliep");

  selectAllFiltered();
  check("NA: alle 434 staan in de selectie", selectedIds.size === 434, `${selectedIds.size}`);
  check("NA: ook de artikelen buiten de getekende bladzijde",
    selectedIds.has("i400") && selectedIds.has("i433"));
  check("NA: niets erbij dat niet aan het filter voldoet",
    !selectedIds.has("i5000"));
  check("het kopvinkje staat daarna aan", kop.checked === true);

  check("applyFilters bewaart de hele uitkomst, niet alleen de bladzijde",
    /itemsGefilterd = filtered;/.test(APP),
    "zonder dit reikt 'alles selecteren' nooit verder dan het scherm");
  check("de balk biedt de klik pas aan als er echt meer is",
    /itemsGefilterd\.length > n/.test(APP));

  // ── 3. De knop die de ontbrekende gegevens ophaalt ────────────────────
  console.log("\nDe knop telt alleen wat er echt ontbreekt");

  const hulp = [
    APP.slice(APP.indexOf("const NON_CLOTHING_PREFIXES"), APP.indexOf("\n", APP.indexOf("const NON_CLOTHING_PREFIXES")) + 1),
    functieUit(APP, "isNonClothingItem"),
    functieUit(APP, "mistMarktplaatsGegevens"),
    "return mistMarktplaatsGegevens;",
  ].join("\n");
  const mist = new Function(hulp)();

  // Zijn echte voorraad: gitaren met prijs en tekst, zonder merk en zonder maat.
  const gitaar = { price: 17.95, description: "Mooie miniatuur", photo_urls: ["a", "b"],
                   brand: "", size: "", category: "muziek snaarinstrumenten gitaren elektrisch" };
  check("NA: een gitaar zonder merk en maat mist niets", mist(gitaar) === false,
    "Marktplaats vraagt daar in de tak muziek helemaal niet om");
  check("een gitaar zonder prijs mist wel iets",
    mist({ ...gitaar, price: null }) === true);
  check("een gitaar zonder tekst mist wel iets",
    mist({ ...gitaar, description: "" }) === true);
  check("een gitaar met één foto mist wel iets",
    mist({ ...gitaar, photo_urls: ["a"] }) === true);
  check("een kledingstuk zonder maat mist nog steeds wel iets",
    mist({ ...gitaar, category: "truien" }) === true,
    "daar blokkeert een ontbrekende maat het plaatsen echt");

  // VOOR-EN-NA op zijn echte voorraad.
  const oudeRegel = (i) => !i.price || !String(i.description || "").trim()
    || (i.photo_urls || []).length <= 1
    || !String(i.brand || "").trim() || !String(i.size || "").trim();
  const voorraad = [];
  for (let i = 0; i < 5533; i++) {
    voorraad.push({ ...gitaar, description: i < 11 ? "" : "Mooie miniatuur" });
  }
  const voor = voorraad.filter(oudeRegel).length;
  const na = voorraad.filter(mist).length;
  check("VOOR: de knop riep 5533", voor === 5533, `${voor}`);
  check("NA: de knop noemt de 11 die het echt betreft", na === 11, `${na}`);

  // ── 4. De inlogverdenking was ongegrond ───────────────────────────────
  //
  // Egbert kreeg op 303 artikelrijen te lezen dat hij niet was ingelogd op
  // 2dehands, en mailde terug: "Ik ben ingelogd op 2dehands, dus weet niet wat
  // er nu mis gaat?" Hij had gelijk, en twee metingen bewijzen dat:
  //
  //   1. Het advertentie-overzicht (/my-account/sell/api/listings) is
  //      afgeschermd. Een kale aanvraag zonder cookies krijgt HTTP 401,
  //      twaalf bytes "Unauthorized" — op 2dehands.be én op marktplaats.nl.
  //      Zijn scan kreeg HTTP 200. Dat kan alleen met een geldige sessie.
  //   2. De inlogcontrole zelf zocht naar "mijn marktplaats" en "uitloggen" in
  //      de paginatekst. Op 2dehands staan die woorden er niet, dus was het
  //      antwoord daar altijd "niet ingelogd", hoe goed je ook was ingelogd.
  console.log("\nEen 200 van de site weegt zwaarder dan een woord op de pagina");

  const reden = eval("(" + functieUit(BG, "mpEmptyScanReason") + ")");

  const ingelogd200 = reden(
    { api_status: 200, fetched: 0, total_entries: 0, signed_in: false }, "2dehands");
  check("VOOR: de oude tekst luidde 'You don't appear to be signed in'",
    /You don't appear to be signed in/.test(
      reden({ api_status: null, fetched: 0, signed_in: false }, "2dehands")),
    "die tekst hoort te blijven bestaan voor het geval dat hij wél klopt");
  check("NA: bij HTTP 200 valt het woord 'not signed in' niet meer",
    !/don't appear to be signed in|not signed in/i.test(ingelogd200),
    ingelogd200.slice(0, 120));
  check("NA: bij HTTP 200 staat er dat hij juist wél is ingelogd",
    /You are signed in to 2dehands/.test(ingelogd200), ingelogd200.slice(0, 120));
  check("NA: en dat er simpelweg niets te importeren valt",
    /nothing to import/.test(ingelogd200), ingelogd200.slice(0, 160));
  check("de waargenomen feiten staan er nog steeds bij",
    /API 200/.test(ingelogd200), ingelogd200.slice(-90));

  // Zegt de site zelf dat er advertenties zijn en lezen wij er nul, dan is er
  // wél iets stuk — maar bij ons, niet bij zijn inlog.
  const leesfout = reden(
    { api_status: 200, fetched: 0, total_entries: 812, signed_in: false }, "2dehands");
  check("zegt de site 812 advertenties en lezen wij er nul, dan is dat ONZE fout",
    /problem on our side/.test(leesfout) && !/not signed in/i.test(leesfout),
    leesfout.slice(0, 140));

  // Een echte weigering blijft gewoon een weigering.
  const geweigerd = reden({ api_status: 401, fetched: 0, signed_in: false }, "2dehands");
  check("HTTP 401 blijft 'log opnieuw in'", /foutcode 401/.test(geweigerd), geweigerd.slice(0, 100));

  check("de inlogcontrole kent nu ook de woorden van 2dehands",
    /mijn 2dehands/.test(BG) && /afmelden/.test(BG),
    "anders blijft elke ingelogde 2dehands-verkoper 'niet ingelogd'");

  const scan = functieUit(BG, "bgScanMp2dh", "async function");
  check("een ingelogd maar leeg account rondt netjes af in plaats van rood",
    /leeg_account: true/.test(scan) && /echtLeeg/.test(scan),
    "een account zonder advertenties is geen storing");
  check("dat mag alleen als de site zelf zegt dat er niets staat",
    /api_status === 200 && !result\.meta\?\.total_entries/.test(scan),
    "anders verdoezelt het een leesfout aan onze kant");

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles groen");
  process.exit(mislukt ? 1 : 0);
})();
