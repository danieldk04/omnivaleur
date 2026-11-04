// Draait de ECHTE kanaalbestanden van de extensie in Node, met een nagebootste
// browser eromheen, en kijkt of een invulstap omvalt op een waarde die nog niet
// bestaat ("Cannot access 'X' before initialization").
//
// Waarom: zo'n content-script is één grote async functie. Wat ná
// `await getJob()` als const staat, bestaat nog niet als fillForm draait.
// De statische proef in test_vinted_categories.py keek alleen naar vinted.js;
// op 04-11-2026 viel elke Facebook-plaatsing met foto's om op FB_MAX_FOTOS
// (stuk sinds 20-09), en Type/Wattage bij audio op Marktplaats (sinds 27-08).
//
// Gebruik: node tests/extensie-const-na-await-echt-test.js [map-met-content]
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const MAP = process.argv[2] || path.join(__dirname, "..", "extension", "content");

function nep() {
  const f = function () { return p; };
  const p = new Proxy(f, {
    get(_, k) {
      if (k === Symbol.toPrimitive) return () => "";
      if (k === Symbol.iterator) return function* () {};
      if (k === "then") return undefined;
      if (k === "length") return 0;
      return p;
    },
    apply() { return p; },
    construct() { return p; },
  });
  return p;
}

function draai(bestand, item) {
  return new Promise((klaar) => {
    const meldingen = [];
    const CL = new Proxy({}, {
      get(_, k) {
        if (k === "step") return async (naam, fn) => {
          try { await fn(); } catch (e) { meldingen.push(`stap ${naam}: ${e && e.message}`); }
        };
        if (k === "MP_ZONDER_BEDRAG") return [];
        return async () => undefined;
      },
    });
    const job = { id: "j1", serverUrl: "http://x", action: "create", payload: item };
    const ctx = {
      console: { log() {}, warn() {}, error() {}, info() {} },
      setTimeout: (fn, ms) => setTimeout(fn, Math.min(ms || 0, 5)),
      clearTimeout, setInterval: () => 0, clearInterval() {},
      Promise, RegExp, Math, JSON, Date, String, Number, Array, Object, Set, Map, Error,
      document: nep(), location: { href: "https://www.example.com/plaats", hostname: "example.com" },
      navigator: nep(), MutationObserver: function () { return nep(); }, Event: function () {},
      chrome: {
        runtime: {
          lastError: null,
          sendMessage(msg, cb) {
            if (msg.type === "GET_JOB") return cb && cb({ job });
            if (msg.error) meldingen.push(`fout: ${msg.error}`);
            if (cb) cb({});
          },
          onMessage: { addListener() {} },
        },
        storage: { local: { get: async () => ({}), set: async () => {} } },
      },
    };
    ctx.window = ctx; ctx.window.CL = CL; ctx.globalThis = ctx;
    vm.createContext(ctx);
    try { vm.runInContext(fs.readFileSync(path.join(MAP, bestand), "utf8"), ctx); }
    catch (e) { meldingen.push(`laden: ${e.message}`); }
    setTimeout(() => klaar(meldingen), 1500);
  });
}

(async () => {
  const gevallen = [
    ["facebook.js", { title: "Gitaar", price: 100, description: "x", condition: "good", photo_urls: ["https://x/1.jpg"] }],
    ["marktplaats.js", { title: "Speaker", price: 50, description: "x", condition: "good", category: "audio luidsprekers", photo_urls: [] }],
    ["tweedehands.js", { title: "Speaker", price: 50, description: "x", condition: "good", category: "audio luidsprekers", photo_urls: [] }],
  ];
  let fouten = 0;
  for (const [bestand, item] of gevallen) {
    if (!fs.existsSync(path.join(MAP, bestand))) continue;
    const m = await draai(bestand, item);
    const tdz = m.filter((t) => /before initialization/.test(t));
    if (tdz.length) { fouten += tdz.length; console.log(`FOUT ${bestand}: ${tdz.join(" | ")}`); }
    else console.log(`ok   ${bestand}`);
  }
  console.log(fouten ? `${fouten} fout(en)` : "0 fouten");
  process.exit(fouten ? 1 : 0);
})();
