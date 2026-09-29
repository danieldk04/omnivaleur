/**
 * Een verkeerd ingevulde inkoopprijs moet vanuit het verkoopoverzicht te
 * corrigeren zijn, en een Nederlands bedrag als "1.360" mag nooit 1,36 worden.
 *
 * WAAROM DIT ER IS (28-09-2026). Johan Kist (Blackbird Guitars) verkocht een
 * Gibson Les Paul voor 1675 en zag 100% winst: de inkoopprijs stond op 1,36
 * (nagemeten in de database). Twee dingen samen:
 *   1. In de verkooptabel onder Analytics had de verkoopprijs een potloodje, de
 *      inkoopprijs niet. Een ingevulde inkoopprijs was daar niet te corrigeren.
 *   2. Chrome leest "1.360" en "1.360,00" in een bedragveld als 1,36 (gemeten in
 *      nl-NL en en-US). Een Nederlander schrijft duizend driehonderdzestig zo.
 *      Het nieuwe potloodje had dezelfde valkuil: corrigeren met "1.360" gaf
 *      opnieuw 1,36.
 *
 * Deze proef opent het ÉCHTE dashboard (frontend/app.html) met een nagebouwde
 * server en doet wat een klant doet: potloodje, bedrag typen, bevestigen; en in
 * het bewerkscherm typen en op opslaan klikken. Hij kijkt wat er naar de server
 * gaat en wat er daarna op het scherm staat.
 *
 * Draaien:    node tests/aankoopprijs-aanpassen-test.mjs
 * Voor-en-na: node tests/aankoopprijs-aanpassen-test.mjs <oude app.html>
 * PLAYWRIGHT=/pad/naar/node_modules/playwright/index.mjs als het nergens standaard staat.
 */
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { join, extname } from "node:path";

const FRONTEND = new URL("../frontend", import.meta.url).pathname;
const APP_BESTAND = process.argv[2] || join(FRONTEND, "app.html");

let chromium;
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

