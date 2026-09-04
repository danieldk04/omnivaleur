// Draait de ECHTE categoriewandelaar uit extension/content/vinted.js tegen een
// namaakkiezer, en bewijst het verschil met de vorige versie.
//
// AANLEIDING 04-09-2026. Daniel: "hij upload heel vaak binnen een categorie op
// vinted naar other... terwijl vinted iets anders voorstelt en ik ook denk dat
// het een andere categorie moet zijn." Voorbeeld: (1365) Black Uniqlo Trousers
// belandde onder Men > Clothing > Trousers > OTHER TROUSERS.
//
// OORZAAK. Onder een tak zit bij Vinted nog een niveau (Chinos, Cargo trousers,
// Skinny trousers, ...). De extensie koos dat blad op woorden uit titel en
// omschrijving. Zegt de tekst daar niets over, en dat is bijna altijd zo, dan
// pakte hij het vangblad "Other ...". Vinted zet op datzelfde moment bovenaan
// zijn eigen voorstellen, afgeleid uit de FOTO'S, en daar keek niemand naar.
//
// WAT HIER IS NAGEBOOTST EN WAT NIET. De vorm van de kiezer is overgenomen uit
// wat er in vinted.js staat opgeschreven van de echte pagina: klikbare regels
// (Cell__clickable) met de naam in Cell__title, en bij een voorstel daaronder
// het kruimelpad in Cell__body ("Men > Clothing > Trousers"). Die vorm is hier
// NIET opnieuw op de echte, ingelogde Vinted gemeten. Wat wel hard is: welk
// blad de verscheepte code kiest bij precies die regels, en dat de vorige
// versie onder dezelfde omstandigheden "Other trousers" koos.
//
// Draaien: node tests/vinted-mock/categorie-voorstel-test.js
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const REPO = path.resolve(__dirname, "../..");
const NIEUW = fs.readFileSync(path.join(REPO, "extension/content/vinted.js"), "utf8");
// Vaste commit, geen HEAD: de auto-push-hook commit werk in uitvoering onder
// "auto: update ...", dus HEAD bevat de reparatie al en dan bewijst de
// voor-proef niets meer.
const OUD = execFileSync("git", ["show", "c04467f:extension/content/vinted.js"],
  { cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

function stuk(bron, van, tot) {
  const a = bron.indexOf(van);
  const b = bron.indexOf(tot, a);
  if (a < 0 || b < 0) { console.error(`niet te vinden in vinted.js: ${van}`); process.exit(1); }
  return bron.slice(a, b);
}

// De echte code, uit het verscheepte bestand gesneden. Zo test deze proef nooit
// een kopie die is achtergebleven.
function laad(bron) {
  const code =
    stuk(bron, "  const V_KLEDING = {", "  // De rode melding onder het prijsveld") +
    stuk(bron, "  const BLAD_VOORKEUR = [", "  const job = await getJob();") +
    stuk(bron, "  function vintedPathFor(cat, gender) {", "  function kiesBlad(namen, tekst) {") +
    stuk(bron, "  function kiesBlad(namen, tekst) {", "  // Loopt het pad af in Vinted's kiezer.") +
    stuk(bron, "  function realClickEl(el) {", "  // Has Vinted accepted a size?") +
    stuk(bron, "  async function walkVintedCategoryPath(item, cat, gender) {",
         "  async function fillCategoryVinted(item) {");
  return new Function("document", "window", "qs", "sleep", "clog", "PointerEvent", "MouseEvent",
    `${code}\nreturn { walkVintedCategoryPath };`);
}

// ── Een namaak-DOM: precies genoeg om de kiezer na te doen ──────────────────
const klassenUit = (sel) => [...sel.matchAll(/\[class\*="([^"]+)"\]/g)].map((m) => m[1]);
function zoek(wortel, sel) {
  const wil = klassenUit(sel);
  const uit = [];
  (function loop(n) {
    for (const k of n.kinderen) {
      if (wil.some((w) => k.klas.includes(w))) uit.push(k);
      loop(k);
    }
  })(wortel);
  return uit;
}
function maakEl(klas, tekst) {
  const el = {
    klas, kinderen: [], _tekst: tekst || "", opClick: null,
    get offsetParent() { return {}; },
    get textContent() {
      return el.kinderen.length ? el.kinderen.map((k) => k.textContent).join(" ") : el._tekst;
    },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 20, height: 20 }),
    scrollIntoView() {}, focus() {},
    click() { if (el.opClick) el.opClick(); },
    dispatchEvent(ev) { if (ev && ev.type === "click" && el.opClick) el.opClick(); return true; },
    querySelector(sel) { return zoek(el, sel)[0] || null; },
    querySelectorAll(sel) { return zoek(el, sel); },
  };
  return el;
}

// De categoriekiezer van Vinted: dicht tot je hem aanklikt, daarna de boom met
// bovenaan de voorstellen uit de foto's. Klik je een tak aan, dan verdwijnen de
// voorstellen en zie je het volgende niveau. Een blad legt de keuze vast.
function maakKiezer(boom, voorstellen) {
  const doc = maakEl("document");
  const inp = {
    value: "", scrollIntoView() {}, focus() {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 20, height: 20 }),
    dispatchEvent(ev) { if (ev && ev.type === "click") toon(boom, true); return true; },
    click() { toon(boom, true); },
  };
  const regel = (naam, kruimel) => {
    const c = maakEl("web_ui__Cell__cell web_ui__Cell__clickable");
    c.kinderen.push(maakEl("web_ui__Cell__title", naam));
    if (kruimel) c.kinderen.push(maakEl("web_ui__Cell__body", kruimel));
    return c;
  };
  function toon(niveau, metVoorstellen) {
    doc.kinderen = [];
    if (metVoorstellen && voorstellen.length) {
      // Let op: het omhulsel om de voorstellen heet zélf ook "...Cell...".
      const bak = maakEl("web_ui__Cells__cells");
      for (const v of voorstellen) bak.kinderen.push(regel(v.titel, v.pad.join(" > ")));
      doc.kinderen.push(bak);
    }
    for (const naam of Object.keys(niveau)) {
      const kind = niveau[naam];
      const c = regel(naam, "");
      c.opClick = () => {
        if (kind && Object.keys(kind).length) toon(kind, false);
        else { inp.value = naam; doc.kinderen = []; }
      };
      doc.kinderen.push(c);
    }
  }
  return { doc, inp };
}

