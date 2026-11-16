/**
 * Snelle Marktplaats-scan (extensie 1.0.424, Daniel 16-11-2026): drie advertenties tegelijk,
 * de eerste 20 vroeg naar de server, merk en maat uit de pagina of uit "Heren M" in de titel.
 * Draait de ECHTE lus uit extension/background.js met nagebouwde browserfuncties eromheen.
 *
 * Draaien:  node tests/extension-snelle-scan-test.js
 */
const fs = require("fs");
const path = require("path");
const bron = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const a = bron.indexOf("    const VERRIJK_BUDGET_MS =");
const b = bron.indexOf("    } catch (e) {\n      // Komt er hier tóch iets doorheen, leg dan vast hoe ver we kwamen.");
if (a < 0 || b < 0) { console.log("lus niet gevonden"); process.exit(1); }
const lus = bron.slice(a, b);

let mislukt = 0;
const ok = (naam, v, kreeg) => { if (v) return console.log(`  ✓ ${naam}`); mislukt++; console.log(`  ✗ ${naam} - kreeg ${JSON.stringify(kreeg)}`); };

async function draai(aantal, opties = {}) {
  const items = Array.from({ length: aantal }, (_, i) => ({
    platform_listing_url: `https://www.marktplaats.nl/v/${i}`, title: i % 2 ? `Vest - Heren M - Goed (${i})` : `Jas ${i}`, brand: "", size: "",
  }));
  const pogingen = {};
  let tegelijk = 0, hoogst = 0, partieel = null, voortgang = [];
  const execInTab = async (_tab, _fn, [url]) => {
    tegelijk++; hoogst = Math.max(hoogst, tegelijk);
    await new Promise((r) => setTimeout(r, 5));
    tegelijk--;
    const i = Number(url.split("/").pop());
    pogingen[i] = (pogingen[i] || 0) + 1;
    // elke vierde advertentie geeft de eerste keer een lege tekst (zoals gemeten bij 85 van 257)
    const leeg = opties.leegEerste && i % 4 === 0 && pogingen[i] === 1;
    return { description: leeg ? "" : "tekst", photo_urls: ["a.jpg"], condition: "", brand: i % 3 === 0 ? "Ralph Lauren" : "", size: "" };
  };
  const fetchStub = async (url, o) => { if (/scan-deel/.test(url)) partieel = JSON.parse(o.body).listings; return { ok: !opties.deelMislukt }; };
  // de lus eindigt midden in een try; sluit hem af voor de test
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const gebouwd = new AsyncFunction("items", "execInTab", "fetch", "reportProgress", "getAuthHeaders", "sleep", "tabId", "serverUrl", "job", "total", "startedAt",
    `let enriched = 0; const result = { meta: {} }; const teVerrijken = items;\n${lus}\n } catch (e) { throw e; }\n return { enriched, afgekaptOpTijd, meta: result.meta };`);
  const uit = await gebouwd(items, execInTab, fetchStub, async (_s, _j, p) => { voortgang.push(p); }, async () => ({}), () => new Promise((r) => setTimeout(r, 1)), 1, "http://x", { id: "j" }, aantal, Date.now());
  return { items, uit, hoogst, partieel, voortgang, pogingen };
}

(async () => {
  console.log("1. Drie tegelijk en eerste batch");
  let r = await draai(257);
  ok("alle 257 verrijkt", r.uit.enriched === 257, r.uit);
  ok("nooit meer dan drie tegelijk", r.hoogst <= 3 && r.hoogst >= 2, r.hoogst);
  ok("eerste batch van 20 (tot 21 door groepen van 3) vooruit gestuurd", r.partieel && r.partieel.length >= 20 && r.partieel.length <= 22, r.partieel && r.partieel.length);
  ok("de batch bevat de EERSTE advertenties", r.partieel && r.partieel[0].platform_listing_url.endsWith("/0"), r.partieel && r.partieel[0]);
  ok("voortgang meldt deel_klaar", r.voortgang.some((p) => p.deel_klaar >= 20), r.voortgang.slice(-1));
  console.log("2. Merk en maat");
  ok("merk uit de pagina", r.items[0].brand === "Ralph Lauren");
  ok("maat uit 'Heren M' in de titel", r.items[1].size === "M", r.items[1]);
  ok("geen maat verzonnen als de titel er geen heeft", r.items[2].size === "", r.items[2]);
  console.log("2b. Tweede ronde voor lege omschrijvingen");
  r = await draai(100, { leegEerste: true });
  ok("alle 100 hebben na afloop een omschrijving", r.items.every((x) => x.description === "tekst"), r.items.filter((x) => !x.description).length);
  ok("alleen de lege zijn opnieuw gelezen", r.pogingen[0] === 2 && r.pogingen[1] === 1, [r.pogingen[0], r.pogingen[1]]);
  console.log("3. Weinig advertenties en mislukte batch");
  r = await draai(5);
  ok("5 advertenties: batch na alle 5", r.partieel && r.partieel.length === 5 && r.uit.enriched === 5, r.partieel && r.partieel.length);
  r = await draai(40, { deelMislukt: true });
  ok("batch mislukt: scan loopt gewoon door", r.uit.enriched === 40, r.uit);
  console.log(mislukt ? `\n${mislukt} mislukt` : "\nAlles ok");
  process.exit(mislukt ? 1 : 0);
})().catch((e) => { console.log("FOUT", e); process.exit(1); });
