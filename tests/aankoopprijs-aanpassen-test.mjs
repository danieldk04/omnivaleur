/**
 * Een verkeerd ingevulde inkoopprijs moet vanuit het verkoopoverzicht te
 * corrigeren zijn, net als de verkoopprijs.
 *
 * WAAROM DIT ER IS (28-09-2026). Johan Kist (Blackbird Guitars) vulde bij een
 * verkoop per ongeluk een verkeerde inkoopprijs in en zag daarna 100% winst. In
 * de verkooptabel onder Analytics stond bij de verkoopprijs een potloodje, bij
 * de inkoopprijs niet: zolang die leeg was stond er "＋ Add cost", daarna alleen
 * het bedrag als platte tekst. Terugdraaien kon vanaf die plek niet meer.
 *
 * Deze proef opent het ÉCHTE dashboard (frontend/app.html) met een nagebouwde
 * server, gaat naar Analytics en past de inkoopprijs aan zoals een klant dat
 * doet: potloodje, bedrag typen, bevestigen. Hij kijkt wat er naar de server
 * gaat (PATCH /api/items/{id}, alleen purchase_price) en wat er daarna in de rij
 * staat. Ook leegmaken, annuleren, onzin typen en een server die weigert.
 *
 * Draaien:    node tests/aankoopprijs-aanpassen-test.mjs
 * Voor-en-na: node tests/aankoopprijs-aanpassen-test.mjs <oude app.html>
 */
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { join, extname } from "node:path";

const FRONTEND = new URL("../frontend", import.meta.url).pathname;
const APP_BESTAND = process.argv[2] || join(FRONTEND, "app.html");

let chromium;
// PLAYWRIGHT=/pad/naar/node_modules/playwright/index.mjs als het nergens standaard staat.
for (const bron of [process.env.PLAYWRIGHT, "playwright", "/opt/node22/lib/node_modules/playwright/index.mjs"].filter(Boolean)) {
  try { ({ chromium } = await import(bron)); break; } catch (_) { /* volgende */ }
}
if (!chromium) { console.log("OVERGESLAGEN: Playwright niet gevonden"); process.exit(0); }

const server = createServer((req, res) => {
  let pad = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (pad === "/app") pad = "/app.html";
  const bestand = pad === "/app.html" ? APP_BESTAND : join(FRONTEND, pad);
  if ((pad !== "/app.html" && !bestand.startsWith(FRONTEND)) || !existsSync(bestand)) { res.writeHead(404); return res.end("nee"); }
  const type = { ".js": "text/javascript", ".json": "application/json", ".html": "text/html", ".png": "image/png" }[extname(bestand)] || "text/plain";
  res.writeHead(200, { "Content-Type": type });
  res.end(readFileSync(bestand));
});
await new Promise((r) => server.listen(0, r));
const BASIS = `http://127.0.0.1:${server.address().port}`;

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── Nepgegevens: een verkochte gitaar met inkoopprijs 0, zoals bij Johan ──
const nu = Date.now();
const dag = 86400000;
const iso = (ms) => new Date(ms).toISOString();
const items = [
  { id: "g1", title: "Gibson J-45 Standard", brand: "Gibson", price: 250, purchase_price: 0, condition: "good",
    category: "gitaren akoestisch", description: "Mooie gitaar", photo_urls: [], created_at: iso(nu - 60 * dag), updated_at: iso(nu - 2 * dag) },
];
const listings = [
  { id: "l1", item_id: "g1", platform: "marktplaats", status: "sold", sold_at: iso(nu - 2 * dag), sold_price: 250, listed_at: iso(nu - 50 * dag) },
];
const antwoorden = {
  "/api/items/settings": { vinted_groepen: [] },
  "/api/listings/": listings,
  "/api/jobs/pending": [],
  "/api/platforms/status": { connected: [], opnieuw_koppelen: [] },
  "/api/billing/status": { status: "active", access_allowed: true, is_owner: false },
  "/api/jobs/active": { working: [], queued: [], queued_total: 0 },
  "/api/items/duplicates": { groups: [] },
};

const verzonden = [];          // elke PATCH op het item: [pad, body]
let serverWeigert = false;

// Zonder gedownloade Playwright-browser: de gewone Chrome van deze computer.
const browser = await chromium.launch().catch(() => chromium.launch({ channel: "chrome" }));
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
await ctx.addInitScript(() => {
  try {
    localStorage.setItem("cl_auth", "1");
    localStorage.setItem("cl_token", "nep");
    localStorage.setItem("cl_email", "johan@example.com");
    localStorage.setItem("omni_taal", "en");
  } catch (_) { /* */ }
});
await ctx.route("**/api/**", async (route) => {
  const req = route.request();
  const url = new URL(req.url());
  const pad = url.pathname;
  if (req.method() === "PATCH" && pad.startsWith("/api/items/")) {
    const body = JSON.parse(req.postData() || "{}");
    verzonden.push([pad, body]);
    if (serverWeigert) return route.fulfill({ status: 500, json: { detail: "Change was not saved: database unavailable" } });
    // Wat backend/api/items.py update_item doet: meegestuurde velden overschrijven.
    const item = items.find((i) => `/api/items/${i.id}` === pad);
    Object.assign(item, body);
    return route.fulfill({ json: { ...item } });
  }
  if (pad === "/api/i18n/ontbrekend") return route.fulfill({ status: 204, body: "" });
  if (pad === "/api/items/" && url.searchParams.get("offset") !== "0") return route.fulfill({ json: [] });
  if (pad === "/api/items/") return route.fulfill({ json: items });
  const a = antwoorden[pad];
  return route.fulfill({ json: a !== undefined ? a : {} });
});
await ctx.route(/googletagmanager|calendly/, (r) => r.abort());

