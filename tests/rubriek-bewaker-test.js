/**
 * De rubriekbewaker: nooit op Plaatsen klikken als het formulier niet op de bedoelde rubriek staat.
 *
 * WAAROM (02-11-2026, Esther): op Marktplaats is de rubriek na het plaatsen niet meer te wijzigen.
 * Draaien:      node tests/rubriek-bewaker-test.js
 * Voor-en-na:   node tests/rubriek-bewaker-test.js <oude shared.js>   (de oude heeft geen bewaker: faalt)
 */
const fs = require("fs");
const path = require("path");
const BESTAND = process.argv[2] || path.join(__dirname, "..", "extension", "content", "shared.js");
const SRC = fs.readFileSync(BESTAND, "utf8");

const start = SRC.indexOf("function bewaakRubriek(");
if (start < 0) { console.error("FOUT: geen bewaakRubriek in " + BESTAND); process.exit(1); }
let diepte = 0, eind = -1;
for (let i = SRC.indexOf("{", start); i < SRC.length; i++) {
  if (SRC[i] === "{") diepte++;
  if (SRC[i] === "}" && --diepte === 0) { eind = i + 1; break; }
}
const bewaak = (pad, item) => new Function("location", SRC.slice(start, eind) + "\nreturn bewaakRubriek(arguments[1]);")({ pathname: pad }, item);

let fouten = 0;
const eis = (naam, ok) => { console.log((ok ? "ok    " : "FOUT  ") + naam); if (!ok) fouten++; };
const werpt = (pad, item) => { try { bewaak(pad, item); return false; } catch (e) { return true; } };

const verwacht = { _rubriek_verwacht: { l1: 621, l2: 631 } };
eis("juiste rubriek: geeft hem terug", JSON.stringify(bewaak("/plaats/621/631", verwacht)) === '{"l1":621,"l2":631}');
eis("juiste rubriek met extra padstuk", JSON.stringify(bewaak("/plaats/621/631/", verwacht)) === '{"l1":621,"l2":631}');
eis("andere tweede rubriek: weigert", werpt("/plaats/621/636", verwacht));
eis("andere hoofdrubriek: weigert", werpt("/plaats/1776/631", verwacht));
eis("melding noemt beide rubrieken", (() => { try { bewaak("/plaats/621/636", verwacht); } catch (e) { return /621\/636/.test(e.message) && /621\/631/.test(e.message); } })());
eis("geen verwachting (Vinted, oude opdracht): geen controle", bewaak("/plaats/1/2", {}) === null);
eis("onleesbaar adres: niet blokkeren, wel null melden", bewaak("/nieuw-schema/abc", verwacht) === null);
eis("geen item: geen fout", bewaak("/plaats/621/631", undefined) === null);
eis("nummers als tekst werken ook", bewaak("/plaats/621/631", { _rubriek_verwacht: { l1: "621", l2: "631" } }) !== null);

console.log(fouten ? `\n${fouten} FOUT` : "\nalles ok");
process.exit(fouten ? 1 : 0);
