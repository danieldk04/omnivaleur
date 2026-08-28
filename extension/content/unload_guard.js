// Draait in de HOOFDWERELD van de pagina, meteen bij het laden.
//
// WAAROM DIT BESTAAT.
//
// Marktplaats en 2dehands hangen aan hun plaatsformulier een "Site verlaten?
// Wijzigingen die je hebt aangebracht worden mogelijk niet opgeslagen"-vraag.
// Sluiten wij zo'n tabblad (na een geplaatste of mislukte advertentie), dan
// stelt Chrome die vraag aan de verkoper — en tot hij "Verlaten" aanklikt staat
// ALLES stil. Ook het volgende tabblad: twee tabbladen van dezelfde site delen
// één proces, dus een venstertje in het ene bevriest het script in het andere.
// Dat is precies wat de verkoper meldde: het invullen bleef hangen, hij moest
// zelf op "Verlaten" klikken, en meteen daarna werd er geplaatst.
//
// Deze wacht doet uit zichzelf NIETS. Hij onthoudt alleen welke beforeunload-
// meldingen de pagina aanzet. Pas als de extensie zelf op het punt staat het
// tabblad te sluiten of weg te navigeren, roept zij __ovDisarmUnload() aan en
// worden ze weggehaald. Bladert de verkoper zelf weg van een half ingevuld
// formulier, dan krijgt hij zijn waarschuwing gewoon.
(() => {
  try {
    if (window.__ovUnloadGuard) return;
    window.__ovUnloadGuard = true;

    const origAdd = EventTarget.prototype.addEventListener;
    const origRemove = EventTarget.prototype.removeEventListener;
    const geregistreerd = [];
    let ontwapend = false;

    EventTarget.prototype.addEventListener = function (type, fn, opts) {
      try {
        if (String(type).toLowerCase() === "beforeunload") {
          if (ontwapend) return undefined;   // niets meer aannemen
          geregistreerd.push({ doel: this, fn, opts });
        }
      } catch (_) { /* nooit de pagina breken */ }
      return origAdd.call(this, type, fn, opts);
    };

    window.__ovDisarmUnload = function () {
      ontwapend = true;
      try { window.onbeforeunload = null; } catch (_) {}
      try { if (document.body) document.body.onbeforeunload = null; } catch (_) {}
      let weg = 0;
      for (const r of geregistreerd.splice(0)) {
        try { origRemove.call(r.doel, "beforeunload", r.fn, r.opts); weg++; } catch (_) {}
      }
      return weg;
    };
  } catch (_) { /* niets aan de hand: dan blijft alles zoals het was */ }
})();
