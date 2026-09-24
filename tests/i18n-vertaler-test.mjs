/**
 * De vertaallaag in een echte browser: vertaalt hij wat hij moet vertalen, en
 * blijft hij af van wat van de klant is?
 *
 * Daniel, 24-09-2026: "invulvelden etc. dus niet vertalen, gewoon echt dat het
 * 1000% klopt." Deze proef laadt de échte frontend/i18n.js en het échte
 * frontend/i18n/nl.json in Chromium en controleert:
 *   - Engels blijft de standaard; zonder keuze wordt er niets opgehaald of veranderd
 *   - tekst, knoppen, placeholders en title vertalen, ook wat later verschijnt
 *   - getallen blijven staan, meervoud klopt ("1 dag" / "3 dagen")
 *   - de waarde van een invulveld, een textarea en klanttitels blijven letterlijk,
 *     ook als ze toevallig gelijk zijn aan een woord uit het woordenboek
 *   - een titel tussen aanhalingstekens in een melding wordt niet vertaald
 *   - alert/confirm, datums en onbekende Engelse zinnen (die worden gemeld)
 *
 * Draaien: node tests/i18n-vertaler-test.mjs
 * Nodig: Playwright (npm i -g playwright) of Chrome; zonder slaat hij over.
 */
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { join, extname } from "node:path";

const FRONTEND = new URL("../frontend", import.meta.url).pathname;

let chromium;
for (const bron of ["playwright", "/opt/node22/lib/node_modules/playwright/index.mjs"]) {
  try { ({ chromium } = await import(bron)); break; } catch (_) { /* volgende */ }
}
if (!chromium) {
  console.log("OVERGESLAGEN: Playwright niet gevonden (npm i -g playwright)");
  process.exit(0);
}

const PROEF = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<script src="/i18n.js?v=proef"></script><title>Omnivaleur</title></head><body>
<h1 id="kop">Welcome back</h1>
<p id="spatie">   Save   </p>
<button id="knop" title="Copy link">Copy</button>
<input id="veld" value="Save" placeholder="Search item…">
<input id="knopveld" type="submit" value="Save">
<textarea id="omschrijving">Save</textarea>
<div class="item-title" id="titel">Sneakers</div>
<div translate="no" id="nee">Save</div>
<div id="later"></div>
<div id="data" data-taalkeuze></div>
</body></html>`;

const server = createServer((req, res) => {
  const pad = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (pad === "/proef.html") { res.writeHead(200, { "Content-Type": "text/html" }); return res.end(PROEF); }
  if (pad === "/api/i18n/ontbrekend") { res.writeHead(204); return res.end(); }
  const bestand = join(FRONTEND, pad);
  if (!bestand.startsWith(FRONTEND) || !existsSync(bestand)) { res.writeHead(404); return res.end(); }
  const type = { ".js": "text/javascript", ".json": "application/json" }[extname(bestand)] || "text/plain";
  res.writeHead(200, { "Content-Type": type });
  res.end(readFileSync(bestand));
});
await new Promise((r) => server.listen(0, r));
const BASIS = `http://127.0.0.1:${server.address().port}`;

