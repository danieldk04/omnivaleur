/**
 * Janneke, 10-10-2026: haar Chrome draaide extensie 1.0.374 terwijl 1.0.376 in de
 * Web Store stond. Elke mislukte Vinted-plaatsing liet een tabblad open voor
 * "maak hem zelf af", met een controle-wekker (jobwd_<tab>), en zolang er zo'n
 * wekker stond weigerde magNuHerstarten de update. Nieuwe mislukking, nieuwe
 * wekker: de oude versie hield zichzelf in stand.
 *
 * Draait de echte magNuHerstarten uit background.js. Op de versie van vóór de
 * reparatie faalt het eerste blok.
 */
const fs = require("fs");
const path = require("path");
const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
function functie(naam) {
  const i = BG.indexOf(`async function ${naam}(`);
  return BG.slice(i, BG.indexOf("\n}\n", i) + 2);
}
let mislukt = 0;
function check(naam, ok) { console.log(`  ${ok ? "ok  " : "FOUT"} ${naam}`); if (!ok) mislukt++; }

async function magHet({ alarmen, opslag, pollLoopt = false }) {
  const chrome = {
    alarms: { getAll: async () => alarmen.map((name) => ({ name })) },
    storage: { local: { get: async () => opslag } },
  };
  const fn = new Function("chrome", "_pollLoopt", "_lopendeScans", "JOB_WATCHDOG_PREFIX",
    functie("magNuHerstarten") + "\nreturn magNuHerstarten();");
  return fn(chrome, pollLoopt, new Set(), "jobwd_");
}

(async () => {
  console.log("Alleen tabbladen die al aan de verkoper zijn teruggegeven");
  check("houden de update niet tegen", await magHet({
    alarmen: ["jobwd_11", "jobwd_12", "poll"],
    opslag: { jobtab_11: { jobId: "a", awaitingManualFinish: true }, jobtab_12: { jobId: "b", awaitingManualFinish: true } },
  }) === true);

  console.log("Een plaatsing die echt nog loopt");
  check("houdt de update wel tegen", await magHet({
    alarmen: ["jobwd_11", "jobwd_13"],
    opslag: { jobtab_11: { jobId: "a", awaitingManualFinish: true }, jobtab_13: { jobId: "c" } },
  }) === false);
  check("ook als er geen opslag bij de wekker is", await magHet({ alarmen: ["jobwd_14"], opslag: {} }) === false);
  check("en tijdens een pollronde nooit", await magHet({ alarmen: [], opslag: {}, pollLoopt: true }) === false);
  process.exit(mislukt ? 1 : 0);
})();
