/**
 * Twee reparaties van 31-10-2026 (Egbert Brouwer), met de échte code uit background.js:
 *
 *  1. De Admarkt-scan nam voor een foto zonder verwerkte maten `i.src` over, een
 *     intern adres (dmz.mp.prod.icas.io, 10.37.x.x) waar niemand bij kan.
 *  2. checkVintedOrders opende elke 10 tot 40 minuten een Vinted-tabblad, ook voor
 *     een klant zonder één Vinted-artikel.
 *
 * Draaien: node tests/extensie-foto-en-vinted-poort-test.js [pad naar background.js]
 * Voor de voor-en-na-proef: geef de oude versie mee, bijvoorbeeld
 *   git show a61c73bf:extension/background.js > /tmp/oud.js
 * De proef hoort dan te falen.
 */
const fs = require("fs");
const vm = require("vm");
const pad = process.argv[2] || __dirname + "/../extension/background.js";
const bron = fs.readFileSync(pad, "utf8");
let mislukt = 0;
const check = (naam, goed, uitleg) => {
  if (goed) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
};

// ── 1. De fotokiezer, letterlijk uit de bron gehaald ──────────────────────
const start = bron.indexOf("const fotos = (ad.images || [])");
const eind = bron.indexOf(".filter(Boolean);", start);
if (start < 0 || eind < 0) { console.log("FOUT: fotokiezer niet gevonden in " + pad); process.exit(1); }
const uitdrukking = bron.slice(start + "const fotos = ".length, eind + ".filter(Boolean)".length);
const kies = (images) => vm.runInNewContext(`(function(ad){ return ${uitdrukking}; })`)({ images });

const CDN = "//admarkt-cdn.marktplaats.com/api/v1/icas-mp-pro-admarkt/images/b6/b6ec5faf?rule=r-1024x1024";
const INTERN = "https://dmz.mp.prod.icas.io/api/sellside/image/19c4d8bdb82af845/5a098dc9-b86f-448d-9239-46c5a4502dec";
console.log("Fotokiezer:");
check("een foto met 1024x1024 geeft dat adres", JSON.stringify(kies([{ links: { "1024x1024": CDN } }])) === JSON.stringify(["https:" + CDN]));
check("alleen het interne src geeft geen foto in plaats van een dood adres",
  kies([{ src: INTERN }]).length === 0, JSON.stringify(kies([{ src: INTERN }])));
check("zonder de vaste maten wordt de grootste beschikbare maat genomen",
  JSON.stringify(kies([{ links: { "200x200": "//x/klein", "800x800": "//x/groot" }, src: INTERN }])) === JSON.stringify(["https://x/groot"]),
  JSON.stringify(kies([{ links: { "200x200": "//x/klein", "800x800": "//x/groot" }, src: INTERN }])));
check("een gewoon bereikbaar src blijft een terugval",
  JSON.stringify(kies([{ src: "https://images.marktplaats.com/a.jpg" }])) === JSON.stringify(["https://images.marktplaats.com/a.jpg"]));
check("een foto met status ERROR blijft weg", kies([{ status: "ERROR", links: { "1024x1024": CDN } }]).length === 0);

// ── 2. De Vinted-poort, de échte functies in een afgeschermde omgeving ────
function haalFunctie(naam) {
  const m = new RegExp(`(?:async )?function ${naam}\\(`).exec(bron);
  if (!m) return null;
  const e = bron.indexOf("\n}\n", m.index);
  return bron.slice(m.index, e + 2);
}
const checkTekst = haalFunctie("checkVintedOrders");
const telTekst = haalFunctie("vintedArtikelenAantal") || "";
async function draai(scenario) {
  const log = { scrape: 0, vragen: [] };
  const ctx = {
    console: { log() {}, warn() {}, error() {} },
    getServerUrl: async () => "https://x.test",
    getAuthHeaders: async () => ({ Authorization: "Bearer t" }),
    scrapeVintedOrders: async () => { log.scrape++; return []; },
    fetch: async (u) => {
      log.vragen.push(String(u));
      if (scenario === "fout") return { ok: false, status: 500, json: async () => ({}) };
      if (scenario === "stuk") throw new Error("netwerk");
      return { ok: true, status: 200, json: async () => scenario === "heeft" ? [{ platform: "vinted", status: "active" }] : [] };
    },
  };
  vm.createContext(ctx);
  vm.runInContext(telTekst + "\n" + checkTekst + "\nthis.draai = checkVintedOrders;", ctx);
  await ctx.draai();
  return log;
}
(async () => {
  console.log("\nVinted-bestellingen:");
  const nul = await draai("leeg");
  check("klant zonder Vinted-artikelen: geen Vinted-tabblad", nul.scrape === 0, `tabblad geopend: ${nul.scrape}x`);
  const heeft = await draai("heeft");
  check("klant met een Vinted-artikel: kijkt zoals altijd", heeft.scrape === 1, `${heeft.scrape}x`);
  const fout = await draai("fout");
  check("lukt de vraag aan de server niet: kijkt zoals altijd", fout.scrape === 1, `${fout.scrape}x`);
  const stuk = await draai("stuk");
  check("netwerk weg: kijkt zoals altijd", stuk.scrape === 1, `${stuk.scrape}x`);
  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})();
