/**
 * Toon (dejuistetoon), 03-09-2026, 12:44:
 *   "Ben al ff aan het laden 50 jobs, maar er gebeurd eigenlijk niets?"
 *
 * Op zijn schermafdruk staat de balk die zegt: "50 jobs queued — the extension
 * is about to start … Within ~15 seconds the extension opens a tab".
 *
 * Gemeten aan zijn eigen opdrachtenlogboek zat er die dag 345 seconden tussen
 * twee publicaties (Calm mode staat bij hem aan; bij drie andere verkopers op
 * dezelfde dag was het 10 tot 12 seconden). Zijn werk liep dus gewoon — de balk
 * beloofde alleen iets wat vijfentwintig keer zo snel was als de werkelijkheid.
 * Acht minuten niets zien terwijl er "about to start" staat leest als kapot.
 *
 * Deze test draait de échte renderActivityBar uit app.html, met een nagebouwd
 * scherm, en zet de oude tekst naast de nieuwe.
 *
 * Draaien: node tests/wachtrijbalk-eerlijk-test.js
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

// Een piepklein scherm: alleen de elementen die de balk aanraakt.
function nepScherm() {
  const el = () => ({ style: {}, textContent: "", innerHTML: "", className: "",
                      classList: { add() {}, remove() {} } });
  const knopen = { "ext-activity-bar": el(), "ext-activity-title": el(),
                   "ext-activity-text": el(), "ext-activity-icon": el() };
  return { knopen, getElementById: (id) => knopen[id] || null };
}

function draai({ queued, pace, online }) {
  const scherm = nepScherm();
  const bron = [
    functieUit("fmtQueueEta"),
    functieUit("fmtSeenAgo"),
    functieUit("renderActivityBar"),
    "renderActivityBar();",
    "return { titel: document.getElementById('ext-activity-title').textContent,",
    "         tekst: document.getElementById('ext-activity-text').innerHTML };",
  ].join("\n");
  const fn = new Function("document", "_activityState", "state", "describeJobs", bron);
  return fn(scherm,
            { working: [], queued, pace },
            { extStatus: online === null ? null : { online, seconds_ago: online ? 3 : 9000 } },
            () => "50 listings");
}

const VIJFTIG = Array.from({ length: 50 }, (_, i) => ({ id: `j${i}`, action: "create" }));

console.log("Calm mode: de balk noemt het echte tempo in plaats van 15 seconden");
const kalm = draai({ queued: VIJFTIG, pace: { calm: true, seconds_between: 345, samples: 10 }, online: true });
check("belooft geen 15 seconden meer", !/15 seconds/.test(kalm.tekst),
      "dit is precies de zin die Toon op zijn scherm zag: " + kalm.tekst.slice(0, 90));
check("noemt Calm mode bij naam", /Calm mode/.test(kalm.titel + kalm.tekst));
check("noemt het gemeten tempo (6 minuten)", /one every 6 minutes/.test(kalm.tekst), kalm.tekst.slice(0, 140));
check("noemt hoe lang die 50 gaan duren", /about 5 hours/.test(kalm.tekst), kalm.tekst.slice(0, 200));
check("zegt met zoveel woorden dat er niets stuk is", /Nothing is stuck/.test(kalm.tekst));
check("vertelt waar de schakelaar zit", /extension icon/.test(kalm.tekst));

console.log("Zonder Calm mode blijft de oude, kloppende tekst staan");
const snel = draai({ queued: VIJFTIG, pace: { calm: false, seconds_between: 11, samples: 10 }, online: true });
check("nog steeds ~15 seconden", /15 seconds/.test(snel.tekst));
check("geen Calm mode-praat bij wie hem uit heeft", !/Calm mode/.test(snel.titel + snel.tekst));

console.log("Staat de extensie stil, dan belooft de balk niets");
const stil = draai({ queued: VIJFTIG, pace: { calm: false, seconds_between: 11, samples: 10 }, online: false });
check("zegt dat er niets loopt", /nothing is running/i.test(stil.titel));
check("belooft geen 15 seconden aan een stille extensie", !/15 seconds/.test(stil.tekst), stil.tekst.slice(0, 120));
check("wijst naar chrome://extensions", /chrome:\/\/extensions/.test(stil.tekst));
check("stelt gerust dat er niets verloren gaat", /Nothing is lost/.test(stil.tekst));

console.log("Weten we het tempo niet, dan doen we geen bewering");
const onbekend = draai({ queued: VIJFTIG, pace: { calm: false, seconds_between: null, samples: 0 }, online: null });
check("valt terug op de gewone tekst", /15 seconds/.test(onbekend.tekst));

// 05-09-2026, Toon opnieuw. Calm mode stond die dag UIT, en tóch stonden er 38
// publicaties van elk een minuut te wachten. De balk zei alleen "about to
// start": over de looptijd van de rij zweeg hij, want die zin zat alleen in de
// Calm mode-tak. Gemeten op zijn account: gat 30 s, hele opdracht 60 s.
console.log("Zonder Calm mode noemt de balk nu wél hoe lang de rij duurt");
const lang = draai({ queued: VIJFTIG,
                     pace: { calm: false, seconds_between: 30, seconds_per_job: 60, samples: 11 },
                     online: true });
check("noemt de looptijd van de hele rij", /about 50 minutes/.test(lang.tekst), lang.tekst.slice(0, 220));
check("zegt met zoveel woorden dat er niets stuk is", /nothing is stuck/i.test(lang.tekst));
check("zegt er nog steeds bij wanneer het begint", /15 seconds/.test(lang.tekst));
check("nog steeds geen Calm mode-praat", !/Calm mode/.test(lang.titel + lang.tekst));

console.log("Bij een kort rijtje geen looptijd erbij");
const kort = draai({ queued: VIJFTIG.slice(0, 2),
                     pace: { calm: false, seconds_between: 30, seconds_per_job: 60, samples: 11 },
                     online: true });
check("twee opdrachten krijgen geen looptijdzin", !/together take/.test(kort.tekst), kort.tekst.slice(0, 160));

console.log("De looptijd rekent met de hele opdracht, niet met het gat ertussen");
const kalmEcht = draai({ queued: VIJFTIG,
                         pace: { calm: true, seconds_between: 345, seconds_per_job: 375, samples: 10 },
                         online: true });
check("Calm mode rekent met seconds_per_job", /about 5 hours/.test(kalmEcht.tekst), kalmEcht.tekst.slice(0, 200));

console.log(mislukt === 0 ? "\nAlles goed." : `\n${mislukt} controle(s) mislukt.`);
process.exit(mislukt === 0 ? 0 : 1);
