/**
 * Vangt op de Admarkt-pagina op wat de pagina zélf aan gegevens ophaalt.
 *
 * WAAROM DIT BESTAAT
 * De eerste opzet haalde na het laden de adressen uit `performance` en vroeg ze
 * daarna nog een keer op. Dat is op deze site om twee redenen niet goed genoeg,
 * allebei gemeten op admarkt.marktplaats.nl (16-08-2026):
 *
 *   1. De site haalt een CSRF-sleutel op (/csrf-token). Zijn de gegevens dus een
 *      POST, dan levert ons eigen GET-verzoek nooit hetzelfde op.
 *   2. Elk onbekend adres geeft HTTP 200 mét de gewone pagina terug in plaats van
 *      een 404. Raden naar een adres levert daardoor altijd "gelukt" op en nooit
 *      een bruikbaar antwoord — je merkt je fout niet.
 *
 * Meekijken lost allebei op: we vragen niets zelf op, we lezen mee met wat de
 * pagina toch al doet. Methode, adres, sleutels en cookies kloppen dan per
 * definitie, want het is het verzoek van de pagina zelf.
 *
 * Dit script MOET vóór de pagina-code draaien (document_start, in de wereld van
 * de pagina), anders heeft de app haar gegevens al binnen voordat wij kijken.
 * Het wordt aangemeld zodra de gebruiker de Admarkt-schakelaar aanzet.
 *
 * Het leest alleen mee en verstuurt zelf niets.
 */
(() => {
  if (window.__omnivaleurVangst) return;      // al geplaatst
  const vangst = [];
  window.__omnivaleurVangst = vangst;

  const MAX = 40;                              // ruim genoeg, en geen geheugenlek
  const INTERESSANT = /json/i;

  function bewaar(methode, url, tekst, type) {
    if (vangst.length >= MAX) return;
    if (!tekst || !INTERESSANT.test(type || "")) return;
    // Vertalingen en toestemmingsbestanden zijn json maar nooit advertenties.
    if (/\/(locales|csrf-token|consent)\b/i.test(url)) return;
    vangst.push({ methode, url, tekst: tekst.slice(0, 400000) });
  }

  const echteFetch = window.fetch;
  window.fetch = function (...args) {
    const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
    const methode = (args[1] && args[1].method) || (args[0] && args[0].method) || "GET";
    return echteFetch.apply(this, args).then((res) => {
      // KLONEN, nooit het origineel uitlezen: doe je dat wel, dan is de body op
      // voor de pagina zelf en breekt de site waar de gebruiker naar kijkt.
      try {
        const kopie = res.clone();
        const type = kopie.headers.get("content-type") || "";
        if (INTERESSANT.test(type)) kopie.text().then(t => bewaar(methode, url, t, type)).catch(() => {});
      } catch (_) {}
      return res;
    });
  };

  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__ovMethode = m; this.__ovUrl = u;
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener("load", () => {
      try {
        bewaar(this.__ovMethode, this.__ovUrl, this.responseText,
               this.getResponseHeader("content-type"));
      } catch (_) {}
    });
    return send.apply(this, arguments);
  };
})();
