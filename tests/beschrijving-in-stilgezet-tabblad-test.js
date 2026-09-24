/**
 * Daniel, 24-09-2026: "ik moet constant handmatig bij Marktplaats op publiceren
 * drukken". Vier van de zeven Marktplaats-plaatsingen van die ochtend strandden
 * op "The description could not be placed into the editor".
 *
 * DE GEMETEN OORZAAK, uit de voortgang van zijn eigen opdrachten:
 *
 *   09:40:57  klokstand: 0.2/s +33868ms visible+focus
 *   09:42:18  klokstand: 0.0/s +64097ms visible+focus
 *   09:42:27  beschrijving: FOUT — The description could not be placed into the editor
 *
 * Het werktabblad stond op de achtergrond in zijn eigen venster en Chrome liet de
 * klok daar nog maar eens per minuut tikken. Het tekstvak zelf is niets mis mee:
 * in zijn eigen Chrome nagemeten zet Lexical's eigen update de tekst er binnen
 * 9 ms in, ook in een verborgen tabblad. Maar de invulfunctie wachtte daarna nog
 * op twee korte klokjes (150 ms en 250 ms). In een stilgezet tabblad komen die pas
 * bij de volgende tik, en in diezelfde tik gaat ook de wachttijd van 8 seconden
 * van de extensie af. Die wint: "niet gelukt", met een formulier dat gewoon
 * gevuld had kunnen worden. Het tabblad blijft daarna half ingevuld staan en de
 * verkoper drukt zelf op plaatsen.
 *
 * Deze test draait de ECHTE _mwFillDescription uit background.js tegen een
 * nagebootste Lexical-editor, met een klok die alleen elke 60 seconden tikt, en
 * de wachttijd van runInMainWorld uit shared.js ernaast.
 *
 * Draaien: node tests/beschrijving-in-stilgezet-tabblad-test.js
 */
const fs = require("fs");
const path = require("path");

const BG = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const SHARED = fs.readFileSync(path.join(__dirname, "..", "extension", "content", "shared.js"), "utf8");
let mislukt = 0;
function check(naam, voorwaarde, uitleg) {
  if (voorwaarde) { console.log(`  ok   ${naam}`); return; }
  mislukt++;
  console.log(`  FOUT ${naam}${uitleg ? " — " + uitleg : ""}`);
}

function functieUit(bron, kop) {
  const start = bron.indexOf(kop);
  if (start < 0) throw new Error("niet gevonden: " + kop);
  let diepte = 0;
  for (let i = bron.indexOf("{", start); i < bron.length; i++) {
    if (bron[i] === "{") diepte++;
    else if (bron[i] === "}" && --diepte === 0) return bron.slice(start, i + 1);
  }
  throw new Error("geen einde: " + kop);
}

// ── Een klok die alleen elke minuut tikt (Chrome's intensieve afknijping) ──
let nu = 0;
let timers = [];
let volg = 0;
function zetTimer(cb, ms) {
  const deadline = nu + (ms || 0);
  timers.push({ cb, deadline, wek: Math.ceil(deadline / 60000) * 60000 || 60000, volg: volg++ });
  return volg;
}
function wisTimer() {}
async function draaiTot(klaar, maxMs) {
  for (;;) {
    await new Promise((r) => setImmediate(r));       // alle microtaken eerst
    if (klaar()) return;
    if (!timers.length || nu > maxMs) return;
    const wek = Math.min(...timers.map((t) => t.wek));
    nu = wek;
    const nuAan = timers.filter((t) => t.wek === wek).sort((a, b) => a.deadline - b.deadline || a.volg - b.volg);
    timers = timers.filter((t) => t.wek !== wek);
    for (const t of nuAan) { t.cb(); await new Promise((r) => setImmediate(r)); }
  }
}

