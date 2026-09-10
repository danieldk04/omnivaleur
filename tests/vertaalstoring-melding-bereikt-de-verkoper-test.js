/**
 * De Juiste Toon (Etten-Leur), 09-09-2026: publiceren lukte niet en op zijn
 * scherm stond elke keer hetzelfde witte blok:
 *
 *   "The server didn't answer in time (503). This usually means it was busy or
 *    restarting. Your item may already be on its way — refresh the page and
 *    check before you try again."
 *
 * Dat klopte van geen kant. De server antwoordde in een fractie van een seconde,
 * en met een duidelijke reden.
 *
 * DE KETEN, ELKE SCHAKEL GEMETEN (10-09-2026)
 *
 * 1. Het Anthropic-tegoed is op. De echte `_vertaal` uit crosslist.py draaien op
 *    zijn eigen tekst geeft:
 *      anthropic.BadRequestError: 400 — "Your credit balance is too low to
 *      access the Anthropic API." (request_id req_011CeuLeAwdUepCeb8EHmzUY)
 *    Dat is een grens van het account, niet van de sleutel: Railway loopt tegen
 *    dezelfde muur.
 * 2. `_vertaal` maakt daar sinds 08-09 terecht een VertalingOnbeschikbaar van,
 *    zodat er geen onvertaalde tekst de deur uit gaat.
 * 3. `_zonder_vertaling` laat een advertentie tóch door als de tekst aantoonbaar
 *    al in de doeltaal staat. Gemeten op zijn eigen artikelen in Supabase:
 *      lijkt_al_in_taal(titel + omschrijving, "nl")
 *        Lederhosen kort incl bretels maat 50 .................. true
 *        Originele trachten Lederhosen maat 52 ................. true
 *        Originele Lederhosen XXXL maat 60 ..................... true
 *        Dames nette Trachten suede broek maat 38 .............. true
 *        AKTIE Originele Lederhosen Maten S.M.L.Xl ............. true
 *        Vintage Oosters tribaal tapijt 140/96 ................. true
 *        Lederhosen maat 54 ................................... true
 *        Perzisch tapijtje versleten sleets rood taupe 128/79 .. FALSE
 *    Precies dat ene artikel staat op zijn schermafbeelding. Alle zeven die het
 *    wél haalden kregen die avond gewoon een opdracht in de wachtrij; van het
 *    tapijtje bestaat er nul, nooit. Zijn omschrijving is kernwoorden zonder
 *    Nederlandse stopwoorden ("Perzisch tapijtje / Versleten Sleets / Rood
 *    taupe / Tweezijdig franje / Afmetingen"), dus de taal is er niet aan af te
 *    lezen en de publicatie wordt tegengehouden. Dat is de bedoeling.
 * 4. Alleen: die reden ging als HTTP 503 de deur uit. Cloudflare vervangt een
 *    502/503 door zijn eigen storingspagina (gemeten 04-09-2026, zie
 *    docs/kennisbank.md), dus `detail` haalde de browser niet. En zelfs als het
 *    er wél doorheen kwam, gooide het scherm de reden alsnog weg: de 503-tak in
 *    publishFailureMessage keek niet naar de meegestuurde reden.
 *
 * Deze proef draait de ECHTE publishFailureMessage uit app.html.
 *
 * Draaien: node tests/vertaalstoring-melding-bereikt-de-verkoper-test.js
 *          node tests/vertaalstoring-melding-bereikt-de-verkoper-test.js --oud
 *                                              (vorige versie; moet FALEN)
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// Een vast commitnummer, geen HEAD: zodra deze reparatie gecommit is vergelijkt
// HEAD de nieuwe code met zichzelf en bewijst de proef niets meer.
const VOOR_DE_REPARATIE = "4fe253cf";
const oud = process.argv.includes("--oud");

function bron(bestand) {
  return oud
    ? execSync(`git show ${VOOR_DE_REPARATIE}:${bestand}`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
    : fs.readFileSync(path.join(WORTEL, bestand), "utf8");
}

const html = bron("frontend/app.html");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function pakFunctie(tekst, naam) {
  const start = tekst.indexOf(`function ${naam}(`);
  if (start < 0) throw new Error(`${naam} niet gevonden in app.html`);
  let diepte = 0, i = tekst.indexOf("{", start);
  for (; i < tekst.length; i++) {
    if (tekst[i] === "{") diepte++;
    else if (tekst[i] === "}") { diepte--; if (!diepte) break; }
  }
  return tekst.slice(start, i + 1);
}

const ctx = {
  console,
  PLATFORM_LABELS: { marktplaats: "Marktplaats", "2dehands": "2dehands", vinted: "Vinted" },
};
vm.createContext(ctx);
vm.runInContext(
  pakFunctie(html, "formatMissingFieldsError") + "\n" +
  pakFunctie(html, "publishFailureMessage"), ctx);

/** Wat leest de verkoper? */
function melding(status, body) {
  const rauw = JSON.stringify(body);
  ctx._res = { status };
  ctx._data = body;
  ctx._rauw = rauw;
  return vm.runInContext("publishFailureMessage(_res, _data, _rauw)", ctx);
}

