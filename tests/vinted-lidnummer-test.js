/**
 * _mwVintedKast draait hier ECHT: hoe stelt de extensie vast wie je bent op
 * Vinted, en wat zegt je kast over één advertentie?
 *
 * Aanleiding (05-09-2026): op de startpagina van vinted.nl stond geen
 * /member/-link en ging het uitklapmenu in het verborgen werk-tabblad niet
 * open. Daniel kreeg daardoor "Could not determine your Vinted member id" terwijl
 * hij ingelogd was. /api/v2/users/current is het antwoord van Vinted zelf en
 * hangt nergens van af; het 401-antwoord hieronder is wat vinted.nl op
 * 01-09-2026 werkelijk teruggaf zonder cookies (zie vinted-eigendom-test.js).
 *
 * Draaien:  node tests/vinted-lidnummer-test.js
 *           node tests/vinted-lidnummer-test.js --oud   (vorige commit: faalt)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const OUD = process.argv.includes("--oud");
const BG = OUD
  ? execSync("git show HEAD:extension/background.js", { cwd: path.join(__dirname, ".."), maxBuffer: 1 << 28 }).toString()
  : fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

const start = BG.indexOf("async function _mwVintedKast(");
if (start < 0) throw new Error("_mwVintedKast niet gevonden");
const bron = BG.slice(start, BG.indexOf("\n}\n", start) + 2);

let mislukt = 0;
const ok = (naam, v, extra) => {
  if (v) { console.log(`  ✓ ${naam}`); return; }
  mislukt++; console.log(`  ✗ ${naam}${extra !== undefined ? " — kreeg " + JSON.stringify(extra) : ""}`);
};

// Een startpagina zonder /member/-link en zonder werkend uitklapmenu: precies
// wat Daniels tabblad liet zien.
const KALE_PAGINA = { querySelectorAll: () => [], querySelector: () => null };

async function kast({ current, kastIds, doc = KALE_PAGINA }) {
  const fetchStub = async (u) => {
    if (u.includes("users/current")) return current;
    if (u.includes("/wardrobe/")) {
      return { ok: true, status: 200,
               json: async () => ({ items: kastIds.map(x => (typeof x === "object" ? x : { id: x })),
                                    pagination: { total_pages: 1 } }) };
    }
    throw new Error("onverwachte aanroep: " + u);
  };
  const fn = new Function("document", "fetch", "setTimeout", `${bron}; return _mwVintedKast;`)(doc, fetchStub, setTimeout);
  return fn("8289521490");
}

const INGELOGD = { ok: true, status: 200, json: async () => ({ user: { id: 12345 } }) };
const UITGELOGD = { ok: false, status: 401, json: async () => ({ code: 100, message_code: "invalid_authentication_token" }) };

(async () => {
  console.log("\nWie ben ik op Vinted?");

  let r = await kast({ current: INGELOGD, kastIds: [111, 222] });
  ok("ingelogd zonder /member/-link op de pagina -> lidnummer via Vinted zelf",
     r.userId === "12345" && r.present === false, r);

  r = await kast({ current: INGELOGD, kastIds: [111, 8289521490] });
  ok("advertentie staat nog in de kast -> present", r.present === true, r);

  r = await kast({ current: INGELOGD, kastIds: [{ id: 8289521490, is_closed: true }] });
  ok("verkocht in de kast -> closed", r.present === true && r.closed === true, r);

  r = await kast({ current: UITGELOGD, kastIds: [] });
  ok("echt uitgelogd -> geen lidnummer, en niets aannemen over de kast",
     r.userId === null && r.present === null, r);

  const METLINK = { querySelectorAll: () => [{ getAttribute: () => "/member/999" }], querySelector: () => null };
  r = await kast({ current: UITGELOGD, kastIds: [], doc: METLINK });
  ok("staat het lidnummer wél op de pagina, dan telt dat nog steeds",
     r.userId === "999", r);

  console.log(mislukt === 0 ? "\nAlles goed\n" : `\n${mislukt} mislukt\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})();
