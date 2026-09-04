/**
 * "2dehands geeft nu weer deze melding" — Daniel, 04-09-2026.
 *
 * Zijn scherm: het zoekertje (598) Burgundy Suitsupply Turtleneck, beschrijving
 * zichtbaar in de editor, en er rood onder: "Geen zoekertjestekst ingevuld."
 * Typte hij zelf één spatie, dan verdween de melding en ging het zoekertje eruit.
 * Soms liep dezelfde ronde wél door. In zijn opdrachtenlijst is dat terug te
 * zien: (598) duurde 9 minuten 20, de twee zoekertjes erna 20 en 21 seconden.
 *
 * GEMETEN OP HET ECHTE FORMULIER (04-09-2026, ingelogd, 2dehands.be én
 * marktplaats.nl, categorie Heren > Truien en Vesten):
 *   * het plaatsformulier is een react-hook-form; de controle bij het plaatsen
 *     leest `control._formValues.description`;
 *   * de zichtbare editor vullen zet 122 tekens in beeld en laat die waarde op
 *     0 staan — het formulier "ziet" dus geen tekst;
 *   * het verborgen veld description_nl-BE vullen helpt niet (React kent die
 *     waarde niet) en execCommand doet in deze editor helemaal niets;
 *   * de validatie van het formulier zelf laten draaien (handleSubmit met eigen
 *     callbacks, dus zonder te plaatsen) gaf met een gevulde editor de fout op
 *     `description`, en na alleen `_formValues.description` te vullen viel
 *     `description` uit de foutenlijst weg. Op beide platforms.
 *
 * Deze test bewaakt die drie functies met een nagebouwd formulier: vullen,
 * teruglezen, en de bewaker die de waarde terugzet als een hertekening hem
 * leeggooit — dat laatste is precies waarom het "soms wel, soms niet" was.
 *
 * Draaien: node tests/zoekertjestekst-formulierstaat-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const SHARED = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "shared.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}
function functieUit(bron, naam) {
  const start = bron.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = bron.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return bron.slice(start, eind + 2);
}

// ── Een nagebouwd plaatsformulier ────────────────────────────────────────
//
// Zo dun mogelijk, maar met precies de vorm die op het echte formulier gemeten
// is: een element met een __reactFiber$-sleutel, een keten van fibers, en ergens
// in de hooks van zo'n fiber het react-hook-form-object met _fields en
// _formValues.
function maakFormulier({ diepte = 8, hook = 17, metDescription = true } = {}) {
  const control = {
    _fields: metDescription ? { description: { _f: { name: "description", value: "" } } } : { title: {} },
    _formValues: metDescription ? { title: "", description: "" } : { title: "" },
  };
  // hooks: een gekoppelde lijst, control zit pas op positie `hook`
  let hooks = null;
  for (let i = 40; i >= 0; i--) {
    hooks = { memoizedState: i === hook ? { current: control } : { tag: 1 }, next: hooks };
  }
  let fiber = { memoizedState: hooks, return: null };
  for (let d = 0; d < diepte; d++) fiber = { memoizedState: null, return: fiber };
  const editor = { dataset: { testid: "text-editor-input_nl-BE" } };
  editor["__reactFiber$abc123"] = fiber;
  return { control, editor };
}

function zetOmgeving(editor) {
  global.document = {
    querySelector: (sel) => (sel.includes("text-editor-input") ? editor : null),
  };
  if (typeof global.window === "undefined") global.window = {};
}

const zetBron   = functieUit(BG, "_mwZetFormulierBeschrijving");
const leesBron  = functieUit(BG, "_mwLeesFormulierBeschrijving");
const bewaakBron = functieUit(BG, "_mwBewaakFormulierBeschrijving");
// eslint-disable-next-line no-eval
const _mwZetFormulierBeschrijving   = eval(`(${zetBron})`);
const _mwLeesFormulierBeschrijving  = eval(`(${leesBron})`);
const _mwBewaakFormulierBeschrijving = eval(`(${bewaakBron})`);

const TEKST = "(598) Burgundy Suitsupply Turtleneck -  XXL - New With Tags";

// ── 1. Vullen en teruglezen ──────────────────────────────────────────────
console.log("\nDe beschrijving belandt in de staat waar het formulier op controleert");
{
  const { control, editor } = maakFormulier();
  zetOmgeving(editor);
  check("voor het vullen houdt het formulier 0 tekens vast",
    _mwLeesFormulierBeschrijving() === 0);
  const geschreven = _mwZetFormulierBeschrijving(TEKST);
  check("vullen meldt het aantal tekens terug", geschreven === TEKST.length,
    `kreeg ${geschreven}, verwachtte ${TEKST.length}`);
  check("de waarde staat in _formValues", control._formValues.description === TEKST);
  check("en ook op het veld zelf", control._fields.description._f.value === TEKST);
  check("teruglezen geeft dezelfde lengte", _mwLeesFormulierBeschrijving() === TEKST.length);
}

// ── 2. Een formulier dat niet zo werkt ───────────────────────────────────
//
// Vinted en Facebook hebben dit soort staat niet. Dan moet de uitkomst -1 zijn
// ("niet van toepassing") en NOOIT 0, want 0 betekent "leeg" en zou een zoekertje
// tegenhouden dat prima geplaatst had kunnen worden.
console.log("\nEen platform zonder dit soort formulier levert -1, geen 0");
{
  global.document = { querySelector: () => null };
  check("vullen geeft -1", _mwZetFormulierBeschrijving(TEKST) === -1);
  check("teruglezen geeft -1", _mwLeesFormulierBeschrijving() === -1);
  const { editor } = maakFormulier({ metDescription: false });
  zetOmgeving(editor);
  check("een formulier zonder beschrijvingsveld geeft ook -1",
    _mwZetFormulierBeschrijving(TEKST) === -1);
}

// ── 3. De bewaker ────────────────────────────────────────────────────────
//
// Dit is de kern van "soms wel, soms niet": tussen het invullen en de knop
// Plaatsen zitten de foto's, de kenmerken en het merk-venster. Elke hertekening
// kan de waarde terugzetten op leeg.
console.log("\nDe bewaker zet de waarde terug zodra een hertekening hem leeggooit");
(async () => {
  const { control, editor } = maakFormulier();
  zetOmgeving(editor);
  _mwZetFormulierBeschrijving(TEKST);
  const aan = _mwBewaakFormulierBeschrijving(TEKST, 5000);
  check("de bewaker start", aan === true);

  control._formValues.description = "";           // hertekening gooit hem leeg
  check("direct na het leeghalen staat er niets", _mwLeesFormulierBeschrijving() === 0);
  await new Promise((r) => setTimeout(r, 700));
  check("binnen een seconde staat de tekst er weer",
    _mwLeesFormulierBeschrijving() === TEKST.length,
    `staat nu op ${_mwLeesFormulierBeschrijving()}`);

  // De bewaker mag NOOIT overschrijven wat het formulier er zelf in zet.
  control._formValues.description = "door de verkoper zelf getypt";
  await new Promise((r) => setTimeout(r, 500));
  check("tekst die er al staat blijft staan",
    control._formValues.description === "door de verkoper zelf getypt");

  clearInterval(global.window.__ovFormDescKeeper);

  // ── 4. Het invulscript gebruikt ze ook echt ──────────────────────────
  console.log("\nHet invulscript roept ze aan op de plekken die ertoe doen");
  check("bij het invullen van de beschrijving", SHARED.includes('runInMainWorld("FILL_FORM_DESC"'));
  check("de bewaker gaat mee aan", SHARED.includes('runInMainWorld("ENFORCE_FORM_DESC"'));
  check("vlak voor het plaatsen wordt teruggelezen", SHARED.includes('runInMainWorld("READ_FORM_DESC"'));
  check("en een lege staat houdt het plaatsen tegen",
    /if \(!zichtbaarLeeg && inStaat !== 0\)/.test(SHARED));
  check("de foutmelding vertelt hoeveel het formulier vasthield",
    SHARED.includes("The form's own description value:"));
  check("de herstelronde zet de staat opnieuw",
    /FILL_HIDDEN_DESC[\s\S]{0,400}FILL_FORM_DESC/.test(SHARED));

  console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} controle(s) mislukt.\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
