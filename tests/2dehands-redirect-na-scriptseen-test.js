/**
 * Egbert Brouwer (papas-plectrums), 07-09-2026: "Voordat ik verder kan zal eerst
 * dit probleem opgelost moeten worden."
 *
 * GEMETEN AAN ZIJN OPDRACHTENLOGBOEK (07-09-2026, live database):
 *   671 plaatsopdrachten voor 2dehands, NUL geslaagd, drie weken lang. De laatste
 *   tientallen falen met "Extension timed out ... (no response after 3 minutes)",
 *   duur claim->afgemeld steeds 200 tot 227 seconden, en NUL voortgangsberichten.
 *   Zijn extensie meldde zich wel (scriptSeen=true), dus zijn 2dehands een
 *   one-page app: het plaatsformulier laadt, ons invulscript injecteert, en PAS
 *   DAARNA stuurt 2dehands.be de pagina naar /identity/v2/login.
 *
 * DE FOUT: de detectie van die doorverwijzing in chrome.tabs.onUpdated stond
 * achter `!meta.scriptSeen`. Zodra ons script geladen was werd de sprong naar de
 * inlogpagina genegeerd en liep de opdracht alsnog drie minuten leeg.
 *
 * Draaien: node tests/2dehands-redirect-na-scriptseen-test.js
 *          node tests/2dehands-redirect-na-scriptseen-test.js --oud   (MOET falen)
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const WORTEL = path.join(__dirname, "..");
// De staat vlak voor deze sessie. Alles daarna is de reparatie.
const BASIS = "2c670b0";
const oud = process.argv.includes("--oud");
const BG = oud
  ? execSync(`git show ${BASIS}:extension/background.js`, { cwd: WORTEL, maxBuffer: 64e6 }).toString()
  : fs.readFileSync(path.join(WORTEL, "extension/background.js"), "utf8");

let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

/** Blok met balanceren van accolades, vanaf de eerste { na de kop. */
function blok(kop) {
  const start = BG.indexOf(kop);
  if (start < 0) return "";
  let diepte = 0, i = BG.indexOf("{", start);
  for (; i < BG.length; i++) {
    if (BG[i] === "{") diepte++;
    else if (BG[i] === "}") { diepte--; if (!diepte) return BG.slice(start, i + 1); }
  }
  return BG.slice(start);
}

// ── 1. De onUpdated-handler herkent de doorverwijzing, ook na scriptSeen ────
const handler = blok("chrome.tabs.onUpdated.addListener(async (tabId, changeInfo)");
check("er is een onUpdated-handler voor job-tabbladen", handler.length > 0);

const iLogin = handler.indexOf("MP_LOGINPAGINA.test(changeInfo.url)");
check("de handler herkent een sprong naar de inlogpagina", iLogin > -1);

const ifStart = handler.lastIndexOf("if (", iLogin);
const voorwaarde = handler.slice(ifStart, handler.indexOf("{", iLogin));
check("de inlogdetectie hangt NIET af van !meta.scriptSeen",
  iLogin > -1 && !/!meta\.scriptSeen/.test(voorwaarde),
  `voorwaarde: ${voorwaarde.replace(/\s+/g, " ").trim()}`);

check("de melding legt uit dat de Marktplaats-familie aparte logins heeft",
  /separate logins/.test(handler));
check("de melding zet ook de rest van de wachtrij stil",
  /stopPlatformWachtrij/.test(handler));

// ── 2. De bewaker kijkt WAAR het tabblad staat i.p.v. te gokken ────────────
const bewaker = blok("async function fireJobWatchdog(");
check("de bewaker kijkt in het tabblad voor hij 'timed out' meldt",
  /const snap = await bekijkVastgelopenTabblad\(tabId\)/.test(bewaker));
check("een tabblad op een inlog/verificatiepagina gaat alsnog naar meldNooitBegonnen",
  /if \(opInlog[\s\S]{0,400}meldNooitBegonnen\(tabId, meta, snap\)/.test(bewaker));
check("de gewone tijdsoverschrijding-melding krijgt nu de feiten van het tabblad mee",
  /timed out waiting for this[\s\S]{0,300}\+ feiten/.test(bewaker));

// meldNooitBegonnen mag een al-gemaakte momentopname hergebruiken (het tabblad
// kan dicht zijn tegen de tijd dat het zelf zou kijken).
const mnb = blok("async function meldNooitBegonnen(");
check("meldNooitBegonnen accepteert een doorgegeven momentopname",
  /function meldNooitBegonnen\(tabId, meta, snapshot\)/.test(mnb)
  && /snapshot \|\| await bekijkVastgelopenTabblad/.test(mnb));

if (mislukt) { console.log(`\n${mislukt} FOUT(EN)`); process.exit(1); }
console.log("\nAlles goed.");
