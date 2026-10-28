/* Gedeelde stukjes voor de gratis tools (/tools). Geen afhankelijkheden.
 * leesBedrag: "1.360" is duizend driehonderdzestig, niet 1,36 (zie kennisbank:
 * bedragveld-leest-duizendtalpunt-als-komma). */
(function (root) {
  'use strict';
  function leesBedrag(tekst) {
    var s = String(tekst == null ? '' : tekst).replace(/[€\s]/g, '');
    if (!s) return NaN;
    var komma = s.lastIndexOf(','), punt = s.lastIndexOf('.');
    if (komma >= 0 && punt >= 0) {
      s = komma > punt ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, '');
    } else if (komma >= 0) {
      s = /^\d{1,3}(,\d{3})+$/.test(s) ? s.replace(/,/g, '') : s.replace(',', '.');
    } else if (punt >= 0 && /^\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, '');
    }
    return /^\d*\.?\d+$|^\d+\.$/.test(s) ? parseFloat(s) : NaN;
  }
  var G = { leesBedrag: leesBedrag };
  if (typeof module !== 'undefined' && module.exports) module.exports = G;
  root.ToolsGedeeld = G;
  if (typeof document === 'undefined') return;

  G.taal = (document.documentElement.lang || 'en').slice(0, 2) === 'nl' ? 'nl' : 'en';
  G.el = function (id) { return document.getElementById(id); };
  G.euro = function (n) {
    return new Intl.NumberFormat(G.taal === 'nl' ? 'nl-NL' : 'en-GB', { style: 'currency', currency: 'EUR' }).format(n);
  };
  G.getal = function (n) {
    return new Intl.NumberFormat(G.taal === 'nl' ? 'nl-NL' : 'en-GB').format(n);
  };
  // Leest een bedragveld. null = leeg, NaN = geen bedrag (de foutregel #<id>-fout wordt gevuld).
  G.veld = function (id, foutTekst) {
    var raw = G.el(id).value.trim(), fout = G.el(id + '-fout');
    if (!raw) { if (fout) fout.textContent = ''; return null; }
    var n = leesBedrag(raw), slecht = isNaN(n) || n < 0;
    if (fout) fout.textContent = slecht ? foutTekst : '';
    return slecht ? NaN : n;
  };
  G.bijWijziging = function (ids, fn) {
    function start() {
      ids.forEach(function (id) {
        var e = G.el(id);
        e.addEventListener(e.tagName === 'SELECT' ? 'change' : 'input', fn);
      });
      fn();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  };
})(typeof window !== 'undefined' ? window : globalThis);
