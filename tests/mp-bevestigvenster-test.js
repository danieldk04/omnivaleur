/**
 * WELKE KNOP BEVESTIGT HET VERWIJDEREN OP MARKTPLAATS?
 *
 * AANLEIDING 20-09-2026, De Juiste Toon (djt@dejuistetoon.eu). Vijf tapijten
 * liepen sinds 14-09 elke nacht opnieuw stuk. Uit haar eigen diagnostiek, die
 * met de foutmelding meereist:
 *
 *   {"fase":"bevestigen","stap":0,"clicked":false,
 *    "gezien":["","Annuleren","Ja"],"open":true}
 *
 * Het venster ging dus gewoon open, met een knop "Ja", en de extensie klikte
 * niets. Oorzaak: twee verwijderroutes met elk hun eigen lijst JA-woorden. De
 * route via het overzicht kende het kale "Ja" wél, de route via de
 * advertentiepagina alleen "ja, verwijderen". Een herplaatsing die zijn oude
 * advertentie niet weg krijgt plaatst bewust geen nieuwe, dus stond de hele
 * herplaatsing stil.
 *
 * Deze proef draait de ECHTE keuzefunctie uit extension/background.js tegen een
 * namaakvenster met exact die drie knoppen, en dezelfde proef tegen de versie
 * van vóór de reparatie.
 *
 * Draaien:  node tests/mp-bevestigvenster-test.js
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// Vastgezet op de laatste versie van vóór de reparatie. "HEAD" zou na de commit
// de nieuwe code zijn, en dan vergelijkt de proef zichzelf.
const VOOR_DE_REPARATIE = "9bf3c6ed";

const NIEUW = fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const OUD = execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`, { cwd: WORTEL, maxBuffer: 64 * 1024 * 1024 }).toString();

let fouten = 0;
function eis(voorwaarde, wat) {
  if (voorwaarde) console.log(`  ok   ${wat}`);
  else { console.log(`  FOUT ${wat}`); fouten++; }
}

// ── Namaakvenster ───────────────────────────────────────────────────────────
// Genoeg DOM om beide versies te laten draaien: zij kijken naar getClientRects,
// offsetParent, disabled, textContent, aria-label en innerText.
function maakPagina({ knoppen, venstertekst = "Weet je het zeker?" }) {
  const geklikt = [];
  const maakKnop = (spec) => {
    const tekst = typeof spec === "string" ? spec : spec.tekst;
    const el = {
      textContent: tekst,
      disabled: false,
      offsetParent: {},                       // zichtbaar volgens de oude versie
      getClientRects: () => [{ width: 90, height: 32 }],
      getAttribute: (n) => (n === "aria-label" ? (spec.ariaLabel ?? null) : null),
      querySelectorAll: () => [],
      click() { geklikt.push(tekst || spec.ariaLabel || "(naamloos)"); },
    };
    return el;
  };
  const lijst = knoppen.map(maakKnop);
  const venster = {
    innerText: `${venstertekst} ${knoppen.map(k => (typeof k === "string" ? k : k.tekst)).join(" ")}`,
    getClientRects: () => [{ width: 400, height: 220 }],
    getAttribute: () => null,
    querySelectorAll: () => lijst,
  };
  const document = {
    querySelectorAll(sel) {
      if (/dialog|Modal|aria-modal/.test(sel)) return [venster];
      return lijst;              // de oude versie valt terug op document-scope
    },
  };
  return { document, geklikt };
}

// ── De echte functies eruit halen ───────────────────────────────────────────
function nieuweKiezer(bron) {
  const constStart = bron.indexOf("const BEVESTIG_JA_BRON =");
  const fnStart = bron.indexOf("function _bevestigInVenster(");
  const fnEind = bron.indexOf("\n}\n", fnStart);
  if (constStart < 0 || fnStart < 0 || fnEind < 0) throw new Error("_bevestigInVenster niet gevonden");
  const constants = bron.slice(constStart, bron.indexOf("\n", bron.indexOf("const BEVESTIG_NEE_BRON =")));
  const fn = bron.slice(fnStart, fnEind + 2);
  return new Function("document", `${constants}\n${fn}\nreturn () => _bevestigInVenster(BEVESTIG_JA_BRON, BEVESTIG_NEE_BRON);`);
}

function oudeKiezer(bron) {
  const merk = "      const res = await execInTab(tabId, async () => {";
  const start = bron.indexOf(merk);
  const eind = bron.indexOf("      }).catch(e => ({ open: null, clicked: false, error: String(e) }));", start);
  if (start < 0 || eind < 0) throw new Error("oude bevestiglus niet gevonden");
  const body = bron.slice(start + merk.length, eind);
  return new Function("document", `return async () => {${body}};`);
}

const nieuw = nieuweKiezer(NIEUW);
const oud = oudeKiezer(OUD);

(async () => {
  console.log("\nHET VENSTER VAN DE JUISTE TOON: knoppen ['', 'Annuleren', 'Ja']");
  {
    const a = maakPagina({ knoppen: ["", "Annuleren", "Ja"] });
    const res = await oud(a.document)();
    eis(res.open === true, "oud: ziet het venster wél openstaan");
    eis(res.clicked === false, "oud: klikt NIETS — precies wat de klant terugstuurde");
    eis(a.geklikt.length === 0, "oud: er is dus niets verwijderd");

    const b = maakPagina({ knoppen: ["", "Annuleren", "Ja"] });
    const res2 = nieuw(b.document)();
    eis(res2.clicked === true, "nieuw: klikt wél");
    eis(res2.picked === "Ja", `nieuw: en klikt "Ja" (gekregen: ${JSON.stringify(res2.picked)})`);
    eis(b.geklikt.join() === "Ja", "nieuw: alleen die ene knop is aangeraakt");
  }

  console.log("\nDE VERKOOPVRAAG MAG NOOIT MET JA BEANTWOORD WORDEN");
  {
    const a = maakPagina({
      knoppen: ["Niet verkocht via Marktplaats", "Verkocht via Marktplaats"],
      venstertekst: 'Heb je "Wollen Flokati kleed" verkocht via Marktplaats?',
    });
    const res = nieuw(a.document)();
    eis(res.picked === "Niet verkocht via Marktplaats", "nieuw: antwoordt 'niet verkocht'");
    eis(!a.geklikt.includes("Verkocht via Marktplaats"), "nieuw: boekt geen valse verkoop");
  }

  console.log("\nANNULEREN IS GEEN BEVESTIGING");
  {
    const a = maakPagina({ knoppen: ["Annuleren"] });
    const res = nieuw(a.document)();
    eis(res.clicked === false, "nieuw: klikt niets als alleen annuleren er staat");
    eis(a.geklikt.length === 0, "nieuw: en raakt Annuleren niet aan");
  }

  console.log("\nEEN HERNOEMDE KNOP BLIJFT NIET JAREN HANGEN");
  {
    const a = maakPagina({ knoppen: ["Annuleren", "Weghalen"] });
    const res = nieuw(a.document)();
    eis(res.picked === "Weghalen", "nieuw: één overgebleven niet-annuleerknop telt als de bevestiging");

    // ...maar niet als het venster over verkopen gaat: daar is stilstaan beter.
    const b = maakPagina({
      knoppen: ["Annuleren", "Verkocht via Marktplaats"],
      venstertekst: "Heb je dit verkocht via Marktplaats?",
    });
    const res2 = nieuw(b.document)();
    eis(res2.clicked === false, "nieuw: bij een verkoopvraag wordt niets gegokt");
  }

  console.log("\nGEEN VENSTER = NIETS TE BEVESTIGEN");
  {
    const document = { querySelectorAll: () => [] };
    const res = nieuw(document)();
    eis(res.open === false, "nieuw: meldt gewoon dat er geen venster is");
  }

  console.log(fouten === 0 ? "\nAlles goed.\n" : `\n${fouten} fout(en).\n`);
  process.exit(fouten === 0 ? 0 : 1);
})();
