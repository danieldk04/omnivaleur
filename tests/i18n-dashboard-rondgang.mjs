/**
 * Rondgang door het ÉCHTE dashboard in het Nederlands, met nepgegevens.
 *
 * tests/test_i18n_compleet.py kijkt in de broncode; deze rondgang kijkt naar
 * wat er werkelijk op het scherm komt. Hij opent app.html (en de inlogpagina's)
 * met ?taal=nl, laat de server nabootsen met een voorraad, advertenties, een
 * mislukte plaatsing, een wachtrij en een lopende proefperiode, klikt elk
 * scherm langs en opent de belangrijkste vensters. Daarna zoekt hij elke
 * zichtbare tekst die er nog Engels uitziet.
 *
 * Draaien:  node tests/i18n-dashboard-rondgang.mjs [--foto map]
 *   --foto map   bewaart per scherm een schermafbeelding (om zelf te bekijken)
 * Faalt als er ergens Engels blijft staan; de lijst zegt waar.
 */
import { createServer } from "node:http";
import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { join, extname } from "node:path";

const FRONTEND = new URL("../frontend", import.meta.url).pathname;
const fotoMap = process.argv.includes("--foto") ? process.argv[process.argv.indexOf("--foto") + 1] : null;
if (fotoMap) mkdirSync(fotoMap, { recursive: true });

let chromium;
for (const bron of ["playwright", "/opt/node22/lib/node_modules/playwright/index.mjs"]) {
  try { ({ chromium } = await import(bron)); break; } catch (_) { /* volgende */ }
}
if (!chromium) { console.log("OVERGESLAGEN: Playwright niet gevonden"); process.exit(0); }

const server = createServer((req, res) => {
  let pad = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (pad === "/app") pad = "/app.html";
  const bestand = join(FRONTEND, pad);
  if (!bestand.startsWith(FRONTEND) || !existsSync(bestand)) { res.writeHead(404); return res.end("nee"); }
  const type = { ".js": "text/javascript", ".json": "application/json", ".html": "text/html", ".png": "image/png", ".webmanifest": "application/json" }[extname(bestand)] || "text/plain";
  res.writeHead(200, { "Content-Type": type });
  res.end(readFileSync(bestand));
});
await new Promise((r) => server.listen(0, r));
const BASIS = `http://127.0.0.1:${server.address().port}`;

