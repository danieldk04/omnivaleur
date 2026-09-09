/**
 * De Juiste Toon, 09-09-2026, 12:19:
 *   "Gisteren hoop geladen, komt nog steeds niet op marktplaats? Wat gaat er fout"
 *
 * Op zijn schermafdruk staat: "50 jobs queued — nothing is running. Your
 * extension has not checked in (last seen 20h ago) … Open Chrome on the
 * computer you use for Omnivaleur … the queue picks up by itself after that."
 *
 * Gemeten in zijn account op dat moment: de laatste melding van zijn extensie
 * was 08-09 13:31 UTC met versie 1.0.260, terwijl er 1.0.313 in de Chrome Web
 * Store stond. De uitgifte geeft zo'n kopie sinds 07-09 geen werk meer. Chrome
 * openen kon dus niets oplossen — de balk stuurde hem naar een schakelaar die
 * al goed stond.
 *
 * Deze test draait de échte renderActivityBar uit app.html met precies die
 * stand, en zet de oude belofte naast de nieuwe tekst.
 *
 * Draaien: node tests/stilstaande-kopie-balk-test.js
 */
const fs = require("fs");
const path = require("path");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");
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

function draai(extStatus) {
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
  return fn(scherm, { working: [], queued: wachtrij, pace: null },
            { extStatus }, () => "50 listings");
}

// Precies wat de server op 09-09-2026 om 11:32 UTC over zijn account wist.
const TOON = {
  online: false,
  seconds_ago: 79200,                 // 22 uur
  outdated_extension: "1.0.260",
  published_extension: "1.0.313",
  outdated_versies_achter: 53,
  outdated_krijgt_geen_werk: true,
};

console.log("Toons stand: stille extensie die tóch geen werk zou krijgen");
const toon = draai(TOON);
check("belooft niet meer dat de rij vanzelf op gang komt",
      !/picks up by itself/.test(toon.tekst),
      "dit is de zin van zijn schermafdruk: " + toon.tekst.slice(0, 120));
check("noemt de versie die er draait", /1\.0\.260/.test(toon.tekst), toon.tekst.slice(0, 160));
check("noemt de versie die er hoort te staan", /1\.0\.313/.test(toon.tekst));
check("zegt in de kop waar het op vastzit", /too old/i.test(toon.titel), toon.titel);
check("wijst naar de Chrome Web Store", /chrome\.google\.com\/webstore/.test(toon.tekst));
check("zegt dat elke Omnivaleur-regel eruit moet", /every<\/b> Omnivaleur entry/.test(toon.tekst));
check("stelt gerust dat het werk blijft staan", /Nothing is lost/.test(toon.tekst));

console.log("Een gewone stille extensie houdt de oude, kloppende tekst");
const gewoon = draai({ online: false, seconds_ago: 9000 });
check("zegt dat er niets loopt", /nothing is running/i.test(gewoon.titel));
check("stuurt hem wél naar de schakelaar", /picks up by itself/.test(gewoon.tekst));
check("geen versiepraat bij wie niets mankeert", !/1\.0\./.test(gewoon.tekst));

console.log("Een kopie die een paar versies achterloopt wordt niet lastiggevallen");
const bijna = draai({ online: false, seconds_ago: 9000, outdated_extension: "1.0.311",
                      published_extension: "1.0.313" });
check("geen 'too old' zonder dat de server het zegt", !/too old/i.test(bijna.titel), bijna.titel);

console.log(mislukt === 0 ? "\nAlles goed." : `\n${mislukt} controle(s) mislukt.`);
process.exit(mislukt === 0 ? 0 : 1);
