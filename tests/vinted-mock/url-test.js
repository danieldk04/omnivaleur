// Tests the SHIPPED manual-publish detection: the matcher block is sliced out of
// background.js so this can never test a stale copy.
const fs = require("fs");
const bg = fs.readFileSync(require("path").resolve(__dirname, "../../extension/background.js"), "utf8");

const start = bg.indexOf("  let m;\n  if (meta.platform === \"vinted\")");
const end = bg.indexOf("  if (!m) return;", start);
if (start < 0 || end < 0) { console.error("matcher block not found"); process.exit(1); }
const block = bg.slice(start, end);

const match = (url, awaitingManualFinish) => {
  const meta = { platform: "vinted", awaitingManualFinish };
  // eslint-disable-next-line no-new-func
  const fn = new Function("url", "meta", block + "\n return m && m[1];");
  return fn(url, meta);
};

const cases = [
  // url,                                                       auto,    handed over
  ["https://www.vinted.nl/items/new",                           null,    null],
  ["https://www.vinted.nl/items/6789012345/edit",               null,    null],
  ["https://www.vinted.nl/items/6789012345/edit?step=2",        null,    null],
  ["https://www.vinted.nl/items/6789012345",                    null,    "6789012345"],
  ["https://www.vinted.nl/items/6789012345?ref=list",           null,    "6789012345"],
  ["https://www.vinted.nl/items/6789012345-khaki-zip-vest",     "6789012345", "6789012345"],
  ["https://www.vinted.nl/member/123/items",                    null,    null],
  ["https://www.vinted.nl/catalog?search_text=vest",            null,    null],
];

let fails = 0;
for (const [url, wantAuto, wantManual] of cases) {
  const gotAuto = match(url, false) || null;
  const gotManual = match(url, true) || null;
  const ok = gotAuto === wantAuto && gotManual === wantManual;
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${url}\n      tijdens invullen: ${gotAuto} (verwacht ${wantAuto})`
    + `   | na overdracht: ${gotManual} (verwacht ${wantManual})`);
}

// ── Na een handmatige Upload landt Vinted op de KAST ────────────────────────
// Waargenomen 31-08-2026: https://www.vinted.com/member/35817973. Daar staat
// geen advertentie-id in, dus de matcher hierboven vindt niets. De garderobe
// weet het wel. Deze proef draait het verscheepte blok, niet een kopie.
const mStart = bg.indexOf("  // NA EEN HANDMATIGE UPLOAD LANDT VINTED OP DE KAST");
const mEnd = bg.indexOf("  let m;\n  if (meta.platform === \"vinted\")", mStart);
if (mStart < 0 || mEnd < 0) { console.error("kastblok niet gevonden"); process.exit(1); }
const kastBlok = bg.slice(mStart, mEnd);

async function kast(url, meta, gevonden) {
  const gedaan = { afgemeld: null, gewist: null, bewakerUit: false };
  const fn = new Function(
    "url", "meta", "key", "tabId", "bgVindVintedAdvertentie", "clearJobWatchdog",
    "chrome", "finaliseJob", "console", "gedaan",
    "return (async () => {" + kastBlok + "return 'DOORGELOPEN'; })();");
  const uit = await fn(
    url, meta, "jobtab_7", 7,
    async () => gevonden,
    () => { gedaan.bewakerUit = true; },
    { storage: { local: { remove: (k) => { gedaan.gewist = k; } } } },
    async (_s, jobId, status, data) => { gedaan.afgemeld = { jobId, status, ...data }; },
    { log: () => {} },
    gedaan);
  return { uit, ...gedaan };
}

const advertentie = { id: "9998887776", url: "https://www.vinted.com/items/9998887776" };
const metaKlaar = () => ({ platform: "vinted", awaitingManualFinish: true, jobId: 42,
                           serverUrl: "https://omnivaleur.com", payload: { title: "Grey Suitsupply Shirt" } });

(async () => {
  let stuk = 0;
  const zeg = (ok, naam) => { console.log(`${ok ? "PASS" : "FAIL"}  ${naam}`); if (!ok) stuk++; };

  let r = await kast("https://www.vinted.com/member/35817973", metaKlaar(), advertentie);
  zeg(r.afgemeld && r.afgemeld.status === "complete"
      && r.afgemeld.platform_listing_id === "9998887776" && r.uit !== "DOORGELOPEN",
      "kastpagina na handmatig plaatsen: advertentie gekoppeld en afgemeld");

  r = await kast("https://www.vinted.com/member/35817973", metaKlaar(), null);
  zeg(!r.afgemeld && !r.gewist && r.uit !== "DOORGELOPEN",
      "niets te vinden in de garderobe: er wordt niets gekoppeld");

  r = await kast("https://www.vinted.com/member/35817973",
                 { ...metaKlaar(), awaitingManualFinish: false }, advertentie);
  zeg(!r.afgemeld && r.uit === "DOORGELOPEN",
      "terwijl de extensie zelf nog bezig is verandert er niets");

  r = await kast("https://www.vinted.com/items/9998887776-grey-shirt", metaKlaar(), advertentie);
  zeg(!r.afgemeld && r.uit === "DOORGELOPEN",
      "een gewone advertentiepagina gaat nog steeds langs de matcher");

  const totaal = stuk + fails;
  console.log(totaal ? `\n${totaal} FOUT` : "\nalle gevallen goed");
  process.exit(totaal ? 1 : 0);
})();
