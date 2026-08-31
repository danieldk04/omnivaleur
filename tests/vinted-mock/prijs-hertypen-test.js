// Draait de ECHTE prijsroutine uit extension/content/vinted.js tegen een
// namaakformulier. De code wordt uit het verscheepte bestand gesneden, zodat
// deze proef nooit een verouderde kopie test.
//
// AANLEIDING 31-08-2026. Het veld toonde €19.99 en Vinted bleef roepen "Price
// must be greater than or equal to 1.0". Daniel vond de handeling die het wél
// oplost: één teken met de hand vervangen door hetzelfde teken. Dat zit nu als
// laatste route in de code. Wat hier wordt vastgelegd:
//   1. helpt gewoon typen, dan is die laatste route niet nodig;
//   2. helpt alleen het vervangen van één teken, dan redt die route het;
//   3. helpt niets, dan zeggen we dat ook — nooit "gelukt" bij een prijs waar
//      het formulier zichtbaar over klaagt.
const fs = require("fs");
const path = require("path");

const SRC = fs.readFileSync(path.resolve(__dirname, "../../extension/content/vinted.js"), "utf8");
const start = SRC.indexOf("  async function fillPriceVinted(price) {");
const eind = SRC.indexOf("  // ---- CATEGORY:");
if (start < 0 || eind < 0 || eind <= start) {
  console.error("de prijsroutine is niet te vinden in vinted.js — is het blok hernoemd?");
  process.exit(1);
}

// Namaakveld: een gemaskeerd, React-gestuurd invoerveld. Het toont wat je erin
// zet, maar het FORMULIER accepteert de waarde alleen langs de weg die deze
// proef openzet. Dat onderscheid is precies het probleem uit de praktijk.
function maakVeld({ accepteertTypen, accepteertHertypen }) {
  const veld = {
    _tekst: "",
    focus() {},
    select() {},
    setSelectionRange(a, b) { this._sel = [a, b]; },
    getAttribute(naam) { return naam === "placeholder" ? "€0.00" : null; },
    scrollIntoView() {},
    dispatchEvent() { return true; },
    // Wat het formulier zelf vasthoudt. Zolang dit niet klopt blijft de rode
    // regel staan, ook al toont het veld de goede prijs.
    formulierWaarde: "",
  };
  Object.defineProperty(veld, "value", {
    get() { return this._tekst; },
    set(v) { this._tekst = String(v); },   // zetten zonder dat het formulier meekijkt
    configurable: true,
  });
  veld._typ = (tekst, viaHertypen) => {
    veld._tekst = tekst;
    if (viaHertypen ? accepteertHertypen : accepteertTypen) veld.formulierWaarde = tekst;
  };
  return veld;
}

function omgeving(veld) {
  const window = {
    HTMLInputElement: {
      prototype: Object.create(Object.prototype, {
        value: {
          set(v) { this._tekst = String(v); },   // de "native setter"
          get() { return this._tekst; },
          configurable: true,
        },
      }),
    },
  };
  const document = {
    documentElement: { getAttribute: () => "en-NL" },
    execCommand(cmd, _ui, arg) {
      // De bewerkroute van de browser zelf: dit is de weg die een toetsaanslag
      // ook aflegt. Vervangen van één teken telt hier als "hertypen".
      if (cmd === "selectAll") { veld._sel = [0, veld._tekst.length]; return true; }
      if (cmd === "delete") {
        veld._typ(veld._tekst.slice(0, -1), true);
        return true;
      }
      if (cmd !== "insertText") return false;
      const [a, b] = veld._sel || [veld._tekst.length, veld._tekst.length];
      const heel = veld._tekst.length;
      const vervangtEenTeken = b - a === 1 && b === heel;
      const nieuw = veld._tekst.slice(0, a) + arg + veld._tekst.slice(b);
      veld._typ(nieuw, vervangtEenTeken || veld._sel === undefined ? vervangtEenTeken : false);
      veld._sel = [nieuw.length, nieuw.length];
      return true;
    },
  };
  const chrome = {
    runtime: {
      // De route via de pagina zelf lukt in de praktijk niet; dat is het geval
      // dat we hier naspelen.
      sendMessage: (_m, cb) => cb({ ok: false, reason: "rejected" }),
    },
  };
  return { window, document, chrome };
}

function _num(v) {
  const s = String(v ?? "").replace(/[^\d.,]/g, "").replace(",", ".");
  const n = parseFloat(s);
  return isFinite(n) ? n : NaN;
}

async function draai(veld) {
  const { window, document, chrome } = omgeving(veld);
  const sleep = () => Promise.resolve();
  const clog = () => {};
  // De rode regel staat er zolang het formulier de prijs niet heeft aangenomen.
  const priceErrorAfterSettle = async () =>
    (_num(veld.formulierWaarde) >= 1 ? null : "Price must be greater than or equal to 1.0");
  // De gebeurtenissen die de code afvuurt bestaan niet in Node; ze doen er hier
  // ook niet toe, want dit namaakveld luistert er (net als het echte) niet naar.
  const Event = function (naam) { this.type = naam; };
  const InputEvent = Event;
  const KeyboardEvent = Event;
  const maak = new Function(
    "window", "document", "chrome", "qs", "sleep", "clog", "_num", "priceErrorAfterSettle",
    "Event", "InputEvent", "KeyboardEvent",
    SRC.slice(start, eind) + "\nreturn { fillPriceVinted };");
  const { fillPriceVinted } = maak(window, document, chrome, () => veld,
    sleep, clog, _num, priceErrorAfterSettle, Event, InputEvent, KeyboardEvent);
  return await fillPriceVinted(19.99);
}

const proeven = [];
function proef(naam, fn) { proeven.push([naam, fn]); }

proef("gewoon typen is genoeg: prijs geaccepteerd", async () => {
  const veld = maakVeld({ accepteertTypen: true, accepteertHertypen: true });
  const ok = await draai(veld);
  return ok === true && _num(veld.formulierWaarde) === 19.99;
});

proef("alleen één teken vervangen werkt: dat is precies wat er nu gebeurt", async () => {
  const veld = maakVeld({ accepteertTypen: false, accepteertHertypen: true });
  const ok = await draai(veld);
  return ok === true && _num(veld.value) === 19.99 && _num(veld.formulierWaarde) === 19.99;
});

proef("helpt niets, dan zeggen we NIET dat het gelukt is", async () => {
  const veld = maakVeld({ accepteertTypen: false, accepteertHertypen: false });
  const ok = await draai(veld);
  return ok === false;
});

proef("de prijs blijft staan zoals hij was, hertypen verandert hem niet", async () => {
  const veld = maakVeld({ accepteertTypen: false, accepteertHertypen: true });
  await draai(veld);
  return _num(veld.value) === 19.99;
});

(async () => {
  let stuk = 0;
  for (const [naam, fn] of proeven) {
    let uitkomst = false;
    try { uitkomst = await fn(); } catch (e) { uitkomst = false; console.error("   " + e.message); }
    console.log(`${uitkomst ? "ok  " : "STUK"}  ${naam}`);
    if (!uitkomst) stuk++;
  }
  process.exit(stuk ? 1 : 0);
})();
