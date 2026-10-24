// Draait de ECHTE marktplaats.js / tweedehands.js en shared.js van main op marktplaats.nl/plaats of
// 2dehands.be/plaats, zonder te plaatsen. Model: vinted_loader.js.
// Gebruik: open de plaatsen-pagina in Daniels Chrome, zet
//   window.__PROEF = { site: "marktplaats" | "2dehands", item: {...payload...}, ref: "main" };
// en voer dit bestand uit. Wacht 60 s, lees dan
//   ({done: __DONE, block: __BLOCK, log: __LOG.filter(x => /stap|EINDE|FOUT/.test(x))})
// Een stap "NIET gelukt" (size, color, brand, condition, price) of een FOUT bij beschrijving/foto's = afwijking.
// Veiligheid: de plaatsklik wordt een throw en elke niet-GET fetch/XHR buiten foto-upload wordt geblokkeerd.
// Sluit daarna het tabblad; nooit opslaan, nooit plaatsen.
(async () => {
  window.__LOG = []; window.__T0 = Date.now(); window.__BLOCK = []; window.__DONE = null;
  const P = window.__PROEF, ref = P.ref || "main";
  const RAW = "https://raw.githubusercontent.com/danieldk04/omnivaleur/" + ref + "/";
  const get = async (p) => (await fetch(RAW + p + "?x=" + Date.now())).text();
  const siteFile = P.site === "2dehands" ? "tweedehands.js" : "marktplaats.js";
  let [shared, site] = await Promise.all([get("extension/content/shared.js"), get("extension/content/" + siteFile)]);
  const marker = 'btn.click();\n    clog("plaatsen: op de knop geklikt';
  if (!shared.includes(marker)) throw new Error("plaatsklik-marker weg: NIET draaien");
  shared = shared.replace(marker, 'throw new Error("PROEF: niet geklikt");\n    clog("plaatsen: op de knop geklikt');
  const ok = /image|upload|photo|media|track|analytics|collect|log|metrics|rum|suggest|categor|predict|price|attribute/i;
  const bad = (m, u) => m && m.toUpperCase() !== "GET" && m.toUpperCase() !== "HEAD" && !ok.test(u);
  const xo = XMLHttpRequest.prototype.open, xs = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u, ...r) { this.__m = m; this.__u = String(u); return xo.call(this, m, u, ...r); };
  XMLHttpRequest.prototype.send = function (b) {
    if (bad(this.__m, this.__u)) { __BLOCK.push(this.__m + " " + this.__u); throw new Error("PROEF-slot"); }
    return xs.call(this, b);
  };
  const of = window.fetch;
  window.fetch = function (u, o) {
    const m = (o && o.method) || (u && u.method) || "GET", url = String(u && u.url || u);
    if (bad(m, url)) { __BLOCK.push(m + " " + url); return Promise.reject(new Error("PROEF-slot")); }
    return of.call(this, u, o);
  };
  const lg = (t) => __LOG.push(((Date.now() - __T0) / 1000).toFixed(1) + " " + t);
  const cb = (f, a) => setTimeout(() => f && f(a), 0);
  const stub = { runtime: { lastError: undefined, id: "proef", getManifest: () => ({ version: "proef" }), getURL: (p) => p, onMessage: { addListener() {} },
    sendMessage(m, f) {
      if (m.type === "GET_JOB") return cb(f, { job: { id: "proef-1", serverUrl: "https://omnivaleur.com", action: "create", payload: P.item } });
      if (m.type === "LOG") { lg(m.text); return cb(f, true); }
      if (m.type === "OV_WEKKER") return setTimeout(() => f && f(true), Math.min(m.ms || 0, 25000));
      if (m.type === "JOB_DONE" || m.type === "JOB_ERROR") { __DONE = { t: m.type, e: m.error }; lg("EINDE " + m.type + " " + (m.error || "")); return cb(f, true); }
      if (m.type === "HEEFT_DEBUGGER") return cb(f, false);
      if (m.type === "ECHTE_DESC_LENGTE") return cb(f, 0);
      return cb(f, {});
    } },
    storage: { sync: { get: (k, f) => cb(f, {}) }, local: { get: (k, f) => cb(f, {}), set: (o, f) => cb(f) } },
    scripting: { executeScript: () => Promise.reject(new Error("geen")) } };
  Object.defineProperty(window, "chrome", { value: stub, configurable: true, writable: true });
  (0, eval)(shared);
  setTimeout(() => { try { (0, eval)(site); } catch (e) { lg("site-script gooide " + e); } }, 10);
})();