// De zin die de server echt meestuurt (backend/services/crosslist.py).
const ECHTE_REDEN =
  "De vertaling naar het Nederlands lukte niet, dus er is niets geplaatst. " +
  "Zodra de vertaling weer werkt gaat deze advertentie vanzelf alsnog de deur uit.";

(async () => {
  console.log(oud ? "VORIGE VERSIE (hier hoort het fout te gaan)" : "HUIDIGE VERSIE");

  // 1. Het geval van De Juiste Toon. De server zegt waarom; dat hoort op het
  //    scherm te staan, niet "de server was druk".
  const m503 = melding(503, { detail: ECHTE_REDEN });
  check("503 met reden: de echte reden staat op het scherm",
        m503.includes("vertaling"), `stond er: ${JSON.stringify(m503)}`);
  check("503 met reden: geen verzonnen tijdverloop meer",
        !/didn't answer in time/.test(m503), `stond er: ${JSON.stringify(m503)}`);

  // 2. Een echte gateway-storing heeft geen reden — dan blijft de oude tekst
  //    staan, inclusief de waarschuwing dat het misschien tóch al loopt.
  const gateway = melding(502, {});
  check("502 zonder reden: gateway-tekst blijft",
        /didn't answer in time/.test(gateway) && /may already be on its way/.test(gateway),
        `stond er: ${JSON.stringify(gateway)}`);

  // 3. Een HTML-storingspagina mag geen brokstukken op het scherm zetten.
  ctx._res = { status: 503 }; ctx._data = {};
  ctx._rauw = "<!DOCTYPE html><html><body>error 503</body></html>";
  const cf = vm.runInContext("publishFailureMessage(_res, _data, _rauw)", ctx);
  check("Cloudflare-pagina: nog steeds de gateway-tekst",
        /didn't answer in time/.test(cf) && !/DOCTYPE/.test(cf),
        `stond er: ${JSON.stringify(cf)}`);

  // 4. De andere takken mogen hier niet door verstoord zijn.
  check("402 blijft het abonnementsverhaal",
        /subscription/i.test(melding(402, {})));
  check("422 blijft de ontbrekende velden tonen",
        /Can't publish yet/.test(melding(422, { detail: { missing_fields: { marktplaats: ["size"] } } })));

  // 5. En de server moet die reden ook echt kúnnen versturen. Een 503 wordt door
  //    Cloudflare vervangen door een eigen pagina, dus op de publicatiepaden mag
  //    VertalingOnbeschikbaar geen 503 meer opleveren.
  for (const bestand of ["backend/api/items.py", "backend/api/listings.py", "backend/api/jobs.py"]) {
    const py = bron(bestand);
    const takken = py.split("except VertalingOnbeschikbaar").slice(1);
    check(`${bestand}: geen 503 bij een vertaalstoring`,
          takken.length > 0 && takken.every(t => !/status_code=50[23]/.test(t.slice(0, 900))),
          "Cloudflare slikt de uitleg bij een 502/503 op");
  }

  console.log(mislukt ? `\n${mislukt} controle(s) mislukt` : "\nAlles goed");
  process.exit(oud ? (mislukt ? 0 : 1) : (mislukt ? 1 : 0));
})();
