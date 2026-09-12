/**
 * De Juiste Toon, 12-09-2026, 14:30:
 *   "Deze pc staat hele dag aan en toch zie ik nog steeds, dat hij 50 stuks
 *    heeft staan, horen die niet weg te gaan?"  /  "Hoeveel tijd zit daar tussen?"
 *
 * Gemeten in zijn account op dat moment: 119 opdrachten open, en tussen 07:51
 * en 11:12 UTC werd er geen enkele opgepakt terwijl er honderd klaarstonden,
 * daarna nog eens 54 minuten niet. Bij twee andere verkopers liepen in diezelfde
 * uren 46 en 24 opdrachten per uur door, dus de server deelde gewoon uit: zijn
 * Chromebook sliep. De balk zei ondertussen "All 50 together take about an hour",
 * want het gemeten tempo gooit slaapgaten er bewust uit.
 *
 * Deze test draait de échte renderActivityBar uit app.html met die stand.
 *
 * Draaien: node tests/wachtrij-staat-stil-omdat-de-computer-slaapt-test.js
 *          node tests/... --oud     (tegen de commit van vóór de reparatie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "3db24936";
const oud = process.argv.includes("--oud");
const APP = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:frontend/app.html`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "frontend", "app.html"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(naam) {
  const start = APP.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  const eind = APP.indexOf("\n}\n", start);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(start, eind + 2);
}

function nepScherm() {
  const el = () => ({ style: {}, textContent: "", innerHTML: "", className: "",
                      classList: { add() {}, remove() {} } });
  const knopen = { "ext-activity-bar": el(), "ext-activity-title": el(),
                   "ext-activity-text": el(), "ext-activity-icon": el() };
  return { knopen, getElementById: (id) => knopen[id] || null };
}

function draai(pace, extStatus) {
  const scherm = nepScherm();
  const bron = [
    "function esc(s){return String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));}",
    functieUit("fmtQueueEta"),
    functieUit("fmtSeenAgo"),
    functieUit("renderActivityBar"),
    "renderActivityBar();",
    "return { titel: document.getElementById('ext-activity-title').textContent,",
    "         tekst: document.getElementById('ext-activity-text').innerHTML };",
  ].join("\n");
  const fn = new Function("document", "_activityState", "state", "describeJobs", bron);
  const wachtrij = Array.from({ length: 50 }, (_, i) => ({ id: `j${i}`, action: "create" }));
  return fn(scherm, { working: [], queued: wachtrij, pace },
            { extStatus }, () => "50 listings");
}

// De stand in Toons account op 12-09-2026 om 13:18 UTC, zoals _stille_uren die
// uit zijn eigen opdrachten meet: 66 seconden per opdracht, 4,2 stille uren in
// twee gaten, 43 opdrachten afgerond in het afgelopen uur.
const TOON = { seconds_between: 16, seconds_per_job: 66, calm: false, samples: 11,
               idle_seconds: 15120, idle_gaps: 2, idle_since: null, done_last_hour: 43 };
const WAKKER = { seconds_between: 16, seconds_per_job: 66, calm: false, samples: 11,
                 idle_seconds: 0, idle_gaps: 0, idle_since: null, done_last_hour: 43 };
const ONLINE = { online: true, seconds_ago: 12 };

console.log("Toons stand: rij van 50, computer sliep ruim vier uur");
const toon = draai(TOON, ONLINE);
check("noemt de stille uren", /did nothing for/.test(toon.tekst), toon.tekst.slice(0, 260));
check("noemt hoeveel uur", /about 4 hours/.test(toon.tekst), toon.tekst.slice(0, 260));
check("legt uit dat een slapende computer niets doet",
      /sleeps or Chrome is closed/.test(toon.tekst));
check("laat zien dat er wél werk af komt", /43<\/b> finished in the last hour/.test(toon.tekst),
      toon.tekst.slice(0, 300));
check("legt uit waarom het getal niet daalt", /a second job/.test(toon.tekst));

console.log("\nZelfde rij, maar de computer bleef wakker");
const wakker = draai(WAKKER, ONLINE);
check("zwijgt over stille uren als die er niet waren",
      !/did nothing for/.test(wakker.tekst), wakker.tekst.slice(0, 200));
check("houdt de gemeten looptijd erin", /together take/.test(wakker.tekst));

console.log("\nGeen meting beschikbaar");
const leeg = draai(null, ONLINE);
check("zegt niets over stille uren zonder meting", !/did nothing for/.test(leeg.tekst));
check("geen 'undefined' in de tekst", !/undefined/.test(leeg.tekst), leeg.tekst.slice(0, 200));

console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
