// Draait de ECHTE vinted.js en shared.js van main op vinted.nl/items/new, zonder te plaatsen.
// Gebruik: open vinted.nl/items/new in Daniels Chrome (Claude in Chrome), zet eerst
//   window.__PROEF = { item: {...payload...}, ref: "main" };
// en voer dit bestand uit via javascript_tool. Wacht 60 s, lees dan
//   ({done: __DONE, log: __LOG.filter(x => /stap|EINDE/.test(x))})
// Een stap "NIET gelukt" bij size, category, brand, colour of price = Vinted heeft iets veranderd.
// "description" in de eindfout is een artefact van deze proef (geen echte achtergrond), negeren.
// Veiligheid: de plaatsklik wordt vervangen door een throw en elk schrijfverzoek buiten foto's,
// attributen en verzendschatting wordt geblokkeerd. Open daarna een NIEUW tabblad voor de volgende proef
// en sluit dit tabblad (er staat een half formulier open; nooit opslaan).
(async () => {
  window.__LOG = []; window.__T0 = Date.now(); window.__BLOCK = []; window.__DONE = null;
  const RAW = "https://raw.githubusercontent.com/danieldk04/omnivaleur/" + (window.__PROEF.ref || "main") + "/";
  const get = async (p) => (await fetch(RAW + p + "?x=" + Date.now())).text();
  let [shared, vinted, prijs] = await Promise.all([get("extension/content/shared.js"), get("extension/content/vinted.js"), get("extension/content/vinted_prijs_main.js")]);
  const nl = (await (await fetch(RAW + "tests/fixtures/vinted_catalogus_nl_15-10-2026.json")).json()).boom;
  const en = (await (await fetch(RAW + "tests/fixtures/vinted_catalogus_en_15-10-2026.json")).json()).boom;
  const marker = 'btn.click();\n    clog("plaatsen: op de knop geklikt';
  if (!shared.includes(marker)) throw new Error("plaatsklik-marker weg: NIET draaien");
  shared = shared.replace(marker, 'throw new Error("PROEF: niet geklikt");\n    clog("plaatsen: op de knop geklikt');
  const okPost = /\/api\/v2\/(photos|item_upload\/(attributes|suggestions|colors|brands|catalogs))|shipping-estimation|missing_item_photo/;
  const xo = XMLHttpRequest.prototype.open, xs = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u, ...r) { this.__m = m; this.__u = String(u); return xo.call(this, m, u, ...r); };
  XMLHttpRequest.prototype.send = function (b) {
    if (this.__m && this.__m.toUpperCase() !== "GET" && !okPost.test(this.__u) && !/tracking|braze|relay|logs-ingress|consume|dd\.vinted|price_suggestions/.test(this.__u)) { __BLOCK.push(this.__m + " " + this.__u); throw new Error("PROEF-slot"); }
    return xs.call(this, b);
  };
  const lg = (t) => __LOG.push(((Date.now() - __T0) / 1000).toFixed(1) + " " + t);
  const cb = (f, a) => setTimeout(() => f && f(a), 0);
  const stub = { runtime: { lastError: undefined, id: "proef", getManifest: () => ({ version: "proef" }), getURL: (p) => p, onMessage: { addListener() {} },
    sendMessage(m, f) {
      if (m.type === "GET_JOB") return cb(f, { job: { id: "proef-1", serverUrl: "https://omnivaleur.com", action: "create", payload: window.__PROEF.item } });
      if (m.type === "VINTED_CATALOGUS") return cb(f, m.taal === "en" ? en : nl);
      if (m.type === "LOG") { lg(m.text); return cb(f, true); }
      if (m.type === "OV_WEKKER") return setTimeout(() => f && f(true), Math.min(m.ms || 0, 25000));
      if (m.type === "JOB_DONE" || m.type === "JOB_ERROR") { __DONE = { t: m.type, e: m.error }; lg("EINDE " + m.type); return cb(f, true); }
      if (m.type === "HEEFT_DEBUGGER") return cb(f, false);
      if (m.type === "ECHTE_DESC_LENGTE") return cb(f, 0);
      return cb(f, {});
    } },
    storage: { sync: { get: (k, f) => cb(f, {}) }, local: { get: (k, f) => cb(f, {}), set: (o, f) => cb(f) } },
    scripting: { executeScript: () => Promise.reject(new Error("geen")) } };
  Object.defineProperty(window, "chrome", { value: stub, configurable: true, writable: true });
  (0, eval)(prijs); (0, eval)(shared);
  setTimeout(() => { try { (0, eval)(vinted); } catch (e) { lg("vinted.js gooide " + e); } }, 10);
})();