const BOOM = {
  Men: {
    Clothing: {
      Trousers: {
        "Cargo trousers": {}, "Chinos": {}, "Cropped trousers": {}, "Formal trousers": {},
        "Joggers": {}, "Skinny trousers": {}, "Other trousers": {},
      },
      "Jumpers & sweaters": { Hoodies: {}, Jumpers: {}, "Other jumpers & sweaters": {} },
    },
  },
  Women: { Clothing: { "Trousers & leggings": { Chinos: {}, "Other trousers": {} } } },
  Kids: { Clothing: {} },
};

// Het artikel uit de melding van Daniel, letterlijk.
const UNIQLO = {
  title: "(1365) Black Uniqlo Trousers - Men XXL - New",
  description: "Authentic designer Trousers from Uniqlo in size XXL, measurements available"
    + " in the pictures. Check the measurements before buying! This item in new condition is"
    + " an excellent addition to your wardrobe.",
  category: "broeken",
  gender: "heren",
};

async function draai(bron, item, voorstellen) {
  const { doc, inp } = maakKiezer(BOOM, voorstellen);
  const log = [];
  const nep = function (type) { this.type = type; };
  const { walkVintedCategoryPath } = laad(bron)(
    doc,
    {},
    (sel) => (/catalog-select-dropdown-input/.test(sel) ? inp : null),
    () => Promise.resolve(),
    (t) => log.push(String(t)),
    nep, nep,
  );
  const ok = await walkVintedCategoryPath(item, item.category, item.gender);
  return { ok, gekozen: inp.value, log };
}

let fout = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  fout++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

const CHINO_VOORSTEL = [{ titel: "Chinos", pad: ["Men", "Clothing", "Trousers"] }];

