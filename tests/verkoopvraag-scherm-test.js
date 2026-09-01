/**
 * De verkoopvraag ("Is dit verkocht?") tegen een namaakscherm.
 *
 * WAAROM DIT ER IS (01-09-2026). Daniel zocht zijn mogelijk-verkochte artikelen
 * in Analytics en vond ze niet: de balk stond alleen boven de itemlijst. Nu
 * wordt hij op twee plekken getekend. Een tekstcontrole op app.html bewijst dat
 * de regels er staan, niet dat er ook echt iets in beide vakken belandt — en
 * juist dáár zat de fout. Daarom draait hier de échte functie uit app.html,
 * tegen twee lege vakken.
 *
 * Draaien:  node tests/verkoopvraag-scherm-test.js
 */
const fs = require("fs");
const path = require("path");

const APP = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.html"), "utf8");

function functieUit(naam, start = `function ${naam}(`) {
  const i = APP.indexOf(start);
  if (i < 0) throw new Error(`${naam} niet gevonden in app.html`);
  // Tellen tot de accolade weer sluit — de functies hier bevatten template
  // strings met accolades, dus alleen tellen buiten quotes is te broos; de
  // functies eindigen op een regel met precies "}" op kolom 0.
  const eind = APP.indexOf("\n}\n", i);
  if (eind < 0) throw new Error(`einde van ${naam} niet gevonden`);
  return APP.slice(i, eind + 2);
}

// Een minimaal scherm: twee vakken, verder niets.
const vakken = {
  "sold-confirm-bar": { style: {}, innerHTML: "" },
  "an-sold-confirm-bar": { style: {}, innerHTML: "" },
};
const document = { getElementById: (id) => vakken[id] || null };

const state = {
  items: [
    { id: "it1", title: "(1314) Donkergroen Suitable Half Zip", price: 24.99 },
    { id: "it2", title: "(1288) Beige Profuomo Fleece Jacket", price: 30 },
  ],
  listings: [
    { item_id: "it1", platform: "marktplaats", status: "sold_unconfirmed",
      listed_at: new Date(Date.now() - 2 * 86400000).toISOString(),
      error_message: "Mogelijk verkocht: de advertentie was al van het platform af" },
    { item_id: "it2", platform: "marktplaats", status: "sold_unconfirmed",
      listed_at: new Date(Date.now() - 40 * 86400000).toISOString(),
      error_message: "Mogelijk verkocht: de advertentie is niet meer te vinden" },
    { item_id: "it1", platform: "vinted", status: "active", listed_at: null },
  ],
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const PLATFORM_ICONS = { marktplaats: "🟠", vinted: "V" };
const PLATFORM_LABELS = { marktplaats: "Marktplaats", vinted: "Vinted" };

const bron = [
  functieUit("soldConfirmRows"),
  APP.slice(APP.indexOf("const SOLD_CONFIRM_BARS ="),
            APP.indexOf("\n", APP.indexOf("const SOLD_CONFIRM_BARS ="))),
  functieUit("renderSoldConfirmBar"),
].join("\n");

// eslint-disable-next-line no-new-func
new Function("document", "state", "esc", "PLATFORM_ICONS", "PLATFORM_LABELS",
  bron + "\nrenderSoldConfirmBar();")(document, state, esc, PLATFORM_ICONS, PLATFORM_LABELS);

let fouten = 0;
function eis(voorwaarde, wat) {
  if (voorwaarde) { console.log(`  ok   ${wat}`); }
  else { console.log(`  FOUT ${wat}`); fouten++; }
}

console.log("Verkoopvraag op het scherm:");
for (const id of ["sold-confirm-bar", "an-sold-confirm-bar"]) {
  const vak = vakken[id];
  eis(vak.style.display === "block", `${id} is zichtbaar`);
  eis(vak.innerHTML.includes("Did these 2 items sell?"), `${id} noemt beide artikelen`);
  eis(vak.innerHTML.includes("(1314)") && vak.innerHTML.includes("(1288)"),
      `${id} toont de titels`);
  eis(vak.innerHTML.includes("Yes, sold") && vak.innerHTML.includes(">No<"),
      `${id} heeft beide knoppen`);
  eis(vak.innerHTML.includes("none of this counts towards your revenue until you answer"),
      `${id} zegt dat het nog niet meetelt in de omzet`);
}
// De oudere advertentie krijgt de nuance dat hij ook verlopen kán zijn.
eis(vakken["an-sold-confirm-bar"].innerHTML.includes("adverts expire after 30"),
    "een advertentie ouder dan 28 dagen krijgt de verlopen-nuance");

// En zonder verdenkingen blijven beide vakken leeg en onzichtbaar.
state.listings = state.listings.map(l => ({ ...l, status: "active" }));
// eslint-disable-next-line no-new-func
new Function("document", "state", "esc", "PLATFORM_ICONS", "PLATFORM_LABELS",
  bron + "\nrenderSoldConfirmBar();")(document, state, esc, PLATFORM_ICONS, PLATFORM_LABELS);
for (const id of ["sold-confirm-bar", "an-sold-confirm-bar"]) {
  eis(vakken[id].style.display === "none" && vakken[id].innerHTML === "",
      `${id} verdwijnt weer als er niets te vragen valt`);
}

console.log(fouten ? `\n${fouten} fout(en)` : "\nAlles goed.");
process.exit(fouten ? 1 : 0);
