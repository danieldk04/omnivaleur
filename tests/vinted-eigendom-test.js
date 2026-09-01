/**
 * De eigendomscontrole draait hier ECHT, tegen nagebootste Vinted-antwoorden.
 *
 * De brontekst nakijken zegt alleen dat de code er staat. Dit zegt wat ze doet.
 * De antwoorden hieronder zijn geen verzinsels: 401 met
 * message_code "invalid_authentication_token" is wat vinted.nl en vinted.com op
 * 01-09-2026 werkelijk teruggaven op /api/v2/users/current zonder cookies.
 *
 * Draaien:  node tests/vinted-eigendom-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

function functieUit(naam) {
  const start = BG.indexOf(`async function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  const eind = BG.indexOf("\n}\n", start);
  return BG.slice(start, eind + 2);
}

let antwoorden = {};
global.fetch = async (url) => {
  for (const [stuk, res] of Object.entries(antwoorden)) {
    if (url.includes(stuk)) {
      if (res.gooi) throw new Error("netwerk weg");
      return { ok: res.status < 400, status: res.status, json: async () => res.body };
    }
  }
  throw new Error("onverwachte aanroep: " + url);
};

eval(functieUit("vintedIngelogd") + functieUit("bgVintedEigenAdvertentie")
     + BG.slice(BG.indexOf("function vintedTitelHoortBij("), BG.indexOf("\n}\n", BG.indexOf("function vintedTitelHoortBij(")) + 2));

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

const KAST = (ids, totalPages = 1) => ({
  status: 200,
  body: { items: ids.map(x => (typeof x === "object" ? x : { id: x, title: "" })),
          pagination: { total_pages: totalPages } },
});
const UITGELOGD = { status: 401, body: { code: 100, message_code: "invalid_authentication_token" } };
const INGELOGD = { status: 200, body: { user: { id: 42 } } };

(async () => {
  console.log("\nvintedIngelogd");

  antwoorden = { "users/current": UITGELOGD };
  ok("uitgelogd (het echte 401-antwoord) = false", (await vintedIngelogd("https://www.vinted.nl")) === false,
     await vintedIngelogd("https://www.vinted.nl"));

  antwoorden = { "users/current": INGELOGD };
  ok("ingelogd = true", (await vintedIngelogd("https://www.vinted.nl")) === true);

  antwoorden = { "users/current": { status: 503, body: {} } };
  ok("Vinted plat (503) = onbekend, niet 'uitgelogd'", (await vintedIngelogd("https://www.vinted.nl")) === null);

  antwoorden = { "users/current": { gooi: true } };
  ok("geen netwerk = onbekend", (await vintedIngelogd("https://www.vinted.nl")) === null);

  antwoorden = { "users/current": { status: 200, body: {} } };
  ok("antwoord zonder gebruiker = false", (await vintedIngelogd("https://www.vinted.nl")) === false);

  console.log("\nbgVintedEigenAdvertentie");
  const O = "https://www.vinted.nl";

  const CARDIGAN = { title: "(1353) Dark Green Suitsupply Cardigan - Men S - Very Good" };
  const VEST = { title: "(1352) Navy Suitsupply Zip Vest - Men XS - Very Good" };

  antwoorden = { "users/current": INGELOGD, "wardrobe": KAST([111, 222, 333]) };
  ok("eigen advertentie = true", (await bgVintedEigenAdvertentie(O, 222)) === true);
  ok("id als tekst telt ook", (await bgVintedEigenAdvertentie(O, "222")) === true);

  // DE ECHTE FOUT UIT DE DATABASE (01-09-2026): artikel 1353 droeg het nummer
  // van 1352. Beide van dezelfde verkoper, dus eigendom alleen is niet genoeg.
  antwoorden = { "users/current": INGELOGD,
                 "wardrobe": KAST([{ id: 9727012245, title: VEST.title }]) };
  ok("advertentie van de verkoper zelf, maar het VERKEERDE artikel = false",
     (await bgVintedEigenAdvertentie(O, 9727012245, CARDIGAN)) === false,
     await bgVintedEigenAdvertentie(O, 9727012245, CARDIGAN));
  ok("hetzelfde artikel = true",
     (await bgVintedEigenAdvertentie(O, 9727012245, VEST)) === true);

  // Vinted toont de VERTAALDE titel. Dat mag nooit als "verkeerde advertentie"
  // gelden, anders sneuvelt elke Nederlandse advertentie.
  antwoorden = { "users/current": INGELOGD,
                 "wardrobe": KAST([{ id: 777, title: "Dubarry of Ireland mens shoes size 41 brown" }]) };
  ok("een vertaalde titel telt gewoon als dezelfde advertentie",
     (await bgVintedEigenAdvertentie(O, 777,
        { title: "Dubarry of Ireland Herenschoenen Maat 41 Bruin",
          title_en: "Dubarry of Ireland mens shoes size 41 brown" })) === true);

  // Afgekapte titel: Vinted kort lange titels in.
  antwoorden = { "users/current": INGELOGD,
                 "wardrobe": KAST([{ id: 888, title: "(1017) Grey Ralph Lauren Zip Vest" }]) };
  ok("een afgekapte titel telt ook",
     (await bgVintedEigenAdvertentie(O, 888,
        { title: "(1017) Grey Ralph Lauren Zip Vest - Men S - Very Good" })) === true);

  // Geen titel van Vinted gekregen: dan is het niet aan ons om te oordelen.
  antwoorden = { "users/current": INGELOGD, "wardrobe": KAST([{ id: 999, title: "" }]) };
  ok("zonder titel van Vinted geen oordeel",
     (await bgVintedEigenAdvertentie(O, 999, CARDIGAN)) === true);

  // Dit is de storing van Budgetheld: een advertentie van een vreemde waar de
  // verkoper op klikte nadat Vinted hem naar de registratiepagina stuurde.
  antwoorden = { "users/current": UITGELOGD };
  ok("uitgelogd = false, dus geen groen vinkje bij andermans advertentie",
     (await bgVintedEigenAdvertentie(O, 999)) === false);
  ok("uitgelogd wordt vastgesteld zonder de kast te hoeven lezen",
     (await bgVintedEigenAdvertentie(O, 999)) === false);

  // DE BELANGRIJKSTE: een échte publicatie mag hier nooit sneuvelen. Vinted zet
  // een nieuwe advertentie pas na een minuut of twee in de kast, dus "nog niet
  // gevonden" moet 'onbekend' opleveren en niet 'niet van jou'.
  antwoorden = { "users/current": INGELOGD, "wardrobe": KAST([111, 222]) };
  ok("ingelogd maar nog niet in de kast = onbekend, NOOIT false",
     (await bgVintedEigenAdvertentie(O, 555)) === null,
     await bgVintedEigenAdvertentie(O, 555));

  antwoorden = { "users/current": INGELOGD, "wardrobe": KAST([]) };
  ok("lege kast bij een ingelogde verkoper = onbekend, niet false",
     (await bgVintedEigenAdvertentie(O, 222)) === null);

  antwoorden = { "users/current": INGELOGD, "wardrobe": { status: 500, body: {} } };
  ok("kast onleesbaar = onbekend", (await bgVintedEigenAdvertentie(O, 222)) === null);

  antwoorden = { "users/current": { status: 503, body: {} } };
  ok("Vinted plat = onbekend, houdt niets tegen", (await bgVintedEigenAdvertentie(O, 222)) === null);

  antwoorden = { "users/current": { gooi: true } };
  ok("geen netwerk = onbekend", (await bgVintedEigenAdvertentie(O, 222)) === null);

  console.log(mislukt ? `\n${mislukt} test(s) mislukt\n` : "\nAlles groen\n");
  process.exit(mislukt ? 1 : 0);
})();
