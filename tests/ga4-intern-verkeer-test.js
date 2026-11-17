/** GA4 intern verkeer (17-11-2026): ?intern=1 zet traffic_type=internal voor dat apparaat, ?intern=0 haalt het weg, gewone bezoekers blijven ongemoeid. node tests/ga4-intern-verkeer-test.js */
const fs = require("fs"), path = require("path");
let mislukt = 0;
const ok = (n, v, k) => { if (v) return console.log("  ✓ " + n); mislukt++; console.log("  ✗ " + n + " - " + JSON.stringify(k)); };
const html = fs.readFileSync(path.join(__dirname, "..", "frontend", "index.html"), "utf8");
const regel = html.split("\n").find((l) => l.includes("gtag('config', 'G-VJ5BVD3GCH'"));
const expr = regel.trim().replace(/^gtag\('config', 'G-VJ5BVD3GCH', /, "").replace(/\);$/, "");
const draai = (zoek, opslag) => new Function("location", "localStorage", "return " + expr)({ search: zoek },
  { getItem: (k) => (k in opslag ? opslag[k] : null), setItem: (k, v) => { opslag[k] = v; }, removeItem: (k) => { delete opslag[k]; } });
let o = {};
ok("gewone bezoeker: geen traffic_type", JSON.stringify(draai("", o)) === "{}");
ok("?intern=1 markeert intern", draai("?intern=1", o).traffic_type === "internal");
ok("en blijft zo zonder parameter", draai("", o).traffic_type === "internal");
ok("?intern=0 haalt het weg", JSON.stringify(draai("?intern=0", o)) === "{}" && !("ov_intern" in o));
let kapot = { getItem() { throw new Error("geblokkeerd"); }, setItem() {}, removeItem() {} };
ok("opslag geblokkeerd: geen fout, gewoon meetellen", JSON.stringify(new Function("location", "localStorage", "return " + expr)({ search: "" }, kapot)) === "{}");
const alle = require("child_process").execSync("grep -rl \"gtag('config', 'G-VJ5BVD3GCH');\" frontend --include=*.html | grep -v ' 2' || true").toString().trim();
ok("geen pagina meer met de oude config", alle === "", alle);
console.log(mislukt ? mislukt + " mislukt" : "Alles ok"); process.exit(mislukt ? 1 : 0);
