/**
 * Waar de verkoper staat, op het formulier van Marktplaats en 2dehands.
 *
 * De Juiste Toon, 10-09-2026: zijn zoekertjes op 2dehands kwamen niet door,
 * veertien keer, allemaal op onze eigen weigering "postcode leeg". Nagemeten op
 * een ingelogd 2dehands-account: het account kent maar één adresgegeven, een
 * Belgische postcode, en hij woont in Nederland. Zijn 402 zoekertjes op
 * "Etten-Leur, Nederland" staan in acht spellingen, want hij tikt het adres bij
 * elk zoekertje opnieuw in.
 *
 * Het blok zelf is live afgelezen op www.2dehands.be/plaats/728/748 en
 * www.marktplaats.nl/plaats/728/748 (11-09-2026):
 *   input#syi-address-radio-home    label "België" resp. "Nederland"
 *   input#syi-address-radio-abroad  label "Buitenland"
 *   thuis:      input[name="contactInformation.postCode"]
 *   buitenland: select#country (op naam) + input[name="contactInformation.foreignCity"],
 *               en het postcodeveld VERDWIJNT dan uit het formulier.
 *
 * Draaien: node tests/locatie-op-het-formulier-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// Vaste commit van vóór de reparatie. Nooit HEAD: na het committen zou de
// voor-proef de reparatie met zichzelf vergelijken en altijd slagen.
const VOOR_DE_REPARATIE = "08db2331";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function bronNu() {
  return fs.readFileSync(path.join(WORTEL, "extension/content/shared.js"), "utf8");
}
function bronVoor() {
  return execSync(`git show ${VOOR_DE_REPARATIE}:extension/content/shared.js`,
                  { cwd: WORTEL, maxBuffer: 40 * 1024 * 1024 }).toString();
}

// Eén functie uit de bron knippen, zodat de proef de echte code draait en niet
// een nagetypte kopie ervan.
function functieUit(bron, naam) {
  const start = bron.indexOf(`function ${naam}(`);
  if (start === -1) return null;
  const kop = bron.lastIndexOf("\n", start);
  const eind = bron.indexOf("\n  }", start);
  return bron.slice(kop, eind + 4);
}

// ---- Een formulier dat zich gedraagt als het echte ------------------------
// Alleen wat vulLocatie aanraakt: twee keuzerondjes met hun label, een
// postcodeveld dat bij "Buitenland" verdwijnt, een landenlijst en een
// woonplaatsveld die er dan juist bij komen.
function maakFormulier({ thuisland = "België", postcode = "", landen = null } = {}) {
  const NAMEN = landen || ["Nederland", "Nederlandse Antillen", "Duitsland", "Frankrijk"];

  class Element {
    constructor() { this._luisteraars = []; }
    dispatchEvent() { return true; }
    addEventListener() {}
    scrollIntoView() {}
  }
  class HTMLInputElement extends Element {
    constructor(naam) { super(); this.name = naam; this._v = ""; this.checked = false; }
    get value() { return this._v; }
    set value(v) { this._v = v; }
    click() { formulier._kies(this); }
  }
  class HTMLSelectElement extends Element {
    constructor(namen) {
      super();
      this.id = "country";
      this.options = [{ value: "", text: "Kies...", disabled: false },
                      ...namen.map((t, i) => ({ value: String(100 + i), text: t, disabled: false }))];
      this.selectedIndex = 0;
    }
    get value() { return this.options[this.selectedIndex].value; }
    set value(v) {
      const i = this.options.findIndex((o) => o.value === v);
      if (i >= 0) this.selectedIndex = i;
    }
  }
  class HTMLTextAreaElement extends Element {}

  const home = new HTMLInputElement("syi-address-radio-home");
  home.id = "syi-address-radio-home";
  home.checked = true;
  const abroad = new HTMLInputElement("syi-address-radio-abroad");
  abroad.id = "syi-address-radio-abroad";
  const pc = new HTMLInputElement("contactInformation.postCode");
  pc.value = postcode;

  const formulier = {
    home, abroad, postcodeVeld: pc, land: null, stad: null,
    _kies(radio) {
      home.checked = radio === home;
      abroad.checked = radio === abroad;
      // Precies wat de site doet: bij Buitenland gaat het postcodeveld weg en
      // komen land en woonplaats ervoor in de plaats.
      if (abroad.checked) {
        formulier.postcodeVeld = null;
        formulier.land = new HTMLSelectElement(NAMEN);
        formulier.stad = new HTMLInputElement("contactInformation.foreignCity");
      } else {
        formulier.postcodeVeld = pc;
        formulier.land = null;
        formulier.stad = null;
      }
    },
  };

  const document = {
    getElementById: (id) => (id === home.id ? home : id === abroad.id ? abroad : null),
    querySelector: (sel) => {
      const m = /^label\[for="(.+)"\]$/.exec(sel);
      if (m) return { textContent: m[1] === home.id ? thuisland : "Buitenland" };
      return null;
    },
  };
  const qs = (sel) => {
    if (sel === 'input[name="contactInformation.postCode"]') return formulier.postcodeVeld;
    if (sel === 'input[name="contactInformation.foreignCity"]') return formulier.stad;
    if (sel === "select#country") return formulier.land;
    return null;
  };
  const window = { HTMLInputElement, HTMLSelectElement, HTMLTextAreaElement };
  return { formulier, document, qs, window };
}

function bouw(bron, omgeving) {
  const stukken = ["fillInput", "fillNativeSelect", "matchScore", "escapeRegex", "locatieLabel",
                   "zelfdeLand", "wachtOpElement", "vulLocatie", "postcodeVeld",
                   "wachtOpPostcode"]
    .map((n) => functieUit(bron, n)).filter(Boolean).join("\n");
  const constanten = (bron.match(/const LOC_HOME = .*\n\s*const LOC_ABROAD = .*/) || [""])[0]
    + "\n" + (bron.match(/const POSTCODE_WACHT_MS = \d+;/) || [""])[0];
  const logs = [];
  const maak = new Function(
    "document", "qs", "window", "sleep", "clog", "Event", "HTMLTextAreaElement",
    `${constanten}\n${stukken}\n return { vulLocatie: typeof vulLocatie === "function" ? vulLocatie : null, wachtOpPostcode };`);
  const api = maak(omgeving.document, omgeving.qs, omgeving.window,
                   (ms) => new Promise((r) => setTimeout(r, Math.min(ms, 30))),
                   (m) => logs.push(m),
                   function Event() { return {}; },
                   omgeving.window.HTMLTextAreaElement);
  return { ...api, logs };
}