let mislukt = 0;
const check = (naam, goed, uitleg) => {
  if (goed) return console.log(`  ok   ${naam}`);
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg !== undefined ? " — " + JSON.stringify(uitleg) : ""}`);
};

const browser = await chromium.launch(existsSync("/opt/pw-browsers/chromium")
  ? {} : { channel: "chrome" }).catch(() => chromium.launch({ channel: "chrome" }));

// ── 1. Standaard Engels: niets ophalen, niets veranderen ────────────────
{
  const page = await browser.newPage();
  const gevraagd = [];
  page.on("request", (r) => gevraagd.push(r.url()));
  await page.goto(`${BASIS}/proef.html`);
  await page.waitForTimeout(300);
  check("zonder keuze blijft het Engels", await page.textContent("#kop") === "Welcome back");
  check("zonder keuze wordt het woordenboek niet opgehaald", !gevraagd.some((u) => u.includes("nl.json")), gevraagd);
  check("taalknop staat er ook in het Engels", (await page.textContent("#data")).includes("NL"));
  await page.close();
}

// ── 2. Nederlands ───────────────────────────────────────────────────────
const page = await browser.newPage();
const dialogen = [];
page.on("dialog", async (d) => { dialogen.push(d.message()); await d.dismiss(); });
await page.goto(`${BASIS}/proef.html?taal=nl`);
await page.evaluate(() => window.OmniI18n.klaar);
await page.waitForTimeout(100);

check("kop vertaald", await page.textContent("#kop") === "Welkom terug", await page.textContent("#kop"));
check("witruimte rond de tekst blijft", await page.textContent("#spatie") === "   Opslaan   ", await page.textContent("#spatie"));
check("knoptekst vertaald", await page.textContent("#knop") === "Kopiëren");
check("title vertaald", await page.getAttribute("#knop", "title") === "Link kopiëren");
check("placeholder vertaald", await page.getAttribute("#veld", "placeholder") === "Zoek item…");
check("waarde van een invulveld blijft", await page.inputValue("#veld") === "Save", await page.inputValue("#veld"));
check("knop van type submit wel vertaald", await page.inputValue("#knopveld") === "Opslaan");
check("textarea blijft", await page.inputValue("#omschrijving") === "Save");
check("klanttitel (.item-title) blijft, ook als hij een woordenboekwoord is", await page.textContent("#titel") === "Sneakers");
check("translate=no blijft", await page.textContent("#nee") === "Save");
check("html lang wordt nl", await page.evaluate(() => document.documentElement.lang) === "nl");

// Wat later verschijnt
await page.evaluate(() => {
  document.getElementById("later").innerHTML =
    '<span id="a">12 items total</span><span id="b">3 days left</span><span id="c">1 day left</span>'
    + '<b id="d">Could not save: Invalid token</b><span id="e">"Boots" has no active listings. Continue anyway?</span>'
    + '<span id="f">Saved. Could not save</span><span id="g">Vinted: Could not save</span>'
    + '<span id="h">Something nobody translated here, please report this to us</span>'
    + '<span id="i">Game day special</span>'
    + '<span id="k">€1,234.50</span><span id="l">Total: €22.00 revenue</span>'
    + '<p><b>Leave it empty and nothing changes</b><span id="m"> — the form keeps using your account as before.</span></p>'
    + '<span id="j">Automatic relisting does not apply here: the old one cannot be removed and a relist would create a duplicate.</span>';
});
await page.waitForTimeout(100);
const t = (id) => page.textContent(id);
check("patroon met getal", await t("#a") === "12 items totaal", await t("#a"));
check("meervoud: 3 dagen", await t("#b") === "nog 3 dagen", await t("#b"));
check("enkelvoud: 1 dag", await t("#c") === "nog 1 dag", await t("#c"));
check("ingevulde foutmelding wordt ook vertaald", await t("#d") === "Kon niet opslaan: Ongeldig token", await t("#d"));
check("titel tussen aanhalingstekens blijft letterlijk", (await t("#e")).startsWith('"Boots" heeft geen actieve advertenties.'), await t("#e"));
check("twee zinnen aan elkaar", await t("#f") === "Opgeslagen. Kon niet opslaan", await t("#f"));
check("voorvoegsel blijft staan", await t("#g") === "Vinted: Kon niet opslaan", await t("#g"));
check("geen spatie voor een dubbele punt", await t("#m") === ": het formulier blijft je account gebruiken zoals voorheen.", await t("#m"));
check("bedrag met komma", await t("#k") === "€1.234,50", await t("#k"));
check("bedrag in een zin", (await t("#l")).includes("€22,00"), await t("#l"));
await page.fill("#veld", "22.50");
await page.waitForTimeout(50);
check("bedrag in een invulveld blijft met punt", await page.inputValue("#veld") === "22.50");
check("meervoudspatroon slokt geen andere tekst op", await t("#i") === "Game day special", await t("#i"));
check("kort patroon vertaalt geen los woord midden in een onbekende zin", !(await t("#j")).includes("verwijderd"), await t("#j"));
check("onbekende zin blijft Engels (niet half)", await t("#h") === "Something nobody translated here, please report this to us");
check("onbekende Engelse zin wordt gemeld", (await page.evaluate(() => OmniI18n.ontbrekend())).includes("Something nobody translated here, please report this to us"));

// Tekst die in een bestaand element verandert
await page.evaluate(() => { document.getElementById("knop").textContent = "Copied"; });
await page.waitForTimeout(50);
check("gewijzigde tekst wordt opnieuw vertaald", await t("#knop") === "Gekopieerd", await t("#knop"));

// Dialogen
await page.evaluate(() => alert("Could not save"));
check("alert vertaald", dialogen[0] === "Kon niet opslaan", dialogen[0]);

// Datums
const datum = await page.evaluate(() => new Date(2026, 8, 24).toLocaleDateString("en-GB", { day: "numeric", month: "long" }));
check("datum in het Nederlands", datum === "24 september", datum);

// Taalknop
check("taalknop toont NL als gekozen", await page.getAttribute('#data button[aria-pressed="true"]', "title") === "Nederlands");

await browser.close();
server.close();
console.log(mislukt ? `\n${mislukt} FOUT` : "\nalles goed");
process.exit(mislukt ? 1 : 0);
