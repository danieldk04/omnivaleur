/**
 * Ook 2dehands heeft een Admarkt, en wij keken daar nooit.
 *
 * WAT ER AAN DE HAND WAS (Egbert Brouwer, 10-09-2026). In background.js stond
 * de aanname dat alleen Marktplaats een zakelijke console heeft; in
 * mpEmptyScanReason stond letterlijk "2dehands, dat geen Admarkt heeft". Dat is
 * onjuist, en het is nagemeten, niet beredeneerd:
 *
 *   https://admarkt.2dehands.be/    -> 302 naar www.2dehands.be/identity/v2/login
 *                                      met client_id=twhbe_console en
 *                                      scope=console_ro console_rw
 *   https://admarkt.2ememain.be/    -> dezelfde login, Franstalige tenant
 *
 * Gevolg van de oude aanname: een zakelijk account op 2dehands heeft daar een
 * leeg persoonlijk "Mijn advertenties"-overzicht, precies zoals op Marktplaats,
 * en kreeg van ons "je bent niet ingelogd". Egbert staat op 2dehands op 671
 * opdrachten en nul geslaagde plaatsingen.
 *
 * WAT DEZE PROEF VASTLEGT. De echte functies uit background.js, met een nep-
 * Chrome eronder, en het echte manifest. In --oud draait hij tegen een VAST
 * commitnummer (niet HEAD, want na de commit zou hij de reparatie met zichzelf
 * vergelijken) en dan MOET hij falen: die code kan 2dehands niet eens noemen.
 *
 * Draaien:  node tests/admarkt-ook-op-2dehands-test.js
 *           node tests/admarkt-ook-op-2dehands-test.js --oud
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
const VOOR_DE_REPARATIE = "b4df1861";
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync(`git show ${VOOR_DE_REPARATIE}:extension/background.js`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");
const MANIFEST = JSON.parse(fs.readFileSync(path.join(WORTEL, "extension/manifest.json"), "utf8"));

let mislukt = 0;
function ok(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

// Op naam MET haakje, anders vindt "admarktUrl" ook "admarktUrlBouwer".
function blokUit(naam, woord = "function") {
  let start = BG.indexOf(`${woord} ${naam}(`);
  if (start < 0) return null;
  // "async" hoort erbij. Zonder dit knip je een async functie eruit als gewone
  // functie en klapt hij op zijn eerste await — de fout wijst dan naar de test
  // en niet naar de code.
  if (BG.slice(Math.max(0, start - 6), start) === "async ") start -= 6;
  let diepte = 0, i = BG.indexOf("{", start);
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(start, i + 1);
}
function constUit(naam) {
  const start = BG.indexOf(`const ${naam} = `);
  if (start < 0) return null;
  const open = BG.indexOf("{", start);
  if (open < 0 || open > BG.indexOf("\n", start)) {   // gewone waarde op één regel
    const eind = BG.indexOf("\n", start);
    return BG.slice(start, eind + 1);
  }
  let diepte = 0, i = open;
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) break; }
  }
  return BG.slice(start, i + 2);
}

// ── de nep-Chrome ──────────────────────────────────────────────────────────
function bouwWereld({ mpToestemming = false, opslag = {}, aangemeld = [] } = {}) {
  const geregistreerd = aangemeld.slice();
  const bewaard = { ...opslag };
  const chrome = {
    runtime: { getManifest: () => MANIFEST },
    storage: {
      local: {
        get: async (k) => {
          const sleutels = Array.isArray(k) ? k : [k];
          const uit = {};
          for (const s of sleutels) if (s in bewaard) uit[s] = bewaard[s];
          return uit;
        },
        set: async (o) => { Object.assign(bewaard, o); },
      },
    },
    permissions: {
      // Deze nep-Chrome zegt ALTIJD nee voor de Belgische console. Zegt de code
      // toch ja, dan kan dat alleen via het manifest — en dat is precies wat we
      // hier willen bewijzen.
      contains: async ({ origins }) =>
        origins.every(o => o.startsWith("https://admarkt.marktplaats.nl") && mpToestemming),
    },
    scripting: {
      getRegisteredContentScripts: async ({ ids }) =>
        geregistreerd.filter(s => ids.includes(s.id)),
      registerContentScripts: async (lijst) => { geregistreerd.push(...lijst); },
      unregisterContentScripts: async ({ ids }) => {
        for (const id of ids) {
          const i = geregistreerd.findIndex(s => s.id === id);
          if (i >= 0) geregistreerd.splice(i, 1);
        }
      },
    },
  };
  const sandbox = { chrome, console: { warn() {}, log() {} }, URL, Date, Number, Math, JSON, Set };
  vm.createContext(sandbox);
  const stukken = [
    constUit("ADMARKT_ORIGINS"), constUit("ADMARKT_SCRIPT_ID"),
    blokUit("admarktOrigin"), blokUit("patroonDektOrigin"), blokUit("manifestDektOrigin"),
    blokUit("admarktUrl"), blokUit("admarktToegestaan"), blokUit("admarktOoitAan"),
    blokUit("admarktVoorkeurAan"), blokUit("admarktUitgezet"), blokUit("admarktMeenemen"),
    blokUit("admarktScriptId"), blokUit("zorgVoorAdmarktMeekijker"),
  ];
  const ontbreekt = stukken.filter(s => !s).length;
  if (ontbreekt) {
    throw new Error(`${ontbreekt} van de ${stukken.length} stukken staan niet in deze `
      + `background.js — deze versie kent de Belgische Admarkt niet.`);
  }
  for (const stuk of stukken) vm.runInContext(stuk, sandbox);
  return { sandbox, geregistreerd, bewaard };
}

(async () => {
  console.log("\n1. Er zijn twee Admarkt-consoles, niet een");
  {
    const { sandbox } = bouwWereld();
    const roep = (js) => vm.runInContext(js, sandbox);
    ok("2dehands wijst naar admarkt.2dehands.be",
       roep(`admarktOrigin("2dehands")`) === "https://admarkt.2dehands.be");
    ok("marktplaats blijft admarkt.marktplaats.nl",
       roep(`admarktOrigin("marktplaats")`) === "https://admarkt.marktplaats.nl");
    ok("een onbekend kanaal valt terug op Marktplaats en niet op undefined",
       roep(`admarktOrigin("vinted")`) === "https://admarkt.marktplaats.nl");
    const url = roep(`admarktUrl("2dehands")`);
    ok("het overzichtsadres staat op de Belgische console",
       url.startsWith("https://admarkt.2dehands.be/advertisements?"), url);
    ok("met de datumgrenzen erin, anders kiest de pagina zelf een periode",
       /startDate=\d{4}-\d{2}-\d{2}&endDate=\d{4}-\d{2}-\d{2}/.test(url), url);
  }

  console.log("\n2. Het manifest dekt de Belgische console al");
  {
    const { sandbox } = bouwWereld();
    const roep = (js) => vm.runInContext(js, sandbox);
    ok("https://*.2dehands.be/* dekt admarkt.2dehands.be",
       roep(`patroonDektOrigin("https://*.2dehands.be/*", "https://admarkt.2dehands.be")`) === true);
    ok("en dekt www.2dehands.be zelf ook",
       roep(`patroonDektOrigin("https://*.2dehands.be/*", "https://www.2dehands.be")`) === true);
    ok("maar niet zomaar een andere site",
       roep(`patroonDektOrigin("https://*.2dehands.be/*", "https://admarkt.marktplaats.nl")`) === false);
    ok("en niet een adres dat er alleen op lijkt",
       roep(`patroonDektOrigin("https://*.dehands.be/*", "https://admarkt.2dehands.be")`) === false);
    ok("het echte manifest dekt de Belgische console",
       roep(`manifestDektOrigin("https://admarkt.2dehands.be")`) === true);
  }

  console.log("\n3. Op 2dehands is er niets te vragen, op Marktplaats verandert er niets");
  {
    const w = bouwWereld({ mpToestemming: false });
    ok("2dehands mag, ook al zegt de toestemmingsvraag nee",
       await vm.runInContext(`admarktToegestaan("2dehands")`, w.sandbox) === true);
    ok("Marktplaats hangt nog steeds aan de schakelaar: uit is uit",
       await vm.runInContext(`admarktToegestaan("marktplaats")`, w.sandbox) === false);
    const aan = bouwWereld({ mpToestemming: true });
    ok("en aan is aan",
       await vm.runInContext(`admarktToegestaan("marktplaats")`, aan.sandbox) === true);
  }

  console.log("\n4. Wanneer kijken we in de Belgische console?");
  {
    const leeg = bouwWereld();
    ok("persoonlijk overzicht leeg: dan kijken we er sowieso",
       await vm.runInContext(`admarktMeenemen(0, "2dehands")`, leeg.sandbox) === true);
    const uit = bouwWereld({ opslag: { admarkt_aan: false } });
    ok("maar wie de schakelaar met de hand uitzette, blijft met rust gelaten",
       await vm.runInContext(`admarktMeenemen(0, "2dehands")`, uit.sandbox) === false);
    const aan = bouwWereld({ opslag: { admarkt_aan: true } });
    ok("staat hij aan, dan kijken we er ook naast een gevuld overzicht",
       await vm.runInContext(`admarktMeenemen(120, "2dehands")`, aan.sandbox) === true);
  }

  console.log("\n5. De meekijker wordt per console apart aangemeld");
  {
    const w = bouwWereld({ mpToestemming: true });
    await vm.runInContext(`zorgVoorAdmarktMeekijker("2dehands")`, w.sandbox);
    await vm.runInContext(`zorgVoorAdmarktMeekijker("marktplaats")`, w.sandbox);
    const be = w.geregistreerd.find(s => s.id === "omnivaleur-admarkt-2dehands");
    const nl = w.geregistreerd.find(s => s.id === "omnivaleur-admarkt");
    ok("de Belgische meekijker staat er", !!be);
    ok("en luistert op admarkt.2dehands.be",
       !!be && be.matches.includes("https://admarkt.2dehands.be/*"), be && be.matches.join());
    ok("en draait vóór de pagina-code, anders is hij te laat",
       !!be && be.runAt === "document_start" && be.world === "MAIN");
    ok("het id van de Marktplaats-meekijker is ONVERANDERD, anders krijgt iedereen een tweede kopie",
       !!nl && nl.matches.includes("https://admarkt.marktplaats.nl/*"));
    // Twee keer aanmelden mag geen dubbele opleveren.
    await vm.runInContext(`zorgVoorAdmarktMeekijker("2dehands")`, w.sandbox);
    ok("nog een keer aanmelden levert geen tweede Belgische meekijker op",
       w.geregistreerd.filter(s => s.id === "omnivaleur-admarkt-2dehands").length === 1);
  }

  console.log("\n6. De onjuiste zin staat niet meer in de code");
  {
    ok("\"2dehands, dat geen Admarkt heeft\" is weg",
       !/2dehands, dat geen Admarkt heeft/.test(BG));
    ok("de scan noemt Admarkt niet langer alleen voor Marktplaats",
       !/platform === "marktplaats" && await admarktMeenemen\(result\.items\.length\)/.test(BG));
  }

  console.log(mislukt === 0 ? "\nAlles goed.\n" : `\n${mislukt} proef(en) mislukt.\n`);
  process.exit(mislukt === 0 ? 0 : 1);
})().catch((e) => {
  console.log(`\nAfgebroken: ${e.message}\n`);
  process.exit(1);
});
