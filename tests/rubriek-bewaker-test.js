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
// De functie eindigt op de eerste regel die met twee spaties en een } begint (de regexen binnenin hebben eigen accolades).
const eind = SRC.indexOf("\n  }\n", start) + 4;
const bewaak = (pad, item, html) => new Function("location", "document", SRC.slice(start, eind) + "\nreturn bewaakRubriek(arguments[2]);")({ pathname: pad }, html === undefined ? undefined : { documentElement: { innerHTML: html } }, item);

let fouten = 0;
const eis = (naam, ok) => { console.log((ok ? "ok    " : "FOUT  ") + naam); if (!ok) fouten++; };
const werpt = (pad, item, html) => { try { bewaak(pad, item, html); return false; } catch (e) { return true; } };

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

const echt = (l1, l2) => `x"c":{"l1":{"id":${l1},"n":"A"},"l2":{"id":${l2},"n":"B"}}y`;
eis("ingebedde rubriek gelijk: ok", bewaak("/plaats/621/631", verwacht, echt(621, 631)).l2 === 631);
eis("ingebedde rubriek wijkt af (adres klopt wel): weigert", werpt("/plaats/621/631", verwacht, echt(621, 636)));
eis("handtas: formulier noemt hoofdrubriek 1826, rubriek gelijk: ok", bewaak("/plaats/621/626", { _rubriek_verwacht: { l1: 621, l2: 626 } }, echt(1826, 626)).l1 === 1826);
eis("geen ingebed blok: alleen het adres telt", bewaak("/plaats/621/631", verwacht, "<html>niets</html>").l2 === 631);

console.log(fouten ? `\n${fouten} FOUT` : "\nalles ok");
process.exit(fouten ? 1 : 0);
