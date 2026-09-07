/**
 * "Je bent niet ingelogd" mag alleen gezegd worden als de site dat zelf zegt.
 *
 * WAT ER GEBEURDE (Egbert Brouwer, papas-plectrums, 06-09-2026).
 * Twee metingen op precies dezelfde URL, in dezelfde browser, dezelfde minuut:
 *
 *   21:07:35  vanuit een tabblad OP www.2dehands.be   -> HTTP 200
 *   21:07:48  vanuit de service worker van de extensie -> HTTP 401
 *   21:11:22  weer vanuit het tabblad                  -> HTTP 200
 *   21:11:27  weer vanuit de service worker            -> HTTP 401
 *
 * Die 200 op /my-account/sell/api/listings krijg je alleen met een geldige
 * sessie; dat is de aanname waar de hele controle op rust. Hij WAS dus
 * ingelogd. Toch is op grond van de 401 zijn wachtrij van 346 opdrachten
 * teruggenomen met de mededeling dat hij niet was ingelogd. Derde keer voor
 * dezelfde man.
 *
 * Deze test legt de regel vast: een weigering uit de achtergrond is een
 * vermoeden, nooit een oordeel. Het oordeel valt in een tabblad op de site.
 *
 * Draaien: node tests/inlogverwijt-alleen-vanuit-de-site-zelf-test.js
 *          node tests/inlogverwijt-alleen-vanuit-de-site-zelf-test.js --oud
 *          (tegen de vorige commit; die MOET falen)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync("git show HEAD:extension/background.js", { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function blokUit(naam, woord = "function") {
  // Op naam MET haakje: anders vindt "mpSessie" ook "mpSessieEerstepartij".
  const start = BG.indexOf(`${woord} ${naam}(`);
  if (start < 0) return null;
  let diepte = 0, i = BG.indexOf("{", start);
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(start, i + 1);
}
function constUit(naam) {
  const start = BG.indexOf(`const ${naam} = `);
  if (start < 0) return null;
  const na = BG.indexOf("=", start) + 1;
  if (BG.slice(na).trimStart().startsWith("[")) {
    let diepte = 0, i = BG.indexOf("[", na);
    for (; i < BG.length; i++) {
      if (BG[i] === "[") diepte++;
      else if (BG[i] === "]") { diepte--; if (!diepte) break; }
    }
    return BG.slice(start, i + 2);
  }
  if (BG.slice(na).trimStart().startsWith("{")) {
    let diepte = 0, i = BG.indexOf("{", na);
    for (; i < BG.length; i++) {
      if (BG[i] === "{") diepte++;
      else if (BG[i] === "}") { diepte--; if (!diepte) break; }
    }
    return BG.slice(start, i + 2);
  }
  return BG.slice(start, BG.indexOf("\n", start));
}

const nodig = {
  mpSessie: blokUit("mpSessie", "async function"),
  mpIngelogdOpDeSiteZelf: blokUit("mpIngelogdOpDeSiteZelf", "async function"),
  mpPlaatsenKlaarzetten: blokUit("mpPlaatsenKlaarzetten", "async function"),
  mpNietIngelogdMelding: blokUit("mpNietIngelogdMelding"),
  vintedOriginKlaarzetten: blokUit("vintedOriginKlaarzetten", "async function"),
  vintedEerstepartijOrigin: blokUit("vintedEerstepartijOrigin", "async function"),
};
const ontbreekt = Object.entries(nodig).filter(([, v]) => !v).map(([k]) => k);
if (ontbreekt.length) {
  check("de eerstepartij-inlogcontrole bestaat", false,
    `ontbreekt: ${ontbreekt.join(", ")}, dus een weigering uit de achtergrond is nog steeds een eindoordeel`);
  // Laat meteen zien wat die versie dan doet in precies de gemeten situatie:
  // de achtergrond krijgt 401 terwijl de site zelf 200 geeft.
  if (nodig.mpPlaatsenKlaarzetten && nodig.mpSessie) {
    const c = {
      console: { log() {}, warn() {}, error() {} },
      SITE_NAAM: { "2dehands": "2dehands (2dehands.be)" },
      fetch: async () => ({ status: 401, ok: false, json: async () => null }),
      gestopt: [],
    };
    c.stopPlatformWachtrij = async (u, p, r) => { c.gestopt.push({ p, r }); };
    vm.createContext(c);
    vm.runInContext([constUit("MP_SESSIE_URL"), constUit("MP_INLOG_URL"),
      nodig.mpSessie, nodig.mpNietIngelogdMelding, nodig.mpPlaatsenKlaarzetten].join("\n"), c);
    vm.runInContext(`mpPlaatsenKlaarzetten({ platform: "2dehands", action: "create" }, "s")`, c)
      .then((uit) => {
        check("een 401 uit de achtergrond neemt niet in zijn eentje de wachtrij af",
          c.gestopt.length === 0 && uit.ok === true,
          "de wachtrij werd gestopt op grond van alleen de achtergrondmeting");
        klaar();
      });
  } else {
    klaar();
  }
}

// ── Opstelling ────────────────────────────────────────────────────────────
// Alleen de stukken die over inloggen gaan, met de buitenwereld nagemaakt.
const bron = [
  constUit("MP_SESSIE_URL"), constUit("MP_INLOG_URL"), constUit("MP_OVERZICHT_URL"),
  constUit("EERSTEPARTIJ_TTL_MS"), constUit("_eerstepartijOordeel"),
  constUit("VINTED_ORIGINS"),
  "const vintedKaalDomein = (o) => String(o || '').replace(/^https:\\/\\/(www\\.)?/, '');",
  "let _vintedOriginCache = null;",
  "let _vintedEerstepartij = null;",
  blokUit("vintedIngelogd", "async function"),
  blokUit("vintedIngelogdOrigin", "async function"),
  nodig.vintedEerstepartijOrigin,
  nodig.vintedOriginKlaarzetten,
  nodig.mpSessie, nodig.mpIngelogdOpDeSiteZelf, nodig.mpNietIngelogdMelding,
  nodig.mpPlaatsenKlaarzetten,
].join("\n");

const ctx = {
  console: { log() {}, warn() {}, error() {} },
  SITE_NAAM: { marktplaats: "Marktplaats (marktplaats.nl)", "2dehands": "2dehands (2dehands.be)", vinted: "Vinted" },
  // Wat de achtergrond (service worker) te horen krijgt.
  achtergrondStatus: 401,
  // Wat een tabblad OP de site te horen krijgt.
  eerstepartij: null,
  gestopt: [],
  tabbladen: 0,
};
ctx.fetch = async () => ({
  status: ctx.achtergrondStatus,
  ok: ctx.achtergrondStatus >= 200 && ctx.achtergrondStatus < 300,
  json: async () => ctx.achtergrondBody || null,
});
ctx.eerstepartijStatus = async () => { ctx.tabbladen++; return ctx.eerstepartij; };
ctx.stopPlatformWachtrij = async (serverUrl, platform, reden) => { ctx.gestopt.push({ platform, reden }); };
vm.createContext(ctx);
vm.runInContext(bron, ctx);

const leegmaken = () => {
  ctx.gestopt.length = 0; ctx.tabbladen = 0;
  vm.runInContext("for (const k of Object.keys(_eerstepartijOordeel)) delete _eerstepartijOordeel[k];"
    + " _vintedEerstepartij = null; _vintedOriginCache = null;", ctx);
};
const plaatsen = () => vm.runInContext(
  `mpPlaatsenKlaarzetten({ platform: "2dehands", action: "create" }, "https://omnivaleur.com")`, ctx);

(async () => {
  // ── 1. De gemeten situatie: achtergrond 401, de site zelf 200 ────────────
  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = { status: 200, body: null, url: "https://www.2dehands.be/my-account/sell/index.html" };
  let uit = await plaatsen();
  check("achtergrond 401 + site zelf 200: de opdracht gaat gewoon door", uit.ok === true,
    JSON.stringify(uit));
  check("achtergrond 401 + site zelf 200: de wachtrij blijft staan", ctx.gestopt.length === 0,
    `er werden ${ctx.gestopt.length} wachtrijen gestopt`);

  // ── 2. Echt uitgelogd: allebei weigeren ─────────────────────────────────
  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = { status: 401, body: null, url: "https://www.2dehands.be/identity/v2/login" };
  uit = await plaatsen();
  check("allebei 401: er wordt niets gepubliceerd", uit.ok === false, JSON.stringify(uit));
  check("allebei 401: de wachtrij wordt wél gestopt", ctx.gestopt.length === 1);
  check("de melding noemt waar de browser terechtkwam",
    /identity\/v2\/login/.test(uit.melding || ""), uit.melding);
  check("de melding zegt dat er twee keer gekeken is",
    /in a tab on/i.test(uit.melding || ""), uit.melding);
  check("de melding bevat geen gedachtestreepje", !/ [—–] /.test(uit.melding || ""), uit.melding);

  // ── 3. Gewoon ingelogd: geen extra tabblad, geen vertraging ──────────────
  leegmaken();
  ctx.achtergrondStatus = 200;
  ctx.eerstepartij = { status: 401, body: null, url: "x" };
  uit = await plaatsen();
  check("wie ingelogd is merkt niets van de extra controle",
    uit.ok === true && ctx.tabbladen === 0, `tabbladen=${ctx.tabbladen}`);

  // ── 4. De tweede meting lukt niet: werk gaat door ────────────────────────
  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = null;                       // tabblad ging niet open
  uit = await plaatsen();
  check("kunnen we het niet vaststellen, dan houden we niets tegen", uit.ok === true,
    JSON.stringify(uit));
  check("en dan wordt er ook geen wachtrij gestopt", ctx.gestopt.length === 0);

  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = { status: 503, body: null, url: "x" };   // onderhoud
  uit = await plaatsen();
  check("een storing bij de site houdt het werk niet tegen", uit.ok === true, JSON.stringify(uit));

  // ── 5. Het oordeel wordt niet per opdracht opnieuw opgehaald ─────────────
  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = { status: 200, body: null, url: "u" };
  await plaatsen(); await plaatsen(); await plaatsen();
  check("de tweede meting kost één tabblad, niet één per opdracht", ctx.tabbladen === 1,
    `${ctx.tabbladen} tabbladen voor drie opdrachten`);

  // ── 6. Vinted zit in dezelfde blinde hoek ───────────────────────────────
  leegmaken();
  ctx.achtergrondStatus = 401;                   // elk Vinted-domein weigert
  ctx.eerstepartij = { status: 200, body: { user: { id: 42 } }, url: "https://www.vinted.nl/" };
  const v = await vm.runInContext(`vintedOriginKlaarzetten({ payload: {} })`, ctx);
  check("Vinted: achtergrond zegt nergens ingelogd, de site zelf wél, dus doorgaan",
    v.ok === true, JSON.stringify(v));

  leegmaken();
  ctx.achtergrondStatus = 401;
  ctx.eerstepartij = { status: 401, body: null, url: "https://www.vinted.nl/member/general" };
  const v2 = await vm.runInContext(`vintedOriginKlaarzetten({ payload: {} })`, ctx);
  check("Vinted: overal geweigerd, dan pas een melding", v2.ok === false, JSON.stringify(v2));

  klaar();
})();

function klaar() {
  console.log(mislukt ? `\n${mislukt} controle(s) mislukt.` : "\nAlles goed.");
  process.exit(mislukt ? 1 : 0);
}