(async function main() {
  // ── 1. De voor-proef ──────────────────────────────────────────────────────
  console.log("Wat de vorige versie deed met precies dit artikel");
  const oud = await draai(OUD, UNIQLO, CHINO_VOORSTEL);
  check("de oude versie koos het vangblad", oud.gekozen === "Other trousers",
    `koos "${oud.gekozen}" — dan bewijst deze proef niets`);
  check("en keek niet naar het voorstel van Vinted",
    !oud.log.some((r) => /voorstel/i.test(r)), oud.log.join(" | "));

  // ── 2. De nieuwe versie volgt het voorstel ────────────────────────────────
  console.log("\nDe nieuwe versie, zelfde artikel, zelfde voorstel");
  const nieuw = await draai(NIEUW, UNIQLO, CHINO_VOORSTEL);
  check("de wandeling slaagt", nieuw.ok === true);
  check("hij kiest Chinos in plaats van Other trousers", nieuw.gekozen === "Chinos",
    `koos "${nieuw.gekozen}"`);
  check("het logboek zegt waaróm", nieuw.log.some((r) => /voorstel van Vinted/.test(r)),
    nieuw.log.join(" | "));
  check("het voorstel is uit het omhulsel gehaald zonder namen te verwisselen",
    nieuw.log.some((r) => /Vinted stelt zelf voor: Chinos/.test(r)), nieuw.log.join(" | "));

  // ── 3. Zegt het artikel het zelf, dan wint het artikel ────────────────────
  console.log("\nStaat het model wél in de tekst, dan telt de tekst");
  const cargo = await draai(NIEUW,
    { ...UNIQLO, title: "(1400) Black Uniqlo Cargo trousers - Men XXL - New" }, CHINO_VOORSTEL);
  check("cargo in de titel wint van het voorstel Chinos", cargo.gekozen === "Cargo trousers",
    `koos "${cargo.gekozen}"`);

  // ── 4. Een voorstel buiten ons eigen pad telt niet mee ────────────────────
  console.log("\nEen voorstel uit een andere tak wordt genegeerd");
  const andereTak = await draai(NIEUW, UNIQLO,
    [{ titel: "Hoodies", pad: ["Men", "Clothing", "Jumpers & sweaters"] }]);
  check("een trui-voorstel verandert niets aan een broek",
    andereTak.gekozen === "Other trousers", `koos "${andereTak.gekozen}"`);

  console.log("\nEen damesvoorstel bij een herenartikel");
  const dames = await draai(NIEUW, UNIQLO,
    [{ titel: "Chinos", pad: ["Women", "Clothing", "Trousers & leggings"] }]);
  check("het artikel blijft bij de heren", dames.gekozen === "Other trousers",
    `koos "${dames.gekozen}" — een herenbroek mag nooit naar de damesafdeling`);

  // ── 5. Geen voorstellen: het oude gedrag blijft ───────────────────────────
  console.log("\nZonder voorstellen verandert er niets");
  const leeg = await draai(NIEUW, UNIQLO, []);
  check("het vangblad blijft de terugval", leeg.gekozen === "Other trousers",
    `koos "${leeg.gekozen}"`);

  // ── 6. Enkelvoud tegen meervoud ───────────────────────────────────────────
  console.log("\nVinted spelt zijn voorstel niet altijd letterlijk zoals de boom");
  const enkel = await draai(NIEUW, UNIQLO,
    [{ titel: "Chino", pad: ["Men", "Clothing", "Trousers"] }]);
  check("\"Chino\" vindt de regel \"Chinos\"", enkel.gekozen === "Chinos",
    `koos "${enkel.gekozen}"`);

  // ── 7. Een voorstel dat twee niveaus dieper gaat ──────────────────────────
  console.log("\nEen voorstel dat verder reikt dan één niveau");
  const diep = await draai(NIEUW,
    { ...UNIQLO, category: "truien" },
    [{ titel: "Hoodies", pad: ["Men", "Clothing", "Jumpers & sweaters"] }]);
  check("onder truien wordt Hoodies gekozen", diep.gekozen === "Hoodies",
    `koos "${diep.gekozen}"`);

  console.log(fout ? `\n${fout} controle(s) mislukt` : "\nAlles goed.");
  process.exit(fout ? 1 : 0);
})();