// ── Nepgegevens: Johans Les Paul, verkocht voor 1675, inkoop 1,36 ──
const nu = Date.now();
const dag = 86400000;
const iso = (ms) => new Date(ms).toISOString();
const items = [
  { id: "g1", title: "Gibson Les Paul Studio Session", brand: "Gibson", price: 1675, purchase_price: 1.36, condition: "good",
    category: "gitaren elektrisch", description: "Mooie gitaar", photo_urls: [], created_at: iso(nu - 60 * dag), updated_at: iso(nu - 2 * dag) },
];
const listings = [
  { id: "l1", item_id: "g1", platform: "marktplaats", status: "sold", sold_at: iso(nu - 1 * dag), sold_price: 1675, listed_at: iso(nu - 50 * dag) },
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

const verzonden = [];          // elke schrijfactie: [methode pad, body]
let serverWeigert = false;

// Zonder gedownloade Playwright-browser: de gewone Chrome van deze computer.
const browser = await chromium.launch().catch(() => chromium.launch({ channel: "chrome" }));
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "nl-NL" });
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
    verzonden.push([`PATCH ${pad}`, body]);
    if (serverWeigert) return route.fulfill({ status: 500, json: { detail: "Change was not saved: database unavailable" } });
    // Wat backend/api/items.py update_item doet: meegestuurde velden overschrijven.
    const item = items.find((i) => `/api/items/${i.id}` === pad);
    Object.assign(item, body);
    return route.fulfill({ json: { ...item } });
  }
  if (req.method() === "POST" && pad === "/api/listings/sold-price") {
    const body = JSON.parse(req.postData() || "{}");
    verzonden.push([`POST ${pad}`, body]);
    listings[0].sold_price = body.sold_price;
    return route.fulfill({ json: { sold_price: body.sold_price } });
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

const RIJ = '[...document.querySelectorAll("#an-sales-tbody tr")].find((t) => t.textContent.includes("Les Paul"))';
const rij = () => page.evaluate(`(() => {
  const tr = ${RIJ};
  if (!tr) return null;
  const td = [...tr.querySelectorAll("td")].map((c) => c.textContent.replace(/\\s+/g, " ").trim());
  return { verkoop: td[3], inkoop: td[4], winst: td[5], marge: td[6],
           potlood: !!tr.querySelector('[title="Edit purchase price"]') };
})()`);
const klik = async (titel) => {
  await page.evaluate(`${RIJ}.querySelector('[title="${titel}"]').click()`);
  await page.waitForTimeout(600);
};
const laatste = () => JSON.stringify(verzonden.at(-1)?.[1]);

console.log("\nBeginstand: verkocht voor 1675, inkoopprijs 1,36 (zoals bij Johan)");
let r = await rij();
check("de verkoop staat in de tabel", r !== null);
check("marge toont 100%, zoals Johan zag", r && r.marge === "100%", r && r.marge);
check("bij de inkoopprijs staat een potloodje", r && r.potlood,
  "er is geen manier om een ingevulde inkoopprijs vanuit deze tabel te wijzigen");

if (r && r.potlood) {
  console.log("\nAnnuleren en onzin veranderen niets");
  antwoord = null;
  await klik("Edit purchase price");
  check("het venster toont het huidige bedrag", meldingen.at(-1)?.[0] === "prompt" && meldingen.at(-1)?.[2] === "1.36",
    JSON.stringify(meldingen.at(-1)));
  antwoord = "abc";
  await klik("Edit purchase price");
  check("onzin geeft een melding", meldingen.at(-1)?.[0] === "alert", JSON.stringify(meldingen.at(-1)));
  check("er ging niets naar de server", verzonden.length === 0, JSON.stringify(verzonden));

  console.log("\nCorrigeren met \"1.360\", zoals een Nederlander het schrijft");
  antwoord = "1.360";
  await klik("Edit purchase price");
  check("de server krijgt 1360, niet 1,36", laatste() === '{"purchase_price":1360}', laatste());
  r = await rij();
  check("de rij toont €1360.00", r && r.inkoop.startsWith("€1360.00"), r && r.inkoop);
  check("winst is 1675 min 1360", r && r.winst === "+€315.00", r && r.winst);
  check("marge is 19%", r && r.marge === "19%", r && r.marge);

  console.log("\nAndere schrijfwijzen");
  for (const [getypt, verwacht] of [["1.360,00", 1360], ["1360,50", 1360.5], ["€ 1.250", 1250], ["22,50", 22.5], ["1,36", 1.36]]) {
    antwoord = getypt;
    await klik("Edit purchase price");
    check(`"${getypt}" wordt ${verwacht}`, laatste() === JSON.stringify({ purchase_price: verwacht }), laatste());
  }

  console.log("\nServer weigert: het oude bedrag blijft staan");
  const voor = (await rij()).inkoop;
  serverWeigert = true;
  antwoord = "99";
  await klik("Edit purchase price");
  serverWeigert = false;
  check("hij krijgt de fout te zien", meldingen.at(-1)?.[0] === "alert" && /purchase price/i.test(meldingen.at(-1)?.[1] || ""),
    JSON.stringify(meldingen.at(-1)));
  check("de rij toont nog het oude bedrag", (await rij()).inkoop === voor, (await rij()).inkoop);

  console.log("\nVerkoopprijs: \"1.675\" is 1675, niet 1,68");
  antwoord = "1.675";
  await klik("Edit sold price");
  check("de server krijgt sold_price 1675", laatste() === JSON.stringify({ item_id: "g1", platform: "marktplaats", sold_price: 1675 }), laatste());
  const telVoor = verzonden.length;
  antwoord = "";
  await klik("Edit sold price");
  check("een lege verkoopprijs gaat niet naar de server", verzonden.length === telVoor && meldingen.at(-1)?.[0] === "alert",
    JSON.stringify(verzonden.at(-1)));

  console.log("\nLeegmaken: niet bekend");
  antwoord = "";
  await klik("Edit purchase price");
  check("de server krijgt purchase_price null", laatste() === '{"purchase_price":null}', laatste());
  r = await rij();
  check("de rij vraagt weer om de kosten", r && r.inkoop.includes("Add cost"), r && r.inkoop);
  check("geen winst of marge meer", r && r.winst === "—" && r.marge === "—", r && `${r.winst} ${r.marge}`);
}

// ── Het bewerkscherm: gewone bedragvelden, dus Chrome maakt van "1.360" 1,36 ──
// De nagebouwde server heeft geen extensie; die melding ligt anders over het scherm.
await page.addStyleTag({ content: "#ext-overlay{display:none!important}" });
async function bewerk(getypt) {
  await page.evaluate(() => editItem("g1"));
  await page.waitForTimeout(300);
  await page.click("#f-purchase", { clickCount: 3 });
  await page.keyboard.press("Backspace");
  await page.keyboard.type(getypt);
  const tel = verzonden.length, mel = meldingen.length;
  await page.click("#save-btn");
  await page.waitForTimeout(1200);
  await page.evaluate(() => { try { closeModal("modal-add"); } catch (_) {} });
  return { patch: verzonden.slice(tel), melding: meldingen.slice(mel).map((m) => m[1]).join(" | ") };
}

console.log("\nBewerkscherm: \"1.360\" typen in een lege inkoopprijs");
let b = await bewerk("1.360");
check("niet opgeslagen als 1,36", b.patch.length === 0, JSON.stringify(b.patch));
check("hij krijgt te horen dat de punt een komma is", /1\.360 becomes 1\.36/.test(b.melding), b.melding);

console.log("\nBewerkscherm: \"1.360,00\"");
b = await bewerk("1.360,00");
check("niet opgeslagen", b.patch.length === 0, JSON.stringify(b.patch));

console.log("\nBewerkscherm: \"1360\" gaat gewoon");
b = await bewerk("1360");
check("alleen de inkoopprijs 1360 gaat naar de server",
  b.patch.length === 1 && JSON.stringify(b.patch[0][1]) === '{"purchase_price":1360}', JSON.stringify(b.patch));

console.log("\nBewerkscherm: stond er al 1,36 en typt hij opnieuw \"1.360\"");
items[0].purchase_price = 1.36;
await page.evaluate(() => { state.items.find((i) => i.id === "g1").purchase_price = 1.36; });
b = await bewerk("1.360");
check("hij krijgt de melding, niet stilletjes 'niets gewijzigd'", b.patch.length === 0 && /1\.360 becomes 1\.36/.test(b.melding),
  JSON.stringify(b));

console.log("\nBewerkscherm: een oud bedrag met drie cijfers blokkeert het opslaan van iets anders niet");
items[0].purchase_price = 0.605;
await page.evaluate(() => { state.items.find((i) => i.id === "g1").purchase_price = 0.605; });
await page.evaluate(() => editItem("g1"));
await page.waitForTimeout(300);
await page.fill("#f-title", "Gibson Les Paul Studio Session Dark Purple");
const tel = verzonden.length;
await page.click("#save-btn");
await page.waitForTimeout(1200);
check("de titel gaat gewoon naar de server", JSON.stringify(verzonden.slice(tel).map((v) => v[1])) === '[{"title":"Gibson Les Paul Studio Session Dark Purple"}]',
  JSON.stringify(verzonden.slice(tel)));

check("geen scriptfouten op de pagina", fouten.length === 0, fouten.join(" | "));

await browser.close();
server.close();
console.log(mislukt ? `\n${mislukt} FOUT` : "\nAlles goed");
process.exit(mislukt ? 1 : 0);
