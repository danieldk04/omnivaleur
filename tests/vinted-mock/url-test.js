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
console.log(fails ? `\n${fails} FOUT` : "\nalle gevallen goed");
process.exit(fails ? 1 : 0);