// ── Nagebootste Lexical-editor: update() zet de staat meteen, zoals de echte ──
function maakEditor() {
  const kaart = new Map();
  class Knoop {
    constructor() { this.kinderen = []; this.ouder = null; }
    append(k) { k.ouder = this; this.kinderen.push(k); return this; }
    remove() { if (this.ouder) this.ouder.kinderen = this.ouder.kinderen.filter((x) => x !== this); }
    getFirstChild() { return this.kinderen[0] || null; }
    getNextSibling() { const k = this.ouder?.kinderen || []; return k[k.indexOf(this) + 1] || null; }
  }
  class Alinea extends Knoop {}
  class Tekst extends Knoop { constructor(t) { super(); this.__text = t; } }
  const root = new Knoop();
  kaart.set("root", root);
  const editor = {
    _nodes: new Map([["paragraph", { klass: Alinea }], ["text", { klass: Tekst }]]),
    _editorState: { _nodeMap: kaart },
    update(fn, opts) {
      fn();
      kaart.clear(); kaart.set("root", root);
      let n = 0;
      for (const p of root.kinderen) for (const t of p.kinderen) kaart.set(String(n++), t);
      queueMicrotask(() => opts && opts.onUpdate && opts.onUpdate());
    },
    regels() { return root.kinderen.map((p) => p.kinderen.map((t) => t.__text).join("")); },
  };
  return editor;
}

async function vulIn(fnBron, tekst) {
  nu = 0; timers = []; volg = 0;
  const editor = maakEditor();
  const el = {
    isContentEditable: true, parentElement: null, __lexicalEditor: editor,
    scrollIntoView() {}, focus() {},
    querySelectorAll() { return []; },
    get innerText() { return editor.regels().join("\n"); },
    get textContent() { return editor.regels().join(""); },
  };
  const omgeving = {
    document: { querySelector: () => el, execCommand: () => false, createRange: () => ({ selectNodeContents() {}, collapse() {} }) },
    window: {}, getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
    HTMLTextAreaElement: class {}, HTMLInputElement: class {},
    setTimeout: zetTimer, clearTimeout: wisTimer,
    DataTransfer: class { setData() {} }, ClipboardEvent: class {}, InputEvent: class {}, Event: class {},
  };
  const fn = new Function(...Object.keys(omgeving), fnBron + "\nreturn _mwFillDescription;")(...Object.values(omgeving));

  // runInMainWorld zoals in shared.js: de wachttijd loopt op dezelfde klok.
  const wacht = Number((functieUit(SHARED, "function runInMainWorld").match(/timeoutMs\s*=\s*(\d+)/) || [])[1]);
  const fillDescBron = functieUit(SHARED, "async function fillDescription(");
  const m = fillDescBron.match(/runInMainWorld\("FILL_DESC",\s*\{[^}]*\}\s*(?:,\s*(\d+))?\)/);
  const wachttijd = Number(m && m[1]) || wacht;
  let uitkomst;
  zetTimer(() => { if (uitkomst === undefined) uitkomst = "wachttijd verstreken"; }, wachttijd);
  fn('[data-testid="text-editor-input_nl-NL"]', tekst).then((ok) => { if (uitkomst === undefined) uitkomst = ok; });
  await draaiTot(() => uitkomst !== undefined, 10 * 60000);
  return { uitkomst, regels: editor.regels(), seconden: nu / 1000 };
}

(async () => {
  const tekst = "Authentieke designer coltrui van Ralph Lauren in maat XL.\nDit item is in zeer goede staat!\n\nMateriaal: Katoen\nConditie: 7-8/10 (Zeer goed)\n\nVragen zijn welkom.";
  console.log("Beschrijving invullen in een tabblad waar de klok eens per minuut tikt:");
  const r = await vulIn(functieUit(BG, "async function _mwFillDescription("), tekst);
  check("de beschrijving telt als gelukt", r.uitkomst === true,
    `uitkomst: ${r.uitkomst} na ${r.seconden}s, terwijl de editor al ${r.regels.filter(Boolean).length} regels had`);
  check("de alinea's staan in de editor", r.regels.join("\n") === tekst);
  console.log(mislukt ? `\n${mislukt} fout(en)` : "\nalles ok");
  process.exit(mislukt ? 1 : 0);
})();
