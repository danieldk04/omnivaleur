/**
 * Type bij Antieke sieraden, zelf verzenden en kopersbescherming op Marktplaats.
 *
 * WAAROM (29-10-2026, Mieneke van Voordeelsieraden). Het plaatsformulier van
 * Antieke sieraden (1826/13) zet Type zelf op "Ring" en wij raakten het nooit aan:
 * elk antiek collier kwam online als ring. Zie de toelichting bij vulSieraadType in
 * extension/content/shared.js, met de metingen op het echte formulier.
 *
 * Draait de ECHTE functies uit shared.js tegen een nagemaakt formulier met de echte
 * optielijst. De echte formulier-proef is apart gedaan (zie team-notes 29-10-2026).
 *
 * Draaien:  node tests/extensie-sieraad-type-test.js
 */
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const SRC = fs.readFileSync(path.resolve(__dirname, "..", "extension", "content", "shared.js"), "utf8");
const a = SRC.indexOf("  const SIERAAD_LIJST");
const b = SRC.indexOf("  // DE BESCHRIJVING ECHT TYPEN.");
if (a < 0 || b < 0) { console.error("sieraad-functies niet gevonden in shared.js"); process.exit(1); }
const CODE = SRC.slice(a, b);

const OPTIES = ["Armband", "Broche", "Hanger", "Ketting", "Manchetknopen", "Oorbellen", "Ring", "Overige typen"];
let fouten = 0;
function proef(naam, fn) {
  try { fn(); console.log("ok    " + naam); }
  catch (e) { fouten++; console.log("FOUT  " + naam + "\n      " + e.message); }
}
const f = new Function("qs", "clog", "centenUitTekst", "wachtOpElement", "sleep", "fillInput", "location", "window", "Event",
  CODE + "\nreturn { sieraadTypeKeuze, vulSieraadType, zetMpVerzending, zetMpKopersbescherming, mpVerzendingKlopt, mpKopersbeschermingKlopt };");
const kies = (title, description = "") => f(() => null, () => {}).sieraadTypeKeuze({ title, description }, OPTIES);

proef("het collier van Mieneke wordt Ketting, niet Ring", () => {
  assert.strictEqual(kies("Antiek bloedkoraal collier 14k gouden slot",
    "De zachte zalmroze kleur van natuurlijk bloedkoraal geeft dit antieke collier een verfijnde uitstraling."), "Ketting");
});
const TABEL = [
  ["Bloedkoraal antieke ketting fraai 14k slot goud dame vintage", "Ketting"],
  ["Antieke gouden ring met robijn", "Ring"], ["Zegelring 14 karaat goud", "Ring"],
  ["Antiek zilveren armband", "Armband"], ["Bedelarmband zilver antiek", "Armband"], ["Schakelarmband antiek", "Armband"],
  ["Antieke broche granaat", "Broche"], ["Oorbellen antiek goud", "Oorbellen"], ["Oorringen antiek", "Oorbellen"],
  ["Antieke oorhangers parel", "Oorbellen"], ["Antieke hanger met ketting", "Hanger"], ["Antieke kettinghanger zilver", "Hanger"],
  ["Medaillon antiek zilver", "Hanger"], ["Manchetknopen antiek zilver", "Manchetknopen"],
  ["Antieke set ring en oorbellen", "Overige typen"], ["Gouden ring met versiering", "Ring"],
  ["Antiek sieraad 14k goud", "Overige typen"], ["Antiek parelsnoer", "Overige typen"],
];
for (const [titel, verwacht] of TABEL) proef(`${titel} -> ${verwacht}`, () => assert.strictEqual(kies(titel), verwacht));
proef("titel zonder sieraad: de omschrijving beslist als die er maar één noemt", () => {
  assert.strictEqual(kies("Antiek sieraad", "Een mooi collier"), "Ketting");
  assert.strictEqual(kies("Antiek sieraad", "Ring en ketting samen"), "Overige typen");
});

// Het veld zelf: Ring wordt overschreven, een sportlijst wordt met rust gelaten.
const maakSelect = (lijst, gekozen) => {
  const options = [{ text: "Kies...", value: "", disabled: true }, ...lijst.map((t) => ({ text: t, value: t, disabled: false }))];
  return { options, selectedIndex: options.findIndex((o) => o.text === gekozen) };
};
const run = (select, item) => {
  const g = new Function("qs", "clog", "window", "Event",
    CODE + "\nreturn { vulSieraadType };");
  const win = { HTMLSelectElement: { prototype: Object.defineProperty({}, "value", {
    set(v) { this.selectedIndex = this.options.findIndex((o) => o.value === v); } }) } };
  const sel = Object.assign(select, { dispatchEvent() {} });
  return g(() => sel, () => {}, win, function Event() {}).vulSieraadType(item).then(() => sel);
};
(async () => {
  const sel = maakSelect(OPTIES, "Ring");
  await run(sel, { title: "Antiek zilveren collier" });
  proef("het vooringevulde Ring wordt Ketting", () => assert.strictEqual(sel.options[sel.selectedIndex].text, "Ketting"));
  const sport = maakSelect(["Voetbal", "Algemeen", "Hardlopen of Fietsen"], "Algemeen");
  await run(sport, { title: "Antiek ring" });
  proef("een Type-lijst van sportkleding blijft ongemoeid", () => assert.strictEqual(sport.options[sport.selectedIndex].text, "Algemeen"));
  console.log(fouten ? `\n${fouten} FOUT` : "\nalles ok");
  process.exit(fouten ? 1 : 0);
})();
