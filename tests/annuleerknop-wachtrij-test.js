/**
 * De Annuleer-knop naast de wachtrijbalk (04-09-2026, Toon / dejuistetoon).
 *
 * Hij zette 's middags 51 publicaties klaar. Elf liepen er, toen ging zijn
 * Chromebook uit en stond de rest stil. 's Avonds drukte hij op deze knop en
 * waren er in één seconde 39 weg, waaronder alle dertien Lederhosen waar hij de
 * volgende dag naar zocht: "komt niet echt door op marktplaats, zie ze niet
 * verschijnen". Diezelfde ochtend was het al een keer gebeurd, toen met 93
 * opdrachten.
 *
 * De knop heette "Cancel" en het venster erachter vroeg of hij "the current
 * publishing action" wilde afbreken — enkelvoud, terwijl er zesendertig aan
 * hingen, en "The item will show as not listed". Wie leest dat er niets loopt
 * en daarnaast een knop Cancel ziet, denkt dat hij iets vastgelopens opruimt.
 *
 * Deze proef draait de échte cancelActiveJobs en renderActivityBar uit app.html.
 *
 * Draaien: node tests/annuleerknop-wachtrij-test.js
 *          node tests/annuleerknop-wachtrij-test.js /tmp/oude-app.html
 */
const fs = require("fs");
const path = require("path");

const bestand = process.argv[2] || path.join(__dirname, "..", "frontend", "app.html");
const APP = fs.readFileSync(bestand, "utf8");

let mislukt = 0;
function ok(v, wat, uitleg) {
  if (v) { console.log("  ✓", wat); return; }
  console.log("  ✗", wat + (uitleg ? " — " + uitleg : "")); mislukt++;
}

function functieUit(naam) {
  let start = APP.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in ${path.basename(bestand)}`);
  // Een async-functie moet mét dat woord mee, anders faalt de await erin.
  if (APP.slice(start - 6, start) === "async ") start -= 6;
  const eind = APP.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(start, eind + 2);
}

function nepKnoop() {
  return { style: {}, textContent: "", innerHTML: "", className: "", disabled: false,
           classList: { add() {}, remove() {} } };
}

/** Draait de echte cancelActiveJobs met een nagebouwd scherm. */
function annuleer({ working, queued, antwoorden }) {
  const knopen = { "ext-activity-bar": nepKnoop(), "ext-activity-title": nepKnoop(),
                   "ext-activity-text": nepKnoop(), "ext-activity-icon": nepKnoop(),
                   "ext-activity-cancel": nepKnoop() };
  const gevraagd = [];
  const geannuleerd = [];
  const stand = { working, queued, pace: null };

  const bron = [
    functieUit("cancelActiveJobs"),
    "return cancelActiveJobs();",
  ].join("\n");

  const fn = new Function(
    "document", "_activityState", "confirm", "apiFetch", "API",
    "renderActivityBar", "loadAll", "showToast", "alert", bron);

  const klaar = fn(
    { getElementById: (id) => knopen[id] || null },
    stand,
    (tekst) => { gevraagd.push(tekst); return antwoorden.length ? antwoorden.shift() : true; },
    (url) => { geannuleerd.push(String(url).match(/jobs\/([^/]+)\/cancel/)[1]);
               return Promise.resolve({ ok: true, json: () => ({}) }); },
    "",
    () => {},
    () => Promise.resolve(),
    () => {},
    () => {},
  );
  return Promise.resolve(klaar).then(() => ({ gevraagd, geannuleerd, stand }));
}

/** Draait de echte renderActivityBar en geeft het bijschrift van de knop terug. */
function knoptekst({ working, queued, pace, online }) {
  const knopen = { "ext-activity-bar": nepKnoop(), "ext-activity-title": nepKnoop(),
                   "ext-activity-text": nepKnoop(), "ext-activity-icon": nepKnoop(),
                   "ext-activity-cancel": nepKnoop() };
  const bron = [
    functieUit("fmtQueueEta"),
    functieUit("fmtSeenAgo"),
    functieUit("renderActivityBar"),
    "renderActivityBar();",
    "return document.getElementById('ext-activity-cancel').textContent;",
  ].join("\n");
  const fn = new Function("document", "_activityState", "state", "describeJobs", bron);
  return fn({ getElementById: (id) => knopen[id] || null },
            { working, queued, pace },
            { extStatus: online === null ? null : { online, seconds_ago: online ? 3 : 12000 } },
            (jobs) => `${jobs.length} things`);
}

const rij = (n, prefix) =>
  Array.from({ length: n }, (_, i) => ({ id: `${prefix}${i}`, platform: "marktplaats", action: "create" }));

(async () => {
  console.log(`\n${path.basename(bestand)}\n`);

  // ── De situatie van Toon: niets loopt, 36 staan te wachten ───────────────
  const toon = await annuleer({ working: [], queued: rij(36, "q"), antwoorden: [true] });
  ok(/36/.test(toon.gevraagd[0] || ""), "het venster noemt het aantal (36)",
     (toon.gevraagd[0] || "geen vraag gesteld").slice(0, 90));
  ok(!/the current publishing action/i.test(toon.gevraagd[0] || ""),
     "praat niet meer over één enkele actie");
  ok(/publish them again|publish it again/i.test(toon.gevraagd[0] || ""),
     "zegt dat hij ze later opnieuw kan publiceren");
  ok(toon.geannuleerd.length === 36, "annuleert er 36 als hij ja zegt",
     `${toon.geannuleerd.length}`);

  const nee = await annuleer({ working: [], queued: rij(36, "q"), antwoorden: [false] });
  ok(nee.geannuleerd.length === 0, "nee betekent nee: er gaat er geen weg");

  // ── Er draait er één, met een rij erachter ───────────────────────────────
  const lopend = await annuleer({ working: rij(1, "w"), queued: rij(35, "q"), antwoorden: [true] });
  ok(lopend.geannuleerd.length === 1,
     "stopt alleen de lopende, niet de 35 die wachten", `${lopend.geannuleerd.length} geannuleerd`);
  ok(lopend.geannuleerd[0] === "w0", "en dat is precies de lopende opdracht");
  ok(/stay in the queue/i.test(lopend.gevraagd[0] || ""),
     "zegt met zoveel woorden dat de rest blijft staan");
  // ── Het bijschrift van de knop ──────────────────────────────────────────
  ok(knoptekst({ working: [], queued: rij(36, "q"), pace: null, online: false }) === "Clear queue (36)",
     "de knop heet 'Clear queue (36)' als er niets loopt",
     knoptekst({ working: [], queued: rij(36, "q"), pace: null, online: false }));
  ok(knoptekst({ working: rij(1, "w"), queued: rij(35, "q"), pace: null, online: true }) === "Stop this one",
     "de knop heet 'Stop this one' zodra er iets draait",
     knoptekst({ working: rij(1, "w"), queued: rij(35, "q"), pace: null, online: true }));

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt\n` : "\nAlles goed\n");
  process.exit(mislukt ? 1 : 0);
})();
