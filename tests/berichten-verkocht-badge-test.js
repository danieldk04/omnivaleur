/**
 * De verkocht-badge in de berichtenlijst van Marktplaats.
 *
 * WAAROM DIT ER IS (01-09-2026, Daniel). "De enige manier dat ik zelf kan
 * controleren of iets op Marktplaats echt verkocht is, is via de verkocht
 * badge." Die badge staat op het GESPREK, niet op de advertentie — daarom zag
 * de app een handmatige verkoop nooit. De berichtenpagina wordt toch al elk
 * kwartier geopend om berichten te tellen, dus de badge wordt daar meegelezen.
 *
 * Deze proef draait de ECHTE leesroutine uit extension/background.js tegen een
 * namaaklijst die is nagebouwd op Daniels eigen scherm — inclusief de vallen
 * waar een verkeerde lezing op zou stranden.
 *
 * Draaien:  node tests/berichten-verkocht-badge-test.js
 */
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.resolve(__dirname, "..", "extension", "background.js"), "utf8");
const start = SRC.indexOf("async function _mwReadNotifCounts(platform) {");
if (start < 0) { console.error("_mwReadNotifCounts niet gevonden in background.js"); process.exit(1); }
const eind = SRC.indexOf("\n}\n", start);
const LEZER = SRC.slice(start, eind + 2);

// ── Namaakscherm ───────────────────────────────────────────────────────────
// Een gespreksrij zoals Marktplaats hem opbouwt: een titelregel, de tegenpartij,
// een voorbeeld van het laatste bericht, eventueel een los groen labeltje, en de
// datum. De badge is een eigen elementje met exact "Verkocht!" erin.
function el(tekst, klasse) {
  return { textContent: tekst, children: [], _class: klasse || "" };
}

function rij({ titel, van, voorbeeld, badge, datum, ongelezen }) {
  const kinderen = [el(titel), el(van), el(voorbeeld)];
  if (badge) kinderen.push(el(badge));
  kinderen.push(el(datum));
  if (ongelezen) kinderen.push(el(voorbeeld, "u-textStyleBodySmallStrong"));
  const regels = [titel, van, voorbeeld];
  if (badge) regels.push(badge);
  regels.push(datum);
  return {
    innerText: regels.join("\n"),
    textContent: regels.join(" "),
    querySelectorAll: () => kinderen,
    querySelector: (sel) =>
      kinderen.find((k) => sel.includes("u-textStyleBodySmallStrong") && k._class.includes("u-textStyleBodySmallStrong")) || null,
  };
}

const RIJEN = [
  // Uit Daniels scherm: drie gesprekken met een verkocht-badge.
  rij({ titel: "(641) Blauw Ralph Lauren Half Zip - Heren M", van: "aan Sybrand",
        voorbeeld: "Hi! Jazeker, vandaag al :) dank voor je aankoop", badge: "Verkocht!", datum: "vandaag" }),
  rij({ titel: "(1308) Marine Profuomo Half Zip - Heren S", van: "van Marktplaats",
        voorbeeld: "Je hebt het product overhandigd en het is onderweg…", badge: "Verkocht!", datum: "gisteren", ongelezen: true }),
  rij({ titel: "(1348) Marineblauw Massimo Dutti Trui", van: "van Marktplaats",
        voorbeeld: "Alles is in orde. Je ontvangt je geld meestal binnen é…", badge: "Verkocht!", datum: "vr 21 aug." }),

  // Wél een gesprek, géén badge: dit artikel is niet aantoonbaar verkocht.
  rij({ titel: "(1314) Donkergroen Suitable Half Zip", van: "van Marco R",
        voorbeeld: "[Betaling]", datum: "wo 19 aug.", ongelezen: true }),

  // VAL 1: het woord "verkocht" middenin een berichtvoorbeeld. Mag nooit tellen —
  // anders boekt een vraag van een koper een verkoop.
  rij({ titel: "(1296) Lichtblauwe Suitsupply trui", van: "aan van Laar",
        voorbeeld: "Is deze al verkocht of nog te koop?", datum: "za 15 aug." }),

  // VAL 2: een badge op iets wat niet uit deze app komt (geen nummer voor de
  // titel). Er valt niets aan te koppelen, dus overslaan in plaats van gokken.
  rij({ titel: "Apple Watch Series 7 - 41mm Aluminium", van: "van Marktplaats",
        voorbeeld: "Je betaalverzoek is verlopen.", badge: "Verkocht!", datum: "zondag" }),

  // VAL 3: een getal tussen haakjes MIDDENIN de tekst. Alleen het nummer aan het
  // begin van een regel is de advertentietitel.
  rij({ titel: "(853) Blauw/Wit Suitsupply Jumper", van: "van Noella",
        voorbeeld: "ik bied (1300) als je hem vandaag opstuurt", badge: "Verkocht!", datum: "do 13 aug." }),

  // VAL 4: hetzelfde gesprek twee keer in beeld mag niet twee verkopen opleveren.
  rij({ titel: "(641) Blauw Ralph Lauren Half Zip - Heren M", van: "aan Sybrand",
        voorbeeld: "Top, bedankt!", badge: "Verkocht!", datum: "vandaag" }),
];

const document = {
  body: { innerText: "Berichten" },
  querySelectorAll: (sel) => (sel.includes("ConversationItem-module-root") ? RIJEN : []),
};

let fouten = 0;
const eis = (ok, wat) => { console.log(`  ${ok ? "ok  " : "FOUT"} ${wat}`); if (!ok) fouten++; };

(async () => {
  // eslint-disable-next-line no-new-func
  const lees = new Function("document", `${LEZER}; return _mwReadNotifCounts;`)(document);
  const uit = await lees("marktplaats");

  console.log("Verkocht-badges uit de berichtenlijst:");
  const skus = (uit.sold || []).map((s) => s.sku);
  eis(skus.includes("641"), "(641) met badge wordt gevonden");
  eis(skus.includes("1308"), "(1308) met badge wordt gevonden");
  eis(skus.includes("1348"), "(1348) met badge wordt gevonden");
  eis(skus.includes("853"), "(853) met badge wordt gevonden");
  eis(!skus.includes("1314"), "(1314) zonder badge wordt NIET als verkocht gemeld");
  eis(!skus.includes("1296"), "'is deze al verkocht?' in een bericht telt niet als badge");
  eis(!skus.includes("1300"), "een getal middenin een bericht is geen advertentienummer");
  eis(skus.filter((s) => s === "641").length === 1, "hetzelfde artikel wordt maar één keer gemeld");
  eis(skus.length === 4, `precies vier meldingen (nu ${skus.length}: ${skus.join(", ")})`);
  eis((uit.sold[0].title || "").startsWith("(641) Blauw Ralph Lauren"),
      "de titel gaat mee zodat de melding leesbaar is");

  // De bestaande telling mag hier niet onder lijden.
  eis(uit.messages === 2, `berichtenteller blijft kloppen (nu ${uit.messages})`);

  // Geen enkele rij: dan ook geen verkopen, en geen null-ongeluk.
  const leeg = new Function("document", `${LEZER}; return _mwReadNotifCounts;`)(
    { body: { innerText: "Berichten" }, querySelectorAll: () => [] });
  const uit2 = await leeg("marktplaats");
  eis(uit2 && uit2.messages === 0 && !(uit2.sold || []).length,
      "een lege lijst levert geen verkopen op");

  console.log(fouten ? `\n${fouten} fout(en)` : "\nAlles goed.");
  process.exit(fouten ? 1 : 0);
})();
