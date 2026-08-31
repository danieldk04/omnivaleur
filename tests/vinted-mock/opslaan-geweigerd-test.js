// Draait de ECHTE foutlezers uit extension/content/vinted.js tegen een namaak-DOM.
// De code wordt uit het verscheepte bestand gesneden, zodat deze proef nooit een
// verouderde kopie test.
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.resolve(__dirname, "../../extension/content/vinted.js"), "utf8");

const reRegel = SRC.match(/^ {2}const FORM_ERR_RE = .*$/m);
const start = SRC.indexOf("  // Vult velden aan die op de Vinted-pagina leeg staan,");
const eind = SRC.indexOf("  // Locate the uploaded-photo tiles on the edit page.");
if (!reRegel || start < 0 || eind < 0 || eind <= start) {
  console.error("de foutlezers zijn niet te vinden in vinted.js — is het blok hernoemd?");
  process.exit(1);
}

const maak = new Function("document", "qs",
  reRegel[0] + "\n" + SRC.slice(start, eind) +
  "\nreturn { formErrorsVinted, emptyRequiredFieldsVinted, saveHintVinted, topUpRequiredFieldsVinted };");

// Namaakscherm: alleen wat deze functies écht opvragen.
function scherm(velden, foutregels) {
  const invoer = Object.entries(velden).map(([testid, value]) =>
    ({ testid, value, offsetParent: {}, textContent: "" }));
  const fouten = (foutregels || []).map((t) =>
    (typeof t === "string" ? { textContent: t, offsetParent: {} } : t));
  const document = {
    querySelectorAll(sel) {
      if (sel.includes('[class*="validation"')) return fouten;
      if (sel.includes('input[data-testid^="category-size"')) {
        return invoer.filter((n) => n.testid.startsWith("category-size") && n.testid.endsWith("-input"));
      }
      return [];
    },
  };
  const qs = (sel) => {
    const m = sel.match(/data-testid="([^"]+)"/);
    return (m && invoer.find((n) => n.testid === m[1])) || null;
  };
  return maak(document, qs);
}

const VOL = {
  "category-size-single-grid-input": "6-7 y",
  "color-select-dropdown-input": "Green",
  "category-condition-single-list-input": "New without tags",
  "catalog-select-dropdown-input": "V-neck jumpers",
};
const ZONDER_MAAT = { ...VOL, "category-size-single-grid-input": "" };

let stuk = 0;
function proef(naam, ok, gezien) {
  if (ok) { console.log("  ok   " + naam); return; }
  stuk++;
  console.error("  STUK " + naam + (gezien === undefined ? "" : "  → " + JSON.stringify(gezien)));
}

// 1. Precies de melding uit het schermbeeld van 31-08-2026.
{
  const a = scherm(ZONDER_MAAT, ["Fill in size to continue"]);
  const f = a.formErrorsVinted();
  proef("de maatklacht van Vinted wordt gelezen", f.length === 1 && f[0] === "Fill in size to continue", f);
  proef("en het lege veld heet size", a.emptyRequiredFieldsVinted().join(",") === "size", a.emptyRequiredFieldsVinted());
  const h = a.saveHintVinted({ size: "" }, f);
  proef("zonder maat in het dashboard zegt de tip dat", /no size in Omnivaleur/.test(h), h);
  const h2 = a.saveHintVinted({ size: "6-7 y" }, f);
  proef("met maat in het dashboard zegt de tip iets anders", /wouldn't accept it/.test(h2), h2);
}

// 2. Nederlandstalige Vinted.
{
  const a = scherm(ZONDER_MAAT, ["Vul de maat in om door te gaan"]);
  proef("de Nederlandse maatklacht wordt ook gelezen", a.formErrorsVinted().length === 1);
  proef("en levert dezelfde tip op", /no size in Omnivaleur/.test(a.saveHintVinted({}, a.formErrorsVinted())));
}

// 3. Geen valse mislukking: een zichtbaar element met "error" in de klassenaam
//    dat geen klacht is, mag een geslaagde opslag niet omzetten in een fout.
{
  const a = scherm(VOL, ["Something went wrong earlier", "0 errors"]);
  proef("onschuldige tekst telt niet als weigering", a.formErrorsVinted().length === 0, a.formErrorsVinted());
  proef("een volledig formulier meldt geen leeg veld", a.emptyRequiredFieldsVinted().length === 0, a.emptyRequiredFieldsVinted());
}

// 4. Een omhullend blok herhaalt de tekst van zijn kind — die dubbel telt niet.
{
  const a = scherm(ZONDER_MAAT, ["Size Fill in size to continue", "Fill in size to continue"]);
  const f = a.formErrorsVinted();
  proef("dezelfde klacht komt maar één keer in de melding", f.length === 1 && f[0] === "Fill in size to continue", f);
}

// 5. Onzichtbare meldingen (offsetParent null) tellen niet mee.
{
  const a = scherm(ZONDER_MAAT, [{ textContent: "Fill in size to continue", offsetParent: null }]);
  proef("een verborgen melding wordt genegeerd", a.formErrorsVinted().length === 0);
}

// 6. Kleur en staat worden net zo goed bij naam genoemd.
{
  const a = scherm({ ...VOL, "color-select-dropdown-input": "", "category-condition-single-list-input": "" }, []);
  proef("lege kleur en staat worden benoemd",
    a.emptyRequiredFieldsVinted().join(",") === "colour,condition", a.emptyRequiredFieldsVinted());
}

if (stuk) { console.error(`\n${stuk} proef(en) stuk`); process.exit(1); }
console.log("\nalles goed");
