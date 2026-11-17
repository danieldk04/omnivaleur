/** GA4 verkoper_intentie op / en /nl: klik op aanmelden, inloggen of prijzen telt, een ander linkje niet, en maar één keer. node tests/verkoper-intentie-test.js */
const fs = require("fs"), path = require("path");
let mislukt = 0;
const ok = (n, v, k) => { if (v) return console.log("  ✓ " + n); mislukt++; console.log("  ✗ " + n + " - " + JSON.stringify(k)); };
for (const bestand of ["index.html", "nl.html"]) {
  console.log(bestand);
  const html = fs.readFileSync(path.join(__dirname, "..", "frontend", bestand), "utf8");
  const blok = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).find((t) => t.includes("verkoper_intentie"));
  ok("snippet staat in de pagina", !!blok);
  const events = [], luisteraars = {};
  const gtag = (...a) => events.push(a);
  const window = { dataLayer: [] };
  const klik = (href) => luisteraars.click && luisteraars.click({ target: { closest: () => (href == null ? null : { getAttribute: () => href }) } });
  new Function("window", "document", "addEventListener", "setTimeout", "gtag", blok.replace("function gtag(){dataLayer.push(arguments);}", "").replace("window.dataLayer = window.dataLayer || [];", ""))(
    window, { visibilityState: "visible" }, (e, f) => { luisteraars[e] = f; }, () => {}, gtag);
  klik("/blog"); ok("gewoon linkje: geen event", !events.some((e) => e[1] === "verkoper_intentie"));
  klik("/register"); const e1 = events.find((e) => e[1] === "verkoper_intentie");
  ok("aanmelden telt", e1 && e1[2].doel === "aanmelden", e1);
  klik("/login"); ok("maar één keer", events.filter((e) => e[1] === "verkoper_intentie").length === 1);
}
console.log(mislukt ? mislukt + " mislukt" : "Alles ok"); process.exit(mislukt ? 1 : 0);
