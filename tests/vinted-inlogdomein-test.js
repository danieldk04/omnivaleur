/**
 * Daniel, 04-09-2026: "vinted geeft bij mij deze melding terwijl ik toch
 * overduidelijk ben ingelogd. hij publiceert daarom niks."
 *
 * De melding luidde: "You are not signed in to Vinted (vinted.com)."
 * Hij was ingelogd op vinted.nl.
 *
 * OORZAAK, GEMETEN OP 04-09-2026:
 *   curl https://www.vinted.com/api/v2/users/current  ->  401, geen doorverwijzing
 * Een Vinted-account leeft op één landdomein en de sessiecookie reist niet mee
 * naar een ander domein. De inlogcontrole viel terug op vinted.com zodra de
 * opdracht geen _create_origin droeg, en dat is bij élke eerste plaatsing zo:
 * _create_origin wordt alleen gezet bij herplaatsen (backend/services/relist.py).
 *
 * Deze test draait de ECHTE functies uit background.js, met een nagebootste
 * Vinted die alleen op vinted.nl een sessie kent.
 *
 * Draaien: node tests/vinted-inlogdomein-test.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execFileSync } = require("child_process");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");

function stukUit(bron, vanaf, functies) {
  const start = bron.indexOf(vanaf);
  if (start < 0) throw new Error(`"${vanaf}" niet gevonden`);
  let code = bron.slice(start, bron.indexOf("\n\n", bron.indexOf("VINTED_ORIGIN_TTL_MS =", start)) + 1);
  for (const naam of functies) {
    const s = bron.indexOf(`async function ${naam}(`);
    if (s < 0) throw new Error(`${naam} niet gevonden`);
    const e = bron.indexOf("\n}\n", s);
    code += "\n" + bron.slice(s, e + 2);
  }
  return code;
}

// Een nagebootste Vinted: ingelogd op vinted.nl, nergens anders.
function maakZand(sessieOp, kapot = []) {
  const zand = { console: { log() {}, warn() {}, error() {} }, gevraagd: [], Date, URL };
  zand.window = zand;
  zand.fetch = async (url) => {
    zand.gevraagd.push(url);
    const origin = new URL(url).origin;
    if (kapot.includes(origin)) throw new Error("net stuk");
    if (origin === sessieOp) {
      return { ok: true, status: 200, json: async () => ({ user: { id: 42 } }) };
    }
    return { ok: false, status: 401, json: async () => ({}) };
  };
  vm.createContext(zand);
  return zand;
}

const CODE = stukUit(BG, "const VINTED_ORIGINS = [",
  ["vintedIngelogd", "vintedIngelogdOrigin", "vintedOriginKlaarzetten"]);

(async () => {
  // ── 1. De voor-proef: de oude code zei aantoonbaar "niet ingelogd" ──────
  console.log("Wat de oude versie deed");
  const OUD = execFileSync("git", ["show", "HEAD:extension/background.js"],
    { cwd: path.join(__dirname, ".."), encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  check("de oude controle viel terug op vinted.com",
    /const origin = job\.payload\?\._create_origin \|\| "https:\/\/www\.vinted\.com";\s*\n\s*const ingelogd = await vintedIngelogd\(origin\);/.test(OUD),
    "dan bewijst deze test niets");

  const oudeFn = OUD.slice(OUD.indexOf("async function vintedIngelogd("));
  const zandOud = maakZand("https://www.vinted.nl");
  vm.runInContext(oudeFn.slice(0, oudeFn.indexOf("\n}\n") + 2), zandOud, { filename: "oud" });
  const oudeUitslag = await zandOud.vintedIngelogd("https://www.vinted.com");
  check("ingelogd op vinted.nl gaf op vinted.com 'niet ingelogd'", oudeUitslag === false,
    `kreeg ${oudeUitslag} — dan lag het ergens anders aan`);

  // ── 2. De nieuwe versie vindt het juiste domein ────────────────────────
  console.log("\nDe nieuwe versie zoekt het domein op");
  const zand = maakZand("https://www.vinted.nl");
  vm.runInContext(CODE, zand, { filename: "background.js" });

  const gevonden = await zand.vintedIngelogdOrigin(null);
  check("hij vindt vinted.nl", gevonden === "https://www.vinted.nl", `kreeg ${gevonden}`);

  const job = { platform: "vinted", action: "create", payload: { title: "Wielrenshirt" } };
  const klaar = await zand.vintedOriginKlaarzetten(job);
  check("de opdracht mag door", klaar.ok === true);
  check("het plaatsformulier opent op vinted.nl",
    job.payload._create_origin === "https://www.vinted.nl",
    `staat op ${job.payload._create_origin} — dan komt de advertentie in de verkeerde catalogus`);

  // ── 3. Een Belgische verkoper ─────────────────────────────────────────
  console.log("\nEen verkoper op vinted.be");
  const zandBe = maakZand("https://www.vinted.be");
  vm.runInContext(CODE, zandBe, { filename: "background.js" });
  const jobBe = { platform: "vinted", action: "create", payload: {} };
  await zandBe.vintedOriginKlaarzetten(jobBe);
  check("hij komt op vinted.be uit", jobBe.payload._create_origin === "https://www.vinted.be",
    `staat op ${jobBe.payload._create_origin}`);

  // ── 4. Echt uitgelogd wordt nog steeds tegengehouden ──────────────────
  console.log("\nEcht nergens ingelogd");
  const zandUit = maakZand("https://www.nergens.example");
  vm.runInContext(CODE, zandUit, { filename: "background.js" });
  const jobUit = { platform: "vinted", action: "create", payload: {} };
  const uit = await zandUit.vintedOriginKlaarzetten(jobUit);
  check("de opdracht wordt afgemeld", uit.ok === false);
  check("de melding noemt geen enkel los domein meer als schuldige",
    !/not signed in to Vinted \(/.test(uit.melding || ""), uit.melding);
  check("de melding zegt welke domeinen zijn nagekeken",
    /vinted\.nl.*vinted\.be.*vinted\.com/.test(uit.melding || ""), uit.melding);
  check("alle vijf domeinen zijn echt bevraagd",
    new Set(zandUit.gevraagd.map((u) => new URL(u).origin)).size === 5,
    `${new Set(zandUit.gevraagd.map((u) => new URL(u).origin)).size} domeinen bevraagd`);

  // ── 5. Een storing mag het werk niet tegenhouden ──────────────────────
  console.log("\nAls Vinted zelf onbereikbaar is");
  const zandStuk = maakZand("https://www.nergens.example",
    ["https://www.vinted.nl", "https://www.vinted.be", "https://www.vinted.de",
     "https://www.vinted.fr", "https://www.vinted.com"]);
  vm.runInContext(CODE, zandStuk, { filename: "background.js" });
  const jobStuk = { platform: "vinted", action: "create", payload: {} };
  const stuk = await zandStuk.vintedOriginKlaarzetten(jobStuk);
  check("de opdracht gaat gewoon door", stuk.ok === true,
    "een onzekere controle mag geen werk tegenhouden");
  check("er wordt dan geen domein opgedrongen", !jobStuk.payload._create_origin);

  // ── 6. Een herplaatsing houdt zijn eigen domein ───────────────────────
  console.log("\nHerplaatsen houdt het domein van de oude advertentie");
  const zandRe = maakZand("https://www.vinted.nl");
  vm.runInContext(CODE, zandRe, { filename: "background.js" });
  const jobRe = { platform: "vinted", action: "create",
                  payload: { _create_origin: "https://www.vinted.nl" } };
  await zandRe.vintedOriginKlaarzetten(jobRe);
  check("hij vraagt vinted.nl als eerste",
    new URL(zandRe.gevraagd[0]).origin === "https://www.vinted.nl");
  check("en blijft daar", jobRe.payload._create_origin === "https://www.vinted.nl");

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed.");
  process.exit(mislukt ? 1 : 0);
})();