const page = await ctx.newPage();
const fouten = [];
page.on("pageerror", (e) => fouten.push(String(e)));

// Wat de "klant" in het volgende venster typt; null = Annuleren.
let antwoord = null;
const meldingen = [];
page.on("dialog", async (d) => {
  if (d.type() === "prompt") {
    meldingen.push(["prompt", d.message(), d.defaultValue()]);
    return antwoord === null ? d.dismiss() : d.accept(antwoord);
  }
  meldingen.push([d.type(), d.message()]);
  return d.accept();
});

await page.goto(`${BASIS}/app.html`);
await page.waitForTimeout(2500);
await page.evaluate(() => showView("analytics"));
await page.waitForTimeout(800);

const rij = () => page.evaluate(() => {
  const tr = [...document.querySelectorAll("#an-sales-tbody tr")].find((t) => t.textContent.includes("Gibson J-45"));
  if (!tr) return null;
  const td = [...tr.querySelectorAll("td")].map((c) => c.textContent.replace(/\s+/g, " ").trim());
  return { verkoop: td[3], inkoop: td[4], winst: td[5], marge: td[6],
           potlood: !!tr.querySelector('[title="Edit purchase price"]') };
});
const klikPotlood = async () => {
  await page.evaluate(() => {
    const tr = [...document.querySelectorAll("#an-sales-tbody tr")].find((t) => t.textContent.includes("Gibson J-45"));
    tr.querySelector('[title="Edit purchase price"]').click();
  });
  await page.waitForTimeout(600);
};

console.log("\nBeginstand: verkocht voor 250, inkoopprijs per ongeluk 0");
let r = await rij();
check("de verkoop staat in de tabel", r !== null);
check("marge toont 100%, zoals Johan zag", r && r.marge === "100%", r && r.marge);
check("bij de inkoopprijs staat een potloodje", r && r.potlood,
  "er is geen manier om een ingevulde inkoopprijs vanuit deze tabel te wijzigen");

if (r && r.potlood) {
  console.log("\nAnnuleren verandert niets");
  antwoord = null;
  await klikPotlood();
  check("het venster vraagt wat hij betaalde en toont het huidige bedrag",
    meldingen.at(-1)?.[0] === "prompt" && meldingen.at(-1)?.[2] === "0.00", JSON.stringify(meldingen.at(-1)));
  check("er ging niets naar de server", verzonden.length === 0, JSON.stringify(verzonden));

  console.log("\nOnzin typen wordt geweigerd");
  antwoord = "abc";
  await klikPotlood();
  check("hij krijgt te horen dat het geen bedrag is", meldingen.at(-1)?.[0] === "alert", JSON.stringify(meldingen.at(-1)));
  check("er ging niets naar de server", verzonden.length === 0, JSON.stringify(verzonden));

  console.log("\nDe echte inkoopprijs invullen: 120,50 (met komma)");
  antwoord = "120,50";
  await klikPotlood();
  check("alleen de inkoopprijs gaat naar de server",
    verzonden.length === 1 && verzonden[0][0] === "/api/items/g1" && JSON.stringify(verzonden[0][1]) === '{"purchase_price":120.5}',
    JSON.stringify(verzonden));
  r = await rij();
  check("de rij toont de nieuwe inkoopprijs", r && r.inkoop.startsWith("€120.50"), r && r.inkoop);
  check("winst is 250 min 120,50", r && r.winst === "+€129.50", r && r.winst);
  check("marge is 52%", r && r.marge === "52%", r && r.marge);
  check("de verkoopprijs bleef staan", r && r.verkoop.startsWith("€250.00"), r && r.verkoop);

  console.log("\nServer weigert: het oude bedrag blijft staan");
  serverWeigert = true;
  antwoord = "99";
  await klikPotlood();
  serverWeigert = false;
  check("hij krijgt de fout te zien", meldingen.at(-1)?.[0] === "alert" && /purchase price/i.test(meldingen.at(-1)?.[1] || ""),
    JSON.stringify(meldingen.at(-1)));
  r = await rij();
  check("de rij toont nog 120,50, niet het geweigerde bedrag", r && r.inkoop.startsWith("€120.50"), r && r.inkoop);

  console.log("\nLeegmaken: niet bekend");
  antwoord = "";
  await klikPotlood();
  check("de server krijgt purchase_price null", JSON.stringify(verzonden.at(-1)?.[1]) === '{"purchase_price":null}',
    JSON.stringify(verzonden.at(-1)));
  r = await rij();
  check("de rij vraagt weer om de kosten", r && r.inkoop.includes("Add cost"), r && r.inkoop);
  check("geen winst of marge meer", r && r.winst === "—" && r.marge === "—", r && `${r.winst} ${r.marge}`);
}

check("geen scriptfouten op de pagina", fouten.length === 0, fouten.join(" | "));

await browser.close();
server.close();
console.log(mislukt ? `\n${mislukt} FOUT` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