(async () => {
  console.log("\nNIEUWE VERSIE");

  // 1. De zaak-Toon: Nederlander op 2dehands.be, postcode van het account leeg.
  {
    const omg = maakFormulier({ thuisland: "België", postcode: "" });
    const { vulLocatie, wachtOpPostcode } = bouw(bronNu(), omg);
    const uitslag = await vulLocatie({ location_country: "Nederland",
                                       location_city: "Etten-Leur" });
    const f = omg.formulier;
    check("kiest Buitenland", f.abroad.checked === true);
    check("zet het land op Nederland",
          f.land && f.land.options[f.land.selectedIndex].text === "Nederland",
          f.land ? f.land.options[f.land.selectedIndex].text : "geen landenlijst");
    check("vult de woonplaats", f.stad && f.stad.value === "Etten-Leur",
          f.stad ? f.stad.value : "geen woonplaatsveld");
    check("meldt terug wat er staat", /Etten-Leur/.test(uitslag) && /Nederland/.test(uitslag), uitslag);
    // En dan het punt van de hele oefening: plaatsen wordt niet meer geweigerd.
    let bezwaar = null;
    try { await wachtOpPostcode(); } catch (e) { bezwaar = e.message; }
    check("plaatsen wordt niet meer geweigerd op een lege postcode", bezwaar === null, bezwaar);
  }

  // 2. Eigen land: Nederlander op Marktplaats. Buitenland zou daar juist fout
  //    zijn — Nederland staat niet eens in die landenlijst.
  {
    const omg = maakFormulier({ thuisland: "Nederland", postcode: "" });
    const { vulLocatie, wachtOpPostcode } = bouw(bronNu(), omg);
    await vulLocatie({ location_country: "Nederland", location_city: "Etten-Leur",
                       location_postcode: "4871 AB" });
    const f = omg.formulier;
    check("blijft op de thuisknop staan", f.home.checked === true && f.abroad.checked === false);
    check("vult de eigen postcode in het lege veld",
          f.postcodeVeld && f.postcodeVeld.value === "4871 AB",
          f.postcodeVeld ? f.postcodeVeld.value : "veld weg");
    let bezwaar = null;
    try { await wachtOpPostcode(); } catch (e) { bezwaar = e.message; }
    check("en dan mag plaatsen door", bezwaar === null, bezwaar);
  }

  // 3. Een postcode die het formulier zelf al had blijft staan. Wat de site uit
  //    het account haalt weet het beter dan wij.
  {
    const omg = maakFormulier({ thuisland: "Nederland", postcode: "4614RG" });
    const { vulLocatie } = bouw(bronNu(), omg);
    await vulLocatie({ location_country: "Nederland", location_postcode: "4871 AB" });
    check("overschrijft een gevulde postcode niet",
          omg.formulier.postcodeVeld.value === "4614RG", omg.formulier.postcodeVeld.value);
  }

  // 4. Niets ingevuld = niets aanraken. Wie deze instelling leeg laat houdt
  //    precies het gedrag dat hij altijd had.
  {
    const omg = maakFormulier({ thuisland: "België", postcode: "" });
    const { vulLocatie, wachtOpPostcode } = bouw(bronNu(), omg);
    const uitslag = await vulLocatie({});
    check("laat het formulier met rust", omg.formulier.home.checked === true
          && omg.formulier.abroad.checked === false && /niet ingesteld/.test(uitslag), uitslag);
    let bezwaar = null;
    try { await wachtOpPostcode(); } catch (e) { bezwaar = e.message; }
    check("en de oude weigering geldt daar nog steeds", bezwaar !== null);
  }

  // 5. Een land dat deze site niet kent. Halverwege blijven staan is erger dan
  //    niets doen: "Buitenland" zonder land is een leeg verplicht veld.
  {
    const omg = maakFormulier({ thuisland: "België", postcode: "",
                                landen: ["Duitsland", "Frankrijk"] });
    const { vulLocatie } = bouw(bronNu(), omg);
    const uitslag = await vulLocatie({ location_country: "Nederland", location_city: "Etten-Leur" });
    check("valt terug op de thuisknop", omg.formulier.home.checked === true, uitslag);
    check("en zegt waaróm", /landenlijst/i.test(uitslag), uitslag);
  }

  // 6. "Nederland" mag nooit "Nederlandse Antillen" worden.
  {
    const omg = maakFormulier({ thuisland: "België", postcode: "",
                                landen: ["Nederlandse Antillen", "Nederland"] });
    const { vulLocatie } = bouw(bronNu(), omg);
    await vulLocatie({ location_country: "Nederland", location_city: "Etten-Leur" });
    const f = omg.formulier;
    check("kiest het land op de naam precies",
          f.land.options[f.land.selectedIndex].text === "Nederland",
          f.land.options[f.land.selectedIndex].text);
  }

  // VOOR-EN-NA. Dezelfde situatie als 1, met de code van vóór de reparatie.
  console.log(`\nOUDE VERSIE (${VOOR_DE_REPARATIE}, ter vergelijking)`);
  {
    const omg = maakFormulier({ thuisland: "België", postcode: "" });
    const { vulLocatie, wachtOpPostcode } = bouw(bronVoor(), omg);
    check("kende deze stap nog niet", vulLocatie === null);
    let bezwaar = null;
    try { await wachtOpPostcode(); } catch (e) { bezwaar = e.message; }
    check("en weigerde dus te plaatsen", bezwaar !== null && /postcode/i.test(bezwaar || ""),
          bezwaar || "geen weigering");
  }

  console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} controle(s) mislukt.\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