// ── Nepgegevens ─────────────────────────────────────────────────────────
const nu = Date.now();
const dag = 86400000;
const iso = (ms) => new Date(ms).toISOString();
const items = [
  { id: "i1", title: "Levi's 501 jeans maat 32", brand: "Levi's", size: "32", price: 35, purchase_price: 12, condition: "good", category: "heren jeans", gender: "heren", description: "Mooie jeans", photo_urls: ["/logo.png"], created_at: iso(nu - 90 * dag), updated_at: iso(nu - 2 * dag), sku: "REV-1" },
  { id: "i2", title: "Stone Island jacket", brand: "Stone Island", size: "L", price: 180, condition: "new", category: "heren jassen", gender: "heren", description: "", photo_urls: [], created_at: iso(nu - 40 * dag), updated_at: iso(nu - 1 * dag), sku: "IMP-2" },
  { id: "i3", title: "Sneakers", brand: "Nike", size: "43", price: 0, condition: "fair", category: "games playstation 5", description: "Test", photo_urls: ["/logo.png"], created_at: iso(nu - 200 * dag), updated_at: iso(nu - 100 * dag) },
  { id: "i4", title: "Ralph Lauren polo", brand: "Ralph Lauren", size: "M", price: 25, purchase_price: 8, condition: "good", category: "heren polo's", description: "Polo", photo_urls: ["/logo.png"], created_at: iso(nu - 60 * dag), updated_at: iso(nu - 5 * dag) },
];
const listings = [
  { id: "l1", item_id: "i1", platform: "vinted", status: "active", listed_at: iso(nu - 80 * dag), platform_url: "https://www.vinted.nl/items/1" },
  { id: "l2", item_id: "i1", platform: "marktplaats", status: "error", error_message: "The description stayed empty on the form, so nothing was published. Paste the text into the description field yourself and click publish." },
  { id: "l3", item_id: "i4", platform: "vinted", status: "sold", sold_at: iso(nu - 3 * dag), sold_price: 22, listed_at: iso(nu - 50 * dag) },
  { id: "l4", item_id: "i2", platform: "marktplaats", status: "active", listed_at: iso(nu - 35 * dag), last_refreshed_at: iso(nu - 2 * dag) },
  { id: "l5", item_id: "i2", platform: "2dehands", status: "sold_unconfirmed", listed_at: iso(nu - 35 * dag) },
];
const antwoorden = {
  "/api/items/settings": { vinted_groepen: [], relist_auto: true, relist_days: 27, vraag_bij_verdwijnen: true },
  "/api/listings/": listings,
  "/api/jobs/pending": [{ id: "j1", platform: "vinted", action: "create", item_id: "i3" }],
  "/api/platforms/status": { connected: ["ebay"], opnieuw_koppelen: [] },
  "/api/billing/status": { status: "trialing", trial_ends_at: iso(nu + 4 * dag), access_allowed: true, is_owner: false },
  "/api/billing/invoices": [],
  "/api/jobs/extension-status": { online: false, last_seen: iso(nu - 7200000), seconds_ago: 7200, extension_version: "1.0.351", published_extension: "1.0.351", kanalen: {} },
  "/api/jobs/active": { working: [], queued: [{ id: "j1", platform: "vinted", action: "create" }], queued_total: 1, pace: { seconds_per_job: 90 } },
  "/api/jobs/relist-status": [],
  "/api/notifications/": { platforms: [{ platform: "vinted", unread_messages: 2, open_offers: 1, updated_at: iso(nu - 600000) }] },
  "/api/imports/summary": { total: 12, by_status: { imported: 8, linked: 2, pending: 2 }, platforms: ["vinted"] },
  "/api/imports/": [],
  "/api/items/duplicates": { groups: [] },
  "/api/referrals/me": { ready: true, link: "https://omnivaleur.com/r/daniel", code: "daniel", clicks: 3, months_earned: 1, trialing: 1, users: [{ name: "Jo***", joined: "2026-09-01", status: "subscribed" }] },
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "nl-NL" });
await ctx.addInitScript(() => {
  try {
    localStorage.setItem("cl_auth", "1");
    localStorage.setItem("cl_token", "nep");
    localStorage.setItem("cl_email", "daniel@example.com");
    localStorage.setItem("omni_taal", "nl");
  } catch (_) { /* */ }
});
await ctx.route("**/api/**", async (route) => {
  const url = new URL(route.request().url());
  const pad = url.pathname;
  if (pad === "/api/i18n/ontbrekend") return route.fulfill({ status: 204, body: "" });
  if (pad === "/api/items/" && url.searchParams.get("offset") !== "0") return route.fulfill({ json: [] });
  if (pad === "/api/items/") return route.fulfill({ json: items });
  const a = antwoorden[pad];
  return route.fulfill({ json: a !== undefined ? a : {} });
});
// Chart.js komt van jsdelivr. Zonder internet: CHARTJS=/pad/naar/chart.umd.js
const CHART_LOKAAL = process.env.CHARTJS;
await ctx.route(/googletagmanager|calendly|jsdelivr.*chart/, (r) => {
  if (!r.request().url().includes("chart")) return r.abort();
  if (CHART_LOKAAL && existsSync(CHART_LOKAAL)) return r.fulfill({ path: CHART_LOKAAL, contentType: "text/javascript" });
  return r.continue().catch(() => r.abort());
});

const page = await ctx.newPage();
const fouten = [];
page.on("pageerror", (e) => fouten.push(String(e)));
page.on("dialog", (d) => d.dismiss());

// Elke zichtbare tekst die er Engels uitziet en niet van de klant is.
async function engelsOpHetScherm(waar) {
  return page.evaluate((waar) => {
    // Engels: minstens twee typisch Engelse woorden, en meer Engels dan Nederlands.
    const ENG = /\b(the|you|your|to|are|not|could|couldn't|and|of|for|this|was|has|have|with|please|try|again|will|it|from|what|when|failed|click|listings?|here|sold|queued|waiting|nothing|already|by|be|can't|don't|isn't)\b/gi;
    const NL = /\b(de|het|een|en|je|jouw|niet|geen|van|voor|zijn|wordt|naar|bij|deze|dit|dat|die|met|op|er|ook|nog|al|of|is|kan|moet|staat|om|wat)\b/gi;
    const lijktEngels = (t) => { const e = (t.match(ENG) || []).length; return e >= 2 && e > (t.match(NL) || []).length; };
    const uit = [];
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      const t = n.data.replace(/\s+/g, " ").trim();
      if (!/[A-Za-z]{3}/.test(t)) continue;
      const el = n.parentElement;
      if (!el || el.closest("script,style,code,textarea,[translate=no],.notranslate,.item-title,.an-sales-title,.imp-kant-t")) continue;
      if (!el.offsetParent && getComputedStyle(el).position !== "fixed") continue; // onzichtbaar
      if (lijktEngels(t)) uit.push(`${waar}: ${t.slice(0, 160)}`);
      else if (/^(Save|Cancel|Close|Edit|Delete|Loading|Publish|Import|Refresh|Settings|Back|Next|Done|Failed|Saved|Copy|Copied)\b/.test(t)) uit.push(`${waar}: ${t}`);
    }
    for (const el of document.querySelectorAll("[placeholder],[title]")) {
      if (!el.offsetParent || el.closest("[translate=no]")) continue;
      for (const a of ["placeholder", "title"]) {
        const v = el.getAttribute(a);
        if (v && lijktEngels(v)) uit.push(`${waar} [${a}]: ${v.slice(0, 160)}`);
      }
    }
    return uit;
  }, waar);
}

