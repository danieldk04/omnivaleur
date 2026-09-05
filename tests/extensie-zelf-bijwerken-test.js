/**
 * De bijwerkcontrole draait hier ECHT, met een nagebootste chrome.alarms/runtime.
 *
 * 05-09-2026: gemeten dat van de negen verkopers waarvan we de versie konden
 * aflezen niemand de versie uit de Web Store draaide; de oudste zat 43 versies
 * achter. Chrome werkt alleen bij terwijl hij draait, dus wie zijn laptop
 * dichtklapt blijft achter. Deze test bewijst twee dingen: dat er om een update
 * gevraagd wordt, en dat er NOOIT herstart wordt terwijl er werk loopt.
 *
 * Draaien:  node tests/extensie-zelf-bijwerken-test.js
 *           node tests/extensie-zelf-bijwerken-test.js --oud   (vorige commit)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const stuk = (naam) => {
  const start = BG.indexOf(`async function ${naam}(`) >= 0
    ? BG.indexOf(`async function ${naam}(`) : BG.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden`);
  let i = BG.indexOf("{", BG.indexOf(")", start)), diep = 0;
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diep++;
    else if (BG[i] === "}") { diep--; if (diep === 0) return BG.slice(start, i + 1); }
  }
  throw new Error(`${naam} loopt niet af`);
};

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — " + JSON.stringify(extra) : ""}`);
};

// Eén ronde van de bijwerkcontrole, in een gesloten omgeving.
async function ronde({ status, pollLoopt = false, scans = 0, alarmen = [],
                       wachtSinds = 0, nu = Date.now() }) {
  const gedaan = { gevraagd: 0, herstart: 0 };
  const omgeving = {
    console: { log() {} },
    Date: { now: () => nu },
    chrome: {
      alarms: { getAll: async () => alarmen.map((n) => ({ name: n })) },
      runtime: {
        requestUpdateCheck: async () => { gedaan.gevraagd++; return { status }; },
        reload: () => { gedaan.herstart++; },
      },
    },
    JOB_WATCHDOG_PREFIX: "jobwd_",
    _pollLoopt: pollLoopt,
    _lopendeScans: new Set(Array.from({ length: scans }, (_, i) => "p" + i)),
    _updateWachtSinds: wachtSinds,
    UPDATE_UITSTEL_MAX_MS: 24 * 60 * 60 * 1000,
  };
  vm.createContext(omgeving);
  vm.runInContext(
    [stuk("magNuHerstarten"), stuk("herstartAlsHetKan"), stuk("controleerOpNieuweVersie")].join("\n"),
    omgeving);
  await vm.runInContext("controleerOpNieuweVersie()", omgeving);
  return { ...gedaan, wachtSinds: omgeving._updateWachtSinds };
}

(async () => {
  console.log(OUD ? "TEGEN DE VORIGE COMMIT (hier hoort het te falen)" : "HUIDIGE CODE");

  let r = await ronde({ status: "no_update" });
  ok("vraagt Chrome om een controle", r.gevraagd === 1, r);
  ok("geen update = geen herstart", r.herstart === 0, r);

  r = await ronde({ status: "update_available" });
  ok("nieuwe versie en niets te doen = herstart meteen", r.herstart === 1, r);

  r = await ronde({ status: "update_available", pollLoopt: true });
  ok("wachtrij loopt = NIET herstarten", r.herstart === 0, r);

  r = await ronde({ status: "update_available", scans: 1 });
  ok("scan bezig = NIET herstarten", r.herstart === 0, r);

  r = await ronde({ status: "update_available", alarmen: ["jobwd_42", "poll"] });
  ok("advertentie halverwege = NIET herstarten", r.herstart === 0, r);

  r = await ronde({ status: "update_available", alarmen: ["poll", "sold-check"] });
  ok("alleen gewone wekkers = wel herstarten", r.herstart === 1, r);

  const nu = 1_000_000_000_000;
  r = await ronde({ status: "update_available", pollLoopt: true,
                    wachtSinds: nu - 25 * 60 * 60 * 1000, nu });
  ok("na een dag vastgelopen werk toch herstarten", r.herstart === 1, r);
  ok("die ronde vraagt Chrome niets meer", r.gevraagd === 0, r);

  console.log(mislukt === 0 ? "\nAlles goed." : `\n${mislukt} mislukt.`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
