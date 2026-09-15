/**
 * Een kanaal waar de browser geen sessie heeft moet te ZIEN zijn.
 *
 * GEMETEN 15-09-2026 (Egbert Brouwer / Papa's Plectrums). Zijn browser had sinds
 * 13-09 11:40 UTC geen sessie meer op 2dehands: het werktabblad kwam op
 * https://www.2dehands.be/identity/v2/login uit en /my-account/sell/api/listings
 * gaf 401 — op 14-09 elf keer en op 15-09 om 12:02 UTC nog eens, op versie
 * 1.0.329, dus met incognito uitgesloten. 231 zoekertjes stonden stil.
 *
 * Wat hij ondertussen zag: "Extension active — ready to publish", en op het
 * dashboard alleen dat er niets gebeurde. De extensie WIST het (mpSessie en
 * mpIngelogdOpDeSiteZelf meten het bij elke poging), maar het oordeel leefde in
 * een variabele die met de service worker meestierf en kwam nergens terecht.
 *
 * Draaien: node tests/kanaalsessie-zichtbaar-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const vm = require("vm");

const WORTEL = path.join(__dirname, "..");
// Laatste commit VÓÓR deze reparatie. Zonder deze vergelijking weet je alleen
// dat de nieuwe code werkt, niet dat ze iets repareert.
const VOOR_DE_REPARATIE = "f9b50ac5";

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function haalBlok(bron, kop) {
  const start = bron.indexOf(kop);
  if (start < 0) return null;
  // Eerst de parameterlijst uitlezen: `extra = {}` als standaardwaarde zette de
  // haakjesteller anders meteen op nul en gaf een halve functie terug.
  let i = bron.indexOf("(", start);
  if (i < 0) return null;
  let haakjes = 0;
  for (; i < bron.length; i++) {
    if (bron[i] === "(") haakjes++;
    else if (bron[i] === ")" && --haakjes === 0) { i++; break; }
  }
  if (kop.startsWith("const")) i = start;   // een object, geen functie
  let diep = 0;
  for (let j = bron.indexOf("{", i); j < bron.length; j++) {
    if (bron[j] === "{") diep++;
    else if (bron[j] === "}" && --diep === 0) {
      const eind = kop.startsWith("const") ? bron.indexOf(";", j) + 1 : j + 1;
      return bron.slice(start, eind);
    }
  }
  return null;
}

// Een nagebouwde chrome.storage.local + chrome.action, zodat we kunnen zien wat
// er BEWAARD wordt en wat er op de knop in de balk komt te staan.
function maakChrome() {
  const opslag = {};
  const knop = { badge: null, titel: null };
  return {
    opslag, knop,
    chrome: {
      storage: {
        local: {
          get: (sleutels, cb) => {
            const lijst = Array.isArray(sleutels) ? sleutels : [sleutels];
            const uit = {};
            for (const k of lijst) if (k in opslag) uit[k] = opslag[k];
            return cb ? (cb(uit), undefined) : Promise.resolve(uit);
          },
          set: (o, cb) => {
            Object.assign(opslag, o);
            return cb ? (cb(), undefined) : Promise.resolve();
          },
        },
      },
      action: {
        setBadgeText: ({ text }) => { knop.badge = text; },
        setBadgeBackgroundColor: () => {},
        setTitle: ({ title }) => { knop.titel = title; },
      },
    },
  };
}

function laadAchtergrond(bron) {
  const nep = maakChrome();
  const zand = {
    console: { warn() {}, log() {} },
    chrome: nep.chrome,
    SITE_NAAM: { marktplaats: "Marktplaats", "2dehands": "2dehands (2dehands.be)" },
    migrateTokensFromSync: () => Promise.resolve(),
  };
  vm.createContext(zand);
  const stukken = [
    /const KANAAL_SESSIE_SLEUTEL = "[^"]+";/.exec(bron)?.[0],
    haalBlok(bron, "function kanaalNaam("),
    haalBlok(bron, "async function onthoudKanaalSessie("),
    haalBlok(bron, "function refreshAuthBadge("),
  ].filter(Boolean);
  vm.runInContext(stukken.join("\n") + "\nthis.onthoud = typeof onthoudKanaalSessie === 'function' ? onthoudKanaalSessie : null;"
    + "\nthis.badge = typeof refreshAuthBadge === 'function' ? refreshAuthBadge : null;", zand);
  return { zand, ...nep };
}

// Het uitklapvenster, met een DOM die net genoeg kan om te zien wat er verschijnt.
function laadPopup(bron, kanalen) {
  const gemaakt = [];
  function maakEl(tag) {
    const el = {
      tag, children: [], style: {}, className: "", _tekst: "",
      set textContent(v) { this._tekst = v; },
      get textContent() { return this._tekst; },
      appendChild(k) { this.children.push(k); },
      addEventListener() {},
      set innerHTML(v) { this._html = v; if (v === "") this.children = []; },
      get innerHTML() { return this._html || ""; },
    };
    gemaakt.push(el);
    return el;
  }
  const els = { kanaalUit: maakEl("div"), readyBadge: maakEl("div") };
  els.readyBadge.style.display = "flex";
  const zand = {
    console: { warn() {}, log() {} },
    document: { getElementById: (id) => els[id] || null, createElement: maakEl },
    chrome: {
      runtime: {
        lastError: null,
        sendMessage: (msg, cb) => cb({ kanalen }),
      },
      tabs: { create() {} },
    },
  };
  vm.createContext(zand);
  const stukken = [
    haalBlok(bron, "const SITES = {"),
    haalBlok(bron, "function sindsWanneer("),
    haalBlok(bron, "async function toonKanaalSessies("),
  ].filter(Boolean);
  if (stukken.length < 3) return null;
  vm.runInContext(stukken.join("\n") + "\nthis.toon = toonKanaalSessies;", zand);
  return { zand, els, alleTekst: () => gemaakt.map(e => e._tekst).join(" | ") };
}

function plat(el) {
  const uit = [el.textContent || ""];
  for (const k of el.children) uit.push(plat(k));
  return uit.join(" ");
}

const NU_BG = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const NU_POPUP = fs.readFileSync(path.join(WORTEL, "extension/popup.js"), "utf8");
const TOEN_BG = execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`,
  { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();
const TOEN_POPUP = execSync(`git show ${VOOR_DE_REPARATIE}:extension/popup.js`,
  { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

(async () => {
  console.log("Kanaalsessie zichtbaar maken");

  console.log("\nNU (background.js)");
  const nu = laadAchtergrond(NU_BG);
  check("onthoudKanaalSessie bestaat", !!nu.zand.onthoud);

  nu.opslag.authToken = "geldig-omnivaleur-bewijs";
  // Precies Egberts meting: 401 op het overzicht, tabblad op de inlogpagina.
  await nu.zand.onthoud("2dehands", false, {
    status: 401, url: "https://www.2dehands.be/identity/v2/login",
  });
  const stand = nu.opslag.kanaalSessie && nu.opslag.kanaalSessie["2dehands"];
  check("het oordeel staat in de opslag, niet in een variabele",
    !!stand && stand.ingelogd === false,
    "een service worker die wordt afgeschoten neemt een variabele mee");
  check("de waargenomen feiten staan erbij",
    stand && stand.status === 401 && /identity\/v2\/login/.test(stand.url || ""));
  check("er staat sinds wanneer het zo is", !!(stand && stand.sinds));

  await new Promise(r => setTimeout(r, 5));
  check("de knop in de balk waarschuwt", nu.knop.badge === "!",
    `badge was ${JSON.stringify(nu.knop.badge)}`);
  check("en noemt het kanaal bij naam", /2dehands/.test(nu.knop.titel || ""),
    `titel was ${JSON.stringify(nu.knop.titel)}`);

  // Een tweede meting met dezelfde uitslag mag de klok niet resetten: anders
  // leest "niet ingelogd" na twee dagen nog steeds als "net gebeurd".
  const eersteSinds = stand.sinds;
  await new Promise(r => setTimeout(r, 3));
  await nu.zand.onthoud("2dehands", false, { status: 401 });
  check("dezelfde uitslag schuift 'sinds' niet op",
    nu.opslag.kanaalSessie["2dehands"].sinds === eersteSinds);

  // Weer ingelogd: de waarschuwing hoort vanzelf weg te gaan.
  await nu.zand.onthoud("2dehands", true, { status: 200 });
  await new Promise(r => setTimeout(r, 5));
  check("weer ingelogd = geen waarschuwing meer", nu.knop.badge === "",
    `badge was ${JSON.stringify(nu.knop.badge)}`);

  // "Weet niet" is geen uitslag. Een netwerkhikje mag niemand beschuldigen.
  const voor = JSON.stringify(nu.opslag.kanaalSessie);
  await nu.zand.onthoud("2dehands", null, { status: null });
  check("'weet niet' verandert niets", JSON.stringify(nu.opslag.kanaalSessie) === voor);

  console.log("\nNU (popup.js)");
  const p = laadPopup(NU_POPUP, {
    "2dehands": { ingelogd: false, status: 401, sinds: Date.now() - 48 * 3600000 },
  });
  check("toonKanaalSessies bestaat", !!p);
  if (p) {
    await p.zand.toon();
    const tekst = plat(p.els.kanaalUit);
    check("het uitklapvenster meldt het kanaal", /Not signed in to 2dehands/.test(tekst),
      `stond er: ${tekst.slice(0, 120)}`);
    check("met hoe lang het al zo is", /2 days/.test(tekst));
    check("en een knop om in te loggen", /Sign in to 2dehands/.test(tekst));
    check("het groene 'ready to publish' staat niet meer naast een dood kanaal",
      p.els.readyBadge.style.display === "none",
      "dit is precies het scherm waarvan Egbert een foto stuurde");
  }

  // Geen kanaal stuk = niets veranderen aan het gewone scherm.
  const p2 = laadPopup(NU_POPUP, { "2dehands": { ingelogd: true, status: 200 } });
  if (p2) {
    await p2.zand.toon();
    check("ingelogd = geen waarschuwing, groen blijft staan",
      p2.els.kanaalUit.style.display === "none" && p2.els.readyBadge.style.display === "flex");
  }

  console.log(`\nDE VERSIE ERVOOR (${VOOR_DE_REPARATIE}) — die hoort te falen`);
  const toen = laadAchtergrond(TOEN_BG);
  check("kende onthoudKanaalSessie niet", !toen.zand.onthoud);
  toen.opslag.authToken = "geldig-omnivaleur-bewijs";
  toen.opslag.kanaalSessie = { "2dehands": { ingelogd: false, status: 401 } };
  toen.zand.badge();
  await new Promise(r => setTimeout(r, 5));
  check("liet de knop in de balk schoon terwijl 2dehands stillag",
    toen.knop.badge === "" && toen.knop.titel === "Omnivaleur",
    `badge=${JSON.stringify(toen.knop.badge)} titel=${JSON.stringify(toen.knop.titel)}`);
  check("het uitklapvenster kende geen kanaalsessie",
    !/toonKanaalSessies/.test(TOEN_POPUP));

  console.log(mislukt ? `\n${mislukt} FOUT(EN)` : "\nAlles goed");
  process.exit(mislukt ? 1 : 0);
})();