const gevonden = new Set();
const noteer = (lijst) => lijst.forEach((r) => gevonden.add(r));

await page.goto(`${BASIS}/app.html`);
await page.evaluate(() => window.OmniI18n.klaar);
await page.waitForTimeout(2500);

const schermen = ["dashboard", "berichten", "analytics", "items", "stale", "calculator", "platforms",
  "protections", "preferences", "refresh", "import", "prijs", "referral", "help"];
for (const s of schermen) {
  await page.evaluate((s) => { try { showView(s); } catch (e) { console.error(e); } }, s);
  await page.waitForTimeout(700);
  noteer(await engelsOpHetScherm(s));
  if (fotoMap) await page.screenshot({ path: join(fotoMap, `${s}.png`), fullPage: false });
}
// Grafieken tekenen op een canvas: kijk in de labels zelf.
const grafiek = await page.evaluate(() => {
  if (!window.Chart) return null;
  showView("analytics");
  return Object.values(Chart.instances || {}).map((c) => [...(c.data.labels || []), ...c.data.datasets.map((d) => d.label)])
    .flat().filter((x) => typeof x === "string");
});
if (grafiek === null) console.log("(Chart.js niet geladen: grafieklabels niet gecontroleerd; zet CHARTJS=…)");
else for (const l of grafiek) if (/^(Revenue|Profit|Sales|Active|Inactive|Listings)$/i.test(l)) gevonden.add(`grafiek: ${l}`);

// Items: elk tabblad
for (const tab of ["live", "todo", "hidden", "sold", "archived"]) {
  await page.evaluate((t) => { try { showView("items"); setItemsTab(t); } catch (_) { /* */ } }, tab);
  await page.waitForTimeout(400);
  noteer(await engelsOpHetScherm(`items/${tab}`));
}
// Vensters
const vensters = [
  ["nieuw item", "openAddItem()"],
  ["item bewerken", "openEditItem && openEditItem('i1')"],
  ["plaatsen", "openCrosslist('i1')"],
  ["fout bij plaatsen", "showPublishError('i1')"],
];
for (const [naam, code] of vensters) {
  await page.evaluate((c) => { try { eval(c); } catch (e) { console.error(e); } }, code);
  await page.waitForTimeout(600);
  noteer(await engelsOpHetScherm(`venster ${naam}`));
  if (fotoMap) await page.screenshot({ path: join(fotoMap, `venster-${naam.replace(/ /g, "-")}.png`) });
  await page.evaluate(() => { document.querySelectorAll(".modal-overlay.open, .modal.open").forEach((m) => m.classList.remove("open"));
    document.querySelectorAll('[id^="modal-"]').forEach((m) => { if (m.style) m.style.display = "none"; }); });
}
const gemeld = await page.evaluate(() => window.OmniI18n.ontbrekend());
gemeld.forEach((t) => gevonden.add(`gemeld: ${t}`));

// Inlogpagina's
for (const p of ["login.html", "register.html", "forgot-password.html", "reset-password.html"]) {
  const q = await ctx.newPage();
  await q.goto(`${BASIS}/${p}`);
  await q.evaluate(() => window.OmniI18n.klaar);
  await q.waitForTimeout(300);
  const oude = page;
  const lijst = await q.evaluate(() => [...document.body.querySelectorAll("*")]
    .filter((e) => e.children.length === 0 && e.offsetParent && e.textContent.trim()
      && document.documentElement.lang === "nl"
      && (e.textContent.match(/\b(the|you|your|to|account|password|log|in|email|back|create|free|now|a)\b/gi) || []).length >= 2
      && !/\b(je|jouw|het|een|de|terug)\b/i.test(e.textContent))
    .map((e) => e.textContent.trim()));
  lijst.forEach((t) => gevonden.add(`${p}: ${t}`));
  if (fotoMap) await q.screenshot({ path: join(fotoMap, p.replace(".html", ".png")) });
  await q.close();
  void oude;
}

await browser.close();
server.close();
console.log(`${gevonden.size} plek(ken) met Engels:`);
for (const r of gevonden) console.log("  " + r);
if (fouten.length) { console.log("\nJavaScript-fouten:"); fouten.forEach((f) => console.log("  " + f)); }
process.exit(gevonden.size || fouten.length ? 1 : 0);
