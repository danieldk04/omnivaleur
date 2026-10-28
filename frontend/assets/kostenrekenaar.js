/* Gratis kostenrekenaar voor Marktplaats, 2dehands, Vinted en eBay.nl.
 *
 * Tarieven gecontroleerd op 28-10-2026 bij de helppagina's van de kanalen zelf
 * (bronnen staan op de pagina). Verandert een tarief, pas dan alleen KANALEN
 * hieronder aan en de datum + bronregels op de twee pagina's.
 *
 * Staat bewust los van het dashboard: de pagina is openbaar, zonder inlog.
 */
(function (root) {
  'use strict';

  // eBay.nl zakelijk: percentage en drempel verschillen per rubriek (ebay.nl help 4809).
  // Particulier heeft één drempel voor alles (ebay.nl help 4822).
  var EBAY_RUBRIEKEN = {
    standaard: { rate: 0.11, drempel: 990 },
    sieraden: { rate: 0.11, drempel: 400 },
    muziek: { rate: 0.11, drempel: 300 },
    foto: { rate: 0.065, drempel: 300 },
    tuin: { rate: 0.11, drempel: 200 }
  };

  // Verkoopkosten van de verkoper over het totaal (artikel + verzendkosten die de koper betaalt).
  function ebayKosten(totaal, o) {
    var t = Math.max(0, totaal);
    if (o.verkoper === 'zakelijk') {
      var r = EBAY_RUBRIEKEN[o.rubriek] || EBAY_RUBRIEKEN.standaard;
      var commissie = r.rate * Math.min(t, r.drempel) + 0.02 * Math.max(0, t - r.drempel);
      return commissie + (t > 10 ? 0.45 : 0.35) + 0.0035 * t;
    }
    var comm = 0.11 * Math.min(t, 1990) + 0.02 * Math.max(0, t - 1990);
    return comm + (t < 10 ? 0.05 : 0.35) + 0.0042 * t;
  }

  var KANALEN = [
    { key: 'marktplaats', naam: 'Marktplaats', kosten: function () { return 0; } },
    { key: '2dehands', naam: '2dehands', kosten: function () { return 0; } },
    { key: 'vinted', naam: 'Vinted', kosten: function () { return 0; } },
    { key: 'ebay', naam: 'eBay', kosten: function (prijs, o) { return ebayKosten(prijs + (o.verzend || 0), o); } }
  ];

  function kanaal(key) {
    for (var i = 0; i < KANALEN.length; i++) if (KANALEN[i].key === key) return KANALEN[i];
    throw new Error('onbekend kanaal ' + key);
  }

  function opties(o) {
    o = o || {};
    return { verkoper: o.verkoper === 'zakelijk' ? 'zakelijk' : 'particulier', rubriek: o.rubriek || 'standaard', verzend: Math.max(0, o.verzend || 0) };
  }

  // Wat de verkoper overhoudt na kosten en inkoop, bij een gevraagde artikelprijs.
  function winstBij(key, prijs, inkoop, o) {
    o = opties(o);
    return prijs - kanaal(key).kosten(prijs, o) - inkoop;
  }

  // Laagste prijs (in hele centen, naar boven) waarbij de winst minstens `winst` is.
  // De kosten stijgen vlak minder snel dan de prijs (marginaal hoogstens 13,5%), dus
  // winstBij groeit met de prijs en halveren werkt.
  function vraagprijs(key, inkoop, winst, o) {
    o = opties(o);
    var nodig = inkoop + winst;
    if (!(nodig > 0)) return 0;
    var lo = 0, hi = (nodig + 5) * 2 + 100;
    for (var i = 0; i < 80; i++) {
      var mid = (lo + hi) / 2;
      if (winstBij(key, mid, inkoop, o) >= winst) hi = mid; else lo = mid;
    }
    var cent = Math.ceil(hi * 100 - 1e-6) / 100;
    return cent;
  }

  // "1.360" is duizend driehonderdzestig, niet 1,36 (zie kennisbank: bedragveld-leest-duizendtalpunt-als-komma).
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

  var api = { KANALEN: KANALEN, ebayKosten: ebayKosten, winstBij: winstBij, vraagprijs: vraagprijs, leesBedrag: leesBedrag };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Kostenrekenaar = api;

  /* ── Scherm ─────────────────────────────────────────────────────────── */
  if (typeof document === 'undefined') return;

  var TEKST = {
    nl: {
      loc: 'nl-NL', geen: 'Geen verkoopkosten', kosten: 'Kosten', vraag: 'Vraagprijs', winst: 'Winst bij jouw prijs', marge: 'marge',
      leeg: 'Vul hierboven je inkoopprijs en gewenste winst in.', ongeldig: 'Dit is geen bedrag.',
      onder: 'Onder inkoop', ebayExtra: 'Over artikel plus verzendkosten, excl. btw'
    },
    en: {
      loc: 'en-GB', geen: 'No selling fees', kosten: 'Fees', vraag: 'Asking price', winst: 'Profit at your price', marge: 'margin',
      leeg: 'Enter your purchase price and desired profit above.', ongeldig: 'This is not an amount.',
      onder: 'Below cost', ebayExtra: 'On item plus shipping, excl. VAT'
    }
  };
  var taal = (document.documentElement.lang || 'en').slice(0, 2) === 'nl' ? 'nl' : 'en';
  var T = TEKST[taal];

  function euro(n) {
    return new Intl.NumberFormat(T.loc, { style: 'currency', currency: 'EUR' }).format(n);
  }
  function el(id) { return document.getElementById(id); }
  function veld(id) {
    var raw = el(id).value.trim();
    var fout = el(id + '-fout');
    if (!raw) { if (fout) fout.textContent = ''; return null; }
    var n = leesBedrag(raw);
    if (fout) fout.textContent = isNaN(n) || n < 0 ? T.ongeldig : '';
    return isNaN(n) || n < 0 ? NaN : n;
  }

  function teken() {
    var inkoop = veld('kr-inkoop'), winst = veld('kr-winst'), prijs = veld('kr-prijs');
    var verzend = veld('kr-verzend');
    var uit = el('kr-resultaten');
    var o = { verkoper: el('kr-verkoper').value, rubriek: el('kr-rubriek').value, verzend: verzend || 0 };
    el('kr-rubriek-rij').style.display = o.verkoper === 'zakelijk' ? '' : 'none';
    if (isNaN(inkoop) || isNaN(winst) || isNaN(prijs) || isNaN(verzend) || (inkoop === null && winst === null)) {
      uit.innerHTML = '<p class="kr-leeg">' + T.leeg + '</p>';
      return;
    }
    inkoop = inkoop || 0; winst = winst || 0;
    var rijen = KANALEN.map(function (k) {
      var vraag = vraagprijs(k.key, inkoop, winst, o);
      var kosten = k.kosten(vraag, o);
      var kostTekst = kosten === 0 && k.key !== 'ebay' ? T.geen : euro(kosten) + (vraag ? ' (' + (kosten / vraag * 100).toFixed(1).replace('.', taal === 'nl' ? ',' : '.') + '%)' : '');
      var cel3 = '';
      if (prijs !== null) {
        var w = winstBij(k.key, prijs, inkoop, o);
        var m = prijs > 0 ? ' · ' + Math.round(w / prijs * 100) + '% ' + T.marge : '';
        cel3 = '<td class="kr-num' + (w < 0 ? ' kr-neg' : '') + '">' + euro(w) + m + '</td>';
      }
      return '<tr><th scope="row">' + k.naam + '</th><td class="kr-num kr-groot">' + euro(vraag) + '</td><td>' + kostTekst + '</td>' + cel3 + '</tr>';
    }).join('');
    uit.innerHTML = '<div class="table-wrap"><table class="kr-tabel"><thead><tr><th></th><th>' + T.vraag + '</th><th>' + T.kosten + '</th>' +
      (prijs !== null ? '<th>' + T.winst + '</th>' : '') + '</tr></thead><tbody>' + rijen + '</tbody></table></div>';
  }

  function start() {
    ['kr-inkoop', 'kr-winst', 'kr-prijs', 'kr-verzend'].forEach(function (id) { el(id).addEventListener('input', teken); });
    ['kr-verkoper', 'kr-rubriek'].forEach(function (id) { el(id).addEventListener('change', teken); });
    teken();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})(typeof window !== 'undefined' ? window : globalThis);
