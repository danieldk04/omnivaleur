/**
 * Het dashboard moet weten dat iemand op Marktplaats en Vinted is ingelogd,
 * ook als er nog nooit werk is geplaatst (Janneke 31d28378, 07-10-2026).
 *
 * Draait de echte meetKanaalSessiesVoorDashboard uit background.js met een
 * nep-Chrome en de meetfuncties eronder nagebootst voor haar situatie:
 * zakelijk Marktplaats-account (persoonlijk adres 401, site-kopbalk zegt ja),
 * Vinted op vinted.be.
 *
 * Draaien:  node tests/kanaal-sessie-meten-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const bron = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const van = bron.indexOf("const SESSIE_METING_VERS_MS");
const tot = bron.indexOf("async function mpSessie(platform)");
if (van < 0 || tot < 0) { console.log("  ✗ meetfunctie staat niet in background.js"); process.exit(1); }

let opslag = {};
const ctx = {
  Date, console,
  leesKanaalSessies: async () => ({ ...opslag }),
  onthoudKanaalSessie: async (p, ingelogd, extra = {}) => { opslag[p] = { ingelogd, at: Date.now(), ...extra }; },
  mpSessie: async () => ({ ingelogd: null, status: 401 }),          // zakelijk: persoonlijk adres is dicht
  mpIngelogdOpDeSiteZelf: async (p) => { ctx.onthoudKanaalSessie(p, true, { status: 401 }); return { ingelogd: true }; },
  vintedIngelogdOrigin: async () => "https://www.vinted.be",
  vintedEerstepartijOrigin: async () => null,
};
vm.createContext(ctx);
vm.runInContext(bron.slice(van, tot) + "\nthis.meet = meetKanaalSessiesVoorDashboard;", ctx);

(async () => {
  let mislukt = 0;
  const ok = (n, v, k) => v ? console.log(`  ✓ ${n}`) : (mislukt++, console.log(`  ✗ ${n} — kreeg ${JSON.stringify(k)}`));
  await ctx.meet();
  ok("Marktplaats (zakelijk) staat als ingelogd", opslag.marktplaats && opslag.marktplaats.ingelogd === true, opslag);
  ok("Vinted (vinted.be) staat als ingelogd", opslag.vinted && opslag.vinted.ingelogd === true && /vinted\.be/.test(opslag.vinted.url), opslag);

  opslag = {};
  ctx.vintedIngelogdOrigin = async () => false;
  ctx.vintedEerstepartijOrigin = async () => false;
  ctx.mpIngelogdOpDeSiteZelf = async (p) => { ctx.onthoudKanaalSessie(p, false, { status: 401 }); return { ingelogd: false }; };
  ctx.meet.klaar = null;
  // tweede ronde binnen de pauze: mag niets meten
  await ctx.meet();
  ok("binnen de pauze wordt niet opnieuw gemeten", Object.keys(opslag).length === 0, opslag);
  console.log(mislukt ? `\n${mislukt} MISLUKT` : "\nalles groen");
  process.exit(mislukt ? 1 : 0);
})();
