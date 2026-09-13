/**
 * "Als ik een tijdje niks doe word ik uitgelogd." (Egbert Brouwer en Daniel
 * zelf, 13-09-2026.)
 *
 * Er zit geen klok op die uitlogt. De vernieuwsleutel van Supabase mag precies
 * één keer gebruikt worden, en er zijn twee partijen die hem gebruiken: het
 * dashboard en de extensie. Zodra de extensie hem doordraait, draagt het
 * dashboard een dode sleutel, en dat blijkt pas als het toegangsbewijs na een
 * uur verloopt — dan vliegt de verkoper eruit.
 *
 * Deze proef draait de echte sessiecode uit frontend/app.html en de echte
 * refreshAccessToken uit extension/background.js.
 *
 * Draaien: node tests/sessie-blijft-staan-test.js
 *          node tests/sessie-blijft-staan-test.js --oud   (moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "d491658f";
const oud = process.argv.includes("--oud");

function bron(bestand) {
  return oud
    ? execSync(`git show ${VOOR_DE_REPARATIE}:${bestand}`, { cwd: WORTEL, maxBuffer: 1 << 24 }).toString()
    : fs.readFileSync(path.join(WORTEL, bestand), "utf8");
}

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// ── Het stuk sessiecode uit app.html, letterlijk zoals het in de pagina staat ──
function sessieCode() {
  const html = bron("frontend/app.html");
  const begin = oud ? html.indexOf("let _tokenVernieuwing = null;")
                    : html.indexOf("let _tokenVernieuwing = null;");
  const eind = html.indexOf("// Safely turn a response into JSON.");
  if (begin < 0 || eind < 0 || eind < begin) throw new Error("sessieblok niet gevonden in app.html");
  return html.slice(begin, eind);
}

// Een JWT met een echte vervaltijd erin; alleen het middenstuk wordt gelezen.
function bewijs(geldigSeconden) {
  const lading = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + geldigSeconden }))
    .toString("base64").replace(/=+$/, "");
  return `kop.${lading}.handtekening`;
}

function dashboard({ sleutel, token, antwoord }) {
  const opslag = { cl_token: token, cl_refresh: sleutel, cl_auth: "1", cl_email: "x@y.nl" };
  const staat = { gewist: false, naarLogin: false, verzoeken: [], intervallen: 0 };
  const sandbox = {
    console: { log() {}, warn() {}, error() {} },
    atob: (s) => Buffer.from(s, "base64").toString("binary"),
    JSON, Math, Date, Promise, setTimeout, clearTimeout,
    setInterval: () => { staat.intervallen++; return 0; },
    API: "https://omnivaleur.com",
    TOKEN: token,
    EXT_SOURCE: "omnivaleur-extension",
    loadBillingStatus() {},
    SESSIE: {
      lees: (k) => (k in opslag ? opslag[k] : null),
      zet: (k, v) => { opslag[k] = v; },
      wis: (k) => { delete opslag[k]; },
      wisAlles() { staat.gewist = true; for (const k of Object.keys(opslag)) delete opslag[k]; },
    },
    location: { set href(v) { staat.naarLogin = true; }, get href() { return ""; } },
    document: { addEventListener() {}, hidden: false },
    window: { addEventListener() {} },
    fetch: async (url, opts) => {
      const lading = opts && opts.body ? JSON.parse(opts.body) : {};
      staat.verzoeken.push({ url: String(url), refresh: lading.refresh_token });
      return antwoord(String(url), lading, opslag);
    },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(sessieCode(), sandbox, { filename: "app.html-sessie" });
  return { sandbox, staat, opslag };
}

const OK = (nieuweSleutel) => ({
  ok: true, status: 200,
  json: async () => ({ ok: true, access_token: bewijs(3600), refresh_token: nieuweSleutel }),
});
const FOUT = (status) => ({ ok: false, status, json: async () => ({ detail: "nee" }) });

(async () => {
  console.log(oud ? "VÓÓR de reparatie (moet falen)" : "Na de reparatie");

  // 1. De extensie draait de sleutel door terwijl de pagina hem net gebruikt.
  console.log("\nDe extensie was ons net voor met dezelfde sleutel:");
  {
    let eerste = true;
    const { sandbox, staat, opslag } = dashboard({
      sleutel: "R0", token: bewijs(-60),
      antwoord: (url, lading, opslag) => {
        if (lading.refresh_token === "R0" && eerste) {
          eerste = false;
          opslag.cl_refresh = "R1";      // de extensie schrijft de verse terug
          return FOUT(401);
        }
        if (lading.refresh_token === "R1") return OK("R2");
        return FOUT(401);
      },
    });
    const res = await sandbox.apiFetch("https://omnivaleur.com/api/items");
    check("de verkoper blijft ingelogd", !staat.gewist && !staat.naarLogin,
          "de sessie werd gewist en er werd naar het inlogscherm gestuurd");
    check("en er is met de nieuwe sleutel vernieuwd", opslag.cl_refresh === "R2",
          `cl_refresh is ${opslag.cl_refresh}`);
  }

  // 2. De server heeft een hik (503). Dat is geen reden om iemand uit te loggen.
  console.log("\nDe server geeft 503 tijdens een deploy:");
  {
    const { sandbox, staat, opslag } = dashboard({
      sleutel: "R0", token: bewijs(-60),
      antwoord: (url) => (url.includes("/auth/refresh") ? FOUT(503) : FOUT(401)),
    });
    await sandbox.apiFetch("https://omnivaleur.com/api/items");
    check("de sessie blijft staan", !staat.gewist && !staat.naarLogin,
          "de verkoper werd uitgelogd door een verbindingshik");
    check("het inlogbewijs staat er nog", opslag.cl_refresh === "R0");
  }

  // 3. Het netwerk valt weg.
  console.log("\nHet netwerk valt weg tijdens het vernieuwen:");
  {
    const { sandbox, staat } = dashboard({
      sleutel: "R0", token: bewijs(-60),
      antwoord: (url) => { if (url.includes("/auth/refresh")) throw new Error("offline"); return FOUT(401); },
    });
    await sandbox.apiFetch("https://omnivaleur.com/api/items").catch(() => {});
    check("de sessie blijft staan", !staat.gewist && !staat.naarLogin,
          "een wegvallende verbinding logde de verkoper uit");
  }

  // 4. Vernieuwen VOOR het verloopt, in plaats van na een mislukt verzoek.
  console.log("\nHet bewijs verloopt bijna:");
  {
    const { sandbox, staat, opslag } = dashboard({
      sleutel: "R0", token: bewijs(60),
      antwoord: () => OK("R1"),
    });
    if (typeof sandbox.zorgVoorVersToken === "function") await sandbox.zorgVoorVersToken();
    check("er wordt uit zichzelf vernieuwd", opslag.cl_refresh === "R1",
          "het bewijs verliep bijna en er gebeurde niets");
    check("zonder een mislukt verzoek af te wachten",
          staat.verzoeken.length === 1 && staat.verzoeken[0].url.includes("/auth/refresh"));
  }
  console.log("\nHet bewijs is nog uren geldig:");
  {
    const { sandbox, staat } = dashboard({ sleutel: "R0", token: bewijs(7200), antwoord: () => OK("R1") });
    if (typeof sandbox.zorgVoorVersToken === "function") await sandbox.zorgVoorVersToken();
    check("dan wordt er niets vernieuwd", staat.verzoeken.length === 0,
          `er gingen ${staat.verzoeken.length} verzoeken uit`);
  }

  // 5. Een sleutel die echt dood is moet nog steeds uitloggen.
  console.log("\nDe sleutel is echt niet meer geldig:");
  {
    const { sandbox, staat } = dashboard({
      sleutel: "R0", token: bewijs(-60),
      antwoord: () => FOUT(401),
    });
    await sandbox.apiFetch("https://omnivaleur.com/api/items");
    check("dan gaat de verkoper wél naar het inlogscherm", staat.gewist && staat.naarLogin,
          "een dode sessie bleef staan, en dan werkt er niets meer zonder uitleg");
  }

  // ── De extensie moet de verse sleutel teruggeven ──────────────────────────
  console.log("\nDe extensie draait de sleutel door:");
  {
    const verstuurd = [];
    const luisteraar = { addListener() {}, removeListener() {} };
    const opslag = () => {
      const d = {};
      return {
        get: (k, terug) => {
          let uit = {};
          if (k == null) uit = { ...d };
          else if (Array.isArray(k) || typeof k === "string") {
            for (const s of (Array.isArray(k) ? k : [k])) if (s in d) uit[s] = d[s];
          } else { uit = { ...k }; for (const s of Object.keys(k)) if (s in d) uit[s] = d[s]; }
          if (typeof terug === "function") { terug(uit); return; }
          return Promise.resolve(uit);
        },
        set: (o, terug) => { Object.assign(d, o); if (typeof terug === "function") { terug(); return; } return Promise.resolve(); },
        remove: (k, terug) => { for (const s of (Array.isArray(k) ? k : [k])) delete d[s]; if (typeof terug === "function") { terug(); return; } return Promise.resolve(); },
        _ruw: d,
      };
    };
    const niets = () => new Proxy(function () {}, {
      get: (doel, sleutel) => {
        if (sleutel === "addListener" || sleutel === "removeListener") return () => {};
        if (sleutel === "then") return undefined;
        if (!(sleutel in doel)) doel[sleutel] = niets();
        return doel[sleutel];
      },
      apply: () => Promise.resolve(),
    });
    const lokaal = opslag();
    const sandbox = {
      chrome: {
        storage: { local: lokaal, session: opslag(), sync: opslag(), onChanged: luisteraar },
        alarms: { create() {}, clear() {}, clearAll() {}, get: async () => null, onAlarm: luisteraar },
        runtime: {
          onInstalled: luisteraar, onMessage: luisteraar, onStartup: luisteraar,
          onConnect: luisteraar, onSuspend: luisteraar, onUpdateAvailable: luisteraar,
          getManifest: () => ({ version: "test" }), getURL: (p) => p, lastError: null,
        },
        tabs: {
          query: async () => [{ id: 7, url: "https://omnivaleur.com/app.html" }],
          sendMessage: (id, msg) => { verstuurd.push({ id, msg }); },
          onRemoved: luisteraar, onUpdated: luisteraar, onActivated: luisteraar,
          onCreated: luisteraar, onReplaced: luisteraar,
          create: async () => ({ id: 1 }), remove: async () => {}, update: async () => ({}),
          get: async () => ({ id: 1 }),
        },
        power: { requestKeepAwake() {}, releaseKeepAwake() {} },
        idle: { queryState: async () => "active", onStateChanged: luisteraar },
        action: niets(), windows: niets(), scripting: niets(), notifications: niets(),
        cookies: niets(), debugger: niets(), permissions: niets(), webRequest: niets(),
        downloads: niets(), management: niets(),
      },
      console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
      setTimeout, clearTimeout, setInterval, clearInterval,
      URL, URLSearchParams, TextEncoder, TextDecoder, Blob, FormData, AbortController,
      Date, Math, JSON, Promise, importScripts: () => {},
      btoa: (s) => Buffer.from(s, "binary").toString("base64"),
      atob: (s) => Buffer.from(s, "base64").toString("binary"),
      crypto: { randomUUID: () => "x", getRandomValues: (a) => a },
      structuredClone: (o) => JSON.parse(JSON.stringify(o)),
      fetch: async () => ({
        ok: true, status: 200,
        json: async () => ({ access_token: bewijs(3600), refresh_token: "R1" }),
      }),
    };
    sandbox.self = sandbox;
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(bron("extension/background.js"), sandbox, { filename: "background.js" });
    await lokaal.set({ refreshToken: "R0" });
    await sandbox.refreshAccessToken();
    const bericht = verstuurd.find((v) => v.msg && v.msg.type === "TOKEN_VERNIEUWD");
    check("het dashboard krijgt de verse sleutel terug", !!bericht,
          "er ging niets naar het openstaande dashboard");
    check("met zowel het bewijs als de sleutel erbij",
          !!bericht && !!bericht.msg.token && bericht.msg.refresh === "R1");
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles in orde");
  process.exit(mislukt ? 1 : 0);
})().catch((e) => { console.error("proef zelf stukgelopen:", e); process.exit(2); });
